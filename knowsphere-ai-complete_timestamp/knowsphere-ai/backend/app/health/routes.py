"""
Health, readiness, and liveness endpoints (Phase 6).

Three distinct endpoints for three distinct consumers, per standard
Kubernetes/container-orchestration convention — they're deliberately NOT
the same check:

  /health/live   — "is the process alive at all?" No dependency checks.
                   Used by an orchestrator to decide whether to restart
                   the container. Must be fast and never fail due to a
                   downstream dependency being slow/down — restarting the
                   whole pod because Redis had a blip is the wrong response.

  /health/ready  — "can this instance actually serve traffic right now?"
                   Checks the dependencies a request actually needs
                   (Postgres, Redis). Used by a load balancer to decide
                   whether to route traffic to this instance. Failing this
                   should pull the instance out of rotation, not restart it.

  /health        — the original Phase 1 endpoint, kept unchanged for
                   backward compatibility with anything already depending
                   on it (uptime monitors, existing Docker healthchecks).
"""
from flask import Blueprint
from sqlalchemy import text

from app.extensions import db
from app.common.responses import success_response, error_response

health_bp = Blueprint("health", __name__, url_prefix="/health")


@health_bp.get("")
def health_check():
    db_status = "ok"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    return success_response(
        data={"status": "ok", "database": db_status},
        message="KnowSphere AI backend is running.",
    )


@health_bp.get("/live")
def liveness():
    """No dependency checks by design — see module docstring. If this
    process can execute Python and return a response at all, it's alive."""
    return success_response(data={"status": "alive"})


@health_bp.get("/ready")
def readiness():
    """Checks the dependencies a request actually needs. Returns 503 (not
    200) when not ready, so a load balancer's health check correctly
    excludes this instance from routing rather than reading a 200 with an
    embedded 'not ready' string it may not parse."""
    checks = {}

    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"unreachable: {exc}"

    try:
        import redis
        import os
        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=2)
        client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"unreachable: {exc}"

    all_ready = all(v == "ok" for v in checks.values())

    if all_ready:
        return success_response(data={"status": "ready", "checks": checks})
    return error_response("NOT_READY", "One or more dependencies are unavailable.", 503, details=checks)
