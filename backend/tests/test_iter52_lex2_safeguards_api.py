# Iteration 52: Lex 2.0 financial safeguards / passes / Extra Lex Credits — public API checks (no AI, no Stripe)
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
NEW_KEYS = ["allowances_v2_enabled", "passes_v2_enabled", "cost_cap_enabled", "emergency_allowance_enabled",
            "emergency_rights_limits_enabled", "credits_enabled", "usage_warnings_v2_enabled"]


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
    orig = requests.get(f"{API}/admin/fair-use", headers=admin).json()["settings"]
    yield
    patch = {k: False for k in NEW_KEYS}
    patch["monthly_cost_caps"] = orig["monthly_cost_caps"]
    patch["emergency_allowance"] = orig["emergency_allowance"]
    r = requests.put(f"{API}/admin/fair-use/settings", json=patch, headers=admin)
    assert r.status_code == 200
    s = r.json()
    assert all(s[k] is False for k in NEW_KEYS)


def put(admin, patch):
    r = requests.put(f"{API}/admin/fair-use/settings", json=patch, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


# Admin fair-use view
def test_admin_fair_use_defaults_off(admin):
    d = requests.get(f"{API}/admin/fair-use", headers=admin).json()
    for k in NEW_KEYS:
        assert d["settings"][k] is False, k
    p = d["proposed"]
    for k in ("allowances", "passes", "credit_packs", "credit_weights"):
        assert k in p
    assert "credits" in d and isinstance(d["credits"], list)
    assert p["credit_weights"].get("msgs") == 1


def test_admin_fair_use_requires_admin(user):
    assert requests.get(f"{API}/admin/fair-use", headers=user).status_code in (401, 403)
    assert requests.put(f"{API}/admin/fair-use/settings", json={"credits_enabled": True}, headers=user).status_code in (401, 403)


# Partial nested patch merge
def test_nested_patch_merges(admin):
    cur = requests.get(f"{API}/admin/fair-use", headers=admin).json()["settings"]
    s = put(admin, {"monthly_cost_caps": {"plus": 11.5}, "emergency_allowance": {"pro": [4, 12]}})
    assert s["monthly_cost_caps"]["plus"] == 11.5
    assert s["monthly_cost_caps"]["pro"] == cur["monthly_cost_caps"]["pro"]
    assert s["emergency_allowance"]["pro"] == [4, 12]
    assert s["emergency_allowance"]["plus"] == cur["emergency_allowance"]["plus"]
    s = put(admin, {"monthly_cost_caps": cur["monthly_cost_caps"], "emergency_allowance": cur["emergency_allowance"]})
    assert s["monthly_cost_caps"] == cur["monthly_cost_caps"]


def test_settings_validation(admin):
    r = requests.put(f"{API}/admin/fair-use/settings", json={"monthly_cost_caps": {"gold": 5}}, headers=admin)
    assert r.status_code == 422
    r = requests.put(f"{API}/admin/fair-use/settings", json={"emergency_rights_daily": 0}, headers=admin)
    assert r.status_code == 422


# Subscription tiers copy
def _plan(tiers, key):
    plans = tiers.get("tiers") or tiers.get("plans") or tiers
    if isinstance(plans, dict):
        return plans.get(key)
    return next(p for p in plans if p.get("id") == key or p.get("tier") == key)


def test_tiers_copy_default_and_v2(admin, user):
    t = requests.get(f"{API}/subscription/tiers", headers=user).text
    assert "300 Lex messages / month (fair use: up to 40 a day)" in t
    put(admin, {"allowances_v2_enabled": True})
    t2 = requests.get(f"{API}/subscription/tiers", headers=user).text
    put(admin, {"allowances_v2_enabled": False})
    assert "150 Lex messages / month (fair use: up to 20 a day)" in t2
    assert "350 Lex messages / month (fair use: up to 50 a day)" in t2
    t3 = requests.get(f"{API}/subscription/tiers", headers=user).text
    assert "300 Lex messages / month (fair use: up to 40 a day)" in t3


# Top-up taglines
def test_topup_taglines(admin, user):
    def day_tag():
        packs = requests.get(f"{API}/topups/packs", headers=user).json()["packs"]
        return next(p for p in packs if p["id"] == "day_pass")["tagline"]
    base = day_tag()
    assert "30 Lex messages" not in base
    put(admin, {"passes_v2_enabled": True})
    v2 = day_tag()
    put(admin, {"passes_v2_enabled": False})
    assert "30 Lex messages" in v2
    assert day_tag() == base


# Credits overview + checkout guards (no Stripe session)
def test_credits_overview_disabled(user):
    d = requests.get(f"{API}/credits", headers=user).json()
    assert d["enabled"] is False
    assert d["balance"] == 0
    packs = {p["id"]: (p["credits"], p["price_gbp"]) for p in d["packs"]}
    assert sorted(packs.values()) == [(25, 4.99), (60, 9.99), (120, 17.99)]
    assert d["valid_days"] == 365


def test_credits_checkout_guards(admin, user):
    r = requests.post(f"{API}/credits/checkout", json={"pack_id": "credits_small", "consent_immediate_supply": True}, headers=user)
    assert r.status_code == 403
    put(admin, {"credits_enabled": True})
    try:
        r1 = requests.post(f"{API}/credits/checkout", json={"pack_id": "credits_small"}, headers=user)
        r2 = requests.post(f"{API}/credits/checkout", json={"pack_id": "credits_small", "consent_immediate_supply": True}, headers=user)
        r3 = requests.post(f"{API}/credits/checkout", json={"pack_id": "nope", "consent_immediate_supply": True}, headers=user)
        d = requests.get(f"{API}/credits", headers=user).json()
    finally:
        put(admin, {"credits_enabled": False})
    assert r1.status_code == 400 and "tick" in r1.json()["detail"]
    assert r2.status_code == 503 and "not configured" in r2.json()["detail"]
    assert "checkout_url" not in r2.json()
    assert r3.status_code == 400
    assert d["enabled"] is True


def test_credits_requires_auth():
    assert requests.get(f"{API}/credits").status_code in (401, 403)
    assert requests.post(f"{API}/credits/checkout", json={"pack_id": "credits_small"}).status_code in (401, 403)


# Regression: usage view with switches off
def test_usage_view_ok(user):
    r = requests.get(f"{API}/subscription/usage", headers=user)
    assert r.status_code == 200
    assert "fair_use" in r.json()
