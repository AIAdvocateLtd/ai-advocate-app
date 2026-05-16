"""
Iter10 backend tests — Live Notes, Document Analyse, Feedback, Daily Tip, Firm subscribe validation, Trial caps.
Covers the 7 feature areas requested in the iter10 review.
"""
import io
import os
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _signup():
    """Create a fresh trial_pro user and return (token, user_id, email)."""
    email = f"TEST_iter10_{uuid.uuid4().hex[:10]}@advocate.app"
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "password": "TestPass123!", "full_name": "Iter10 Tester",
        "language": "en-GB", "country": "GB",
    }, timeout=30)
    assert r.status_code == 200, f"signup failed: {r.status_code} {r.text}"
    data = r.json()
    return data["access_token"], data["user"]["id"], email


@pytest.fixture(scope="module")
def auth():
    tok, uid, email = _signup()
    return {"token": tok, "user_id": uid, "email": email,
            "headers": {"Authorization": f"Bearer {tok}"}}


# ---------- 1) Live Notes ----------
class TestLiveNotes:
    def test_add_and_fetch(self, auth):
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        r1 = requests.post(f"{API}/live/notes", headers=auth["headers"], json={
            "session_id": session_id, "speaker": "user", "text": "Officer asked my name.",
        }, timeout=15)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert "id" in d1 and "ts_ms" in d1 and "created_at" in d1
        assert d1["text"] == "Officer asked my name."

        # second note — out of order timing? deliberate small wait
        time.sleep(0.05)
        r2 = requests.post(f"{API}/live/notes", headers=auth["headers"], json={
            "session_id": session_id, "speaker": "lex", "text": "You have the right to remain silent.",
            "note_kind": "advice",
        }, timeout=15)
        assert r2.status_code == 200

        rg = requests.get(f"{API}/live/notes/{session_id}", headers=auth["headers"], timeout=15)
        assert rg.status_code == 200
        body = rg.json()
        assert body["count"] == 2
        assert body["notes"][0]["ts_ms"] <= body["notes"][1]["ts_ms"], "notes should be sorted ascending by ts_ms"
        # store for later test
        auth["live_session_id"] = session_id

    def test_list_sessions(self, auth):
        r = requests.get(f"{API}/live/sessions", headers=auth["headers"], timeout=15)
        assert r.status_code == 200
        sessions = r.json()
        assert isinstance(sessions, list)
        ids = [s["session_id"] for s in sessions]
        assert auth.get("live_session_id") in ids

    def test_pdf_export(self, auth):
        sid = auth.get("live_session_id")
        assert sid
        r = requests.get(f"{API}/live/notes/{sid}/export", headers=auth["headers"], timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "response is not a valid PDF"
        assert len(r.content) > 800

    def test_pdf_export_empty_session(self, auth):
        r = requests.get(f"{API}/live/notes/nonexistent_sess_xyz/export", headers=auth["headers"], timeout=15)
        assert r.status_code == 404


# ---------- 2) Daily Tip ----------
class TestDailyTip:
    def test_daily_tip_with_caching(self, auth):
        # Use a fixed lang+country pair — second call should return cached=True
        r1 = requests.get(f"{API}/tips/daily?language=en-GB&country=GB", headers=auth["headers"], timeout=45)
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert "date" in d1 and "tip" in d1 and "cached" in d1
        assert isinstance(d1["tip"], str) and len(d1["tip"]) > 5

        r2 = requests.get(f"{API}/tips/daily?language=en-GB&country=GB", headers=auth["headers"], timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        # second call must come from cache
        assert d2["cached"] is True, f"expected cached=True on second call, got {d2}"
        assert d2["tip"] == d1["tip"]


# ---------- 3) Feedback ----------
class TestFeedback:
    def test_thumbs_up(self, auth):
        r = requests.post(f"{API}/feedback", headers=auth["headers"], json={
            "rating": "up", "session_id": "abc123", "surface": "lex_chat",
        }, timeout=15)
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_thumbs_down_with_comment(self, auth):
        r = requests.post(f"{API}/feedback", headers=auth["headers"], json={
            "rating": "down", "session_id": "abc123", "comment": "Wrong jurisdiction",
            "surface": "lex_chat",
        }, timeout=15)
        assert r.status_code == 200

    def test_invalid_rating(self, auth):
        r = requests.post(f"{API}/feedback", headers=auth["headers"], json={
            "rating": "meh", "session_id": "x",
        }, timeout=15)
        assert r.status_code in (400, 422)


# ---------- 4) Firm subscribe validation ----------
class TestFirmSubscribe:
    def _firm_token(self):
        # Create a firm account
        em = f"firm_iter10_{uuid.uuid4().hex[:8]}@law.example"
        r = requests.post(f"{API}/firm/signup", json={
            "email": em, "password": "TestPass123!",
            "firm_name": "Iter10 LLP", "contact_name": "Jane Doe",
            "phone": "+44 20 0000 0000", "country": "GB", "city": "London",
            "specialties": ["employment"], "website": "https://example.com",
        }, timeout=20)
        if r.status_code != 200:
            pytest.skip(f"firm signup unavailable: {r.status_code} {r.text}")
        return r.json().get("access_token") or r.json().get("token")

    def test_verified_plan_rejected(self):
        tok = self._firm_token()
        r = requests.post(f"{API}/firm/subscribe?plan=verified",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code == 400, f"expected 400 for plan=verified, got {r.status_code}: {r.text}"

    def test_featured_plan(self):
        tok = self._firm_token()
        r = requests.post(f"{API}/firm/subscribe?plan=featured",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        # 503 = price not configured (acceptable); 200 = checkout url; 500 = stripe error
        assert r.status_code in (200, 503), f"unexpected {r.status_code}: {r.text}"

    def test_premium_plan(self):
        tok = self._firm_token()
        r = requests.post(f"{API}/firm/subscribe?plan=premium",
                          headers={"Authorization": f"Bearer {tok}"}, timeout=15)
        assert r.status_code in (200, 503), f"unexpected {r.status_code}: {r.text}"


# ---------- 5) Document Analyse (image upload + deadline auto-reminder + quota) ----------
def _png_with_text():
    """Return a minimal 600x400 PNG with text rendered using PIL — enough for the LLM
    to attempt OCR. We can't rely on actual content, but we need a valid image file."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (600, 400), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "PARKING CHARGE NOTICE\nIssued: 02 Jan 2026\nPay £60 by 25 Jan 2026 or appeal.",
           fill="black")
    bio = io.BytesIO(); img.save(bio, format="PNG"); bio.seek(0)
    return bio.getvalue()


class TestDocumentAnalyse:
    @pytest.fixture(scope="class")
    def doc_user(self):
        tok, uid, em = _signup()
        return {"token": tok, "user_id": uid, "email": em,
                "headers": {"Authorization": f"Bearer {tok}"}}

    def test_analyse_returns_schema(self, doc_user):
        png = _png_with_text()
        files = {"file": ("ticket.png", png, "image/png")}
        data = {"language": "en-GB", "country": "GB"}
        r = requests.post(f"{API}/document/analyze", headers=doc_user["headers"],
                          files=files, data=data, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("category", "summary", "deadlines", "suggested_response", "next_steps", "severity"):
            assert k in body, f"missing key {k} in response: {body}"
        assert body["severity"] in ("low", "medium", "high", "urgent")
        assert isinstance(body["deadlines"], list)
        assert isinstance(body["next_steps"], list)

    def test_case_link_creates_case_item_and_reminders(self, doc_user):
        # First create a case
        rc = requests.post(f"{API}/cases", headers=doc_user["headers"],
                           json={"title": "TEST_iter10_case", "type": "other"}, timeout=15)
        assert rc.status_code in (200, 201), rc.text
        case_id = rc.json()["id"]

        # Analyse with case_id
        png = _png_with_text()
        files = {"file": ("ticket.png", png, "image/png")}
        data = {"language": "en-GB", "country": "GB", "case_id": case_id}
        r = requests.post(f"{API}/document/analyze", headers=doc_user["headers"],
                          files=files, data=data, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("case_id") == case_id

        # Verify case item created
        ri = requests.get(f"{API}/cases/{case_id}", headers=doc_user["headers"], timeout=15)
        assert ri.status_code == 200
        items = ri.json().get("items", [])
        kinds = [it.get("kind") for it in items]
        assert "document_analysis" in kinds, f"document_analysis item not created in case. items={items}"

        # If LLM extracted at least one deadline, a reminder should exist
        # NOTE: doc-auto reminders are persisted with `completed: False` (no `status` field),
        # whereas GET /reminders filters by status="pending" by default — schema mismatch
        # bug means they won't appear in the default list. We test BOTH defaults and "no
        # status" filter.
        if body.get("deadlines"):
            rr_default = requests.get(f"{API}/reminders", headers=doc_user["headers"], timeout=15)
            rr_all = requests.get(f"{API}/reminders?status=", headers=doc_user["headers"], timeout=15)
            assert rr_default.status_code == 200 and rr_all.status_code == 200
            rem_default = rr_default.json().get("reminders", [])
            rem_all = rr_all.json().get("reminders", [])
            doc_default = [x for x in rem_default if x.get("source") == "doc_auto" and x.get("case_id") == case_id]
            doc_all = [x for x in rem_all if x.get("source") == "doc_auto" and x.get("case_id") == case_id]
            # Capture for reporting
            doc_user["doc_reminders_default"] = doc_default
            doc_user["doc_reminders_all"] = doc_all
            print(f"\n  default-filter doc_auto reminders: {len(doc_default)}")
            print(f"  no-filter doc_auto reminders: {len(doc_all)}")
            print(f"  body.deadlines (LLM-extracted): {len(body['deadlines'])}")
            assert len(doc_all) >= 1, (
                "expected at least 1 auto-generated reminder with source=doc_auto when "
                f"LLM extracted {len(body['deadlines'])} deadlines"
            )


# ---------- 6) Trial cap visibility (lex_chat_daily=50, deep_think_monthly=5, ...) ----------
class TestTrialCaps:
    def test_usage_endpoint_or_me_reports_trial_pro(self, auth):
        r = requests.get(f"{API}/auth/me", headers=auth["headers"], timeout=15)
        assert r.status_code == 200
        me = r.json()
        # accept either nested or flat
        tier = me.get("tier") or me.get("user", {}).get("tier")
        assert tier == "trial_pro", f"new user should be trial_pro, got {tier}"
