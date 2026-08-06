# Local Development Guide

Assumes you've already completed [INSTALLATION.md](./INSTALLATION.md).

## Day-to-day commands

| Action | Command |
|---|---|
| Run backend dev server | `flask run --port 5000` (from `backend/`, venv active, env vars set) |
| Run Celery worker | `celery -A celery_worker.celery_app worker --loglevel=info` |
| Run frontend dev server | `npm run dev` (from `frontend/`) |
| Apply a new migration | `flask db upgrade` |
| Generate a migration after model changes | `flask db migrate -m "description"` — **see the HNSW note below before running this** |
| Create/reset the admin user | `flask seed-admin` |
| Type-check frontend | `npx tsc -b` |
| Build frontend for production | `npm run build` |
| Run the full test suite | `pytest` (from `backend/`, see below for DB setup) |
| Lint for unused imports | `flake8 --select=F401 app/` |

## The recurring Alembic/HNSW gotcha

If you add or modify a model and run `flask db migrate`, this project's
history (see the README's Migration History table) had a **fixed** issue
where autogenerate proposed dropping `ix_document_chunks_embedding_hnsw` —
now genuinely fixed at the source by declaring the index on the
`DocumentChunk` model itself (`app/documents/models.py`'s `__table_args__`).
Confirmed via `flask db migrate` reporting "No changes in schema detected"
for schema-only changes. If you ever see a `drop_index(...hnsw...)` line
in a newly generated migration again, something reintroduced the same
class of mismatch — check that the model's declarative index still
matches the real DB index before blindly running `db upgrade`.

## Running the test suite locally

Tests use a **separate, real Postgres database** with pgvector enabled —
not SQLite, not mocks (see `backend/tests/conftest.py`'s docstring for why).

```bash
# One-time setup:
sudo -u postgres psql -c "CREATE DATABASE knowsphere_test OWNER knowsphere;"
sudo -u postgres psql -d knowsphere_test -c "CREATE EXTENSION IF NOT EXISTS vector;"

cd backend
pip install -r requirements-dev.txt
pytest                              # everything
pytest tests/unit                   # just unit tests (fast, ~3s)
pytest tests/integration            # integration (spawns real mock LLM server subprocesses)
pytest tests/e2e                    # the full user-journey test
pytest --cov=app --cov-report=html  # coverage report → backend/htmlcov/index.html
```

**Recommendation, from direct experience building this suite**: run
`tests/unit`, `tests/integration`, and `tests/e2e` as **separate
invocations** (exactly what the commands above do), not one combined
`pytest tests/`. A combined run occasionally hit a subprocess-teardown
interaction that caused intermittent hangs — root-caused and mitigated
(see `tests/conftest.py`'s comments on why `drop_all()` isn't called at
teardown, and why the session-scoped Redis flush exists), but running
categories separately is both how CI should be structured anyway and the
most reliable way to run them locally.

## Editing the frontend design system

Colors, fonts, and spacing tokens live in `frontend/tailwind.config.js`
and are used consistently across every page — ink/paper/gold/teal, Lora
for display headings, Inter for body text, JetBrains Mono for
codes/citations. Match this rather than introducing new one-off colors
when adding a page.

## Adding a new backend module

Follow the existing pattern: `app/<module>/models.py`, `service.py`
(business logic), `routes.py` (thin HTTP layer calling into service.py),
registered in `app/__init__.py`'s `create_app()`. Look at `app/notifications/`
for the smallest complete example of this pattern.

## Adding a new frontend page

1. Create `frontend/src/pages/YourPage.tsx`.
2. Add a lazy import in `App.tsx` (see the existing pattern — every
   dashboard page is code-split, not bundled into the initial load).
3. Add a route under the appropriate `<ProtectedRoute allowedRoles={...}>`.
4. Add a nav entry in `components/layout/Sidebar.tsx`'s `WORKSPACE_ITEMS`
   or `ADMIN_ITEMS`.
