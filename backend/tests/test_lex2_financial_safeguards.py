"""Lex 2.0 financial safeguards, passes v2, Extra Lex Credits, emergency allowance (no AI calls, no payments).
Run: cd /app/backend && python -m pytest tests/test_lex2_financial_safeguards.py -q"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import stage3  # noqa: E402
import ai_usage  # noqa: E402

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
db = server.db
run = LOOP.run_until_complete
TAG = f"l2fin-{uuid.uuid4().hex[:8]}"


async def _no_email(subject, html):
    return None

stage3._email_owner = _no_email
run(stage3.ensure_indexes())


def _user(tier="plus", **kw):
    u = {"id": f"{TAG}-{uuid.uuid4().hex[:6]}", "email": f"{TAG}.{uuid.uuid4().hex[:4]}@example.com", "tier": tier,
         "subscription_status": "active" if tier in ("plus", "pro", "yearly") else "free", **kw}
    run(db.users.insert_one(dict(u)))
    return u


def _set(**kw):
    return run(stage3.update_settings(kw))


def _paid_on():
    _set(paid_limits_effective_at=(stage3._now() - timedelta(days=1)).isoformat(),
         thresholds={"plus": {"flag": 100, "cooldown": 100}, "pro": {"flag": 100, "cooldown": 100}})


def _deny(coro):
    with pytest.raises(HTTPException) as e:
        run(coro)
    assert e.value.status_code == 429
    return e.value.detail


async def _access_after(coro):
    await coro
    return ai_usage._access.get()


def _setcount(uid, bucket, feature, n):
    run(db.usage.update_one({"user_id": uid, "bucket": bucket, "feature": feature}, {"$set": {"count": n}}, upsert=True))


def _day():
    return f"{stage3._now().astimezone(stage3.UK):%Y-%m-%d}"


def _month():
    return f"{stage3._now().astimezone(stage3.UK):%Y-%m}"


def _grant(uid, pack="credits_small", sid=None, pi=None):
    return run(stage3.grant_credits(uid, pack, sid or f"cs_{TAG}_{uuid.uuid4().hex[:6]}", pi or f"pi_{TAG}_{uuid.uuid4().hex[:6]}"))


@pytest.fixture(autouse=True, scope="module")
def _restore():
    before = run(db.app_settings.find_one({"_id": "stage3"})) or {}
    yield
    run(db.app_settings.replace_one({"_id": "stage3"}, before, upsert=True) if before else db.app_settings.delete_one({"_id": "stage3"}))
    stage3._cache["settings"] = None
    for c in ("users",):
        run(db[c].delete_many({"id": {"$regex": f"^{TAG}"}}))
    for c in ("usage", "llm_usage", "s3_flags", "s3_events", "s3_consumptions", "lex_credits", "emergency_events"):
        run(db[c].delete_many({"user_id": {"$regex": TAG}}))
    run(db.emergency_rights_cache.delete_many({"_id": {"$regex": TAG}}))


@pytest.fixture(autouse=True)
def _fresh_request():
    stage3.begin_request()
    ai_usage.begin_request("/api/lex/chat")
    stage3._cache["monthly"].clear()
    yield


def test_all_new_switches_default_off():
    d = stage3.DEFAULTS
    for k in ("allowances_v2_enabled", "passes_v2_enabled", "cost_cap_enabled", "emergency_allowance_enabled",
              "emergency_rights_limits_enabled", "credits_enabled", "usage_warnings_v2_enabled"):
        assert d[k] is False
    assert d["monthly_cost_caps"] == {"plus": 10.0, "pro": 18.0, "yearly": 18.0}


def test_pricing_copy_follows_allowance_version():
    _set(allowances_v2_enabled=False)
    t = run(server.get_tiers())["tiers"]
    assert "300 Lex messages / month (fair use: up to 40 a day)" in t[1]["highlights"]
    _set(allowances_v2_enabled=True)
    t = run(server.get_tiers())["tiers"]
    assert "150 Lex messages / month (fair use: up to 20 a day)" in t[1]["highlights"]
    assert "350 Lex messages / month (fair use: up to 50 a day)" in t[2]["highlights"]
    _set(allowances_v2_enabled=False)


def test_v2_daily_and_monthly_allowances():
    _paid_on(); _set(allowances_v2_enabled=True)
    u = _user("plus")
    _setcount(u["id"], f"s3d-{_day()}", "msgs", 20)
    assert "fair-use limit of 20" in _deny(stage3.consume(u, "plus", "lex_chat"))
    p = _user("pro")
    _setcount(p["id"], f"s3m-{_month()}", "msgs", 350)
    assert "350 Lex messages" in _deny(stage3.consume(p, "pro", "lex_chat"))
    _set(allowances_v2_enabled=False, paid_limits_effective_at=None)


def test_cost_cap_blocks_with_reserve_and_only_when_enabled():
    _paid_on()
    u = _user("plus")
    run(db.llm_usage.insert_one({"user_id": u["id"], "ts": stage3._now().isoformat(), "cost_gbp": 9.80}))
    assert run(stage3.consume(u, "plus", "lex_chat"))
    _set(cost_cap_enabled=True)
    stage3._cache["monthly"].clear()
    assert "fair-use limit for AI use" in _deny(stage3.consume(u, "plus", "letters_generate"))
    pro = _user("pro")
    run(db.llm_usage.insert_one({"user_id": pro["id"], "ts": stage3._now().isoformat(), "cost_gbp": 17.0}))
    assert run(stage3.consume(pro, "pro", "lex_chat"))
    _set(cost_cap_enabled=False, paid_limits_effective_at=None)


def test_cost_cap_uses_fresh_spend_near_limit():
    _paid_on(); _set(cost_cap_enabled=True)
    u = _user("plus")
    run(db.llm_usage.insert_one({"user_id": u["id"], "ts": stage3._now().isoformat(), "cost_gbp": 8.5}))
    assert run(stage3.consume(u, "plus", "lex_chat"))
    run(db.llm_usage.insert_one({"user_id": u["id"], "ts": stage3._now().isoformat(), "cost_gbp": 1.5}))
    _deny(stage3.consume(u, "plus", "lex_chat"))  # cached value ignored once within 80% of the cap
    _set(cost_cap_enabled=False, paid_limits_effective_at=None)


def test_credit_grant_is_idempotent_and_expires_in_12_months():
    u = _user("free")
    sid = f"cs_{TAG}_dup"
    assert _grant(u["id"], "credits_medium", sid=sid)
    assert not _grant(u["id"], "credits_medium", sid=sid)
    b = run(stage3.credit_balance(u["id"]))
    assert b["balance"] == 60
    days = (stage3._parse_dt(b["lots"][0]["expires_at"]) - stage3._now()).days
    assert 363 <= days <= 365


def test_credits_used_only_after_allowance_with_weights_and_refund():
    _paid_on(); _set(credits_enabled=True, allowances_v2_enabled=True)
    u = _user("plus")
    _grant(u["id"])
    assert run(stage3.consume(u, "plus", "lex_chat"))  # plan allowance first
    assert run(stage3.credit_balance(u["id"]))["balance"] == 25
    _setcount(u["id"], f"s3m-{_month()}", "msgs", 150)
    assert run(_access_after(stage3.consume(u, "plus", "lex_chat"))) == "credits"
    assert run(stage3.credit_balance(u["id"]))["balance"] == 24
    _setcount(u["id"], f"s3m-{_month()}", "analyses", 15)
    assert run(stage3.consume(u, "plus", "doc_analyze"))
    assert run(stage3.credit_balance(u["id"]))["balance"] == 20
    run(stage3.refund(u["id"], "doc_analyze"))
    assert run(stage3.credit_balance(u["id"]))["balance"] == 24
    assert run(stage3._count(u["id"], f"s3cr-m-{_month()}", "credits")) == 1
    _set(credits_enabled=False, allowances_v2_enabled=False, paid_limits_effective_at=None)


def test_credits_never_used_when_disabled_or_for_deep_think_or_expired():
    _paid_on(); _set(allowances_v2_enabled=True)
    u = _user("plus")
    _grant(u["id"])
    _setcount(u["id"], f"s3m-{_month()}", "msgs", 150)
    _deny(stage3.consume(u, "plus", "lex_chat"))  # credits switched off
    _set(credits_enabled=True)
    pro = _user("pro")
    _grant(pro["id"])
    _setcount(pro["id"], f"s3m-{_month()}", "deep_think", 999)
    assert run(stage3.consume(pro, "pro", "deep_think", soft=True)) in (True, False)
    assert run(stage3.credit_balance(pro["id"]))["balance"] == 25
    run(db.lex_credits.update_many({"user_id": u["id"]}, {"$set": {"expires_at": (stage3._now() - timedelta(days=1)).isoformat()}}))
    _deny(stage3.consume(u, "plus", "lex_chat"))
    _set(credits_enabled=False, allowances_v2_enabled=False, paid_limits_effective_at=None)


def test_credits_allowed_past_cost_cap_and_daily_max():
    _paid_on(); _set(credits_enabled=True, cost_cap_enabled=True, credits_daily_max=2)
    u = _user("plus")
    _grant(u["id"])
    run(db.llm_usage.insert_one({"user_id": u["id"], "ts": stage3._now().isoformat(), "cost_gbp": 9.80}))
    assert run(stage3.consume(u, "plus", "lex_chat"))
    assert run(stage3.consume(u, "plus", "lex_chat"))
    _deny(stage3.consume(u, "plus", "lex_chat"))  # daily credit max
    _set(credits_enabled=False, cost_cap_enabled=False, credits_daily_max=60, paid_limits_effective_at=None)


def test_free_customer_with_credits_after_lifetime_actions():
    _set(credits_enabled=True)
    u = _user("free", signup_device_id=f"{TAG}-dev")
    run(stage3.consume(u, "free", "lex_chat")); run(stage3.consume(u, "free", "lex_chat"))
    msg = _deny(stage3.consume(u, "free", "lex_chat"))
    assert "Extra Lex Credits" in msg
    _grant(u["id"])
    assert run(stage3.consume(u, "free", "lex_chat"))
    assert run(stage3.credit_balance(u["id"]))["balance"] == 24
    _set(credits_enabled=False)


def test_refund_and_chargeback_revoke_unused_credits():
    u = _user("plus")
    pi = f"pi_{TAG}_rf"
    _grant(u["id"], "credits_large", pi=pi)
    run(db.lex_credits.update_one({"payment_intent": pi}, {"$set": {"remaining": 100}}))  # 20 used
    run(stage3.revoke_credits(pi, "refunded", 0.5))
    assert run(stage3.credit_balance(u["id"]))["balance"] == 40
    run(stage3.revoke_credits(pi, "disputed"))
    assert run(stage3.credit_balance(u["id"]))["balance"] == 0
    assert run(db.lex_credits.find_one({"payment_intent": pi}))["status"] == "disputed"


def test_emergency_allowance_after_limit_3_per_day():
    _paid_on(); _set(allowances_v2_enabled=True, emergency_allowance_enabled=True)
    u = _user("plus")
    _setcount(u["id"], f"s3m-{_month()}", "msgs", 150)
    urgent = "I have been arrested and I am at the police station right now, what do I do?"
    for _ in range(3):
        stage3.begin_request()
        run(stage3.pre_chat(u, "plus", urgent + uuid.uuid4().hex[:4], stream=False))
        run(stage3.release(u["id"]))
        assert run(_access_after(stage3.consume(u, "plus", "lex_chat"))) == "emergency"
    run(db.s3_events.delete_many({"user_id": u["id"]}))
    stage3.begin_request()
    run(stage3.pre_chat(u, "plus", urgent + "x", stream=False))
    msg = _deny(stage3.consume(u, "plus", "lex_chat"))
    assert "999" in msg and "0345 345 4345" in msg
    _set(allowances_v2_enabled=False, emergency_allowance_enabled=False, paid_limits_effective_at=None)


def test_emergency_allowance_not_for_ordinary_questions_or_documents():
    _paid_on(); _set(allowances_v2_enabled=True, emergency_allowance_enabled=True)
    u = _user("plus")
    _setcount(u["id"], f"s3m-{_month()}", "msgs", 150)
    run(stage3.pre_chat(u, "plus", "What is the difference between a will and a trust?", stream=False))
    _deny(stage3.consume(u, "plus", "lex_chat"))
    run(stage3.release(u["id"]))
    _setcount(u["id"], f"s3m-{_month()}", "analyses", 15)
    stage3.begin_request()
    run(stage3.pre_chat(u, "plus", "Bailiffs are at my door right now, eviction today", stream=False))
    _deny(stage3.consume(u, "plus", "doc_analyze"))
    _set(allowances_v2_enabled=False, emergency_allowance_enabled=False, paid_limits_effective_at=None)


def test_passes_v2_only_for_new_purchases():
    s = _set(passes_v2_enabled=True)
    since = s["passes_v2_since"]
    old_act = (stage3._parse_dt(since) - timedelta(minutes=5)).isoformat()
    new_act = stage3._now().isoformat()
    exp = (stage3._now() + timedelta(hours=20)).isoformat()
    s = run(stage3.settings())
    assert old_act >= s["launched_at"]
    old = _user("free", topup_active={"kind": "day_pass", "label": "Day Pass", "activated_at": old_act, "expires_at": exp})
    new = _user("free", topup_active={"kind": "day_pass", "label": "Day Pass", "activated_at": new_act, "expires_at": exp})
    _setcount(old["id"], f"s3-pass-{old_act}", "msgs", 30)
    _setcount(new["id"], f"s3-pass-{new_act}", "msgs", 30)
    assert run(stage3.consume(old, "plus", "lex_chat"))  # purchased before: keeps 50
    assert "Day Pass" in _deny(stage3.consume(new, "plus", "lex_chat"))  # new purchase: 30
    _set(passes_v2_enabled=False)


def test_usage_warnings_v2_at_80_percent():
    _paid_on(); _set(allowances_v2_enabled=True, usage_warnings_v2_enabled=True, credits_enabled=True,
                     emergency_allowance_enabled=True)
    u = _user("plus")
    _setcount(u["id"], f"s3m-{_month()}", "msgs", 121)
    v = run(stage3.usage_view(u, "plus"))
    joined = " ".join(v["warnings"])
    assert "121 of your 150 Lex messages" in joined and "29 left" in joined and "Resets on 1 " in joined
    assert "never charged automatically" in joined and "Emergency answers left today: 3" in joined
    assert v["can_buy_credits"] and v["emergency"]["daily"] == 3 and v["helplines"]
    _set(allowances_v2_enabled=False, usage_warnings_v2_enabled=False, credits_enabled=False,
         emergency_allowance_enabled=False, paid_limits_effective_at=None)


def test_emergency_rights_reuse_and_daily_limit_without_ai():
    _set(emergency_rights_limits_enabled=True, emergency_rights_daily=1)
    u = _user("free")
    country = f"GB-{TAG}"
    run(stage3.emergency_rights_store(country, "en-GB", "CACHED SCRIPT"))
    r = run(server.emergency_rights(server.EmergencyRequest(country=country), user=u))
    assert r["rights_script"] == "CACHED SCRIPT" and r["reused"]
    _setcount(u["id"], f"s3er-{stage3._uk_day()}", "emergency_rights", 1)
    r = run(server.emergency_rights(server.EmergencyRequest(country=country, note="handcuffed"), user=u))
    assert r["limited"] and "999" in r["rights_script"]
    _set(emergency_rights_limits_enabled=False, emergency_rights_daily=5)


def test_settings_patch_merges_nested_caps():
    s = _set(monthly_cost_caps={"plus": 13.0})
    assert s["monthly_cost_caps"] == {"plus": 13.0, "pro": 18.0, "yearly": 18.0}
    _set(monthly_cost_caps={"plus": 10.0})
