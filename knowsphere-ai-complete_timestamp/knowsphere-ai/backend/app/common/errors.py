"""
Global error handling.

Registered on the app in the factory so every unhandled exception — HTTP
error or otherwise — comes back to the client in the standard error
envelope instead of Flask's default HTML error page.
"""
import logging
from werkzeug.exceptions import HTTPException
from app.common.responses import error_response

logger = logging.getLogger("knowsphere.errors")


class AppError(Exception):
    """Base class for application-raised errors with a stable error code.

    Raise this (or a subclass) anywhere in business logic when you want
    precise control over the code/message/status returned to the client,
    e.g. raise AppError("PROVIDER_NOT_FOUND", "Provider does not exist", 404)
    """

    def __init__(self, code: str, message: str, status_code: int = 400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        return error_response(err.code, err.message, err.status_code, err.details)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        return error_response(
            code=err.name.upper().replace(" ", "_"),
            message=err.description or err.name,
            status_code=err.code or 500,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        logger.exception("Unhandled exception")
        try:
            from app.notifications.service import notify
            notify("system_error", title="Unhandled application error",
                   message=str(err), severity="error", resource_type="request")
        except Exception:  # noqa: BLE001 — notification creation must never mask the original error response
            pass
        # Avoid leaking internals to the client; full trace goes to logs only.
        return error_response(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred. Please try again.",
            status_code=500,
        )
