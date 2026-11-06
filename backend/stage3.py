"""Stage 3: fair-use allowances, spend safeguards, Free site brake, abuse guards."""
import os, re, time, hashlib, logging, contextvars
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException

logger = logging.getLogger(__name__)
UK = ZoneInfo("Europe/London")
_db = None
_cache = {"settings": None, "at": 0.0, "site_spend": (0.0, 0.0), "monthly": {}}

DEFAULTS = {
    "login_limits_enabled": True,
    "abuse_guards_enabled": True,
    "free_lifetime_enabled": True,
    "free_lifetime_actions": 2,
    "free_lifetime_cost_cap_gbp": 0.10,
    "free_signups_per_network_7d": 10,
    "pass_limits_enabled": True,
    "spend_guard_enabled": True,
    "paid_limits_effective_at": None,
    "site_brake_enabled": True,
    "site_brake_multiplier": 2.0,
    "site_brake_manual": None,
    "site_brake_manual_day": None,
    "burst_per_minute": 8,
    "cooldown_minutes": 60,
    "thresholds": {
        "plus": {"flag": 1.50, "cooldown": 4.00, "monthly_review": 12.00},
        "pro": {"flag": 3.00, "cooldown": 8.00, "monthly_review": 25.00},
        "yearly": {"flag": 3.00, "cooldown": 8.00, "monthly_review": 20.00},
    },
}

# (monthly, daily) allowances once paid limits take effect. None = no cap.
_PRO = {"msgs": (600, 80), "letters": (50, None), "analyses": (25, None), "tts": (150, None),
        "live_sessions": (6, None), "translations": (150, None), "hearing_min": (300, None)}
PAID = {"plus": {"msgs": (300, 40), "letters": (20, None), "analyses": (15, None), "tts": (100, None)},
        "pro": _PRO, "yearly": _PRO}
PASSES = {
    "day_pass": {"msgs": 50, "letters": 2, "analyses": 5, "tts": 10},
    "weekend_pass": {"msgs": 120, "letters": 5, "analyses": 5, "tts": 30},
    "crisis_pack": {"msgs": 80, "deep_think": 5, "letters": 5, "analyses": 5, "live_sessions": 1,
                    "hearing_min": 60, "tts": 30, "translations": 30},
    "letter_pack": {"msgs": 100, "letters": 5, "analyses": 1},
}
FREE_KINDS = {"msgs", "letters", "analyses"}
FEATURE_KIND = {"lex_chat": "msgs", "letters_generate": "letters", "evidence_analyze": "analyses",
                "doc_analyze": "analyses", "tts": "tts", "live_assist_session": "live_sessions",
                "deep_think": "deep_think", "translate": "translations", "hearing": "hearing_min"}
KIND_LABEL = {"msgs": "Lex messages", "letters": "letters", "analyses": "document analyses", "tts": "read-alouds",
              "live_sessions": "Live Assist sessions", "translations": "translations",
              "hearing_min": "hearing-recorder minutes", "deep_think": "Deep Think answers"}
PAID_TIERS = ("plus", "pro", "yearly")
SUPPORT = "support@aiadvocate.co.uk"

_req = contextvars.ContextVar("s3_request", default=None)


def init(db):
    global _db
    _db = db


async def ensure_indexes():
    await _db.s3_events.create_index("at", expireAfterSeconds=3600)
    await _db.s3_events.create_index([("user_id", 1), ("kind", 1), ("at", -1)])
    await _db.s3_consumptions.create_index("at_dt", expireAfterSeconds=86400)
    await _db.s3_consumptions.create_index([("user_id", 1), ("feature", 1), ("at_dt", -1)])
    await _db.s3_flags.create_index([("user_id", 1), ("day", 1)])
    await _db.llm_usage.create_index([("user_id", 1), ("ts", 1)])
    await _db.llm_usage.create_index("ts")


def _now():
    return datetime.now(timezone.utc)


def _uk_midnight_utc(months_back: bool = False) -> datetime:
    n = _now().astimezone(UK)
    start = n.replace(day=1) if months_back else n
    return start.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _uk_day() -> str:
    return _now().astimezone(UK).strftime("%Y-%m-%d")


def canonical_email(email: str) -> str:
    e = (email or "").strip().lower()
    if "@" not in e:
        return e
    local, domain = e.split("@", 1)
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def email_key(email: str) -> str:
    """Pseudonymous allowance key — the address itself is never stored in usage counters."""
    return "email:" + hashlib.sha256(canonical_email(email).encode()).hexdigest()[:32]


# ---------------- Settings ----------------
async def settings() -> dict:
    if _cache["settings"] and time.monotonic() - _cache["at"] < 15:
        return _cache["settings"]
    doc = await _db.app_settings.find_one({"_id": "stage3"}) or {}
    if not doc:
        doc = {"_id": "stage3", "launched_at": _now().isoformat()}
        await _db.app_settings.update_one({"_id": "stage3"}, {"$setOnInsert": doc}, upsert=True)
    merged = {**DEFAULTS, **{k: v for k, v in doc.items() if k != "_id"}}
    merged["thresholds"] = {t: {**DEFAULTS["thresholds"][t], **(doc.get("thresholds") or {}).get(t, {})}
                            for t in DEFAULTS["thresholds"]}
    _cache.update(settings=merged, at=time.monotonic())
    return merged


async def update_settings(patch: dict) -> dict:
    allowed = set(DEFAULTS) - {"site_brake_manual", "site_brake_manual_day"}
    clean = {k: v for k, v in patch.items() if k in allowed and v is not None or k == "paid_limits_effective_at"}
    if clean.get("paid_limits_effective_at"):
        clean["paid_limits_effective_at"] = _parse_dt(clean["paid_limits_effective_at"]).isoformat()
    if "thresholds" in clean:
        cur = (await settings())["thresholds"]
        clean["thresholds"] = {t: {k: float(v) for k, v in {**cur[t], **(clean["thresholds"].get(t) or {})}.items()
                                   if k in ("flag", "cooldown", "monthly_review")} for t in cur}
    if clean:
        await _db.app_settings.update_one({"_id": "stage3"}, {"$set": clean}, upsert=True)
    if clean.get("paid_limits_effective_at"):
        await _snapshot_yearly_grandfathering()
    _cache["settings"] = None
    return await settings()


async def _snapshot_yearly_grandfathering():
    # Yearly subscribers keep current terms until their renewal date at the time limits were announced.
    async for u in _db.users.find({"tier": "yearly", "subscription_status": "active",
                                   "s3_grandfather_until": {"$exists": False}},
                                  {"_id": 0, "id": 1, "current_period_end": 1}):
        until = u.get("current_period_end") or (_now() + timedelta(days=365)).isoformat()
        await _db.users.update_one({"id": u["id"]}, {"$set": {"s3_grandfather_until": until}})


# ---------------- Spend ----------------
async def _sum_cost(match: dict) -> float:
    agg = await _db.llm_usage.aggregate([{"$match": match},
                                         {"$group": {"_id": None, "t": {"$sum": "$cost_gbp"}}}]).to_list(1)
    return round(float((agg[0]["t"] if agg else 0) or 0), 4)


async def user_spend_today(user_id: str) -> float:
    return await _sum_cost({"user_id": user_id, "ts": {"$gte": _uk_midnight_utc().isoformat()}})


async def user_spend_month(user_id: str) -> float:
    hit = _cache["monthly"].get(user_id)
    if hit and time.monotonic() - hit[1] < 600:
        return hit[0]
    v = await _sum_cost({"user_id": user_id, "ts": {"$gte": _uk_midnight_utc(True).isoformat()}})
    _cache["monthly"][user_id] = (v, time.monotonic())
    return v


async def site_spend_today() -> float:
    v, at = _cache["site_spend"]
    if time.monotonic() - at < 60:
        return v
    v = await _sum_cost({"ts": {"$gte": _uk_midnight_utc().isoformat()}})
    _cache["site_spend"] = (v, time.monotonic())
    return v


def daily_budget() -> float:
    return float(os.environ.get("AA_DAILY_LLM_BUDGET_GBP") or 30)


async def _email_owner(subject: str, html: str):
    try:
        from email_helper import send_email
        admins = [e.strip() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()]
        if os.environ.get("SENTRY_ENV") == "preview":
            subject = f"[Preview] {subject}"
        for a in admins:
            await send_email(to=a, kind="firm", subject=subject, body_html=html)
    except Exception as e:
        logger.warning(f"stage3 owner email failed: {e!r}")


# ---------------- Site brake (Free only) ----------------
async def brake_status() -> dict:
    s = await settings()
    day = _uk_day()
    spent = await site_spend_today()
    limit = daily_budget() * float(s["site_brake_multiplier"])
    manual = s.get("site_brake_manual") if s.get("site_brake_manual_day") == day else None
    if manual == "paused":
        paused, reason = True, "manual"
    elif manual == "override" or not s["site_brake_enabled"]:
        paused, reason = False, manual or "disabled"
    else:
        paused, reason = spent >= limit, "auto"
    return {"paused": paused, "reason": reason, "spent_today_gbp": spent, "brake_at_gbp": round(limit, 2),
            "alert_at_gbp": daily_budget(), "manual": manual, "day": day, "enabled": s["site_brake_enabled"]}


async def set_brake(action: str):
    val = {"pause": "paused", "override": "override", "resume": None}[action]
    await _db.app_settings.update_one({"_id": "stage3"}, {"$set": {"site_brake_manual": val,
                                                                    "site_brake_manual_day": _uk_day()}}, upsert=True)
    _cache["settings"] = None


async def check_free_brake():
    st = await brake_status()
    s = await settings()
    if st["paused"] and st["reason"] == "auto" and s.get("brake_emailed_day") != st["day"]:
        await _db.app_settings.update_one({"_id": "stage3"}, {"$set": {"brake_emailed_day": st["day"]}})
        _cache["settings"] = None
        await _email_owner(f"AI Advocate — Free AI paused (estimated spend £{st['spent_today_gbp']:.2f} today)",
                           f"<p>Estimated AI spend today reached £{st['spent_today_gbp']:.2f} (brake at £{st['brake_at_gbp']:.2f}). "
                           "Free-tier AI is paused until midnight UK time. Paid customers are not affected.</p>"
                           "<p>You can resume Free AI from Admin → Fair use &amp; spending.</p>")
    elif not st["paused"] and s.get("brake_emailed_day") and s.get("brake_emailed_day") != st["day"] \
            and s.get("brake_reset_emailed_day") != s.get("brake_emailed_day"):
        await _db.app_settings.update_one({"_id": "stage3"}, {"$set": {"brake_reset_emailed_day": s["brake_emailed_day"]}})
        _cache["settings"] = None
        await _email_owner("AI Advocate — Free AI resumed", "<p>The daily Free-tier safety brake has reset. Free AI is available again.</p>")
    if st["paused"]:
        raise HTTPException(429, "Lex is very busy for free accounts today, so free questions are paused until midnight UK time. "
                                 "Paid plans are not affected — upgrade to keep going now.")


# ---------------- Spend safeguards (paid) ----------------
def _threshold_tier(tier: str):
    return "yearly" if tier == "yearly" else "pro" if tier in ("pro", "trial_pro") else "plus" if tier == "plus" else None


async def paid_limits_active(user: dict) -> bool:
    s = await settings()
    eff, gf = _parse_dt(s.get("paid_limits_effective_at")), _parse_dt(user.get("s3_grandfather_until"))
    if not eff or _now() < eff:
        return False
    return not (gf and _now() < gf)


def _parse_dt(v):
    if not v:
        return None
    d = v if isinstance(v, datetime) else datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=UK)


async def _flag(user: dict, day: str, level: str, spent: float, until: str = None):
    doc = {"user_id": user["id"], "email": user.get("email"), "tier": user.get("tier"), "day": day, "level": level,
           "spent_gbp": spent, "at": _now().isoformat(), "until": until, "lifted": False}
    await _db.s3_flags.insert_one(doc)
    label = {"flag": "flagged", "cooldown": "put on a 1-hour cool-down", "paused": "paused until midnight",
             "monthly_review": "flagged for monthly review"}[level]
    await _email_owner(f"AI Advocate — customer {label} (estimated £{spent:.2f})",
                       f"<p>{user.get('email')} ({user.get('tier')}) was {label}. Estimated AI spend: £{spent:.2f}.</p>"
                       "<p>Review or lift it in Admin → Fair use &amp; spending.</p>")


async def check_spend(user: dict, tier: str):
    s = await settings()
    tt = _threshold_tier(tier)
    if not s["spend_guard_enabled"] or not tt or user.get("s3_exempt"):
        return
    th = s["thresholds"][tt]
    day = _uk_day()
    flags = await _db.s3_flags.find({"user_id": user["id"], "day": day}, {"_id": 0}).to_list(50)
    now_iso = _now().isoformat()
    for f in flags:
        if f["level"] in ("cooldown", "paused") and not f.get("lifted") and (f.get("until") or "") > now_iso:
            until = datetime.fromisoformat(f["until"]).astimezone(UK).strftime("%H:%M")
            raise HTTPException(429, f"Your account has had unusually high AI usage today, so Lex is taking a short break "
                                     f"until {until} (UK time). This fair-use safeguard is explained in our Terms. "
                                     f"If you think this is a mistake, email {SUPPORT}.")
    levels = {f["level"] for f in flags}
    if any(f.get("lifted") and f["level"] in ("cooldown", "paused") for f in flags):
        return
    spent = await user_spend_today(user["id"])
    enforce = await paid_limits_active(user)
    if spent >= th["flag"] and "flag" not in levels:
        await _flag(user, day, "flag", spent)
    if enforce and spent >= th["cooldown"] * 2 and "paused" not in levels and "cooldown" in levels:
        until = _uk_midnight_utc() + timedelta(days=1)
        await _flag(user, day, "paused", spent, until.isoformat())
        return await check_spend(user, tier)
    if enforce and spent >= th["cooldown"] and "cooldown" not in levels:
        until = _now() + timedelta(minutes=int(s["cooldown_minutes"]))
        await _flag(user, day, "cooldown", spent, until.isoformat())
        return await check_spend(user, tier)
    month = _now().astimezone(UK).strftime("%Y-%m")
    if spent >= th["flag"] / 2 or not _cache["monthly"].get(user["id"]):
        if await user_spend_month(user["id"]) >= th["monthly_review"] and \
                not await _db.s3_flags.find_one({"user_id": user["id"], "level": "monthly_review", "day": {"$regex": f"^{month}"}}):
            await _flag(user, day, "monthly_review", await user_spend_month(user["id"]))


# ---------------- Abuse guards (chat) ----------------
async def pre_chat(user: dict, tier: str, message: str, stream: bool):
    """Burst, duplicate/retry, one-answer-at-a-time, brake and spend checks before any AI work."""
    s = await settings()
    if _is_owner(user) or user.get("s3_exempt"):
        return
    if tier == "free":
        await check_free_brake()
    await check_spend(user, tier)
    if not s["abuse_guards_enabled"]:
        return
    uid, now = user["id"], _now()
    recent = await _db.s3_events.count_documents({"user_id": uid, "kind": "msg", "at": {"$gte": now - timedelta(seconds=60)}})
    if recent >= int(s["burst_per_minute"]):
        raise HTTPException(429, "You're sending messages very quickly. Please wait a minute and try again.")
    h = hashlib.sha256((message or "").strip().lower().encode()).hexdigest()[:24]
    same = await _db.s3_events.find({"user_id": uid, "kind": "msg", "h": h, "at": {"$gte": now - timedelta(minutes=10)}},
                                    {"_id": 0, "at": 1}).sort("at", -1).to_list(10)
    if same and (now - same[0]["at"].replace(tzinfo=timezone.utc)).total_seconds() < 30:
        raise HTTPException(429, "Lex is already working on that message — please wait for the answer.")
    if len(same) >= 4:
        raise HTTPException(429, "You've retried this message several times. Please wait 10 minutes or rephrase your question.")
    lock = await _db.s3_events.find_one({"user_id": uid, "kind": "lock", "at": {"$gte": now - timedelta(seconds=90)}})
    if lock:
        raise HTTPException(429, "Lex is still answering your previous message — please wait for it to finish.")
    await _db.s3_events.insert_one({"user_id": uid, "kind": "msg", "h": h, "at": now})
    await _db.s3_events.insert_one({"user_id": uid, "kind": "lock", "at": now})
    r = _req.get()
    if r is not None:
        r["lock"] = uid


def keep_lock_for_stream():
    """The streaming body releases the lock itself when it finishes."""
    r = _req.get()
    if r is not None:
        r["lock"] = None


async def release(user_id: str):
    await _db.s3_events.delete_many({"user_id": user_id, "kind": "lock"})


# ---------------- Allowances ----------------
def _is_owner(user: dict) -> bool:
    admins = [e.strip().lower() for e in (os.environ.get("ADMIN_EMAILS") or "admin@aiadvocate.co.uk").split(",") if e.strip()]
    return (user.get("email") or "").lower() in admins


def _active_pass(user: dict, launched_at: str):
    p = user.get("topup_active") or {}
    if p.get("kind") in PASSES and (p.get("expires_at") or "") > _now().isoformat() \
            and (p.get("activated_at") or "") >= launched_at:
        return p
    return None


async def _count(key: str, bucket: str, feature: str) -> int:
    d = await _db.usage.find_one({"user_id": key, "bucket": bucket, "feature": feature}, {"_id": 0, "count": 1})
    return int((d or {}).get("count") or 0)


async def _inc(entries: list, amount: int):
    for key, bucket, feature in entries:
        await _db.usage.update_one({"user_id": key, "bucket": bucket, "feature": feature},
                                   {"$inc": {"count": amount}, "$set": {"updated_at": _now().isoformat()}}, upsert=True)


def _deny(msg: str, soft: bool):
    if soft:
        return False
    raise HTTPException(429, msg)


async def replaces_legacy(user: dict, tier: str, feature: str) -> bool:
    s = await settings()
    kind = FEATURE_KIND.get(feature, feature)
    if tier == "free":
        return s["free_lifetime_enabled"] and kind in FREE_KINDS
    if _active_pass(user, s["launched_at"]) and s["pass_limits_enabled"]:
        return True
    return tier in PAID_TIERS and kind in PAID.get(tier, {}) and await paid_limits_active(user)


async def consume(user: dict, tier: str, feature: str, amount: int = 1, soft: bool = False):
    """Charge Stage 3 allowances. Raises 429 (or returns False when soft) if exhausted."""
    s = await settings()
    kind = FEATURE_KIND.get(feature, feature)
    if _is_owner(user) or user.get("s3_exempt"):
        return True
    entries = []
    if tier == "free":
        if kind in FREE_KINDS:
            await check_free_brake()
        if not (s["free_lifetime_enabled"] and kind in FREE_KINDS):
            return True
        keys = [email_key(user.get("email"))]
        if user.get("signup_device_id"):
            keys.append(f"device:{user['signup_device_id']}")
        used = max([await _count(k, "s3-lifetime", "free_actions") for k in keys])
        cap = int(s["free_lifetime_actions"])
        if used >= cap:
            return _deny(f"You've used your {cap} free Lex questions. Upgrade to Plus or buy a Day Pass to keep going.", soft)
        if await _sum_cost({"user_id": user["id"], "ts": {"$gte": s["launched_at"]}}) >= float(s["free_lifetime_cost_cap_gbp"]):
            return _deny("You've reached the free usage limit. Upgrade to Plus or buy a Day Pass to keep going.", soft)
        entries = [(k, "s3-lifetime", "free_actions") for k in keys]
    else:
        await check_spend(user, tier)
        p = _active_pass(user, s["launched_at"]) if s["pass_limits_enabled"] else None
        base_tier = user.get("tier") if user.get("subscription_status") == "active" else None
        if p and kind in PASSES[p["kind"]]:
            bucket = f"s3-pass-{p['activated_at']}"
            if await _count(user["id"], bucket, kind) + amount <= PASSES[p["kind"]][kind]:
                entries = [(user["id"], bucket, kind)]
            elif base_tier not in PAID_TIERS:
                return _deny(f"You've used all the {KIND_LABEL.get(kind, kind)} included in your {p.get('label') or 'pass'}.", soft)
            else:
                tier = base_tier
        if not entries and tier in PAID_TIERS and kind in PAID[tier] and await paid_limits_active(user):
            monthly, daily = PAID[tier][kind]
            n = _now().astimezone(UK)
            mb, db_ = f"s3m-{n:%Y-%m}", f"s3d-{n:%Y-%m-%d}"
            if monthly is not None and await _count(user["id"], mb, kind) + amount > monthly:
                return _deny(f"You've used this month's {monthly} {KIND_LABEL[kind]} on your plan. "
                             "Your allowance resets on the 1st of the month.", soft)
            if daily is not None and await _count(user["id"], db_, kind) + amount > daily:
                return _deny(f"You've reached today's fair-use limit of {daily} {KIND_LABEL[kind]}. "
                             "It resets at midnight UK time.", soft)
            entries = [(user["id"], mb, kind)] + ([(user["id"], db_, kind)] if daily is not None else [])
    if not entries:
        return True
    await _inc(entries, amount)
    await _db.s3_consumptions.insert_one({"user_id": user["id"], "feature": feature, "entries": entries,
                                          "amount": amount, "at_dt": _now()})
    return True


async def refund(user_id: str, feature: str):
    c = await _db.s3_consumptions.find_one_and_delete({"user_id": user_id, "feature": feature,
                                                       "at_dt": {"$gte": _now() - timedelta(minutes=30)}},
                                                      sort=[("at_dt", -1)])
    if c:
        for key, bucket, f in c["entries"]:
            await _db.usage.update_one({"user_id": key, "bucket": bucket, "feature": f, "count": {"$gt": 0}},
                                       {"$inc": {"count": -int(c.get("amount") or 1)}})


async def charge(user: dict, tier: str, feature: str, amount: int = 1):
    """For AI endpoints without a legacy quota: abuse checks + allowance, refunded automatically on failure."""
    await consume(user, tier, feature, amount)
    track_charge(user["id"], feature, "s3")


# ---------------- Per-request refund tracking ----------------
def begin_request():
    _req.set({"charges": [], "lock": None})


def track_charge(user_id: str, feature: str, period: str):
    r = _req.get()
    if r is not None:
        r["charges"].append((user_id, feature, period))


def request_charges():
    r = _req.get()
    return r["charges"] if r is not None else []


def request_lock():
    r = _req.get()
    return r["lock"] if r is not None else None


# ---------------- Customer usage view ----------------
async def usage_view(user: dict, tier: str) -> dict:
    s = await settings()
    out = {"items": {}, "warnings": []}
    if _is_owner(user):
        return out
    if tier == "free" and s["free_lifetime_enabled"]:
        keys = [email_key(user.get("email"))] + \
            ([f"device:{user['signup_device_id']}"] if user.get("signup_device_id") else [])
        used = max([await _count(k, "s3-lifetime", "free_actions") for k in keys])
        cap = int(s["free_lifetime_actions"])
        out["items"]["free_actions"] = {"used": used, "limit": cap, "period": "lifetime"}
        if used >= cap:
            out["warnings"].append(f"You've used your {cap} free Lex questions.")
        return out
    if tier in PAID_TIERS and await paid_limits_active(user):
        n = _now().astimezone(UK)
        for kind, (monthly, _d) in PAID[tier].items():
            used = await _count(user["id"], f"s3m-{n:%Y-%m}", kind)
            out["items"][kind] = {"used": used, "limit": monthly, "period": "monthly"}
            if monthly and used >= 0.8 * monthly:
                out["warnings"].append(f"You've used {used} of {monthly} {KIND_LABEL[kind]} this month.")
    return out
