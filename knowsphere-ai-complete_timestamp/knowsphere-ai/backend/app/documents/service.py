"""
Shared helpers used by both the upload routes and the Celery pipeline task —
kept here so routes.py stays focused on HTTP concerns and tasks.py stays
focused on pipeline orchestration.
"""
import hashlib
import os
import uuid

from werkzeug.utils import secure_filename

from app.extensions import db
from app.documents.models import UploadLog, DocumentProcessingEvent
from app.documents.parsers.registry import is_supported_extension

CHAT_EXPORT_EXTENSIONS = {"json", "txt"}  # explicit chat-export endpoint accepts these


def get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def is_allowed_extension(filename: str, for_chat_export: bool = False) -> bool:
    ext = get_extension(filename)
    if for_chat_export:
        return ext in CHAT_EXPORT_EXTENSIONS
    return is_supported_extension(ext)


def compute_file_hash(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def save_uploaded_file(file_storage, upload_dir: str) -> tuple[str, int, str]:
    """Save a werkzeug FileStorage to disk under a UUID-prefixed name
    (avoids collisions/path traversal from the original filename) and
    returns (absolute_path, size_bytes, content_hash)."""
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = secure_filename(file_storage.filename) or "upload"
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    dest_path = os.path.join(upload_dir, stored_name)

    file_storage.save(dest_path)
    size_bytes = os.path.getsize(dest_path)
    content_hash = compute_file_hash(dest_path)
    return dest_path, size_bytes, content_hash


def record_event(document, stage: str, message: str | None = None):
    event = DocumentProcessingEvent(document_id=document.id, stage=stage, message=message)
    db.session.add(event)
    document.status = stage
    if message and stage == "failed":
        document.error_message = message
    db.session.commit()


def log_upload_action(document_id, filename, content_hash, action, status, message, user_id):
    log = UploadLog(
        document_id=document_id, filename=filename, content_hash=content_hash,
        action=action, status=status, message=message, performed_by_user_id=user_id,
    )
    db.session.add(log)
    db.session.commit()
