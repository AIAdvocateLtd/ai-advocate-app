"""Stage 3A: server-side login attempt limiting (Mongo-backed, works across restarts and servers)."""
import hashlib
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
import stage3

_db = None
WINDOW = timedelta(minutes=15)
PER_ACCOUNT_IP, PER_ACCOUNT_ANY_IP, PER_IP, PER_2FA, PER_RESET_IP = 5, 15, 20, 5, 10


def init(db):
    global _db
    _db = db


async def ensure_indexes():
    await _db.login_attempts.create_index("at", expireAfterSeconds=86400)
    await _db.login_attempts.create_index([("scope", 1), ("key", 1), ("at", -1)])


def _h(v: str) -> str:
    return hashlib.sha256((v or "").strip().lower().encode()).hexdigest()[:32]


async def _enabled() -> bool:
    return bool((await stage3.settings())["login_limits_enabled"])


async def _retry_minutes(scope: str, key: str, limit: int):
    since = datetime.now(timezone.utc) - WINDOW
    rows = await _db.login_attempts.find({"scope": scope, "key": key, "at": {"$gte": since}},
                                         {"_id": 0, "at": 1}).sort("at", -1).to_list(limit)
    if len(rows) < limit:
        return None
    oldest = rows[-1]["at"].replace(tzinfo=timezone.utc)
    return max(1, int(((oldest + WINDOW) - datetime.now(timezone.utc)).total_seconds() // 60) + 1)


def _locked(mins: int, msg: str = None):
    raise HTTPException(429, msg or f"Too many sign-in attempts. For your security, please try again in {mins} minute"
                                    f"{'s' if mins != 1 else ''}, or reset your password.")


async def check(kind: str, email: str, ip: str):
    if not await _enabled():
        return
    e = _h(f"{kind}:{email}")
    for scope, key, limit in (("acct_ip", f"{e}:{_h(ip)}", PER_ACCOUNT_IP), ("acct", e, PER_ACCOUNT_ANY_IP),
                              ("ip", _h(ip), PER_IP)):
        mins = await _retry_minutes(scope, key, limit)
        if mins:
            await _db.security_events.insert_one({"kind": "login_lockout", "scope": scope, "account_kind": kind,
                                                  "email_hash": e, "created_at": datetime.now(timezone.utc).isoformat(),
                                                  "acknowledged": False})
            _locked(mins)


async def fail(kind: str, email: str, ip: str):
    if not await _enabled():
        return
    now, e = datetime.now(timezone.utc), _h(f"{kind}:{email}")
    await _db.login_attempts.insert_many([{"scope": "acct_ip", "key": f"{e}:{_h(ip)}", "at": now},
                                          {"scope": "acct", "key": e, "at": now},
                                          {"scope": "ip", "key": _h(ip), "at": now}])


async def success(kind: str, email: str, ip: str):
    e = _h(f"{kind}:{email}")
    await _db.login_attempts.delete_many({"scope": {"$in": ["acct_ip", "acct"]}, "key": {"$in": [e, f"{e}:{_h(ip)}"]}})


async def check_2fa(tmp_token: str):
    if await _enabled() and await _retry_minutes("2fa", _h(tmp_token), PER_2FA):
        raise HTTPException(429, "Too many incorrect codes. Please sign in again from the start.")


async def fail_2fa(tmp_token: str):
    if await _enabled():
        await _db.login_attempts.insert_one({"scope": "2fa", "key": _h(tmp_token), "at": datetime.now(timezone.utc)})


async def check_reset(ip: str):
    if not await _enabled():
        return
    mins = await _retry_minutes("reset_ip", _h(ip), PER_RESET_IP)
    if mins:
        _locked(mins, f"Too many attempts with invalid reset links. Please try again in {mins} minutes.")


async def fail_reset(ip: str):
    if await _enabled():
        await _db.login_attempts.insert_one({"scope": "reset_ip", "key": _h(ip), "at": datetime.now(timezone.utc)})
