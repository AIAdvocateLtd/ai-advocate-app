"""Backend tests: Deadline reminders, key dates, checklist, cron, signup-no-trial, prefs."""
import os
import uuid
import time
import requests
from datetime import datetime, timedelta, timezone
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

# Load WEBHOOK_CRON_SECRET from backend .env (not from frontend env)
def _load_cron_secret():
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                if line.strip().startswith("WEBHOOK_CRON_SECRET"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""

CRON_SECRET = _load_cron_secret()


def _mark_verified_in_mongo(email: str):
    """Directly mark a test user email_verified=True to bypass real verification."""
    try:
        from pymongo import MongoClient
        c = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=3000)
        c["ai_advocate_db"].users.update_one(
            {"email": email},
            {"$set": {"email_verified": True, "email_verified_at": datetime.now(timezone.utc).isoformat()}})
        c.close()
    except Exception as e:
        print(f"[warn] mongo verify-flag update failed: {e}")


def _signup(email=None):
    email = email or f"TEST_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "password": "Test12345!", "full_name": "Test User",
        "language": "en", "country": "GB"
    }, timeout=30)
    if r.status_code == 200:
        _mark_verified_in_mongo(email)
    return r, email


@pytest.fixture(scope="module")
def user_token():
    r, email = _signup()
    assert r.status_code == 200, f"signup failed: {r.status_code} {r.text}"
    data = r.json()
    return {"token": data["access_token"], "email": email, "user": data.get("user", {})}


@pytest.fixture
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token['token']}", "Content-Type": "application/json"}


# ============ 1. SIGNUP: no automatic trial ============
class TestSignupNoTrial:
    def test_signup_starts_on_free_no_trial(self):
        r, email = _signup()
        assert r.status_code == 200, r.text
        data = r.json()
        user = data.get("user") or {}
        # Verify no trial via /auth/me
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}, timeout=15)
        assert me.status_code == 200
        mu = me.json()
        assert mu.get("tier") in ("free", None), f"tier should be free, got {mu.get('tier')}"
        assert (mu.get("trial_days_remaining") or 0) == 0, f"trial_days_remaining should be 0, got {mu.get('trial_days_remaining')}"
        # subscription_status - optional field
        ss = mu.get("subscription_status")
        if ss is not None:
            assert ss == "free", f"subscription_status should be 'free', got {ss}"


# ============ 2. KEY DATES & REMINDERS ============
class TestKeyDates:
    def _create_case(self, auth_headers):
        r = requests.post(f"{API}/cases", headers=auth_headers, json={
            "name": "TEST_Case_KD", "category": "immigration", "description": "test"
        }, timeout=15)
        assert r.status_code in (200, 201), r.text
        return r.json()["id"] if "id" in r.json() else r.json().get("case", {}).get("id")

    def test_create_reminder_with_case_id_and_list(self, auth_headers):
        case_id = self._create_case(auth_headers)
        due = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = requests.post(f"{API}/reminders", headers=auth_headers, json={
            "case_id": case_id, "title": "TEST key date", "due_at": due, "kind": "deadline"
        }, timeout=15)
        assert r.status_code == 200, r.text
        rem = r.json()
        assert rem["case_id"] == case_id
        assert rem["status"] == "pending"
        assert "id" in rem

        # GET key-dates
        kd = requests.get(f"{API}/cases/{case_id}/key-dates", headers=auth_headers, timeout=15)
        assert kd.status_code == 200
        dates = kd.json()["key_dates"]
        assert any(d["id"] == rem["id"] for d in dates), "created reminder not in key_dates"

    def test_key_dates_404_for_foreign_case(self, auth_headers):
        # Create a case under second user, try accessing from first user
        r2, _ = _signup()
        token2 = r2.json()["access_token"]
        h2 = {"Authorization": f"Bearer {token2}", "Content-Type": "application/json"}
        rc = requests.post(f"{API}/cases", headers=h2, json={"name": "TEST_Foreign", "category": "immigration"}, timeout=15)
        assert rc.status_code in (200, 201)
        foreign_case_id = rc.json().get("id") or rc.json().get("case", {}).get("id")

        r = requests.get(f"{API}/cases/{foreign_case_id}/key-dates", headers=auth_headers, timeout=15)
        assert r.status_code == 404

    def test_reminder_resolves_case_from_session(self, auth_headers):
        case_id = self._create_case(auth_headers)
        # Create a conversation linked to the case
        session_id = f"TEST_sess_{uuid.uuid4().hex[:8]}"
        # Try linking via conversation endpoints — use a simpler path: direct Lex chat with case_id
        # Open a chat with linked_case_id by posting to /chat
        chat = requests.post(f"{API}/chat", headers=auth_headers, json={
            "message": "test linking", "session_id": session_id, "language": "en",
            "country": "GB", "linked_case_id": case_id
        }, timeout=60)
        # chat may succeed or hit quota; either way check conversation exists
        if chat.status_code != 200:
            pytest.skip(f"chat endpoint returned {chat.status_code}; skipping session link test")

        due = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
        r = requests.post(f"{API}/reminders", headers=auth_headers, json={
            "session_id": session_id, "title": "TEST session-linked", "due_at": due
        }, timeout=15)
        assert r.status_code == 200, r.text
        rem = r.json()
        assert rem.get("case_id") == case_id, f"session should resolve case_id; got {rem.get('case_id')}"

        kd = requests.get(f"{API}/cases/{case_id}/key-dates", headers=auth_headers, timeout=15)
        assert any(d["id"] == rem["id"] for d in kd.json()["key_dates"])


# ============ 3. CHECKLIST ============
class TestChecklist:
    def test_generate_and_toggle_checklist(self, auth_headers):
        # Create case + reminder
        rc = requests.post(f"{API}/cases", headers=auth_headers, json={"name": "TEST_Case_CL", "category": "immigration"}, timeout=15)
        case_id = rc.json().get("id") or rc.json().get("case", {}).get("id")
        due = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        rr = requests.post(f"{API}/reminders", headers=auth_headers, json={
            "case_id": case_id, "title": "ILR application submission", "due_at": due, "kind": "deadline",
            "description": "Submit ILR application"
        }, timeout=15)
        assert rr.status_code == 200
        rid = rr.json()["id"]

        # Generate checklist via real Claude call
        r = requests.post(f"{API}/reminders/{rid}/checklist", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text
        rem = r.json()
        cl = rem.get("checklist") or []
        assert 6 <= len(cl) <= 12, f"checklist length {len(cl)} out of range"
        for item in cl:
            assert "id" in item and "text" in item and item.get("done") is False

        # Toggle one item
        item_id = cl[0]["id"]
        pr = requests.patch(f"{API}/reminders/{rid}/checklist/{item_id}",
                            headers=auth_headers, json={"done": True}, timeout=15)
        assert pr.status_code == 200

        # Verify persisted via key-dates
        kd = requests.get(f"{API}/cases/{case_id}/key-dates", headers=auth_headers, timeout=15)
        reminders_list = kd.json()["key_dates"]
        this = next((x for x in reminders_list if x["id"] == rid), None)
        assert this and any(i["id"] == item_id and i["done"] is True for i in this.get("checklist", []))

        # 404 for unknown item
        bad = requests.patch(f"{API}/reminders/{rid}/checklist/zzzzzzzz",
                             headers=auth_headers, json={"done": True}, timeout=15)
        assert bad.status_code == 404


# ============ 4. PREFERENCES ============
class TestPreferences:
    def test_toggle_deadline_emails_persists(self, auth_headers):
        r = requests.patch(f"{API}/auth/preferences", headers=auth_headers, json={"deadline_emails_enabled": False}, timeout=15)
        assert r.status_code == 200, r.text
        me = requests.get(f"{API}/auth/me", headers=auth_headers, timeout=15).json()
        assert me.get("deadline_emails_enabled") is False
        # Restore
        requests.patch(f"{API}/auth/preferences", headers=auth_headers, json={"deadline_emails_enabled": True}, timeout=15)


# ============ 5. CRON DEADLINE REMINDERS ============
class TestCronDeadlineReminders:
    def test_cron_auth_401_without_token(self):
        r = requests.post(f"{API}/cron/deadline-reminders", json={}, timeout=15)
        assert r.status_code == 401

    def test_cron_auth_401_wrong_token(self):
        r = requests.post(f"{API}/cron/deadline-reminders",
                          headers={"Authorization": "Bearer wrong-token"}, json={}, timeout=15)
        assert r.status_code == 401

    def test_cron_queued_and_duplicate(self):
        if not CRON_SECRET:
            pytest.skip("WEBHOOK_CRON_SECRET not available")
        wid = f"TEST_run_{uuid.uuid4().hex[:10]}"
        headers = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": wid, "Content-Type": "application/json"}
        r = requests.post(f"{API}/cron/deadline-reminders", headers=headers, json={}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        assert r.json().get("queued") is True
        # Same webhook id again → duplicate
        r2 = requests.post(f"{API}/cron/deadline-reminders", headers=headers, json={}, timeout=15)
        assert r2.status_code == 200
        assert r2.json().get("duplicate") is True

    def test_cron_marks_emailed_days_correctly(self, auth_headers, user_token):
        """Create reminders with various due dates and verify emailed_days threshold logic.

        Uses Resend's documented testing address so sends succeed (example.com is rejected
        by Resend and would prevent emailed_days from being persisted)."""
        if not CRON_SECRET:
            pytest.skip("WEBHOOK_CRON_SECRET not available")

        # Create a dedicated user with a Resend-friendly test email
        test_email = f"delivered+TEST_{uuid.uuid4().hex[:8]}@resend.dev"
        r = requests.post(f"{API}/auth/signup", json={
            "email": test_email, "password": "Test12345!", "full_name": "Test",
            "language": "en", "country": "GB"}, timeout=30)
        if r.status_code != 200:
            pytest.skip(f"signup for resend test user failed: {r.text}")
        _mark_verified_in_mongo(test_email)
        tok = r.json()["access_token"]
        hh = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

        rc = requests.post(f"{API}/cases", headers=hh, json={"name": "TEST_Case_Cron", "category": "immigration"}, timeout=15)
        case_id = rc.json().get("id") or rc.json().get("case", {}).get("id")

        now = datetime.now(timezone.utc)
        # Reminder due in ~3 days (should get [7,3])
        due3 = (now + timedelta(days=3, hours=2)).isoformat()
        r3 = requests.post(f"{API}/reminders", headers=hh, json={
            "case_id": case_id, "title": "TEST due in 3", "due_at": due3
        }, timeout=15).json()
        # Reminder due in ~1 day (should get [7,3,1])
        due1 = (now + timedelta(days=1, hours=2)).isoformat()
        r1 = requests.post(f"{API}/reminders", headers=hh, json={
            "case_id": case_id, "title": "TEST due in 1", "due_at": due1
        }, timeout=15).json()
        # Reminder due in 10 days (should get nothing)
        due10 = (now + timedelta(days=10)).isoformat()
        r10 = requests.post(f"{API}/reminders", headers=hh, json={
            "case_id": case_id, "title": "TEST due in 10", "due_at": due10
        }, timeout=15).json()

        # Trigger cron with NEW webhook id
        wid = f"TEST_run_{uuid.uuid4().hex[:10]}"
        headers = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": wid, "Content-Type": "application/json"}
        r = requests.post(f"{API}/cron/deadline-reminders", headers=headers, json={}, timeout=15)
        assert r.status_code == 200

        # Allow background task to complete (real Resend send takes a few seconds per email)
        time.sleep(15)

        kd = requests.get(f"{API}/cases/{case_id}/key-dates", headers=hh, timeout=15).json()["key_dates"]
        by_id = {d["id"]: d for d in kd}

        ed3 = sorted(by_id.get(r3["id"], {}).get("emailed_days") or [])
        ed1 = sorted(by_id.get(r1["id"], {}).get("emailed_days") or [])
        ed10 = sorted(by_id.get(r10["id"], {}).get("emailed_days") or [])

        assert ed3 == [3, 7], f"due-in-3 expected [3,7], got {ed3}"
        assert ed1 == [1, 3, 7], f"due-in-1 expected [1,3,7], got {ed1}"
        assert ed10 == [], f"due-in-10 expected [], got {ed10}"

    def test_cron_skips_when_disabled(self, auth_headers, user_token):
        if not CRON_SECRET:
            pytest.skip("WEBHOOK_CRON_SECRET not available")
        # Disable deadline emails for this user
        requests.patch(f"{API}/auth/preferences", headers=auth_headers, json={"deadline_emails_enabled": False}, timeout=15)

        rc = requests.post(f"{API}/cases", headers=auth_headers, json={"name": "TEST_Case_Off", "category": "immigration"}, timeout=15)
        case_id = rc.json().get("id") or rc.json().get("case", {}).get("id")
        due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        rem = requests.post(f"{API}/reminders", headers=auth_headers, json={
            "case_id": case_id, "title": "TEST off-user", "due_at": due
        }, timeout=15).json()

        wid = f"TEST_run_{uuid.uuid4().hex[:10]}"
        headers = {"Authorization": f"Bearer {CRON_SECRET}", "X-Webhook-Id": wid, "Content-Type": "application/json"}
        requests.post(f"{API}/cron/deadline-reminders", headers=headers, json={}, timeout=15)
        time.sleep(6)

        kd = requests.get(f"{API}/cases/{case_id}/key-dates", headers=auth_headers, timeout=15).json()["key_dates"]
        this = next((d for d in kd if d["id"] == rem["id"]), {})
        assert not (this.get("emailed_days") or []), f"disabled user should not be emailed; got {this.get('emailed_days')}"

        # Restore
        requests.patch(f"{API}/auth/preferences", headers=auth_headers, json={"deadline_emails_enabled": True}, timeout=15)


# ============ 6. CONTENT CHECK ============
class TestContentCleanup:
    FORBIDDEN = ["app store", "google play", "play store", "7-day", "free trial"]

    def _strip_html_comments(self, s: str) -> str:
        import re
        return re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)

    @pytest.mark.parametrize("path", ["/terms.html", "/privacy.html", "/intro-pack.html"])
    def test_public_pages_no_banned(self, path):
        html = requests.get(f"{BASE_URL}{path}", timeout=15).text
        html = self._strip_html_comments(html)
        text = html.lower()
        found = [t for t in self.FORBIDDEN if t in text]
        # "14-day" cooling-off is permitted per spec (not in FORBIDDEN)
        assert not found, f"{path} contains banned terms: {found}"

    @pytest.mark.parametrize("lang", ["en", "es", "fr", "de", "it", "pt", "pl", "ro", "ar", "ur", "zh"])
    def test_in_app_terms_no_banned(self, lang):
        r = requests.get(f"{API}/legal/terms?language={lang}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        text = (d.get("content") or d.get("terms") or str(d)).lower()
        # Apple/Google payment wording + trial checks
        for banned in ["app store", "google play", "play store", "apple id", "7-day", "14-day free", "free trial"]:
            assert banned not in text, f"lang={lang} contains '{banned}'"
