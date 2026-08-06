"""Unit tests for providers/registry.py."""
from app.providers.registry import is_supported, provider_metadata, SUPPORTED_PROVIDERS


def test_all_eight_providers_registered():
    expected = {"openai", "anthropic", "gemini", "groq", "openrouter", "nvidia_nim", "ollama", "openai_compatible"}
    assert set(SUPPORTED_PROVIDERS.keys()) == expected


def test_is_supported_true_for_known_type():
    assert is_supported("openai") is True
    assert is_supported("anthropic") is True


def test_is_supported_false_for_unknown_type():
    assert is_supported("cohere") is False
    assert is_supported("") is False


def test_provider_metadata_returns_expected_shape():
    meta = provider_metadata("openai")
    assert "label" in meta
    assert "key_prefix" in meta
    assert "requires_base_url" in meta


def test_local_providers_require_base_url():
    assert provider_metadata("ollama")["requires_base_url"] is True
    assert provider_metadata("openai_compatible")["requires_base_url"] is True


def test_hosted_providers_do_not_require_base_url():
    assert provider_metadata("openai")["requires_base_url"] is False
    assert provider_metadata("anthropic")["requires_base_url"] is False
