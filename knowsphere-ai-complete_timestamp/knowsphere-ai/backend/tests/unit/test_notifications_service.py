"""Unit tests for notifications/service.py."""
from app.notifications.service import notify
from app.notifications.models import Notification


def test_notify_creates_a_row(app):
    with app.app_context():
        n = notify("system_error", title="Test error", message="something broke", severity="error")
        assert n is not None
        assert Notification.query.count() == 1
        assert Notification.query.first().title == "Test error"


def test_notify_defaults_severity_to_warning(app):
    with app.app_context():
        notify("failed_upload", title="Upload failed")
        assert Notification.query.first().severity == "warning"


def test_notify_stores_resource_reference(app):
    with app.app_context():
        notify("failed_embedding", title="x", resource_type="document", resource_id=42)
        row = Notification.query.first()
        assert row.resource_type == "document"
        assert row.resource_id == "42"  # stored as string, since resource may later be deleted
