"""
LLM chat-completion provider abstraction.

Mirrors the same pattern as retrieval/embeddings.py: one interface, one
adapter class per vendor, selected via Phase 1's existing ProviderConfig
table. This is the "Selected LLM Provider" step of the Enterprise RAG
workflow — the RAG engine (app/retrieval/rag_service.py) calls
generate()/generate_stream() without knowing or caring which vendor is
behind it.

Honest limitation: this sandbox's network egress allowlist does not
include api.groq.com or openrouter.ai (the two providers actually
requested for this deployment), so those two adapters are implemented
against each vendor's publicly documented OpenAI-compatible API shape and
verified against a local mock server that reproduces that exact contract
(see tests/test_llm_providers.py) — not against the live services. The
same OpenAIStyleProvider class is used for OpenAI, Groq, OpenRouter, NVIDIA
NIM, and generic OpenAI-compatible endpoints, since all five expose the
same /chat/completions shape; only the base_url and model differ.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


class LLMError(Exception):
    pass


@dataclass
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class BaseLLMProvider(ABC):
    model_name: str = "unknown"

    #: Populated by generate()/generate_stream() with real token counts
    #: parsed from the provider's own response, when the provider reports
    #: them (most do, in the shape {"prompt_tokens": N, "completion_tokens": N}).
    #: None if the provider didn't report usage (common for streaming
    #: responses) or hasn't been called yet — callers should fall back to
    #: local token counting in that case. Deliberately an instance
    #: attribute rather than a generate() return-value change, so this is
    #: additive to the existing interface, not a breaking change to every
    #: call site that already calls generate().
    last_usage: dict | None = None

    @abstractmethod
    def generate(
        self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2
    ) -> str:
        """Return the full response text. Blocking, non-streaming."""
        ...

    def generate_stream(
        self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2
    ) -> Iterator[str]:
        """Yield response text incrementally. Default implementation falls
        back to a single non-streaming call yielded as one chunk; real
        adapters override this with true incremental streaming."""
        yield self.generate(messages, max_tokens=max_tokens, temperature=temperature)
