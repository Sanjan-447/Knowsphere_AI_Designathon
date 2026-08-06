"""
Flask application factory.

All blueprints registered here: health, auth, providers, documents, chat,
audit, observability, analytics, notifications (Phase 1-5). Phase 6 adds
security hardening (rate limiting, secure headers, environment
validation) as cross-cutting concerns — no new blueprints, no new
business logic, per that phase's explicit scope.
"""
from flask import Flask

from app.config import get_config
from app.extensions import db, migrate, jwt, cors
from app.common.errors import register_error_handlers
from app.common.logging_config import configure_logging, register_request_id_middleware
from app.cli import register_cli
from app.security.rate_limit import limiter
from app.security.headers import register_security_headers
from app.security.env_validation import validate_environment


def create_app(env_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(env_name))

    # --- Phase 6: fail fast on insecure/missing configuration ---
    import os
    validate_environment(os.getenv("APP_ENV", "development"))

    # --- Extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )
    limiter.init_app(app)

    # --- Cross-cutting concerns ---
    configure_logging(app)
    register_request_id_middleware(app)
    register_error_handlers(app)
    register_security_headers(app)
    register_cli(app)

    # --- Models must be imported before Flask-Migrate can detect them ---
    from app.rbac.models import Role                          # noqa: F401
    from app.auth.models import User, RefreshSession           # noqa: F401
    from app.providers.models import ProviderConfig            # noqa: F401
    from app.documents.models import (                          # noqa: F401
        Document, DocumentChunk, DocumentMetadata,
        DocumentProcessingEvent, UploadLog, DocumentACL,
    )
    from app.chat.models import ChatSession, ChatMessage, Citation, Feedback  # noqa: F401
    from app.audit.models import AuditLog  # noqa: F401
    from app.observability.models import ObservabilityConfig  # noqa: F401
    from app.notifications.models import Notification  # noqa: F401

    # --- JWT callbacks ---
    _register_jwt_callbacks()

    # --- Blueprints (Phase 1 + Phase 2 + Phase 3 + Phase 5 scope) ---
    from app.health.routes import health_bp
    from app.auth.routes import auth_bp
    from app.providers.routes import providers_bp
    from app.documents.routes import documents_bp
    from app.chat.routes import chat_bp
    from app.audit.routes import audit_bp
    from app.observability.routes import observability_bp
    from app.analytics.routes import analytics_bp
    from app.notifications.routes import notifications_bp

    prefix = app.config["API_PREFIX"]
    app.register_blueprint(health_bp, url_prefix=f"{prefix}/health")
    app.register_blueprint(auth_bp, url_prefix=f"{prefix}/auth")
    app.register_blueprint(providers_bp, url_prefix=f"{prefix}/providers")
    app.register_blueprint(documents_bp, url_prefix=f"{prefix}/documents")
    app.register_blueprint(chat_bp, url_prefix=f"{prefix}/chat")
    app.register_blueprint(audit_bp, url_prefix=f"{prefix}/audit")
    app.register_blueprint(observability_bp, url_prefix=f"{prefix}/observability")
    app.register_blueprint(analytics_bp, url_prefix=f"{prefix}/analytics")
    app.register_blueprint(notifications_bp, url_prefix=f"{prefix}/notifications")

    return app


def _register_jwt_callbacks() -> None:
    from app.common.responses import error_response

    @jwt.unauthorized_loader
    def _missing_token(reason):
        return error_response("MISSING_TOKEN", reason, 401)

    @jwt.invalid_token_loader
    def _invalid_token(reason):
        return error_response("INVALID_TOKEN", reason, 401)

    @jwt.expired_token_loader
    def _expired_token(jwt_header, jwt_payload):
        token_type = jwt_payload.get("type", "token")
        return error_response("TOKEN_EXPIRED", f"The {token_type} has expired.", 401)

    @jwt.revoked_token_loader
    def _revoked_token(jwt_header, jwt_payload):
        return error_response("TOKEN_REVOKED", "This token has been revoked.", 401)
