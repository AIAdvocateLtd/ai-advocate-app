"""Customer account erasure (UK GDPR Art. 17) and the extra categories for the data export (Art. 15/20).
Order is fail-safe: the account is locked first, every collection is attempted, and any failure leaves a
PII-free tombstone marked "incomplete" that the periodic sweeper retries."""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

# Collections holding the customer's own personal / legal data, keyed by user_id -> permanently deleted.
DELETE_BY_USER_ID = [
    "conversations", "cases", "case_items", "case_notes", "case_timeline_summaries", "legal_files", "lex_uploads",
    "reminders", "feature_requests", "vault_items", "vault_meta", "vault_shares", "usage_counters", "lex_chats",
    "security_events", "engagement_files", "wills", "emergency_profile", "emergency_events", "emergency_tracks",
    "evidence", "evidence_files", "evidence_invites", "witness_statements", "witness_invites", "form_drafts",
    "form_ocr_scans", "live_notes", "contract_analyses", "share_tokens", "feedback", "lex_feedback", "s3_flags",
    "law_firm_inquiries",
]
DELETE_BY_EMAIL = ["password_reset_tokens", "email_verify_log", "pending_comp_grants", "s3_flags"]
DELETE_OTHER = [("taster_answers", "claimed_by")]
# Kept for a stated reason, with the link to the person replaced by a one-way anonymous code.
ANONYMISE = [
    ("llm_usage", "user_id", None, "AI cost and spending-limit accounting"),
    ("usage", "user_id", None, "usage-limit accounting"),
    ("gift_topups", "recipient_user_id", "recipient_email", "financial record of a paid gift (UK tax: 6 years)"),
    ("comp_audit", "target_id", "target_email", "admin audit trail of complimentary access"),
    ("privacy_analytics_deletions", "user_id", "user_email", "accountability record of an analytics erasure"),
]
EXPORT_EXTRA = [
    "lex_uploads", "emergency_profile", "emergency_events", "emergency_tracks", "evidence", "evidence_files",
    "evidence_invites", "witness_statements", "witness_invites", "form_drafts", "form_ocr_scans", "live_notes",
    "contract_analyses", "case_timeline_summaries", "share_tokens", "vault_shares", "feedback", "lex_feedback",
    "law_firm_inquiries",
]
EXPORT_LIMIT = 2000
_SECRET_KEYS = {"token", "token_hash", "file_b64", "password_hash", "hashed_password", "totp_secret", "key", "secret"}


def anon_code(uid: str, secret: str) -> str:
    return "anon-" + hmac.new(secret.encode(), uid.encode(), hashlib.sha256).hexdigest()[:20]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def erase_user(db, uid: str, email: Optional[str], secret: str, retain: Optional[dict] = None) -> dict:
    """Idempotent: safe to rerun for the same uid until status is complete."""
    await db.users.update_one({"id": uid}, {"$set": {"deleted": True, "deletion.status": "in_progress",
                                                     "deletion.started_at": _now()},
                                            "$unset": {"password_hash": "", "hashed_password": "", "totp_secret": "",
                                                       "totp_backup_codes": ""}})
    failed: List[str] = []
    removed = {}

    async def attempt(label, coro):
        try:
            r = await coro
            n = getattr(r, "deleted_count", None)
            n = getattr(r, "modified_count", 0) if n is None else n
            if n:
                removed[label] = removed.get(label, 0) + n
        except Exception as e:
            logger.warning(f"erasure step {label} failed for {uid}: {e!r}")
            failed.append(label)

    for col in DELETE_BY_USER_ID:
        await attempt(col, db[col].delete_many({"user_id": uid}))
    for col, field in DELETE_OTHER:
        await attempt(col, db[col].delete_many({field: uid}))
    if email:
        for col in DELETE_BY_EMAIL:
            await attempt(f"{col}(email)", db[col].delete_many({"email": {"$in": list({email, email.lower()})}}))
    try:
        engs = [e["id"] async for e in db.engagements.find({"client_user_id": uid}, {"_id": 0, "id": 1})]
        if engs:
            await attempt("engagement_messages", db.engagement_messages.delete_many({"engagement_id": {"$in": engs}}))
            await attempt("engagement_files", db.engagement_files.delete_many({"engagement_id": {"$in": engs}}))
            await attempt("engagements", db.engagements.delete_many({"id": {"$in": engs}}))
    except Exception:
        failed.append("engagements")
    code = anon_code(uid, secret)
    for col, id_field, email_field, _ in ANONYMISE:
        upd = {id_field: code, **({email_field: None} if email_field else {})}
        await attempt(f"{col}(anonymised)", db[col].update_many({id_field: uid}, {"$set": upd}))
    status = "incomplete" if failed else "complete"
    tomb = {"id": uid, "deleted": True, "deleted_at": _now(), "email": f"deleted-{uid}@ai-advocate.local",
            "deletion": {"status": status, "failed": failed, "completed_at": _now() if not failed else None,
                         "retained": [f"{c}: {why}" for c, _, _, why in ANONYMISE]}}
    if retain:
        tomb.update(retain)
    if failed and email:
        tomb["deletion"]["pending_email"] = email.lower()  # needed only to finish erasure; removed on completion
    await db.users.replace_one({"id": uid}, tomb)
    return {"status": status, "failed": failed, "removed": removed}


async def retry_incomplete(db, secret: str) -> int:
    n = 0
    keep = ("stripe_subscription_id", "stripe_cancel_failed")
    async for u in db.users.find({"deletion.status": {"$in": ["incomplete", "in_progress"]}}, {"_id": 0}):
        await erase_user(db, u["id"], (u.get("deletion") or {}).get("pending_email") or
                         (None if str(u.get("email", "")).startswith("deleted-") else u.get("email")), secret,
                         {k: u[k] for k in keep if u.get(k)})
        n += 1
    return n


def clean(v, decrypt):
    if isinstance(v, dict):
        return {k: clean(x, decrypt) for k, x in v.items() if k not in _SECRET_KEYS and not k.endswith("_hash")}
    if isinstance(v, list):
        return [clean(x, decrypt) for x in v]
    if isinstance(v, str) and v.startswith("enc:"):
        return decrypt(v)
    return v


async def export_extra(db, uid: str, decrypt) -> dict:
    """The customer's own records only (user_id match), decrypted, with tokens / hashes / file blobs removed."""
    out = {}
    for col in EXPORT_EXTRA:
        rows = await db[col].find({"user_id": uid}, {"_id": 0}).to_list(EXPORT_LIMIT)
        if rows:
            out[col] = [clean(r, decrypt) for r in rows]
    rows = await db.taster_answers.find({"claimed_by": uid}, {"_id": 0}).to_list(EXPORT_LIMIT)
    if rows:
        out["taster_answers"] = [clean(r, decrypt) for r in rows]
    return out
