# Production Readiness Checklist

## Application & data layer

- [x] Security hardening (see [SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md))
- [x] Real test suite with a documented pass history (see [TESTING_REPORT.md](./TESTING_REPORT.md))
- [x] Structured logging option (`LOG_FORMAT=json`) for log aggregators
- [x] Health/readiness/liveness endpoints, distinct for their actual
      orchestrator purposes (`/health/live` never checks dependencies,
      `/health/ready` does)
- [x] Environment validation refuses to boot in production with
      insecure/missing secrets — verified, not just written
- [x] Database migrations are real, tested, and the recurring HNSW
      false-positive is fixed at the source
- [x] Multi-stage Docker images for backend and frontend (smaller,
      no build tools in the runtime image, non-root user)
- [ ] **Not tuned for scale**: HNSW index parameters, Celery concurrency,
      and rate-limit thresholds are all reasonable defaults, not
      empirically tuned against real production traffic
- [ ] **No multi-tenancy** — single organization only

## Observability

- [x] LangSmith integration (real SDK, admin-provisioned key, verified
      live connectivity test attempt)
- [x] System/provider monitoring dashboards backed by real health checks
      and real aggregated usage data
- [x] Audit logging, immutable by construction (no edit/delete route)
- [ ] **No live-traffic alerting** — notifications exist for individual
      failure events, but there's no threshold-based alerting (e.g. "error
      rate > 5% for 10 minutes") wired to an on-call system

## Deployment & CI/CD

**Deliberately deferred at the user's request** — the priority right now
is validating the application runs correctly in a local environment
before any deployment work begins. Not implemented as part of this pass:

- [ ] GitHub Actions CI/CD workflows
- [ ] Vercel/Render/Railway/Azure/AWS deployment configuration
- [ ] Deployment Guide

These remain real Phase 6 spec items; they're simply sequenced after
local validation rather than before it, per explicit instruction.

## Before you actually deploy anywhere

When you do get to deployment, at minimum:
1. Set `APP_ENV=production` and confirm the app refuses to boot with any
   default secret (this is enforced — test it deliberately once).
2. Configure a real embedding provider — the local dev-only fallback is
   explicitly not semantically meaningful.
3. Wire up a real ClamAV instance if malware scanning matters for your
   threat model — right now it's an honest stub, not a real scanner.
4. Load-test with your actual expected traffic before trusting the
   default rate limits, Celery concurrency, or HNSW index parameters.
5. Decide on your actual LLM provider(s) and verify their live API
   behavior yourself — every adapter here was tested against local mock
   servers reproducing the documented contract, not the live vendor APIs.
