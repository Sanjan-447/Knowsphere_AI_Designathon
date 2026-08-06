"""
Route-level RBAC enforcement.

This is the "route decorator" half of the two-layer RBAC design from the
architecture blueprint (Section 11) — the other half, data-layer filtering,
arrives with the documents/retrieval modules in a later phase.
"""
from functools import wraps

from flask import g
from flask_jwt_extended import verify_jwt_in_request, get_jwt

from app.common.errors import AppError


def require_role(*allowed_roles: str):
    """Restrict an endpoint to one or more roles, e.g. @require_role("admin")."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")
            if role not in allowed_roles:
                raise AppError(
                    code="FORBIDDEN",
                    message=f"This action requires one of roles: {', '.join(allowed_roles)}.",
                    status_code=403,
                )
            g.current_user_role = role
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_auth(fn):
    """Require a valid access token, any role."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        return fn(*args, **kwargs)

    return wrapper
