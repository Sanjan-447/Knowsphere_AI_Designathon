"""Unit tests for analytics/service.py — cost estimation and overview against a real (empty or seeded) DB."""
from app.analytics.service import _estimate_cost_for_messages, get_overview, COST_PER_1K_TOKENS


def test_cost_table_has_entries_for_all_llm_providers():
    for provider in ["openai", "anthropic", "gemini", "groq", "openrouter", "nvidia_nim", "ollama", "openai_compatible"]:
        assert provider in COST_PER_1K_TOKENS
        assert "prompt" in COST_PER_1K_TOKENS[provider]
        assert "completion" in COST_PER_1K_TOKENS[provider]


def test_ollama_and_openrouter_marked_as_zero_cost():
    """Self-hosted (Ollama) is genuinely free beyond your own compute;
    OpenRouter's rate varies too much by model to have one number, so it's
    marked 0 rather than a misleading average."""
    assert COST_PER_1K_TOKENS["ollama"]["prompt"] == 0.0
    assert COST_PER_1K_TOKENS["openrouter"]["prompt"] == 0.0


def test_get_overview_on_empty_database_returns_zeros_not_errors(app):
    with app.app_context():
        data = get_overview()
        assert data["total_users"] == 0
        assert data["total_queries"] == 0
        assert data["cache_hit_rate"] == 0.0
        assert data["estimated_api_cost_usd"] == 0.0


def test_get_overview_counts_seeded_admin_user(app, admin_user):
    with app.app_context():
        data = get_overview()
        assert data["total_users"] == 1
        assert data["active_users"] == 1
