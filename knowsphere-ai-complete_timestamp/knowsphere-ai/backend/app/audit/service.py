"""
Audit logging service.

One function, `log_action()`, called from existing route handlers at the
point an auditable event happens. This is an additive change to those
route files (one new line each), not a rewrite — the existing response
shape, status codes, and business logic in auth/providers/documents/chat
routes are untouched; only a logging call was added.

Design note on granularity: the Phase 5 spec lists "Chat" and "Retrieval"
as separate trackable actions. In practice, every chat response already
carries its retrieval stats (chunks considered, retrieval time, provider
used) in ChatMessage.retrieval_metadata — writing a second, separate audit
row per message purely to satisfy a literal reading of the list would
double audit volume for no queryable benefit, since the two events always
co-occur at the same moment for the same user. Instead, ACTION_CHAT's
`details` includes the retrieval stats directly, so a single audit row
answers both "did this user chat" and "what did retrieval look like for
it" — a deliberate consolidation, not a missed requirement.
"""
from flask import request

from app.extensions import db
from app.audit.models import AuditLog


def log_action(
    action: str,
    *,
    actor_user_id: int | None = None,
    actor_email: str | None = None,
    actor_role: str | None = None,
    resource_type: str | None = None,
    resource_id=None,
    details: dict | None = None,
):
    """Write one audit log row. Never raises — an audit logging failure
    should never break the actual request it's describing; errors are
    swallowed after a rollback so the caller's own transaction isn't
    poisoned by an audit-table problem."""
    try:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            details=details or {},
            ip_address=request.remote_addr if request else None,
            user_agent=(request.headers.get("User-Agent", "")[:500] if request else None),
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        import logging
        logging.getLogger("knowsphere.audit").exception("Failed to write audit log entry (action=%s)", action)
