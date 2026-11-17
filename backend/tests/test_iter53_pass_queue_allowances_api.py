# Iteration 53: switch-driven allowances copy, new cap defaults, pass queue view (no AI, no Stripe)
import os
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
SWITCHES = ["allowances_v2_enabled", "passes_v2_enabled", "cost_cap_enabled", "emergency_allowance_enabled",
            "emergency_rights_limits_enabled", "credits_enabled", "usage_warnings_v2_enabled"]


def _env(key):
    for line in open("/app/backend/.env"):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json().get('access_token') or r.json().get('token')}"}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@aiadvocate.co.uk", "AdminLex2026!")


@pytest.fixture(scope="module")
def user():
    return _login("test@advocate.app", "Test12345!")


@pytest.fixture(scope="module", autouse=True)
def restore(admin):
    yield
    r = requests.put(f"{API}/admin/fair-use/settings", json={k: False for k in SWITCHES}, headers=admin)
    assert r.status_code == 200
    assert all(r.json()[k] is False for k in SWITCHES)


def _wait_allow(pred, tries=12):
    d = None
    for _ in range(tries):
        d = requests.get(f"{API}/plans/allowances").json()
        if pred(d):
            return d
        time.sleep(2)
    return d


# Admin defaults: new caps + v2 review levels, v1 review thresholds unchanged
def test_admin_defaults(admin):
    s = requests.get(f"{API}/admin/fair-use", headers=admin).json()["settings"]
    assert s["monthly_cost_caps"] == {"plus": 14, "pro": 28, "yearly": 28}
    assert s["monthly_review_v2"] == {"plus": 10, "pro": 18, "yearly": 18}
    assert s["thresholds"]["plus"]["monthly_review"] == 12
    assert s["thresholds"]["pro"]["monthly_review"] == 25
    for k in SWITCHES:
        assert s[k] is False, k


# Public allowances with switches OFF
def test_allowances_default():
    d = _wait_allow(lambda d: d["version"] == "v1")
    assert d["plus"] == {"monthly": 300, "daily": 40}
    assert d["pro"] == {"monthly": 600, "daily": 80}
    assert d["fair_use_note"] == ""
    t = requests.get(f"{API}/subscription/tiers").json()
    assert t["fair_use_note"] == ""
    txt = str(t["tiers"])
    assert "300 Lex messages" in txt and "600 Lex messages" in txt


# Switch v2 + cost cap ON → 150/20, 350/50, fair-use note
def test_allowances_v2_on(admin):
    r = requests.put(f"{API}/admin/fair-use/settings",
                     json={"allowances_v2_enabled": True, "cost_cap_enabled": True}, headers=admin)
    assert r.status_code == 200
    d = _wait_allow(lambda d: d["version"] == "v2" and d["cost_cap"])
    assert d["plus"] == {"monthly": 150, "daily": 20}
    assert d["pro"] == {"monthly": 350, "daily": 50}
    n = d["fair_use_note"]
    assert "20 Lex messages a day on Plus" in n and "50 on Pro" in n
    assert "monthly fair-use limit on AI cost" in n and "pause Lex before your message allowance" in n
    t = requests.get(f"{API}/subscription/tiers").json()
    assert t["fair_use_note"] == n
    txt = str(t["tiers"])
    assert "150 Lex messages / month (fair use: up to 20 a day)" in txt
    assert "350 Lex messages / month (fair use: up to 50 a day)" in txt
    # switch back off
    requests.put(f"{API}/admin/fair-use/settings",
                 json={"allowances_v2_enabled": False, "cost_cap_enabled": False}, headers=admin)
    d = _wait_allow(lambda d: d["version"] == "v1" and not d["cost_cap"])
    assert d["plus"]["monthly"] == 300 and d["fair_use_note"] == ""


# Queued pass view for seeded data
def test_topups_packs_queued(user):
    c = MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]
    now = datetime.now(timezone.utc)
    exp = (now + timedelta(hours=10)).isoformat()
    u = c.users.find_one({"email": "test@advocate.app"}, {"topup_active": 1, "topup_queue": 1})
    assert not u.get("topup_active") and not u.get("topup_queue"), "account already has pass data"
    c.users.update_one({"email": "test@advocate.app"}, {"$set": {
        "topup_active": {"kind": "day_pass", "label": "Day Pass", "grants_tier": "plus", "duration_hours": 24,
                         "activated_at": (now - timedelta(hours=14)).isoformat(), "expires_at": exp},
        "topup_queue": [{"kind": "weekend_pass", "label": "Weekend Pass", "grants_tier": "plus", "duration_hours": 72,
                         "purchased_at": now.isoformat(), "queue_id": "x1", "queued_at": now.isoformat()}]}})
    try:
        d = requests.get(f"{API}/topups/packs", headers=user).json()
        assert d["active"]["kind"] == "day_pass" and d["active"]["expires_at"] == exp
        q = d["queued"]
        assert len(q) == 1 and q[0]["kind"] == "weekend_pass"
        assert q[0]["starts_at"] == exp
        assert datetime.fromisoformat(q[0]["ends_at"]) - datetime.fromisoformat(exp) == timedelta(hours=72)
        # promotion must NOT happen while active pass still running
        u2 = c.users.find_one({"email": "test@advocate.app"}, {"topup_queue": 1})
        assert len(u2["topup_queue"]) == 1
    finally:
        c.users.update_one({"email": "test@advocate.app"}, {"$unset": {"topup_active": "", "topup_queue": ""}})
