"""
Notification model.

An in-app notification center, not an external delivery mechanism (no
email/SMS/push integration here — that's real additional infrastructure
this phase doesn't ask for). Notifications are created at the point each
documented failure type actually happens (see the trigger points listed
in service.py), and read via GET /notifications by admins.

"Expired Documents" is the one type without a natural real-time trigger
point (nothing "happens" when a document quietly gets old — there's no
event to hook). Rather than fake a background scheduler this project
doesn't have (no Celery Beat is configured), it's exposed as an
admin-triggered check (POST /notifications/check-expired-documents) that
scans and creates notifications for anything newly past the threshold —
honest about the lack of automatic periodic scanning rather than pretend
one exists.
"""
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db

NOTIFICATION_TYPES = (
    "failed_upload", "failed_embedding", "failed_retrieval", "provider_failure",
    "background_job_failure", "system_error", "expired_document",
)

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    notification_type = db.Column(db.String(30), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, default=SEVERITY_WARNING)

    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=True)

    resource_type = db.Column(db.String(50), nullable=True)
    resource_id = db.Column(db.String(100), nullable=True)
    extra = db.Column(JSONB, nullable=True)

    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "notification_type": self.notification_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "extra": self.extra or {},
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
