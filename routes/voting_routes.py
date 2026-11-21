from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)
from datetime import datetime
import secrets

from database import get_db_connection


# =========================================================
# BLUEPRINT
# =========================================================

voting_bp = Blueprint(
    "voting",
    __name__,
    url_prefix="/vote"
)


# =========================================================
# ELECTION STATUS CHECK
# =========================================================

def is_election_open(election):

    if not election:
        return False

    if str(election.get("status", "")).upper() != "ACTIVE":
        return False

    now = datetime.now()

    start_time = election.get("start_datetime")
    end_time = election.get("end_datetime")

    if start_time and now < start_time:
        return False

    if end_time and now > end_time:
        return False

    return True


# =========================================================
# GET ACTIVE ELECTION
# =========================================================

def get_active_election(voting_token):

    connection = get_db_connection()

    if not connection:
        return None

    cursor = None

    try:

        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM elections
            WHERE voting_token = %s
            LIMIT 1
            """,
            (voting_token,)
        )

        election = cursor.fetchone()

        if not election:
            return None

        if not is_election_open(election):
            return None

        return election

    finally:

        if cursor:
            cursor.close()

        connection.close()


# =========================================================
# VOTING PAGE
# URL: /vote/<voting_token>
# =========================================================

@voting_bp.route(
    "/<string:voting_token>",
    methods=["GET"]
)
def voting_page(voting_token):

    election = get_active_election(voting_token)

    if not election:

        return render_template(
            "vote/voting.html",
            election=None,
            positions=[],
            candidates={}
        )

    connection = get_db_connection()

    if not connection:
        return "Database connection failed", 500

    cursor = None

    try:

        cursor = connection.cursor(dictionary=True)

        # Get election positions
        cursor.execute(
            """
            SELECT *
            FROM positions
            WHERE election_id = %s
            ORDER BY id ASC
            """,
            (election["id"],)
        )

        positions = cursor.fetchall()

        # Get active candidates
        cursor.execute(
            """
            SELECT *
            FROM candidates
            WHERE election_id = %s
            AND status = 'ACTIVE'
            ORDER BY position_id ASC, name ASC
            """,
            (election["id"],)
        )

        candidate_rows = cursor.fetchall()

        # Group candidates position-wise
        candidates = {}

        for candidate in candidate_rows:

            position_id = candidate["position_id"]

            candidates.setdefault(
                position_id,
                []
            ).append(candidate)

        return render_template(
            "vote/voting.html",
            election=election,
            positions=positions,
            candidates=candidates
        )

    finally:

        if cursor:
            cursor.close()

        connection.close()


# =========================================================
# CANDIDATE PROFILE
# URL: /vote/<token>/candidate/<candidate_id>
# =========================================================

@voting_bp.route(
    "/<string:voting_token>/candidate/<int:candidate_id>",
    methods=["GET"]
)
def candidate_profile(voting_token, candidate_id):

    election = get_active_election(voting_token)

    if not election:
        return "Election is not active.", 403

    connection = get_db_connection()

    if not connection:
        return "Database connection failed", 500

    cursor = None

    try:

        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                c.*,
                p.position_name,
                e.title AS election_title
            FROM candidates c

            JOIN positions p
                ON c.position_id = p.id

            JOIN elections e
                ON c.election_id = e.id

            WHERE c.id = %s
            AND c.election_id = %s
            AND c.status = 'ACTIVE'
            """,
            (
                candidate_id,
                election["id"]
            )
        )

        candidate = cursor.fetchone()

        if not candidate:
            return "Candidate not found.", 404

        return render_template(
            "vote/candidate_profile.html",
            election=election,
            candidate=candidate,
            voting_token=voting_token
        )

    finally:

        if cursor:
            cursor.close()

        connection.close()


# =========================================================
# SUBMIT VOTE
# URL: /vote/<voting_token>/submit
# METHOD: POST
#
# STUDENT IDENTIFICATION: ROLL NUMBER
# =========================================================

@voting_bp.route(
    "/<string:voting_token>/submit",
    methods=["POST"]
)
def submit_vote(voting_token):

    def back_to_voting(message):

        flash(message, "error")

        return redirect(
            url_for(
                "voting.voting_page",
                voting_token=voting_token
            )
        )

    # -----------------------------------------------------
    # Get roll number from form
    # -----------------------------------------------------

    roll_number = request.form.get(
        "student_id",
        ""
    ).strip()

    if not roll_number:

        return back_to_voting(
            "Please enter your roll number."
        )

    connection = get_db_connection()

    if not connection:
        return "Database connection failed", 500

    cursor = None

    try:

        cursor = connection.cursor(dictionary=True)

        # Start transaction
        connection.start_transaction()

        # -------------------------------------------------
        # Lock and verify election
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM elections
            WHERE voting_token = %s
            FOR UPDATE
            """,
            (voting_token,)
        )

        election = cursor.fetchone()

        if not is_election_open(election):

            connection.rollback()

            return back_to_voting(
                "This election is not currently active."
            )

        # -------------------------------------------------
        # Verify student using ROLL NUMBER
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM students
            WHERE roll_number = %s
            AND status = 'ACTIVE'
            FOR UPDATE
            """,
            (roll_number,)
        )

        student = cursor.fetchone()

        if not student:

            connection.rollback()

            return back_to_voting(
                "Student not found or inactive. Please check your roll number."
            )

        # IMPORTANT:
        # Use database student ID for votes table.
        student_db_id = student["id"]

        # -------------------------------------------------
        # Get election positions
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM positions
            WHERE election_id = %s
            ORDER BY id ASC
            """,
            (election["id"],)
        )

        positions = cursor.fetchall()

        if not positions:

            connection.rollback()

            return back_to_voting(
                "No voting positions are available."
            )

        # -------------------------------------------------
        # Validate all candidate selections
        # -------------------------------------------------

        selected_votes = []

        for position in positions:

            field_name = f"position_{position['id']}"

            candidate_id = request.form.get(
                field_name,
                ""
            )

            if not candidate_id or not candidate_id.isdigit():

                connection.rollback()

                return back_to_voting(
                    f"Please select a candidate for {position['position_name']}."
                )

            candidate_id = int(candidate_id)

            # Verify candidate belongs to correct election
            # and correct position
            cursor.execute(
                """
                SELECT id
                FROM candidates
                WHERE id = %s
                AND election_id = %s
                AND position_id = %s
                AND status = 'ACTIVE'
                """,
                (
                    candidate_id,
                    election["id"],
                    position["id"]
                )
            )

            candidate = cursor.fetchone()

            if not candidate:

                connection.rollback()

                return back_to_voting(
                    "Invalid candidate selection."
                )

            selected_votes.append(
                (
                    election["id"],
                    position["id"],
                    candidate_id
                )
            )

        # -------------------------------------------------
        # Prevent duplicate voting
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT id
            FROM votes
            WHERE student_id = %s
            AND election_id = %s
            FOR UPDATE
            """,
            (
                student_db_id,
                election["id"]
            )
        )

        existing_votes = cursor.fetchall()

        if existing_votes:

            connection.rollback()

            return back_to_voting(
                "You have already voted in this election."
            )

        # -------------------------------------------------
        # Insert votes
        # -------------------------------------------------

        for election_id, position_id, candidate_id in selected_votes:

            vote_token = secrets.token_urlsafe(32)

            cursor.execute(
                """
                INSERT INTO votes (
                    election_id,
                    position_id,
                    candidate_id,
                    student_id,
                    vote_token
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    election_id,
                    position_id,
                    candidate_id,
                    student_db_id,
                    vote_token
                )
            )

        # -------------------------------------------------
        # Commit votes
        # -------------------------------------------------

        connection.commit()

        flash(
            "Your vote has been submitted successfully!",
            "success"
        )

        return redirect(
            url_for("voting.success")
        )

    except Exception as e:

        connection.rollback()

        print(
            "Voting submission error:",
            e
        )

        return back_to_voting(
            "Unable to submit your vote. Please try again."
        )

    finally:

        if cursor:
            cursor.close()

        connection.close()


# =========================================================
# SUCCESS PAGE
# URL: /vote/success
# TEMPLATE: templates/vote_success.html
# =========================================================

@voting_bp.route(
    "/success",
    methods=["GET"]
)
def success():

    return render_template(
        "vote_success.html"
    )