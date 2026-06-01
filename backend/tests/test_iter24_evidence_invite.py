"""
Iter 24 — Evidence collection magic-link + Auto-witness from chat
Tests the new public evidence-invite flow end-to-end + regression on witness invite endpoint
(which the InviteWitnessFromChatPanel reuses).
"""

import os
import io
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: load from /app/frontend/.env
    try:
        with open("/app/frontend/.env") as _f:
            for _ln in _f:
                if _ln.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = _ln.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
API = f"{BASE_URL}/api"

TEST_EMAIL = "test@advocate.app"
TEST_PASSWORD = "Test12345!"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{API}/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"No token returned: {r.json()}"
    return tok


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(scope="module")
def case_id(headers):
    """Create a TEST_ case used across the evidence flow."""
    payload = {"title": f"TEST_evidence_{uuid.uuid4().hex[:6]}", "matter_type": "general", "country": "GB"}
    r = requests.post(f"{API}/cases", json=payload, headers=headers, timeout=20)
    assert r.status_code in (200, 201), f"Case create failed: {r.status_code} {r.text}"
    cid = r.json().get("id")
    assert cid
    return cid


# ---------- 1a: create invite ----------

class TestEvidenceInviteCreate:
    def test_create_invite_returns_magic_link(self, headers, case_id):
        body = {
            "label": "Please send us the dismissal letter",
            "instructions": "Upload your dismissal letter (PDF or photo). We need this for your case.",
        }
        r = requests.post(f"{API}/cases/{case_id}/evidence/invite", json=body, headers=headers, timeout=20)
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        data = r.json()
        for k in ("invite_id", "token", "magic_link", "expires_at", "email_sent"):
            assert k in data, f"missing key {k} in {data}"
        assert "/evidence/" in data["magic_link"]
        # share state with later tests via class attribute
        TestEvidenceInviteCreate.token = data["token"]
        TestEvidenceInviteCreate.invite_id = data["invite_id"]

    def test_invite_unknown_case_returns_404(self, headers):
        body = {"label": "Anything please", "instructions": "Send anything that may help."}
        r = requests.post(f"{API}/cases/does-not-exist/evidence/invite", json=body, headers=headers, timeout=15)
        assert r.status_code == 404


# ---------- 1b: public fetch ----------

class TestEvidencePublicFetch:
    def test_invalid_token_returns_404(self):
        r = requests.get(f"{API}/evidence/totally-bad-token-xxx", timeout=15)
        assert r.status_code == 404

    def test_valid_token_returns_ready(self):
        tok = TestEvidenceInviteCreate.token
        r = requests.get(f"{API}/evidence/{tok}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ready"
        assert d["label"]
        assert d["instructions"]
        assert "requester_name" in d
        assert d["max_uploads"] == 8
        assert d["upload_count"] == 0


# ---------- 1c: public upload ----------

class TestEvidencePublicUpload:
    def test_upload_success(self):
        tok = TestEvidenceInviteCreate.token
        files = {"file": ("dismissal.txt", b"This is the dismissal letter content. " * 4, "text/plain")}
        data = {"uploader_name": "Jane Witness", "description": "My dismissal letter from HR."}
        r = requests.post(f"{API}/evidence/{tok}/upload", files=files, data=data, timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        j = r.json()
        assert j["ok"] is True
        assert "evidence_file_id" in j
        assert isinstance(j["remaining_uploads"], int)
        TestEvidencePublicUpload.file_id = j["evidence_file_id"]

    def test_upload_uploader_name_too_short(self):
        tok = TestEvidenceInviteCreate.token
        files = {"file": ("x.txt", b"some content that is definitely longer than fifty bytes for sure ok ok", "text/plain")}
        r = requests.post(f"{API}/evidence/{tok}/upload",
                          files=files, data={"uploader_name": "A"}, timeout=15)
        assert r.status_code == 400

    def test_upload_bad_token_404(self):
        files = {"file": ("x.txt", b"some content that is definitely longer than fifty bytes for sure ok", "text/plain")}
        r = requests.post(f"{API}/evidence/bad-token-zzz/upload",
                          files=files, data={"uploader_name": "Jane Witness"}, timeout=15)
        assert r.status_code == 404

    def test_upload_oversize_returns_413(self):
        tok = TestEvidenceInviteCreate.token
        big = b"A" * (13 * 1024 * 1024)
        files = {"file": ("big.bin", big, "application/octet-stream")}
        r = requests.post(f"{API}/evidence/{tok}/upload",
                          files=files, data={"uploader_name": "Big Bob"}, timeout=60)
        assert r.status_code == 413


# ---------- 1d: owner list ----------

class TestEvidenceOwnerList:
    def test_owner_list_returns_files_and_invites(self, headers, case_id):
        r = requests.get(f"{API}/cases/{case_id}/evidence/invites", headers=headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "invites" in data and "files" in data
        assert len(data["invites"]) >= 1
        assert len(data["files"]) >= 1
        # file_b64 must be excluded
        for f in data["files"]:
            assert "file_b64" not in f, "file_b64 must not be in listing response"
            assert "filename" in f
            assert "uploader_name" in f


# ---------- 1e: download ----------

class TestEvidenceDownload:
    def test_owner_can_download_decrypted(self, headers, case_id):
        file_id = TestEvidencePublicUpload.file_id
        r = requests.get(f"{API}/cases/{case_id}/evidence/files/{file_id}/download",
                         headers=headers, timeout=20)
        assert r.status_code == 200
        # Should be the original text content
        assert b"dismissal letter" in r.content.lower()
        assert "text/plain" in (r.headers.get("Content-Type") or "")

    def test_cross_user_returns_404(self, case_id):
        # No auth header at all → should not 200
        file_id = TestEvidencePublicUpload.file_id
        r = requests.get(f"{API}/cases/{case_id}/evidence/files/{file_id}/download", timeout=15)
        assert r.status_code in (401, 403, 404)


# ---------- 1f: close invite ----------

class TestEvidenceClose:
    def test_close_invite(self, headers, case_id):
        invite_id = TestEvidenceInviteCreate.invite_id
        r = requests.post(f"{API}/cases/{case_id}/evidence/invites/{invite_id}/close",
                          headers=headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_upload_after_close_returns_403(self):
        tok = TestEvidenceInviteCreate.token
        files = {"file": ("after.txt", b"trying after close - should be rejected by API rules", "text/plain")}
        r = requests.post(f"{API}/evidence/{tok}/upload",
                          files=files, data={"uploader_name": "Late Larry"}, timeout=15)
        assert r.status_code == 403

    def test_public_fetch_shows_closed(self):
        tok = TestEvidenceInviteCreate.token
        r = requests.get(f"{API}/evidence/{tok}", timeout=15)
        assert r.status_code == 200
        assert r.json().get("status") == "closed"


# ---------- 2: witness invite endpoint (reused by InviteWitnessFromChatPanel) ----------

class TestWitnessInviteRegression:
    def test_witness_invite_endpoint_still_works(self, headers, case_id):
        body = {
            "witness_name": "John Witness",
            "context_for_witness": "What I discussed with Lex: I was dismissed. Lex's analysis: This may be unfair dismissal. Please write what you witnessed...",
        }
        r = requests.post(f"{API}/cases/{case_id}/witness/invite", json=body, headers=headers, timeout=20)
        assert r.status_code == 200, f"{r.status_code}: {r.text}"
        d = r.json()
        assert "magic_link" in d
        assert "/witness/" in d["magic_link"]
        assert "token" in d


# ---------- cleanup ----------

@pytest.fixture(scope="module", autouse=True)
def _cleanup(case_id, headers):
    yield
    try:
        requests.delete(f"{API}/cases/{case_id}", headers=headers, timeout=10)
    except Exception:
        pass
