"""Stage 3 fair-use, safeguards and login limits (no AI calls). Run: cd /app/backend && python -m pytest tests/test_stage3_limits.py -q"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import stage3  # noqa: E402
import login_guard  # noqa: E402

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
db = server.db
run = LOOP.run_until_complete
TAG = f"s3test-{uuid.uuid4().hex[:8]}"
SENT = []


async def _no_email(subject, html):
    SENT.append(subject)


stage3._email_owner = _no_email


def _user(tier="free", **kw):
    u = {"id": f"{TAG}-{uuid.uuid4().hex[:6]}", "email": f"{TAG}.{uuid.uuid4().hex[:4]}@example.com", "tier": tier,
         "subscription_status": "active" if tier in ("plus", "pro", "yearly") else "free", **kw}
    run(db.users.insert_one(dict(u)))
    return u


@pytest.fixture(autouse=True, scope="module")
def _restore():
    before = run(db.app_settings.find_one({"_id": "stage3"})) or {}
    yield
    run(db.app_settings.replace_one({"_id": "stage3"}, before, upsert=True) if before else db.app_settings.delete_one({"_id": "stage3"}))
    stage3._cache["settings"] = None
    run(db.users.delete_many({"id": {"$regex": f"^{TAG}"}}))
    run(db.usage.delete_many({"user_id": {"$regex": TAG}}))
    run(db.llm_usage.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.s3_flags.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.s3_events.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.s3_consumptions.delete_many({"user_id": {"$regex": f"^{TAG}"}}))
    run(db.login_attempts.delete_many({}))


def _deny(coro):
    with pytest.raises(HTTPException) as e:
        run(coro)
    assert e.value.status_code == 429
    return e.value.detail


def test_canonical_email():
    assert stage3.canonical_email("J.O.Smith+x@GoogleMail.com") == "josmith@gmail.com"
    assert stage3.canonical_email("a.b+y@outlook.com") == "a.b@outlook.com"


def test_free_two_lifetime_actions_and_refund():
    u = _user("free", signup_device_id=f"{TAG}-dev1")
    assert run(stage3.consume(u, "free", "lex_chat"))
    assert run(stage3.consume(u, "free", "letters_generate"))
    assert "2 free Lex questions" in _deny(stage3.consume(u, "free", "lex_chat"))
    run(stage3.refund(u["id"], "letters_generate"))
    assert run(stage3.consume(u, "free", "evidence_analyze"))


def test_free_allowance_shared_by_device_and_gmail_alias():
    a = _user("free", signup_device_id=f"{TAG}-dev2", email=f"{TAG}.x.y@gmail.com")
    run(stage3.consume(a, "free", "lex_chat")); run(stage3.consume(a, "free", "lex_chat"))
    same_device = _user("free", signup_device_id=f"{TAG}-dev2")
    _deny(stage3.consume(same_device, "free", "lex_chat"))
    alias = _user("free", email=f"{TAG}.xy+new@gmail.com")
    _deny(stage3.consume(alias, "free", "lex_chat"))


def test_legacy_free_daily_quota_replaced_and_refund_quota():
    u = _user("free")
    ok, *_ = run(server.check_quota_and_increment(u["id"], "free", "lex_chat", "daily"))
    assert ok
    run(server.refund_quota(u["id"], "lex_chat", "daily"))
    assert run(stage3.usage_view(u, "free"))["items"]["free_actions"]["used"] == 0


def test_paid_limits_off_until_effective_date():
    u = _user("plus")
    run(stage3.update_settings({"paid_limits_effective_at": None}))
    run(db.usage.update_one({"user_id": u["id"], "bucket": f"s3d-{stage3._now().astimezone(stage3.UK):%Y-%m-%d}", "feature": "msgs"},
                            {"$set": {"count": 40}}, upsert=True))
    assert run(stage3.consume(u, "plus", "lex_chat"))
    run(stage3.update_settings({"paid_limits_effective_at": (stage3._now() - timedelta(days=1)).isoformat()}))
    assert "fair-use limit of 40" in _deny(stage3.consume(u, "plus", "lex_chat"))
    run(stage3.update_settings({"paid_limits_effective_at": None}))


def test_yearly_grandfathered_until_renewal():
    future = (stage3._now() + timedelta(days=200)).isoformat()
    u = _user("yearly", current_period_end=future)
    run(stage3.update_settings({"paid_limits_effective_at": (stage3._now() - timedelta(days=1)).isoformat()}))
    fresh = run(db.users.find_one({"id": u["id"]}, {"_id": 0}))
    assert fresh["s3_grandfather_until"] == future
    assert not run(stage3.paid_limits_active(fresh))
    run(stage3.update_settings({"paid_limits_effective_at": None}))


def test_day_pass_caps_without_subscription():
    s = run(stage3.settings())
    act = (stage3._now()).isoformat()
    u = _user("free", topup_active={"kind": "day_pass", "label": "Day Pass", "activated_at": act,
                                    "expires_at": (stage3._now() + timedelta(hours=20)).isoformat()})
    assert act >= s["launched_at"]
    run(db.usage.update_one({"user_id": u["id"], "bucket": f"s3-pass-{act}", "feature": "msgs"}, {"$set": {"count": 50}}, upsert=True))
    assert "Day Pass" in _deny(stage3.consume(u, "plus", "lex_chat"))


def test_paid_cooldown_then_lift():
    run(stage3.update_settings({"paid_limits_effective_at": (stage3._now() - timedelta(days=1)).isoformat()}))
    u = _user("plus")
    run(db.llm_usage.insert_one({"user_id": u["id"], "ts": stage3._now().isoformat(), "cost_gbp": 4.2}))
    assert "short break" in _deny(stage3.check_spend(u, "plus"))
    levels = {f["level"] for f in run(db.s3_flags.find({"user_id": u["id"]}).to_list(10))}
    assert {"flag", "cooldown"} <= levels
    run(db.s3_flags.update_many({"user_id": u["id"], "level": "cooldown"}, {"$set": {"lifted": True}}))
    run(stage3.check_spend(u, "plus"))
    run(stage3.update_settings({"paid_limits_effective_at": None}))


def test_paid_flag_only_before_effective_date():
    u = _user("pro")
    run(db.llm_usage.insert_one({"user_id": u["id"], "ts": stage3._now().isoformat(), "cost_gbp": 9.0}))
    run(stage3.check_spend(u, "pro"))
    assert [f["level"] for f in run(db.s3_flags.find({"user_id": u["id"]}).to_list(10))] == ["flag"]


def test_free_site_brake_manual_pause_and_resume():
    u = _user("free")
    run(stage3.set_brake("pause"))
    assert "paused until midnight" in _deny(stage3.consume(u, "free", "lex_chat"))
    run(stage3.set_brake("resume"))
    assert run(stage3.consume(u, "free", "lex_chat"))


def test_pre_chat_duplicate_and_lock():
    u = _user("plus")
    stage3.begin_request()
    run(stage3.pre_chat(u, "plus", "same question", stream=False))
    _deny(stage3.pre_chat(u, "plus", "another question", stream=False))
    run(stage3.release(u["id"]))
    assert "already working" in _deny(stage3.pre_chat(u, "plus", "same question", stream=False))


def test_login_lockout_and_success_reset():
    email, ip = f"{TAG}@example.com", "203.0.113.9"
    for _ in range(5):
        run(login_guard.check("user", email, ip)); run(login_guard.fail("user", email, ip))
    assert "Too many sign-in attempts" in _deny(login_guard.check("user", email, ip))
    run(login_guard.check("user", email, "198.51.100.7"))
    run(login_guard.success("user", email, ip))
    run(login_guard.check("user", email, ip))


def test_2fa_attempt_limit():
    tok = f"{TAG}-tmp"
    for _ in range(5):
        run(login_guard.fail_2fa(tok))
    assert "sign in again" in _deny(login_guard.check_2fa(tok))


def test_client_ip_ignores_spoofed_forwarded_for():
    from types import SimpleNamespace as NS
    req = lambda x: NS(headers={"x-forwarded-for": x}, client=NS(host="10.0.0.1"))
    assert server._client_ip(req("203.0.113.77,136.108.30.124,104.22.56.9,34.102.193.45")) == "136.108.30.124"
    assert server._client_ip(req("136.108.30.124,108.162.237.97,34.102.193.45")) == "136.108.30.124"
    assert server._client_ip(req("1.2.3.4, 9.9.9.9, 34.102.193.45")) == "9.9.9.9"
