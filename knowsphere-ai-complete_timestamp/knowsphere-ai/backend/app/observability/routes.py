"""
LangSmith configuration endpoints — admin-only. This is the actual
provision for inserting a LangSmith API key: GET to view current config
(key always masked unless explicitly revealed), PATCH to update it, POST
to test connectivity with a real (if network-permitting) call to
LangSmith's API.
"""
from flask import Blueprint, request

from app.extensions import db
from app.common.responses import success_response
from app.common.errors import AppError
from app.auth.decorators import require_role
from app.rbac.models import ROLE_ADMIN
from app.observability.service import get_or_create_config, test_connection
from app.observability.monitoring_service import get_system_status, get_provider_monitoring
from app.audit.service import log_action
from app.audit.models import ACTION_ADMIN_ACTION
from datetime import datetime, timezone
from flask_jwt_extended import get_jwt_identity

observability_bp = Blueprint("observability", __name__, url_prefix="/observability")


@observability_bp.get("/langsmith")
@require_role(ROLE_ADMIN)
def get_langsmith_config():
    config = get_or_create_config()
    return success_response(data=config.to_dict())


@observability_bp.patch("/langsmith")
@require_role(ROLE_ADMIN)
def update_langsmith_config():
    config = get_or_create_config()
    payload = request.get_json(silent=True) or {}

    if "api_key" in payload:
        config.set_api_key(payload["api_key"] or None)
    if "project_name" in payload:
        project_name = (payload["project_name"] or "").strip()
        if not project_name:
            raise AppError("VALIDATION_ERROR", "project_name cannot be empty.", 422)
        config.project_name = project_name
    if "endpoint" in payload:
        config.endpoint = (payload["endpoint"] or "").strip() or None
    if "tracing_enabled" in payload:
        enabled = bool(payload["tracing_enabled"])
        if enabled and not config.encrypted_api_key:
            raise AppError("VALIDATION_ERROR", "Cannot enable tracing without an API key configured.", 422)
        config.tracing_enabled = enabled

    db.session.commit()

    log_action(ACTION_ADMIN_ACTION, actor_user_id=int(get_jwt_identity()), resource_type="observability_config",
               resource_id=config.id, details={"action": "langsmith_config_updated", "fields": list(payload.keys())})

    return success_response(data=config.to_dict(), message="LangSmith configuration updated.")


@observability_bp.post("/langsmith/test-connection")
@require_role(ROLE_ADMIN)
def test_langsmith_connection():
    config = get_or_create_config()
    passed, message = test_connection(config)

    config.last_test_at = datetime.now(timezone.utc)
    config.last_test_status = "passed" if passed else "failed"
    config.last_test_message = message
    db.session.commit()

    return success_response(data=config.to_dict(), message=message)


@observability_bp.get("/system")
@require_role(ROLE_ADMIN)
def system_status():
    """System Monitoring: real, live health checks — Postgres, pgvector,
    Redis, Celery workers/queue size, disk usage, CPU/memory."""
    return success_response(data=get_system_status())


@observability_bp.get("/providers")
@require_role(ROLE_ADMIN)
def provider_monitoring():
    """Provider Monitoring Dashboard: per-provider response time, success/
    error rate, token usage, estimated cost, last-used — all aggregated
    from real chat_messages data, not simulated."""
    return success_response(data=get_provider_monitoring())
