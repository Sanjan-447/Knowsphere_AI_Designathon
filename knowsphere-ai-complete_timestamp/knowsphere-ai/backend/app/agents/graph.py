"""
The RAG StateGraph — LangGraph as the workflow controller, per the Phase 4
spec. This module only wires together node functions defined elsewhere
(agents/nodes/*); it contains no business logic of its own, only routing
decisions (the conditional edge functions below).

Graph shape (matches the Phase 4 spec's workflow diagram):

    START -> injection_check
                |
                +-- flagged --> injection_refusal --> persist --> END
                |
                +-- clear --> cache_lookup
                                  |
                                  +-- hit --> persist --> END
                                  |
                                  +-- miss --> retrieval -> reranking ->
                                               context_builder -> prompt_builder ->
                                               resolve_llm_provider
                                                   |
                                                   +-- no provider --> no_provider --> persist --> END
                                                   |
                                                   +-- provider found --> llm_generation ->
                                                        citation_extraction -> cache_write -> persist -> END

This is used by RagService.answer() (the non-streaming path) end-to-end.
The streaming path (RagService.answer_stream()) calls the individual node
functions directly in the same order, up through prompt_builder, rather
than invoking this compiled graph — see rag_service.py's module docstring
for the full explanation of why token-level SSE streaming doesn't fit
LangGraph's node model, and answer_stream() reuses these exact same node
functions rather than duplicating their logic.
"""
from langgraph.graph import StateGraph, START, END

from app.agents.state import GraphState
from app.agents.nodes.injection_node import injection_check_node
from app.agents.nodes.cache_node import cache_lookup_node, cache_write_node
from app.agents.nodes.retrieval_nodes import retrieval_node, reranking_node, resolve_llm_provider_node
from app.agents.nodes.context_prompt_nodes import context_builder_node, prompt_builder_node
from app.agents.nodes.generation_nodes import (
    llm_generation_node, citation_extraction_node, no_provider_node, injection_refusal_node,
)
from app.agents.nodes.persistence_node import persistence_node, retrieval_metadata_node


def _route_after_injection(state: GraphState) -> str:
    return "injection_refusal" if state.get("injection_flagged") else "cache_lookup"


def _route_after_cache(state: GraphState) -> str:
    return "persist" if state.get("cache_hit") else "retrieval"


def _route_after_provider_resolution(state: GraphState) -> str:
    return "llm_generation" if state.get("llm_config") is not None else "no_provider"


def build_rag_graph():
    graph = StateGraph(GraphState)

    graph.add_node("injection_check", injection_check_node)
    graph.add_node("injection_refusal", injection_refusal_node)
    graph.add_node("cache_lookup", cache_lookup_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("reranking", reranking_node)
    graph.add_node("context_builder", context_builder_node)
    graph.add_node("prompt_builder", prompt_builder_node)
    graph.add_node("resolve_llm_provider", resolve_llm_provider_node)
    graph.add_node("no_provider", no_provider_node)
    graph.add_node("llm_generation", llm_generation_node)
    graph.add_node("citation_extraction", citation_extraction_node)
    graph.add_node("retrieval_metadata", retrieval_metadata_node)
    graph.add_node("cache_write", cache_write_node)
    graph.add_node("persist", persistence_node)

    graph.add_edge(START, "injection_check")
    graph.add_conditional_edges("injection_check", _route_after_injection, {
        "injection_refusal": "injection_refusal", "cache_lookup": "cache_lookup",
    })
    graph.add_edge("injection_refusal", "persist")

    graph.add_conditional_edges("cache_lookup", _route_after_cache, {
        "persist": "persist", "retrieval": "retrieval",
    })

    graph.add_edge("retrieval", "reranking")
    graph.add_edge("reranking", "context_builder")
    graph.add_edge("context_builder", "prompt_builder")
    graph.add_edge("prompt_builder", "resolve_llm_provider")
    graph.add_conditional_edges("resolve_llm_provider", _route_after_provider_resolution, {
        "llm_generation": "llm_generation", "no_provider": "no_provider",
    })

    graph.add_edge("no_provider", "persist")
    graph.add_edge("llm_generation", "citation_extraction")
    graph.add_edge("citation_extraction", "retrieval_metadata")
    graph.add_edge("retrieval_metadata", "cache_write")
    graph.add_edge("cache_write", "persist")

    graph.add_edge("persist", END)

    return graph.compile()


# Compiled once at import time — the graph structure itself is static;
# only the state passed to .invoke() varies per request.
rag_graph = build_rag_graph()
