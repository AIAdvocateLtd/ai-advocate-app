"""
Regression tests — Case Timeline ↔ Case Files wiring (Iter 22).

- Resume chat from timeline
- Auto-promote (3+ turns) creates a Case File
- Manual promote endpoint creates / returns existing case
- Idempotency

Run: pytest /app/backend/tests/test_case_files_promote.py -v
"""
import os
import time
import uuid
import asyncio
import pytest
import requests
from datetime import datetime, timezone

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"


def _new_user():
    email = f"caseprom_{uuid.uuid4().hex[:10]}@advocate.app"
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "password": "Test12345!", "full_name": "Case Test",
        "language": "en-GB", "country": "GB", "device_id": f"d-{uuid.uuid4().hex[:8]}",
    })
    assert r.status_code == 200, r.text
    return r.json()["access_token"], email


def _insert_conv_directly(email: str, session_id: str, turns: int = 3, category: str = "ask_lex"):
    """Bypass the chat endpoint (rate limits) and insert turns straight into the DB
    so we can test the timeline auto-promote pass deterministically."""
    import sys
    sys.path.insert(0, "/app/backend")
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    from server import encrypt_text

    async def go():
        c = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = c[os.environ["DB_NAME"]]
        u = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
        now = datetime.now(timezone.utc).isoformat()
        for i in range(turns):
            await db.conversations.insert_one({
                "id": str(uuid.uuid4()), "user_id": u["id"], "session_id": session_id,
                "category": category,
                "user_message": encrypt_text(f"Bullied at work turn {i+1}"),
                "assistant_response": encrypt_text(f"Response {i+1}"),
                "language": "en-GB", "model_used": "haiku",
                "created_at": now,
            })

    asyncio.run(go())


def test_resume_chat_session_returns_full_history():
    token, email = _new_user()
    sid = f"resume-{uuid.uuid4().hex[:8]}"
    _insert_conv_directly(email, sid, turns=2)
    r = requests.get(f"{API}/lex/sessions/{sid}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    turns = r.json()
    assert len(turns) == 2
    # Verify decrypted content surfaces
    assert "Bullied at work turn 1" in turns[0]["user_message"]


def test_auto_promote_on_3_turns():
    token, email = _new_user()
    sid = f"auto-{uuid.uuid4().hex[:8]}"
    _insert_conv_directly(email, sid, turns=3, category="employment")
    # Before: no cases
    cases_before = requests.get(f"{API}/cases", headers={"Authorization": f"Bearer {token}"}).json()["cases"]
    assert len(cases_before) == 0
    # Hit /timeline → triggers auto-promote
    t = requests.get(f"{API}/timeline", headers={"Authorization": f"Bearer {token}"}).json()
    # After: should have 1 auto-created case
    cases_after = requests.get(f"{API}/cases", headers={"Authorization": f"Bearer {token}"}).json()["cases"]
    assert len(cases_after) == 1
    c = cases_after[0]
    assert c["source"] == "auto"
    assert c["category"] == "employment"
    assert c["linked_session_id"] == sid
    # Title should be cleaned ("Bullied at work" not "Bullied at work turn 1" with "Turn" appended)
    assert "Bullied at work" in c["name"]
    # Timeline row should show linked_case_id
    chat_row = next((i for i in t["items"] if i.get("id") == sid), None)
    assert chat_row is not None
    assert chat_row.get("linked_case_id") == c["id"]


def test_manual_promote_endpoint():
    token, email = _new_user()
    sid = f"manual-{uuid.uuid4().hex[:8]}"
    _insert_conv_directly(email, sid, turns=1, category="ask_lex")
    r = requests.post(f"{API}/cases/from-session",
                      json={"session_id": sid},
                      headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    case = r.json()["case"]
    assert case["source"] == "manual"
    assert case["linked_session_id"] == sid


def test_manual_promote_idempotent():
    token, email = _new_user()
    sid = f"idem-{uuid.uuid4().hex[:8]}"
    _insert_conv_directly(email, sid, turns=1)
    r1 = requests.post(f"{API}/cases/from-session", json={"session_id": sid},
                       headers={"Authorization": f"Bearer {token}"})
    r2 = requests.post(f"{API}/cases/from-session", json={"session_id": sid},
                       headers={"Authorization": f"Bearer {token}"})
    assert r1.status_code == 200 and r2.status_code == 200
    # Same case_id
    assert r1.json()["case"]["id"] == r2.json()["case"]["id"]


def test_manual_promote_with_overrides():
    token, email = _new_user()
    sid = f"override-{uuid.uuid4().hex[:8]}"
    _insert_conv_directly(email, sid, turns=1)
    r = requests.post(f"{API}/cases/from-session",
                      json={"session_id": sid, "name_override": "v. Acme Ltd · Discrimination",
                            "category_override": "employment"},
                      headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    case = r.json()["case"]
    assert case["name"] == "v. Acme Ltd · Discrimination"
    assert case["category"] == "employment"


def test_manual_promote_unknown_session_returns_404():
    token, _ = _new_user()
    r = requests.post(f"{API}/cases/from-session", json={"session_id": "does-not-exist"},
                      headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404
