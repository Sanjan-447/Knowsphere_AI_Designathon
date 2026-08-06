"""
Conversation persistence node — the graph's terminal node.

Wraps exactly the same DB writes Phase 3's RagService._persist_and_return()
did: a user ChatMessage, an assistant ChatMessage with retrieval_metadata,
one Citation row per extracted citation, and the auto-titling behavior for
a brand-new session. Builds retrieval_metadata from whatever the earlier
nodes populated in state (cache hit, injection refusal, and normal-answer
paths all converge here with different subsets of state populated — this
node handles all three uniformly).
"""
import time

from app.extensions import db
from app.chat.models import ChatMessage, Citation
from app.agents.state import GraphState
from app.audit.service import log_action
from app.audit.models import ACTION_CHAT


def build_retrieval_metadata(state: GraphState) -> dict:
    # Cache-hit and injection-refusal paths already have a complete
    # retrieval_metadata dict from an earlier node (loaded from cache, or
    # {"injection_flagged": True}) — use it as-is rather than rebuilding.
    if state.get("retrieval_metadata"):
        return state["retrieval_metadata"]

    reranked = state.get("reranked_chunks", [])
    context = state.get("context")
    metadata = {
        "retrieval_time_ms": state.get("retrieval_time_ms", 0),
        "embedding_model": state.get("embedding_model", "unknown"),
        "top_k": state.get("top_k"),
        "chunks_considered": len(reranked),
        "context_truncated": context.truncated if context else False,
        "context_tokens": context.total_tokens if context else 0,
        "injection_flagged": state.get("injection_flagged", False),
        "served_from_cache": False,
        "retrieved": [
            {
                "document_id": c.document_id, "document_title": c.document_title,
                "similarity_score": c.similarity_score, "source_type": c.document_source_type,
                "chunk_id": c.chunk_id, "chunk_index": c.chunk_index,
            }
            for c in reranked
        ],
        # Retrieval Inspector fields (Phase 5) — deliberately included here
        # rather than as new ChatMessage columns, since this data is only
        # ever surfaced through the admin-only inspector endpoint
        # (GET /chat/admin/messages/{id}/inspect), never through the normal
        # session/message endpoints a regular user's chat UI calls. Those
        # endpoints never pass include_retrieval_metadata=True, so this
        # stays invisible to end users by construction, not by a
        # field-level permission check that could be forgotten somewhere.
        "final_context_render": context.render() if context and not context.is_empty else None,
        "generated_prompt": (
            [{"role": m.role, "content": m.content} for m in state["prompt_messages"]]
            if state.get("prompt_messages") else None
        ),
    }
    if state.get("retrieval_error"):
        metadata["retrieval_error"] = state["retrieval_error"]
    return metadata


def retrieval_metadata_node(state: GraphState) -> dict:
    """Runs after citation_extraction, before cache_write — its only job is
    making retrieval_metadata available in state before cache_write_node
    needs to read it. Without this as its own node, cache_write_node would
    run before persistence_node ever builds the metadata dict (a real bug
    caught by testing: cache_write_node raised a KeyError on
    'retrieval_metadata' the first time this graph actually ran an
    uncached, successful answer end-to-end)."""
    return {"retrieval_metadata": build_retrieval_metadata(state)}


def persistence_node(state: GraphState) -> dict:
    session = state["session"]
    retrieval_metadata = build_retrieval_metadata(state)
    latency_ms = int((time.monotonic() - state["start_time"]) * 1000)

    user_msg = ChatMessage(session_id=session.id, role="user", content=state["question"])
    db.session.add(user_msg)

    assistant_msg = ChatMessage(
        session_id=session.id, role="assistant", content=state["response_text"],
        provider_used=state.get("provider_used", "none"), model_used=state.get("model_used", "none"),
        latency_ms=latency_ms, retrieval_metadata=retrieval_metadata,
        prompt_tokens=state.get("prompt_tokens"), completion_tokens=state.get("completion_tokens"),
        had_error=state.get("had_error", False),
    )
    db.session.add(assistant_msg)
    db.session.flush()

    for record in state.get("citations", []):
        db.session.add(Citation(
            message_id=assistant_msg.id, marker=record.marker, document_id=record.document_id,
            chunk_id=record.chunk_id, citation_type=record.citation_type,
            display_fields=record.display_fields, snippet=record.snippet,
            confidence_score=record.confidence_score,
        ))

    if session.title == "New chat" and len(session.messages) == 0:
        session.title = state["question"][:80]

    db.session.commit()

    log_action(
        ACTION_CHAT, actor_user_id=session.user_id, resource_type="chat_session", resource_id=session.id,
        details={
            "question": state["question"][:300], "provider_used": state.get("provider_used"),
            "chunks_considered": retrieval_metadata.get("chunks_considered"),
            "retrieval_time_ms": retrieval_metadata.get("retrieval_time_ms"),
            "latency_ms": latency_ms, "citation_count": len(state.get("citations", [])),
            "injection_flagged": retrieval_metadata.get("injection_flagged", False),
        },
    )

    return {"retrieval_metadata": retrieval_metadata, "latency_ms": latency_ms}
