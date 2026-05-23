"""
Iteration 19 tests:
  1. NEW: POST /api/lex/chat now returns `citations: [{n, title, url, source}]`
  2. NEW: GET  /api/lex/sessions/{session_id} surfaces persisted `citations` per row
  3. Regression: emergency contacts GET filters out malformed entries (name<2 or phone<7 digits)
  4. Regression: soft-delete + recycle-bin lifecycle for legal_files
  5. Regression: save-to-vault, timeline snapshot, empty-bin, case upload + case-item delete
  6. Smoke: /api/ returns {app:'AI Advocate', status:'ok'}

NOTE on Tavily budget: we only call /api/lex/chat ONCE with a substantive UK-law
question to verify citations come back. The second lex call is a tiny throwaway
that triggers persistence so we can read back via /lex/sessions/{id}.
"""
import os
import io
import uuid
import base64
import pytest
import requests


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL"):
                        url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
        except FileNotFoundError:
            pass
    assert url, "REACT_APP_BACKEND_URL not set"
    return url.rstrip("/")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@aiadvocate.co.uk"
ADMIN_PASS = "AdminLex2026!"


# ==================== Fixtures ====================
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def token(session):
    r = session.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=20,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ==================== Smoke: root health ====================
class TestSmoke:
    def test_api_root_returns_app_metadata(self, session):
        r = session.get(f"{API}/", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("app") == "AI Advocate"
        assert data.get("status") == "ok"


# ==================== NEW: citation pills on /lex/chat ====================
class TestLexCitations:
    """Single real Tavily-backed call to verify response shape."""

    SESSION_ID = None  # populated by the first test, reused by the second

    def test_lex_chat_returns_citations_array(self, session, auth):
        payload = {
            "message": "What is the notice period under section 21 Housing Act 1988?",
            "category": "Housing",
            "country": "GB",
            "language": "en-GB",
            "deep_think": False,
        }
        r = session.post(f"{API}/lex/chat", headers=auth, json=payload, timeout=180)
        # 402 would mean admin lost Pro — fail loudly because credentials say owner has unlimited.
        assert r.status_code == 200, f"lex/chat failed: {r.status_code} {r.text[:500]}"
        body = r.json()

        # Core response shape
        assert isinstance(body.get("response"), str) and len(body["response"]) > 20, \
            "response field missing or too short"
        assert "session_id" in body and body["session_id"], "session_id missing"
        assert "citations" in body, "citations key missing from /lex/chat response"
        cits = body["citations"]
        assert isinstance(cits, list), f"citations is not a list: {type(cits)}"

        # For a substantive legal question with Tavily configured we expect >=1 citation.
        # If Tavily is rate-limited or capped, citations may be []. We log + soft-skip
        # that scenario rather than fail the whole suite.
        if len(cits) == 0:
            pytest.skip("Tavily returned no citations (possibly rate-limited / capped). "
                        "Shape is correct (list present) but cannot validate item structure.")

        # Validate each citation has {n, title, url, source}
        for c in cits:
            assert isinstance(c, dict), f"citation not a dict: {c}"
            assert "n" in c and isinstance(c["n"], int), f"missing/invalid n: {c}"
            assert "title" in c and isinstance(c["title"], str), f"missing/invalid title: {c}"
            assert "url" in c and isinstance(c["url"], str), f"missing/invalid url: {c}"
            assert "source" in c and c["source"] in ("official", "web"), \
                f"invalid source: {c.get('source')}"

        # Numbering should start at 1 and increment
        ns = [c["n"] for c in cits]
        assert ns == sorted(ns), f"citation n values not sorted: {ns}"
        assert ns[0] == 1, f"citation numbering should start at 1, got {ns[0]}"

        # Stash session_id for the next test
        TestLexCitations.SESSION_ID = body["session_id"]

    def test_lex_sessions_returns_citations_field(self, session, auth):
        sid = TestLexCitations.SESSION_ID
        if not sid:
            pytest.skip("Prior /lex/chat test did not produce a session_id")
        r = session.get(f"{API}/lex/sessions/{sid}", headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        msgs = r.json()
        assert isinstance(msgs, list) and len(msgs) >= 1, f"no messages returned: {msgs}"
        # Every persisted row should now carry a citations field (may be empty list)
        for m in msgs:
            assert "citations" in m, f"row missing citations key: {list(m.keys())}"
            assert isinstance(m["citations"], list), \
                f"citations field is not a list: {type(m['citations'])}"


# ==================== Regression: emergency contacts filtering ====================
class TestEmergencyContactsFiltering:
    def test_get_filters_malformed_contacts(self, session, auth):
        """POST a mix of valid + malformed contacts. GET must only surface the valid one.
        The backend also filters on POST, so malformed entries should never persist."""
        payload = {
            "contacts": [
                # valid
                {"name": "TEST_Alice Smith", "relationship": "Lawyer",
                 "phone": "+447700900111", "is_lawyer": True, "include_in_sos": True},
                # malformed: name too short
                {"name": "A", "phone": "+447700900222"},
                # malformed: phone too short (only 4 digits)
                {"name": "TEST_Bob", "phone": "0123"},
                # malformed: blank phone
                {"name": "TEST_Carol", "phone": ""},
            ],
            "lawyer_standby_enabled": False,
            "lawyer_standby_radius_km": 25.0,
            "sos_message": "TEST iter19",
            "tracking_window_minutes": 60,
        }
        r = session.post(f"{API}/emergency/contacts", headers=auth, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        post_body = r.json()
        # Server-side filter on POST: only 1 valid contact should be persisted
        assert post_body.get("saved") is True
        assert post_body.get("contact_count") == 1, \
            f"POST should have filtered to 1, got {post_body.get('contact_count')}"

        # GET should also only return the valid contact
        r2 = session.get(f"{API}/emergency/contacts", headers=auth, timeout=20)
        assert r2.status_code == 200, r2.text
        get_body = r2.json()
        contacts = get_body.get("contacts", [])
        assert len(contacts) == 1, f"GET returned {len(contacts)} contacts, expected 1: {contacts}"
        c = contacts[0]
        assert c["name"] == "TEST_Alice Smith"
        # malformed names/phones must NOT appear
        for c in contacts:
            assert len(c.get("name", "")) >= 2
            import re
            digits = re.sub(r"\D", "", c.get("phone", "") or "")
            assert len(digits) >= 7


# ==================== Regression: soft-delete + recycle bin ====================
def _create_legal_file(session, auth):
    r = session.post(
        f"{API}/legal-letter",
        json={
            "letter_type": "Complaint",
            "your_name": "TEST_Iter19_User",
            "recipient": "TEST_Iter19_Landlord",
            "details": "TEST_Iter19 - regression check for soft-delete lifecycle.",
            "language": "en-GB",
        },
        headers=auth, timeout=120,
    )
    if r.status_code == 402:
        pytest.skip("Subscription required for legal-letter; admin should have it.")
    assert r.status_code == 200, f"create legal file failed: {r.status_code} {r.text}"
    lst = session.get(f"{API}/legal-files", headers=auth, timeout=20).json()
    assert isinstance(lst, list) and len(lst) > 0
    return lst[0]["id"]


class TestRecycleBinRegression:
    def test_legal_file_full_lifecycle(self, session, auth):
        file_id = _create_legal_file(session, auth)

        # Soft delete
        r = session.delete(f"{API}/legal-files/{file_id}", headers=auth, timeout=20)
        assert r.status_code == 200
        assert r.json().get("deleted") is True

        # In recycle bin
        bin_data = session.get(f"{API}/recycle-bin", headers=auth, timeout=20).json()
        ids = [i["id"] for i in bin_data["items"] if i.get("kind") == "legal_file"]
        assert file_id in ids

        # Restore
        r = session.post(f"{API}/recycle-bin/restore/legal_file/{file_id}", headers=auth, timeout=20)
        assert r.status_code == 200 and r.json().get("restored") is True

        # Delete again and purge
        session.delete(f"{API}/legal-files/{file_id}", headers=auth, timeout=20)
        r = session.delete(f"{API}/recycle-bin/legal_file/{file_id}", headers=auth, timeout=20)
        assert r.status_code == 200 and r.json().get("purged") is True

        # Purge again → 404
        r2 = session.delete(f"{API}/recycle-bin/legal_file/{file_id}", headers=auth, timeout=20)
        assert r2.status_code == 404

    def test_save_to_vault_creates_row(self, session, auth):
        file_id = _create_legal_file(session, auth)
        payload = {
            "file_id": file_id,
            "encrypted_content": base64.b64encode(b"iter19-ciphertext").decode(),
            "iv": base64.b64encode(b"iter19-iv").decode(),
            "label": "TEST_vault_iter19",
        }
        r = session.post(f"{API}/legal-files/{file_id}/save-to-vault",
                         headers=auth, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("saved") is True
        assert body.get("vault_item_id")
        # Cleanup
        session.delete(f"{API}/legal-files/{file_id}", headers=auth, timeout=20)
        session.delete(f"{API}/recycle-bin/legal_file/{file_id}", headers=auth, timeout=20)

    def test_empty_bin_endpoint(self, session, auth):
        # Add at least one item to bin
        try:
            file_id = _create_legal_file(session, auth)
            session.delete(f"{API}/legal-files/{file_id}", headers=auth, timeout=20)
        except Exception:
            pass
        r = session.delete(f"{API}/recycle-bin", headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "purged_count" in body
        assert isinstance(body["purged_count"], int)
        # bin should now be empty
        b2 = session.get(f"{API}/recycle-bin", headers=auth, timeout=20).json()
        assert b2["count"] == 0


# ==================== Regression: cases upload + case-item delete ====================
class TestCaseRegression:
    def test_upload_file_and_delete_item_decrements_count(self, session, auth):
        # Create case
        r = session.post(f"{API}/cases", headers=auth, json={
            "name": f"TEST_Iter19_{uuid.uuid4().hex[:6]}",
            "summary": "iter19 regression",
            "status": "open",
        }, timeout=20)
        assert r.status_code in (200, 201), r.text
        case_id = r.json().get("id") or r.json().get("case", {}).get("id")
        assert case_id

        # Upload 2 files
        headers_no_ct = {k: v for k, v in auth.items()}
        item_ids = []
        for i in range(2):
            files = {"file": (f"iter19_{i}.txt", f"hello {i}".encode(), "text/plain")}
            data = {"title": f"TEST_iter19_{i}"}
            ur = requests.post(f"{API}/cases/{case_id}/upload-file",
                               files=files, data=data, headers=headers_no_ct, timeout=30)
            assert ur.status_code == 200, ur.text
            item_ids.append(ur.json()["id"])

        c1 = session.get(f"{API}/cases/{case_id}", headers=auth, timeout=20).json()
        count_before = c1.get("items_count", 2)
        assert count_before >= 2

        # Delete one item
        d = session.delete(f"{API}/case-items/{item_ids[0]}", headers=auth, timeout=20)
        assert d.status_code == 200 and d.json().get("deleted") is True

        c2 = session.get(f"{API}/cases/{case_id}", headers=auth, timeout=20).json()
        assert c2.get("items_count") == count_before - 1, \
            f"items_count not decremented: {count_before} -> {c2.get('items_count')}"

        # Cleanup
        session.delete(f"{API}/cases/{case_id}", headers=auth, timeout=20)
        session.delete(f"{API}/recycle-bin/case/{case_id}", headers=auth, timeout=20)


# ==================== Regression: timeline snapshot + clear ====================
class TestTimelineRegression:
    def test_snapshot_creates_legal_file(self, session, auth):
        r = session.post(f"{API}/timeline/snapshot", headers=auth, timeout=45)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("saved") is True
        sid = body.get("snapshot_id")
        assert sid

        lst = session.get(f"{API}/legal-files", headers=auth, timeout=20).json()
        match = [f for f in lst if f.get("id") == sid]
        assert match, f"snapshot {sid} not in legal-files"
        assert match[0].get("type") == "timeline_snapshot"

        # cleanup
        session.delete(f"{API}/legal-files/{sid}", headers=auth, timeout=20)
        session.delete(f"{API}/recycle-bin/legal_file/{sid}", headers=auth, timeout=20)

    def test_clear_timeline_returns_counts(self, session, auth):
        r = session.delete(f"{API}/timeline", headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("cleared") is True
        assert isinstance(body.get("conversations"), int)
        assert isinstance(body.get("reminders"), int)
