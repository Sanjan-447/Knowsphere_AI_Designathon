"""
Resolves a Phase 1 ProviderConfig row into a ready-to-use LLM adapter.

Default model names are a starting point, not a guarantee — model catalogs
change often and this environment can't browse to verify current names.
Every default is overridable per-provider via ProviderConfig.extra_config
= {"model": "..."}  (set from the Settings UI). OpenRouter's default below
is deliberately a ":free"-tagged model, since that matches this
deployment's stated goal of running on free tiers.
"""
from app.providers.models import ProviderConfig
from app.providers.llm.base import BaseLLMProvider, LLMError
from app.providers.llm.openai_style import OpenAIStyleProvider
from app.providers.llm.anthropic_provider import AnthropicProvider
from app.providers.llm.gemini_provider import GeminiProvider
from app.providers.llm.ollama_provider import OllamaProvider

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
    "gemini": "gemini-1.5-flash",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.1-8b-instruct:free",
    "nvidia_nim": "meta/llama3-8b-instruct",
    "ollama": "llama3",
}

DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}


def get_llm_provider(provider_config: ProviderConfig) -> BaseLLMProvider:
    if provider_config is None:
        raise LLMError(
            "No LLM provider is configured and active. Add one under Settings -> "
            "Provider settings and set it as default."
        )

    ptype = provider_config.provider_type
    extra = provider_config.extra_config or {}
    model = extra.get("model") or DEFAULT_MODELS.get(ptype)
    api_key = provider_config.get_api_key()

    if ptype in ("openai", "groq", "openrouter", "nvidia_nim", "openai_compatible"):
        base_url = provider_config.base_url or DEFAULT_BASE_URLS.get(ptype)
        if not base_url:
            raise LLMError(f"Provider '{provider_config.display_name}' ({ptype}) has no base_url configured.")
        if not model:
            raise LLMError(
                f"No model configured for '{provider_config.display_name}'. "
                "Set extra_config.model in Settings."
            )
        return OpenAIStyleProvider(api_key=api_key, base_url=base_url, model=model)

    if ptype == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model, base_url=provider_config.base_url)

    if ptype == "gemini":
        return GeminiProvider(api_key=api_key, model=model, base_url=provider_config.base_url)

    if ptype == "ollama":
        return OllamaProvider(model=model, base_url=provider_config.base_url)

    raise LLMError(f"Provider type '{ptype}' is not supported for generation.")
