"""
Provider management endpoints.

Restricted to Admins — deciding which LLM vendor the whole org's assistant
calls, and holding the API keys for it, is an administrative action.
Phase 1 implements infrastructure only: storing config securely and running
lightweight format validation. Real connectivity checks (an actual signed
request to the provider) are deferred to the phase that implements the
provider adapters themselves (app/providers/openai_provider.py etc.).
"""
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity

from app.extensions import db
from app.common.responses import success_response
from app.common.errors import AppError
from app.auth.decorators import require_role
from app.rbac.models import ROLE_ADMIN
from app.providers.models import ProviderConfig
from app.providers.registry import SUPPORTED_PROVIDERS, is_supported, provider_metadata
from app.audit.service import log_action
from app.audit.models import ACTION_PROVIDER_CHANGE

providers_bp = Blueprint("providers", __name__, url_prefix="/providers")

VALID_CAPABILITIES = ("llm", "embedding", "both")
# Provider types with no embedding adapter implemented (see retrieval/embeddings.py)
# can only ever be "llm" — this is enforced below, not just a UI default.
LLM_ONLY_TYPES = ("anthropic", "groq", "openrouter", "nvidia_nim", "ollama")


def _default_capability(provider_type: str) -> str:
    return "llm" if provider_type in LLM_ONLY_TYPES else "both"


@providers_bp.get("/supported-types")
@require_role(ROLE_ADMIN)
def list_supported_types():
    return success_response(data=SUPPORTED_PROVIDERS)


@providers_bp.get("")
@require_role(ROLE_ADMIN)
def list_providers():
    providers = ProviderConfig.query.order_by(ProviderConfig.created_at.asc()).all()
    return success_response(data=[p.to_dict() for p in providers])


@providers_bp.get("/<int:provider_id>")
@require_role(ROLE_ADMIN)
def get_provider(provider_id: int):
    provider = ProviderConfig.query.get(provider_id)
    if not provider:
        raise AppError("PROVIDER_NOT_FOUND", "Provider not found.", 404)
    return success_response(data=provider.to_dict())


@providers_bp.post("")
@require_role(ROLE_ADMIN)
def create_provider():
    payload = request.get_json(silent=True) or {}
    display_name = (payload.get("display_name") or "").strip()
    provider_type = (payload.get("provider_type") or "").strip().lower()
    api_key = payload.get("api_key")
    base_url = (payload.get("base_url") or "").strip() or None
    extra_config = payload.get("extra_config") or {}

    if not display_name or not provider_type:
        raise AppError("VALIDATION_ERROR", "display_name and provider_type are required.", 422)

    if not is_supported(provider_type):
        raise AppError(
            "UNSUPPORTED_PROVIDER",
            f"'{provider_type}' is not a supported provider type. See GET /providers/supported-types.",
            422,
        )

    meta = provider_metadata(provider_type)
    if meta.get("requires_base_url") and not base_url:
        raise AppError("VALIDATION_ERROR", f"{meta['label']} requires a base_url.", 422)

    capability = (payload.get("capability") or _default_capability(provider_type)).strip().lower()
    if capability not in VALID_CAPABILITIES:
        raise AppError("VALIDATION_ERROR", f"capability must be one of {VALID_CAPABILITIES}.", 422)
    if provider_type in LLM_ONLY_TYPES and capability in ("embedding", "both"):
        raise AppError(
            "VALIDATION_ERROR",
            f"'{meta.get('label', provider_type)}' has no embedding adapter implemented; capability must be 'llm'.",
            422,
        )

    provider = ProviderConfig(
        display_name=display_name,
        provider_type=provider_type,
        capability=capability,
        base_url=base_url,
        extra_config=extra_config,
        created_by_user_id=int(get_jwt_identity()),
    )
    provider.set_api_key(api_key)

    db.session.add(provider)
    db.session.commit()

    log_action(ACTION_PROVIDER_CHANGE, actor_user_id=int(get_jwt_identity()), resource_type="provider_config",
               resource_id=provider.id, details={"action": "created", "provider_type": provider_type, "display_name": display_name})

    return success_response(data=provider.to_dict(), message="Provider created.", status_code=201)


@providers_bp.patch("/<int:provider_id>")
@require_role(ROLE_ADMIN)
def update_provider(provider_id: int):
    provider = ProviderConfig.query.get(provider_id)
    if not provider:
        raise AppError("PROVIDER_NOT_FOUND", "Provider not found.", 404)

    payload = request.get_json(silent=True) or {}

    if "display_name" in payload:
        provider.display_name = payload["display_name"].strip()
    if "capability" in payload:
        cap = (payload["capability"] or "").strip().lower()
        if cap not in VALID_CAPABILITIES:
            raise AppError("VALIDATION_ERROR", f"capability must be one of {VALID_CAPABILITIES}.", 422)
        if provider.provider_type in LLM_ONLY_TYPES and cap in ("embedding", "both"):
            raise AppError("VALIDATION_ERROR", "This provider type has no embedding adapter; capability must be 'llm'.", 422)
        provider.capability = cap
    if "api_key" in payload:
        provider.set_api_key(payload["api_key"])
    if "base_url" in payload:
        provider.base_url = payload["base_url"] or None
    if "extra_config" in payload:
        provider.extra_config = payload["extra_config"] or {}
    if "is_active" in payload:
        provider.is_active = bool(payload["is_active"])
        if not provider.is_active and provider.is_default:
            provider.is_default = False  # a disabled provider cannot remain the default

    db.session.commit()
    log_action(ACTION_PROVIDER_CHANGE, actor_user_id=int(get_jwt_identity()), resource_type="provider_config",
               resource_id=provider.id, details={"action": "updated", "fields": list(payload.keys())})
    return success_response(data=provider.to_dict(), message="Provider updated.")


@providers_bp.delete("/<int:provider_id>")
@require_role(ROLE_ADMIN)
def delete_provider(provider_id: int):
    provider = ProviderConfig.query.get(provider_id)
    if not provider:
        raise AppError("PROVIDER_NOT_FOUND", "Provider not found.", 404)
    db.session.delete(provider)
    db.session.commit()
    log_action(ACTION_PROVIDER_CHANGE, actor_user_id=int(get_jwt_identity()), resource_type="provider_config",
               resource_id=provider_id, details={"action": "deleted", "display_name": provider.display_name})
    return success_response(message="Provider deleted.")


@providers_bp.post("/<int:provider_id>/validate")
@require_role(ROLE_ADMIN)
def validate_provider(provider_id: int):
    """
    Phase 1 validation is format-only: confirms a key is present where
    required and (if the provider defines a known prefix) roughly matches
    the expected shape, plus that a base_url is set where required.

    This deliberately does NOT make an outbound network call to the
    provider yet — that lands with the real provider adapters.
    """
    provider = ProviderConfig.query.get(provider_id)
    if not provider:
        raise AppError("PROVIDER_NOT_FOUND", "Provider not found.", 404)

    meta = provider_metadata(provider.provider_type)
    errors = []

    needs_key = meta.get("key_prefix") is not None or provider.provider_type not in ("ollama",)
    if needs_key and not provider.encrypted_api_key:
        errors.append("API key is required for this provider type.")

    if meta.get("requires_base_url") and not provider.base_url:
        errors.append("base_url is required for this provider type.")

    expected_prefix = meta.get("key_prefix")
    if expected_prefix and provider.encrypted_api_key:
        actual_key = provider.get_api_key()
        if not actual_key.startswith(expected_prefix):
            errors.append(f"API key does not match the expected '{expected_prefix}' prefix for {meta.get('label')}.")

    passed = len(errors) == 0
    provider.last_validated_at = datetime.now(timezone.utc)
    provider.last_validation_status = "passed" if passed else "failed"
    db.session.commit()

    return success_response(
        data={"passed": passed, "errors": errors, "provider": provider.to_dict()},
        message="Validation passed." if passed else "Validation failed.",
    )


@providers_bp.post("/<int:provider_id>/activate")
@require_role(ROLE_ADMIN)
def set_default_provider(provider_id: int):
    """Set this provider as the org-wide default. Unsets any previous default."""
    provider = ProviderConfig.query.get(provider_id)
    if not provider:
        raise AppError("PROVIDER_NOT_FOUND", "Provider not found.", 404)

    if not provider.is_active:
        raise AppError("PROVIDER_INACTIVE", "Cannot set an inactive provider as default.", 422)

    ProviderConfig.query.filter(ProviderConfig.id != provider.id).update({"is_default": False})
    provider.is_default = True
    db.session.commit()

    log_action(ACTION_PROVIDER_CHANGE, actor_user_id=int(get_jwt_identity()), resource_type="provider_config",
               resource_id=provider.id, details={"action": "set_default", "display_name": provider.display_name})

    return success_response(data=provider.to_dict(), message=f"{provider.display_name} is now the default provider.")
