# Security Checklist

Status of every item the Phase 6 spec asked for. Marked honestly — ✅
done and verified, ⚠️ partial/conditional, ❌ not implemented — rather than
checking every box regardless of actual state.

| Item | Status | Notes |
|---|---|---|
| Secure HTTP headers | ✅ | CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy — `app/security/headers.py`, verified present on real responses |
| Content Security Policy | ✅ | `default-src 'none'` — correct for an API-only backend that serves no HTML of its own |
| CORS configuration | ✅ | Restricted to `CORS_ORIGINS` env var, not wildcard |
| CSRF protection | ⚠️ N/A by design | This is a stateless JWT Bearer-token API, never cookie-authenticated — CSRF specifically exploits automatic cookie-sending, which doesn't apply here. Documented explicitly in `headers.py` rather than silently omitted. **Revisit if cookie-based auth is ever introduced.** |
| Secure cookie configuration | ⚠️ N/A | No cookies are used for auth (see above) |
| Rate limiting | ✅ | Redis-backed, global default + strict brute-force limit on login (10/min), verified live (11th attempt correctly 429s) |
| Request size limits | ✅ | `MAX_CONTENT_LENGTH` / `MAX_UPLOAD_SIZE_MB` |
| API throttling | ✅ | Same mechanism as rate limiting above |
| Brute-force login protection | ✅ | Verified live |
| Session timeout | ✅ | 30-min access token expiry (configurable) |
| Refresh token rotation | ✅ | Since Phase 1 — every refresh revokes the used token and issues a new pair; verified a reused revoked token is correctly rejected |
| File upload validation | ✅ | Extension check (Phase 2) + real magic-byte content-signature verification (Phase 6) — verified rejects a genuinely disguised file |
| Malware-safe upload handling | ⚠️ Honest stub | Real clamd protocol implementation exists (`app/security/file_validation.py`), but no ClamAV daemon is provisioned in this environment. Reports `not_configured` truthfully rather than faking a "clean" result. **Wire up a real clamd instance before relying on this in production.** |
| Secret management improvements | ✅ | All provider API keys + LangSmith key encrypted at rest (Fernet); startup validation refuses insecure defaults in production |
| Environment variable validation | ✅ | `app/security/env_validation.py` — verified production mode genuinely refuses to boot with missing/default secrets |
| API key encryption | ✅ | Since Phase 1, extended to LangSmith key in Phase 5 |
| Security logging | ✅ | `knowsphere.security` logger category; login attempts, RBAC denials, and config problems all logged |
| Security middleware | ✅ | Consolidated in `app/security/` |
| RBAC consistently enforced | ✅ | Every admin-only endpoint verified via unit tests (`test_rbac.py`) rejecting non-admin roles with 403, not just relying on frontend hiding buttons |

## Known limitations, stated plainly

- **No multi-tenancy isolation** — this is a single-organization system.
- **ClamAV is not actually running anywhere** in this project's tested
  environment — the integration point is real, the scanning is not.
- **CSRF's "N/A" status depends on auth staying token-based.** If a
  future change introduces cookie-based sessions for any reason, this
  needs to be revisited, not assumed still safe.
- **Rate limits are starting-point defaults**, not tuned against real
  production traffic this project has never seen.
