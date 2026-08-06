"""
Vector store query layer.

This is the one place that talks pgvector directly. The critical property,
called out repeatedly since Phase 1's RBAC design: permission filtering
happens INSIDE this query (a SQL join against document_acl), not as a
post-filter on already-retrieved results. A chunk belonging to a document
the caller's role can't see is never fetched, let alone considered for
similarity ranking.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, or_

from app.extensions import db
from app.documents.models import Document, DocumentChunk, DocumentACL
from app.rbac.models import Role


@dataclass
class RetrievalFilters:
    department: str | None = None
    source_type: str | None = None
    file_type: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    document_ids: list[int] | None = None  # restrict to a specific set, e.g. for re-querying a citation


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    chunk_index: int
    content: str
    chunk_metadata: dict
    similarity_score: float  # 1 - cosine_distance, so higher = more similar
    document_title: str
    document_file_type: str
    document_source_type: str
    document_department: str | None


def _role_visibility_clause(role_name: str):
    """A document is visible to `role_name` if it has no ACL rows at all
    (open to everyone) or has an ACL row naming this role — mirrors
    Document.is_visible_to() from documents/routes.py, expressed as SQL so
    it runs as part of the query instead of a Python post-filter."""
    has_acl = (
        select(DocumentACL.id).where(DocumentACL.document_id == Document.id).exists()
    )
    allowed_for_role = (
        select(DocumentACL.id)
        .join(Role, Role.id == DocumentACL.role_id)
        .where(DocumentACL.document_id == Document.id, Role.name == role_name)
        .exists()
    )
    return or_(~has_acl, allowed_for_role)


def vector_search(
    query_embedding: list[float],
    *,
    current_role: str,
    top_k: int = 8,
    similarity_threshold: float = 0.0,
    filters: RetrievalFilters | None = None,
    bypass_acl: bool = False,
) -> list[RetrievedChunk]:
    """
    Cosine-similarity search over ready, active documents' chunks.

    similarity_threshold is expressed as similarity (0..1, higher=better),
    not raw cosine distance, so callers don't need to know pgvector's
    distance-operator convention. bypass_acl=True is for Admin/Manager
    document-management contexts (e.g. an admin testing retrieval across
    the whole library); the chat path always leaves it False.
    """
    filters = filters or RetrievalFilters()

    # pgvector's <=> operator returns cosine DISTANCE (0=identical, 2=opposite).
    # similarity = 1 - distance for the standard cosine case.
    distance_expr = DocumentChunk.embedding.cosine_distance(query_embedding)

    query = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.chunk_metadata,
            distance_expr.label("distance"),
            Document.title,
            Document.file_type,
            Document.source_type,
            Document.department,
        )
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.status == "ready")
        .where(DocumentChunk.embedding.isnot(None))
    )

    if not bypass_acl:
        query = query.where(_role_visibility_clause(current_role))

    if filters.department:
        query = query.where(Document.department == filters.department)
    if filters.source_type:
        query = query.where(Document.source_type == filters.source_type)
    if filters.file_type:
        query = query.where(Document.file_type == filters.file_type)
    if filters.created_after:
        query = query.where(Document.created_at >= filters.created_after)
    if filters.created_before:
        query = query.where(Document.created_at <= filters.created_before)
    if filters.document_ids:
        query = query.where(Document.id.in_(filters.document_ids))

    query = query.order_by(distance_expr.asc()).limit(top_k)

    rows = db.session.execute(query).all()

    results = []
    for row in rows:
        similarity = 1 - float(row.distance)
        if similarity < similarity_threshold:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=row.id,
                document_id=row.document_id,
                chunk_index=row.chunk_index,
                content=row.content,
                chunk_metadata=row.chunk_metadata or {},
                similarity_score=round(similarity, 4),
                document_title=row.title,
                document_file_type=row.file_type,
                document_source_type=row.source_type,
                document_department=row.department,
            )
        )
    return results
