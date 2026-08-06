"""
Environment variable validation, run once at app startup.

Development mode gets a soft warning for insecure defaults (so the
project still runs out-of-the-box per Phase 1's original promise);
production mode raises and refuses to start. The distinction matters: a
missing ENCRYPTION_KEY in dev just means test data isn't really secret;
the same gap in production means every stored provider API key and
LangSmith key is sitting in the database with a key an attacker could
guess (the hardcoded fallback strings are public — they're in this
repository's source code).
"""
import logging
import os

logger = logging.getLogger("knowsphere.security")

_INSECURE_DEFAULTS = {
    "SECRET_KEY": "change-me-in-production",
    "JWT_SECRET_KEY": "change-me-jwt-secret",
}

_REQUIRED_IN_PRODUCTION = ["SECRET_KEY", "JWT_SECRET_KEY", "ENCRYPTION_KEY", "DATABASE_URL"]


class InsecureConfigurationError(Exception):
    pass


def validate_environment(env_name: str) -> None:
    is_production = env_name == "production"
    problems = []

    for key, insecure_value in _INSECURE_DEFAULTS.items():
        current = os.getenv(key, insecure_value)
        if current == insecure_value:
            problems.append(f"{key} is using the insecure default value — set a real secret in your environment.")

    if not os.getenv("ENCRYPTION_KEY"):
        problems.append(
            "ENCRYPTION_KEY is not set. Provider API keys and the LangSmith key cannot be "
            "encrypted at rest without it. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    if is_production:
        for key in _REQUIRED_IN_PRODUCTION:
            if not os.getenv(key):
                problems.append(f"{key} must be set explicitly in production (no fallback is used).")

        if not os.getenv("DATABASE_URL", "").startswith("postgresql"):
            problems.append(
                "DATABASE_URL must point at PostgreSQL in production — the SQLite fallback has no "
                "pgvector support and Phase 2+ features will fail."
            )

    if problems:
        message = "Configuration problems detected:\n" + "\n".join(f"  - {p}" for p in problems)
        if is_production:
            raise InsecureConfigurationError(message)
        logger.warning("%s\n(Running in development mode — see above; this will refuse to start in production.)", message)
