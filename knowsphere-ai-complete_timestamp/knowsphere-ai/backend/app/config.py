"""
Environment-based configuration for KnowSphere AI.

Config is selected via the FLASK_ENV / APP_ENV environment variable and loaded
through python-dotenv from a .env file (see .env.example at project root).
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env from the backend/ directory (or wherever the process is run from)
load_dotenv()


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class BaseConfig:
    """Shared configuration across all environments."""

    # --- Core ---
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    APP_NAME = os.getenv("APP_NAME", "KnowSphere AI")
    API_PREFIX = "/api/v1"

    # --- Database ---
    # NOTE (Phase 2+): Documents/DocumentChunks use a pgvector column, which
    # requires a real PostgreSQL instance with the `vector` extension enabled.
    # The SQLite fallback below still works for Phase 1's tables (users,
    # roles, provider_configs) but Phase 2 onward requires DATABASE_URL to
    # point at Postgres+pgvector — see docker-compose.yml / README.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.getcwd(), "knowsphere_dev.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Redis / Celery (Phase 2+) ---
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

    # --- File uploads (Phase 2+) ---
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
    MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50")) * 1024 * 1024

    # --- JWT ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "30"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "30"))
    )
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    # --- Encryption (for provider API keys at rest) ---
    # Must be a valid Fernet key (32 url-safe base64-encoded bytes).
    # Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    # --- CORS ---
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

    # --- Logging ---
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv("LOG_FORMAT", "text")  # "text" (human-readable) | "json" (structured, for log aggregators)


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = _env_bool("SQL_ECHO", False)


class TestingConfig(BaseConfig):
    DEBUG = True
    TESTING = True
    # Deliberately NOT hardcoding sqlite:///:memory: here (as this class did
    # through Phase 1) — Phase 2+ models use pgvector and JSONB columns that
    # SQLite cannot represent at all, so any test touching Document,
    # DocumentChunk, or Notification would fail immediately with a
    # CompileError. Inherits BaseConfig's real DATABASE_URL-driven URI
    # instead; tests/conftest.py points this at a dedicated Postgres test
    # database (knowsphere_test) rather than the dev database.
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)

    # Phase 6's rate limiter (10 logins/min, brute-force protection) is
    # keyed by remote address — every test client request looks like the
    # same "IP," so a real test run creating many users and logging each
    # of them in collectively exceeds that limit within seconds, causing
    # unrelated tests to fail with 429s that have nothing to do with what
    # they're actually testing. Found by running the suite, not
    # anticipated in advance. Disabling this in TESTING is the correct
    # fix — rate limiting is a production concern about a single client
    # hammering the endpoint, not about a test suite exercising many
    # distinct legitimate scenarios quickly.
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_ECHO = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(env_name: str | None = None):
    env_name = env_name or os.getenv("APP_ENV", "development")
    return CONFIG_MAP.get(env_name, DevelopmentConfig)
