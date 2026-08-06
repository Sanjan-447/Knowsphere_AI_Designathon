"""
Shared pytest fixtures.

Uses a real, separate Postgres database (knowsphere_test) with pgvector
enabled — not SQLite, not mocks. This project's Phase 2+ features
genuinely require pgvector; testing against SQLite would validate a code
path (the fallback) that Phase 2 onward doesn't actually run on, which
would make the tests reassuring but wrong. Migrations are applied once
per test session; each test cleans up its own rows via the autouse
clean_db fixture rather than relying on transaction rollback, which is
simpler to reason about correctly against a real Celery/Redis-adjacent
stack where some operations (like task .delay()) don't participate in
the same DB transaction anyway.
"""
import os

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-1234567890-not-for-real-use")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-1234567890-not-for-real-use")
os.environ.setdefault("DATABASE_URL", "postgresql://knowsphere:knowsphere@localhost:5432/knowsphere_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/2")  # separate Redis DB index, isolated from dev data
os.environ.setdefault("UPLOAD_DIR", "/tmp/knowsphere_test_uploads")

import pytest
from cryptography.fernet import Fernet

os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session", autouse=True)
def clean_redis_at_session_start():
    """The response cache (Redis DB index 2, isolated from dev/prod data)
    persists across separate pytest invocations, unlike Postgres, which
    tests/conftest.py's fresh test database setup implicitly resets. A
    stale cache entry from a previous run leaking into a supposedly-fresh
    run caused a real, confusing failure: a cache test's very first
    request came back `from_cache: true` because a prior run had already
    cached an answer under the same key (same question text + role).
    Flushing once at session start is enough — within a session,
    different tests use different question text, so cache keys don't
    collide with each other."""
    import redis
    client = redis.from_url(os.getenv("REDIS_URL"))
    client.flushdb()


@pytest.fixture(scope="session")
def app():
    flask_app = create_app("testing")
    with flask_app.app_context():
        _db.create_all()  # tests run against the current model state directly, not through migrations
        yield flask_app
        # Deliberately NOT calling _db.drop_all() here — it was observed to
        # hang intermittently, most likely blocked waiting for a table lock
        # held by a connection left open by one of the many manually-entered
        # `with app.app_context():` blocks scattered across the integration
        # tests (Flask only auto-closes the scoped session at the end of a
        # real request; a manually-pushed context doesn't get that same
        # signal). Rather than chase down that specific connection-pool
        # interaction, the pragmatic fix: the test database is disposable
        # and expected to be recreated fresh before every run anyway (see
        # the Testing Guide), so nothing depends on drop_all() actually
        # running here.


@pytest.fixture(autouse=True)
def clean_db(app):
    """Runs after every test — deletes all rows in FK-safe order so tests
    never see leftover state from a previous test, without the overhead of
    dropping/recreating the whole schema each time."""
    yield
    with app.app_context():
        from app.chat.models import Feedback, Citation, ChatMessage, ChatSession
        from app.documents.models import (
            DocumentACL, DocumentMetadata, DocumentProcessingEvent, UploadLog, DocumentChunk, Document,
        )
        from app.audit.models import AuditLog
        from app.notifications.models import Notification
        from app.providers.models import ProviderConfig
        from app.observability.models import ObservabilityConfig
        from app.auth.models import RefreshSession, User
        from app.rbac.models import Role

        for model in [
            Feedback, Citation, ChatMessage, ChatSession, DocumentACL, DocumentMetadata,
            DocumentProcessingEvent, UploadLog, DocumentChunk, Document, AuditLog,
            Notification, ProviderConfig, ObservabilityConfig, RefreshSession, User, Role,
        ]:
            model.query.delete()
        _db.session.commit()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(app):
    from app.rbac.models import ensure_default_roles, Role, ROLE_ADMIN
    from app.auth.models import User

    with app.app_context():
        ensure_default_roles()
        role = Role.query.filter_by(name=ROLE_ADMIN).first()
        user = User(email="admin@test.local", display_name="Test Admin", role_id=role.id)
        user.set_password("TestPass123!")
        _db.session.add(user)
        _db.session.commit()
        return user.id


@pytest.fixture
def employee_user(app):
    from app.rbac.models import ensure_default_roles, Role, ROLE_EMPLOYEE
    from app.auth.models import User

    with app.app_context():
        ensure_default_roles()
        role = Role.query.filter_by(name=ROLE_EMPLOYEE).first()
        user = User(email="employee@test.local", display_name="Test Employee", role_id=role.id)
        user.set_password("TestPass123!")
        _db.session.add(user)
        _db.session.commit()
        return user.id


@pytest.fixture
def admin_headers(client, admin_user):
    r = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "TestPass123!"})
    token = r.get_json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def employee_headers(client, employee_user):
    r = client.post("/api/v1/auth/login", json={"email": "employee@test.local", "password": "TestPass123!"})
    token = r.get_json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
