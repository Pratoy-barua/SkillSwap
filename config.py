"""Environment-driven configuration for SkillSwap."""

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-this-secret")
    _database_url = os.getenv("DATABASE_URL")
    _database_password = os.getenv("MYSQL_PASSWORD")
    SQLALCHEMY_DATABASE_URI = _database_url or (
    "mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4".format(
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=os.getenv("MYSQL_PORT", "3306"),
        database=os.getenv("MYSQL_DATABASE", "skillswap"),
    )
)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
    PUBLIC_UPLOAD_FOLDER = BASE_DIR / "static" / "uploads" / "public"
    PRIVATE_UPLOAD_FOLDER = BASE_DIR / "private_uploads" / "verification"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
