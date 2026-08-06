"""
Citation Engine.

Parses [n] markers out of the LLM's raw response and maps each one back to
the ContextBlock it referred to, producing the type-specific display fields
the Phase 3 spec calls for (documents get page/section, emails get
subject/sender/date, chat exports get channel/sender/timestamp, share
links get file_name/source). Also defends against a model citing a number
that was never actually in the context it was given — that's a
hallucinated citation, and gets dropped rather than shown as if it were real.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.documents.models import (
    Document, DocumentMetadata, SOURCE_EMAIL, SOURCE_CHAT_EXPORT, SOURCE_SHARE_LINK,
)
from app.retrieval.context_builder import ContextBundle, ContextBlock

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")


@dataclass
class CitationRecord:
    marker: int
    document_id: int
    chunk_id: int
    citation_type: str
    display_fields: dict
    snippet: str
    confidence_score: float


def _lookup_metadata(document_id: int, key: str) -> str | None:
    row = DocumentMetadata.query.filter_by(document_id=document_id, key=key).first()
    return row.value if row else None


def _lookup_source_last_modified(document_id: int) -> str | None:
    """source_last_modified is deliberately routed to Document's fixed
    column during ingestion (see documents/tasks.py), not into the flexible
    document_metadata table — so it must be looked up there, not via
    _lookup_metadata(). Missed on the first pass (caught by actually
    testing with a real uploaded .eml file, which is exactly why this
    project tests against real files rather than only unit-level mocks)."""
    doc = Document.query.get(document_id)
    if doc and doc.source_last_modified:
        return doc.source_last_modified.isoformat()
    return None


def _display_fields_for(block: ContextBlock) -> tuple[str, dict]:
    chunk = block.chunk
    source_type = chunk.document_source_type

    if source_type == SOURCE_EMAIL:
        return "email", {
            "subject": _lookup_metadata(chunk.document_id, "email_subject") or chunk.document_title,
            "sender": _lookup_metadata(chunk.document_id, "email_from") or "unknown",
            "date": _lookup_source_last_modified(chunk.document_id),
        }

    if source_type == SOURCE_CHAT_EXPORT:
        section = chunk.chunk_metadata.get("section", "")
        return "chat_export", {
            "channel": _lookup_metadata(chunk.document_id, "chat_platform") or chunk.document_title,
            "sender": None,  # individual sender isn't resolvable at the chunk level once messages are batched
            "timestamp": section,
        }

    if source_type == SOURCE_SHARE_LINK:
        return "share_link", {
            "file_name": chunk.document_title,
            "source": _lookup_metadata(chunk.document_id, "source_url") or "unknown",
        }

    # SOURCE_UPLOAD and anything else defaults to the generic "document" shape
    return "document", {
        "document_name": chunk.document_title,
        "page": chunk.chunk_metadata.get("page"),
        "section": chunk.chunk_metadata.get("section"),
    }


def extract_citations(response_text: str, context: ContextBundle) -> list[CitationRecord]:
    blocks_by_index = {b.index: b for b in context.blocks}

    cited_markers = sorted({int(m) for m in _CITATION_MARKER_RE.findall(response_text)})

    records = []
    for marker in cited_markers:
        block = blocks_by_index.get(marker)
        if block is None:
            # The model cited a source number that wasn't actually provided —
            # drop it silently rather than surface a citation to nothing.
            continue

        citation_type, display_fields = _display_fields_for(block)
        records.append(
            CitationRecord(
                marker=marker,
                document_id=block.chunk.document_id,
                chunk_id=block.chunk.chunk_id,
                citation_type=citation_type,
                display_fields=display_fields,
                snippet=block.chunk.content[:300],
                confidence_score=block.chunk.similarity_score,
            )
        )
    return records
