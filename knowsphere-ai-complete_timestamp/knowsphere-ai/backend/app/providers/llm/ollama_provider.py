"""
Ollama adapter, using its native /api/chat endpoint (NDJSON streaming, one
JSON object per line) rather than Ollama's newer OpenAI-compatibility mode
— native is more reliable across Ollama versions, and this is a purely
local, self-hosted provider so there's no vendor API contract drift to
worry about.
"""
import json
from typing import Iterator

import requests

from app.providers.llm.base import BaseLLMProvider, ChatMessage, LLMError


class OllamaProvider(BaseLLMProvider):
    def __init__(self, model: str, base_url: str | None = None):
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.model_name = model

    def generate(self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        try:
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
        except requests.RequestException as exc:
            raise LLMError(f"Ollama request failed (is `ollama serve` running at {self.base_url}?): {exc}") from exc

        if not resp.ok:
            raise LLMError(f"Ollama returned {resp.status_code}: {resp.text[:400]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMError(f"Ollama returned a 200 response that wasn't valid JSON: {resp.text[:400]}") from exc

        if "prompt_eval_count" in data or "eval_count" in data:
            self.last_usage = {
                "prompt_tokens": data.get("prompt_eval_count"),
                "completion_tokens": data.get("eval_count"),
            }

        try:
            return data["message"]["content"]
        except KeyError as exc:
            raise LLMError(f"Unexpected Ollama response shape: {data}") from exc

    def generate_stream(
        self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2
    ) -> Iterator[str]:
        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        try:
            resp = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120, stream=True)
        except requests.RequestException as exc:
            raise LLMError(f"Ollama streaming request failed: {exc}") from exc

        if not resp.ok:
            raise LLMError(f"Ollama returned {resp.status_code}: {resp.text[:400]}")

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = chunk.get("message", {}).get("content")
            if text:
                yield text
            if chunk.get("done"):
                break
