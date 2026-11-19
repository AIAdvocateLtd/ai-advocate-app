"""Two-step sign-in (email code or authenticator app), session revocation and admin MFA rules."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

_db = None
CODE_TTL = timedelta(minutes=5)
CODE_MAX_ATTEMPTS = 5
RESEND_GAP = timedelta(seconds=30)
SENDS_PER_HOUR = 5
ACCOUNT_GUESSES = 10
GUESS_WINDOW = timedelta(minutes=15)


def init(db):
    global _db
    _db = db


def _now():
    return datetime.now(timezone.utc)


def _fernet() -> Fernet:
    key = os.environ.get("TOTP_ENC_KEY")
    if not key:
        raise HTTPException(503, "Two-step sign-in is not configured on this server.")
    return Fernet(key.encode())


def enc_secret(secret: str) -> str:
    return "enc:" + _fernet().encrypt(secret.encode()).decode()


def dec_secret(stored: str) -> str:
    """Encrypted secrets carry an 'enc:' prefix; older plaintext secrets still work until re-enrolled."""
    if not stored or not stored.startswith("enc:"):
        return stored or ""
    try:
        return _fernet().decrypt(stored[4:].encode()).decode()
    except InvalidToken:
        raise HTTPException(500, "Two-step secret could not be read.")


def is_admin(user: dict) -> bool:
    admins = {e.strip().lower() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()}
    return (user.get("email") or "").lower() in admins or bool(user.get("is_owner"))


def mfa_method(user: dict) -> Optional[str]:
    """Authenticator always wins. Admins can never satisfy two-step with an email code."""
    if os.environ.get("MFA_BREAKGLASS_USER_ID") and os.environ.get("MFA_BREAKGLASS_USER_ID") == user.get("id"):
        return None
    if user.get("totp_enabled"):
        return "totp"
    if user.get("email_2fa_enabled") and not is_admin(user):
        return "email"
    return None


def mask_email(email: str) -> str:
    name, _, dom = (email or "").partition("@")
    return (name[:2] + "***@" + dom) if dom else "***"


def _code_hash(user_id: str, code: str) -> str:
    key = (os.environ.get("JWT_SECRET") or "").encode()
    return hmac.new(key, f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


async def issue_email_code(user: dict, purpose: str, send) -> dict:
    """Creates a fresh 6-digit code (replacing any earlier one) and emails it. Enforces resend limits."""
    now = _now()
    doc_id = f"{user['id']}:{purpose}"
    prev = await _db.auth_codes.find_one({"_id": doc_id}) or {}
    sends = [s if s.tzinfo else s.replace(tzinfo=timezone.utc) for s in prev.get("sends", [])]
    sends = [s for s in sends if s > now - timedelta(hours=1)]
    if sends and now - max(sends) < RESEND_GAP:
        raise HTTPException(429, "Please wait 30 seconds before asking for another code.")
    if len(sends) >= SENDS_PER_HOUR:
        raise HTTPException(429, "Too many codes requested. Please try again in an hour.")
    code = f"{secrets.randbelow(10**6):06d}"
    await _db.auth_codes.replace_one({"_id": doc_id}, {"_id": doc_id, "user_id": user["id"], "purpose": purpose,
                                                       "hash": _code_hash(user["id"], code), "expires_at": now + CODE_TTL,
                                                       "attempts": 0, "sends": sends + [now]}, upsert=True)
    await send(user["email"], code)
    return {"sent": True, "to": mask_email(user["email"]), "expires_in": int(CODE_TTL.total_seconds())}


async def check_email_code(user: dict, purpose: str, code: str) -> bool:
    """Single-use: deleted on success; 5 wrong tries or 5 minutes kills it."""
    doc_id = f"{user['id']}:{purpose}"
    doc = await _db.auth_codes.find_one({"_id": doc_id})
    if not doc or not doc.get("hash"):
        return False
    exp = doc["expires_at"].replace(tzinfo=timezone.utc) if doc["expires_at"].tzinfo is None else doc["expires_at"]
    if exp < _now() or doc.get("attempts", 0) >= CODE_MAX_ATTEMPTS:
        await _db.auth_codes.update_one({"_id": doc_id}, {"$unset": {"hash": ""}})
        return False
    if not hmac.compare_digest(doc["hash"], _code_hash(user["id"], (code or "").strip())):
        await _db.auth_codes.update_one({"_id": doc_id}, {"$inc": {"attempts": 1}})
        return False
    await _db.auth_codes.update_one({"_id": doc_id}, {"$unset": {"hash": ""}})
    return True


async def guard_guesses(user_id: str):
    """Account-wide cap on wrong second-step codes, independent of how many sign-ins are started."""
    since = _now() - GUESS_WINDOW
    n = await _db.login_attempts.count_documents({"scope": "mfa_acct", "key": user_id, "at": {"$gte": since}})
    if n >= ACCOUNT_GUESSES:
        raise HTTPException(429, "Too many incorrect codes. Please wait 15 minutes and sign in again.")


async def fail_guess(user_id: str):
    await _db.login_attempts.insert_one({"scope": "mfa_acct", "key": user_id, "at": _now()})


async def revoke_sessions(user_id: str, reason: str) -> int:
    """Bumps the session version so every previously issued sign-in token stops working."""
    doc = await _db.users.find_one_and_update({"id": user_id}, {"$inc": {"token_version": 1},
                                                               "$set": {"sessions_revoked_at": _now().isoformat()}},
                                              return_document=True, projection={"token_version": 1})
    await log(user_id, "sessions_revoked", {"reason": reason})
    return int((doc or {}).get("token_version") or 0)


def session_valid(payload: dict, user: dict) -> bool:
    if payload.get("stage") or payload.get("kind") not in (None, "user"):
        return False
    return int(payload.get("tv") or 0) == int(user.get("token_version") or 0)


async def log(user_id: str, kind: str, extra: Optional[dict] = None):
    """Informational security log (never contains codes, secrets, passwords or tokens)."""
    await _db.security_events.insert_one({"id": secrets.token_hex(16), "user_id": user_id, "kind": kind,
                                          "created_at": _now().isoformat(), "acknowledged": True, **(extra or {})})


async def admin_enforcement_on() -> bool:
    doc = await _db.app_settings.find_one({"_id": "security"}) or {}
    return bool(doc.get("admin_totp_required"))
