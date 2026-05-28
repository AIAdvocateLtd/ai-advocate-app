"""
Pre-launch smoke test for AI Advocate.
Covers the 16 critical paths flagged by the user before clicking Deploy.
Runs against the LIVE backend at REACT_APP_BACKEND_URL.

This is a SMOKE test, not a regression run. We assert:
- 2xx where it should be 200
- response shape (not full semantics)
- non-empty bodies for LLM endpoints
- PDF magic bytes for PDF endpoints

If any of these fail, the deploy should be paused.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@aiadvocate.co.uk"
ADMIN_PW = "AdminLex2026!"


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def demo_ctx(http):
    r = http.post(f"{API}/auth/demo", json={})
    assert r.status_code == 200, f"demo login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    return {"token": data["access_token"], "user": data["user"]}


@pytest.fixture(scope="module")
def admin_ctx(http):
    r = http.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    return {"token": data["access_token"], "user": data["user"]}


def _auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# 1) Demo mode
class TestDemoMode:
    def test_demo_returns_token_and_is_demo(self, demo_ctx):
        assert demo_ctx["token"]
        assert demo_ctx["user"].get("is_demo") is True

    def test_demo_seeded_case(self, http, demo_ctx):
        r = http.get(f"{API}/cases", headers=_auth(demo_ctx["token"]))
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        cases = body if isinstance(body, list) else body.get("cases", [])
        assert len(cases) >= 1
        sarah = next((c for c in cases if "sarah" in ((c.get("name") or c.get("title") or "").lower())), None)
        assert sarah is not None, f"seeded Sarah case not found in {[(c.get('name') or c.get('title')) for c in cases]}"
        # at least 3 items
        assert sarah.get("items_count", 0) >= 3, f"expected 3+ items, got {sarah.get('items_count')}"


# 2) Signup flow
class TestSignup:
    def test_signup_returns_token_no_demo_flag(self, http):
        email = f"TEST_smoke_{uuid.uuid4().hex[:10]}@advocate.app"
        r = http.post(f"{API}/auth/signup", json={
            "email": email, "password": "Test12345!", "full_name": "Smoke Test"
        })
        assert r.status_code == 200, r.text[:300]
        token = r.json()["access_token"]
        me = http.get(f"{API}/auth/me", headers=_auth(token))
        assert me.status_code == 200
        body = me.json()
        assert body.get("email") == email
        assert body.get("is_demo") in (False, None)


# 3) Admin login
class TestAdminLogin:
    def test_admin_is_owner_flag(self, admin_ctx):
        u = admin_ctx["user"]
        assert u.get("is_owner") is True, f"expected is_owner=true, got {u}"


# 4) Lex chat
class TestLexChat:
    def test_lex_chat_returns_non_empty(self, http, demo_ctx):
        r = http.post(
            f"{API}/lex/chat",
            headers=_auth(demo_ctx["token"]),
            json={"message": "Can my employer dismiss me without notice in the UK?"},
            timeout=60,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        body = data.get("response") or data.get("answer") or data.get("message") or ""
        assert isinstance(body, str) and len(body.strip()) > 20, f"empty/short lex body: {data}"


# 5) Emergency contacts
class TestEmergency:
    def test_save_and_get_contacts(self, http, demo_ctx):
        payload = {
            "contacts": [{"name": "Jane Doe", "phone": "+447700900123", "relationship": "friend"}],
            "lawyer_standby_enabled": False,
            "lawyer_standby_radius_km": 25.0,
            "sos_message": "I may be in trouble — please call me.",
            "tracking_window_minutes": 60,
        }
        r = http.post(f"{API}/emergency/contacts", headers=_auth(demo_ctx["token"]), json=payload)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("saved") is True
        g = http.get(f"{API}/emergency/contacts", headers=_auth(demo_ctx["token"]))
        assert g.status_code == 200
        body = g.json()
        contacts = body.get("contacts") if isinstance(body, dict) else body
        assert contacts and any("Jane" in (c.get("name") or "") for c in contacts)

    # 6) Watch token
    def test_watch_token(self, http, demo_ctx):
        r = http.post(f"{API}/emergency/watch-token", headers=_auth(demo_ctx["token"]))
        assert r.status_code == 200
        assert isinstance(r.json().get("watch_token"), str)
        assert len(r.json()["watch_token"]) > 8


# 8) feedback suggest
class TestFeedbackSuggest:
    def test_feedback_suggest_creates_record(self, http, demo_ctx, admin_ctx):
        text = f"TEST_smoke please add Scottish family law guidance {uuid.uuid4().hex[:6]}"
        r = http.post(f"{API}/feedback/suggest", headers=_auth(demo_ctx["token"]),
                      json={"text": text, "category_hint": "family"})
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("received") is True
        time.sleep(0.5)
        # 9) admin sees it
        s = http.get(f"{API}/admin/suggestions", headers=_auth(admin_ctx["token"]))
        assert s.status_code == 200
        data = s.json()
        rows = data.get("rows") or data.get("items") or data.get("suggestions") or []
        assert "open_count" in data or "rows" in data or "items" in data, f"unexpected shape: {data}"
        match = next((r2 for r2 in rows if text in (r2.get("text") or "")), None)
        assert match is not None, "submitted suggestion not visible in admin inbox"
        sid = match.get("id")
        # PATCH resolved
        p = http.patch(f"{API}/admin/suggestions/{sid}",
                       headers=_auth(admin_ctx["token"]), json={"resolved": True})
        assert p.status_code in (200, 204), p.text[:200]
        # DELETE
        d = http.delete(f"{API}/admin/suggestions/{sid}", headers=_auth(admin_ctx["token"]))
        assert d.status_code in (200, 204), d.text[:200]


# 10) Solicitor brief PDF
class TestSolicitorBrief:
    def test_solicitor_brief_pdf(self, http, admin_ctx):
        r = http.get(f"{API}/admin/solicitor-brief.pdf", headers=_auth(admin_ctx["token"]))
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.content[:5] == b"%PDF-", f"not a PDF: {r.content[:20]}"


# 11) Auth 401 interceptor
class TestAuthInterceptor:
    def test_invalid_token_returns_401(self, http):
        r = http.get(f"{API}/auth/me", headers={"Authorization": "Bearer notarealtoken"})
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# 12) Stripe top-up checkout
class TestStripeTopup:
    def test_topup_checkout_returns_url_or_503(self, http, demo_ctx):
        r = http.post(f"{API}/topups/checkout",
                      headers=_auth(demo_ctx["token"]),
                      json={"pack_id": "day_pass"})
        # 200 with url if Stripe price configured; 503 with config hint otherwise (acceptable).
        # 5xx other than 503 = blocker.
        assert r.status_code in (200, 402, 503), f"unexpected: {r.status_code} {r.text[:300]}"
        if r.status_code == 200:
            data = r.json()
            url = data.get("url") or data.get("checkout_url")
            assert isinstance(url, str) and url.startswith("http"), data


# 13) Case timeline
class TestCaseTimeline:
    def test_timeline_returns_feed(self, http, demo_ctx):
        body = http.get(f"{API}/cases", headers=_auth(demo_ctx["token"])).json()
        cases = body if isinstance(body, list) else body.get("cases", [])
        cid = cases[0]["id"]
        r = http.get(f"{API}/cases/{cid}/timeline", headers=_auth(demo_ctx["token"]))
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # accept any shape; just confirm 200 + structured response
        assert data is not None

    # 14) PDF export
    def test_timeline_pdf(self, http, demo_ctx):
        body = http.get(f"{API}/cases", headers=_auth(demo_ctx["token"])).json()
        cases = body if isinstance(body, list) else body.get("cases", [])
        cid = cases[0]["id"]
        r = http.get(f"{API}/cases/{cid}/export-pdf", headers=_auth(demo_ctx["token"]))
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        assert r.content[:5] == b"%PDF-"


# 15) Waitlist
class TestWaitlist:
    def test_waitlist_join_and_admin_export(self, http, admin_ctx):
        email = f"TEST_wl_{uuid.uuid4().hex[:8]}@advocate.app"
        r = http.post(f"{API}/waitlist/join",
                      json={"email": email, "full_name": "Smoke WL", "country": "GB", "source": "smoke"})
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("ok") is True
        # admin list
        adm = http.get(f"{API}/admin/waitlist", headers=_auth(admin_ctx["token"]))
        assert adm.status_code == 200, adm.text[:200]
        rows = adm.json().get("rows", [])
        assert any(row.get("email") == email for row in rows), f"{email} not found in admin waitlist"


# 16) /terms.html and /privacy.html
class TestPolicyPages:
    def test_terms_v14(self):
        r = requests.get(f"{BASE_URL}/terms.html", timeout=20)
        assert r.status_code == 200
        assert "v1.4" in r.text, "terms.html missing v1.4 marker"

    def test_privacy_v11(self):
        r = requests.get(f"{BASE_URL}/privacy.html", timeout=20)
        assert r.status_code == 200
        assert "v1.1" in r.text, "privacy.html missing v1.1 marker"
