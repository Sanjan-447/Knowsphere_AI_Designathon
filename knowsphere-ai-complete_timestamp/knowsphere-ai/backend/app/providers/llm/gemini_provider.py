"""
Gemini generateContent/streamGenerateContent adapter. Same honest caveat as
the other non-Anthropic adapters: implemented against the documented API
shape, not verified against a live key from this sandbox (this environment
cannot reach generativelanguage.googleapis.com either).
"""
import json
from typing import Iterator

import requests

from app.providers.llm.base import BaseLLMProvider, ChatMessage, LLMError


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        if not api_key:
            raise LLMError("Gemini provider requires an API key.")
        self.api_key = api_key
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self.model_name = model

    def _build_payload(self, messages: list[ChatMessage], max_tokens: int, temperature: float) -> dict:
        system_parts = [m.content for m in messages if m.role == "system"]
        contents = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [{"text": m.content}]}
            for m in messages if m.role != "system"
        ]
        payload = {
            "contents": contents,
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return payload

    def generate(self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2) -> str:
        url = f"{self.base_url}/models/{self.model_name}:generateContent?key={self.api_key}"
        try:
            resp = requests.post(url, json=self._build_payload(messages, max_tokens, temperature), timeout=90)
        except requests.RequestException as exc:
            raise LLMError(f"Gemini request failed: {exc}") from exc

        if not resp.ok:
            raise LLMError(f"Gemini returned {resp.status_code}: {resp.text[:400]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMError(f"Gemini returned a 200 response that wasn't valid JSON: {resp.text[:400]}") from exc

        usage = data.get("usageMetadata")
        if usage:
            self.last_usage = {
                "prompt_tokens": usage.get("promptTokenCount"),
                "completion_tokens": usage.get("candidatesTokenCount"),
            }

        try:
            parts = data["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected Gemini response shape: {data}") from exc

    def generate_stream(
        self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2
    ) -> Iterator[str]:
        url = f"{self.base_url}/models/{self.model_name}:streamGenerateContent?alt=sse&key={self.api_key}"
        try:
            resp = requests.post(
                url, json=self._build_payload(messages, max_tokens, temperature), timeout=90, stream=True
            )
        except requests.RequestException as exc:
            raise LLMError(f"Gemini streaming request failed: {exc}") from exc

        if not resp.ok:
            raise LLMError(f"Gemini returned {resp.status_code}: {resp.text[:400]}")

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            try:
                chunk = json.loads(line[len("data:"):].strip())
                parts = chunk["candidates"][0]["content"]["parts"]
                for p in parts:
                    if p.get("text"):
                        yield p["text"]
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
