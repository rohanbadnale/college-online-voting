from flask import Flask, render_template, redirect, url_for

from config import Config
from database import get_db_connection

from routes.admin_routes import admin_bp
from routes.voting_routes import voting_bp
from routes.student_routes import student_bp

# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.config.from_object(Config)


# =========================================================
# REGISTER BLUEPRINTS
# =========================================================

app.register_blueprint(admin_bp)
app.register_blueprint(voting_bp)
app.register_blueprint(student_bp)

# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# STUDENT VOTING ENTRY
# =========================================================

@app.route("/student")
def student_voting():

    connection = get_db_connection()

    if not connection:

        return """
        <h2>Database Connection Failed</h2>
        <p>Please check MySQL/XAMPP and try again.</p>
        """, 500

    cursor = connection.cursor(dictionary=True)

    try:

        # Find currently active election
        cursor.execute("""
            SELECT *
            FROM elections
            WHERE status = 'ACTIVE'
            ORDER BY id DESC
            LIMIT 1
        """)

        election = cursor.fetchone()

    finally:

        cursor.close()
        connection.close()


    # No active election
    if not election:

        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>No Active Election</title>

            <style>
                body {
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background: #f5f7fb;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                }

                .box {
                    background: white;
                    padding: 40px;
                    border-radius: 15px;
                    text-align: center;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.10);
                    max-width: 450px;
                }

                h2 {
                    color: #222;
                }

                p {
                    color: #666;
                }

                a {
                    display: inline-block;
                    margin-top: 15px;
                    padding: 12px 22px;
                    background: #2563eb;
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                }
            </style>

        </head>

        <body>

            <div class="box">

                <h2>No Active Election</h2>

                <p>
                    Currently there is no active election.
                </p>

                <a href="/">
                    Back to Home
                </a>

            </div>

        </body>
        </html>
        """, 404


    # =====================================================
    # REDIRECT TO VOTING PAGE
    # =====================================================

    return redirect(
        url_for(
            "voting.voting_page",
            voting_token=election["voting_token"]
        )
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )