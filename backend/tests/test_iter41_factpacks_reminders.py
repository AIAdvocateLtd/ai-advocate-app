"""Iteration 41 — Fact packs (all UK nations) + auto-saved deadline reminders from Lex chat."""
import os
import json
import uuid
from datetime import date
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
from deadline_calc import compute  # noqa: E402

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
mdb = MongoClient(os.environ.get("MONGO_URL"))[os.environ.get("DB_NAME")]
ADMIN = {"email": "admin@aiadvocate.co.uk", "password": "AdminLex2026!"}
CREATED_REMINDERS = []


@pytest.fixture(scope="module")
def ah():
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code}")
    yield {"Authorization": f"Bearer {r.json()['access_token']}"}
    # cleanup only reminders this run created
    if CREATED_REMINDERS:
        mdb.reminders.delete_many({"id": {"$in": CREATED_REMINDERS}, "source": "lex_auto"})


def _chat(ah, msg, session_id=None):
    body = {"message": msg, "category": "general", "language": "en-GB", "country": "GB"}
    if session_id:
        body["session_id"] = session_id
    r = requests.post(f"{BASE}/api/lex/chat", headers=ah, json=body, timeout=180)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    for s in d.get("saved_reminders") or []:
        CREATED_REMINDERS.append(s["id"])
    return d


# --- Pure deadline maths (unit)
class TestDeadlineMaths:
    def test_et_england_6_months(self):
        items = compute([{"type": "employment_tribunal", "event_date": "2026-10-31", "jurisdiction": "england"}])
        assert items[0][1] == "Contact ACAS (tribunal time limit)"
        assert items[0][2] == date(2027, 4, 30)

    def test_et_ni_3_months_less_day(self):
        items = compute([{"type": "employment_tribunal", "event_date": "2026-11-02", "jurisdiction": "northern_ireland"}])
        assert items[0][1] == "Contact the LRA / tribunal time limit"
        assert items[0][2] == date(2027, 2, 1)

    def test_wales_s173(self):
        items = compute([{"type": "tenancy_notice", "served_date": "2026-11-01", "tenancy_start_date": "2025-03-01",
                          "jurisdiction": "wales"}])
        assert items[0][2] == date(2027, 5, 1)
        assert "Warning" not in items[0][0]


# --- Fact packs seeded and visible to admin
class TestFactPacks:
    def test_admin_lessons_counts(self, ah):
        r = requests.get(f"{BASE}/api/admin/lex-lessons", headers=ah, timeout=30)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        rows = d.get("lessons") or d.get("items") or d
        fp = [x for x in rows if x.get("source") == "fact_pack" and x.get("status") == "approved"]
        counts = {}
        for x in fp:
            counts[x["category"]] = counts.get(x["category"], 0) + 1
        print("COUNTS", counts)
        assert counts == {"immigration": 13, "employment": 8, "housing": 5, "family": 5, "benefits": 6}


# --- Lex chat auto-saved reminders (non-stream)
class TestAutoReminders:
    def test_acas_reminder_and_no_dup(self, ah):
        sid = f"TEST_{uuid.uuid4()}"
        q = "I was dismissed on 31 October 2026 in England. When must I contact ACAS?"
        d = _chat(ah, q, sid)
        print("RESP", d["response"][:600], d.get("saved_reminders"))
        assert "saved_reminders" in d
        titles = [s["title"] for s in d["saved_reminders"]]
        assert "Contact ACAS (tribunal time limit)" in titles
        s = [x for x in d["saved_reminders"] if x["title"].startswith("Contact ACAS")][0]
        assert s["due_at"].startswith("2027-04-30")
        assert "30 April 2027" in d["response"]
        # persisted
        lst = requests.get(f"{BASE}/api/reminders", headers=ah, timeout=30).json()["reminders"]
        assert any(r["id"] == s["id"] and r.get("source") == "lex_auto" for r in lst)
        # dup
        d2 = _chat(ah, q, sid)
        print("DUP saved", d2.get("saved_reminders"))
        assert not any(x["title"].startswith("Contact ACAS") for x in d2["saved_reminders"])
        assert mdb.reminders.count_documents({"user_id": lst[0]["user_id"], "title": s["title"],
                                              "due_at": s["due_at"], "status": "pending"}) == 1
        # delete (dismiss) via API
        r = requests.patch(f"{BASE}/api/reminders/{s['id']}?status=dismissed", headers=ah, timeout=30)
        assert r.status_code == 200
        lst = requests.get(f"{BASE}/api/reminders", headers=ah, timeout=30).json()["reminders"]
        assert not any(r["id"] == s["id"] for r in lst)

    def test_ni_lra(self, ah):
        d = _chat(ah, "I live in Belfast, dismissed 2 November 2026, deadline?")
        print("NI", d["response"][:600], d.get("saved_reminders"))
        assert any(x["title"] == "Contact the LRA / tribunal time limit" and x["due_at"].startswith("2027-02-01")
                   for x in d["saved_reminders"])
        assert "LRA" in d["response"] or "Labour Relations Agency" in d["response"]
        assert "1 February 2027" in d["response"]

    def test_wales_s173_chat(self, ah):
        d = _chat(ah, "I'm in Cardiff, landlord served a section 173 notice on 1 November 2026, I moved in 1 March 2025")
        print("WALES", d["response"][:600], d.get("saved_reminders"))
        assert "1 May 2027" in d["response"]
        assert any(x["due_at"].startswith("2027-05-01") for x in d["saved_reminders"])

    def test_no_dates_no_reminders(self, ah):
        d = _chat(ah, "What is a tenancy deposit?")
        assert d["saved_reminders"] == []


# --- Topic fact packs used in answers
class TestTopicPacks:
    def test_uc_rate(self, ah):
        d = _chat(ah, "How much is Universal Credit for a single 30 year old?")
        print("UC", d["response"][:500])
        assert "424.90" in d["response"]
        assert d["saved_reminders"] == []

    def test_scotland_divorce(self, ah):
        d = _chat(ah, "How long does divorce take in Scotland?")
        r = d["response"].lower()
        print("DIV", d["response"][:600])
        assert ("1 year" in r or "one year" in r) and ("2 years" in r or "two years" in r)


# --- Streaming done event includes saved_reminders
class TestStream:
    def test_stream_done_has_saved_reminders(self, ah):
        r = requests.post(f"{BASE}/api/lex/chat/stream", headers=ah, timeout=180, stream=True,
                          json={"message": "My visa expires on 15 March 2027. When must I apply to extend?",
                                "category": "general", "language": "en-GB", "country": "GB"})
        assert r.status_code == 200
        body = "".join(c.decode("utf-8", "ignore") for c in r.iter_content(1024))
        done = [l for l in body.splitlines() if l.startswith("data:") and '"type": "done"' in l]
        assert done, body[-300:]
        meta = json.loads(done[0][5:].strip())
        print("STREAM saved", meta.get("saved_reminders"))
        for s in meta.get("saved_reminders") or []:
            CREATED_REMINDERS.append(s["id"])
        assert any(s["due_at"].startswith("2027-03-15") for s in meta["saved_reminders"])
