import io


def _create_message(client, admin_headers, app, default_provider):
    session_id = client.post("/api/v1/chat/sessions", headers=admin_headers, json={}).get_json()["data"]["id"]
    client.post(f"/api/v1/chat/sessions/{session_id}/messages", headers=admin_headers, json={"message": "feedback test"})
    r = client.get(f"/api/v1/chat/sessions/{session_id}", headers=admin_headers)
    return [m["id"] for m in r.get_json()["data"]["messages"] if m["role"] == "assistant"][0]


def test_submit_and_update_feedback(client, admin_headers, app, default_provider):
    message_id = _create_message(client, admin_headers, app, default_provider)

    r1 = client.post(f"/api/v1/chat/messages/{message_id}/feedback", headers=admin_headers, json={"rating": "helpful"})
    assert r1.get_json()["data"]["rating"] == "helpful"

    r2 = client.post(f"/api/v1/chat/messages/{message_id}/feedback", headers=admin_headers, json={"rating": "not_helpful"})
    assert r2.get_json()["data"]["rating"] == "not_helpful"

    from app.chat.models import Feedback
    assert Feedback.query.count() == 1  # updated in place, not duplicated


def test_invalid_rating_rejected(client, admin_headers, app, default_provider):
    message_id = _create_message(client, admin_headers, app, default_provider)
    r = client.post(f"/api/v1/chat/messages/{message_id}/feedback", headers=admin_headers, json={"rating": "meh"})
    assert r.status_code == 422


def test_audit_export_csv_returns_valid_csv(client, admin_headers):
    client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "TestPass123!"})
    r = client.get("/api/v1/audit/export?format=csv", headers=admin_headers)
    assert r.status_code == 200
    assert r.content_type.startswith("text/csv")
    assert b"action" in r.data  # header row present


def test_analytics_export_pdf_returns_valid_pdf(client, admin_headers):
    r = client.get("/api/v1/analytics/export/overview?format=pdf", headers=admin_headers)
    assert r.status_code == 200
    assert r.data[:4] == b"%PDF"


def test_analytics_export_excel_returns_valid_xlsx(client, admin_headers):
    r = client.get("/api/v1/analytics/export/overview?format=excel", headers=admin_headers)
    assert r.status_code == 200
    assert r.data[:2] == b"PK"  # xlsx is a zip archive
