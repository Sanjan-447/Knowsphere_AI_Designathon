"""
OpenAI-compatible chat completions adapter.

Used for five provider_types that all speak the same wire format:
OpenAI itself, Groq, OpenRouter, NVIDIA NIM, and generic "openai_compatible"
endpoints. Only base_url, api_key, and model differ between them — see
factory.py for the per-provider defaults.

Default model names below are my best knowledge of what's currently
available on each platform's free/low-cost tier, but model catalogs change
frequently and I have no way to verify these are current from this
environment (no web search here). Treat them as a starting point — override
via the provider's extra_config.model field in Settings if a model has been
renamed or deprecated.
"""
import json
from typing import Iterator

import requests

from app.providers.llm.base import BaseLLMProvider, ChatMessage, LLMError


class OpenAIStyleProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None, base_url: str, model: str):
        if not base_url:
            raise LLMError("An OpenAI-compatible provider requires a base_url.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model_name = model

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _payload(self, messages: list[ChatMessage], max_tokens: int, temperature: float, stream: bool) -> dict:
        return {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

    def generate(self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2) -> str:
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(messages, max_tokens, temperature, stream=False),
                timeout=90,
            )
        except requests.RequestException as exc:
            raise LLMError(f"Request to {self.base_url} failed: {exc}") from exc

        if not resp.ok:
            raise LLMError(f"{self.base_url} returned {resp.status_code}: {resp.text[:400]}")

        try:
            data = resp.json()
        except ValueError as exc:  # requests raises simplejson/json's JSONDecodeError, a ValueError subclass
            raise LLMError(f"{self.base_url} returned a 200 response that wasn't valid JSON: {resp.text[:400]}") from exc

        usage = data.get("usage")
        if usage:
            self.last_usage = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            }

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected response shape from {self.base_url}: {data}") from exc

    def generate_stream(
        self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2
    ) -> Iterator[str]:
        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=self._payload(messages, max_tokens, temperature, stream=True),
                timeout=90,
                stream=True,
            )
        except requests.RequestException as exc:
            raise LLMError(f"Streaming request to {self.base_url} failed: {exc}") from exc

        if not resp.ok:
            raise LLMError(f"{self.base_url} returned {resp.status_code}: {resp.text[:400]}")

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                delta = chunk["choices"][0].get("delta", {})
                text = delta.get("content")
                if text:
                    yield text
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
