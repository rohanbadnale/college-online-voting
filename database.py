import mysql.connector
from mysql.connector import Error

from config import Config


def get_db_connection():

    try:

        connection = mysql.connector.connect(
            host=Config.DB_CONFIG["host"],
            user=Config.DB_CONFIG["user"],
            password=Config.DB_CONFIG["password"],
            database=Config.DB_CONFIG["database"]
        )

        if connection.is_connected():
            return connection

    except Error as e:

        print("Database connection error:", e)

    return None