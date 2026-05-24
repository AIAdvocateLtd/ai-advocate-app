"""
Iter 20 — Phase A: Consumer Top-up Packs (one-off Stripe Web Checkout).
Tests:
 1. GET /api/topups/packs returns 4 packs with correct prices, grants_tier, configured=false, active=null
 2. POST /api/topups/checkout pack_id=day_pass (unconfigured) -> 503 helpful msg
 3. POST /api/topups/checkout pack_id=bogus -> 400
 4. POST /api/topups/checkout without auth -> 401/403
 5. POST /api/webhook/stripe with bogus signature -> 400 (route exists & rejects)
 6. Admin comp-grant to test user surfaces is_comp + comp_pro_until via GET /api/auth/me
"""
import os
import json
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

TEST_EMAIL = "test@advocate.app"
TEST_PASSWORD = "Test12345!"
ADMIN_EMAIL = "admin@aiadvocate.co.uk"
ADMIN_PASSWORD = "AdminLex2026!"

EXPECTED_PACKS = {
    "day_pass": {"price_gbp": 4.99, "grants_tier": "plus"},
    "letter_pack": {"price_gbp": 9.99, "grants_tier": "plus"},
    "weekend_pass": {"price_gbp": 14.99, "grants_tier": "plus"},
    "crisis_pack": {"price_gbp": 29.99, "grants_tier": "pro"},
}


@pytest.fixture(scope="module")
def test_token():
    r = requests.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Test user login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


# ----- 1. GET /api/topups/packs -----
class TestTopupPacksCatalog:
    def test_list_packs_returns_4(self, test_token):
        r = requests.get(f"{API}/topups/packs", headers={"Authorization": f"Bearer {test_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "packs" in data and "active" in data
        ids = {p["id"] for p in data["packs"]}
        assert ids == set(EXPECTED_PACKS.keys()), f"Missing/extra pack ids: {ids}"

    def test_pack_prices_and_grants(self, test_token):
        r = requests.get(f"{API}/topups/packs", headers={"Authorization": f"Bearer {test_token}"}, timeout=15)
        packs = {p["id"]: p for p in r.json()["packs"]}
        for pid, expected in EXPECTED_PACKS.items():
            p = packs[pid]
            assert p["price_gbp"] == expected["price_gbp"], f"{pid} price={p['price_gbp']}"
            assert p["grants_tier"] == expected["grants_tier"], f"{pid} grants_tier={p['grants_tier']}"
            assert p["configured"] is False, f"{pid} should be unconfigured (no Stripe price id) but configured={p['configured']}"
            assert isinstance(p.get("label"), str) and p["label"]
            assert isinstance(p.get("tagline"), str) and p["tagline"]

    def test_active_is_none_for_fresh_user(self, test_token):
        r = requests.get(f"{API}/topups/packs", headers={"Authorization": f"Bearer {test_token}"}, timeout=15)
        data = r.json()
        # spec says: returns `active: null` for a fresh user
        assert data["active"] in (None,), f"active expected None, got {data['active']}"


# ----- 2/3/4. POST /api/topups/checkout -----
class TestTopupCheckout:
    def test_unconfigured_pack_returns_503(self, test_token):
        r = requests.post(
            f"{API}/topups/checkout",
            headers={"Authorization": f"Bearer {test_token}"},
            json={"pack_id": "day_pass"},
            timeout=15,
        )
        assert r.status_code == 503, f"expected 503, got {r.status_code} {r.text}"
        body = r.json()
        msg = json.dumps(body)
        assert "STRIPE_PRICE_TOPUP_DAY_PASS" in msg, f"Helpful admin msg missing: {msg}"

    def test_bogus_pack_returns_400(self, test_token):
        r = requests.post(
            f"{API}/topups/checkout",
            headers={"Authorization": f"Bearer {test_token}"},
            json={"pack_id": "bogus"},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
        body = r.json()
        msg = json.dumps(body).lower()
        assert "unknown top-up pack" in msg or "bogus" in msg

    def test_no_auth_returns_401_or_403(self):
        r = requests.post(f"{API}/topups/checkout", json={"pack_id": "day_pass"}, timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code} {r.text}"


# ----- 5. Webhook exists & rejects bad sig -----
class TestTopupWebhook:
    def test_webhook_route_exists_rejects_bad_sig(self):
        payload = json.dumps({
            "id": "evt_test_iter20",
            "type": "checkout.session.completed",
            "data": {"object": {"metadata": {"user_id": "fake", "topup_pack": "crisis_pack"}}}
        })
        r = requests.post(
            f"{API}/webhook/stripe",
            data=payload,
            headers={"Stripe-Signature": "t=0,v1=garbage", "Content-Type": "application/json"},
            timeout=15,
        )
        # Endpoint exists -> not 404. With bogus sig + secret set, expect 400.
        assert r.status_code != 404, "webhook route missing"
        assert r.status_code in (400, 401, 403), f"expected sig rejection, got {r.status_code} {r.text}"


# ----- 6. Admin comp grant flow -----
class TestAdminCompGrant:
    def test_comp_test_user_then_me_shows_comp(self, admin_token, test_token):
        # try comp endpoint
        r = requests.post(
            f"{API}/admin/users/comp",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"email": TEST_EMAIL, "days": 7},
            timeout=20,
        )
        if r.status_code == 404:
            pytest.skip("/api/admin/users/comp endpoint not present in this build")
        assert r.status_code in (200, 201), f"comp grant failed: {r.status_code} {r.text}"

        # refresh test user via /api/auth/me
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {test_token}"}, timeout=15)
        assert me.status_code == 200, me.text
        pub = me.json()
        assert pub.get("is_comp") is True, f"is_comp not surfaced: {pub.get('is_comp')}"
        comp_until = pub.get("comp_pro_until")
        assert comp_until, "comp_pro_until missing"
        # should be ~7 days in the future
        dt = datetime.fromisoformat(comp_until.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff_days = (dt - now).days
        assert 5 <= diff_days <= 8, f"comp_pro_until ~7 days expected, got {diff_days} days"
        assert pub.get("tier") == "pro", f"comp user should be tier=pro, got {pub.get('tier')}"
