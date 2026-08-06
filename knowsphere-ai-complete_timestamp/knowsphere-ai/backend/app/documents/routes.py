"""
Document management endpoints.

Upload/delete/reprocess are Admin+Manager actions (content management);
viewing (list/preview/status) is open to any authenticated role, filtered
by document_acl for non-managers — the same "route decorator + data-layer
filter" two-layer RBAC pattern as Phase 1's provider routes, now applied to
documents.
"""
import os

from flask import Blueprint, request, current_app
from flask_jwt_extended import get_jwt_identity, get_jwt

from app.extensions import db
from app.common.responses import success_response
from app.common.errors import AppError
from app.auth.decorators import require_role, require_auth
from app.rbac.models import Role, ROLE_ADMIN, ROLE_MANAGER
from app.documents.models import (
    Document, DocumentChunk, DocumentACL, DocumentMetadata,
    SOURCE_UPLOAD, SOURCE_EMAIL, SOURCE_CHAT_EXPORT, SOURCE_SHARE_LINK,
    STATUS_UPLOADED,
)
from app.documents.service import (
    is_allowed_extension, get_extension, save_uploaded_file,
    log_upload_action, record_event,
)
from app.documents.connectors.share_link_downloader import ShareLinkDownloader
from app.documents.connectors.base import ConnectorError
from app.documents.tasks import process_document
from app.audit.service import log_action
from app.audit.models import ACTION_UPLOAD, ACTION_DELETE, ACTION_REPROCESS, ACTION_SEARCH
from app.security.file_validation import validate_file_signature, scan_for_malware

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")

MANAGER_ROLES = (ROLE_ADMIN, ROLE_MANAGER)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _current_role() -> str:
    return get_jwt().get("role")


def _visible_to_current_user(document: Document) -> bool:
    if _current_role() in MANAGER_ROLES:
        return True
    if not document.acl_entries:
        return True  # no ACL configured = visible to all roles
    return _current_role() in document.visible_role_names()


def _apply_acl(document: Document, role_names: list[str] | None):
    if not role_names:
        return
    for name in role_names:
        role = Role.query.filter_by(name=name).first()
        if role:
            db.session.add(DocumentACL(document_id=document.id, role_id=role.id))
    db.session.commit()


def _create_document_record(*, title, original_filename, file_type, source_type,
                             storage_path, content_hash, file_size_bytes,
                             department, tags, visible_to_roles, user_id):
    document = Document(
        title=title,
        original_filename=original_filename,
        file_type=file_type,
        source_type=source_type,
        storage_path=storage_path,
        content_hash=content_hash,
        file_size_bytes=file_size_bytes,
        department=department,
        tags=tags or [],
        status=STATUS_UPLOADED,
        uploaded_by_user_id=user_id,
    )
    db.session.add(document)
    db.session.commit()
    _apply_acl(document, visible_to_roles)
    record_event(document, STATUS_UPLOADED, "File received.")
    return document


def _check_duplicate(content_hash: str) -> Document | None:
    return Document.query.filter_by(content_hash=content_hash).first()


# ------------------------------------------------------------------
# Upload endpoints
# ------------------------------------------------------------------
@documents_bp.post("")
@require_role(*MANAGER_ROLES)
def upload_documents():
    """Multi-file upload. Accepts multipart/form-data with one or more
    'files' entries, plus optional department/tags/visible_to_roles fields
    (tags and visible_to_roles as JSON-encoded arrays, or repeated form fields)."""
    files = request.files.getlist("files")
    if not files:
        raise AppError("VALIDATION_ERROR", "At least one file is required (field name: 'files').", 422)

    department = request.form.get("department") or None
    tags = request.form.getlist("tags") or None
    visible_to_roles = request.form.getlist("visible_to_roles") or None
    force_reupload = request.form.get("overwrite_duplicates", "false").lower() == "true"

    user_id = int(get_jwt_identity())
    upload_dir = current_app.config["UPLOAD_DIR"]
    results = []

    for file_storage in files:
        filename = file_storage.filename
        if not filename:
            continue

        if not is_allowed_extension(filename):
            log_upload_action(None, filename, None, "upload", "rejected", "Unsupported file type.", user_id)
            results.append({"filename": filename, "status": "rejected", "message": "Unsupported file type."})
            continue

        # Save first (need the hash), then decide whether it's a duplicate.
        dest_path, size_bytes, content_hash = save_uploaded_file(file_storage, upload_dir)

        max_bytes = current_app.config["MAX_UPLOAD_SIZE_MB"] * 1024 * 1024
        if size_bytes > max_bytes:
            os.remove(dest_path)
            log_upload_action(None, filename, content_hash, "upload", "rejected",
                               f"Exceeds {current_app.config['MAX_UPLOAD_SIZE_MB']}MB limit.", user_id)
            results.append({"filename": filename, "status": "rejected", "message": "File too large."})
            continue

        existing = _check_duplicate(content_hash)
        if existing and not force_reupload:
            os.remove(dest_path)
            log_upload_action(existing.id, filename, content_hash, "upload", "rejected",
                               "Duplicate content already exists.", user_id)
            results.append({
                "filename": filename, "status": "duplicate",
                "message": "This exact file already exists.",
                "existing_document_id": existing.id,
            })
            continue

        ext = get_extension(filename)

        # Security hardening (Phase 6): verify the file's actual content
        # matches what its extension claims — a disguised file (e.g. an
        # executable renamed to .pdf) gets rejected here, before it's ever
        # handed to a parser.
        sig_valid, sig_message = validate_file_signature(dest_path, ext)
        if not sig_valid:
            os.remove(dest_path)
            log_upload_action(None, filename, content_hash, "upload", "rejected", sig_message, user_id)
            results.append({"filename": filename, "status": "rejected", "message": sig_message})
            continue

        malware_status, malware_message = scan_for_malware(dest_path)
        if malware_status == "infected":
            os.remove(dest_path)
            log_upload_action(None, filename, content_hash, "upload", "rejected",
                               f"Malware scan flagged this file: {malware_message}", user_id)
            results.append({"filename": filename, "status": "rejected", "message": "Malware detected in file."})
            continue

        source_type = SOURCE_EMAIL if ext in ("eml", "msg") else SOURCE_UPLOAD

        document = _create_document_record(
            title=filename, original_filename=filename, file_type=ext, source_type=source_type,
            storage_path=dest_path, content_hash=content_hash, file_size_bytes=size_bytes,
            department=department, tags=tags, visible_to_roles=visible_to_roles, user_id=user_id,
        )
        log_upload_action(document.id, filename, content_hash, "upload", "success", None, user_id)
        log_action(ACTION_UPLOAD, actor_user_id=user_id, resource_type="document", resource_id=document.id,
                   details={"filename": filename, "file_type": ext, "source_type": source_type})
        process_document.delay(document.id)
        results.append({"filename": filename, "status": "accepted", "document_id": document.id})

    return success_response(data={"results": results}, message="Upload processed.", status_code=202)


@documents_bp.post("/share-link")
@require_role(*MANAGER_ROLES)
def upload_via_share_link():
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip()
    if not url:
        raise AppError("VALIDATION_ERROR", "url is required.", 422)

    bearer_token = payload.get("bearer_token")
    department = payload.get("department")
    tags = payload.get("tags")
    visible_to_roles = payload.get("visible_to_roles")
    user_id = int(get_jwt_identity())

    upload_dir = current_app.config["UPLOAD_DIR"]
    downloader = ShareLinkDownloader(bearer_token=bearer_token)

    try:
        dest_path = downloader.fetch(url, upload_dir)
    except ConnectorError as exc:
        log_upload_action(None, url, None, "upload", "rejected", str(exc), user_id)
        raise AppError("SHARE_LINK_FAILED", str(exc), 422)

    filename = os.path.basename(dest_path).split("_", 1)[-1]
    ext = get_extension(filename)
    if not is_allowed_extension(filename):
        os.remove(dest_path)
        raise AppError("UNSUPPORTED_FILE_TYPE", f"Downloaded file '{filename}' is not a supported type.", 422)

    size_bytes = os.path.getsize(dest_path)
    from app.documents.service import compute_file_hash
    content_hash = compute_file_hash(dest_path)

    existing = _check_duplicate(content_hash)
    if existing:
        os.remove(dest_path)
        return success_response(
            data={"status": "duplicate", "existing_document_id": existing.id},
            message="This exact file already exists.",
        )

    document = _create_document_record(
        title=filename, original_filename=filename, file_type=ext, source_type=SOURCE_SHARE_LINK,
        storage_path=dest_path, content_hash=content_hash, file_size_bytes=size_bytes,
        department=department, tags=tags, visible_to_roles=visible_to_roles, user_id=user_id,
    )
    db.session.add(DocumentMetadata(document_id=document.id, key="source_url", value=url))
    db.session.commit()

    log_upload_action(document.id, filename, content_hash, "upload", "success", f"via share link {url}", user_id)
    process_document.delay(document.id)

    return success_response(data={"document_id": document.id, "status": "accepted"}, status_code=202)


@documents_bp.post("/chat-export")
@require_role(*MANAGER_ROLES)
def upload_chat_export():
    file_storage = request.files.get("file")
    if not file_storage or not file_storage.filename:
        raise AppError("VALIDATION_ERROR", "A file is required (field name: 'file').", 422)

    if not is_allowed_extension(file_storage.filename, for_chat_export=True):
        raise AppError("UNSUPPORTED_FILE_TYPE", "Chat exports must be .json or .txt.", 422)

    department = request.form.get("department") or None
    tags = request.form.getlist("tags") or None
    visible_to_roles = request.form.getlist("visible_to_roles") or None
    user_id = int(get_jwt_identity())
    upload_dir = current_app.config["UPLOAD_DIR"]

    dest_path, size_bytes, content_hash = save_uploaded_file(file_storage, upload_dir)

    existing = _check_duplicate(content_hash)
    if existing:
        os.remove(dest_path)
        return success_response(
            data={"status": "duplicate", "existing_document_id": existing.id},
            message="This exact file already exists.",
        )

    ext = get_extension(file_storage.filename)
    document = _create_document_record(
        title=file_storage.filename, original_filename=file_storage.filename, file_type=ext,
        source_type=SOURCE_CHAT_EXPORT, storage_path=dest_path, content_hash=content_hash,
        file_size_bytes=size_bytes, department=department, tags=tags,
        visible_to_roles=visible_to_roles, user_id=user_id,
    )
    log_upload_action(document.id, file_storage.filename, content_hash, "upload", "success", None, user_id)
    process_document.delay(document.id)

    return success_response(data={"document_id": document.id, "status": "accepted"}, status_code=202)


# ------------------------------------------------------------------
# Read endpoints
# ------------------------------------------------------------------
@documents_bp.get("")
@require_auth
def list_documents():
    query = Document.query

    search = request.args.get("search")
    if search:
        query = query.filter(Document.title.ilike(f"%{search}%"))
        log_action(ACTION_SEARCH, actor_user_id=int(get_jwt_identity()), resource_type="document",
                   details={"query": search})

    file_type = request.args.get("file_type")
    if file_type:
        query = query.filter(Document.file_type == file_type)

    source_type = request.args.get("source_type")
    if source_type:
        query = query.filter(Document.source_type == source_type)

    status = request.args.get("status")
    if status:
        query = query.filter(Document.status == status)

    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 25)), 100)

    all_docs = query.order_by(Document.created_at.desc()).all()
    visible_docs = [d for d in all_docs if _visible_to_current_user(d)]

    start = (page - 1) * page_size
    paged = visible_docs[start:start + page_size]

    return success_response(data={
        "documents": [d.to_dict() for d in paged],
        "total": len(visible_docs),
        "page": page,
        "page_size": page_size,
    })


@documents_bp.get("/<int:document_id>")
@require_auth
def get_document(document_id: int):
    document = Document.query.get(document_id)
    if not document or not _visible_to_current_user(document):
        raise AppError("NOT_FOUND", "Document not found.", 404)

    data = document.to_dict()
    data["metadata"] = [m.to_dict() for m in document.extra_metadata]
    data["processing_events"] = [e.to_dict() for e in document.processing_events]
    return success_response(data=data)


@documents_bp.get("/<int:document_id>/preview")
@require_auth
def preview_document(document_id: int):
    document = Document.query.get(document_id)
    if not document or not _visible_to_current_user(document):
        raise AppError("NOT_FOUND", "Document not found.", 404)

    chunks = (
        DocumentChunk.query.filter_by(document_id=document.id)
        .order_by(DocumentChunk.chunk_index.asc())
        .limit(5)
        .all()
    )
    preview_text = "\n\n".join(c.content for c in chunks)[:3000]
    return success_response(data={
        "document_id": document.id,
        "title": document.title,
        "preview_text": preview_text,
        "truncated": len(preview_text) >= 3000,
    })


@documents_bp.get("/<int:document_id>/status")
@require_auth
def document_status(document_id: int):
    document = Document.query.get(document_id)
    if not document or not _visible_to_current_user(document):
        raise AppError("NOT_FOUND", "Document not found.", 404)

    return success_response(data={
        "document_id": document.id,
        "status": document.status,
        "error_message": document.error_message,
        "events": [e.to_dict() for e in document.processing_events],
    })


# ------------------------------------------------------------------
# Mutations
# ------------------------------------------------------------------
@documents_bp.delete("/<int:document_id>")
@require_role(*MANAGER_ROLES)
def delete_document(document_id: int):
    document = Document.query.get(document_id)
    if not document:
        raise AppError("NOT_FOUND", "Document not found.", 404)

    user_id = int(get_jwt_identity())
    storage_path = document.storage_path

    log_upload_action(document.id, document.title, document.content_hash, "delete", "success", None, user_id)
    log_action(ACTION_DELETE, actor_user_id=user_id, resource_type="document", resource_id=document.id,
               details={"title": document.title})
    db.session.delete(document)
    db.session.commit()

    if storage_path and os.path.exists(storage_path):
        try:
            os.remove(storage_path)
        except OSError:
            pass

    return success_response(message="Document deleted.")


@documents_bp.post("/<int:document_id>/reprocess")
@require_role(*MANAGER_ROLES)
def reprocess_document(document_id: int):
    document = Document.query.get(document_id)
    if not document:
        raise AppError("NOT_FOUND", "Document not found.", 404)

    user_id = int(get_jwt_identity())
    log_upload_action(document.id, document.title, document.content_hash, "reprocess", "success", None, user_id)
    log_action(ACTION_REPROCESS, actor_user_id=user_id, resource_type="document", resource_id=document.id,
               details={"title": document.title})
    process_document.delay(document.id)

    return success_response(message="Reprocessing started.", status_code=202)


@documents_bp.post("/<int:document_id>/reupload")
@require_role(*MANAGER_ROLES)
def reupload_document(document_id: int):
    document = Document.query.get(document_id)
    if not document:
        raise AppError("NOT_FOUND", "Document not found.", 404)

    file_storage = request.files.get("file")
    if not file_storage or not file_storage.filename:
        raise AppError("VALIDATION_ERROR", "A file is required (field name: 'file').", 422)

    if not is_allowed_extension(file_storage.filename):
        raise AppError("UNSUPPORTED_FILE_TYPE", "Unsupported file type.", 422)

    user_id = int(get_jwt_identity())
    upload_dir = current_app.config["UPLOAD_DIR"]

    old_path = document.storage_path
    dest_path, size_bytes, content_hash = save_uploaded_file(file_storage, upload_dir)

    document.storage_path = dest_path
    document.content_hash = content_hash
    document.file_size_bytes = size_bytes
    document.file_type = get_extension(file_storage.filename)
    document.original_filename = file_storage.filename
    document.version += 1
    document.error_message = None
    db.session.commit()

    if old_path and os.path.exists(old_path):
        try:
            os.remove(old_path)
        except OSError:
            pass

    log_upload_action(document.id, file_storage.filename, content_hash, "reupload", "success",
                       f"version {document.version}", user_id)
    process_document.delay(document.id)

    return success_response(data=document.to_dict(), message="Re-uploaded; reprocessing started.", status_code=202)
