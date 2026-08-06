"""
Audit log model.

Immutable by design: no update or delete route is ever exposed for this
table (see routes.py — only GET/search and CSV export exist). Any code
that needs to "undo" an audit entry should write a new compensating entry,
never mutate or remove the original — that's the actual meaning of
"audit logs are immutable" from the Phase 5 spec's security requirements,
enforced by omission (no route exists to violate it) rather than by a
DB-level trigger, which would be real extra infrastructure for a property
the application layer already guarantees by never offering the endpoint.
"""
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db

# Canonical action types — matching the Phase 5 spec's list exactly, kept
# as string constants (not a DB enum) so a new action type never requires
# a migration, consistent with how Document/ProviderConfig status fields
# already work in this codebase.
ACTION_LOGIN = "login"
ACTION_LOGOUT = "logout"
ACTION_UPLOAD = "upload"
ACTION_DELETE = "delete"
ACTION_REPROCESS = "reprocess"
ACTION_SEARCH = "search"
ACTION_RETRIEVAL = "retrieval"
ACTION_CHAT = "chat"
ACTION_PROVIDER_CHANGE = "provider_change"
ACTION_RBAC_CHANGE = "rbac_change"
ACTION_ADMIN_ACTION = "admin_action"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # nullable: a failed
    # login attempt has no authenticated actor yet, but is still worth auditing
    actor_email = db.Column(db.String(255), nullable=True)  # denormalized snapshot — survives if the user is later deleted
    actor_role = db.Column(db.String(20), nullable=True)

    action = db.Column(db.String(30), nullable=False, index=True)
    resource_type = db.Column(db.String(50), nullable=True)  # e.g. "document", "provider_config", "user"
    resource_id = db.Column(db.String(100), nullable=True)  # string, not FK — resource may be deleted later

    details = db.Column(JSONB, nullable=True)  # action-specific extra context
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "actor_user_id": self.actor_user_id,
            "actor_email": self.actor_email,
            "actor_role": self.actor_role,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details or {},
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
