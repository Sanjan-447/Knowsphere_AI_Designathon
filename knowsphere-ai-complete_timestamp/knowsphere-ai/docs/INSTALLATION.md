# Installation Guide

This covers getting KnowSphere AI running on your machine. For day-to-day
development workflow once it's running, see [LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md).

## Prerequisites

| Requirement | Why |
|---|---|
| Docker + Docker Compose | Easiest path — runs Postgres, Redis, backend, worker, frontend together |
| **OR**, for a non-Docker setup: | |
| Python 3.12 | Backend |
| Node.js 20+ | Frontend |
| PostgreSQL 16 with the **pgvector** extension | Required from Phase 2 onward — see the note below, this is not optional |
| Redis | Celery broker + response cache + rate limiting |

**Why pgvector is non-negotiable**: Phase 1's SQLite fallback only covers
`users`/`roles`/`provider_configs`. Every document/chunk/embedding table
added from Phase 2 onward uses a `vector` column type SQLite cannot
represent at all. If you're not using Docker, you need real Postgres with
`CREATE EXTENSION vector;` run once, or nothing past Phase 1 will work.

## Option A — Docker (recommended)

```bash
git clone <your-repo-url> knowsphere-ai
cd knowsphere-ai
cp .env.example .env
```

Generate a real encryption key and paste it into `.env` as `ENCRYPTION_KEY`:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Start everything:
```bash
docker compose up --build
```

This starts, in order: Postgres (with pgvector), Redis, the backend
(auto-runs migrations on boot in the **dev** compose file — see the
Docker Guide for why production doesn't do this), the Celery worker, and
the frontend dev server.

Seed roles and your first admin account:
```bash
docker compose exec backend flask seed-roles
docker compose exec backend flask seed-admin
# follow the prompts for email / display name / password
```

Visit:
- Frontend: http://localhost:5173
- Backend API: http://localhost:5000/api/v1
- Health check: http://localhost:5000/api/v1/health

## Option B — Without Docker

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
# for running tests too: pip install -r requirements-dev.txt

cp ../.env.example .env
# Edit .env: set ENCRYPTION_KEY (see command above), SECRET_KEY, JWT_SECRET_KEY,
# and DATABASE_URL pointing at your real Postgres+pgvector instance.

export FLASK_APP=wsgi.py
flask db upgrade
flask seed-roles
flask seed-admin

flask run --port 5000
```

In a second terminal, start the Celery worker (uploads will sit at
`status: uploaded` forever without this running):
```bash
cd backend
source venv/bin/activate
export FLASK_APP=wsgi.py  # plus the same env vars as above
celery -A celery_worker.celery_app worker --loglevel=info
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

## Verifying the install worked

```bash
curl http://localhost:5000/api/v1/health/ready
```
Should return `{"success": true, "data": {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}}`.

Then log into the frontend with the admin account you seeded, upload one
of the files in `sample-documents/`, and ask a question about it in
**Ask Knowsphere**. If you get a cited answer, everything is wired up
correctly end to end.

## What's next

- To actually get semantically meaningful answers (not just the plumbing
  working), configure a real embedding provider — see
  [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md) and the
  README's Provider Configuration Guide.
- For running the test suite, see [../backend/tests](../backend/tests) and
  the Testing Report in the main README.
- If something doesn't work, check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) first.
