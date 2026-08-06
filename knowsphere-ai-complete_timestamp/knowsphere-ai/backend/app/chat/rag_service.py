"""
RAG Service — Phase 3's orchestrator, now backed by a LangGraph StateGraph
(Phase 4) instead of a hand-written sequence of method calls. The public
interface is UNCHANGED from Phase 3: routes.py, the frontend, and every
existing test call answer()/answer_stream() exactly as before.

Non-streaming path (answer()): builds an initial GraphState and runs it
through app.agents.graph.rag_graph end-to-end. Every step in the Phase 4
spec's workflow diagram (injection check -> cache lookup -> retrieval ->
reranking -> context builder -> prompt builder -> LLM generation ->
citation extraction -> persistence) is a real graph node; see
app/agents/graph.py for the wiring and app/agents/nodes/* for each node.

Streaming path (answer_stream()): does NOT invoke the compiled graph.
LangGraph's node model is "return a value once, synchronously" — it
doesn't fit a generator that needs to yield partial text incrementally
over SSE while the LLM is still producing tokens. Wrapping true token
streaming in a graph node would mean either (a) buffering the whole
response before yielding anything, silently defeating the entire point of
streaming, or (b) reaching for LangGraph's async/custom-stream-writer
machinery, which is real additional complexity for a feature (mid-generation
token streaming through the orchestration layer) nothing in this spec asks
for — the spec asks that streaming CONTINUE WORKING, not that it be
routed through the graph. So answer_stream() calls the exact same node
functions from app/agents/nodes/* directly, in the same order, up through
prompt_builder_node — reusing 100% of the same code the graph uses, just
invoked as plain function calls instead of through graph.invoke() — then
runs the token-by-token generate_stream() loop exactly as Phase 3 did,
then calls citation_extraction_node and persistence_node directly to
finish. Nothing about streaming's behavior changed; only where the
"prepare" steps' code lives changed (moved to agents/nodes/, shared with
the graph, not duplicated).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator

from app.chat.models import ChatSession
from app.retrieval.vector_store import RetrievalFilters
from app.retrieval.retriever import DEFAULT_SIMILARITY_THRESHOLD
from app.providers.models import ProviderConfig
from app.providers.llm.factory import get_llm_provider
from app.providers.llm.base import LLMError
from app.chat.prompt_builder import INSUFFICIENT_CONTEXT_RESPONSE
from app.security.prompt_injection_guard import INJECTION_REFUSAL
from app.notifications.service import notify

from app.agents.graph import rag_graph
from app.observability.service import traced_invoke, StreamTraceHandle
from app.agents.nodes.injection_node import injection_check_node
from app.agents.nodes.retrieval_nodes import retrieval_node, reranking_node, resolve_llm_provider_node
from app.agents.nodes.context_prompt_nodes import context_builder_node, prompt_builder_node
from app.agents.nodes.generation_nodes import citation_extraction_node, _estimate_tokens_locally
from app.agents.nodes.persistence_node import persistence_node


@dataclass
class RagAnswer:
    response_text: str
    citations: list
    retrieval_metadata: dict
    provider_used: str
    model_used: str
    latency_ms: int
    injection_flagged: bool
    from_cache: bool = False


class RagService:
    """
    Kept as a class (rather than bare module functions) purely for
    interface continuity with Phase 3 — routes.py does
    `rag_service = RagService()` and calls methods on it. It's a thin
    facade now: the real orchestration logic lives in the graph.
    """

    def answer(
        self,
        *,
        session: ChatSession,
        question: str,
        current_role: str,
        top_k: int = 8,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        filters: RetrievalFilters | None = None,
        llm_provider_config: ProviderConfig | None = None,
        use_cache: bool = True,
    ) -> RagAnswer:
        initial_state = {
            "session": session, "question": question, "current_role": current_role,
            "top_k": top_k, "similarity_threshold": similarity_threshold, "filters": filters,
            "llm_provider_config": llm_provider_config, "use_cache": use_cache,
            "start_time": time.monotonic(),
        }
        final_state = traced_invoke(rag_graph, initial_state)

        return RagAnswer(
            response_text=final_state["response_text"],
            citations=final_state.get("citations", []),
            retrieval_metadata=final_state.get("retrieval_metadata", {}),
            provider_used=final_state.get("provider_used", "none"),
            model_used=final_state.get("model_used", "none"),
            latency_ms=final_state.get("latency_ms", 0),
            injection_flagged=final_state.get("injection_flagged", False),
            from_cache=final_state.get("from_cache", False),
        )

    def answer_stream(
        self,
        *,
        session: ChatSession,
        question: str,
        current_role: str,
        top_k: int = 8,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        filters: RetrievalFilters | None = None,
        llm_provider_config: ProviderConfig | None = None,
    ) -> Iterator[str]:
        state = {
            "session": session, "question": question, "current_role": current_role,
            "top_k": top_k, "similarity_threshold": similarity_threshold, "filters": filters,
            "llm_provider_config": llm_provider_config, "use_cache": False,
            "start_time": time.monotonic(),
        }

        with StreamTraceHandle(question) as trace:
            # --- injection check (same node function the graph uses) ---
            state.update(injection_check_node(state))
            if state["injection_flagged"]:
                yield INJECTION_REFUSAL
                state.update({"response_text": INJECTION_REFUSAL, "citations": [], "provider_used": "none", "model_used": "none"})
                persistence_node(state)
                trace.record(outputs={"response": INJECTION_REFUSAL, "injection_flagged": True})
                return

            # --- prepare: retrieval -> reranking -> context -> prompt -> resolve provider ---
            state.update(retrieval_node(state))
            state.update(reranking_node(state))
            state.update(context_builder_node(state))
            state.update(prompt_builder_node(state))
            state.update(resolve_llm_provider_node(state))

            llm_config = state.get("llm_config")
            if llm_config is None:
                msg = "No LLM provider is configured yet. Ask an administrator to add one under Settings."
                yield msg
                state.update({"response_text": msg, "citations": [], "provider_used": "none", "model_used": "none"})
                persistence_node(state)
                trace.record(outputs={"response": msg, "provider_configured": False})
                return

            # --- the one part that stays a plain generator loop, not a graph node (see module docstring) ---
            full_text_parts = []
            provider = get_llm_provider(llm_config)
            trace_error = None
            had_error = False
            try:
                for chunk in provider.generate_stream(state["prompt_messages"]):
                    full_text_parts.append(chunk)
                    yield chunk
            except LLMError as exc:
                error_text = f"\n\n[The language model provider returned an error: {exc}]"
                full_text_parts.append(error_text)
                yield error_text
                trace_error = str(exc)
                had_error = True
                notify("provider_failure", title=f"LLM provider error (streaming): {llm_config.display_name}",
                       message=str(exc), severity="error", resource_type="provider_config", resource_id=llm_config.id)

            response_text = "".join(full_text_parts)
            context = state["context"]
            if context.is_empty and INSUFFICIENT_CONTEXT_RESPONSE not in response_text:
                response_text = INSUFFICIENT_CONTEXT_RESPONSE

            state["response_text"] = response_text
            state.update(citation_extraction_node(state))  # same node function the graph uses

            # Streaming responses from these adapters don't parse real usage
            # out of the stream (see the LLM adapters' generate_stream()
            # methods) — estimate locally rather than leave tokens null.
            usage = _estimate_tokens_locally(state["prompt_messages"], response_text)

            # --- finalize: persistence (same node function the graph uses) ---
            state.update({
                "provider_used": llm_config.provider_type, "model_used": getattr(provider, "model_name", "unknown"),
                "prompt_tokens": usage["prompt_tokens"], "completion_tokens": usage["completion_tokens"],
                "had_error": had_error,
            })
            persistence_node(state)

            trace.record(
                outputs={
                    "response": response_text, "citation_count": len(state.get("citations", [])),
                    "chunks_considered": len(state.get("reranked_chunks", [])),
                    "provider_used": llm_config.provider_type,
                },
                error=trace_error,
            )
