"""
Response cache lookup/write nodes.

Wraps app.retrieval.response_cache exactly as Phase 3 used it — same key
composition (question + role + top_k + filters; deliberately NOT provider
id, and role is included as a security property, both explained in the
README's "Response Caching Explained" section), same TTL, same "only the
non-streaming path" scope. `use_cache=False` in state (set by the streaming
path, since these nodes are never wired into the streaming flow) or an
explicit `llm_provider_config` override both skip the lookup — matching
Phase 3's exact prior behavior.
"""
from app.agents.state import GraphState
from app.retrieval.response_cache import make_cache_key, get_cached, set_cached
from app.chat.citation_engine import CitationRecord


def cache_lookup_node(state: GraphState) -> dict:
    if not state.get("use_cache", True) or state.get("llm_provider_config") is not None:
        return {"cache_key": None, "cache_hit": False}

    cache_key = make_cache_key(
        question=state["question"], role=state["current_role"], top_k=state["top_k"],
        filters_repr=repr(state.get("filters")), provider_id=None,
    )
    cached = get_cached(cache_key)
    if not cached:
        return {"cache_key": cache_key, "cache_hit": False}

    return {
        "cache_key": cache_key,
        "cache_hit": True,
        "response_text": cached["response_text"],
        "citations": [CitationRecord(**c) for c in cached["citations"]],
        "retrieval_metadata": {**cached["retrieval_metadata"], "served_from_cache": True},
        "provider_used": cached["provider_used"],
        "model_used": cached["model_used"],
        "from_cache": True,
    }


def cache_write_node(state: GraphState) -> dict:
    """Only reached via the graph's conditional routing when there was a
    cache_key (i.e. cache lookup was attempted and missed) and the context
    wasn't empty — same "don't cache empty-context answers" rule as Phase 3.
    Also skips caching if the LLM call itself failed (had_error) — a
    transient provider outage shouldn't get served as a "cached answer" to
    everyone else asking the same question for the next 10 minutes."""
    cache_key = state.get("cache_key")
    context = state.get("context")
    if cache_key and context is not None and not context.is_empty and not state.get("had_error"):
        set_cached(cache_key, {
            "response_text": state["response_text"],
            "citations": [c.__dict__ for c in state.get("citations", [])],
            "retrieval_metadata": state["retrieval_metadata"],
            "provider_used": state["provider_used"],
            "model_used": state["model_used"],
        })
    return {}
