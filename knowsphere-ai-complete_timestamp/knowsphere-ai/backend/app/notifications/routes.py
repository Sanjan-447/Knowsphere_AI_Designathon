from flask import Blueprint, request

from app.extensions import db
from app.common.responses import success_response
from app.common.errors import AppError
from app.auth.decorators import require_role
from app.rbac.models import ROLE_ADMIN
from app.notifications.models import Notification
from app.notifications.service import scan_for_expired_documents

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.get("")
@require_role(ROLE_ADMIN)
def list_notifications():
    query = Notification.query
    if request.args.get("unread_only", "false").lower() == "true":
        query = query.filter_by(is_read=False)
    if request.args.get("notification_type"):
        query = query.filter_by(notification_type=request.args["notification_type"])

    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 50)), 200)
    total = query.count()
    unread_count = Notification.query.filter_by(is_read=False).count()

    rows = query.order_by(Notification.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return success_response(data={
        "notifications": [n.to_dict() for n in rows],
        "total": total, "unread_count": unread_count, "page": page, "page_size": page_size,
    })


@notifications_bp.patch("/<int:notification_id>/read")
@require_role(ROLE_ADMIN)
def mark_read(notification_id: int):
    n = Notification.query.get(notification_id)
    if not n:
        raise AppError("NOT_FOUND", "Notification not found.", 404)
    n.is_read = True
    db.session.commit()
    return success_response(data=n.to_dict())


@notifications_bp.post("/mark-all-read")
@require_role(ROLE_ADMIN)
def mark_all_read():
    count = Notification.query.filter_by(is_read=False).update({"is_read": True})
    db.session.commit()
    return success_response(message=f"Marked {count} notification(s) as read.")


@notifications_bp.post("/check-expired-documents")
@require_role(ROLE_ADMIN)
def check_expired_documents():
    days = int((request.get_json(silent=True) or {}).get("days_threshold", 365))
    created = scan_for_expired_documents(days_threshold=days)
    return success_response(message=f"Scan complete — {created} new notification(s) created.", data={"created": created})
