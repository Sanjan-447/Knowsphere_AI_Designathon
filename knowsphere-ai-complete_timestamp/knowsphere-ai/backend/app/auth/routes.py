"""
Authentication endpoints: login, logout, refresh, current user, and
admin-only user creation.

Self-service registration is intentionally NOT exposed — enterprise user
provisioning belongs behind admin action (or, in a later phase, SSO/SCIM
federation from the org's identity provider per the architecture blueprint).
Phase 1 bootstraps the first admin via the `flask seed-admin` CLI command
(see app/cli.py).
"""
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    decode_token,
)

from app.extensions import db
from app.common.responses import success_response
from app.common.errors import AppError
from app.auth.models import User, RefreshSession
from app.auth.decorators import require_role
from app.rbac.models import Role, ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE
from app.audit.service import log_action
from app.audit.models import ACTION_LOGIN, ACTION_LOGOUT, ACTION_RBAC_CHANGE, ACTION_ADMIN_ACTION
from app.security.rate_limit import limiter

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

ALL_ROLES = {ROLE_ADMIN, ROLE_MANAGER, ROLE_EMPLOYEE}


def _issue_tokens(user: User):
    """Create an access + refresh token pair and persist the refresh session."""
    extra_claims = {"role": user.role.name, "display_name": user.display_name}

    access_token = create_access_token(identity=str(user.id), additional_claims=extra_claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=extra_claims)

    refresh_jti = decode_token(refresh_token)["jti"]
    refresh_exp = datetime.fromtimestamp(decode_token(refresh_token)["exp"], tz=timezone.utc)

    session = RefreshSession(
        jti=refresh_jti,
        user_id=user.id,
        user_agent=request.headers.get("User-Agent", "")[:255],
        ip_address=request.remote_addr,
        expires_at=refresh_exp,
    )
    db.session.add(session)
    db.session.commit()

    return access_token, refresh_token


@auth_bp.post("/login")
@limiter.limit("10 per minute")
def login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        raise AppError("VALIDATION_ERROR", "email and password are required.", 422)

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        log_action(ACTION_LOGIN, actor_email=email, details={"result": "failed"})
        raise AppError("INVALID_CREDENTIALS", "Invalid email or password.", 401)

    if not user.is_active:
        log_action(ACTION_LOGIN, actor_user_id=user.id, actor_email=email, details={"result": "account_disabled"})
        raise AppError("ACCOUNT_DISABLED", "This account has been disabled.", 403)

    user.last_login_at = datetime.now(timezone.utc)
    db.session.commit()

    access_token, refresh_token = _issue_tokens(user)
    log_action(ACTION_LOGIN, actor_user_id=user.id, actor_email=user.email, actor_role=user.role.name,
               details={"result": "success"})

    return success_response(
        data={
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
        message="Login successful.",
    )


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    claims = get_jwt()
    user_id = get_jwt_identity()
    jti = claims["jti"]

    session = RefreshSession.query.filter_by(jti=jti).first()
    if not session or session.revoked:
        raise AppError("INVALID_REFRESH_TOKEN", "Refresh token is invalid or has been revoked.", 401)

    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise AppError("REFRESH_TOKEN_EXPIRED", "Refresh token has expired. Please log in again.", 401)

    user = User.query.get(int(user_id))
    if not user or not user.is_active:
        raise AppError("ACCOUNT_DISABLED", "This account is no longer active.", 403)

    # Rotate: revoke the used refresh token and issue a new pair.
    session.revoked = True
    db.session.commit()

    access_token, refresh_token = _issue_tokens(user)

    return success_response(
        data={"access_token": access_token, "refresh_token": refresh_token},
        message="Token refreshed.",
    )


@auth_bp.post("/logout")
@jwt_required(refresh=True)
def logout():
    claims = get_jwt()
    session = RefreshSession.query.filter_by(jti=claims["jti"]).first()
    if session:
        session.revoked = True
        db.session.commit()
    log_action(ACTION_LOGOUT, actor_user_id=int(get_jwt_identity()))
    return success_response(message="Logged out.")


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        raise AppError("NOT_FOUND", "User not found.", 404)
    return success_response(data=user.to_dict())


@auth_bp.post("/users")
@require_role(ROLE_ADMIN)
def create_user():
    """Admin-only: provision a new user with a role."""
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    display_name = (payload.get("display_name") or "").strip()
    role_name = (payload.get("role") or ROLE_EMPLOYEE).strip().lower()

    if not email or not password or not display_name:
        raise AppError("VALIDATION_ERROR", "email, password, and display_name are required.", 422)

    if role_name not in ALL_ROLES:
        raise AppError("VALIDATION_ERROR", f"role must be one of {sorted(ALL_ROLES)}.", 422)

    if User.query.filter_by(email=email).first():
        raise AppError("USER_EXISTS", "A user with this email already exists.", 409)

    role = Role.query.filter_by(name=role_name).first()
    if not role:
        raise AppError("ROLE_NOT_FOUND", "Configured role does not exist. Run database seeding.", 500)

    user = User(email=email, display_name=display_name, role_id=role.id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    log_action(ACTION_RBAC_CHANGE, actor_user_id=int(get_jwt_identity()), resource_type="user",
               resource_id=user.id, details={"action": "user_created", "assigned_role": role_name})

    return success_response(data=user.to_dict(), message="User created.", status_code=201)


@auth_bp.get("/users")
@require_role(ROLE_ADMIN)
def list_users():
    """Admin Panel: User Management list — who exists, their role, active status."""
    users = User.query.order_by(User.created_at.asc()).all()
    return success_response(data=[u.to_dict() for u in users])


@auth_bp.patch("/users/<int:user_id>")
@require_role(ROLE_ADMIN)
def update_user(user_id: int):
    """Admin Panel: assign roles, disable/re-enable users. Both are
    RBAC-relevant actions, audited accordingly."""
    user = User.query.get(user_id)
    if not user:
        raise AppError("NOT_FOUND", "User not found.", 404)

    payload = request.get_json(silent=True) or {}
    changes = {}

    if "role" in payload:
        role_name = (payload["role"] or "").strip().lower()
        if role_name not in ALL_ROLES:
            raise AppError("VALIDATION_ERROR", f"role must be one of {sorted(ALL_ROLES)}.", 422)
        role = Role.query.filter_by(name=role_name).first()
        old_role = user.role.name if user.role else None
        user.role_id = role.id
        changes["role"] = {"from": old_role, "to": role_name}

    if "is_active" in payload:
        old_active = user.is_active
        user.is_active = bool(payload["is_active"])
        changes["is_active"] = {"from": old_active, "to": user.is_active}

    db.session.commit()

    if changes:
        log_action(ACTION_RBAC_CHANGE, actor_user_id=int(get_jwt_identity()), resource_type="user",
                   resource_id=user.id, details=changes)

    return success_response(data=user.to_dict(), message="User updated.")


@auth_bp.post("/users/<int:user_id>/reset-sessions")
@require_role(ROLE_ADMIN)
def reset_user_sessions(user_id: int):
    """Admin Panel: force-logout a user everywhere by revoking all their
    active refresh sessions — e.g. after a role change or a suspected
    compromised account."""
    user = User.query.get(user_id)
    if not user:
        raise AppError("NOT_FOUND", "User not found.", 404)

    revoked_count = RefreshSession.query.filter_by(user_id=user.id, revoked=False).update({"revoked": True})
    db.session.commit()

    log_action(ACTION_ADMIN_ACTION, actor_user_id=int(get_jwt_identity()), resource_type="user",
               resource_id=user.id, details={"action": "reset_sessions", "sessions_revoked": revoked_count})

    return success_response(message=f"Revoked {revoked_count} active session(s) for {user.email}.")
