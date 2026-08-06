"""
Analytics API. Read-only, admin+manager (managers reasonably need
visibility into usage/effectiveness for their teams without needing full
system-admin rights — consistent with how documents/providers already
split admin-only mutation from admin+manager read access elsewhere in
this codebase).
"""
from datetime import datetime

from flask import Blueprint, request

from app.common.responses import success_response
from app.common.errors import AppError
from app.auth.decorators import require_role
from app.rbac.models import ROLE_ADMIN, ROLE_MANAGER
from app.analytics import service
from app.analytics import knowledge_service
from app.analytics.export_service import export_response

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")

_ROLES = (ROLE_ADMIN, ROLE_MANAGER)


def _parse_filters() -> dict:
    filters = {}
    if request.args.get("date_from"):
        filters["date_from"] = datetime.fromisoformat(request.args["date_from"])
    if request.args.get("date_to"):
        filters["date_to"] = datetime.fromisoformat(request.args["date_to"])
    if request.args.get("department"):
        filters["department"] = request.args["department"]
    if request.args.get("user_id"):
        filters["user_id"] = int(request.args["user_id"])
    if request.args.get("provider"):
        filters["provider"] = request.args["provider"]
    return filters


@analytics_bp.get("/overview")
@require_role(*_ROLES)
def overview():
    return success_response(data=service.get_overview())


@analytics_bp.get("/trends")
@require_role(*_ROLES)
def trends():
    granularity = request.args.get("granularity", "day")
    if granularity not in ("day", "week", "month"):
        granularity = "day"
    return success_response(data=service.get_activity_trend(granularity=granularity, **_parse_filters()))


@analytics_bp.get("/topics")
@require_role(*_ROLES)
def topics():
    limit = min(int(request.args.get("limit", 20)), 100)
    return success_response(data=service.get_most_asked_topics(limit=limit, **_parse_filters()))


@analytics_bp.get("/documents")
@require_role(*_ROLES)
def frequently_accessed_documents():
    limit = min(int(request.args.get("limit", 20)), 100)
    return success_response(data=service.get_frequently_accessed_documents(limit=limit, **_parse_filters()))


@analytics_bp.get("/departments")
@require_role(*_ROLES)
def department_usage():
    return success_response(data=service.get_department_usage(**_parse_filters()))


@analytics_bp.get("/providers")
@require_role(*_ROLES)
def provider_usage():
    return success_response(data=service.get_provider_usage_distribution(**_parse_filters()))


@analytics_bp.get("/feedback")
@require_role(*_ROLES)
def feedback_summary():
    return success_response(data=service.get_feedback_summary(**_parse_filters()))


# ------------------------------------------------------------------
# Knowledge Intelligence Dashboard — admin-only (governance/gap-analysis
# surfaces, not routine usage metrics)
# ------------------------------------------------------------------
@analytics_bp.get("/knowledge/unanswered-questions")
@require_role(ROLE_ADMIN)
def unanswered_questions():
    limit = min(int(request.args.get("limit", 50)), 200)
    return success_response(data=knowledge_service.get_unanswered_questions(limit=limit))


@analytics_bp.get("/knowledge/missing-areas")
@require_role(ROLE_ADMIN)
def missing_knowledge_areas():
    limit = min(int(request.args.get("limit", 20)), 100)
    return success_response(data=knowledge_service.get_missing_knowledge_areas(limit=limit))


@analytics_bp.get("/knowledge/low-confidence")
@require_role(ROLE_ADMIN)
def low_confidence_responses():
    threshold = float(request.args.get("threshold", 0.3))
    limit = min(int(request.args.get("limit", 50)), 200)
    return success_response(data=knowledge_service.get_low_confidence_responses(threshold=threshold, limit=limit))


@analytics_bp.get("/knowledge/never-retrieved")
@require_role(ROLE_ADMIN)
def never_retrieved_documents():
    return success_response(data=knowledge_service.get_never_retrieved_documents())


@analytics_bp.get("/knowledge/duplicates")
@require_role(ROLE_ADMIN)
def duplicate_documents():
    return success_response(data=knowledge_service.get_duplicate_documents())


@analytics_bp.get("/knowledge/stale")
@require_role(ROLE_ADMIN)
def stale_documents():
    days = int(request.args.get("days", 180))
    return success_response(data=knowledge_service.get_stale_documents(days_threshold=days))


@analytics_bp.get("/knowledge/expired-policies")
@require_role(ROLE_ADMIN)
def expired_policies():
    days = int(request.args.get("days", 365))
    return success_response(data=knowledge_service.get_expired_policies(days_threshold=days))


@analytics_bp.get("/knowledge/coverage")
@require_role(ROLE_ADMIN)
def knowledge_coverage():
    return success_response(data=knowledge_service.get_knowledge_coverage())


# ------------------------------------------------------------------
# Export & Reporting
# ------------------------------------------------------------------
def _get_format() -> str:
    fmt = request.args.get("format", "csv").lower()
    if fmt not in ("csv", "excel", "pdf"):
        raise AppError("VALIDATION_ERROR", "format must be one of: csv, excel, pdf.", 422)
    return fmt


@analytics_bp.get("/export/overview")
@require_role(*_ROLES)
def export_overview():
    data = service.get_overview()
    rows = [{"metric": k, "value": v} for k, v in data.items()]
    return export_response(_get_format(), "Enterprise Overview", ["metric", "value"], rows, "overview_report")


@analytics_bp.get("/export/usage")
@require_role(*_ROLES)
def export_usage():
    granularity = request.args.get("granularity", "day")
    rows = service.get_activity_trend(granularity=granularity, **_parse_filters())
    fields = ["date", "query_count", "avg_response_time_ms", "avg_retrieval_time_ms", "total_tokens"]
    return export_response(_get_format(), "Usage Report", fields, rows, "usage_report",
                            subtitle=f"Granularity: {granularity}")


@analytics_bp.get("/export/feedback")
@require_role(*_ROLES)
def export_feedback():
    from app.chat.models import Feedback, ChatMessage
    query = Feedback.query.join(ChatMessage, ChatMessage.id == Feedback.message_id)
    query = _apply_filters_generic(query, **_parse_filters())
    entries = query.order_by(Feedback.created_at.desc()).limit(5000).all()

    rows = []
    for f in entries:
        rows.append({
            "feedback_id": f.id, "message_id": f.message_id, "rating": f.rating,
            "comment": f.comment or "", "created_at": f.created_at.isoformat() if f.created_at else "",
        })
    fields = ["feedback_id", "message_id", "rating", "comment", "created_at"]
    return export_response(_get_format(), "Feedback Report", fields, rows, "feedback_report")


def _apply_filters_generic(query, **filters):
    from app.chat.models import ChatMessage
    if filters.get("date_from"):
        query = query.filter(ChatMessage.created_at >= filters["date_from"])
    if filters.get("date_to"):
        query = query.filter(ChatMessage.created_at <= filters["date_to"])
    return query


@analytics_bp.get("/export/knowledge-gaps")
@require_role(ROLE_ADMIN)
def export_knowledge_gaps():
    rows = []
    for q in knowledge_service.get_unanswered_questions(limit=200):
        rows.append({"type": "unanswered_question", "detail": q["question"] or "", "extra": "", "created_at": q["created_at"] or ""})
    for area in knowledge_service.get_missing_knowledge_areas(limit=50):
        rows.append({"type": "missing_knowledge_area", "detail": area["term"], "extra": f"count={area['count']}", "created_at": ""})
    for doc in knowledge_service.get_never_retrieved_documents():
        rows.append({"type": "never_retrieved_document", "detail": doc["title"], "extra": doc.get("department") or "", "created_at": doc["created_at"] or ""})
    for doc in knowledge_service.get_stale_documents(days_threshold=180):
        rows.append({"type": "stale_document", "detail": doc["title"], "extra": f"{doc['days_since_update']} days old", "created_at": doc["last_updated"] or ""})

    fields = ["type", "detail", "extra", "created_at"]
    return export_response(_get_format(), "Knowledge Gap Report", fields, rows, "knowledge_gap_report")
