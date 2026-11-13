"""Iter45 Stage 2 live checks (pytest). Budget: 7 Lex chat calls total. Fictional users only, cleaned up after.
Covers: additive fields, streaming markers, quota exhaustion, jurisdiction conflict, cross-convo isolation,
llm-spend cost_basis, measured usage rows, ACAS reminder regression, lex-lessons needs_review."""
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
BASE_URL = [ln.split("=", 1)[1].strip() for ln in open("/app/frontend/.env") if ln.startswith("REACT_APP_BACKEND_URL")][0].rstrip("/")
API = BASE_URL + "/api"
PW = "Test12345!"
DOMAIN = "@stage2-fictional-test.co.uk"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
STATE = {"since": datetime.now(timezone.utc).isoformat(), "calls": 0}
MARK = re.compile(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\](?!\()")


def _mk(email, extra):
    base = DB.users.find_one({"email": "test@advocate.app"})
    DB.users.delete_many({"email": email})
    doc = {k: v for k, v in base.items() if k not in ("_id", "stripe_customer_id", "stripe_subscription_id")}
    doc.update({"id": str(uuid.uuid4()), "email": email, "full_name": "TEST_ Iter45", "jurisdiction": "england", **extra})
    DB.users.insert_one(doc)
    return doc["id"]


def _login(email, pw=PW):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def chat(h, msg, sid=None, category=None, stream=False):
    STATE["calls"] += 1
    assert STATE["calls"] <= 7, "AI budget exceeded"
    body = {"message": msg, "session_id": sid, "language": "en-GB", "country": "GB", "category": category}
    if not stream:
        r = requests.post(f"{API}/lex/chat", json=body, headers=h, timeout=240)
        assert r.status_code == 200, r.text[:300]
        return r.json()
    meta, done = {}, {}
    with requests.post(f"{API}/lex/chat/stream", json=body, headers=h, timeout=240, stream=True) as r:
        assert r.status_code == 200, r.text[:300]
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                ev = json.loads(line[6:])
                if ev.get("type") == "meta":
                    meta = ev
                elif ev.get("type") == "done":
                    done = ev
    return {"meta": meta, "done": done, "session_id": meta.get("session_id"),
            "response": done.get("full_text", ""), "citations": meta.get("citations", []),
            "research_status": meta.get("research_status")}


def markers(text):
    return {int(n) for m in MARK.findall(text or "") for n in re.findall(r"\d+", m)}


@pytest.fixture(scope="module")
def users():
    a = _mk("iter45.a" + DOMAIN, {"tier": "plus", "subscription_status": "active"})
    b = _mk("iter45.b" + DOMAIN, {"tier": "plus", "subscription_status": "active"})
    s = _mk("iter45.scot" + DOMAIN, {"tier": "plus", "subscription_status": "active", "jurisdiction": "scotland"})
    yield {"a": (a, _login("iter45.a" + DOMAIN)), "b": (b, _login("iter45.b" + DOMAIN)), "s": (s, _login("iter45.scot" + DOMAIN))}
    ids = [a, b, s]
    DB.conversations.delete_many({"user_id": {"$in": ids}})
    DB.reminders.delete_many({"user_id": {"$in": ids}})
    DB.users.delete_many({"id": {"$in": ids}})


@pytest.fixture(scope="module")
def admin_h():
    return _login("admin@aiadvocate.co.uk", "AdminLex2026!")


# Regular chat: additive fields + ACAS reminder regression (call 1)
def test_regular_chat_fields_and_acas_reminder(users):
    uid, h = users["a"]
    r = chat(h, "I was dismissed on 2 November 2026 in England, when must I contact ACAS?")
    for k in ("session_id", "response", "citations", "saved_reminders", "model", "connected_session_id",
              "research_status", "jurisdiction_check"):
        assert k in r, k
    assert r["research_status"] in ("ok", "no_results", "unavailable", "quota_exhausted", "not_configured")
    assert r["jurisdiction_check"] is False
    print("research_status", r["research_status"], "reminders", r["saved_reminders"])
    assert markers(r["response"]) <= {c["n"] for c in r["citations"]}, markers(r["response"])
    rem = r["saved_reminders"]
    assert any("2027-05-01" in json.dumps(x) and "ACAS" in json.dumps(x) for x in rem), rem
    assert "1 May 2027" in r["response"], r["response"][:500]
    assert DB.reminders.count_documents({"user_id": uid}) >= 1


# Streaming chat: meta research_status, done full_text, markers ⊆ citations (call 2)
def test_streaming_markers(users):
    _, h = users["b"]
    r = chat(h, "Fictional test: in England, how much notice must a landlord give under a section 21 notice?", stream=True)
    assert "research_status" in r["meta"], r["meta"]
    assert len(r["response"]) > 100
    cit = {c["n"] for c in r["citations"]}
    print("stream status", r["research_status"], "markers", markers(r["response"]), "cits", cit)
    assert markers(r["response"]) <= cit


# Quota exhaustion simulation (call 3) — restores original count
def test_quota_exhausted_high_risk(users):
    _, h = users["a"]
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    orig = DB.tavily_usage.find_one({"month": month}, {"_id": 0})
    STATE["orig_tavily"] = orig
    DB.tavily_usage.update_one({"month": month}, {"$set": {"count": 100000}}, upsert=True)
    try:
        r = chat(h, "Fictional test: my landlord in Bristol changed the locks while I was out and put my belongings "
                    "on the street. What are my rights right now?", category="property")
    finally:
        if orig:
            DB.tavily_usage.update_one({"month": month}, {"$set": {"count": orig.get("count", 0)}})
        else:
            DB.tavily_usage.delete_one({"month": month})
    after = DB.tavily_usage.find_one({"month": month}, {"_id": 0})
    STATE["tavily_after"] = after
    text = r["response"]
    print("QUOTA RESP HEAD:", text[:400], "\nTAIL:", text[-400:])
    assert r["research_status"] == "quota_exhausted"
    assert re.search(r"couldn.t check|could not check|unable to check|not able to check|couldn.t verify|could not verify|wasn.t able to check",
                     text, re.I), text[:300]
    assert not MARK.search(text), "citation markers present"
    assert "[CONFIDENCE: HIGH]" not in text
    assert r["citations"] == []


# Jurisdiction conflict (call 4)
def test_jurisdiction_conflict(users):
    uid, h = users["s"]
    r = chat(h, "Fictional test: my landlord is refusing to return my deposit for the house I rent in Cardiff. What can I do?")
    head = r["response"][:500]
    print("JURIS HEAD:", head)
    assert r["jurisdiction_check"] is True
    assert "?" in head and re.search(r"Wales|Scotland|Cardiff", head)
    assert DB.users.find_one({"id": uid})["jurisdiction"] == "scotland"


# Cross-conversation isolation (calls 5-7)
def test_cross_conversation_isolation(users):
    uid, h = users["b"]
    ra = chat(h, "Fictional test: my letting agent Quillfeather Homes Ltd kept my £640 deposit in Norwich. Just note that for now.")
    rb = chat(h, "New question: do you know the name of my letting agent and how much deposit they kept?", stream=True)
    assert rb["session_id"] != ra["session_id"]
    assert "quillfeather" not in rb["response"].lower(), rb["response"][:300]
    assert "640" not in rb["response"]
    _, ha = users["a"]
    # other user cannot read the session
    g = requests.get(f"{API}/lex/sessions/{ra['session_id']}", headers=ha, timeout=30)
    assert g.status_code in (200, 404)
    assert "quillfeather" not in g.text.lower()
    # owner can read own session (current-conversation memory store intact)
    g2 = requests.get(f"{API}/lex/sessions/{ra['session_id']}", headers=h, timeout=30)
    assert g2.status_code == 200 and "quillfeather" in g2.text.lower()
    # same-conversation memory still works
    rc = chat(h, "What was the name of my letting agent again?", sid=ra["session_id"])
    assert "quillfeather" in rc["response"].lower(), rc["response"][:300]


# Admin llm-spend cost_basis
def test_llm_spend_cost_basis(admin_h):
    r = requests.get(f"{API}/admin/llm-spend", headers=admin_h, timeout=30)
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    for k in ("total_gbp", "calls", "by_model", "top_users", "cost_basis", "cost_basis_note"):
        assert k in d, k
    for k in ("measured", "estimated", "flat_rate"):
        assert k in d["cost_basis"]
    print("cost_basis", d["cost_basis"])


def test_llm_spend_requires_admin(users):
    _, h = users["a"]
    r = requests.get(f"{API}/admin/llm-spend", headers=h, timeout=30)
    assert r.status_code in (401, 403)


# usage rows measured / tokens_source (runs after chat tests)
def test_usage_rows_measured(users):
    import time
    time.sleep(2)
    ids = [users[k][0] for k in users]
    rows = list(DB.llm_usage.find({"user_id": {"$in": ids}, "ts": {"$gte": STATE["since"]}}, {"_id": 0}))
    print("rows", [(r["provider"], r["model"], r["tokens_source"], r["measured"], r["feature"], r.get("cost_gbp")) for r in rows])
    assert rows
    llm = [r for r in rows if r["provider"] != "tavily"]
    assert llm
    for r in rows:
        assert r["tokens_source"] in ("provider", "estimated_tokenizer_v2", "not_applicable")
        assert (r["tokens_source"] == "provider") == r["measured"]
    lex = [r for r in llm if r.get("feature") in ("lex_chat", "lex_chat_stream")]
    print("lex rows", [(r["feature"], r["tokens_source"]) for r in lex])
    assert any(r["measured"] for r in llm)


# Lessons admin list with needs_review flags
def test_admin_lessons_needs_review(admin_h):
    r = requests.get(f"{API}/admin/lex-lessons", headers=admin_h, timeout=30)
    assert r.status_code == 200, r.text[:200]
    d = r.json()
    rows = d if isinstance(d, list) else d.get("lessons") or d.get("items") or []
    assert rows
    flagged = [x for x in rows if x.get("needs_review")]
    print("lessons", len(rows), "flagged", len(flagged))
    assert flagged and all(x.get("review_reason") for x in flagged)
