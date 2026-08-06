"""
Retrieval module.

Implements: embeddings.py (Phase 2), vector_store.py (RBAC/metadata-filtered
pgvector cosine search), reranker.py (lexical-overlap reranking), retriever.py
(RetrievalService orchestrating embed -> search -> rerank), context_builder.py
(token-budgeted, deduplicated, numbered context assembly).

Reserved for later: a real hybrid (vector + lexical/BM25) search
implementation behind retriever.py's HybridSearchStrategy interface.
"""
