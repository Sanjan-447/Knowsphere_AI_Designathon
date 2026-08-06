"""
Fixtures specific to integration tests: a real subprocess running a mock
OpenAI-compatible server, so tests exercise the actual HTTP request/response
code path in the LLM adapters rather than mocking that layer away.
"""
import os
import subprocess
import time

import pytest

from tests.helpers.wait_for_port import wait_for_port

_HELPERS_DIR = os.path.join(os.path.dirname(__file__), "..", "helpers")
_MOCK_SERVER_SCRIPT = os.path.join(_HELPERS_DIR, "mock_llm_server.py")
_MOCK_SERVER_PORT = 8890  # dedicated port for this shared fixture — see
# the module docstring in test_provider_switching.py for why every test
# file using a mock server needs its own port: three files hardcoding the
# same port 8877 caused an intermittent, hard-to-reproduce cross-file
# failure (passed in isolation, failed when the full suite ran together)
# from subprocess teardown/setup races on the same socket. Found by
# actually running the full suite, not by inspection.


@pytest.fixture(scope="module")
def mock_llm_server():
    proc = subprocess.Popen(
        ["python3", _MOCK_SERVER_SCRIPT, str(_MOCK_SERVER_PORT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    wait_for_port("127.0.0.1", _MOCK_SERVER_PORT)
    yield f"http://127.0.0.1:{_MOCK_SERVER_PORT}"
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def default_provider(app, mock_llm_server):
    from app.extensions import db
    from app.providers.models import ProviderConfig

    with app.app_context():
        provider = ProviderConfig(
            display_name="Test Mock Provider", provider_type="openai_compatible",
            base_url=mock_llm_server, extra_config={"model": "mock-model"},
            capability="llm", is_active=True, is_default=True,
        )
        db.session.add(provider)
        db.session.commit()
        return provider.id
