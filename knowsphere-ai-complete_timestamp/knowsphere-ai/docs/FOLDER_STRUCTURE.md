# Folder Structure Documentation

Generated directly from the actual project tree (not hand-typed from
memory) as of the end of Phase 6's documentation pass.

## Backend (`backend/app/`)

Vertical-slice organization — each module owns its full stack (models,
service logic, routes), not horizontal layers.

```
app/
├── __init__.py                # Flask app factory — every blueprint registered here
├── config.py                  # Environment-driven config classes (Base/Development/Testing/Production)
├── extensions.py              # db, migrate, jwt, cors instances
├── celery_app.py              # Celery app instance (kept separate from celery_worker.py — see its docstring on why)
├── cli.py                     # flask seed-roles / flask seed-admin
│
├── auth/                      # Phase 1: login, JWT, refresh rotation, admin user management
├── rbac/                      # Phase 1: Role model, default role seeding
├── providers/                 # Phase 1/3: LLM+embedding provider config, capability field
│   └── llm/                   # Phase 3: chat-completion adapters (OpenAI-style, Anthropic, Gemini, Ollama)
├── documents/                 # Phase 2: ingestion pipeline
│   ├── parsers/                #   PDF/DOCX/TXT/MD/CSV/XLSX/JSON/EML/MSG, one class per format
│   └── connectors/             #   share-link downloader (real connector interface for future ones)
├── retrieval/                  # Phase 2/3: embeddings, vector search, reranking, context building, response cache
├── agents/                     # Phase 4: LangGraph state, nodes (one file per pipeline stage), graph wiring
├── chat/                       # Phase 3/4/5: sessions/messages/citations/feedback models, prompt builder,
│                                #   citation engine, the RAG orchestrator, chat + retrieval-inspector routes
├── audit/                      # Phase 5: immutable audit log (write-and-read-only, no update/delete route)
├── observability/              # Phase 5: LangSmith config + tracing, system/provider monitoring
├── analytics/                  # Phase 5: usage analytics, knowledge intelligence, CSV/Excel/PDF export
├── notifications/              # Phase 5: in-app notification center
├── security/                   # Phase 1/6: encryption, prompt injection guard, rate limiting, secure headers,
│                                #   env validation, file signature validation
├── common/                     # Standardized response envelope, error handling, logging config
└── health/                     # Phase 1/6: health, readiness, liveness endpoints
```

## Backend tests (`backend/tests/`)

```
tests/
├── conftest.py           # Shared fixtures — real Postgres test DB, admin/employee user fixtures
├── unit/                 # 38 tests — pure logic, no external services (prompt builder, citation
│                          #   engine, reranker, RBAC, provider registry, analytics math, notifications)
├── integration/           # 19 tests — real DB + real (mock) LLM subprocess servers (upload pipeline,
│                          #   full RAG pipeline, chat API, provider switching, feedback/reporting)
├── e2e/                   # 1 test — full API-surface user journey: login → upload → chat → citation
│                          #   → feedback → dashboard → export
└── helpers/               # In-repo mock LLM server scripts + a real TCP-readiness poller
    #   (NOT scratch files outside the repo — these are part of what you clone/ship)
```

## Frontend (`frontend/src/`)

```
src/
├── App.tsx                 # Routing — every dashboard page is React.lazy()-loaded, not bundled upfront
├── main.tsx
├── context/AuthContext.tsx  # Session state, automatic access-token refresh on expiry
├── routes/ProtectedRoute.tsx # Auth + role-gating wrapper
│
├── api/                     # One file per backend resource group, mirroring app/*/routes.py 1:1:
│   auth.ts, providers.ts, documents.ts, chat.ts, analytics.ts, monitoring.ts,
│   notifications.ts, audit.ts, client.ts (axios instance + auto-refresh interceptor)
│
├── components/
│   ├── layout/              # Sidebar (grouped nav + notification badge), DashboardLayout
│   ├── chat/                # ChatSidebar, CitationCard, SourcePanel
│   ├── documents/           # DocumentDrawer (metadata/processing-timeline/preview)
│   └── dashboard/           # KpiCard, HealthBadge — shared across every Phase 5 dashboard
│
├── pages/                   # One file per route — LoginPage, DashboardHomePage, ChatPage,
│                             # DocumentsPage, AnalyticsPage, KnowledgeIntelligencePage,
│                             # SystemMonitoringPage, AuditLogPage, NotificationsPage,
│                             # AdminUsersPage, ProviderManagementPage, LangSmithSettingsPage,
│                             # SettingsPage, RetrievalDashboardPage
│
└── types/index.ts           # Shared TS types, mirroring every backend JSON response shape
```

## Project root

```
knowsphere-ai/
├── backend/                  # Flask API + Celery worker
├── frontend/                 # React + TS + Tailwind SPA
├── docs/                     # This documentation set
│   └── api/openapi.yaml       # Validated OpenAPI 3.0 spec
├── sample-documents/          # Real files (PDF/DOCX/EML/XLSX/TXT/MD/CSV/JSON) for testing ingestion
├── docker-compose.yml          # Dev profile — bind-mounted source, Vite dev server
├── docker-compose.prod.yml     # Production profile — multi-stage images, no bind mounts, nginx frontend
├── .env.example
├── .gitignore
└── README.md                  # Build history, cross-phase reference, all 6 phases' detailed write-ups
```
