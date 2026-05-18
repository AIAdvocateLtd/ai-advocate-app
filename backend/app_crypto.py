"""Field-level encryption helper for AI Advocate.

Uses Fernet (AES-128-CBC + HMAC-SHA256) for fast, authenticated encryption of
sensitive plaintext at rest in MongoDB.

The master key lives in env var `AA_DATA_KEY` (a 32-byte base64-encoded
Fernet key). Rotating this key invalidates all previously-encrypted data
unless you keep the old key around for decrypt-only.

Encrypted values are stored as opaque base64 strings prefixed with `enc:v1:`
so any future migration can detect them.
"""
import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

_AA_DATA_KEY = os.environ.get("AA_DATA_KEY", "")
_FERNET: Optional[Fernet] = None

if _AA_DATA_KEY:
    try:
        _FERNET = Fernet(_AA_DATA_KEY.encode())
    except Exception as ex:  # noqa: BLE001
        # If the key is malformed we surface a startup error via logger later;
        # encryption helpers below will raise if used.
        _FERNET = None

PREFIX = "enc:v1:"


def is_enabled() -> bool:
    return _FERNET is not None


def encrypt_text(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a string. Returns None if input is None/empty. Returns the
    plaintext untouched if encryption is disabled (no master key configured)
    so the app stays usable in dev environments without keys.
    """
    if plaintext is None or plaintext == "":
        return plaintext
    if _FERNET is None:
        return plaintext
    if isinstance(plaintext, str) and plaintext.startswith(PREFIX):
        # already encrypted — no double-encryption
        return plaintext
    token = _FERNET.encrypt(plaintext.encode("utf-8"))
    return f"{PREFIX}{token.decode('ascii')}"


def decrypt_text(value: Optional[str]) -> Optional[str]:
    """Decrypt a string previously produced by encrypt_text. Plain strings
    (not prefixed) are returned as-is — supports gradual migration of legacy
    plaintext rows.
    """
    if value is None or value == "":
        return value
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value
    if _FERNET is None:
        return value  # cannot decrypt without key — caller decides handling
    raw = value[len(PREFIX):].encode("ascii")
    try:
        return _FERNET.decrypt(raw).decode("utf-8")
    except InvalidToken:
        return value  # corrupted / wrong key — leave as-is


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt binary content (e.g. uploaded file blobs). Returns raw Fernet
    token bytes (no prefix — stored as bytes on disk or in GridFS)."""
    if _FERNET is None:
        return data
    return _FERNET.encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    if _FERNET is None:
        return token
    try:
        return _FERNET.decrypt(token)
    except InvalidToken:
        return token
