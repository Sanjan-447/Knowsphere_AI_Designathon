"""Unit tests for RBAC — require_role decorator behavior against real routes."""


def test_admin_only_endpoint_rejects_employee(client, employee_headers):
    r = client.get("/api/v1/providers", headers=employee_headers)
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "FORBIDDEN"


def test_admin_only_endpoint_allows_admin(client, admin_headers):
    r = client.get("/api/v1/providers", headers=admin_headers)
    assert r.status_code == 200


def test_unauthenticated_request_rejected(client):
    r = client.get("/api/v1/providers")
    assert r.status_code == 401


def test_employee_can_access_own_chat_sessions(client, employee_headers):
    """Employees are explicitly allowed to use chat — RBAC restricts admin
    surfaces, not the core product experience."""
    r = client.post("/api/v1/chat/sessions", headers=employee_headers, json={})
    assert r.status_code == 201


def test_employee_cannot_upload_documents(client, employee_headers):
    r = client.post("/api/v1/documents", headers=employee_headers, data={})
    # Blocked by RBAC (403) before even reaching the "no files" validation.
    assert r.status_code == 403


def test_disabled_user_cannot_login(client, app):
    from app.extensions import db
    from app.rbac.models import ensure_default_roles, Role, ROLE_EMPLOYEE
    from app.auth.models import User

    with app.app_context():
        ensure_default_roles()
        role = Role.query.filter_by(name=ROLE_EMPLOYEE).first()
        user = User(email="disabled@test.local", display_name="Disabled", role_id=role.id, is_active=False)
        user.set_password("TestPass123!")
        db.session.add(user)
        db.session.commit()

    r = client.post("/api/v1/auth/login", json={"email": "disabled@test.local", "password": "TestPass123!"})
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "ACCOUNT_DISABLED"
