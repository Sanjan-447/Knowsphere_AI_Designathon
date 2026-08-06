"""
The ingestion pipeline task: parsing -> cleaning -> chunking -> embedding ->
storage, run asynchronously so a large upload never blocks an HTTP request
thread. This is the one task file for Phase 2 — Enterprise RAG retrieval
(Phase 3) will add its own tasks module for re-indexing triggers etc.
"""
import logging

from app.celery_app import celery_app
from app.extensions import db
from app.documents.models import (
    Document, DocumentChunk, DocumentMetadata,
    STATUS_VALIDATING, STATUS_PARSING, STATUS_CHUNKING, STATUS_EMBEDDING,
    STATUS_INDEXING, STATUS_READY, STATUS_FAILED,
    SOURCE_CHAT_EXPORT,
)
from app.providers.models import ProviderConfig
from app.documents.parsers.base import ParserError
from app.documents.parsers.registry import get_parser_for_extension, get_chat_export_parser
from app.documents.chunking import chunk_document
from app.documents.service import record_event
from app.retrieval.embeddings import get_embedding_provider, EmbeddingError
from app.notifications.service import notify

logger = logging.getLogger("knowsphere.ingestion")

EMBEDDING_BATCH_SIZE = 16


def _resolve_parser(document: Document):
    if document.source_type == SOURCE_CHAT_EXPORT:
        return get_chat_export_parser()
    parser = get_parser_for_extension(document.file_type)
    if parser is None:
        raise ParserError(f"No parser registered for file type '{document.file_type}'.")
    return parser


def _resolve_embedding_provider():
    """Prefer the org's default embedding-capable provider; fall back to the
    dev-only local provider (with a loud warning) if none is configured.

    Phase 6 fix: this previously filtered only by provider_type, not
    capability — meaning an LLM-only provider (capability='llm') of type
    'openai_compatible' could be mistakenly selected here for embedding
    generation, the exact bug the capability field was added in Phase 3/4
    to prevent on the chat/retrieval side. That fix was never propagated
    to this ingestion-side resolver. Found via real-file upload testing
    (a document ingestion failed trying to call an LLM-only mock
    provider's nonexistent /embeddings endpoint), not a hypothetical."""
    capability_filter = ProviderConfig.capability.in_(["embedding", "both"])
    provider_config = ProviderConfig.query.filter(
        ProviderConfig.is_default.is_(True),
        ProviderConfig.is_active.is_(True),
        ProviderConfig.provider_type.in_(["openai", "gemini", "openai_compatible"]),
        capability_filter,
    ).first()
    if provider_config is None:
        provider_config = ProviderConfig.query.filter(
            ProviderConfig.is_active.is_(True),
            ProviderConfig.provider_type.in_(["openai", "gemini", "openai_compatible"]),
            capability_filter,
        ).first()
    return get_embedding_provider(provider_config)


@celery_app.task(bind=True, name="documents.process_document")
def process_document(self, document_id: int):
    document = Document.query.get(document_id)
    if document is None:
        logger.error("process_document: document %s not found", document_id)
        return {"status": "error", "message": "document not found"}

    try:
        # --- Parse ---
        record_event(document, STATUS_VALIDATING, "Starting ingestion pipeline.")
        record_event(document, STATUS_PARSING, f"Parsing as {document.file_type}.")
        parser = _resolve_parser(document)
        parsed = parser.parse(document.storage_path)

        # Merge parser-extracted metadata into DocumentMetadata rows
        # (author/source_last_modified go to the fixed columns if not already set;
        # everything else becomes a flexible key/value row).
        for key, value in parsed.metadata.items():
            if key == "author" and not document.author:
                document.author = str(value)
                continue
            if key == "source_last_modified":
                from datetime import datetime
                try:
                    document.source_last_modified = datetime.fromisoformat(str(value))
                except ValueError:
                    pass
                continue
            existing = DocumentMetadata.query.filter_by(document_id=document.id, key=key).first()
            if existing:
                existing.value = str(value)
            else:
                db.session.add(DocumentMetadata(document_id=document.id, key=key, value=str(value)))
        db.session.commit()

        # --- Chunk ---
        record_event(document, STATUS_CHUNKING, "Splitting into semantic chunks.")
        drafts = chunk_document(parsed)
        if not drafts:
            raise ParserError("Document produced no chunkable content after cleaning.")

        # Clear any prior chunks (reprocess case) before inserting fresh ones.
        DocumentChunk.query.filter_by(document_id=document.id).delete()
        db.session.commit()

        chunk_rows = []
        for idx, draft in enumerate(drafts):
            row = DocumentChunk(
                document_id=document.id,
                chunk_index=idx,
                content=draft.content,
                token_count=draft.token_count,
                chunk_metadata={"section": draft.section_label} if draft.section_label else {},
            )
            db.session.add(row)
            chunk_rows.append(row)
        db.session.commit()

        # --- Embed ---
        record_event(document, STATUS_EMBEDDING, f"Generating embeddings for {len(chunk_rows)} chunks.")
        provider = _resolve_embedding_provider()

        for start in range(0, len(chunk_rows), EMBEDDING_BATCH_SIZE):
            batch = chunk_rows[start:start + EMBEDDING_BATCH_SIZE]
            texts = [c.content for c in batch]
            vectors = provider.embed(texts)
            for row, vector in zip(batch, vectors):
                row.embedding = vector
                row.embedding_model = provider.model_name
        db.session.commit()

        # --- Index (pgvector: the row insert above *is* the index write — an
        # HNSW/IVFFlat index on document_chunks.embedding, added in the
        # migration, updates automatically on commit) ---
        record_event(document, STATUS_INDEXING, "Finalizing vector index entries.")

        record_event(document, STATUS_READY, f"Ready — {len(chunk_rows)} chunks embedded with {provider.model_name}.")
        return {"status": "ready", "chunk_count": len(chunk_rows)}

    except ParserError as exc:
        db.session.rollback()
        record_event(document, STATUS_FAILED, f"Parsing failed: {exc}")
        notify("failed_upload", title=f"Document failed to process: {document.title}",
               message=str(exc), severity="error", resource_type="document", resource_id=document.id)
        return {"status": "failed", "message": str(exc)}
    except EmbeddingError as exc:
        db.session.rollback()
        record_event(document, STATUS_FAILED, f"Embedding failed: {exc}")
        notify("failed_embedding", title=f"Embedding failed for document: {document.title}",
               message=str(exc), severity="error", resource_type="document", resource_id=document.id)
        return {"status": "failed", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 — pipeline boundary: never let an unexpected error hang a task silently
        db.session.rollback()
        logger.exception("Unexpected ingestion failure for document %s", document_id)
        record_event(document, STATUS_FAILED, f"Unexpected error: {exc}")
        notify("background_job_failure", title=f"Ingestion pipeline failed unexpectedly: {document.title}",
               message=str(exc), severity="error", resource_type="document", resource_id=document.id)
        return {"status": "failed", "message": str(exc)}
