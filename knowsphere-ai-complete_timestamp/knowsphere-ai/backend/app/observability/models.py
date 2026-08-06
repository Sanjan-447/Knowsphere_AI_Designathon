"""
LangSmith observability configuration.

Deliberately NOT stored in ProviderConfig (Phase 1/3's LLM/embedding
provider table) — LangSmith isn't an LLM or embedding provider, it's a
tracing service, and forcing it into a table whose `provider_type` column
is validated against a fixed list of LLM vendors would be a worse fit
than a small, dedicated table. This is a singleton (one row, or none) —
there's exactly one LangSmith project this deployment traces to, not a
list to choose a "default" from the way LLM providers work.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.security.encryption import encrypt_value, decrypt_value, mask_value


class ObservabilityConfig(db.Model):
    __tablename__ = "observability_config"

    id = db.Column(db.Integer, primary_key=True)

    encrypted_api_key = db.Column(db.Text, nullable=True)
    project_name = db.Column(db.String(255), nullable=False, default="knowsphere-ai")
    endpoint = db.Column(db.String(500), nullable=True)  # defaults to LangSmith's public API if unset
    tracing_enabled = db.Column(db.Boolean, nullable=False, default=False)

    last_test_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_test_status = db.Column(db.String(20), nullable=True)  # "passed" | "failed" | None
    last_test_message = db.Column(db.Text, nullable=True)

    updated_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def set_api_key(self, raw_key: str | None) -> None:
        self.encrypted_api_key = encrypt_value(raw_key) if raw_key else None

    def get_api_key(self) -> str | None:
        return decrypt_value(self.encrypted_api_key) if self.encrypted_api_key else None

    def to_dict(self, reveal_key: bool = False):
        api_key_display = None
        if self.encrypted_api_key:
            plain = self.get_api_key()
            api_key_display = plain if reveal_key else mask_value(plain)

        return {
            "id": self.id,
            "api_key": api_key_display,
            "has_api_key": bool(self.encrypted_api_key),
            "project_name": self.project_name,
            "endpoint": self.endpoint,
            "tracing_enabled": self.tracing_enabled,
            "last_test_at": self.last_test_at.isoformat() if self.last_test_at else None,
            "last_test_status": self.last_test_status,
            "last_test_message": self.last_test_message,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
