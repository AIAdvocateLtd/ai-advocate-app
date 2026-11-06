"""Stage 3 release verification — simulated, no AI calls.
Run: cd /app/backend && python -m pytest tests/test_stage3_release.py -q"""
import os
import sys
import uuid
from datetime import timedelta

import pytest
import requests
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.test_stage3_limits import run, db, server, stage3, login_guard, _user, _deny, TAG, SENT  # noqa: E402,F401
from tests.test_stage3_limits import _restore  # noqa: E402,F401  (module cleanup fixture)

API = (open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].strip('"')) + "/api"
UKNOW = lambda: stage3._now().astimezone(stage3.UK)  # noqa: E731


def _month(uid, kind, n):
    run(db.usage.update_one({"user_id": uid, "bucket": f"s3m-{UKNOW():%Y-%m}", "feature": kind}, {"$set": {"count": n}}, upsert=True))


def _day(uid, kind, n):
    run(db.usage.update_one({"user_id": uid, "bucket": f"s3d-{UKNOW():%Y-%m-%d}", "feature": kind}, {"$set": {"count": n}}, upsert=True))


@pytest.fixture
def paid_on():
    run(stage3.update_settings({"paid_limits_effective_at": (stage3._now() - timedelta(days=1)).isoformat()}))
    yield
    run(stage3.update_settings({"paid_limits_effective_at": None}))


def _fresh(u):
    return run(db.users.find_one({"id": u["id"]}, {"_id": 0}))


# ---------- Pro / Yearly allowances ----------
def test_pro_monthly_and_daily_message_caps(paid_on):
    u = _user("pro")
    _month(u["id"], "msgs", 600)
    assert "600 Lex messages" in _deny(stage3.consume(u, "pro", "lex_chat"))
    _month(u["id"], "msgs", 10); _day(u["id"], "msgs", 80)
    assert "fair-use limit of 80" in _deny(stage3.consume(u, "pro", "lex_chat"))
    _day(u["id"], "msgs", 79)
    assert run(stage3.consume(u, "pro", "lex_chat"))


@pytest.mark.parametrize("tier,feature,kind,cap", [
    ("pro", "letters_generate", "letters", 50), ("pro", "evidence_analyze", "analyses", 25),
    ("pro", "doc_analyze", "analyses", 25), ("pro", "tts", "tts", 150), ("pro", "translate", "translations", 150),
    ("pro", "live_assist_session", "live_sessions", 6), ("plus", "letters_generate", "letters", 20),
    ("plus", "evidence_analyze", "analyses", 15), ("plus", "tts", "tts", 100), ("yearly", "tts", "tts", 150),
])
def test_feature_caps_match_wording(paid_on, tier, feature, kind, cap):
    u = _user(tier)
    _month(u["id"], kind, cap - 1)
    assert run(stage3.consume(u, tier, feature))
    _deny(stage3.consume(u, tier, feature))


def test_hearing_minutes_cap(paid_on):
    u = _user("pro")
    _month(u["id"], "hearing_min", 290)
    assert run(stage3.consume(u, "pro", "hearing", amount=10))
    _deny(stage3.consume(u, "pro", "hearing", amount=1))


def test_yearly_grandfathered_until_renewal_then_capped(paid_on):
    gf = _user("yearly", s3_grandfather_until=(stage3._now() + timedelta(days=100)).isoformat())
    _month(gf["id"], "msgs", 600)
    assert run(stage3.consume(gf, "yearly", "lex_chat"))
    renewed = _user("yearly", s3_grandfather_until=(stage3._now() - timedelta(days=1)).isoformat())
    _month(renewed["id"], "msgs", 600)
    _deny(stage3.consume(renewed, "yearly", "lex_chat"))


def test_no_paid_caps_before_start_date_or_for_trials():
    run(stage3.update_settings({"paid_limits_effective_at": None}))
    for tier in ("plus", "pro", "yearly", "trial_pro"):
        u = _user(tier)
        _month(u["id"], "msgs", 5000); _day(u["id"], "msgs", 500)
        assert run(stage3.consume(u, tier, "lex_chat")), tier
        assert run(stage3.consume(u, tier, "letters_generate")), tier


# ---------- Passes ----------
def _pass(kind, label, before_launch=False):
    act = "2000-01-01T00:00:00+00:00" if before_launch else stage3._now().isoformat()
    return _user("free", topup_active={"kind": kind, "label": label, "activated_at": act,
                                       "expires_at": (stage3._now() + timedelta(hours=20)).isoformat()}), act


def _pass_count(uid, act, kind, n):
    run(db.usage.update_one({"user_id": uid, "bucket": f"s3-pass-{act}", "feature": kind}, {"$set": {"count": n}}, upsert=True))


@pytest.mark.parametrize("kind,label,tier,feature,cap_kind,cap", [
    ("weekend_pass", "Weekend Pass", "plus", "lex_chat", "msgs", 120),
    ("weekend_pass", "Weekend Pass", "plus", "tts", "tts", 30),
    ("day_pass", "Day Pass", "plus", "letters_generate", "letters", 2),
    ("day_pass", "Day Pass", "plus", "tts", "tts", 10),
    ("crisis_pack", "Crisis Pack", "pro", "live_assist_session", "live_sessions", 1),
    ("crisis_pack", "Crisis Pack", "pro", "translate", "translations", 30),
    ("letter_pack", "Letter Pack", "plus", "lex_chat", "msgs", 100),
    ("letter_pack", "Letter Pack", "plus", "letters_generate", "letters", 5),
    ("letter_pack", "Letter Pack", "plus", "doc_analyze", "analyses", 1),
])
def test_pass_entitlements(kind, label, tier, feature, cap_kind, cap):
    u, act = _pass(kind, label)
    _pass_count(u["id"], act, cap_kind, cap - 1)
    assert run(stage3.consume(u, tier, feature))
    assert label in _deny(stage3.consume(u, tier, feature))


def test_crisis_deep_think_soft_cap_and_old_pass_uncapped():
    u, act = _pass("crisis_pack", "Crisis Pack")
    _pass_count(u["id"], act, "deep_think", 5)
    assert run(stage3.consume(u, "pro", "deep_think", soft=True)) is False
    old, act2 = _pass("day_pass", "Day Pass", before_launch=True)
    _pass_count(old["id"], act2, "msgs", 999)
    assert run(stage3.consume(old, "plus", "lex_chat"))


def test_pass_falls_back_to_subscription(paid_on):
    u, act = _pass("day_pass", "Day Pass")
    run(db.users.update_one({"id": u["id"]}, {"$set": {"tier": "plus", "subscription_status": "active"}}))
    u = _fresh(u)
    _pass_count(u["id"], act, "msgs", 50)
    assert run(stage3.consume(u, "plus", "lex_chat"))
    assert run(db.usage.find_one({"user_id": u["id"], "bucket": f"s3m-{UKNOW():%Y-%m}", "feature": "msgs"}))["count"] == 1


# ---------- Spending safeguards ----------
def _spend(uid, gbp):
    run(db.llm_usage.insert_one({"user_id": uid, "ts": stage3._now().isoformat(), "cost_gbp": gbp}))


def test_pro_cooldown_then_pause_until_midnight(paid_on):
    u = _user("pro")
    _spend(u["id"], 8.1)
    assert "short break" in _deny(stage3.check_spend(u, "pro"))
    run(db.s3_flags.update_many({"user_id": u["id"], "level": "cooldown"}, {"$set": {"until": stage3._now().isoformat()}}))
    _spend(u["id"], 8.0)
    _deny(stage3.check_spend(u, "pro"))
    levels = [f["level"] for f in run(db.s3_flags.find({"user_id": u["id"]}).to_list(10))]
    assert "paused" in levels and "cooldown" in levels


def test_yearly_monthly_review_flag_alert_only():
    run(stage3.update_settings({"paid_limits_effective_at": None}))
    u = _user("yearly")
    _spend(u["id"], 21)
    run(stage3.check_spend(u, "yearly"))
    levels = {f["level"] for f in run(db.s3_flags.find({"user_id": u["id"]}).to_list(10))}
    assert levels == {"flag", "monthly_review"}


def test_auto_site_brake_free_only_and_email():
    SENT.clear()
    run(db.app_settings.update_one({"_id": "stage3"}, {"$set": {"site_brake_multiplier": 0.000001},
                                                        "$unset": {"brake_emailed_day": "", "site_brake_manual": ""}}))
    stage3._cache["settings"] = None
    stage3._cache["site_spend"] = (0.0, 0.0)
    _spend(f"{TAG}-site", 0.01)
    try:
        free = _user("free")
        assert "paused until midnight" in _deny(stage3.consume(free, "free", "lex_chat"))
        assert any("Free AI paused" in s for s in SENT)
        assert run(stage3.consume(_user("pro"), "pro", "lex_chat"))
    finally:
        run(db.app_settings.update_one({"_id": "stage3"}, {"$set": {"site_brake_multiplier": 2.0}, "$unset": {"brake_emailed_day": ""}}))
        stage3._cache["settings"] = None


def test_translate_refunded_when_request_fails(paid_on):
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    u = _user("pro")

    async def call_next(_req):
        await stage3.charge(u, "pro", "translate")
        return JSONResponse({"detail": "AI failed"}, status_code=500)

    req = Request({"type": "http", "method": "POST", "path": "/api/lex/translate", "headers": [], "query_string": b""})
    run(server._ai_usage_request_context(req, call_next))
    assert run(db.usage.find_one({"user_id": u["id"], "bucket": f"s3m-{UKNOW():%Y-%m}", "feature": "translations"}))["count"] == 0


# ---------- Login / signup security ----------
def test_account_locked_from_any_network_after_15():
    email = f"{TAG}-any@example.com"
    for i in range(15):
        run(login_guard.fail("user", email, f"198.51.100.{i + 1}"))
    _deny(login_guard.check("user", email, "198.51.100.200"))


def test_network_locked_after_50_failures_across_emails():
    ip = "192.0.2.77"
    for i in range(50):
        run(login_guard.fail("user", f"{TAG}-n{i}@example.com", ip))
    _deny(login_guard.check("user", f"{TAG}-other@example.com", ip))
    run(login_guard.check("user", f"{TAG}-other@example.com", "192.0.2.78"))


def test_firm_login_and_reset_link_limits_over_http():
    try:
        codes = [requests.post(f"{API}/firm/login", json={"email": f"{TAG}-firm@example.com", "password": "x"}, timeout=20).status_code
                 for _ in range(6)]
        assert codes[-1] == 429, codes
        codes = [requests.post(f"{API}/firm/users/login", json={"email": f"{TAG}-fee@example.com", "password": "x"}, timeout=20).status_code
                 for _ in range(6)]
        assert codes[-1] == 429, codes
        codes = [requests.post(f"{API}/auth/reset-password", json={"token": uuid.uuid4().hex, "new_password": "Abcdefgh1!"}, timeout=20).status_code
                 for _ in range(11)]
        assert 429 in codes, codes
    finally:
        run(db.login_attempts.delete_many({}))


def test_sentry_and_owner_email_environment_label():
    src = open(os.path.join(os.path.dirname(server.__file__), "server.py")).read()
    assert 'environment="preview" if "preview.emergentagent.com" in (os.environ.get("FRONTEND_URL") or "") else "production"' in src
    assert "preview.emergentagent.com" in os.environ.get("FRONTEND_URL", "")
