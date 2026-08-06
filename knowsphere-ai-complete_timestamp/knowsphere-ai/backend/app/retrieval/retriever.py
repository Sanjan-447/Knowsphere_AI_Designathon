"""
The Retrieval Service — orchestrates "embed the query, search pgvector,
apply metadata/RBAC filters, rerank" into one call. This is what
rag_service.py (the top-level RAG orchestrator) calls; everything below
this is retrieval, everything above it is generation/prompting.

Hybrid search (combining this vector path with a real lexical/full-text
search path, e.g. Postgres tsvector) is intentionally NOT implemented here —
per the Phase 3 spec, this only needs an interface ready for it. See
HybridSearchStrategy below: a real hybrid implementation later means
writing one class here, not touching any caller.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict

from app.providers.models import ProviderConfig
from app.retrieval.embeddings import get_embedding_provider
from app.retrieval.vector_store import vector_search, RetrievalFilters, RetrievedChunk
from app.retrieval.reranker import BaseReranker, LexicalOverlapReranker

logger = logging.getLogger("knowsphere.retrieval")

DEFAULT_TOP_K = 8
DEFAULT_SIMILARITY_THRESHOLD = -1.0  # genuinely "no filtering" by default.
# Cosine similarity ranges [-1, 1], so -1.0 is an inclusive floor — nothing
# gets excluded. This was previously 0.0, which looked like "no filtering"
# but wasn't: caught during testing, the LocalDeterministicProvider's
# non-normalized pseudo-embeddings routinely produce negative similarity
# scores for legitimately-should-be-retrieved chunks, and a 0.0 floor
# silently dropped them. Real, properly-normalized embedding models rarely
# produce negative similarity for topically related text, so raising this
# threshold once a real embedding provider is configured is still the right
# call (see the Performance Recommendations in the README) — it just
# shouldn't be the *default*, since the default has to behave sanely with
# the dev-only fallback too.


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    retrieval_time_ms: int
    embedding_model: str
    query: str
    top_k: int

    def to_dict(self):
        return {
            "chunks": [asdict(c) for c in self.chunks],
            "retrieval_time_ms": self.retrieval_time_ms,
            "embedding_model": self.embedding_model,
            "query": self.query,
            "top_k": self.top_k,
            "chunk_count": len(self.chunks),
        }


class HybridSearchStrategy:
    """Interface placeholder for future hybrid (vector + lexical) search.
    Not implemented in Phase 3 — semantic-only retrieval is what's asked
    for now; this class documents where a BM25/tsvector pass would plug in
    alongside vector_search() without changing RetrievalService's public
    surface."""

    def search(self, query: str, **kwargs):
        raise NotImplementedError("Hybrid search is reserved for a future phase.")


class RetrievalService:
    def __init__(self, reranker: BaseReranker | None = None):
        self.reranker = reranker or LexicalOverlapReranker()

    def search_candidates(
        self,
        query: str,
        *,
        current_role: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        filters: RetrievalFilters | None = None,
        embedding_provider_config: ProviderConfig | None = None,
        bypass_acl: bool = False,
    ) -> tuple[list[RetrievedChunk], str]:
        """Embed the query and run the RBAC/metadata-filtered pgvector search
        — the 'Retrieval' step, without reranking. Split out from retrieve()
        in Phase 4 so LangGraph can model retrieval and reranking as two
        distinct, independently-testable graph nodes (per the Phase 4 spec's
        workflow diagram) without duplicating this logic in the node itself.
        Returns over-fetched candidates (candidate_k, not top_k) — call
        rerank_candidates() to cut down to top_k.
        """
        embedder = get_embedding_provider(embedding_provider_config)
        query_vector = embedder.embed([query])[0]

        # Over-fetch before reranking so the lexical pass has real
        # candidates to reorder, not just the vector-only top_k.
        candidate_k = max(top_k * 3, top_k + 10)
        candidates = vector_search(
            query_vector,
            current_role=current_role,
            top_k=candidate_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
            bypass_acl=bypass_acl,
        )
        return candidates, embedder.model_name

    def rerank_candidates(self, query: str, candidates: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        """The 'Reranking' step, split out for the same reason as
        search_candidates() above — a distinct graph node, and also the
        natural seam for swapping in a real cross-encoder reranker later
        without touching retrieve() or any graph node's plumbing."""
        return self.reranker.rerank(query, candidates)[:top_k]

    def retrieve(
        self,
        query: str,
        *,
        current_role: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        filters: RetrievalFilters | None = None,
        embedding_provider_config: ProviderConfig | None = None,
        bypass_acl: bool = False,
    ) -> RetrievalResult:
        """Unchanged behavior/signature from Phase 3 — now implemented as
        search_candidates() + rerank_candidates() in sequence, so any
        existing caller (or test) of retrieve() sees identical results.
        Kept for callers that want retrieval+reranking as one call (e.g.
        ad-hoc debugging, or Phase 3's original test suite) without needing
        to know about the graph's two-node split."""
        start = time.monotonic()

        candidates, embedding_model = self.search_candidates(
            query, current_role=current_role, top_k=top_k, similarity_threshold=similarity_threshold,
            filters=filters, embedding_provider_config=embedding_provider_config, bypass_acl=bypass_acl,
        )
        reranked = self.rerank_candidates(query, candidates, top_k)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "retrieval query=%r role=%s results=%d time_ms=%d model=%s",
            query, current_role, len(reranked), elapsed_ms, embedding_model,
        )

        return RetrievalResult(
            chunks=reranked,
            retrieval_time_ms=elapsed_ms,
            embedding_model=embedding_model,
            query=query,
            top_k=top_k,
        )
