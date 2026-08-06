"""
Secure HTTP headers.

Applied via after_request rather than a dependency like Flask-Talisman —
the header set this API actually needs is small and stable enough that
owning it directly is simpler than configuring a general-purpose
security-headers library, and it means every header's presence and value
is visible in one place, in this file, not spread across a config object.

CSRF note (read before wondering why there's no CSRF middleware here):
this API authenticates via a JWT Bearer token in the Authorization
header, never via cookies (see auth/routes.py — access and refresh
tokens are returned in the JSON body and stored client-side in memory/
localStorage, not as cookies). CSRF is fundamentally an attack that
piggybacks on a browser's automatic cookie-sending behavior; it doesn't
apply to a request scheme where the client must explicitly attach a
bearer token that a malicious third-party page has no way to read or
forge. Adding CSRF tokens here would protect against an attack vector
this API isn't exposed to, while adding real friction to every request.
If a future phase introduces cookie-based session auth, CSRF protection
would need to be added at that point — noted here so it isn't forgotten
if that assumption ever changes.
"""
from flask import Flask


def register_security_headers(app: Flask) -> None:
    @app.after_request
    def _set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # CSP is deliberately restrictive for an API-only backend (the
        # frontend is a separate origin/process) — it never serves HTML
        # pages of its own, so there's no legitimate script/style source
        # to allow beyond 'none'.
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        # HSTS only makes sense once you're actually terminating HTTPS —
        # in local/dev (Flask's built-in server, plain HTTP), sending this
        # header is at best a no-op and at worst confusing. Gate it on the
        # request actually being secure (a reverse proxy in production
        # should be setting X-Forwarded-Proto: https, which Flask surfaces
        # via request.is_secure when ProxyFix or equivalent is configured).
        from flask import request
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
