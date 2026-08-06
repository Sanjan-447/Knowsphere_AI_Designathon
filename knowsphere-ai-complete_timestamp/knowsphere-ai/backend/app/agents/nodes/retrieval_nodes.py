"""
Retrieval and reranking nodes — two separate graph steps per the Phase 4
spec's workflow diagram, backed by the two methods split out of
RetrievalService.retrieve() in Phase 4 (see retriever.py's docstring on
search_candidates()/rerank_candidates() for why). Embedding-failure
degradation reuses the exact same _safe-style handling Phase 3 had in
RagService — moved here since retrieval is now a graph node rather than a
method Phase 3's RagService called directly.
"""
import logging
import time

from app.agents.state import GraphState
from app.retrieval.retriever import RetrievalService
from app.retrieval.embeddings import EmbeddingError
from app.providers.models import ProviderConfig
from app.notifications.service import notify

logger = logging.getLogger("knowsphere.agents.retrieval")

# Shared, stateless — safe to reuse across graph invocations, same pattern
# Phase 3's RagService used for its self.retrieval_service instance.
_retrieval_service = RetrievalService()


def _resolve_default_provider(provider_types: tuple[str, ...], required_capability: str) -> ProviderConfig | None:
    """Unchanged from Phase 3's rag_service.py — moved here since retrieval
    is now graph-node territory, but the query itself (and the capability
    bug-fix reasoning behind it) is identical."""
    capability_filter = ProviderConfig.capability.in_([required_capability, "both"])
    return ProviderConfig.query.filter(
        ProviderConfig.is_default.is_(True),
        ProviderConfig.is_active.is_(True),
        ProviderConfig.provider_type.in_(provider_types),
        capability_filter,
    ).first() or ProviderConfig.query.filter(
        ProviderConfig.is_active.is_(True),
        ProviderConfig.provider_type.in_(provider_types),
        capability_filter,
    ).first()


EMBEDDING_PROVIDER_TYPES = ("openai", "gemini", "openai_compatible")
LLM_PROVIDER_TYPES = ("openai", "anthropic", "gemini", "groq", "openrouter", "nvidia_nim", "ollama", "openai_compatible")


def retrieval_node(state: GraphState) -> dict:
    start = time.monotonic()
    embedding_config = _resolve_default_provider(EMBEDDING_PROVIDER_TYPES, required_capability="embedding")
    try:
        candidates, embedding_model = _retrieval_service.search_candidates(
            state["question"], current_role=state["current_role"], top_k=state["top_k"],
            similarity_threshold=state["similarity_threshold"], filters=state.get("filters"),
            embedding_provider_config=embedding_config,
        )
        return {
            "embedding_provider_config": embedding_config, "retrieval_start_time": start,
            "candidates": candidates, "embedding_model": embedding_model, "retrieval_error": None,
        }
    except EmbeddingError as exc:
        logger.error("Embedding/retrieval failed, degrading to empty candidates: %s", exc)
        notify("failed_retrieval", title="Retrieval failed for a chat query",
               message=str(exc), severity="error", resource_type="chat_query", extra={"question": state["question"][:200]})
        return {"embedding_provider_config": embedding_config, "retrieval_start_time": start, "candidates": [], "embedding_model": "unavailable", "retrieval_error": str(exc)}
    except Exception as exc:  # noqa: BLE001 — outermost retrieval safety net, same as Phase 3's _safe_retrieve
        logger.exception("Unexpected retrieval failure, degrading to empty candidates")
        notify("failed_retrieval", title="Unexpected retrieval failure for a chat query",
               message=str(exc), severity="error", resource_type="chat_query", extra={"question": state["question"][:200]})
        return {"embedding_provider_config": embedding_config, "retrieval_start_time": start, "candidates": [], "embedding_model": "unavailable", "retrieval_error": str(exc)}


def reranking_node(state: GraphState) -> dict:
    reranked = _retrieval_service.rerank_candidates(state["question"], state.get("candidates", []), state["top_k"])
    start = state.get("retrieval_start_time")
    elapsed_ms = int((time.monotonic() - start) * 1000) if start else 0
    return {"reranked_chunks": reranked, "retrieval_time_ms": elapsed_ms}


def resolve_llm_provider_node(state: GraphState) -> dict:
    """Resolves which LLM provider will answer — kept as its own tiny node
    (rather than folded into llm_generation_node) so the graph's conditional
    edge ("was a provider found?") can branch on it explicitly."""
    llm_config = state.get("llm_provider_config") or _resolve_default_provider(LLM_PROVIDER_TYPES, required_capability="llm")
    return {"llm_config": llm_config}
