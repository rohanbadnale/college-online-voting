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