"""
LLM provider configuration model.

Mirrors `llm_provider_configs` from the architecture blueprint's DB schema,
scoped down for Phase 1 (no org_id yet — multi-tenancy arrives later).
The API key is stored only in encrypted form; `encrypted_api_key` is never
serialized to the API response as-is (see to_dict, which returns a masked
preview instead).
"""
from app.extensions import db
from app.security.encryption import encrypt_value, decrypt_value, mask_value


class ProviderConfig(db.Model):
    __tablename__ = "provider_configs"

    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(255), nullable=False)
    provider_type = db.Column(db.String(50), nullable=False)  # see providers/registry.py

    # Phase 3 addition: a provider_type like "openai_compatible" is
    # genuinely ambiguous — it could be an LLM endpoint, an embedding
    # endpoint, or both, and Phase 3's RAG service needs to resolve "the
    # default LLM provider" and "the default embedding provider"
    # independently without accidentally picking the same config for both
    # (which previously caused a real bug: a Groq/OpenRouter-style
    # chat-completions-only provider being mistakenly selected for
    # embedding calls). Existing rows default to "llm" for backward
    # compatibility with Phase 1/2 data.
    capability = db.Column(db.String(20), nullable=False, default="llm")  # "llm" | "embedding" | "both"

    encrypted_api_key = db.Column(db.Text, nullable=True)  # null for local providers e.g. Ollama
    base_url = db.Column(db.String(500), nullable=True)  # required for NIM/Ollama/OpenAI-compatible
    extra_config = db.Column(db.JSON, nullable=True)  # provider-specific extras (org id, project, etc.)

    is_active = db.Column(db.Boolean, default=True, nullable=False)   # soft-enable/disable
    is_default = db.Column(db.Boolean, default=False, nullable=False)  # the provider used when none specified

    last_validated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_validation_status = db.Column(db.String(20), nullable=True)  # "passed" | "failed" | None

    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    def set_api_key(self, raw_key: str | None) -> None:
        self.encrypted_api_key = encrypt_value(raw_key) if raw_key else None

    def get_api_key(self) -> str | None:
        """Decrypt the stored key. Callers must never log or return this directly."""
        return decrypt_value(self.encrypted_api_key) if self.encrypted_api_key else None

    def to_dict(self, reveal_key: bool = False):
        api_key_display = None
        if self.encrypted_api_key:
            plain = self.get_api_key()
            api_key_display = plain if reveal_key else mask_value(plain)

        return {
            "id": self.id,
            "display_name": self.display_name,
            "provider_type": self.provider_type,
            "capability": self.capability,
            "api_key": api_key_display,
            "base_url": self.base_url,
            "extra_config": self.extra_config,
            "is_active": self.is_active,
            "is_default": self.is_default,
            "last_validated_at": self.last_validated_at.isoformat() if self.last_validated_at else None,
            "last_validation_status": self.last_validation_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
