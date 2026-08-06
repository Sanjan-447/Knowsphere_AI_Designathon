"""
LLM Generation and Citation Extraction nodes.

llm_generation_node wraps providers/llm/factory.get_llm_provider() +
.generate() exactly as Phase 3's RagService.answer() called them,
including the same graceful-degradation-on-LLMError behavior (a provider
timeout/401/500/malformed-JSON becomes an apologetic message, never an
uncaught exception — the exact bugs found and fixed during Phase 3's
error-handling audit stay fixed here, since this is the same code, not a
rewrite of it).

citation_extraction_node wraps citation_engine.extract_citations() and the
same "belt-and-suspenders" empty-context substitution Phase 3 had.
"""
import logging

from app.agents.state import GraphState
from app.providers.llm.factory import get_llm_provider
from app.providers.llm.base import LLMError
from app.chat.citation_engine import extract_citations
from app.chat.prompt_builder import INSUFFICIENT_CONTEXT_RESPONSE
from app.security.prompt_injection_guard import INJECTION_REFUSAL
from app.documents.chunking import count_tokens
from app.notifications.service import notify

logger = logging.getLogger("knowsphere.agents.generation")


def _estimate_tokens_locally(messages, response_text: str) -> dict:
    """Fallback when the provider doesn't report real usage (streaming
    responses from these adapters don't parse it — see the LLM adapters'
    generate_stream() methods — and it's an honest estimate, not the real
    count, for any provider that simply doesn't return it)."""
    prompt_text = "\n".join(m.content for m in messages)
    return {"prompt_tokens": count_tokens(prompt_text), "completion_tokens": count_tokens(response_text)}


def llm_generation_node(state: GraphState) -> dict:
    llm_config = state.get("llm_config")
    context = state["context"]

    try:
        provider = get_llm_provider(llm_config)
        response_text = provider.generate(state["prompt_messages"])
        model_used = getattr(provider, "model_name", "unknown")
        usage = getattr(provider, "last_usage", None)
        had_error = False
    except LLMError as exc:
        logger.error("LLM generation failed: %s", exc)
        response_text = f"The assistant's language model provider returned an error: {exc}"
        model_used = "unknown"
        usage = None
        had_error = True
        notify("provider_failure", title=f"LLM provider error: {llm_config.display_name}",
               message=str(exc), severity="error", resource_type="provider_config", resource_id=llm_config.id)

    if context.is_empty and INSUFFICIENT_CONTEXT_RESPONSE not in response_text:
        response_text = INSUFFICIENT_CONTEXT_RESPONSE

    if not usage or usage.get("prompt_tokens") is None:
        usage = _estimate_tokens_locally(state["prompt_messages"], response_text)

    return {
        "response_text": response_text,
        "provider_used": llm_config.provider_type,
        "model_used": model_used,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "had_error": had_error,
    }


def citation_extraction_node(state: GraphState) -> dict:
    context = state["context"]
    citations = extract_citations(state["response_text"], context) if not context.is_empty else []
    return {"citations": citations}


def no_provider_node(state: GraphState) -> dict:
    """Reached when no LLM provider is configured/active at all — a
    distinct terminal node so this case is explicit in the graph rather
    than an if-check buried inside generation."""
    return {
        "response_text": "No LLM provider is configured yet. Ask an administrator to add one under Settings -> Provider settings.",
        "citations": [],
        "provider_used": "none",
        "model_used": "none",
    }


def injection_refusal_node(state: GraphState) -> dict:
    """Terminal node for the injection-flagged path."""
    return {
        "response_text": INJECTION_REFUSAL,
        "citations": [],
        "provider_used": "none",
        "model_used": "none",
    }
