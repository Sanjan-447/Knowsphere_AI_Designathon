# Environment Configuration Guide

Full reference for every environment variable, beyond what's in
`.env.example`'s inline comments.

## Required (app refuses to start in production without these)

| Variable | Purpose | Notes |
|---|---|---|
| `SECRET_KEY` | Flask session/signing secret | Must not be the default `change-me-in-production` value in production — enforced by `app/security/env_validation.py`, verified to actually refuse startup |
| `JWT_SECRET_KEY` | JWT signing secret | Same enforcement as above |
| `ENCRYPTION_KEY` | Fernet key encrypting provider API keys + LangSmith key at rest | Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `DATABASE_URL` | Postgres connection string | Must be `postgresql://...` in production (SQLite fallback only covers Phase 1 tables) |

## Database & cache

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | SQLite fallback (dev only) | See above |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker, response cache, rate limiter storage — all share one Redis instance |

## Auth

| Variable | Default | Notes |
|---|---|---|
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | 30 | Session timeout for access tokens |
| `JWT_REFRESH_TOKEN_EXPIRES_DAYS` | 30 | Refresh tokens rotate on every use (see `auth/routes.py`'s `refresh()`) — a stolen refresh token can be used exactly once before rotation invalidates it |

## File uploads

| Variable | Default | Notes |
|---|---|---|
| `UPLOAD_DIR` | `./uploads` | Where ingested files are stored |
| `MAX_UPLOAD_SIZE_MB` | 50 | Hard limit; also caps `MAX_CONTENT_LENGTH` globally |

## Security (Phase 6)

| Variable | Default | Notes |
|---|---|---|
| `CLAMD_HOST` / `CLAMD_PORT` | unset / 3310 | Optional real malware scanning. Unset means uploads skip scanning and the system honestly reports `not_configured` rather than faking a "clean" result — see `app/security/file_validation.py` |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed frontend origins |

## Logging (Phase 6)

| Variable | Default | Notes |
|---|---|---|
| `LOG_LEVEL` | INFO | Standard Python logging levels |
| `LOG_FORMAT` | text | `text` (human-readable) or `json` (structured, one object per line — use in production with a log aggregator) |

## Observability

LangSmith is **not** configured via environment variables — it's an
admin-managed, database-stored, runtime-toggleable setting (`PATCH
/api/v1/observability/langsmith`), specifically so a key can be added or
rotated without a redeploy. See the README's "LangSmith Observability"
section for the full provisioning flow.

## Frontend

| Variable | Default | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:5000/api/v1` | **Baked in at build time**, not read at runtime — Vite inlines `import.meta.env.VITE_*` into the compiled JS bundle. Changing this after building requires a rebuild, not just a container restart. For Docker production builds, pass it as a build arg (see `frontend/Dockerfile.prod`) |

## Provider keys (LLM/embedding)

Also **not** environment variables — every LLM/embedding provider (OpenAI,
Anthropic, Gemini, Groq, OpenRouter, NVIDIA NIM, Ollama, or a generic
OpenAI-compatible endpoint) is configured via the admin UI
(`Settings → Provider settings` → `POST /api/v1/providers`), encrypted at
rest with `ENCRYPTION_KEY`, and switchable at runtime with zero redeploy —
this was verified live during Phase 3 development (a session answered
from one provider, then, after one API call to `/activate`, the very next
session's answer came from a different provider).

## Testing-specific variables

`backend/tests/conftest.py` sets these automatically via
`os.environ.setdefault(...)` — you don't need to set them yourself, but
they're worth knowing about if a test behaves unexpectedly:

- `DATABASE_URL` → `knowsphere_test` (a separate database from dev)
- `REDIS_URL` → `redis://localhost:6379/2` (a separate Redis DB index from dev)
- Rate limiting is disabled (`RATELIMIT_ENABLED = False` in `TestingConfig`)
  — otherwise many tests logging in different users in quick succession
  would trip the brute-force protection meant for a single real client.
