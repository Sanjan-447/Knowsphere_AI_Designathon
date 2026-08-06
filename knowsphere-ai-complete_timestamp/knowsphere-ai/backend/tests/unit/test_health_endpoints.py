"""Unit tests for health/readiness/liveness endpoints."""


def test_liveness_always_succeeds_no_auth_needed(client):
    r = client.get("/api/v1/health/live")
    assert r.status_code == 200
    assert r.get_json()["data"]["status"] == "alive"


def test_readiness_checks_real_dependencies(client):
    r = client.get("/api/v1/health/ready")
    assert r.status_code == 200
    checks = r.get_json()["data"]["checks"]
    assert checks["database"] == "ok"
    assert checks["redis"] == "ok"


def test_legacy_health_endpoint_still_works(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.get_json()["data"]["status"] == "ok"
