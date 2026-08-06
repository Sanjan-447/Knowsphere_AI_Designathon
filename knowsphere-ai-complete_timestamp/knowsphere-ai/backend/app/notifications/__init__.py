"""
Notifications module (Phase 5): an in-app notification center for
administrators, covering the failure types the spec lists — failed
uploads, failed embeddings, failed retrievals, provider failures,
background job failures, system errors, and expired documents.

Not an external delivery mechanism (no email/SMS/push) — see models.py's
docstring for the full scoping notes, including why "expired documents"
is admin-triggered rather than automatically scheduled (no Celery Beat
is configured in this project).
"""
