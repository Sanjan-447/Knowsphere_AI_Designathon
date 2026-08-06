# Testing Report

## Summary

| Metric | Result |
|---|---|
| Total tests | 58 (38 unit, 19 integration, 1 E2E) |
| Pass rate | 100% (58/58), confirmed stable across 3+ consecutive full runs |
| Code coverage | 58% overall (see breakdown below) |
| Real bugs found via testing | 11, across the whole project's development (not just this suite) |
| Test database | Real PostgreSQL + pgvector — not SQLite, not mocked |
| LLM dependency | Real mock HTTP servers reproducing the actual OpenAI-compatible/vendor-specific wire protocols — not a mocked Python function |

## What "unit," "integration," and "E2E" mean concretely here

- **Unit** (`tests/unit/`, 38 tests): pure logic — prompt construction,
  citation extraction/hallucination-rejection, the lexical reranker,
  provider registry validation, RBAC enforcement against real routes,
  analytics cost math, notification creation, health endpoints.
- **Integration** (`tests/integration/`, 19 tests): real Postgres + real
  Celery task execution (called synchronously, bypassing the broker — the
  standard way to test Celery task bodies) + real mock LLM server
  subprocesses. Covers the upload pipeline, the full RAG pipeline through
  the actual LangGraph, chat session management, provider switching, and
  feedback/export.
- **End-to-end** (`tests/e2e/`, 1 test): the complete user journey —
  login → upload → ingest → chat → citation → feedback → dashboard →
  export — through the real API surface. **Honest scoping note**: this is
  API-level E2E, not browser-level. True browser-automation E2E
  (Playwright/Cypress driving the actual rendered React UI) needs tooling
  this environment doesn't have installed, and wasn't asked to be newly
  provisioned. This test exercises every layer except the rendered UI
  itself.

## Coverage by area

Full breakdown available via `pytest --cov=app --cov-report=html`
(output: `backend/htmlcov/index.html`). Notable patterns:

- **Near-100% coverage**: `agents/graph.py`, `agents/state.py`,
  `providers/registry.py`, `security/prompt_injection_guard.py`,
  `retrieval/reranker.py` — the pure-logic modules unit tests target directly.
- **Lower coverage, expected**: individual LLM adapters (`providers/llm/
  anthropic_provider.py`, `gemini_provider.py`, `ollama_provider.py` —
  15-17% each) and document parsers not exercised by the specific sample
  files used in tests (`chat_export_parser.py` at 0%, since no test
  currently uploads a chat export). This reflects what the test suite
  actually exercises, not a coverage target dishonestly inflated by
  testing trivial code paths.
- **58% overall** is a reasonable baseline for a system this size, not a
  ceiling — the honest gaps above are the natural next tests to add.

## Real bugs found and fixed via testing (project-wide, chronological)

This is the concrete payoff of the testing discipline maintained
throughout this project, not just this final phase:

1. **Phase 3**: capability ambiguity — an LLM-only provider mistakenly
   selected for embedding generation.
2. **Phase 4**: `cache_write_node` ordering bug — `KeyError` on
   `retrieval_metadata` because it was built after the node that needed
   to read it.
3. **Phase 4**: retrieval/reranking timing regression — splitting one
   method into two lost the combined elapsed-time measurement the admin
   dashboard depends on.
4. **Post-Phase-4 real-file testing**: PDF/DOCX/EML/XLSX/share-link
   parsers had never been exercised with genuine files — found one real
   bug (email citation dates always `null`, wrong-table lookup).
5. **Phase 5**: token counts were columns that existed but were never
   populated by any code path.
6. **Phase 5**: the response cache could serve a stuck provider error for
   its full TTL — no `had_error` check gating what gets cached.
7. **Phase 5**: a genuine `str_replace` mistake of my own — accidentally
   deleted the `Citation` class declaration while inserting a new model;
   caught immediately by checking class declarations were still present.
8. **Phase 5**: `Feedback` had no cascade-delete relationship from
   `ChatMessage` — deleting a session with feedback attached crashed with
   a foreign-key violation.
9. **Phase 5**: a LangSmith `RunTree` field-name mismatch
   (`project_name`/`client` vs. the real `session_name`/`ls_client`) —
   caught by inspecting the installed SDK's actual schema instead of
   assuming API consistency.
10. **Phase 6**: `TestingConfig` hardcoded SQLite — a Phase 1 assumption
    invalidated by Phase 2's pgvector/JSONB columns, which would have
    broken every test touching those models.
11. **Phase 6**: the ingestion pipeline's embedding-provider resolver
    (`documents/tasks.py`) had never received the Phase 3/4 capability
    fix applied to the chat-side resolver — the exact same class of bug
    as #1, latent and unfixed until real-file upload testing surfaced it.

Plus test-infrastructure issues that were real and worth fixing even
though they weren't application bugs: the Phase 6 rate limiter blocking
the test suite itself, three test files colliding on the same hardcoded
mock-server port, a fixed `time.sleep(1)` that was measurably flaky under
load, a `drop_all()` teardown call that hung (removed rather than
root-caused further, since the test database is disposable anyway), and
stale Redis cache data leaking across separate pytest invocations.

## Running the suite

See [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md)'s testing section for
exact commands. Recommended: run `tests/unit`, `tests/integration`, and
`tests/e2e` as separate invocations, not one combined `pytest tests/` —
documented reasoning in that file and in `tests/conftest.py`'s comments.

## What isn't tested

- Live calls to Groq, OpenRouter, Anthropic, Gemini, or real LangSmith —
  this sandbox's network allowlist doesn't reach those hosts. Every
  adapter is implemented against each vendor's documented API shape and
  verified against local mock servers reproducing that exact contract,
  but final verification against the live services is on you, once real
  keys are configured.
- Browser-rendered frontend behavior (see the E2E scoping note above).
- `.msg` (Outlook binary email) parsing with a real file — no
  straightforward way to generate one synthetically; the parser is
  unit-testable but untested end-to-end with a genuine `.msg`.
- Load/stress testing at scale — nothing in this suite simulates
  concurrent users or large corpora; see the Performance Optimization
  Summary for what would need attention before that kind of validation.
