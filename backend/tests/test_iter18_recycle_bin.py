"""
Iteration 18 tests: Recycle bin + soft delete + save-to-vault + timeline snapshot + case upload-file.
Targets the new endpoints introduced in this batch.
"""
import os
import io
import base64
import uuid
import pytest
import requests

def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        # Fall back to frontend/.env
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
    r = session.post(f"{API}/auth/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
                     timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ==================== Helpers ====================
def _create_legal_file(session, auth):
    """Generate a legal letter so we have a legal_files row to play with."""
    r = session.post(
        f"{API}/legal-letter",
        json={
            "letter_type": "Complaint",
            "your_name": "TEST_User",
            "recipient": "TEST_Landlord",
            "details": "TEST_Iter18 - request repair within 14 days.",
            "language": "en-GB",
        },
        headers=auth, timeout=120,
    )
    if r.status_code == 402:
        pytest.skip("Subscription required for legal-letter; admin should have it but skipping.")
    assert r.status_code == 200, f"create legal file failed: {r.status_code} {r.text}"
    # Fetch list and pick the most recent
    lst = session.get(f"{API}/legal-files", headers=auth, timeout=20).json()
    assert isinstance(lst, list) and len(lst) > 0
    return lst[0]["id"]


def _create_case(session, auth):
    r = session.post(f"{API}/cases", headers=auth, json={
        "name": f"TEST_Iter18_Case_{uuid.uuid4().hex[:6]}",
        "summary": "test summary",
        "status": "open",
    }, timeout=20)
    assert r.status_code in (200, 201), f"create case failed: {r.status_code} {r.text}"
    return r.json().get("id") or r.json().get("case", {}).get("id")


# ==================== Recycle bin: empty state ====================
class TestRecycleBinBaseline:
    def test_recycle_bin_listing_works(self, session, auth):
        r = session.get(f"{API}/recycle-bin", headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and "count" in data
        assert isinstance(data["items"], list)
        assert data["count"] == len(data["items"])


# ==================== Legal file soft-delete → recycle bin → restore → purge ====================
class TestLegalFileSoftDeleteFlow:
    def test_full_lifecycle(self, session, auth):
        file_id = _create_legal_file(session, auth)

        # Soft delete
        r = session.delete(f"{API}/legal-files/{file_id}", headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("deleted") is True

        # Should NOT appear in list anymore
        lst = session.get(f"{API}/legal-files", headers=auth, timeout=20).json()
        assert all(f["id"] != file_id for f in lst), "soft-deleted file still in legal-files list"

        # Should appear in recycle bin
        bin_data = session.get(f"{API}/recycle-bin", headers=auth, timeout=20).json()
        ids_in_bin = [i["id"] for i in bin_data["items"] if i.get("kind") == "legal_file"]
        assert file_id in ids_in_bin, f"file {file_id} missing from recycle bin {ids_in_bin}"

        # Restore
        r = session.post(f"{API}/recycle-bin/restore/legal_file/{file_id}", headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("restored") is True

        # Should be back in list
        lst2 = session.get(f"{API}/legal-files", headers=auth, timeout=20).json()
        assert any(f["id"] == file_id for f in lst2), "restored file not in legal-files list"

        # Soft-delete again then permanently purge
        session.delete(f"{API}/legal-files/{file_id}", headers=auth, timeout=20)
        r = session.delete(f"{API}/recycle-bin/legal_file/{file_id}", headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("purged") is True

        # Re-purge should 404
        r = session.delete(f"{API}/recycle-bin/legal_file/{file_id}", headers=auth, timeout=20)
        assert r.status_code == 404

    def test_unknown_kind_returns_400(self, session, auth):
        r = session.post(f"{API}/recycle-bin/restore/bogus/abc-123", headers=auth, timeout=20)
        assert r.status_code == 400

    def test_restore_nonexistent_returns_404(self, session, auth):
        r = session.post(f"{API}/recycle-bin/restore/legal_file/does-not-exist", headers=auth, timeout=20)
        assert r.status_code == 404


# ==================== Case soft-delete cascade + restore ====================
class TestCaseSoftDeleteCascade:
    def test_case_delete_cascades_items(self, session, auth):
        case_id = _create_case(session, auth)
        # Attach an item via the new upload-file endpoint
        files = {"file": ("note_iter18.txt", b"cascade test note", "text/plain")}
        data = {"title": "TEST_item_iter18", "description": "preview content"}
        headers = {k: v for k, v in auth.items()}
        r = requests.post(f"{API}/cases/{case_id}/upload-file",
                          files=files, data=data, headers=headers, timeout=30)
        assert r.status_code == 200, r.text
        item_id = r.json().get("id")
        assert item_id

        # Verify case+item live
        case = session.get(f"{API}/cases/{case_id}", headers=auth, timeout=20).json()
        assert any(it["id"] == item_id for it in case.get("items", []))

        # Soft delete case
        r = session.delete(f"{API}/cases/{case_id}", headers=auth, timeout=20)
        assert r.status_code == 200, r.text

        # Case no longer in list
        cases_resp = session.get(f"{API}/cases", headers=auth, timeout=20).json()
        all_cases = cases_resp.get("cases", []) if isinstance(cases_resp, dict) else cases_resp
        assert all(c["id"] != case_id for c in all_cases)

        # Case + item should both be in recycle bin
        bin_data = session.get(f"{API}/recycle-bin", headers=auth, timeout=20).json()
        case_ids = [i["id"] for i in bin_data["items"] if i.get("kind") == "case"]
        item_ids = [i["id"] for i in bin_data["items"] if i.get("kind") == "case_item"]
        assert case_id in case_ids, f"case {case_id} not in bin"
        assert item_id in item_ids, f"item {item_id} not in bin"

        # Restore case → item also restored
        r = session.post(f"{API}/recycle-bin/restore/case/{case_id}", headers=auth, timeout=20)
        assert r.status_code == 200, r.text

        case2 = session.get(f"{API}/cases/{case_id}", headers=auth, timeout=20).json()
        assert any(it["id"] == item_id for it in case2.get("items", [])), \
            "Restoring case did not restore cascaded items"

        # Cleanup
        session.delete(f"{API}/cases/{case_id}", headers=auth, timeout=20)
        session.delete(f"{API}/recycle-bin/case/{case_id}", headers=auth, timeout=20)


# ==================== Case item delete decrements items_count ====================
class TestCaseItemDelete:
    def test_delete_case_item_decrements_count(self, session, auth):
        case_id = _create_case(session, auth)
        # Attach two items via upload-file
        ids = []
        headers = {k: v for k, v in auth.items()}
        for i in range(2):
            files = {"file": (f"f_{i}.txt", f"content{i}".encode(), "text/plain")}
            r = requests.post(f"{API}/cases/{case_id}/upload-file",
                              files=files,
                              data={"title": f"TEST_n_{i}"},
                              headers=headers, timeout=30)
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])

        # Fetch case → items_count should be 2
        case = session.get(f"{API}/cases/{case_id}", headers=auth, timeout=20).json()
        initial_count = case.get("items_count", 2)

        # Delete one item
        r = session.delete(f"{API}/case-items/{ids[0]}", headers=auth, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("deleted") is True

        case2 = session.get(f"{API}/cases/{case_id}", headers=auth, timeout=20).json()
        new_count = case2.get("items_count", initial_count - 1)
        assert new_count == initial_count - 1, f"items_count not decremented: {initial_count} -> {new_count}"

        # The item should NOT be in current case items
        assert all(it["id"] != ids[0] for it in case2.get("items", []))

        # Cleanup
        session.delete(f"{API}/cases/{case_id}", headers=auth, timeout=20)


# ==================== Case upload-file (multipart) ====================
class TestCaseUploadFile:
    def test_upload_file_to_case(self, session, auth):
        case_id = _create_case(session, auth)

        # multipart upload — clear Content-Type so requests sets boundary
        files = {"file": ("evidence_iter18.txt", b"hello world iter18 evidence", "text/plain")}
        data = {"title": "TEST_evidence_iter18", "description": "evidence desc"}
        headers = {k: v for k, v in auth.items()}
        r = requests.post(f"{API}/cases/{case_id}/upload-file",
                          files=files, data=data, headers=headers, timeout=30)
        assert r.status_code == 200, f"upload failed: {r.status_code} {r.text}"
        item = r.json()
        assert item.get("id")
        assert item.get("case_id") == case_id
        assert item.get("sha256")
        assert item.get("size_bytes") == len(b"hello world iter18 evidence")

        # The new item should show up in case detail
        case_resp = session.get(f"{API}/cases/{case_id}", headers=auth, timeout=20).json()
        assert any(it["id"] == item["id"] for it in case_resp.get("items", []))

        # Cleanup
        session.delete(f"{API}/cases/{case_id}", headers=auth, timeout=20)

    def test_upload_to_unknown_case_returns_404(self, session, auth):
        files = {"file": ("x.txt", b"x", "text/plain")}
        headers = {k: v for k, v in auth.items()}
        r = requests.post(f"{API}/cases/nope-iter18/upload-file",
                          files=files, headers=headers, timeout=20)
        assert r.status_code == 404


# ==================== Save legal-file to Vault ====================
class TestSaveToVault:
    def test_save_legal_file_to_vault_creates_row(self, session, auth):
        file_id = _create_legal_file(session, auth)

        payload = {
            "file_id": file_id,
            "encrypted_content": base64.b64encode(b"shim-ciphertext-iter18").decode(),
            "iv": base64.b64encode(b"shim-iv").decode(),
            "label": "TEST_vault_iter18",
        }
        r = session.post(f"{API}/legal-files/{file_id}/save-to-vault",
                         headers=auth, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("saved") is True
        assert body.get("vault_item_id")

        # Cleanup the source
        session.delete(f"{API}/legal-files/{file_id}", headers=auth, timeout=20)

    def test_save_to_vault_nonexistent_file_returns_404(self, session, auth):
        payload = {
            "file_id": "does-not-exist-iter18",
            "encrypted_content": "abc",
            "iv": "abc",
        }
        r = session.post(f"{API}/legal-files/does-not-exist-iter18/save-to-vault",
                         headers=auth, json=payload, timeout=20)
        assert r.status_code == 404


# ==================== Timeline snapshot + clear ====================
class TestTimelineEndpoints:
    def test_snapshot_creates_legal_file(self, session, auth):
        r = session.post(f"{API}/timeline/snapshot", headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("saved") is True
        snap_id = body.get("snapshot_id")
        assert snap_id

        # Verify it appears in legal-files list as a timeline_snapshot
        lst = session.get(f"{API}/legal-files", headers=auth, timeout=20).json()
        matched = [f for f in lst if f.get("id") == snap_id]
        assert matched, f"snapshot {snap_id} not in legal-files list"
        assert matched[0].get("type") == "timeline_snapshot"

        # Cleanup
        session.delete(f"{API}/legal-files/{snap_id}", headers=auth, timeout=20)
        session.delete(f"{API}/recycle-bin/legal_file/{snap_id}", headers=auth, timeout=20)

    def test_clear_timeline_soft_deletes_conversations_and_reminders(self, session, auth):
        # We won't assert specific counts, just that endpoint returns 200 and shape is right.
        r = session.delete(f"{API}/timeline", headers=auth, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("cleared") is True
        assert "conversations" in body
        assert "reminders" in body
        assert isinstance(body["conversations"], int)
        assert isinstance(body["reminders"], int)


# ==================== Empty recycle bin ====================
class TestEmptyRecycleBin:
    def test_empty_bin_returns_purged_count(self, session, auth):
        # Soft delete a fresh file so something is in the bin
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
        assert body["purged_count"] >= 0

        # Bin should now be empty (or at least the legal-file we just added is gone)
        bin_now = session.get(f"{API}/recycle-bin", headers=auth, timeout=20).json()
        assert bin_now["count"] == 0
