"""
Integration test: switching the default LLM provider takes effect on the
very next request — this is the concrete proof behind the "free vs
premium provider, switching is a database flag not a redeploy" claim made
during this project's development.

Port note: uses dedicated ports 8891/8892, not the shared fixture's 8890
or the e2e test's port — three test files originally all hardcoded 8877,
which caused a real, intermittent cross-file failure (see
integration/conftest.py's comment) only visible when the full suite ran
together, not file-by-file. Every test file that spins up its own mock
server subprocess now owns a distinct port.
"""
import os
import subprocess

from tests.helpers.wait_for_port import wait_for_port

_HELPERS_DIR = os.path.join(os.path.dirname(__file__), "..", "helpers")
_PORT_A = 8891
_PORT_B = 8892


def test_switching_default_provider_changes_which_backend_answers(client, admin_headers, app):
    from app.extensions import db
    from app.providers.models import ProviderConfig

    mock_a = subprocess.Popen(
        ["python3", os.path.join(_HELPERS_DIR, "mock_llm_server.py"), str(_PORT_A)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    mock_b = subprocess.Popen(
        ["python3", os.path.join(_HELPERS_DIR, "mock_llm_server_b.py"), str(_PORT_B)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    wait_for_port("127.0.0.1", _PORT_A)
    wait_for_port("127.0.0.1", _PORT_B)

    try:
        with app.app_context():
            provider_a = ProviderConfig(
                display_name="Provider A", provider_type="groq", base_url=f"http://127.0.0.1:{_PORT_A}/v1",
                extra_config={"model": "mock-model"}, capability="llm", is_active=True, is_default=True,
            )
            provider_b = ProviderConfig(
                display_name="Provider B", provider_type="openai", base_url=f"http://127.0.0.1:{_PORT_B}/v1",
                extra_config={"model": "mock-model"}, capability="llm", is_active=True, is_default=False,
            )
            db.session.add_all([provider_a, provider_b])
            db.session.commit()
            provider_b_id = provider_b.id

        session_id = client.post("/api/v1/chat/sessions", headers=admin_headers, json={}).get_json()["data"]["id"]
        r1 = client.post(f"/api/v1/chat/sessions/{session_id}/messages", headers=admin_headers, json={"message": "q1"})
        assert r1.get_json()["data"]["provider_used"] == "groq"

        switch = client.post(f"/api/v1/providers/{provider_b_id}/activate", headers=admin_headers)
        assert switch.status_code == 200

        session_id_2 = client.post("/api/v1/chat/sessions", headers=admin_headers, json={}).get_json()["data"]["id"]
        r2 = client.post(f"/api/v1/chat/sessions/{session_id_2}/messages", headers=admin_headers, json={"message": "q2"})
        assert r2.get_json()["data"]["provider_used"] == "openai"
    finally:
        mock_a.terminate()
        mock_b.terminate()
        mock_a.wait(timeout=5)
        mock_b.wait(timeout=5)
