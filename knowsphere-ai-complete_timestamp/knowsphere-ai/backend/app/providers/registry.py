"""
Supported provider type registry.

Phase 1 defines the *shape* of provider management only — CRUD, secure key
storage, format validation, and default/active selection. Actual LLM calls
(app/providers/*_provider.py adapters implementing a common interface, per
the architecture blueprint Section 3/6) arrive in a later phase.
"""

# provider_type -> metadata used for basic validation and frontend display.
SUPPORTED_PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "key_prefix": "sk-",
        "requires_base_url": False,
    },
    "anthropic": {
        "label": "Anthropic Claude",
        "key_prefix": "sk-ant-",
        "requires_base_url": False,
    },
    "gemini": {
        "label": "Google Gemini",
        "key_prefix": None,
        "requires_base_url": False,
    },
    "groq": {
        "label": "Groq",
        "key_prefix": "gsk_",
        "requires_base_url": False,
    },
    "openrouter": {
        "label": "OpenRouter",
        "key_prefix": "sk-or-",
        "requires_base_url": False,
    },
    "nvidia_nim": {
        "label": "NVIDIA NIM",
        "key_prefix": "nvapi-",
        "requires_base_url": True,
    },
    "ollama": {
        "label": "Ollama (self-hosted)",
        "key_prefix": None,
        "requires_base_url": True,
    },
    "openai_compatible": {
        "label": "OpenAI-compatible endpoint",
        "key_prefix": None,
        "requires_base_url": True,
    },
}


def is_supported(provider_type: str) -> bool:
    return provider_type in SUPPORTED_PROVIDERS


def provider_metadata(provider_type: str) -> dict:
    return SUPPORTED_PROVIDERS.get(provider_type, {})
