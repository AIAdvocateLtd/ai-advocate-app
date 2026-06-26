"""
Timeline per-item delete bug verification (2026-06).

Bug: GET /api/timeline returned soft-deleted chats because the aggregate
filtered only by user_id (not by deleted_at). When the user clicked the
trash icon on a stale row, DELETE returned 404 'Chat not found or already
deleted'. The fix:
  - /api/timeline conversations aggregate now filters deleted_at.
  - /api/lex/sessions mirrors the same filter.
  - DELETE /api/timeline/item is idempotent: returns 200 with rows: 0 when
    the row is already soft-deleted, only 404 when nothing exists at all.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-law-guide-1.preview.emergentagent.com").rstrip("/")
EMAIL = "test@advocate.app"
PASSWORD = "Test12345!"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data, f"no token in response: {data}"
    return data["access_token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def seed_chat(auth):
    """Make sure the test user has at least one chat in /api/timeline.
    Tries POST /api/lex/ask (the primary chat endpoint) to seed."""
    sid = f"test-sess-{uuid.uuid4().hex[:10]}"
    try:
        r = requests.post(
            f"{BASE_URL}/api/lex/ask",
            json={"message": "TEST seed for delete bug", "session_id": sid, "category": "ask_lex"},
            headers=auth,
            timeout=60,
        )
        # We don't strictly require 200 — if the endpoint name has changed
        # the user might already have chats from earlier runs.
        print(f"seed POST /api/lex/ask -> {r.status_code}")
    except Exception as e:
        print(f"seed attempt failed (non-fatal): {e}")
    return sid


# ---------- tests ----------

def _get_timeline(auth):
    r = requests.get(f"{BASE_URL}/api/timeline", headers=auth, timeout=30)
    assert r.status_code == 200, f"GET /api/timeline failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    assert "items" in body
    return body


class TestTimelineDeleteBug:
    """Primary bug fix verification — chat delete -> disappears from list."""

    def test_a_login_succeeds(self, token):
        assert isinstance(token, str) and len(token) > 10

    def test_b_timeline_returns_items(self, auth, seed_chat):
        tl = _get_timeline(auth)
        items = tl["items"]
        assert isinstance(items, list)
        print(f"timeline returned {len(items)} items, total_chats={tl.get('stats', {}).get('total_chats')}")
        chats = [i for i in items if i.get("kind") == "chat"]
        if len(chats) == 0:
            pytest.skip("No chats in timeline for test user — cannot exercise chat delete")

    def test_c_delete_chat_removes_from_timeline(self, auth):
        """PRIMARY BUG: deleted session_id must NOT reappear in subsequent GET."""
        tl_before = _get_timeline(auth)
        chats = [i for i in tl_before["items"] if i.get("kind") == "chat"]
        if not chats:
            pytest.skip("no chat to delete")
        target_id = chats[0]["id"]
        print(f"deleting chat session_id={target_id}")

        # delete
        r = requests.delete(
            f"{BASE_URL}/api/timeline/item",
            params={"kind": "chat", "item_id": target_id},
            headers=auth,
            timeout=20,
        )
        assert r.status_code == 200, f"delete failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("deleted") is True
        assert body.get("kind") == "chat"
        # rows should be >= 1 on first delete (the conversations rows soft-deleted)
        assert body.get("rows", 0) >= 1, f"expected rows>=1 on fresh delete, got {body}"

        # confirm it's gone from /api/timeline
        tl_after = _get_timeline(auth)
        remaining_ids = [i["id"] for i in tl_after["items"] if i.get("kind") == "chat"]
        assert target_id not in remaining_ids, (
            f"BUG: deleted chat {target_id} still in timeline. remaining={remaining_ids[:10]}"
        )
        print(f"OK: {target_id} removed; timeline now has {len(remaining_ids)} chats")
        # stash for next test
        pytest._deleted_chat_id = target_id

    def test_d_lex_sessions_also_filters_deleted(self, auth):
        """Same deleted session_id must not appear in GET /api/lex/sessions."""
        target_id = getattr(pytest, "_deleted_chat_id", None)
        if not target_id:
            pytest.skip("previous chat-delete test was skipped/failed")
        r = requests.get(f"{BASE_URL}/api/lex/sessions", headers=auth, timeout=20)
        assert r.status_code == 200, f"lex/sessions failed: {r.status_code} {r.text}"
        data = r.json()
        # response could be {sessions:[...]} or a bare list
        sess = data.get("sessions", data) if isinstance(data, dict) else data
        ids = [s.get("session_id") for s in sess if isinstance(s, dict)]
        assert target_id not in ids, f"BUG: {target_id} still in /api/lex/sessions: {ids[:10]}"

    def test_e_idempotent_second_delete_returns_200(self, auth):
        """Second delete of same already-soft-deleted session must be 200, NOT 404."""
        target_id = getattr(pytest, "_deleted_chat_id", None)
        if not target_id:
            pytest.skip("no previously-deleted id available")
        r = requests.delete(
            f"{BASE_URL}/api/timeline/item",
            params={"kind": "chat", "item_id": target_id},
            headers=auth,
            timeout=20,
        )
        assert r.status_code == 200, (
            f"idempotency BROKEN: second delete returned {r.status_code} {r.text}"
        )
        body = r.json()
        assert body.get("deleted") is True
        assert body.get("rows", 1) == 0, f"expected rows:0 on idempotent re-delete, got {body}"

    def test_f_genuinely_missing_chat_still_404(self, auth):
        bogus = f"this-id-does-not-exist-{uuid.uuid4().hex}"
        r = requests.delete(
            f"{BASE_URL}/api/timeline/item",
            params={"kind": "chat", "item_id": bogus},
            headers=auth,
            timeout=20,
        )
        assert r.status_code == 404, f"expected 404 for unknown id, got {r.status_code} {r.text}"
        assert "not found" in r.text.lower()

    def test_g_validation_bogus_kind(self, auth):
        r = requests.delete(
            f"{BASE_URL}/api/timeline/item",
            params={"kind": "bogus", "item_id": "x"},
            headers=auth,
            timeout=20,
        )
        assert r.status_code == 400, f"expected 400 for bad kind, got {r.status_code}"
        assert "unsupported kind" in r.text.lower()

    def test_h_validation_empty_item_id(self, auth):
        r = requests.delete(
            f"{BASE_URL}/api/timeline/item",
            params={"kind": "chat", "item_id": ""},
            headers=auth,
            timeout=20,
        )
        # FastAPI may treat empty string differently; accept 400 or 422.
        assert r.status_code in (400, 422), f"expected 400/422 for empty id, got {r.status_code} {r.text}"


class TestTimelineDeadlineDelete:
    """Deadline per-item delete end-to-end."""

    def test_create_reminder_and_delete(self, auth):
        # try to create a reminder via POST /api/reminders
        payload = {"title": "TEST_delete_me", "due_at": "2099-12-31T12:00:00Z", "category": "deadline"}
        r = requests.post(f"{BASE_URL}/api/reminders", json=payload, headers=auth, timeout=20)
        if r.status_code not in (200, 201):
            # fallback: look in existing timeline
            tl = _get_timeline(auth)
            deadlines = [i for i in tl["items"] if i.get("kind") == "deadline"]
            if not deadlines:
                pytest.skip(f"cannot create reminder (status {r.status_code}) and none exist in timeline")
            rid = deadlines[0]["id"]
        else:
            body = r.json()
            rid = body.get("id") or body.get("reminder", {}).get("id")
            assert rid, f"no reminder id in response: {body}"

        # delete
        rd = requests.delete(
            f"{BASE_URL}/api/timeline/item",
            params={"kind": "deadline", "item_id": rid},
            headers=auth,
            timeout=20,
        )
        assert rd.status_code == 200, f"deadline delete failed: {rd.status_code} {rd.text}"
        # verify gone
        tl = _get_timeline(auth)
        ids = [i["id"] for i in tl["items"] if i.get("kind") == "deadline"]
        assert rid not in ids, f"deadline {rid} still present after delete"


class TestTimelineCaseDelete:
    """Case per-item delete end-to-end (only if user has a case)."""

    def test_delete_case_if_present(self, auth):
        tl = _get_timeline(auth)
        cases = [i for i in tl["items"] if i.get("kind") == "case"]
        if not cases:
            pytest.skip("no cases in timeline to delete")
        cid = cases[0]["id"]
        r = requests.delete(
            f"{BASE_URL}/api/timeline/item",
            params={"kind": "case", "item_id": cid},
            headers=auth,
            timeout=20,
        )
        assert r.status_code == 200, f"case delete failed: {r.status_code} {r.text}"
        tl2 = _get_timeline(auth)
        ids = [i["id"] for i in tl2["items"] if i.get("kind") == "case"]
        assert cid not in ids, f"case {cid} still present after delete"
