"""
Response cache.

Caches the full RAG answer (response text + citations + retrieval metadata)
for a short TTL, keyed by a hash of the question + role + filters +
top_k + which provider would answer it. Only applied to the non-streaming
path — streaming responses are inherently a poor fit for whole-response
caching (the point of streaming is to start showing text before the full
answer exists), and it's noted as such in the RAG service.

Deliberately NOT caching across different roles or different sets of
authorized documents under the same key — the cache key includes the
role precisely so a cached answer for one role's permitted documents can
never be served to a different role.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os

import redis

logger = logging.getLogger("knowsphere.cache")

_redis_client: redis.Redis | None = None
_redis_unavailable = False

DEFAULT_TTL_SECONDS = 600  # 10 minutes — short enough that a newly-uploaded
# or re-indexed document doesn't stay invisible for long, long enough to
# absorb repeated identical questions (e.g. an FAQ-style question asked by
# several employees in the same day).


def _get_client() -> redis.Redis | None:
    global _redis_client, _redis_unavailable
    if _redis_client is not None or _redis_unavailable:
        return _redis_client
    try:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()
        _redis_client = client
    except Exception as exc:
        logger.warning("Response cache disabled — could not connect to Redis: %s", exc)
        _redis_unavailable = True
    return _redis_client


def make_cache_key(*, question: str, role: str, top_k: int, filters_repr: str, provider_id: int | None) -> str:
    raw = f"{question.strip().lower()}|{role}|{top_k}|{filters_repr}|{provider_id}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"knowsphere:rag_answer:{digest}"


def get_cached(key: str) -> dict | None:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Cache read failed: %s", exc)
        return None


def set_cached(key: str, value: dict, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.setex(key, ttl_seconds, json.dumps(value))
    except Exception as exc:
        logger.warning("Cache write failed: %s", exc)
