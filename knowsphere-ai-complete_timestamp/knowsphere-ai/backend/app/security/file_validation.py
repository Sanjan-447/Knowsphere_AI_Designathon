"""
File upload content validation (Phase 6 security hardening).

Extension-based validation (documents/service.py's is_allowed_extension())
only checks what the filename *claims* to be — a malicious actor can
rename a .exe to report.pdf trivially. This module checks what the file
*actually is*, via magic-byte/content sniffing (python-magic, backed by
libmagic — the same detection engine the `file` command uses), and
rejects a mismatch before the file ever reaches a parser.

Malware scanning honesty note: real virus/malware scanning needs a
running ClamAV daemon (clamd) — genuine infrastructure this project
doesn't provision (no clamd process, no virus definition database). 
scan_for_malware() below is written against the real clamd protocol
(via a TCP/socket connection, if configured) and returns a clear
"not configured" result rather than silently pretending to scan when
nothing is actually running. Wire up a real clamd instance (via
CLAMD_HOST/CLAMD_PORT) in a real deployment to make this functional
rather than advisory.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("knowsphere.security")

# Expected MIME type(s) per supported extension. Content sniffing can be
# imprecise for some office formats (docx/xlsx are technically zip
# archives), so a couple of extensions accept more than one detected type.
_EXPECTED_MIME_TYPES = {
    "pdf": {"application/pdf"},
    "docx": {"application/zip", "application/x-zip-compressed",
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xlsx": {"application/zip", "application/x-zip-compressed",
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "txt": {"text/plain"},
    "md": {"text/plain"},
    "csv": {"text/plain", "text/csv"},
    "json": {"text/plain", "application/json"},
    "eml": {"text/plain", "message/rfc822"},
    "msg": {"application/vnd.ms-outlook", "application/octet-stream", "application/CDFV2"},
}


def validate_file_signature(file_path: str, claimed_extension: str) -> tuple[bool, str]:
    """Returns (is_valid, message). is_valid=True if the file's actual
    content matches what its extension claims, or if the extension isn't
    one this check has an opinion about (fails open for anything not in
    _EXPECTED_MIME_TYPES, rather than blocking formats this check doesn't
    understand yet)."""
    expected = _EXPECTED_MIME_TYPES.get(claimed_extension.lower())
    if not expected:
        return True, "No content-signature check defined for this extension; skipped."

    try:
        import magic
        detected = magic.from_file(file_path, mime=True)
    except Exception as exc:  # noqa: BLE001 — a broken libmagic install shouldn't block all uploads
        logger.warning("File signature check unavailable (%s) — allowing upload through unchecked.", exc)
        return True, "Signature check unavailable; allowed through unchecked."

    if detected in expected:
        return True, f"Content matches claimed type ({detected})."

    return False, (
        f"File claims to be .{claimed_extension} but its actual content looks like '{detected}', "
        f"not one of {sorted(expected)}. This may be a disguised or corrupted file."
    )


def scan_for_malware(file_path: str) -> tuple[str, str]:
    """Returns (status, message) where status is 'clean' | 'infected' |
    'not_configured' | 'error'. See module docstring — this only actually
    scans if a real clamd instance is reachable via CLAMD_HOST/CLAMD_PORT;
    otherwise it honestly reports 'not_configured' rather than a fake
    'clean' result."""
    import os
    host = os.getenv("CLAMD_HOST")
    port = int(os.getenv("CLAMD_PORT", "3310"))

    if not host:
        return "not_configured", "No ClamAV daemon configured (set CLAMD_HOST/CLAMD_PORT to enable real scanning)."

    try:
        import socket
        with open(file_path, "rb") as f:
            data = f.read()

        sock = socket.create_connection((host, port), timeout=10)
        sock.sendall(b"zINSTREAM\0")
        # clamd INSTREAM protocol: 4-byte big-endian length prefix per chunk, zero-length chunk to end.
        chunk_size = 8192
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
        sock.sendall((0).to_bytes(4, "big"))

        response = sock.recv(4096).decode(errors="replace")
        sock.close()

        if "FOUND" in response:
            return "infected", response.strip()
        if "OK" in response:
            return "clean", response.strip()
        return "error", f"Unexpected clamd response: {response.strip()}"
    except Exception as exc:  # noqa: BLE001 — a scanning infrastructure failure shouldn't crash the upload endpoint
        logger.error("ClamAV scan failed: %s", exc)
        return "error", str(exc)
