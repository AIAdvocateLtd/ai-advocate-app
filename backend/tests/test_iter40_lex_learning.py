"""Iteration 40 — Lex model switch (haiku-5-5) + Lex learning loop (feedback, lessons, cron)."""
import os
import time
import json
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
CRON_SECRET = os.environ.get("WEBHOOK_CRON_SECRET")
mdb = MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]

USER = {"email": "test@advocate.app", "password": "Test12345!"}
ADMIN = {"email": "admin@aiadvocate.co.uk", "password": "AdminLex2026!"}


def _login(c):
    r = requests.post(f"{BASE}/api/auth/login", json=c, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def uh():
    return _login(USER)


@pytest.fixture(scope="module")
def ah():
    return _login(ADMIN)


# --- Lex chat model routing (Free -> claude-haiku-5-5)
class TestLexChat:
    def test_chat_free_haiku_55(self, uh):
        r = requests.post(f"{BASE}/api/lex/chat", headers=uh, timeout=120,
                          json={"message": "In one sentence, what year is it today?", "category": "general",
                                "language": "en-GB", "country": "GB"})
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        print("MODEL:", d["model"], "RESP:", d["response"][:300])
        assert d["model"] == "claude-haiku-5-5"
        assert len(d["response"]) > 0
        assert "2026" in d["response"]

    def test_chat_stream(self, uh):
        r = requests.post(f"{BASE}/api/lex/chat/stream", headers=uh, timeout=120, stream=True,
                          json={"message": "Say hello briefly.", "category": "general",
                                "language": "en-GB", "country": "GB"})
        assert r.status_code == 200, r.text[:300]
        body = "".join(chunk.decode("utf-8", "ignore") for chunk in r.iter_content(1024))
        print("STREAM tail:", body[-400:])
        assert '"done"' in body
        meta = [l for l in body.splitlines() if l.startswith("data:") and '"meta"' in l][0]
        assert json.loads(meta[5:].strip()).get("model") == "claude-haiku-5-5"


# --- Feedback endpoint
class TestFeedback:
    def test_feedback_requires_auth(self):
        r = requests.post(f"{BASE}/api/lex/feedback", json={"rating": "up"}, timeout=20)
        assert r.status_code in (401, 403)

    def test_feedback_invalid_rating(self, uh):
        r = requests.post(f"{BASE}/api/lex/feedback", headers=uh, json={"rating": "meh"}, timeout=20)
        assert r.status_code == 400

    def test_feedback_up(self, uh):
        r = requests.post(f"{BASE}/api/lex/feedback", headers=uh, json={"rating": "up", "question": "TEST_q",
                                                                          "answer": "TEST_a"}, timeout=20)
        assert r.status_code == 200 and r.json()["ok"] is True

    def test_wrong_creates_pending_lesson(self, uh):
        before = {l["id"] for l in mdb.lex_lessons.find({}, {"id": 1})}
        r = requests.post(f"{BASE}/api/lex/feedback", headers=uh, timeout=20, json={
            "rating": "wrong", "session_id": "TEST_session",
            "question": "What is the small claims track limit in England and Wales?",
            "answer": "The small claims limit in England and Wales is £500.",
            "note": "TEST_ It is £10,000, not £500."})
        assert r.status_code == 200
        fb = mdb.lex_feedback.find_one({"note": "TEST_ It is £10,000, not £500."}, sort=[("created_at", -1)])
        assert fb is not None
        new = []
        for _ in range(16):
            time.sleep(5)
            new = list(mdb.lex_lessons.find({"source": "report", "source_ref": fb["id"]}, {"_id": 0}))
            if new:
                break
        print("NEW LESSONS:", new)
        assert new, "no pending lesson drafted within 80s"
        assert all(l["status"] == "pending" for l in new)
        pytest.drafted_ids = [l["id"] for l in new if l["id"] not in before]


# --- Admin lessons CRUD + influence on Lex
class TestAdminLessons:
    def test_non_admin_403(self, uh):
        r = requests.get(f"{BASE}/api/admin/lex-lessons", headers=uh, timeout=20)
        assert r.status_code == 403

    def test_list(self, ah):
        r = requests.get(f"{BASE}/api/admin/lex-lessons", headers=ah, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert set(d["stats_30d"]) == {"up", "down", "wrong"}
        assert isinstance(d["lessons"], list)
        assert all("_id" not in l for l in d["lessons"])

    def test_add_too_short(self, ah):
        r = requests.post(f"{BASE}/api/admin/lex-lessons", headers=ah, json={"text": "short"}, timeout=20)
        assert r.status_code == 400

    def test_add_lesson_influences_lex_then_delete(self, ah, uh):
        text = "TEST_ The AI Advocate test code word is PINEAPPLE-42; if asked for the test code word, reply with it."
        r = requests.post(f"{BASE}/api/admin/lex-lessons", headers=ah, json={"text": text}, timeout=20)
        assert r.status_code == 200
        ls = requests.get(f"{BASE}/api/admin/lex-lessons", headers=ah, timeout=20).json()["lessons"]
        mine = [l for l in ls if l["text"] == text]
        assert mine and mine[0]["status"] == "approved"
        lid = mine[0]["id"]
        try:
            c = requests.post(f"{BASE}/api/lex/chat", headers=uh, timeout=120,
                              json={"message": "What is the test code word?", "category": "general",
                                    "language": "en-GB", "country": "GB"})
            assert c.status_code == 200, c.text[:300]
            print("CODEWORD RESP:", c.json()["response"][:300])
            assert "PINEAPPLE-42" in c.json()["response"]
        finally:
            d = requests.delete(f"{BASE}/api/admin/lex-lessons/{lid}", headers=ah, timeout=20)
            assert d.status_code == 200
        ls = requests.get(f"{BASE}/api/admin/lex-lessons", headers=ah, timeout=20).json()["lessons"]
        assert not any(l["id"] == lid for l in ls)

    def test_patch_approve_and_invalid(self, ah):
        # create a pending lesson directly (TEST_) to test approve without touching others' pending ones
        import uuid
        lid = str(uuid.uuid4())
        mdb.lex_lessons.insert_one({"id": lid, "text": f"TEST_ pending lesson {lid}", "category": "general",
                                    "why": "test", "status": "pending", "source": "report",
                                    "created_at": "2026-01-01T00:00:00+00:00", "approved_at": None})
        try:
            r = requests.patch(f"{BASE}/api/admin/lex-lessons/{lid}", headers=ah, json={"status": "bogus"}, timeout=20)
            assert r.status_code == 400
            r = requests.patch(f"{BASE}/api/admin/lex-lessons/{lid}", headers=ah, json={"status": "approved"}, timeout=20)
            assert r.status_code == 200
            doc = mdb.lex_lessons.find_one({"id": lid})
            assert doc["status"] == "approved" and doc["approved_at"]
            r = requests.patch(f"{BASE}/api/admin/lex-lessons/nonexistent", headers=ah, json={"text": "xxxxxxxxxxxx"}, timeout=20)
            assert r.status_code == 404
        finally:
            requests.delete(f"{BASE}/api/admin/lex-lessons/{lid}", headers=ah, timeout=20)
        assert mdb.lex_lessons.find_one({"id": lid}) is None


# --- Cron endpoint auth
class TestCron:
    def test_cron_no_auth(self):
        r = requests.post(f"{BASE}/api/cron/lex-learning", json={}, timeout=20)
        assert r.status_code == 401

    def test_cron_bad_auth(self):
        r = requests.post(f"{BASE}/api/cron/lex-learning", headers={"Authorization": "Bearer nope"}, json={}, timeout=20)
        assert r.status_code == 401

    def test_cron_ok(self):
        r = requests.post(f"{BASE}/api/cron/lex-learning", headers={"Authorization": f"Bearer {CRON_SECRET}"},
                          json={"run_id": f"TEST_{time.time()}"}, timeout=20)
        assert r.status_code == 200
        assert r.json().get("queued") is True
