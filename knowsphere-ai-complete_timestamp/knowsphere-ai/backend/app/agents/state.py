"""
Graph state schema.

A plain TypedDict, not a Pydantic model — this graph runs synchronously,
in-process, and every value that flows through it (ProviderConfig rows,
RetrievedChunk dataclasses, ContextBundle, ChatMessage ORM objects) is a
live Python object, never serialized across a process boundary. A
validating schema would add overhead and friction for no real benefit
here; that's the "do not introduce unnecessary abstractions" instruction
from the Phase 4 spec applied concretely.

`total=False` because different nodes populate different subsets of this
dict as the graph progresses — e.g. `response_text` doesn't exist until
after the LLM generation node runs, and never gets set at all if the
injection guard short-circuits the graph.
"""
from __future__ import annotations

from typing import TypedDict, Any

from app.chat.models import ChatSession
from app.providers.models import ProviderConfig
from app.retrieval.vector_store import RetrievalFilters, RetrievedChunk
from app.retrieval.context_builder import ContextBundle


class GraphState(TypedDict, total=False):
    # --- input, set once before graph.invoke() ---
    session: ChatSession
    question: str
    current_role: str
    top_k: int
    similarity_threshold: float
    filters: RetrievalFilters | None
    llm_provider_config: ProviderConfig | None  # explicit override, if any
    use_cache: bool
    start_time: float  # time.monotonic() at invocation, for latency_ms

    # --- prompt injection node ---
    injection_flagged: bool

    # --- cache lookup node ---
    cache_key: str | None
    cache_hit: bool

    # --- retrieval node ---
    embedding_provider_config: ProviderConfig | None
    candidates: list[RetrievedChunk]
    embedding_model: str
    retrieval_start_time: float

    # --- reranking node ---
    reranked_chunks: list[RetrievedChunk]
    retrieval_time_ms: int

    # --- context builder node ---
    context: ContextBundle

    # --- prompt builder node ---
    prompt_messages: list  # list[app.providers.llm.base.ChatMessage]

    # --- LLM generation node ---
    llm_config: ProviderConfig | None  # resolved default, if no override was given
    response_text: str
    provider_used: str
    model_used: str
    prompt_tokens: int | None
    completion_tokens: int | None
    had_error: bool

    # --- citation extraction node ---
    citations: list  # list[app.chat.citation_engine.CitationRecord]

    # --- persistence node / final output ---
    retrieval_metadata: dict[str, Any]
    retrieval_error: str | None
    from_cache: bool
    latency_ms: int
