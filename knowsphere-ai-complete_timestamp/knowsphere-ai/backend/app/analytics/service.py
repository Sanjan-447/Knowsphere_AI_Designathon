"""
Analytics service — pure aggregation over existing tables (chat_messages,
citations, documents, users, provider_configs). No new business data is
generated here; every number is derived from what the system already
recorded during Phases 1-4 plus this phase's token-tracking fix.

Cost estimation note: COST_PER_1K_TOKENS below is illustrative, not
verified current pricing — this environment can't browse the web to
confirm today's rates, and prices change often. Treat "Estimated API
Cost" as a rough order-of-magnitude figure and update the table with your
actual negotiated/current rates before trusting it for real budgeting.

"Most Asked Topics" is genuine keyword-frequency analysis (reusing the
same stopword-aware tokenizer from retrieval/reranker.py), not semantic
topic modeling/clustering — that would need either an LLM call per
question or a clustering library, both real additional scope beyond what
this phase asks for. Stated plainly so it isn't mistaken for something
more sophisticated than it is.
"""
from __future__ import annotations

from collections import Counter
from sqlalchemy import func, cast, Float

from app.extensions import db
from app.chat.models import ChatMessage, ChatSession, Citation, Feedback
from app.documents.models import Document
from app.auth.models import User
from app.retrieval.reranker import _tokenize

# Illustrative — see module docstring.
COST_PER_1K_TOKENS = {
    "openai": {"prompt": 0.00015, "completion": 0.0006},
    "anthropic": {"prompt": 0.003, "completion": 0.015},
    "gemini": {"prompt": 0.000075, "completion": 0.0003},
    "groq": {"prompt": 0.00005, "completion": 0.00008},
    "openrouter": {"prompt": 0.0, "completion": 0.0},  # varies wildly by model; 0 = "unknown, treat as free-tier"
    "nvidia_nim": {"prompt": 0.0002, "completion": 0.0002},
    "ollama": {"prompt": 0.0, "completion": 0.0},  # self-hosted — genuinely free beyond your own compute
    "openai_compatible": {"prompt": 0.0, "completion": 0.0},
}


def _apply_common_filters(query, *, date_from=None, date_to=None, department=None, user_id=None, provider=None):
    if date_from:
        query = query.filter(ChatMessage.created_at >= date_from)
    if date_to:
        query = query.filter(ChatMessage.created_at <= date_to)
    if provider:
        query = query.filter(ChatMessage.provider_used == provider)
    if user_id:
        query = query.join(ChatSession, ChatSession.id == ChatMessage.session_id).filter(ChatSession.user_id == user_id)
    if department:
        # Department lives on Document, reached via this message's citations.
        query = (
            query.join(Citation, Citation.message_id == ChatMessage.id)
            .join(Document, Document.id == Citation.document_id)
            .filter(Document.department == department)
        )
    return query


def get_overview() -> dict:
    """Enterprise Dashboard KPI cards."""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    total_documents = Document.query.count()
    from app.documents.models import DocumentChunk
    indexed_chunks = DocumentChunk.query.filter(DocumentChunk.embedding.isnot(None)).count()

    total_sessions = ChatSession.query.count()
    assistant_messages = ChatMessage.query.filter_by(role="assistant")
    total_queries = assistant_messages.count()

    avg_response_time = db.session.query(func.avg(cast(ChatMessage.latency_ms, Float))).filter(
        ChatMessage.role == "assistant", ChatMessage.latency_ms.isnot(None)
    ).scalar()

    avg_retrieval_time = db.session.query(
        func.avg(cast(ChatMessage.retrieval_metadata["retrieval_time_ms"].astext, Float))
    ).filter(ChatMessage.role == "assistant", ChatMessage.retrieval_metadata.isnot(None)).scalar()

    total_with_cache_flag = assistant_messages.filter(
        ChatMessage.retrieval_metadata["served_from_cache"].isnot(None)
    ).count()
    cache_hits = assistant_messages.filter(
        ChatMessage.retrieval_metadata["served_from_cache"].astext == "true"
    ).count()
    cache_hit_rate = (cache_hits / total_with_cache_flag) if total_with_cache_flag else 0.0

    token_totals = db.session.query(
        func.coalesce(func.sum(ChatMessage.prompt_tokens), 0),
        func.coalesce(func.sum(ChatMessage.completion_tokens), 0),
    ).filter(ChatMessage.role == "assistant").first()
    total_prompt_tokens, total_completion_tokens = token_totals

    estimated_cost = _estimate_cost_for_messages(assistant_messages)

    return {
        "total_users": total_users,
        "active_users": active_users,
        "uploaded_documents": total_documents,
        "indexed_chunks": indexed_chunks,
        "chat_sessions": total_sessions,
        "total_queries": total_queries,
        "avg_response_time_ms": round(avg_response_time, 1) if avg_response_time else 0,
        "avg_retrieval_time_ms": round(avg_retrieval_time, 1) if avg_retrieval_time else 0,
        "cache_hit_rate": round(cache_hit_rate, 4),
        "total_tokens_consumed": int(total_prompt_tokens) + int(total_completion_tokens),
        "estimated_api_cost_usd": round(estimated_cost, 4),
    }


def _estimate_cost_for_messages(query) -> float:
    rows = query.with_entities(ChatMessage.provider_used, ChatMessage.prompt_tokens, ChatMessage.completion_tokens).all()
    total = 0.0
    for provider_used, prompt_tokens, completion_tokens in rows:
        rates = COST_PER_1K_TOKENS.get(provider_used or "", {"prompt": 0.0, "completion": 0.0})
        total += ((prompt_tokens or 0) / 1000.0) * rates["prompt"]
        total += ((completion_tokens or 0) / 1000.0) * rates["completion"]
    return total


def get_provider_usage_distribution(**filters) -> list[dict]:
    query = _apply_common_filters(
        ChatMessage.query.filter(ChatMessage.role == "assistant"), **filters
    )
    rows = (
        query.with_entities(ChatMessage.provider_used, func.count(), func.avg(cast(ChatMessage.latency_ms, Float)))
        .group_by(ChatMessage.provider_used).all()
    )
    return [
        {"provider": provider or "none", "query_count": count, "avg_latency_ms": round(avg_latency, 1) if avg_latency else 0}
        for provider, count, avg_latency in rows
    ]


def get_activity_trend(granularity: str = "day", **filters) -> list[dict]:
    """Query volume, response time, retrieval latency, token consumption —
    all bucketed by the same time granularity so the frontend can plot
    them on one shared x-axis."""
    trunc_unit = {"day": "day", "week": "week", "month": "month"}.get(granularity, "day")
    bucket = func.date_trunc(trunc_unit, ChatMessage.created_at)

    query = _apply_common_filters(
        ChatMessage.query.filter(ChatMessage.role == "assistant"), **filters
    )
    rows = (
        query.with_entities(
            bucket.label("bucket"),
            func.count().label("query_count"),
            func.avg(cast(ChatMessage.latency_ms, Float)).label("avg_latency_ms"),
            func.avg(cast(ChatMessage.retrieval_metadata["retrieval_time_ms"].astext, Float)).label("avg_retrieval_ms"),
            func.coalesce(func.sum(ChatMessage.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(ChatMessage.completion_tokens), 0).label("completion_tokens"),
        )
        .group_by(bucket).order_by(bucket).all()
    )
    return [
        {
            "date": row.bucket.isoformat(),
            "query_count": row.query_count,
            "avg_response_time_ms": round(row.avg_latency_ms, 1) if row.avg_latency_ms else 0,
            "avg_retrieval_time_ms": round(row.avg_retrieval_ms, 1) if row.avg_retrieval_ms else 0,
            "total_tokens": int(row.prompt_tokens) + int(row.completion_tokens),
        }
        for row in rows
    ]


def get_most_asked_topics(limit: int = 20, **filters) -> list[dict]:
    """Keyword-frequency proxy for topics — see module docstring for what
    this genuinely is (and isn't)."""
    query = _apply_common_filters(ChatMessage.query.filter(ChatMessage.role == "user"), **filters)
    questions = [row[0] for row in query.with_entities(ChatMessage.content).all()]

    counter = Counter()
    for q in questions:
        counter.update(_tokenize(q).keys())

    return [{"term": term, "count": count} for term, count in counter.most_common(limit)]


def get_frequently_accessed_documents(limit: int = 20, **filters) -> list[dict]:
    query = Citation.query.join(ChatMessage, ChatMessage.id == Citation.message_id)
    query = _apply_common_filters(query, **filters)
    rows = (
        query.with_entities(Citation.document_id, func.count().label("citation_count"))
        .group_by(Citation.document_id).order_by(func.count().desc()).limit(limit).all()
    )
    doc_ids = [r.document_id for r in rows if r.document_id]
    docs_by_id = {d.id: d for d in Document.query.filter(Document.id.in_(doc_ids)).all()}
    return [
        {
            "document_id": r.document_id,
            "title": docs_by_id[r.document_id].title if r.document_id in docs_by_id else "(deleted document)",
            "citation_count": r.citation_count,
        }
        for r in rows
    ]


def get_department_usage(**filters) -> list[dict]:
    query = (
        Citation.query.join(ChatMessage, ChatMessage.id == Citation.message_id)
        .join(Document, Document.id == Citation.document_id)
    )
    if filters.get("date_from"):
        query = query.filter(ChatMessage.created_at >= filters["date_from"])
    if filters.get("date_to"):
        query = query.filter(ChatMessage.created_at <= filters["date_to"])

    rows = (
        query.with_entities(Document.department, func.count().label("citation_count"))
        .group_by(Document.department).order_by(func.count().desc()).all()
    )
    return [{"department": dept or "(none)", "citation_count": count} for dept, count in rows]


def get_feedback_summary(**filters) -> dict:
    query = Feedback.query.join(ChatMessage, ChatMessage.id == Feedback.message_id)
    query = _apply_common_filters(query, **filters)

    total = query.count()
    helpful = query.filter(Feedback.rating == "helpful").count()
    not_helpful = query.filter(Feedback.rating == "not_helpful").count()

    return {
        "total_feedback": total,
        "helpful": helpful,
        "not_helpful": not_helpful,
        "helpful_rate": round(helpful / total, 4) if total else None,
    }
