"""
WSGI entrypoint. Used by gunicorn in production:
    gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app

For local development, use `flask run` instead (see README).
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
