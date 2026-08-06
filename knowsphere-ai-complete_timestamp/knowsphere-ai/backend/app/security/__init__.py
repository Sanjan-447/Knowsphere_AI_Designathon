"""
Security module.

Phase 1 implements: encryption.py (Fernet-based encryption for provider API
keys at rest).

Reserved for later phases: pii_redaction.py, prompt_injection_guard.py, and
a real Vault/KMS-backed secrets_manager.py to replace the local
ENCRYPTION_KEY approach, per the architecture blueprint's security section.
"""
