"""
Symmetric encryption for sensitive fields at rest (currently: provider API keys).

Phase 1 uses a local Fernet key from the ENCRYPTION_KEY env var. This is
already isolated behind a small interface (encrypt/decrypt) so swapping the
backing mechanism for a real secrets manager (Vault, AWS KMS, Azure Key
Vault) in a later phase means changing this file only — nothing that calls
encrypt_value()/decrypt_value() needs to change.
"""
import os
from cryptography.fernet import Fernet, InvalidToken

_fernet_instance: Fernet | None = None


class EncryptionNotConfigured(Exception):
    pass


def _get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        key = os.getenv("ENCRYPTION_KEY", "")
        if not key:
            raise EncryptionNotConfigured(
                "ENCRYPTION_KEY is not set. Generate one with:\n"
                "  python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\"\n"
                "and set it in your .env file."
            )
        _fernet_instance = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet_instance


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext string, returning a base64 token safe to store in a text column."""
    if plaintext is None:
        return None
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(token: str) -> str:
    """Decrypt a token previously produced by encrypt_value(). Never log the result."""
    if token is None:
        return None
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt value — invalid token or wrong ENCRYPTION_KEY") from exc


def mask_value(plaintext: str, visible_chars: int = 4) -> str:
    """Return a display-safe masked version, e.g. 'sk-ant-...a1b2', for UI display only."""
    if not plaintext:
        return ""
    if len(plaintext) <= visible_chars:
        return "*" * len(plaintext)
    return f"{plaintext[:6]}...{plaintext[-visible_chars:]}"
