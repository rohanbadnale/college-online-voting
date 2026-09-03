import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "change-this-secret-key"
    )

    ADMIN_REGISTRATION_KEY = os.getenv(
        "ADMIN_REGISTRATION_KEY",
        ""
    )

    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "college_voting"),
    }