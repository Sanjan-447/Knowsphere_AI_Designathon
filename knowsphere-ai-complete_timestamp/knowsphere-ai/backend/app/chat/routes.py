"""
Chat API routes.

Open to any authenticated role (Employee included) — unlike documents and
providers, asking questions is the whole point of the assistant for every
role; what differs per role is which documents retrieval can see, enforced
inside RagService/vector_store, not at the route level.
"""
import json

from flask import Blueprint, request, Response, stream_with_context
from flask_jwt_extended import get_jwt_identity, get_jwt

from app.extensions import db
from app.common.responses import success_response
from app.common.errors import AppError
from app.auth.decorators import require_auth, require_role
from app.rbac.models import ROLE_ADMIN
from app.chat.models import ChatSession, ChatMessage, Feedback
from app.auth.models import User
from app.retrieval.vector_store import RetrievalFilters
from app.chat.rag_service import RagService

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")
rag_service = RagService()


def _current_role() -> str:
    return get_jwt().get("role")


def _get_owned_session(session_id: int) -> ChatSession:
    session = ChatSession.query.get(session_id)
    if not session or session.user_id != int(get_jwt_identity()):
        raise AppError("NOT_FOUND", "Chat session not found.", 404)
    return session


def _parse_filters(payload: dict) -> RetrievalFilters | None:
    f = payload.get("filters") or {}
    if not f:
        return None
    return RetrievalFilters(
        department=f.get("department"), source_type=f.get("source_type"), file_type=f.get("file_type"),
    )


@chat_bp.post("/sessions")
@require_auth
def create_session():
    user_id = int(get_jwt_identity())
    payload = request.get_json(silent=True) or {}
    session = ChatSession(user_id=user_id, title=payload.get("title") or "New chat")
    db.session.add(session)
    db.session.commit()
    return success_response(data=session.to_dict(), message="Chat created.", status_code=201)


@chat_bp.get("/sessions")
@require_auth
def list_sessions():
    user_id = int(get_jwt_identity())
    sessions = (
        ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.updated_at.desc()).all()
    )
    return success_response(data=[s.to_dict() for s in sessions])


@chat_bp.get("/sessions/<int:session_id>")
@require_auth
def get_session(session_id: int):
    session = _get_owned_session(session_id)
    return success_response(data=session.to_dict(include_messages=True))


@chat_bp.patch("/sessions/<int:session_id>")
@require_auth
def rename_session(session_id: int):
    session = _get_owned_session(session_id)
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        raise AppError("VALIDATION_ERROR", "title is required.", 422)
    session.title = title[:255]
    db.session.commit()
    return success_response(data=session.to_dict(), message="Chat renamed.")


@chat_bp.delete("/sessions/<int:session_id>")
@require_auth
def delete_session(session_id: int):
    session = _get_owned_session(session_id)
    db.session.delete(session)
    db.session.commit()
    return success_response(message="Chat deleted.")


@chat_bp.post("/sessions/<int:session_id>/messages")
@require_auth
def send_message(session_id: int):
    """Non-streaming send — used by simpler clients/testing. The frontend
    chat UI uses the SSE variant below for a live-typing experience."""
    session = _get_owned_session(session_id)
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()
    if not question:
        raise AppError("VALIDATION_ERROR", "message is required.", 422)

    top_k = int(payload.get("top_k", 8))
    filters = _parse_filters(payload)

    result = rag_service.answer(
        session=session, question=question, current_role=_current_role(),
        top_k=top_k, filters=filters,
    )

    return success_response(data={
        "response": result.response_text,
        "citations": [c.__dict__ for c in result.citations],
        "provider_used": result.provider_used,
        "model_used": result.model_used,
        "latency_ms": result.latency_ms,
        "from_cache": result.from_cache,
        "retrieval": result.retrieval_metadata,
    })


@chat_bp.post("/sessions/<int:session_id>/messages/stream")
@require_auth
def send_message_stream(session_id: int):
    """SSE streaming variant. Emits `data: {...}\\n\\n` events of shape
    {"type": "chunk", "text": "..."} while generating, then a final
    {"type": "done", "citations": [...], ...} event."""
    session = _get_owned_session(session_id)
    payload = request.get_json(silent=True) or {}
    question = (payload.get("message") or "").strip()
    if not question:
        raise AppError("VALIDATION_ERROR", "message is required.", 422)

    top_k = int(payload.get("top_k", 8))
    filters = _parse_filters(payload)
    current_role = _current_role()

    def event_stream():
        for chunk in rag_service.answer_stream(
            session=session, question=question, current_role=current_role, top_k=top_k, filters=filters,
        ):
            yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

        # After the generator is exhausted, the message + citations have
        # been persisted by rag_service; fetch the just-created assistant
        # message to emit a final structured event.
        last_message = session.messages[-1] if session.messages else None
        if last_message and last_message.role == "assistant":
            yield f"data: {json.dumps({'type': 'done', 'message': last_message.to_dict()})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'done', 'message': None})}\n\n"

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# ------------------------------------------------------------------
# Feedback (Phase 5)
# ------------------------------------------------------------------
@chat_bp.post("/messages/<int:message_id>/feedback")
@require_auth
def submit_feedback(message_id: int):
    message = ChatMessage.query.get(message_id)
    if not message:
        raise AppError("NOT_FOUND", "Message not found.", 404)

    # Only the session owner may rate their own conversation's messages.
    if message.session.user_id != int(get_jwt_identity()):
        raise AppError("NOT_FOUND", "Message not found.", 404)

    payload = request.get_json(silent=True) or {}
    rating = (payload.get("rating") or "").strip().lower()
    if rating not in ("helpful", "not_helpful"):
        raise AppError("VALIDATION_ERROR", "rating must be 'helpful' or 'not_helpful'.", 422)

    user_id = int(get_jwt_identity())
    existing = Feedback.query.filter_by(message_id=message_id, user_id=user_id).first()
    if existing:
        existing.rating = rating
        existing.comment = payload.get("comment")
    else:
        existing = Feedback(
            message_id=message_id, user_id=user_id, rating=rating, comment=payload.get("comment"),
        )
        db.session.add(existing)
    db.session.commit()

    return success_response(data=existing.to_dict(), message="Feedback recorded.")


# ------------------------------------------------------------------
# Admin retrieval dashboard
# ------------------------------------------------------------------
@chat_bp.get("/admin/recent-retrievals")
@require_role(ROLE_ADMIN)
def recent_retrievals():
    """
    Cross-user retrieval visibility for debugging/administration — per the
    spec's "Retrieval Dashboard: for debugging and administrator
    visibility." Shows recent assistant messages org-wide with their full
    retrieval metadata (retrieved documents, similarity scores, source
    types, chunk count, retrieval time, tokens). Admin-only: this
    necessarily surfaces other users' questions.
    """
    limit = min(int(request.args.get("limit", 50)), 200)

    messages = (
        ChatMessage.query.filter(ChatMessage.role == "assistant")
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for msg in messages:
        session = msg.session
        user = User.query.get(session.user_id) if session else None
        # The question is the immediately preceding user message in the same session.
        preceding = (
            ChatMessage.query.filter(
                ChatMessage.session_id == msg.session_id,
                ChatMessage.role == "user",
                ChatMessage.created_at <= msg.created_at,
            )
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        results.append({
            "message_id": msg.id,
            "session_id": msg.session_id,
            "user_email": user.email if user else None,
            "question": preceding.content if preceding else None,
            "response_preview": msg.content[:200],
            "provider_used": msg.provider_used,
            "model_used": msg.model_used,
            "latency_ms": msg.latency_ms,
            "retrieval_metadata": msg.retrieval_metadata,
            "citation_count": len(msg.citations),
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    return success_response(data={"results": results, "count": len(results)})


@chat_bp.get("/admin/messages/<int:message_id>/inspect")
@require_role(ROLE_ADMIN)
def inspect_message(message_id: int):
    """Retrieval Inspector: full debugging detail for one assistant message
    — retrieved chunks with similarity scores in ranking order, source
    documents, the final rendered context, the actual generated prompt,
    and citations. Admin/debugging only — this is the one place the raw
    prompt sent to the LLM is ever exposed via the API."""
    message = ChatMessage.query.get(message_id)
    if not message or message.role != "assistant":
        raise AppError("NOT_FOUND", "Assistant message not found.", 404)

    metadata = message.retrieval_metadata or {}
    return success_response(data={
        "message_id": message.id,
        "session_id": message.session_id,
        "content": message.content,
        "provider_used": message.provider_used,
        "model_used": message.model_used,
        "had_error": message.had_error,
        "prompt_tokens": message.prompt_tokens,
        "completion_tokens": message.completion_tokens,
        "latency_ms": message.latency_ms,
        "retrieved_chunks": metadata.get("retrieved", []),  # already in ranking order
        "retrieval_time_ms": metadata.get("retrieval_time_ms"),
        "embedding_model": metadata.get("embedding_model"),
        "context_tokens": metadata.get("context_tokens"),
        "context_truncated": metadata.get("context_truncated"),
        "final_context": metadata.get("final_context_render"),
        "generated_prompt": metadata.get("generated_prompt"),
        "citations": [c.to_dict() for c in message.citations],
        "served_from_cache": metadata.get("served_from_cache", False),
        "created_at": message.created_at.isoformat() if message.created_at else None,
    })
