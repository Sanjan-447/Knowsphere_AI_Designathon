def test_create_and_list_sessions(client, admin_headers):
    r = client.post("/api/v1/chat/sessions", headers=admin_headers, json={})
    assert r.status_code == 201
    session_id = r.get_json()["data"]["id"]

    r2 = client.get("/api/v1/chat/sessions", headers=admin_headers)
    assert any(s["id"] == session_id for s in r2.get_json()["data"])


def test_rename_session(client, admin_headers):
    session_id = client.post("/api/v1/chat/sessions", headers=admin_headers, json={}).get_json()["data"]["id"]
    r = client.patch(f"/api/v1/chat/sessions/{session_id}", headers=admin_headers, json={"title": "Renamed"})
    assert r.get_json()["data"]["title"] == "Renamed"


def test_delete_session(client, admin_headers):
    session_id = client.post("/api/v1/chat/sessions", headers=admin_headers, json={}).get_json()["data"]["id"]
    r = client.delete(f"/api/v1/chat/sessions/{session_id}", headers=admin_headers)
    assert r.status_code == 200
    r2 = client.get(f"/api/v1/chat/sessions/{session_id}", headers=admin_headers)
    assert r2.status_code == 404


def test_user_cannot_access_another_users_session(client, admin_headers, employee_headers):
    session_id = client.post("/api/v1/chat/sessions", headers=admin_headers, json={}).get_json()["data"]["id"]
    r = client.get(f"/api/v1/chat/sessions/{session_id}", headers=employee_headers)
    assert r.status_code == 404  # not 403 — existence isn't confirmed to a non-owner either
