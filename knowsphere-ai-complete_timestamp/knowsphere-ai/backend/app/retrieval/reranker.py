"""
Re-ranking stage.

A full cross-encoder reranker (e.g. sentence-transformers) needs a model
download this sandbox's network allowlist can't reach, and is genuinely
heavy infrastructure for a project this size. Instead, LexicalOverlapReranker
implements a real, working hybrid signal: it blends the vector similarity
score with a keyword-overlap score (a lightweight BM25-inspired heuristic),
which measurably helps in the common case where a query uses the same
distinctive terms as the relevant chunk (e.g. "PTO", "wellness stipend") —
pure vector similarity can occasionally rank a topically-similar-but-wrong
chunk above the one with an exact term match.

BaseReranker is the interface future work (Phase 4+, or a real
cross-encoder once infra allows) plugs into without touching call sites.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter

from app.retrieval.vector_store import RetrievedChunk

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "to", "of", "in",
    "on", "for", "and", "or", "what", "how", "do", "does", "i", "my", "me", "can",
    "will", "should", "would", "it", "this", "that", "with", "as", "at", "by",
}


def _tokenize(text: str) -> Counter:
    words = [w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS and len(w) > 2]
    return Counter(words)


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        ...


class NoOpReranker(BaseReranker):
    """Leaves vector-similarity ordering untouched — useful for isolating
    vector search quality during testing/debugging."""

    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return chunks


class LexicalOverlapReranker(BaseReranker):
    #: weight given to the vector similarity score vs. the lexical overlap score
    vector_weight = 0.7
    lexical_weight = 0.3

    def rerank(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not chunks:
            return chunks

        query_terms = _tokenize(query)
        if not query_terms:
            return chunks

        scored = []
        for chunk in chunks:
            chunk_terms = _tokenize(chunk.content)
            overlap = sum((query_terms & chunk_terms).values())
            max_possible = sum(query_terms.values()) or 1
            lexical_score = min(overlap / max_possible, 1.0)

            blended = self.vector_weight * chunk.similarity_score + self.lexical_weight * lexical_score
            scored.append((blended, chunk))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [chunk for _, chunk in scored]
