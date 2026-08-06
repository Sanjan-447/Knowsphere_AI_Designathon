"""
Notification service.

notify() is the one function every trigger point calls — same
"never break the caller's real work" resilience pattern as
audit/service.py's log_action(): a notification-creation failure is
logged and swallowed, never allowed to propagate into (and break) the
actual request/task it's describing.
"""
import logging

from app.extensions import db
from app.notifications.models import Notification

logger = logging.getLogger("knowsphere.notifications")


def notify(notification_type: str, title: str, *, message: str = None, severity: str = "warning",
           resource_type: str = None, resource_id=None, extra: dict = None):
    try:
        n = Notification(
            notification_type=notification_type, severity=severity, title=title, message=message,
            resource_type=resource_type, resource_id=str(resource_id) if resource_id is not None else None,
            extra=extra or {},
        )
        db.session.add(n)
        db.session.commit()
        return n
    except Exception:
        db.session.rollback()
        logger.exception("Failed to create notification (type=%s)", notification_type)
        return None


def scan_for_expired_documents(days_threshold: int = 365) -> int:
    """Admin-triggered scan (see module docstring for why this isn't an
    automatic background job) — creates one notification per document that
    just crossed the expiry threshold and doesn't already have an
    un-actioned notification for it, so re-running this doesn't spam
    duplicate alerts for the same stale document."""
    from app.analytics.knowledge_service import get_expired_policies

    expired = get_expired_policies(days_threshold=days_threshold)
    created = 0
    for doc in expired:
        existing = Notification.query.filter_by(
            notification_type="expired_document", resource_type="document",
            resource_id=str(doc["document_id"]), is_read=False,
        ).first()
        if existing:
            continue
        notify(
            "expired_document",
            title=f"Document may be out of date: {doc['title']}",
            message=f"Last updated {doc['days_since_update']} days ago (threshold: {days_threshold} days).",
            severity="warning", resource_type="document", resource_id=doc["document_id"],
            extra={"days_since_update": doc["days_since_update"], "department": doc.get("department")},
        )
        created += 1
    return created
