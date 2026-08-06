"""
Embedding provider abstraction.

Mirrors the same "thin, boring interface per vendor" pattern the
architecture blueprint calls for with LLM providers (app/providers/*) — one
abstract method, one adapter class per vendor, selected via the existing
ProviderConfig table from Phase 1's provider management. Adding a new
embedding vendor later means one new adapter class and one registry entry.

Honest limitation: this sandbox's network egress is restricted to a fixed
allowlist that does not include api.openai.com or
generativelanguage.googleapis.com, so the OpenAI/Gemini adapters below are
implemented against each vendor's real, documented API shape but could not
be exercised against the live services from here. LocalDeterministicProvider
exists so the ingestion pipeline can be run and verified end-to-end in this
environment without real API keys — it is explicitly a dev/test stand-in,
never intended for production use, and is called out as such everywhere it
appears (config, logs, and the README).
"""
from __future__ import annotations

import hashlib
import struct
from abc import ABC, abstractmethod

import requests

from app.providers.models import ProviderConfig
from app.documents.models import EMBEDDING_DIMENSIONS


class EmbeddingError(Exception):
    pass


class BaseEmbeddingProvider(ABC):
    model_name: str = "unknown"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    model_name = "text-embedding-3-small"

    def __init__(self, api_key: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            resp = requests.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model_name, "input": texts},
                timeout=60,
            )
        except requests.RequestException as exc:
            raise EmbeddingError(f"OpenAI embeddings request failed: {exc}") from exc

        if not resp.ok:
            raise EmbeddingError(f"OpenAI embeddings API returned {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            ordered = sorted(data["data"], key=lambda d: d["index"])
            return [item["embedding"] for item in ordered]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingError(f"Unexpected response shape from OpenAI embeddings API: {exc}") from exc


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    model_name = "text-embedding-004"

    def __init__(self, api_key: str, base_url: str | None = None):
        self.api_key = api_key
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        # Gemini's embedContent endpoint is single-text; batch via batchEmbedContents where available.
        url = f"{self.base_url}/models/{self.model_name}:batchEmbedContents?key={self.api_key}"
        payload = {
            "requests": [
                {"model": f"models/{self.model_name}", "content": {"parts": [{"text": t}]}}
                for t in texts
            ]
        }
        try:
            resp = requests.post(url, json=payload, timeout=60)
        except requests.RequestException as exc:
            raise EmbeddingError(f"Gemini embeddings request failed: {exc}") from exc

        if not resp.ok:
            raise EmbeddingError(f"Gemini embeddings API returned {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            for item in data.get("embeddings", []):
                embeddings.append(item["values"])
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingError(f"Unexpected response shape from Gemini embeddings API: {exc}") from exc
        return embeddings


class OpenAICompatibleEmbeddingProvider(BaseEmbeddingProvider):
    """For self-hosted or third-party OpenAI-compatible embedding endpoints
    (e.g. a local vLLM/text-embeddings-inference server)."""

    model_name = "custom"

    def __init__(self, api_key: str | None, base_url: str, model_name: str | None = None):
        if not base_url:
            raise EmbeddingError("OpenAI-compatible embedding provider requires a base_url.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        if model_name:
            self.model_name = model_name

    def embed(self, texts: list[str]) -> list[list[float]]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            resp = requests.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json={"model": self.model_name, "input": texts},
                timeout=60,
            )
        except requests.RequestException as exc:
            raise EmbeddingError(f"OpenAI-compatible embeddings request failed: {exc}") from exc

        if not resp.ok:
            raise EmbeddingError(f"Embedding endpoint returned {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            ordered = sorted(data["data"], key=lambda d: d["index"])
            return [item["embedding"] for item in ordered]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingError(f"Unexpected response shape from embedding endpoint: {exc}") from exc


class LocalDeterministicProvider(BaseEmbeddingProvider):
    """
    DEV/TEST ONLY — never use in production.

    Produces a deterministic, hash-derived pseudo-embedding so the full
    ingestion pipeline (chunking -> embedding -> pgvector storage) can be
    exercised end-to-end without a real provider API key or network access.
    It is NOT semantically meaningful: similar text does not reliably
    produce similar vectors. This exists purely to prove the pipeline's
    plumbing works; real semantic retrieval quality requires a real
    provider (Phase 3 will surface a clear warning if this is still active
    when Enterprise RAG retrieval is implemented).
    """

    model_name = "local-deterministic-dev-only"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_embed(t) for t in texts]

    @staticmethod
    def _hash_embed(text: str) -> list[float]:
        vector = []
        seed = text.encode("utf-8")
        counter = 0
        while len(vector) < EMBEDDING_DIMENSIONS:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            # Unpack 8 floats (4 bytes each -> as unsigned ints, normalized to [-1, 1]) per digest chunk
            for i in range(0, len(digest) - 3, 4):
                if len(vector) >= EMBEDDING_DIMENSIONS:
                    break
                (val,) = struct.unpack(">I", digest[i:i + 4])
                vector.append((val / 0xFFFFFFFF) * 2 - 1)
            counter += 1
        return vector


def get_embedding_provider(provider_config: ProviderConfig | None) -> BaseEmbeddingProvider:
    """
    Resolve a Phase 1 ProviderConfig into an embedding adapter. Falls back to
    LocalDeterministicProvider (with a loud warning) if no embedding-capable
    provider is configured — see that class's docstring for why this is
    dev/test only.
    """
    import logging
    logger = logging.getLogger("knowsphere.embeddings")

    if provider_config is None:
        logger.warning(
            "No embedding provider configured — using LocalDeterministicProvider "
            "(dev/test only, NOT semantically meaningful). Configure an OpenAI, "
            "Gemini, or OpenAI-compatible provider in Settings for real embeddings."
        )
        return LocalDeterministicProvider()

    api_key = provider_config.get_api_key()

    if provider_config.provider_type == "openai":
        return OpenAIEmbeddingProvider(api_key=api_key, base_url=provider_config.base_url)
    if provider_config.provider_type == "gemini":
        return GeminiEmbeddingProvider(api_key=api_key, base_url=provider_config.base_url)
    if provider_config.provider_type == "openai_compatible":
        extra = provider_config.extra_config or {}
        return OpenAICompatibleEmbeddingProvider(
            api_key=api_key, base_url=provider_config.base_url, model_name=extra.get("embedding_model")
        )

    raise EmbeddingError(
        f"Provider type '{provider_config.provider_type}' does not support embeddings in Phase 2. "
        "Supported: openai, gemini, openai_compatible."
    )
