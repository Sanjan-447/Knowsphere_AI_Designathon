"""
Anthropic Messages API adapter — kept separate from OpenAIStyleProvider
because Anthropic's wire format genuinely differs: `system` is a top-level
field (not a message with role="system"), and streaming uses named SSE
events (message_start, content_block_delta, message_stop) rather than
OpenAI's uniform "data: {...}" chunks.

api.anthropic.com IS reachable from this sandbox (unlike Groq/OpenRouter),
so this adapter's request/response shape reflects the documented /v1/messages
contract; the honest caveat from base.py's docstring still applies to
whether this exact code path has been exercised against a live key here.
"""
import json
from typing import Iterator

import requests

from app.providers.llm.base import BaseLLMProvider, ChatMessage, LLMError

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        if not api_key:
            raise LLMError("Anthropic provider requires an API key.")
        self.api_key = api_key
        self.base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self.model_name = model

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _split_system(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
        system = None
        turns = []
        for m in messages:
            if m.role == "system":
                system = (system + "\n\n" if system else "") + m.content
            else:
                turns.append({"role": m.role, "content": m.content})
        return system, turns

    def generate(self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2) -> str:
        system, turns = self._split_system(messages)
        payload = {"model": self.model_name, "max_tokens": max_tokens, "temperature": temperature, "messages": turns}
        if system:
            payload["system"] = system

        try:
            resp = requests.post(f"{self.base_url}/v1/messages", headers=self._headers(), json=payload, timeout=90)
        except requests.RequestException as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc

        if not resp.ok:
            raise LLMError(f"Anthropic returned {resp.status_code}: {resp.text[:400]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMError(f"Anthropic returned a 200 response that wasn't valid JSON: {resp.text[:400]}") from exc

        usage = data.get("usage")
        if usage:
            self.last_usage = {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
            }

        try:
            return "".join(block["text"] for block in data["content"] if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise LLMError(f"Unexpected Anthropic response shape: {data}") from exc

    def generate_stream(
        self, messages: list[ChatMessage], max_tokens: int = 1000, temperature: float = 0.2
    ) -> Iterator[str]:
        system, turns = self._split_system(messages)
        payload = {
            "model": self.model_name, "max_tokens": max_tokens, "temperature": temperature,
            "messages": turns, "stream": True,
        }
        if system:
            payload["system"] = system

        try:
            resp = requests.post(
                f"{self.base_url}/v1/messages", headers=self._headers(), json=payload, timeout=90, stream=True
            )
        except requests.RequestException as exc:
            raise LLMError(f"Anthropic streaming request failed: {exc}") from exc

        if not resp.ok:
            raise LLMError(f"Anthropic returned {resp.status_code}: {resp.text[:400]}")

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[len("data:"):].strip())
            except json.JSONDecodeError:
                continue
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                text = delta.get("text")
                if text:
                    yield text
