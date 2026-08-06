"""Unit tests for chat/citation_engine.py."""
from app.chat.citation_engine import extract_citations
from app.retrieval.context_builder import ContextBundle, ContextBlock
from app.retrieval.vector_store import RetrievedChunk


def _block(index, chunk_id, title="Doc A", source_type="upload", score=0.5):
    chunk = RetrievedChunk(
        chunk_id=chunk_id, document_id=chunk_id, chunk_index=0, content="some text",
        chunk_metadata={"section": "§1"}, similarity_score=score,
        document_title=title, document_file_type="txt",
        document_source_type=source_type, document_department="HR",
    )
    return ContextBlock(index=index, chunk=chunk, token_count=5)


def test_extract_citations_single_marker():
    context = ContextBundle(blocks=[_block(1, 100)], total_tokens=5, truncated=False)
    citations = extract_citations("The answer is here [1].", context)
    assert len(citations) == 1
    assert citations[0].marker == 1
    assert citations[0].document_id == 100


def test_extract_citations_multiple_markers_all_captured():
    context = ContextBundle(blocks=[_block(1, 100), _block(2, 200), _block(3, 300)], total_tokens=15, truncated=False)
    citations = extract_citations("See [1] and [2] and [3].", context)
    assert sorted(c.marker for c in citations) == [1, 2, 3]


def test_extract_citations_rejects_hallucinated_marker():
    """The model citing [99] when only source [1] was ever provided must
    not produce a fake citation — this is the core anti-hallucination guarantee."""
    context = ContextBundle(blocks=[_block(1, 100)], total_tokens=5, truncated=False)
    citations = extract_citations("Based on [1] and also [99].", context)
    assert len(citations) == 1
    assert citations[0].marker == 1


def test_extract_citations_no_markers_returns_empty():
    context = ContextBundle(blocks=[_block(1, 100)], total_tokens=5, truncated=False)
    citations = extract_citations("No citation markers in this text at all.", context)
    assert citations == []


def test_extract_citations_duplicate_marker_deduplicates():
    context = ContextBundle(blocks=[_block(1, 100)], total_tokens=5, truncated=False)
    citations = extract_citations("See [1]. Also see [1] again.", context)
    assert len(citations) == 1


def test_extract_citations_email_type_has_correct_display_fields(app):
    chunk = RetrievedChunk(
        chunk_id=1, document_id=1, chunk_index=0, content="text", chunk_metadata={},
        similarity_score=0.5, document_title="An Email", document_file_type="eml",
        document_source_type="email", document_department=None,
    )
    context = ContextBundle(blocks=[ContextBlock(index=1, chunk=chunk, token_count=5)], total_tokens=5, truncated=False)
    citations = extract_citations("[1]", context)
    assert citations[0].citation_type == "email"
    assert "subject" in citations[0].display_fields
    assert "sender" in citations[0].display_fields
