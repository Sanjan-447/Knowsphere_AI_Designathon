"""
Standardized API response envelope.

Every endpoint in KnowSphere AI returns one of these two shapes so the
frontend can rely on a single parsing path regardless of which module
answered the request:

Success:
    { "success": true, "data": <any>, "message": "...", "request_id": "..." }

Error:
    { "success": false, "error": { "code": "...", "message": "..." },
      "request_id": "..." }
"""
from flask import jsonify, g


def _request_id() -> str | None:
    return getattr(g, "request_id", None)


def success_response(data=None, message: str = "OK", status_code: int = 200):
    payload = {
        "success": True,
        "data": data,
        "message": message,
        "request_id": _request_id(),
    }
    return jsonify(payload), status_code


def error_response(code: str, message: str, status_code: int = 400, details=None):
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "request_id": _request_id(),
    }
    return jsonify(payload), status_code
