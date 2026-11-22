from flask import request
import os
import uuid
from werkzeug.utils import secure_filename
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)
import secrets

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from database import get_db_connection
from config import Config


# =========================================================
# ADMIN BLUEPRINT
# =========================================================

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# =========================================================
# ADMIN LOGIN
# =========================================================

@admin_bp.route("/login", methods=["GET", "POST"])
def login():

    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("admin/login.html")

        connection = get_db_connection()

        if connection is None:
            flash("Database connection failed.", "error")
            return render_template("admin/login.html")

        cursor = connection.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    password_hash,
                    status
                FROM admins
                WHERE email = %s
                LIMIT 1
                """,
                (email,)
            )

            admin = cursor.fetchone()

        finally:

            cursor.close()
            connection.close()

        if not admin:
            flash("Invalid email or password.", "error")
            return render_template("admin/login.html")

        if admin["status"] != "ACTIVE":
            flash("This admin account is inactive.", "error")
            return render_template("admin/login.html")

        if not check_password_hash(
            admin["password_hash"],
            password
        ):
            flash("Invalid email or password.", "error")
            return render_template("admin/login.html")

        session.clear()

        session["admin_id"] = admin["id"]
        session["admin_name"] = admin["name"]
        session["admin_email"] = admin["email"]

        return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html")


# =========================================================
# ADMIN REGISTRATION
# =========================================================

@admin_bp.route("/register", methods=["GET", "POST"])
def register():

    if session.get("admin_id"):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )
        registration_key = request.form.get(
            "registration_key",
            ""
        ).strip()

        if not name or not email or not password or not confirm_password:
            flash(
                "All required fields must be filled.",
                "error"
            )
            return render_template("admin/register.html")

        if len(name) < 2:
            flash(
                "Name must contain at least 2 characters.",
                "error"
            )
            return render_template("admin/register.html")

        if "@" not in email or "." not in email:
            flash(
                "Please enter a valid email address.",
                "error"
            )
            return render_template("admin/register.html")

        if len(password) < 8:
            flash(
                "Password must contain at least 8 characters.",
                "error"
            )
            return render_template("admin/register.html")

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "error"
            )
            return render_template("admin/register.html")

        configured_key = getattr(
            Config,
            "ADMIN_REGISTRATION_KEY",
            ""
        )

        if not configured_key:
            flash(
                "Admin registration is not configured.",
                "error"
            )
            return render_template("admin/register.html")

        if registration_key != configured_key:
            flash(
                "Invalid admin registration key.",
                "error"
            )
            return render_template("admin/register.html")

        connection = get_db_connection()

        if connection is None:
            flash(
                "Database connection failed.",
                "error"
            )
            return render_template("admin/register.html")

        cursor = connection.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT id
                FROM admins
                WHERE email = %s
                LIMIT 1
                """,
                (email,)
            )

            existing_admin = cursor.fetchone()

            if existing_admin:

                flash(
                    "An admin account with this email already exists.",
                    "error"
                )

                return render_template(
                    "admin/register.html"
                )

            password_hash = generate_password_hash(password)

            cursor.execute(
                """
                INSERT INTO admins
                (
                    name,
                    email,
                    password_hash,
                    status
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    'ACTIVE'
                )
                """,
                (
                    name,
                    email,
                    password_hash
                )
            )

            connection.commit()

            flash(
                "Admin account created successfully. Please login.",
                "success"
            )

            return redirect(
                url_for("admin.login")
            )

        except Exception as e:

            connection.rollback()

            print(
                "Admin registration error:",
                e
            )

            flash(
                "Unable to create admin account.",
                "error"
            )

            return render_template(
                "admin/register.html"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template("admin/register.html")


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@admin_bp.route("/dashboard")
def dashboard():

    if not session.get("admin_id"):

        flash(
            "Please login to access the admin panel.",
            "error"
        )

        return redirect(
            url_for("admin.login")
        )

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "error"
        )

        return render_template(
            "admin/dashboard.html",
            admin_name=session.get("admin_name"),
            admin_email=session.get("admin_email"),
            stats={
                "total_elections": 0,
                "active_elections": 0,
                "total_candidates": 0,
                "total_students": 0,
                "total_votes": 0
            },
            elections=[]
        )

    cursor = connection.cursor(dictionary=True)

    try:

        # Total elections
        cursor.execute(
            "SELECT COUNT(*) AS total FROM elections"
        )

        total_elections = cursor.fetchone()["total"]

        # Active elections
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM elections
            WHERE status = 'ACTIVE'
            """
        )

        active_elections = cursor.fetchone()["total"]

        # Total candidates
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM candidates
            WHERE status = 'ACTIVE'
            """
        )

        total_candidates = cursor.fetchone()["total"]

        # Total students
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM students
            WHERE status = 'ACTIVE'
            """
        )

        total_students = cursor.fetchone()["total"]

        # Total votes
        cursor.execute(
            "SELECT COUNT(*) AS total FROM votes"
        )

        total_votes = cursor.fetchone()["total"]

        # Recent elections
        cursor.execute(
            """
            SELECT
                id,
                title,
                start_datetime,
                end_datetime,
                status
            FROM elections
            ORDER BY created_at DESC
            LIMIT 5
            """
        )

        elections = cursor.fetchall()

        stats = {
            "total_elections": total_elections,
            "active_elections": active_elections,
            "total_candidates": total_candidates,
            "total_students": total_students,
            "total_votes": total_votes
        }

        return render_template(
            "admin/dashboard.html",
            admin_name=session.get("admin_name"),
            admin_email=session.get("admin_email"),
            stats=stats,
            elections=elections
        )

    except Exception as e:

        print("Dashboard error:", e)

        flash(
            "Unable to load dashboard data.",
            "error"
        )

        return render_template(
            "admin/dashboard.html",
            admin_name=session.get("admin_name"),
            admin_email=session.get("admin_email"),
            stats={
                "total_elections": 0,
                "active_elections": 0,
                "total_candidates": 0,
                "total_students": 0,
                "total_votes": 0
            },
            elections=[]
        )

    finally:

        cursor.close()
        connection.close()
        # =========================================================
# ELECTIONS MANAGEMENT
# =========================================================

@admin_bp.route("/elections")
def elections():

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )

        return render_template(
            "admin/elections.html",
            elections=[]
        )

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                title,
                description,
                voting_token,
                start_datetime,
                end_datetime,
                status,
                created_at
            FROM elections
            ORDER BY created_at DESC
            """
        )

        elections = cursor.fetchall()

        return render_template(
            "admin/elections.html",
            elections=elections
        )

    except Exception as e:

        print("Elections error:", e)

        flash(
            "Unable to load elections.",
            "error"
        )

        return render_template(
            "admin/elections.html",
            elections=[]
        )

    finally:

        cursor.close()
        connection.close()


# =========================================================
# CREATE ELECTION
# =========================================================

@admin_bp.route("/elections/create", methods=["POST"])
def create_election():

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    title = request.form.get(
        "title",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    start_datetime = request.form.get(
        "start_datetime",
        ""
    ).strip()

    end_datetime = request.form.get(
        "end_datetime",
        ""
    ).strip()

    if not title:
        flash(
            "Election title is required.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    if not start_datetime or not end_datetime:
        flash(
            "Start and end date/time are required.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    if start_datetime >= end_datetime:
        flash(
            "End date/time must be after start date/time.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    voting_token = secrets.token_urlsafe(32)

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    cursor = connection.cursor()

    try:

        cursor.execute(
            """
            INSERT INTO elections
            (
                title,
                description,
                voting_token,
                start_datetime,
                end_datetime,
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                'UPCOMING'
            )
            """,
            (
                title,
                description,
                voting_token,
                start_datetime,
                end_datetime
            )
        )

        election_id = cursor.lastrowid

        connection.commit()

        # Audit log
        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                admin_id,
                action,
                description
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session.get("admin_id"),
                "CREATE_ELECTION",
                f"Created election #{election_id}: {title}"
            )
        )

        connection.commit()

        flash(
            "Election created successfully.",
            "success"
        )

    except Exception as e:

        connection.rollback()

        print(
            "Create election error:",
            e
        )

        flash(
            "Unable to create election.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(url_for("admin.elections"))


# =========================================================
# START ELECTION
# =========================================================

@admin_bp.route(
    "/elections/<int:election_id>/start",
    methods=["POST"]
)
def start_election(election_id):

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                title,
                status
            FROM elections
            WHERE id = %s
            LIMIT 1
            """,
            (election_id,)
        )

        election = cursor.fetchone()

        if not election:
            flash(
                "Election not found.",
                "error"
            )
            return redirect(url_for("admin.elections"))

        if election["status"] != "UPCOMING":
            flash(
                "Only upcoming elections can be started.",
                "error"
            )
            return redirect(url_for("admin.elections"))

        cursor.execute(
            """
            UPDATE elections
            SET status = 'ACTIVE'
            WHERE id = %s
            """,
            (election_id,)
        )

        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                admin_id,
                action,
                description
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session.get("admin_id"),
                "START_ELECTION",
                f"Started election #{election_id}: {election['title']}"
            )
        )

        connection.commit()

        flash(
            "Election started successfully.",
            "success"
        )

    except Exception as e:

        connection.rollback()

        print(
            "Start election error:",
            e
        )

        flash(
            "Unable to start election.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(url_for("admin.elections"))


# =========================================================
# END ELECTION
# =========================================================

@admin_bp.route(
    "/elections/<int:election_id>/end",
    methods=["POST"]
)
def end_election(election_id):

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                title,
                status
            FROM elections
            WHERE id = %s
            LIMIT 1
            """,
            (election_id,)
        )

        election = cursor.fetchone()

        if not election:
            flash(
                "Election not found.",
                "error"
            )
            return redirect(url_for("admin.elections"))

        if election["status"] != "ACTIVE":
            flash(
                "Only active elections can be ended.",
                "error"
            )
            return redirect(url_for("admin.elections"))

        cursor.execute(
            """
            UPDATE elections
            SET status = 'COMPLETED'
            WHERE id = %s
            """,
            (election_id,)
        )

        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                admin_id,
                action,
                description
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session.get("admin_id"),
                "END_ELECTION",
                f"Ended election #{election_id}: {election['title']}"
            )
        )

        connection.commit()

        flash(
            "Election ended successfully.",
            "success"
        )

    except Exception as e:

        connection.rollback()

        print(
            "End election error:",
            e
        )

        flash(
            "Unable to end election.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(url_for("admin.elections"))


# =========================================================
# CANCEL ELECTION
# =========================================================

@admin_bp.route(
    "/elections/<int:election_id>/cancel",
    methods=["POST"]
)
def cancel_election(election_id):

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                title,
                status
            FROM elections
            WHERE id = %s
            LIMIT 1
            """,
            (election_id,)
        )

        election = cursor.fetchone()

        if not election:
            flash(
                "Election not found.",
                "error"
            )
            return redirect(url_for("admin.elections"))

        if election["status"] in (
            "COMPLETED",
            "CANCELLED"
        ):
            flash(
                "This election cannot be cancelled.",
                "error"
            )
            return redirect(url_for("admin.elections"))

        cursor.execute(
            """
            UPDATE elections
            SET status = 'CANCELLED'
            WHERE id = %s
            """,
            (election_id,)
        )

        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                admin_id,
                action,
                description
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session.get("admin_id"),
                "CANCEL_ELECTION",
                f"Cancelled election #{election_id}: {election['title']}"
            )
        )

        connection.commit()

        flash(
            "Election cancelled successfully.",
            "success"
        )

    except Exception as e:

        connection.rollback()

        print(
            "Cancel election error:",
            e
        )

        flash(
            "Unable to cancel election.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(url_for("admin.elections"))


# =========================================================
# ADMIN LOGOUT
# =========================================================

@admin_bp.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(
        url_for("admin.login")
    )
# =========================================================
# POSITION MANAGEMENT
# =========================================================

@admin_bp.route("/positions/<int:election_id>")
def positions(election_id):

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    cursor = connection.cursor(dictionary=True)

    try:

        # Get election
        cursor.execute(
            """
            SELECT
                id,
                title,
                status
            FROM elections
            WHERE id = %s
            LIMIT 1
            """,
            (election_id,)
        )

        election = cursor.fetchone()

        if not election:
            flash(
                "Election not found.",
                "error"
            )
            return redirect(url_for("admin.elections"))

        # Get positions
        cursor.execute(
            """
            SELECT
                id,
                election_id,
                position_name
            FROM positions
            WHERE election_id = %s
            ORDER BY id ASC
            """,
            (election_id,)
        )

        positions = cursor.fetchall()

        return render_template(
            "admin/positions.html",
            election=election,
            positions=positions
        )

    except Exception as e:

        print("Positions error:", e)

        flash(
            "Unable to load positions.",
            "error"
        )

        return redirect(
            url_for("admin.elections")
        )

    finally:

        cursor.close()
        connection.close()


# =========================================================
# ADD POSITION
# =========================================================

@admin_bp.route(
    "/elections/<int:election_id>/positions/create",
    methods=["POST"]
)
def create_position(election_id):

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    position_name = request.form.get(
        "position_name",
        ""
    ).strip()

    if not position_name:
        flash(
            "Position name is required.",
            "error"
        )
        return redirect(
            url_for(
                "admin.positions",
                election_id=election_id
            )
        )

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )
        return redirect(
            url_for(
                "admin.positions",
                election_id=election_id
            )
        )

    cursor = connection.cursor(dictionary=True)

    try:

        # Check election
        cursor.execute(
            """
            SELECT
                id,
                title,
                status
            FROM elections
            WHERE id = %s
            LIMIT 1
            """,
            (election_id,)
        )

        election = cursor.fetchone()

        if not election:
            flash(
                "Election not found.",
                "error"
            )
            return redirect(
                url_for("admin.elections")
            )

        if election["status"] in (
            "COMPLETED",
            "CANCELLED"
        ):
            flash(
                "Positions cannot be added to this election.",
                "error"
            )
            return redirect(
                url_for(
                    "admin.positions",
                    election_id=election_id
                )
            )

        # Duplicate position check
        cursor.execute(
            """
            SELECT id
            FROM positions
            WHERE election_id = %s
            AND LOWER(position_name) = LOWER(%s)
            LIMIT 1
            """,
            (
                election_id,
                position_name
            )
        )

        existing_position = cursor.fetchone()

        if existing_position:
            flash(
                "This position already exists in the election.",
                "error"
            )
            return redirect(
                url_for(
                    "admin.positions",
                    election_id=election_id
                )
            )

        # Insert position
        cursor.execute(
            """
            INSERT INTO positions
            (
                election_id,
                position_name
            )
            VALUES
            (
                %s,
                %s
            )
            """,
            (
                election_id,
                position_name
            )
        )

        position_id = cursor.lastrowid

        # Audit log
        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                admin_id,
                action,
                description
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session.get("admin_id"),
                "CREATE_POSITION",
                f"Created position #{position_id}: "
                f"{position_name} "
                f"for election #{election_id}"
            )
        )

        connection.commit()

        flash(
            "Position added successfully.",
            "success"
        )

    except Exception as e:

        connection.rollback()

        print(
            "Create position error:",
            e
        )

        flash(
            "Unable to add position.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for(
            "admin.positions",
            election_id=election_id
        )
    )


# =========================================================
# EDIT POSITION
# =========================================================

@admin_bp.route(
    "/positions/<int:position_id>/edit",
    methods=["POST"]
)
def edit_position(position_id):

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    position_name = request.form.get(
        "position_name",
        ""
    ).strip()

    if not position_name:
        flash(
            "Position name is required.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    cursor = connection.cursor(dictionary=True)

    try:

        # Get position + election
        cursor.execute(
            """
            SELECT
                p.id,
                p.election_id,
                p.position_name,
                e.title,
                e.status
            FROM positions p
            INNER JOIN elections e
                ON p.election_id = e.id
            WHERE p.id = %s
            LIMIT 1
            """,
            (position_id,)
        )

        position = cursor.fetchone()

        if not position:
            flash(
                "Position not found.",
                "error"
            )
            return redirect(
                url_for("admin.elections")
            )

        if position["status"] in (
            "COMPLETED",
            "CANCELLED"
        ):
            flash(
                "This position cannot be edited.",
                "error"
            )
            return redirect(
                url_for(
                    "admin.positions",
                    election_id=position["election_id"]
                )
            )

        # Duplicate check
        cursor.execute(
            """
            SELECT id
            FROM positions
            WHERE election_id = %s
            AND LOWER(position_name) = LOWER(%s)
            AND id != %s
            LIMIT 1
            """,
            (
                position["election_id"],
                position_name,
                position_id
            )
        )

        duplicate = cursor.fetchone()

        if duplicate:
            flash(
                "Another position with this name already exists.",
                "error"
            )
            return redirect(
                url_for(
                    "admin.positions",
                    election_id=position["election_id"]
                )
            )

        cursor.execute(
            """
            UPDATE positions
            SET position_name = %s
            WHERE id = %s
            """,
            (
                position_name,
                position_id
            )
        )

        # Audit
        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                admin_id,
                action,
                description
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session.get("admin_id"),
                "EDIT_POSITION",
                f"Updated position #{position_id} "
                f"to: {position_name}"
            )
        )

        connection.commit()

        flash(
            "Position updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin.positions",
                election_id=position["election_id"]
            )
        )

    except Exception as e:

        connection.rollback()

        print(
            "Edit position error:",
            e
        )

        flash(
            "Unable to update position.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for("admin.elections")
    )


# =========================================================
# DELETE POSITION
# =========================================================

@admin_bp.route(
    "/positions/<int:position_id>/delete",
    methods=["POST"]
)
def delete_position(position_id):

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )
        return redirect(url_for("admin.elections"))

    cursor = connection.cursor(dictionary=True)

    try:

        # Get position
        cursor.execute(
            """
            SELECT
                p.id,
                p.election_id,
                p.position_name,
                e.title,
                e.status
            FROM positions p
            INNER JOIN elections e
                ON p.election_id = e.id
            WHERE p.id = %s
            LIMIT 1
            """,
            (position_id,)
        )

        position = cursor.fetchone()

        if not position:
            flash(
                "Position not found.",
                "error"
            )
            return redirect(
                url_for("admin.elections")
            )

        if position["status"] in (
            "ACTIVE",
            "COMPLETED"
        ):
            flash(
                "Position cannot be deleted after election starts.",
                "error"
            )
            return redirect(
                url_for(
                    "admin.positions",
                    election_id=position["election_id"]
                )
            )

        # Check candidates
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM candidates
            WHERE position_id = %s
            """,
            (position_id,)
        )

        candidate_count = cursor.fetchone()["total"]

        if candidate_count > 0:
            flash(
                "Cannot delete position because candidates "
                "are already assigned to it.",
                "error"
            )
            return redirect(
                url_for(
                    "admin.positions",
                    election_id=position["election_id"]
                )
            )

        cursor.execute(
            """
            DELETE FROM positions
            WHERE id = %s
            """,
            (position_id,)
        )

        # Audit
        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                admin_id,
                action,
                description
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session.get("admin_id"),
                "DELETE_POSITION",
                f"Deleted position #{position_id}: "
                f"{position['position_name']} "
                f"from election #{position['election_id']}"
            )
        )

        connection.commit()

        flash(
            "Position deleted successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin.positions",
                election_id=position["election_id"]
            )
        )

    except Exception as e:

        connection.rollback()

        print(
            "Delete position error:",
            e
        )

        flash(
            "Unable to delete position.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(
        url_for("admin.elections")
    )
# =========================================================
# CANDIDATE MANAGEMENT
# =========================================================

@admin_bp.route("/candidates")
def candidates():

    if not session.get("admin_id"):
        flash("Please login to access the admin panel.", "error")
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("admin.dashboard"))

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                e.id,
                e.title,
                e.status,
                e.start_datetime,
                e.end_datetime,
                COUNT(c.id) AS candidate_count
            FROM elections e
            LEFT JOIN candidates c
                ON e.id = c.election_id
                AND c.status = 'ACTIVE'
            GROUP BY
                e.id,
                e.title,
                e.status,
                e.start_datetime,
                e.end_datetime,
                e.created_at
            ORDER BY e.created_at DESC
            """
        )

        elections = cursor.fetchall()

        return render_template(
            "admin/candidates.html",
            elections=elections
        )

    except Exception as e:

        print("Candidates page error:", e)

        flash(
            "Unable to load candidates.",
            "error"
        )

        return redirect(
            url_for("admin.dashboard")
        )

    finally:

        cursor.close()
        connection.close()


# =========================================================
# VIEW CANDIDATES OF ELECTION
# =========================================================

@admin_bp.route(
    "/elections/<int:election_id>/candidates"
)
def election_candidates(election_id):

    if not session.get("admin_id"):
        flash(
            "Please login to access the admin panel.",
            "error"
        )

        return redirect(
            url_for("admin.login")
        )

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "error"
        )

        return redirect(
            url_for("admin.elections")
        )

    cursor = connection.cursor(dictionary=True)

    try:

        # -------------------------------------------------
        # GET ELECTION
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                title,
                description,
                status,
                start_datetime,
                end_datetime
            FROM elections
            WHERE id = %s
            LIMIT 1
            """,
            (election_id,)
        )

        election = cursor.fetchone()

        if not election:

            flash(
                "Election not found.",
                "error"
            )

            return redirect(
                url_for("admin.elections")
            )

        # -------------------------------------------------
        # GET POSITIONS
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                election_id,
                position_name
            FROM positions
            WHERE election_id = %s
            ORDER BY id ASC
            """,
            (election_id,)
        )

        positions = cursor.fetchall()

        # -------------------------------------------------
        # GET CANDIDATES
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                c.id,
                c.election_id,
                c.position_id,
                c.name,
                c.roll_number,
                c.department,
                c.year,
                c.manifesto,
                c.photo,
                c.profile_url,
                c.status,
                c.created_at,
                p.position_name
            FROM candidates c
            INNER JOIN positions p
                ON c.position_id = p.id
            WHERE c.election_id = %s
            ORDER BY
                p.id ASC,
                c.name ASC
            """,
            (election_id,)
        )

        candidates = cursor.fetchall()

        return render_template(
            "admin/candidates.html",
            election=election,
            positions=positions,
            candidates=candidates
        )

    except Exception as e:

        print(
            "Election candidates error:",
            e
        )

        flash(
            "Unable to load candidates.",
            "error"
        )

        return redirect(
            url_for("admin.elections")
        )

    finally:

        cursor.close()
        connection.close()

# =========================================================
# ADD / CREATE CANDIDATE
# =========================================================

@admin_bp.route(
    "/elections/<int:election_id>/candidates/create",
    methods=["GET", "POST"]
)
def create_candidate(election_id):

    # -----------------------------------------------------
    # ADMIN CHECK
    # -----------------------------------------------------

    if not session.get("admin_id"):

        flash(
            "Please login to access the admin panel.",
            "error"
        )

        return redirect(
            url_for("admin.login")
        )

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "error"
        )

        return redirect(
            url_for("admin.elections")
        )

    cursor = connection.cursor(dictionary=True)

    try:

        # -------------------------------------------------
        # GET ELECTION
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                title,
                description,
                status,
                start_datetime,
                end_datetime
            FROM elections
            WHERE id = %s
            LIMIT 1
            """,
            (election_id,)
        )

        election = cursor.fetchone()

        if not election:

            flash(
                "Election not found.",
                "error"
            )

            return redirect(
                url_for("admin.elections")
            )

        # -------------------------------------------------
        # GET POSITIONS
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                election_id,
                position_name
            FROM positions
            WHERE election_id = %s
            ORDER BY id ASC
            """,
            (election_id,)
        )

        positions = cursor.fetchall()

        # =================================================
        # GET REQUEST
        # =================================================

        if request.method == "GET":

            return render_template(
                "admin/add_candidate.html",
                election=election,
                positions=positions
            )

        # =================================================
        # POST REQUEST
        # =================================================

        name = request.form.get(
            "name",
            ""
        ).strip()

        roll_number = request.form.get(
            "roll_number",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        year = request.form.get(
            "year",
            ""
        ).strip()

        manifesto = request.form.get(
            "manifesto",
            ""
        ).strip()

        profile_url = request.form.get(
            "profile_url",
            ""
        ).strip()

        position_id = request.form.get(
            "position_id",
            ""
        ).strip()

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not name:

            flash(
                "Candidate name is required.",
                "error"
            )

            return render_template(
                "admin/add_candidate.html",
                election=election,
                positions=positions
            )

        if not position_id:

            flash(
                "Please select a position.",
                "error"
            )

            return render_template(
                "admin/add_candidate.html",
                election=election,
                positions=positions
            )

        try:

            position_id = int(position_id)

        except ValueError:

            flash(
                "Invalid position.",
                "error"
            )

            return render_template(
                "admin/add_candidate.html",
                election=election,
                positions=positions
            )

        # -------------------------------------------------
        # ELECTION STATUS CHECK
        # -------------------------------------------------

        if election["status"] in (
            "ACTIVE",
            "COMPLETED",
            "CANCELLED"
        ):

            flash(
                "Candidates cannot be added after the election starts.",
                "error"
            )

            return redirect(
                url_for(
                    "admin.election_candidates",
                    election_id=election_id
                )
            )

        # -------------------------------------------------
        # POSITION CHECK
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                position_name
            FROM positions
            WHERE id = %s
            AND election_id = %s
            LIMIT 1
            """,
            (
                position_id,
                election_id
            )
        )

        position = cursor.fetchone()

        if not position:

            flash(
                "Selected position does not belong to this election.",
                "error"
            )

            return render_template(
                "admin/add_candidate.html",
                election=election,
                positions=positions
            )

        # -------------------------------------------------
        # DUPLICATE CANDIDATE CHECK
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id
            FROM candidates
            WHERE election_id = %s
            AND position_id = %s
            AND LOWER(name) = LOWER(%s)
            LIMIT 1
            """,
            (
                election_id,
                position_id,
                name
            )
        )

        existing = cursor.fetchone()

        if existing:

            flash(
                "This candidate already exists for this position.",
                "error"
            )

            return render_template(
                "admin/add_candidate.html",
                election=election,
                positions=positions
            )

        # =================================================
        # PHOTO UPLOAD
        # =================================================

        photo = request.files.get("photo")

        photo_path = None

        if photo and photo.filename:

            # Allowed extensions
            allowed_extensions = {
                "jpg",
                "jpeg",
                "png"
            }

            original_filename = secure_filename(
                photo.filename
            )

            # Check extension
            if "." not in original_filename:

                flash(
                    "Invalid photo file.",
                    "error"
                )

                return render_template(
                    "admin/add_candidate.html",
                    election=election,
                    positions=positions
                )

            extension = (
                original_filename
                .rsplit(".", 1)[1]
                .lower()
            )

            # Validate extension
            if extension not in allowed_extensions:

                flash(
                    "Only JPG, JPEG and PNG photos are allowed.",
                    "error"
                )

                return render_template(
                    "admin/add_candidate.html",
                    election=election,
                    positions=positions
                )

            # -------------------------------------------------
            # CREATE UPLOAD DIRECTORY
            # -------------------------------------------------

            upload_folder = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(__file__)
                    )
                ),
                "static",
                "images",
                "candidates"
            )

            os.makedirs(
                upload_folder,
                exist_ok=True
            )

            # -------------------------------------------------
            # UNIQUE FILE NAME
            # -------------------------------------------------

            filename = (
                f"{uuid.uuid4().hex}.{extension}"
            )

            file_path = os.path.join(
                upload_folder,
                filename
            )

            # -------------------------------------------------
            # SAVE PHOTO
            # -------------------------------------------------

            photo.save(file_path)

            # -------------------------------------------------
            # DATABASE PATH
            # -------------------------------------------------

            photo_path = (
                f"images/candidates/{filename}"
            )

            print(
                "Candidate photo saved:",
                file_path
            )

        # =================================================
        # INSERT CANDIDATE
        # =================================================

        cursor.execute(
            """
            INSERT INTO candidates
            (
                election_id,
                position_id,
                name,
                roll_number,
                department,
                year,
                manifesto,
                photo,
                profile_url,
                status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'ACTIVE'
            )
            """,
            (
                election_id,
                position_id,
                name,
                roll_number,
                department,
                year,
                manifesto,
                photo_path,
                profile_url
            )
        )

        candidate_id = cursor.lastrowid

        # =================================================
        # AUDIT LOG
        # =================================================

        cursor.execute(
            """
            INSERT INTO audit_logs
            (
                admin_id,
                action,
                description
            )
            VALUES
            (
                %s,
                %s,
                %s
            )
            """,
            (
                session.get("admin_id"),
                "CREATE_CANDIDATE",
                f"Created candidate #{candidate_id}: "
                f"{name} for position "
                f"{position['position_name']} "
                f"in election #{election_id}"
            )
        )

        connection.commit()

        flash(
            "Candidate added successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin.election_candidates",
                election_id=election_id
            )
        )

    except Exception as e:

        connection.rollback()

        print(
            "Create candidate error:",
            e
        )

        flash(
            "Unable to create candidate.",
            "error"
        )

        return render_template(
            "admin/add_candidate.html",
            election=election,
            positions=positions
        )

    finally:

        cursor.close()
        connection.close()

# =========================================================
# ELECTION RESULTS
# URL: /admin/results
# =========================================================

@admin_bp.route("/results")
def results():

    if not session.get("admin_id"):
        flash("Please login to access the admin panel.", "error")
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("admin.dashboard"))

    cursor = connection.cursor(dictionary=True)

    try:

        # Get all elections
        cursor.execute("""
            SELECT
                id,
                title,
                status,
                start_datetime,
                end_datetime
            FROM elections
            ORDER BY created_at DESC
        """)

        elections = cursor.fetchall()

        election_id = request.args.get("election_id")

        selected_election = None
        result_groups = []

        if elections:

            if election_id:
                selected_election = next(
                    (
                        e for e in elections
                        if str(e["id"]) == str(election_id)
                    ),
                    None
                )

            if selected_election is None:
                selected_election = elections[0]

            # Candidate-wise results grouped by position
            cursor.execute("""
                SELECT
                    p.id AS position_id,
                    p.position_name,
                    c.id AS candidate_id,
                    c.name AS candidate_name,
                    c.roll_number,
                    c.department,
                    c.year,
                    COUNT(v.id) AS vote_count

                FROM positions p

                LEFT JOIN candidates c
                    ON c.position_id = p.id
                    AND c.election_id = p.election_id

                LEFT JOIN votes v
                    ON v.candidate_id = c.id
                    AND v.position_id = p.id
                    AND v.election_id = p.election_id

                WHERE p.election_id = %s

                GROUP BY
                    p.id,
                    p.position_name,
                    c.id,
                    c.name,
                    c.roll_number,
                    c.department,
                    c.year

                ORDER BY
                    p.id ASC,
                    vote_count DESC,
                    c.name ASC
            """, (selected_election["id"],))

            rows = cursor.fetchall()

            # Group results by position
            positions = {}

            for row in rows:

                position_id = row["position_id"]

                if position_id not in positions:
                    positions[position_id] = {
                        "position_name": row["position_name"],
                        "candidates": []
                    }

                if row["candidate_id"] is not None:

                    positions[position_id]["candidates"].append({
                        "id": row["candidate_id"],
                        "name": row["candidate_name"],
                        "roll_number": row["roll_number"],
                        "department": row["department"],
                        "year": row["year"],
                        "votes": int(row["vote_count"] or 0)
                    })

            # Calculate totals, percentages and winners
            for position in positions.values():

                candidates = position["candidates"]

                total_votes = sum(
                    candidate["votes"]
                    for candidate in candidates
                )

                highest_votes = max(
                    (candidate["votes"] for candidate in candidates),
                    default=0
                )

                winners = [
                    candidate
                    for candidate in candidates
                    if candidate["votes"] == highest_votes
                    and highest_votes > 0
                ]

                for candidate in candidates:

                    if total_votes > 0:
                        candidate["percentage"] = round(
                            candidate["votes"] / total_votes * 100,
                            2
                        )
                    else:
                        candidate["percentage"] = 0

                    candidate["is_winner"] = (
                        len(winners) == 1
                        and candidate["votes"] == highest_votes
                        and highest_votes > 0
                    )

                position["total_votes"] = total_votes
                position["winners"] = winners
                position["tie"] = len(winners) > 1

                result_groups.append(position)

        return render_template(
            "admin/results.html",
            elections=elections,
            selected_election=selected_election,
            result_groups=result_groups
        )

    except Exception as e:

        print("Results page error:", e)

        flash("Unable to load election results.", "error")

        return render_template(
            "admin/results.html",
            elections=elections if "elections" in locals() else [],
            selected_election=None,
            result_groups=[]
        )

    finally:

        cursor.close()
        connection.close()

@admin_bp.route("/audit-logs")
def audit_logs():

    if not session.get("admin_id"):
        flash("Please login first.", "error")
        return redirect(url_for("admin.login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()

        if connection is None:
            raise Exception("Database connection returned None")

        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                l.id,
                l.admin_id,
                a.name AS admin_name,
                l.action,
                l.description,
                l.ip_address,
                l.created_at
            FROM audit_logs l
            LEFT JOIN admins a
                ON l.admin_id = a.id
            ORDER BY l.created_at DESC
            LIMIT 100
        """)

        logs = cursor.fetchall()

        return render_template(
            "admin/audit_logs.html",
            logs=logs,
            admin_name=session.get("admin_name", "Admin"),
            admin_email=session.get("admin_email", "")
        )

    except Exception as e:
        import traceback
        traceback.print_exc()

        flash(f"Audit Logs Error: {str(e)}", "error")
        return redirect(url_for("admin.dashboard"))

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()
            # =========================================================
# VOTING LINKS MANAGEMENT
# =========================================================

@admin_bp.route("/voting-links")
def voting_links():

    if not session.get("admin_id"):
        flash("Please login first.", "error")
        return redirect(url_for("admin.login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()

        if not connection:
            raise Exception("Database connection failed")

        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                id,
                title,
                status,
                voting_token,
                start_datetime,
                end_datetime
            FROM elections
            ORDER BY id DESC
        """)

        elections = cursor.fetchall()

        for election in elections:
            election["voting_url"] = (
                request.host_url.rstrip("/")
                + url_for(
                    "voting.voting_page",
                    voting_token=election["voting_token"]
                )
            )

        return render_template(
            "admin/voting_links.html",
            elections=elections,
            admin_name=session.get("admin_name", "Admin"),
            admin_email=session.get("admin_email", "")
        )

    except Exception as e:
        print("Voting Links Error:", e)
        flash(f"Voting Links Error: {str(e)}", "error")
        return redirect(url_for("admin.dashboard"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()