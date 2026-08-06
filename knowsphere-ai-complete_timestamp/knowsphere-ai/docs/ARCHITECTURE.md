# Architecture Documentation

For the full, most current diagram see the README's "Cross-Phase
Reference" section, updated through Phase 5 and referenced again in the
Phase 4/6 write-ups. This document explains the *reasoning* behind the
major structural decisions — the "why," not just the "what."

## Layered structure

```
Frontend (React/TS) → Flask API (blueprints) → LangGraph orchestration
                                              → Retrieval/RAG engine
                                              → PostgreSQL + pgvector
                                              → Redis (cache/broker)
                                              → Celery worker (async ingestion)
```

Each blueprint (`health`, `auth`, `providers`, `documents`, `chat`,
`audit`, `observability`, `analytics`, `notifications`) is a self-contained
vertical slice — its own `models.py`, `service.py`, `routes.py` — rather
than horizontal layers (all models together, all routes together). A new
engineer working on notifications never needs to open `chat/`.

## Why PostgreSQL + pgvector, not a separate vector database

The spec at project start called for ChromaDB. Changed to pgvector after
explicit discussion (see conversation history / README) for one load-bearing
reason: RBAC. This system's permission model depends on filtering happening
**inside the retrieval query itself** — `vector_store.py`'s
`_role_visibility_clause()` is a SQL join against `document_acl`, executed
as part of the same query that does the cosine-similarity search. If
vectors lived in a separate system (Chroma) while permissions lived in
Postgres, every retrieval would need two round-trips reconciled in
application code — and if those two systems ever drifted out of sync, the
failure mode is a **permission leak**, not a crash. That's the worst
possible failure mode for an enterprise knowledge tool. One database, one
source of truth, makes that class of bug structurally impossible rather
than just tested-against.

## Why LangGraph orchestrates but doesn't replace business logic

Phase 4's entire design constraint: every node in `app/agents/nodes/*` is
a thin wrapper around a function that already existed in Phase 3 —
`check_for_injection()`, `build_context()`, `build_prompt()`,
`extract_citations()`, the LLM adapters. Zero business logic moved. The
graph in `app/agents/graph.py` contains only wiring (`add_node`,
`add_edge`, `add_conditional_edges`) — no logic of its own. This means the
retrieval/prompting/citation code is testable and reasoned-about
independent of whether it's invoked via the graph or (as the streaming
chat path does) via direct function calls in sequence.

## Why streaming bypasses the compiled graph

LangGraph's node model is "return a value once." Token-by-token SSE
streaming needs to yield incrementally while the LLM is still generating.
Rather than take on real added complexity (LangGraph's async/custom
stream-writer machinery) for something the spec never asked to be
graph-orchestrated, `RagService.answer_stream()` calls the exact same node
**functions** the graph uses, directly, in the same order, up through
prompt-building — zero duplicated logic, just a different invocation
mechanism. See `app/chat/rag_service.py`'s module docstring for the full
reasoning.

## Why the `capability` field exists on `ProviderConfig`

A real bug, caught by testing, not designed in from the start: a provider
`provider_type` like `openai_compatible` is ambiguous between "this is a
chat endpoint" and "this is an embedding endpoint." Early Phase 3 testing
had a chat-only mock provider mistakenly selected as the embedding
provider too. `capability` (`llm` | `embedding` | `both`) fixes this
structurally — enforced at the API validation layer for provider types
with no embedding adapter (Groq, OpenRouter, Anthropic, NVIDIA NIM, Ollama
are hard-locked to `capability='llm'`).

## Why `retrieval_metadata` carries the raw prompt, not a new table

The Retrieval Inspector (Phase 5) needs the actual prompt sent to the LLM
for debugging. Rather than a new `ChatMessage` column exposed by default,
it's stored inside the existing `retrieval_metadata` JSONB field — which
only the admin-only `GET /chat/admin/messages/{id}/inspect` endpoint ever
reads with `generated_prompt`/`final_context_render` included. The regular
session/message endpoints never pass that flag, so the raw prompt is
invisible to a normal user's chat UI by construction, not by a
field-level permission check that could be forgotten on some future
endpoint.

## Multi-tenancy

Not implemented. Every table assumes a single organization. Adding real
multi-tenancy would mean an `organizations` table and an `org_id` foreign
key threaded through `documents`, `users`, `provider_configs`, and a
middleware-enforced tenant filter on every query — a substantial, deliberate
addition, not a small patch, and out of scope for what's been built.
