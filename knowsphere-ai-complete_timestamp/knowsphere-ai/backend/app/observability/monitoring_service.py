"""
System monitoring service — every check here is a real, live probe against
the actual running infrastructure (not a static "assume it's fine"
placeholder). Each check is wrapped individually so one failing dependency
(e.g. Celery workers not running) doesn't prevent reporting on the others.
"""
from __future__ import annotations

import logging
import os
import shutil

from sqlalchemy import text

from app.extensions import db

logger = logging.getLogger("knowsphere.monitoring")


def check_postgres() -> dict:
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "healthy", "message": "Connected."}
    except Exception as exc:
        return {"status": "unhealthy", "message": str(exc)}


def check_pgvector() -> dict:
    try:
        row = db.session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).first()
        if row:
            return {"status": "healthy", "message": f"pgvector {row[0]} installed."}
        return {"status": "unhealthy", "message": "pgvector extension not found."}
    except Exception as exc:
        return {"status": "unhealthy", "message": str(exc)}


def check_redis() -> dict:
    try:
        import redis
        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=2)
        client.ping()
        info = client.info()
        return {
            "status": "healthy",
            "message": "Connected.",
            "used_memory_mb": round(info.get("used_memory", 0) / (1024 * 1024), 1),
            "connected_clients": info.get("connected_clients"),
        }
    except Exception as exc:
        return {"status": "unhealthy", "message": str(exc)}


def check_celery() -> dict:
    """Real inspection of live Celery workers via the broker — not a
    simulated status. Returns 'unhealthy' (not an exception) if no workers
    respond, since that's a legitimate, common operational state (e.g. the
    worker process isn't running) rather than a code error."""
    try:
        from app.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=2)
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
        stats = inspector.stats() or {}

        worker_names = list(stats.keys())
        if not worker_names:
            return {"status": "unhealthy", "message": "No Celery workers responded.", "worker_count": 0, "queue_size": 0}

        active_count = sum(len(tasks) for tasks in active.values())
        reserved_count = sum(len(tasks) for tasks in reserved.values())

        return {
            "status": "healthy",
            "message": f"{len(worker_names)} worker(s) online.",
            "worker_count": len(worker_names),
            "active_tasks": active_count,
            "queue_size": reserved_count,
            "workers": worker_names,
        }
    except Exception as exc:
        return {"status": "unhealthy", "message": str(exc), "worker_count": 0, "queue_size": 0}


def get_storage_usage() -> dict:
    upload_dir = os.getenv("UPLOAD_DIR", os.path.join(os.getcwd(), "uploads"))
    try:
        total, used, free = shutil.disk_usage(upload_dir if os.path.isdir(upload_dir) else "/")
        upload_dir_size = 0
        if os.path.isdir(upload_dir):
            for root, _, files in os.walk(upload_dir):
                for f in files:
                    try:
                        upload_dir_size += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        return {
            "disk_total_gb": round(total / (1024**3), 2),
            "disk_used_gb": round(used / (1024**3), 2),
            "disk_free_gb": round(free / (1024**3), 2),
            "disk_used_percent": round((used / total) * 100, 1) if total else 0,
            "upload_dir_size_mb": round(upload_dir_size / (1024 * 1024), 2),
        }
    except Exception as exc:
        return {"error": str(exc)}


def get_resource_usage() -> dict:
    """Real CPU/memory figures via psutil — where available, per the
    spec's own caveat ("CPU Usage (where available)"). psutil works in
    virtually every real deployment environment (containers included);
    the caveat mainly covers exotic/restricted sandboxes."""
    try:
        import psutil
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used_mb": round(psutil.virtual_memory().used / (1024 * 1024), 1),
            "memory_total_mb": round(psutil.virtual_memory().total / (1024 * 1024), 1),
        }
    except Exception as exc:
        return {"error": str(exc)}


def get_provider_monitoring() -> list[dict]:
    """Per-provider operational stats for the Provider Monitoring
    Dashboard — response time, success/error rate, token usage, estimated
    cost, and last-used timestamp, all aggregated from real chat_messages
    data (not simulated). One row per provider_config that has ever
    actually answered a message, plus every currently-configured provider
    even if unused yet (so a newly-added provider shows up with zero
    activity rather than being invisible)."""
    from sqlalchemy import func, cast, Float
    from app.chat.models import ChatMessage
    from app.providers.models import ProviderConfig
    from app.analytics.service import COST_PER_1K_TOKENS

    configs = ProviderConfig.query.all()
    rows = (
        db.session.query(
            ChatMessage.provider_used,
            func.count().label("total"),
            func.sum(cast(ChatMessage.had_error, db.Integer)).label("error_count"),
            func.avg(cast(ChatMessage.latency_ms, Float)).label("avg_latency_ms"),
            func.coalesce(func.sum(ChatMessage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(ChatMessage.completion_tokens), 0).label("completion_tokens"),
            func.max(ChatMessage.created_at).label("last_used"),
        )
        .filter(ChatMessage.role == "assistant", ChatMessage.provider_used.isnot(None), ChatMessage.provider_used != "none")
        .group_by(ChatMessage.provider_used)
        .all()
    )
    stats_by_type = {r.provider_used: r for r in rows}

    results = []
    for config in configs:
        stat = stats_by_type.get(config.provider_type)
        if stat and stat.total:
            error_count = int(stat.error_count or 0)
            success_rate = round(1 - (error_count / stat.total), 4)
            rates = COST_PER_1K_TOKENS.get(config.provider_type, {"prompt": 0.0, "completion": 0.0})
            cost = (int(stat.prompt_tokens) / 1000.0) * rates["prompt"] + (int(stat.completion_tokens) / 1000.0) * rates["completion"]
            results.append({
                "provider_config_id": config.id,
                "display_name": config.display_name,
                "provider_type": config.provider_type,
                "is_active": config.is_active,
                "is_default": config.is_default,
                "query_count": stat.total,
                "success_rate": success_rate,
                "error_rate": round(1 - success_rate, 4),
                "avg_response_time_ms": round(stat.avg_latency_ms, 1) if stat.avg_latency_ms else 0,
                "total_tokens": int(stat.prompt_tokens) + int(stat.completion_tokens),
                "estimated_cost_usd": round(cost, 4),
                "last_used": stat.last_used.isoformat() if stat.last_used else None,
                "last_validation_status": config.last_validation_status,
            })
        else:
            results.append({
                "provider_config_id": config.id,
                "display_name": config.display_name,
                "provider_type": config.provider_type,
                "is_active": config.is_active,
                "is_default": config.is_default,
                "query_count": 0,
                "success_rate": None,
                "error_rate": None,
                "avg_response_time_ms": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "last_used": None,
                "last_validation_status": config.last_validation_status,
            })

    return results


def get_system_status() -> dict:
    postgres = check_postgres()
    pgvector = check_pgvector()
    redis_status = check_redis()
    celery_status = check_celery()

    checks = [postgres["status"], pgvector["status"], redis_status["status"], celery_status["status"]]
    overall = "healthy" if all(c == "healthy" for c in checks) else "degraded"

    return {
        "overall_status": overall,
        "postgresql": postgres,
        "pgvector": pgvector,
        "redis": redis_status,
        "celery": celery_status,
        "storage": get_storage_usage(),
        "resources": get_resource_usage(),
    }
