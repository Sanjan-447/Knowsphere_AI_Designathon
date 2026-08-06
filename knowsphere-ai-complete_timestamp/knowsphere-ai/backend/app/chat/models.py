"""
Chat domain models: ChatSession, ChatMessage, Citation.

Citation is a separate table (not a JSON blob on ChatMessage) so citation
cards can be queried/joined independently — e.g. the retrieval dashboard's
"which documents get cited most" view (mirroring the analytics instrumentation
already planned in the architecture blueprint) is a straight aggregation
over this table, not a JSON-parsing exercise.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db


def _uid() -> str:
    return str(uuid.uuid4())


class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_uid = db.Column(db.String(36), unique=True, nullable=False, default=_uid)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False, default="New chat")

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = db.relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def to_dict(self, include_messages: bool = False):
        data = {
            "id": self.id,
            "session_uid": self.session_uid,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages),
        }
        if include_messages:
            data["messages"] = [m.to_dict() for m in self.messages]
        return data


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"), nullable=False)
    session = db.relationship("ChatSession", back_populates="messages")

    role = db.Column(db.String(20), nullable=False)  # "user" | "assistant"
    content = db.Column(db.Text, nullable=False)

    provider_used = db.Column(db.String(50), nullable=True)
    model_used = db.Column(db.String(100), nullable=True)

    prompt_tokens = db.Column(db.Integer, nullable=True)
    completion_tokens = db.Column(db.Integer, nullable=True)
    latency_ms = db.Column(db.Integer, nullable=True)
    had_error = db.Column(db.Boolean, nullable=False, default=False)  # True if the LLM call itself failed
    # (provider timeout/401/500/malformed JSON) and the stored content is a
    # graceful degraded message, not a real model response. Added so
    # Provider Monitoring can compute real success/error rates instead of
    # string-matching against response text for an error-shaped sentence.

    # Retrieval debug info for the admin dashboard: retrieval_time_ms,
    # embedding_model, top_k, similarity scores per retrieved chunk, etc.
    retrieval_metadata = db.Column(JSONB, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    citations = db.relationship("Citation", back_populates="message", cascade="all, delete-orphan")
    feedback_entries = db.relationship("Feedback", cascade="all, delete-orphan")

    def to_dict(self, include_retrieval_metadata: bool = False):
        data = {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "provider_used": self.provider_used,
            "model_used": self.model_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "citations": [c.to_dict() for c in self.citations],
        }
        if include_retrieval_metadata:
            data["retrieval_metadata"] = self.retrieval_metadata
            data["prompt_tokens"] = self.prompt_tokens
            data["completion_tokens"] = self.completion_tokens
            data["latency_ms"] = self.latency_ms
        return data


class Feedback(db.Model):
    """👍/👎 + optional comment on an assistant message. A separate table
    (not a column on ChatMessage) so a rating can be changed without
    mutating the immutable chat record — same reasoning as Citation being
    its own table rather than a JSON blob."""

    __tablename__ = "message_feedback"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    rating = db.Column(db.String(20), nullable=False)  # "helpful" | "not_helpful"
    comment = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (db.UniqueConstraint("message_id", "user_id", name="uq_feedback_message_user"),)

    def to_dict(self):
        return {
            "id": self.id,
            "message_id": self.message_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Citation(db.Model):
    __tablename__ = "citations"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"), nullable=False)
    message = db.relationship("ChatMessage", back_populates="citations")

    marker = db.Column(db.Integer, nullable=False)  # the [n] number used in the response text
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    chunk_id = db.Column(db.Integer, db.ForeignKey("document_chunks.id"), nullable=True)

    citation_type = db.Column(db.String(20), nullable=False)  # document | email | chat_export | share_link
    # Type-specific display fields, per the Phase 3 spec:
    #   document: {document_name, page, section}
    #   email: {subject, sender, date}
    #   chat_export: {channel, sender, timestamp}
    #   share_link: {file_name, source}
    display_fields = db.Column(JSONB, nullable=True)

    snippet = db.Column(db.Text, nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "marker": self.marker,
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "citation_type": self.citation_type,
            "display_fields": self.display_fields or {},
            "snippet": self.snippet,
            "confidence_score": self.confidence_score,
        }
