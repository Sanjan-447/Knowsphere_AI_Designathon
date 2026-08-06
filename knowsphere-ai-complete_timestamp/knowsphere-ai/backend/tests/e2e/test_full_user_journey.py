"""
End-to-end test: login -> upload -> ingest -> chat -> citation -> feedback
-> dashboard -> report export, as one continuous flow through the real API.

Honest scoping note: this is API-level E2E, not browser-level. True
browser-based E2E (Playwright/Cypress driving the actual React UI) needs
browser automation tooling this environment doesn't have installed and
wasn't asked to set up as a new capability. This test exercises every
layer *except* the rendered UI itself — auth, RBAC, ingestion, the real
LangGraph pipeline, citations, feedback, analytics aggregation, and
report generation — which is the meaningful backend contract the UI
depends on being correct.
"""
import io
import subprocess
import os

from tests.helpers.wait_for_port import wait_for_port

_HELPERS_DIR = os.path.join(os.path.dirname(__file__), "..", "helpers")
_PORT = 8893  # dedicated — see integration/conftest.py's comment on why every
# test file spinning up a mock server needs a distinct port


def test_full_user_journey(client, app):
    from app.extensions import db
    from app.rbac.models import ensure_default_roles, Role, ROLE_ADMIN
    from app.auth.models import User
    from app.providers.models import ProviderConfig
    from app.documents.tasks import process_document

    mock = subprocess.Popen(
        ["python3", os.path.join(_HELPERS_DIR, "mock_llm_server.py"), str(_PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    wait_for_port("127.0.0.1", _PORT)

    try:
        # 1. Bootstrap an admin (equivalent to `flask seed-admin`)
        with app.app_context():
            ensure_default_roles()
            role = Role.query.filter_by(name=ROLE_ADMIN).first()
            user = User(email="journey@test.local", display_name="Journey Admin", role_id=role.id)
            user.set_password("JourneyPass123!")
            db.session.add(user)
            provider = ProviderConfig(
                display_name="Journey Provider", provider_type="openai_compatible",
                base_url=f"http://127.0.0.1:{_PORT}", extra_config={"model": "mock-model"},
                capability="llm", is_active=True, is_default=True,
            )
            db.session.add(provider)
            db.session.commit()

        # 2. Login
        r = client.post("/api/v1/auth/login", json={"email": "journey@test.local", "password": "JourneyPass123!"})
        assert r.status_code == 200
        headers = {"Authorization": f"Bearer {r.get_json()['data']['access_token']}"}

        # 3. Upload a document
        data = {"files": [(io.BytesIO(b"Remote Work Policy\n\nEmployees may work remotely with manager approval."), "policy.txt")]}
        r = client.post("/api/v1/documents", headers=headers, data=data, content_type="multipart/form-data")
        assert r.status_code == 202
        document_id = r.get_json()["data"]["results"][0]["document_id"]

        # 4. Ingest (synchronous task call, standing in for the Celery worker)
        with app.app_context():
            process_document(document_id)
            from app.documents.models import Document
            assert Document.query.get(document_id).status == "ready"

        # 5. Chat and get a cited answer
        session_id = client.post("/api/v1/chat/sessions", headers=headers, json={}).get_json()["data"]["id"]
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages", headers=headers,
            json={"message": "TRIGGER_CITE_ALL can I work remotely", "top_k": 3},
        )
        assert r.status_code == 200
        body = r.get_json()["data"]
        assert body["citations"], "expected the answer to cite the uploaded policy"

        # 6. Submit feedback on the answer
        msg_id = client.get(f"/api/v1/chat/sessions/{session_id}", headers=headers).get_json()["data"]["messages"][-1]["id"]
        r = client.post(f"/api/v1/chat/messages/{msg_id}/feedback", headers=headers, json={"rating": "helpful"})
        assert r.status_code == 200

        # 7. Dashboard reflects the activity
        r = client.get("/api/v1/analytics/overview", headers=headers)
        overview = r.get_json()["data"]
        assert overview["total_queries"] >= 1
        assert overview["uploaded_documents"] >= 1

        # 8. Export a report
        r = client.get("/api/v1/analytics/export/feedback?format=csv", headers=headers)
        assert r.status_code == 200
        assert r.content_type.startswith("text/csv")
    finally:
        mock.terminate()
        mock.wait(timeout=5)
