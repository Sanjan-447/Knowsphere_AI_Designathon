"""
Celery worker entrypoint.

Run the worker with:
    celery -A celery_worker.celery_app worker --loglevel=info

The Celery app object itself lives in app/celery_app.py (see that file's
docstring for why — breaking a circular import with routes.py). This file's
job is to attach Flask app-context wrapping so task code can freely use
`from app.extensions import db` etc. as if it were running inside a normal
Flask request.
"""
from app import create_app
from app.celery_app import celery_app

flask_app = create_app()


class _ContextTask(celery_app.Task):
    def __call__(self, *args, **kwargs):
        with flask_app.app_context():
            return self.run(*args, **kwargs)


celery_app.Task = _ContextTask

# Task modules must be imported AFTER celery_app.Task is set above, so tasks
# registered via @celery_app.task(...) inherit the Flask-context wrapping.
import app.documents.tasks  # noqa: E402, F401
