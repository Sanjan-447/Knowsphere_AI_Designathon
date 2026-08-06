"""
Logging setup and per-request correlation ID.

Every request gets a UUID stored on flask.g and echoed back in the
X-Request-ID response header. This is included in the standardized response
envelope (app/common/responses.py) and is the join key that correlates an
HTTP request with its LangSmith trace (Phase 5's observability module) and
its audit log entry (Phase 5's audit module) — three different systems,
one shared correlation ID.

Phase 6 addition: LOG_FORMAT=json switches to structured JSON output (one
JSON object per line — the standard shape most log aggregators, e.g.
CloudWatch/Datadog/Loki, expect) instead of the human-readable text format
Phases 1-5 used in every terminal output shown throughout this project's
development. Text remains the default, since it's what every dev workflow
in this codebase has actually been read as; JSON is what a production
deployment should set.

The "distinct log categories" Phase 6 asks for (structured/error/
performance/security/Celery/retrieval logs) already exist as separate
named loggers throughout the codebase — knowsphere.security,
knowsphere.audit, knowsphere.cache, knowsphere.rag, knowsphere.agents.*,
knowsphere.ingestion, knowsphere.monitoring, knowsphere.notifications,
knowsphere.embeddings, knowsphere.errors, plus Celery's own
celery.* loggers — rather than a new taxonomy invented here. This module
just makes sure all of them get the same formatter, level, and
request-ID correlation, consistently.
"""
import json
import logging
import sys
import uuid

from flask import g, request


class JsonFormatter(logging.Formatter):
    """One JSON object per log line — request_id, logger name (which
    doubles as the category: knowsphere.security, knowsphere.audit, etc.),
    level, message, and timestamp. Exceptions get their traceback as a
    string field rather than interleaved free-text, so a log aggregator
    can index on it instead of pattern-matching a multi-line blob."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(app):
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    log_format = app.config.get("LOG_FORMAT", "text").lower()

    handler = logging.StreamHandler(sys.stdout)
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | req=%(request_id)s | %(message)s"
        ))

    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            try:
                record.request_id = getattr(g, "request_id", "-")
            except RuntimeError:
                # Outside of an application/request context (e.g. startup logs)
                record.request_id = "-"
            return True

    handler.addFilter(RequestIdFilter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(level)

    app.logger.handlers = [handler]
    app.logger.setLevel(level)

    # Celery's own loggers (celery.task, celery.worker, etc.) go through
    # the root logger's handler by default already, since they don't set
    # propagate=False — no extra wiring needed for "Celery logs" to share
    # the same format/level as everything else.


def register_request_id_middleware(app):
    @app.before_request
    def _assign_request_id():
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    @app.after_request
    def _echo_request_id(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        return response
