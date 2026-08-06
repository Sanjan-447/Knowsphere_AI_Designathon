"""
Document Intelligence domain models.

Chunks and their embeddings live in Postgres via pgvector (see
app/config.py's note on why: keeping ACL and vectors in one transactional
store means a permission filter is a SQL join, not a second system to keep
in sync — this is the same reasoning as the RBAC design from Phase 1's
provider work, now extended to retrieval).

Five model groups here, matching the Phase 2 spec's "extend existing
models with" list:
  - Document              (core record + fixed metadata columns)
  - DocumentChunk         (chunk text + embedding + chunk-level metadata)
  - DocumentMetadata      (flexible key/value metadata beyond the fixed columns)
  - DocumentProcessingEvent (the "Processing Status" ask — a stage/status
                              history, not just a single column, so the UI
                              can show real ingestion progress)
  - UploadLog             (audit trail of every upload/reprocess/delete action)
  - DocumentACL           (role-based visibility, join table against Phase 1's Role)
"""
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db

EMBEDDING_DIMENSIONS = 1536  # matches OpenAI text-embedding-3-small / ada-002

# --- Enums (kept as string constants, matching the Role pattern from rbac/models.py) ---
SOURCE_UPLOAD = "upload"
SOURCE_EMAIL = "email"
SOURCE_CHAT_EXPORT = "chat_export"
SOURCE_SHARE_LINK = "share_link"

STATUS_UPLOADED = "uploaded"
STATUS_VALIDATING = "validating"
STATUS_PARSING = "parsing"
STATUS_CHUNKING = "chunking"
STATUS_EMBEDDING = "embedding"
STATUS_INDEXING = "indexing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"

ALL_STATUSES = [
    STATUS_UPLOADED, STATUS_VALIDATING, STATUS_PARSING, STATUS_CHUNKING,
    STATUS_EMBEDDING, STATUS_INDEXING, STATUS_READY, STATUS_FAILED,
]


def _uid() -> str:
    return str(uuid.uuid4())


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    document_uid = db.Column(db.String(36), unique=True, nullable=False, default=_uid)

    title = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(500), nullable=True)
    file_type = db.Column(db.String(20), nullable=False)   # pdf, docx, txt, csv, xlsx, json, md, eml, msg
    source_type = db.Column(db.String(30), nullable=False, default=SOURCE_UPLOAD)

    storage_path = db.Column(db.String(1000), nullable=True)  # relative path under UPLOAD_DIR
    content_hash = db.Column(db.String(64), nullable=False, index=True)  # SHA-256, for duplicate detection
    file_size_bytes = db.Column(db.Integer, nullable=True)

    # Fixed metadata fields called out explicitly in the spec
    department = db.Column(db.String(255), nullable=True)
    author = db.Column(db.String(255), nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    tags = db.Column(JSONB, nullable=True)  # list[str]
    source_last_modified = db.Column(db.DateTime(timezone=True), nullable=True)  # from the source file/system, if known

    status = db.Column(db.String(20), nullable=False, default=STATUS_UPLOADED)
    error_message = db.Column(db.Text, nullable=True)

    uploaded_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    chunks = db.relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    extra_metadata = db.relationship("DocumentMetadata", back_populates="document", cascade="all, delete-orphan")
    processing_events = db.relationship(
        "DocumentProcessingEvent", back_populates="document",
        cascade="all, delete-orphan", order_by="DocumentProcessingEvent.created_at",
    )
    acl_entries = db.relationship("DocumentACL", back_populates="document", cascade="all, delete-orphan")

    def visible_role_names(self) -> list[str]:
        return [entry.role.name for entry in self.acl_entries]

    def to_dict(self, include_chunk_count: bool = True):
        data = {
            "id": self.id,
            "document_uid": self.document_uid,
            "title": self.title,
            "original_filename": self.original_filename,
            "file_type": self.file_type,
            "source_type": self.source_type,
            "file_size_bytes": self.file_size_bytes,
            "department": self.department,
            "author": self.author,
            "version": self.version,
            "tags": self.tags or [],
            "source_last_modified": self.source_last_modified.isoformat() if self.source_last_modified else None,
            "status": self.status,
            "error_message": self.error_message,
            "visible_to_roles": self.visible_role_names(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_chunk_count:
            data["chunk_count"] = len(self.chunks)
        return data


class DocumentChunk(db.Model):
    __tablename__ = "document_chunks"

    id = db.Column(db.Integer, primary_key=True)
    chunk_uid = db.Column(db.String(36), unique=True, nullable=False, default=_uid)

    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    document = db.relationship("Document", back_populates="chunks")

    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    token_count = db.Column(db.Integer, nullable=True)

    # Nullable until the embedding stage completes — lets us persist chunks
    # from the chunking stage immediately and fill in vectors asynchronously.
    embedding = db.Column(Vector(EMBEDDING_DIMENSIONS), nullable=True)
    embedding_model = db.Column(db.String(100), nullable=True)

    chunk_metadata = db.Column(JSONB, nullable=True)  # e.g. {"section": "§2", "page": 4}

    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Declared here (not just via raw SQL in the Phase 2 migration) so
        # Alembic's autogenerate recognizes this index as part of the model
        # and stops proposing to drop it — a false-positive that recurred
        # in every migration generated since Phase 2 (see the README's
        # Migration History) until this was finally fixed at the source
        # here, in Phase 5, rather than manually stripped a sixth time.
        db.Index(
            "ix_document_chunks_embedding_hnsw", "embedding",
            postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def to_dict(self, include_embedding: bool = False):
        data = {
            "id": self.id,
            "chunk_uid": self.chunk_uid,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "token_count": self.token_count,
            "embedding_model": self.embedding_model,
            "has_embedding": self.embedding is not None,
            "chunk_metadata": self.chunk_metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_embedding and self.embedding is not None:
            data["embedding"] = list(self.embedding)
        return data


class DocumentMetadata(db.Model):
    """Flexible key/value metadata beyond Document's fixed columns —
    e.g. email 'from'/'subject', chat export 'channel', share-link 'source_url'."""

    __tablename__ = "document_metadata"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    document = db.relationship("Document", back_populates="extra_metadata")

    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Text, nullable=True)

    __table_args__ = (db.UniqueConstraint("document_id", "key", name="uq_document_metadata_key"),)

    def to_dict(self):
        return {"key": self.key, "value": self.value}


class DocumentProcessingEvent(db.Model):
    """One row per pipeline stage transition — gives the UI a real progress
    trail ('uploaded' -> 'parsing' -> 'chunking' -> 'embedding' -> 'indexing'
    -> 'ready', or a 'failed' event with a message), not just a status column."""

    __tablename__ = "document_processing_events"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    document = db.relationship("Document", back_populates="processing_events")

    stage = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "stage": self.stage,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UploadLog(db.Model):
    """Audit trail for upload/reprocess/delete actions — separate from
    DocumentProcessingEvent, which tracks pipeline stages for one document;
    this tracks user-initiated actions, including ones that never produced
    a document row (e.g. a rejected duplicate or a validation failure)."""

    __tablename__ = "upload_logs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)

    filename = db.Column(db.String(500), nullable=True)
    content_hash = db.Column(db.String(64), nullable=True)
    action = db.Column(db.String(30), nullable=False)   # upload | reupload | reprocess | delete
    status = db.Column(db.String(20), nullable=False)    # success | rejected | failed
    message = db.Column(db.Text, nullable=True)

    performed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "filename": self.filename,
            "action": self.action,
            "status": self.status,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DocumentACL(db.Model):
    """Which roles may see a document — the same enforcement point pattern
    as the earlier prototype's document_acl, now backed by Phase 1's real
    Role table instead of a hardcoded role list."""

    __tablename__ = "document_acl"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)

    document = db.relationship("Document", back_populates="acl_entries")
    role = db.relationship("Role")

    __table_args__ = (db.UniqueConstraint("document_id", "role_id", name="uq_document_acl"),)
