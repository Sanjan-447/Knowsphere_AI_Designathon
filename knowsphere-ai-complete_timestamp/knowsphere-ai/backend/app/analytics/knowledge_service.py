"""
Knowledge Intelligence service.

Two honest scoping notes, stated once here:

1. "Duplicate Documents" will almost always return empty by design — Phase
   2's upload pipeline rejects exact-content duplicates via SHA-256 hash
   comparison before a document row is even created (see
   documents/routes.py's _check_duplicate()). This function still queries
   for documents sharing a content_hash, as a defensive check (e.g. if
   that upload-time check were ever bypassed, or two documents are
   near-duplicates uploaded under different filenames before the hash
   check would catch a byte-identical file) — an empty result here is
   confirmation the duplicate-prevention system is working, not a broken
   feature.

2. "Expired Policies" — there is no expiration-date field anywhere in the
   document schema; nothing in this system tracks "this policy expires on
   X." Rather than fabricate that data, expired-policy detection is
   implemented as a proxy: documents older than a configurable threshold
   (default 365 days since last update), same underlying query as "stale
   documents" with a stricter default cutoff. If real expiration dates
   matter for your use case, that's a schema addition (e.g. a
   `document_metadata` row with key="expires_at") for a future phase, not
   something this phase invents data for.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.extensions import db
from app.chat.models import ChatMessage, Citation
from app.documents.models import Document, DocumentChunk
from app.chat.prompt_builder import INSUFFICIENT_CONTEXT_RESPONSE
from app.retrieval.reranker import _tokenize
from collections import Counter


def get_unanswered_questions(limit: int = 50) -> list[dict]:
    """Assistant messages that gave the standard 'not available in the
    enterprise knowledge base' fallback — i.e. retrieval found nothing
    usable, or nothing was cited. This IS the "Missing Knowledge Areas"
    data source too (see get_missing_knowledge_areas() below, which just
    re-buckets these same questions by keyword)."""
    rows = (
        ChatMessage.query.filter(
            ChatMessage.role == "assistant",
            ChatMessage.content == INSUFFICIENT_CONTEXT_RESPONSE,
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for msg in rows:
        preceding = (
            ChatMessage.query.filter(
                ChatMessage.session_id == msg.session_id, ChatMessage.role == "user",
                ChatMessage.created_at <= msg.created_at,
            )
            .order_by(ChatMessage.created_at.desc()).first()
        )
        results.append({
            "message_id": msg.id,
            "question": preceding.content if preceding else None,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })
    return results


def get_missing_knowledge_areas(limit: int = 20) -> list[dict]:
    """Keyword-frequency over unanswered questions — same honest 'this is
    frequency analysis, not topic modeling' caveat as analytics/service.py's
    get_most_asked_topics()."""
    unanswered = get_unanswered_questions(limit=500)  # wider sample for frequency analysis than the display limit
    counter = Counter()
    for row in unanswered:
        if row["question"]:
            counter.update(_tokenize(row["question"]).keys())
    return [{"term": term, "count": count} for term, count in counter.most_common(limit)]


def get_low_confidence_responses(threshold: float = 0.3, limit: int = 50) -> list[dict]:
    """Assistant messages where every citation fell below the similarity
    threshold — a real answer was given, but retrieval wasn't confident
    about it. Threshold is meaningful once a real embedding provider is
    configured (see the README's repeated caveat on dev-only embeddings'
    similarity scores not being semantically comparable)."""
    messages = (
        ChatMessage.query.filter(ChatMessage.role == "assistant", ChatMessage.content != INSUFFICIENT_CONTEXT_RESPONSE)
        .order_by(ChatMessage.created_at.desc())
        .limit(500)  # scan a bounded recent window rather than the whole table
        .all()
    )

    results = []
    for msg in messages:
        if not msg.citations:
            continue
        max_score = max((c.confidence_score or 0) for c in msg.citations)
        if max_score < threshold:
            results.append({
                "message_id": msg.id,
                "content": msg.content[:300],
                "max_confidence": round(max_score, 4),
                "citation_count": len(msg.citations),
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })
        if len(results) >= limit:
            break
    return results


def get_never_retrieved_documents() -> list[dict]:
    cited_doc_ids = {row[0] for row in db.session.query(Citation.document_id).distinct().all() if row[0] is not None}
    docs = Document.query.filter(Document.status == "ready").all()
    return [
        {"document_id": d.id, "title": d.title, "department": d.department, "created_at": d.created_at.isoformat() if d.created_at else None}
        for d in docs if d.id not in cited_doc_ids
    ]


def get_duplicate_documents() -> list[dict]:
    """See module docstring — expected to be empty in normal operation."""
    rows = (
        db.session.query(Document.content_hash, func.count().label("count"))
        .group_by(Document.content_hash).having(func.count() > 1).all()
    )
    results = []
    for content_hash, count in rows:
        docs = Document.query.filter_by(content_hash=content_hash).all()
        results.append({
            "content_hash": content_hash, "count": count,
            "documents": [{"id": d.id, "title": d.title, "created_at": d.created_at.isoformat() if d.created_at else None} for d in docs],
        })
    return results


def get_stale_documents(days_threshold: int = 180) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
    docs = Document.query.filter(Document.status == "ready", Document.updated_at < cutoff).order_by(Document.updated_at.asc()).all()
    return [
        {
            "document_id": d.id, "title": d.title, "department": d.department,
            "last_updated": d.updated_at.isoformat() if d.updated_at else None,
            "days_since_update": (datetime.now(timezone.utc) - d.updated_at.replace(tzinfo=timezone.utc)).days if d.updated_at else None,
        }
        for d in docs
    ]


def get_expired_policies(days_threshold: int = 365) -> list[dict]:
    """Proxy for real expiration tracking — see module docstring."""
    return get_stale_documents(days_threshold=days_threshold)


def get_knowledge_coverage() -> dict:
    total_docs = Document.query.filter(Document.status == "ready").count()
    total_chunks = DocumentChunk.query.count()
    cited_doc_count = len({row[0] for row in db.session.query(Citation.document_id).distinct().all() if row[0] is not None})

    by_department = dict(
        db.session.query(Document.department, func.count()).filter(Document.status == "ready").group_by(Document.department).all()
    )
    by_source_type = dict(
        db.session.query(Document.source_type, func.count()).filter(Document.status == "ready").group_by(Document.source_type).all()
    )
    by_file_type = dict(
        db.session.query(Document.file_type, func.count()).filter(Document.status == "ready").group_by(Document.file_type).all()
    )

    return {
        "total_documents": total_docs,
        "total_chunks": total_chunks,
        "documents_ever_retrieved": cited_doc_count,
        "documents_never_retrieved": total_docs - cited_doc_count,
        "coverage_rate": round(cited_doc_count / total_docs, 4) if total_docs else None,
        "by_department": {k or "(none)": v for k, v in by_department.items()},
        "by_source_type": by_source_type,
        "by_file_type": by_file_type,
    }
