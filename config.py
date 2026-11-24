
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
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "college_voting"),

        # Local XAMPP: SSL disabled by default.
        # Cloud database: configure SSL through environment variables.
        "ssl_disabled": os.getenv("DB_SSL_DISABLED", "true").lower() == "true",
        "ssl_verify_cert": os.getenv("DB_SSL_VERIFY_CERT", "false").lower() == "true",
        "ssl_verify_identity": os.getenv("DB_SSL_VERIFY_IDENTITY", "false").lower() == "true",
    }
