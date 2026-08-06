"""Unit tests for retrieval/reranker.py."""
from app.retrieval.reranker import LexicalOverlapReranker, NoOpReranker, _tokenize
from app.retrieval.vector_store import RetrievedChunk


def _chunk(chunk_id, content, score):
    return RetrievedChunk(
        chunk_id=chunk_id, document_id=chunk_id, chunk_index=0, content=content,
        chunk_metadata={}, similarity_score=score, document_title="Doc",
        document_file_type="txt", document_source_type="upload", document_department=None,
    )


def test_tokenize_strips_stopwords_and_short_words():
    tokens = _tokenize("What is the vacation policy for new hires?")
    assert "vacation" in tokens
    assert "policy" in tokens
    assert "the" not in tokens  # stopword
    assert "is" not in tokens   # stopword


def test_noop_reranker_preserves_order():
    chunks = [_chunk(1, "a", 0.9), _chunk(2, "b", 0.1)]
    result = NoOpReranker().rerank("query", chunks)
    assert [c.chunk_id for c in result] == [1, 2]


def test_lexical_reranker_boosts_exact_keyword_match():
    """A chunk with a near-tied vector similarity but a strong exact
    keyword match should outrank one with slightly higher similarity but
    zero lexical overlap — demonstrating the blend actually blends, not
    just defers to vector score. (Numbers chosen so this holds under the
    real 0.7/0.3 weighting used by LexicalOverlapReranker: blended score
    = 0.7*similarity + 0.3*lexical_overlap_ratio. With similarity 0.30 vs
    0.32 and lexical overlap 1.0 vs 0.0, chunk 1 scores 0.7*0.30+0.3*1.0=0.51
    against chunk 2's 0.7*0.32+0.3*0=0.224 — a wide enough margin that a
    reasonable range of overlap-detection edge cases still passes.)"""
    close_similarity_exact_match = _chunk(1, "wellness stipend amount is fixed", score=0.30)
    close_similarity_no_match = _chunk(2, "unrelated text about parking policy", score=0.32)

    reranked = LexicalOverlapReranker().rerank("wellness stipend amount", [close_similarity_exact_match, close_similarity_no_match])
    assert reranked[0].chunk_id == 1


def test_lexical_reranker_empty_query_falls_back_to_original_order():
    chunks = [_chunk(1, "text one", 0.2), _chunk(2, "text two", 0.9)]
    # A query with only stopwords tokenizes to nothing meaningful.
    result = LexicalOverlapReranker().rerank("is the a", chunks)
    assert [c.chunk_id for c in result] == [1, 2]


def test_lexical_reranker_handles_empty_chunk_list():
    assert LexicalOverlapReranker().rerank("anything", []) == []
