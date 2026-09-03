from flask import Flask, render_template

from config import Config
from database import get_db_connection
from routes.admin_routes import admin_bp


app = Flask(__name__)
app.config.from_object(Config)

app.register_blueprint(admin_bp)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/test-db")
def test_db():

    connection = get_db_connection()

    if connection:
        connection.close()
        return "DATABASE CONNECTION SUCCESSFUL ✅"

    return "DATABASE CONNECTION FAILED ❌"


if __name__ == "__main__":
    app.run(debug=True)