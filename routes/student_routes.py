
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from database import get_db_connection


student_bp = Blueprint(
    "student",
    __name__,
    url_prefix="/admin/students"
)


# =========================================================
# STUDENT LIST + SEARCH
# =========================================================

@student_bp.route("/")
def student_list():

    # Admin authentication
    if not session.get("admin_id"):
        flash("Please login to access the admin panel.", "error")
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("admin.dashboard"))

    cursor = connection.cursor(dictionary=True)

    try:

        search = request.args.get("search", "").strip()

        if search:

            cursor.execute("""
                SELECT
                    id,
                    name,
                    roll_number,
                    email,
                    department,
                    year,
                    status,
                    created_at
                FROM students
                WHERE name LIKE %s
                   OR roll_number LIKE %s
                   OR email LIKE %s
                   OR department LIKE %s
                ORDER BY id DESC
            """, (
                f"%{search}%",
                f"%{search}%",
                f"%{search}%",
                f"%{search}%"
            ))

        else:

            cursor.execute("""
                SELECT
                    id,
                    name,
                    roll_number,
                    email,
                    department,
                    year,
                    status,
                    created_at
                FROM students
                ORDER BY id DESC
            """)

        students = cursor.fetchall()

        return render_template(
            "admin/students.html",
            students=students,
            search=search
        )

    except Exception as e:

        print("Student list error:", e)

        flash("Unable to load students.", "error")

        return redirect(url_for("admin.dashboard"))

    finally:

        cursor.close()
        connection.close()


# =========================================================
# ADD STUDENT
# =========================================================

@student_bp.route("/add", methods=["GET", "POST"])
def add_student():

    # Admin authentication
    if not session.get("admin_id"):
        flash("Please login to access the admin panel.", "error")
        return redirect(url_for("admin.login"))

    # GET request - display form
    if request.method == "GET":

        return render_template("admin/add_student.html")


    # POST request - process form
    name = request.form.get("name", "").strip()
    roll_number = request.form.get("roll_number", "").strip()
    email = request.form.get("email", "").strip()
    department = request.form.get("department", "").strip()
    year = request.form.get("year", "").strip()


    # Validate required fields
    if not name or not roll_number or not email:

        flash(
            "Name, Roll Number and Email are required.",
            "error"
        )

        return redirect(url_for("student.add_student"))


    connection = get_db_connection()

    if connection is None:

        flash("Database connection failed.", "error")

        return redirect(url_for("student.student_list"))


    cursor = connection.cursor(dictionary=True)

    try:

        # Check duplicate roll number or email
        cursor.execute("""
            SELECT id
            FROM students
            WHERE roll_number = %s OR email = %s
        """, (roll_number, email))

        existing_student = cursor.fetchone()


        if existing_student:

            flash(
                "Roll Number or Email already exists.",
                "error"
            )

            return redirect(url_for("student.add_student"))


        # Insert new student
        cursor.execute("""
            INSERT INTO students
            (
                name,
                roll_number,
                email,
                department,
                year,
                status
            )
            VALUES (%s, %s, %s, %s, %s, 'ACTIVE')
        """, (
            name,
            roll_number,
            email,
            department or None,
            year or None
        ))


        connection.commit()

        flash("Student added successfully!", "success")

        return redirect(url_for("student.student_list"))


    except Exception as e:

        connection.rollback()

        print("Add student error:", e)

        flash("Unable to add student.", "error")

        return redirect(url_for("student.add_student"))


    finally:

        cursor.close()
        connection.close()
# =========================================================
# DELETE STUDENT
# =========================================================

@student_bp.route("/delete/<int:student_id>", methods=["POST"])
def delete_student(student_id):

    # Admin authentication
    if not session.get("admin_id"):
        flash("Please login to access the admin panel.", "error")
        return redirect(url_for("admin.login"))

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("student.student_list"))

    cursor = connection.cursor(dictionary=True)

    try:

        # Check student exists
        cursor.execute(
            "SELECT id, name FROM students WHERE id = %s",
            (student_id,)
        )

        student = cursor.fetchone()

        if not student:
            flash("Student not found.", "error")
            return redirect(url_for("student.student_list"))

        # Delete student
        cursor.execute(
            "DELETE FROM students WHERE id = %s",
            (student_id,)
        )

        connection.commit()

        flash(
            f"Student {student['name']} deleted successfully!",
            "success"
        )

    except Exception as e:

        connection.rollback()

        print("Delete student error:", e)

        flash(
            "Unable to delete student. They may have associated voting records.",
            "error"
        )

    finally:

        cursor.close()
        connection.close()

    return redirect(url_for("student.student_list"))