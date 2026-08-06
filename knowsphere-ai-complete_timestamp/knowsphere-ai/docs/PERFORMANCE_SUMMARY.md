# Performance Optimization Summary

## What's actually optimized, and verified

| Area | What was done | Verified how |
|---|---|---|
| pgvector similarity search | HNSW index on `document_chunks.embedding`, declared on the model (not just raw SQL) so it survives future migrations correctly | Confirmed via `flask db migrate` reporting no schema drift; confirmed the index is actually used via a direct SQL similarity query |
| Response caching | Redis-backed, 10-minute TTL, keyed by question+role+top_k+filters (role included as a *security* property, not just a cache-hit optimization) | Live-tested: identical question twice, second call `from_cache: true` at near-zero latency |
| Database indexing | Indexes on `audit_logs.action`/`created_at`, `chat_messages` foreign keys, `documents.content_hash` (duplicate detection) | Present in migrations, exercised by every query that filters on them |
| Frontend bundle size / lazy loading | Every Phase 5 dashboard page is `React.lazy()`-loaded, not bundled into the initial page load | **Proven, not just claimed**: the production build output shows `recharts` (383KB, the largest single dependency) isolated into its own chunk, only fetched when a chart page is actually visited |
| Celery concurrency | `--concurrency=2` in docker-compose (dev), configurable | Not load-tested against real throughput |
| Prompt/token optimization | Context Builder respects a token budget (default 3000) and dedupes chunks before they ever reach the prompt; conversation history is windowed (`MAX_HISTORY_MESSAGES=12`), not unbounded | Verified via unit tests confirming windowing actually truncates |

## What's explicitly NOT done, and why

- **Pagination/virtualized tables**: Audit Log page has real prev/next
  pagination. The **Documents page does not** — it loads up to 100
  documents flat. Analytics/Knowledge Intelligence tables are naturally
  small (top-N lists), so pagination there wouldn't add value. **This is
  the one Phase 6 performance item left genuinely incomplete** — worth
  fixing before a deployment with a large document library.
- **Image optimization**: no user-uploaded images exist in this system's
  data model (documents are parsed to text; there's no image-heavy
  content type), so this item doesn't apply to what's actually built.
- **Load/stress testing**: nothing in this project simulates concurrent
  users or measures actual throughput under load. The "<2 second average
  response time" target from the Phase 6 spec was never measured against
  real traffic — response time in this project's testing has only ever
  been measured against a local mock LLM server with near-zero network
  latency, which tells you the *pipeline's own overhead* (typically tens
  of milliseconds for retrieval + reranking) but nothing about real-world
  latency once an actual LLM provider's response time (frequently 1-5+
  seconds for a real generation call) dominates the total.
- **HNSW index tuning** (`m`/`ef_construction` parameters): left at
  pgvector's defaults. Fine at the current scale (a handful of test
  documents); worth revisiting past a few hundred thousand chunks.

## Honest bottom line on the "<2 second average response time" target

This project cannot claim to have met or measured this target under real
conditions. What's true: the RAG pipeline's own processing (embedding via
the dev-local provider, vector search, reranking, context building,
prompt building) consistently completes in tens of milliseconds in every
test run. The dominant cost in a real deployment will be the LLM
generation call itself, which depends entirely on which provider you
configure — Groq, for instance, is specifically fast for this reason,
while some other providers/models are not. Meeting a 2-second target is
realistic with a fast provider and small `top_k`, but this hasn't been
empirically measured against a live provider from this environment.
