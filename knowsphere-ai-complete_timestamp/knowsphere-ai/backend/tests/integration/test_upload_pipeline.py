"""
Integration test: upload -> parse -> chunk -> embed -> ready, exercising
the real pipeline end to end. The Celery task is called directly as a
plain function (bypassing .delay() and the broker) — this is the standard
way to test a Celery task's actual logic synchronously without needing a
running worker process in the test suite; the task body itself is
identical code to what a real worker executes.
"""
import io


def test_txt_upload_processes_to_ready(client, admin_headers, app):
    from app.documents.tasks import process_document
    from app.documents.models import Document

    data = {
        "files": [(io.BytesIO(b"Section one.\n\nThis is a test document about vacation policy."), "test.txt")],
    }
    r = client.post("/api/v1/documents", headers=admin_headers, data=data, content_type="multipart/form-data")
    assert r.status_code == 202
    result = r.get_json()["data"]["results"][0]
    assert result["status"] == "accepted"
    document_id = result["document_id"]

    with app.app_context():
        process_document(document_id)  # synchronous call — see module docstring
        doc = Document.query.get(document_id)
        assert doc.status == "ready"
        assert len(doc.chunks) > 0
        assert doc.chunks[0].embedding is not None


def test_duplicate_upload_is_rejected(client, admin_headers):
    content = b"Identical content for duplicate detection test."
    data1 = {"files": [(io.BytesIO(content), "first.txt")]}
    r1 = client.post("/api/v1/documents", headers=admin_headers, data=data1, content_type="multipart/form-data")
    assert r1.get_json()["data"]["results"][0]["status"] == "accepted"

    data2 = {"files": [(io.BytesIO(content), "second.txt")]}
    r2 = client.post("/api/v1/documents", headers=admin_headers, data=data2, content_type="multipart/form-data")
    assert r2.get_json()["data"]["results"][0]["status"] == "duplicate"


def test_unsupported_file_type_rejected(client, admin_headers):
    data = {"files": [(io.BytesIO(b"binary junk"), "malware.exe")]}
    r = client.post("/api/v1/documents", headers=admin_headers, data=data, content_type="multipart/form-data")
    assert r.get_json()["data"]["results"][0]["status"] == "rejected"


def test_disguised_file_content_rejected(client, admin_headers):
    """Real file, wrong content — a .pdf that's actually plain text should
    be caught by the magic-byte signature check (Phase 6 security hardening)."""
    data = {"files": [(io.BytesIO(b"this is plain text, not a real PDF"), "disguised.pdf")]}
    r = client.post("/api/v1/documents", headers=admin_headers, data=data, content_type="multipart/form-data")
    result = r.get_json()["data"]["results"][0]
    assert result["status"] == "rejected"
    assert "disguised" in result["message"].lower() or "content" in result["message"].lower()


def test_employee_cannot_delete_document(client, admin_headers, employee_headers, app):
    data = {"files": [(io.BytesIO(b"content for delete permission test"), "delete_test.txt")]}
    r = client.post("/api/v1/documents", headers=admin_headers, data=data, content_type="multipart/form-data")
    document_id = r.get_json()["data"]["results"][0]["document_id"]

    r2 = client.delete(f"/api/v1/documents/{document_id}", headers=employee_headers)
    assert r2.status_code == 403
