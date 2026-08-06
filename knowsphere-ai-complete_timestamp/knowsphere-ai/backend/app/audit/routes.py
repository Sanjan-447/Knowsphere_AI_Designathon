"""
Audit log API — admin-only. Deliberately exposes only GET (search) and a
CSV export — no PATCH/DELETE exists for this resource anywhere in the
codebase, which is what "audit logs are immutable" means in practice here.
"""
from flask import Blueprint, request

from app.common.responses import success_response
from app.auth.decorators import require_role
from app.rbac.models import ROLE_ADMIN
from app.audit.models import AuditLog

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


def _apply_filters(query):
    action = request.args.get("action")
    if action:
        query = query.filter(AuditLog.action == action)

    actor_email = request.args.get("actor_email")
    if actor_email:
        query = query.filter(AuditLog.actor_email.ilike(f"%{actor_email}%"))

    resource_type = request.args.get("resource_type")
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)

    date_from = request.args.get("date_from")
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)

    date_to = request.args.get("date_to")
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)

    return query


@audit_bp.get("")
@require_role(ROLE_ADMIN)
def list_audit_logs():
    query = _apply_filters(AuditLog.query)
    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 50)), 200)

    total = query.count()
    rows = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size).all()
    )

    return success_response(data={
        "logs": [r.to_dict() for r in rows],
        "total": total, "page": page, "page_size": page_size,
    })


@audit_bp.get("/export")
@require_role(ROLE_ADMIN)
def export_audit_logs_csv():
    from app.analytics.export_service import export_response

    query = _apply_filters(AuditLog.query).order_by(AuditLog.created_at.desc())
    rows_raw = query.limit(10000).all()  # sane ceiling for a single export

    fmt = request.args.get("format", "csv").lower()
    fields = ["id", "created_at", "actor_email", "actor_role", "action", "resource_type", "resource_id", "ip_address", "details"]
    rows = [
        {
            "id": r.id, "created_at": r.created_at.isoformat() if r.created_at else "",
            "actor_email": r.actor_email or "", "actor_role": r.actor_role or "", "action": r.action,
            "resource_type": r.resource_type or "", "resource_id": r.resource_id or "",
            "ip_address": r.ip_address or "", "details": str(r.details or {}),
        }
        for r in rows_raw
    ]
    return export_response(fmt, "Audit Log Export", fields, rows, "audit_log_export")


@audit_bp.get("/action-types")
@require_role(ROLE_ADMIN)
def list_action_types():
    """Distinct action values actually present — populates a filter dropdown
    without hardcoding the list twice (frontend + backend)."""
    rows = AuditLog.query.with_entities(AuditLog.action).distinct().all()
    return success_response(data=sorted(r[0] for r in rows))
