"""Iter13 — Additional engagement coverage:
- reminders/badge endpoint
- firm/subscribe plan validation
- free + featured tier engagement 402
- invite locked to email (wrong client rejection)
"""
import os, time, asyncio, base64
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = BASE_URL + "/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ai_advocate_db")

CLIENT_EMAIL = "test@advocate.app"
CLIENT_PWD = "Test12345!"


def _bump_tier(firm_id: str, tier: str):
    async def _do():
        cli = AsyncIOMotorClient(MONGO_URL)
        db = cli[DB_NAME]
        await db.firm_accounts.update_one({"id": firm_id}, {"$set": {"tier": tier, "status": "approved"}})
        cli.close()
    asyncio.run(_do())


@pytest.fixture(scope="module")
def client_token():
    r = requests.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PWD}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    return d.get("token") or d.get("access_token")


@pytest.fixture()
def fresh_firm():
    """Signup a new firm each call (default tier=free)."""
    email = f"TEST_firm_iter13_{int(time.time()*1000)}@advocate.app"
    r = requests.post(f"{API}/firm/signup", json={
        "firm_name": "Iter13 Test Firm", "contact_name": "Test Lead",
        "email": email, "password": "FirmPass123!", "country": "GB", "city": "London",
        "specialties": ["employment"],
    }, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"id": d["firm"]["id"], "token": d["access_token"], "email": email,
            "headers": {"Authorization": f"Bearer {d['access_token']}"}}


# -------------------- Reminders badge ----------------------
class TestRemindersBadge:
    def test_badge_returns_count_field(self, client_token):
        r = requests.get(f"{API}/reminders/badge", headers={"Authorization": f"Bearer {client_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "count" in data and isinstance(data["count"], int)
        assert data["count"] >= 0

    def test_badge_requires_auth(self):
        r = requests.get(f"{API}/reminders/badge", timeout=15)
        assert r.status_code in (401, 403), r.text


# -------------------- Firm subscribe plan validation ----------------------
class TestFirmSubscribePlan:
    def test_invalid_plan_returns_400(self, fresh_firm):
        r = requests.post(f"{API}/firm/subscribe?plan=verified", headers=fresh_firm["headers"], timeout=15)
        assert r.status_code == 400, r.text
        assert "plan must be" in r.text.lower() or "featured" in r.text.lower()

    @pytest.mark.parametrize("plan", ["featured", "premium", "practice"])
    def test_valid_plans_accepted(self, fresh_firm, plan):
        # Either 200 with checkout_url, or 503 because price ID env not configured (practice).
        r = requests.post(f"{API}/firm/subscribe?plan={plan}", headers=fresh_firm["headers"], timeout=20)
        assert r.status_code in (200, 503), f"plan={plan}: {r.status_code} {r.text}"
        if r.status_code == 200:
            assert "checkout_url" in r.json()


# -------------------- Tier-based engagement creation gate ----------------------
class TestEngagementTierGate:
    def test_free_tier_blocked_402(self, fresh_firm):
        # Default tier is 'free' on signup.
        r = requests.post(f"{API}/firm/engagements", headers=fresh_firm["headers"],
                          json={"client_email": "someone@example.com", "matter": "Test"}, timeout=15)
        assert r.status_code == 402, r.text

    def test_featured_tier_blocked_402(self, fresh_firm):
        _bump_tier(fresh_firm["id"], "featured")
        r = requests.post(f"{API}/firm/engagements", headers=fresh_firm["headers"],
                          json={"client_email": "someone@example.com", "matter": "Test"}, timeout=15)
        assert r.status_code == 402, r.text

    def test_premium_tier_allows(self, fresh_firm):
        _bump_tier(fresh_firm["id"], "premium")
        r = requests.post(f"{API}/firm/engagements", headers=fresh_firm["headers"],
                          json={"client_email": CLIENT_EMAIL, "matter": "Employment"}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("invite_token") and d.get("invite_url")

    def test_firm_engagements_list_includes_limit(self, fresh_firm):
        _bump_tier(fresh_firm["id"], "premium")
        r = requests.get(f"{API}/firm/engagements", headers=fresh_firm["headers"], timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "limit" in d and d["limit"] == 25
        assert "active_count" in d


# -------------------- Invite locked to email ----------------------
class TestInviteEmailLock:
    def test_wrong_email_rejected_403(self, fresh_firm):
        _bump_tier(fresh_firm["id"], "premium")
        # Invite is sent to a non-matching email
        r = requests.post(f"{API}/firm/engagements", headers=fresh_firm["headers"],
                          json={"client_email": "someoneelse@example.com", "matter": "Locked"}, timeout=15)
        assert r.status_code == 200, r.text
        token = r.json()["invite_token"]

        # Public preview still works (no auth)
        pv = requests.get(f"{API}/engagements/invite/{token}", timeout=15)
        assert pv.status_code == 200
        assert "firm_name" in pv.json() and "matter" in pv.json()

        # Logged-in client (test@advocate.app) tries to accept — should be 403
        login = requests.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PWD}, timeout=15)
        tok = login.json().get("token") or login.json().get("access_token")
        acc = requests.post(f"{API}/engagements/accept/{token}",
                            headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert acc.status_code == 403, acc.text
        assert "someoneelse@example.com" in acc.text.lower() or "sign in" in acc.text.lower()


# -------------------- Public preview 404 ----------------------
class TestInvitePreview404:
    def test_unknown_token_404(self):
        r = requests.get(f"{API}/engagements/invite/nonexistent_xyz", timeout=15)
        assert r.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
