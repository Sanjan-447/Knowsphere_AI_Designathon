"""
The Celery app instance lives here — deliberately with NO dependency on
`create_app()` — so that app/documents/routes.py (which needs `.delay()` to
enqueue tasks) and celery_worker.py (the actual worker entrypoint, which
wraps task execution in a Flask app context) can both import it without a
circular import.

celery_worker.py is where the Flask-context wrapping actually gets attached
(see that file) — this module only defines the Celery app and its broker
config, read directly from the environment rather than from Flask's config
object, since Flask isn't initialized yet when this module is first
imported via the routes -> tasks import chain.
"""
import os

from celery import Celery

_broker = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
_backend = os.getenv("CELERY_RESULT_BACKEND", os.getenv("REDIS_URL", "redis://localhost:6379/0"))

celery_app = Celery("knowsphere", broker=_broker, backend=_backend)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
