"""
Iter9 backend feature tests.
Covers: Case Files, Reminders, Video gating, Law Firm Portal, Admin Dashboard,
Cloud Backup, Trustpilot Pre-renewal Review prompt.
"""
import os
import io
import time
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
PW = "Test12345!"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "ai_advocate_db")


# ---------- helpers ----------
def _signup(email_prefix: str):
    email = f"TEST_iter9_{email_prefix}_{int(time.time()*1000)}@advocate.app"
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "password": PW, "country": "GB", "language": "en-GB"
    }, timeout=30)
    assert r.status_code == 200, f"signup failed: {r.status_code} {r.text}"
    j = r.json()
    return email, j["access_token"], j["user"]


def _hdrs(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def trial_user():
    email, tok, user = _signup("trial")
    return {"email": email, "token": tok, "user": user}


@pytest.fixture(scope="module")
def free_user():
    """Trial-expired user → tier becomes free."""
    import asyncio
    email, tok, user = _signup("free")

    async def expire():
        cli = AsyncIOMotorClient(MONGO_URL)
        await cli[DB_NAME].users.update_one(
            {"email": email},
            {"$set": {"trial_end_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                      "subscription_status": "free", "tier": "free"}}
        )
        cli.close()
    asyncio.get_event_loop().run_until_complete(expire())
    # re-login to refresh token claims
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=30)
    assert r.status_code == 200
    return {"email": email, "token": r.json()["access_token"], "user": r.json()["user"]}


@pytest.fixture(scope="module")
def admin_user():
    """Create user whose email is admin@aiadvocate.co.uk so they pass admin gate."""
    import asyncio
    email = "admin@aiadvocate.co.uk"
    # Try signup; if conflict, try login.
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "password": PW, "country": "GB", "language": "en-GB"
    }, timeout=30)
    if r.status_code != 200:
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=30)
        assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return {"email": email, "token": r.json()["access_token"], "user": r.json()["user"]}


# ============ CASE FILES ============
class TestCases:
    def test_create_list_get_patch_delete(self, trial_user):
        tok = trial_user["token"]
        # create
        r = requests.post(f"{API}/cases", json={"name": "TEST Parking PCN", "category": "motoring"}, headers=_hdrs(tok))
        assert r.status_code == 200, r.text
        case = r.json()
        assert case["name"] == "TEST Parking PCN"
        assert case["status"] == "open"
        assert case["items_count"] == 0
        cid = case["id"]

        # list
        r = requests.get(f"{API}/cases", headers=_hdrs(tok))
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()["cases"]]
        assert cid in ids

        # get
        r = requests.get(f"{API}/cases/{cid}", headers=_hdrs(tok))
        assert r.status_code == 200
        assert r.json()["items"] == []

        # patch (rename + close)
        r = requests.patch(f"{API}/cases/{cid}", json={"name": "TEST Renamed Case", "status": "closed"},
                            headers=_hdrs(tok))
        assert r.status_code == 200
        assert r.json()["name"] == "TEST Renamed Case"
        assert r.json()["status"] == "closed"

        # attach item
        r = requests.post(f"{API}/cases/{cid}/items", json={
            "item_type": "chat", "item_id": "chat_test_1",
            "title": "PCN appeal letter draft", "preview": "Dear Sir/Madam, I appeal..."
        }, headers=_hdrs(tok))
        assert r.status_code == 200, r.text
        assert r.json()["case_id"] == cid

        # GET again — items now 1
        r = requests.get(f"{API}/cases/{cid}", headers=_hdrs(tok))
        assert len(r.json()["items"]) == 1

        # delete
        r = requests.delete(f"{API}/cases/{cid}", headers=_hdrs(tok))
        assert r.status_code == 200
        assert r.json()["deleted"] is True

        # GET 404
        r = requests.get(f"{API}/cases/{cid}", headers=_hdrs(tok))
        assert r.status_code == 404

    def test_export_pdf(self, trial_user):
        tok = trial_user["token"]
        r = requests.post(f"{API}/cases", json={"name": "TEST Export Case"}, headers=_hdrs(tok))
        cid = r.json()["id"]
        requests.post(f"{API}/cases/{cid}/items", json={
            "item_type": "chat", "item_id": "x1", "title": "Note", "preview": "Body"
        }, headers=_hdrs(tok))
        r = requests.get(f"{API}/cases/{cid}/export-pdf", headers=_hdrs(tok))
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_auto_name(self, trial_user):
        tok = trial_user["token"]
        r = requests.post(f"{API}/cases", json={"name": "Untitled case"}, headers=_hdrs(tok))
        cid = r.json()["id"]
        requests.post(f"{API}/cases/{cid}/items", json={
            "item_type": "chat", "item_id": "n1",
            "title": "Got a Penalty Charge Notice", "preview": "I parked for 10 minutes and got a £100 PCN from Westminster council."
        }, headers=_hdrs(tok))
        r = requests.post(f"{API}/cases/{cid}/auto-name", headers=_hdrs(tok))
        assert r.status_code == 200
        assert isinstance(r.json().get("name"), str)
        assert len(r.json()["name"]) > 0


# ============ REMINDERS ============
class TestReminders:
    def test_create_list_update(self, trial_user):
        tok = trial_user["token"]
        due = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        r = requests.post(f"{API}/reminders", json={"title": "TEST Appeal PCN", "due_at": due, "kind": "deadline"},
                          headers=_hdrs(tok))
        assert r.status_code == 200, r.text
        rid = r.json()["id"]

        r = requests.get(f"{API}/reminders", headers=_hdrs(tok))
        assert r.status_code == 200
        assert any(x["id"] == rid for x in r.json()["reminders"])

        r = requests.patch(f"{API}/reminders/{rid}?status=done", headers=_hdrs(tok))
        assert r.status_code == 200

        r = requests.get(f"{API}/reminders?status=done", headers=_hdrs(tok))
        assert any(x["id"] == rid for x in r.json()["reminders"])

    def test_detect_endpoint(self, trial_user):
        tok = trial_user["token"]
        msg = "I got a £100 PCN today, I have 14 days to challenge it."
        r = requests.post(f"{API}/reminders/detect",
                          data={"message": msg, "language": "en-GB", "country": "GB"},
                          headers=_hdrs(tok), timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "deadlines" in body
        assert isinstance(body["deadlines"], list)


# ============ VIDEO ANALYZE ============
class TestVideo:
    def test_free_tier_402(self, free_user):
        tok = free_user["token"]
        # Tiny dummy audio file — should be rejected by tier check BEFORE STT runs.
        files = {"audio": ("dummy.webm", b"\x00\x00\x00\x00", "audio/webm")}
        r = requests.post(f"{API}/video/analyze", files=files,
                          data={"language": "en-GB", "country": "GB"},
                          headers=_hdrs(tok), timeout=30)
        assert r.status_code == 402, f"expected 402 got {r.status_code} {r.text}"


# ============ FIRM PORTAL ============
class TestFirmPortal:
    @pytest.fixture(scope="class")
    def firm(self):
        email = f"firm_test_{int(time.time()*1000)}@example.com"
        r = requests.post(f"{API}/firm/signup", json={
            "email": email, "password": "FirmPass123!",
            "firm_name": "TEST Firm Ltd", "contact_name": "Jane Doe",
            "sra_number": "123456", "country": "GB", "city": "London",
            "phone": "+44 20 1234 5678", "specialties": ["criminal", "family"],
            "website": "https://example.com"
        }, timeout=30)
        assert r.status_code == 200, r.text
        return {"email": email, "token": r.json()["access_token"], "firm": r.json()["firm"]}

    def test_signup_returns_token_and_pending_status(self, firm):
        assert firm["firm"]["status"] == "pending_review"
        assert firm["token"]

    def test_login(self, firm):
        r = requests.post(f"{API}/firm/login", json={"email": firm["email"], "password": "FirmPass123!"}, timeout=30)
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_me_returns_recent_leads(self, firm):
        r = requests.get(f"{API}/firm/me", headers=_hdrs(firm["token"]))
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == firm["email"]
        assert "recent_leads" in body
        assert isinstance(body["recent_leads"], list)

    def test_listing_update_403_until_approved(self, firm):
        r = requests.patch(f"{API}/firm/listing", json={"phone": "+44 1234"}, headers=_hdrs(firm["token"]))
        assert r.status_code == 403


# ============ ADMIN ============
class TestAdmin:
    def test_non_admin_403(self, trial_user):
        r = requests.get(f"{API}/admin/stats", headers=_hdrs(trial_user["token"]))
        assert r.status_code == 403

    def test_admin_stats(self, admin_user):
        r = requests.get(f"{API}/admin/stats", headers=_hdrs(admin_user["token"]))
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("users_total", "firms_pending", "firms_approved", "chats_today", "leads_today"):
            assert k in body

    def test_admin_firms_list(self, admin_user):
        r = requests.get(f"{API}/admin/firms", headers=_hdrs(admin_user["token"]))
        assert r.status_code == 200
        assert isinstance(r.json()["firms"], list)

    def test_admin_approve_flow(self, admin_user):
        # find a pending firm
        r = requests.get(f"{API}/admin/firms?status=pending_review", headers=_hdrs(admin_user["token"]))
        firms = r.json()["firms"]
        if not firms:
            pytest.skip("No pending firm to approve")
        fid = firms[0]["id"]
        r = requests.post(f"{API}/admin/firms/action", json={"firm_id": fid, "action": "approve"},
                          headers=_hdrs(admin_user["token"]))
        assert r.status_code == 200
        assert r.json()["new_status"] == "approved"

    def test_admin_invalid_action(self, admin_user):
        r = requests.get(f"{API}/admin/firms", headers=_hdrs(admin_user["token"]))
        firms = r.json()["firms"]
        if not firms:
            pytest.skip("No firm")
        fid = firms[0]["id"]
        r = requests.post(f"{API}/admin/firms/action", json={"firm_id": fid, "action": "blow_up"},
                          headers=_hdrs(admin_user["token"]))
        assert r.status_code == 400


# ============ CLOUD BACKUP ============
class TestBackup:
    def test_export_for_trial(self, trial_user):
        r = requests.get(f"{API}/backup/export", headers=_hdrs(trial_user["token"]))
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/json")
        body = r.json()
        for k in ("cases", "conversations", "evidence", "letters", "reminders", "recordings", "user"):
            assert k in body

    def test_export_402_for_free(self, free_user):
        r = requests.get(f"{API}/backup/export", headers=_hdrs(free_user["token"]))
        assert r.status_code == 402, r.text


# ============ REVIEW PROMPT ============
class TestReview:
    def test_trial_running(self, trial_user):
        # Fresh signup has 14 days trial → should_prompt false (trial_running)
        r = requests.get(f"{API}/review/should-prompt", headers=_hdrs(trial_user["token"]))
        assert r.status_code == 200
        body = r.json()
        assert body["should_prompt"] is False
        assert body["reason"] in ("trial_running", "trial_ending")

    def test_trial_ending_true(self):
        # Create a trial user with trial_end_date ~30h from now → trial_days_remaining=1 → should_prompt true
        import asyncio
        email, tok, _ = _signup("trial_ending")

        async def shrink():
            cli = AsyncIOMotorClient(MONGO_URL)
            await cli[DB_NAME].users.update_one(
                {"email": email},
                {"$set": {"trial_end_date": (datetime.now(timezone.utc) + timedelta(hours=30)).isoformat()}}
            )
            cli.close()
        asyncio.get_event_loop().run_until_complete(shrink())
        r = requests.get(f"{API}/review/should-prompt", headers=_hdrs(tok))
        assert r.status_code == 200
        body = r.json()
        assert body["should_prompt"] is True
        assert body["reason"] == "trial_ending"

    def test_paid_renewal_soon(self):
        # Create a user, set tier=plus active with next_billing_date 5 days away → true
        import asyncio
        email, tok, _ = _signup("paid_renewal")

        async def set_paid():
            cli = AsyncIOMotorClient(MONGO_URL)
            await cli[DB_NAME].users.update_one(
                {"email": email},
                {"$set": {
                    "tier": "plus", "subscription_status": "active",
                    "next_billing_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
                }}
            )
            cli.close()
        asyncio.get_event_loop().run_until_complete(set_paid())
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=30)
        tok = r.json()["access_token"]
        r = requests.get(f"{API}/review/should-prompt", headers=_hdrs(tok))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["should_prompt"] is True
        assert body["reason"] == "renewal_soon"

    def test_review_recorded_stops_prompt(self):
        import asyncio
        email, tok, _ = _signup("recorded")

        async def shrink():
            cli = AsyncIOMotorClient(MONGO_URL)
            await cli[DB_NAME].users.update_one(
                {"email": email},
                {"$set": {"trial_end_date": (datetime.now(timezone.utc) + timedelta(hours=30)).isoformat()}}
            )
            cli.close()
        asyncio.get_event_loop().run_until_complete(shrink())
        r = requests.get(f"{API}/review/should-prompt", headers=_hdrs(tok))
        assert r.json()["should_prompt"] is True

        r = requests.post(f"{API}/review/recorded", headers=_hdrs(tok))
        assert r.status_code == 200
        assert r.json()["recorded"] is True

        r = requests.get(f"{API}/review/should-prompt", headers=_hdrs(tok))
        assert r.json()["should_prompt"] is False
        assert r.json()["reason"] == "already_reviewed"
