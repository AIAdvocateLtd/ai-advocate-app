"""
Regression tests — Per-case Timeline + enhanced PDF export (Iter 23).

Run: pytest /app/backend/tests/test_case_timeline_feed.py -v
"""
import os
import uuid
import asyncio
import pytest
import requests
from datetime import datetime, timezone

API = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"


def _new_user_with_case():
    """Create a user, seed a session with 3 turns, hit /timeline to auto-create a case."""
    email = f"casefeed_{uuid.uuid4().hex[:10]}@advocate.app"
    r = requests.post(f"{API}/auth/signup", json={
        "email": email, "password": "Test12345!", "full_name": "Feed Test",
        "language": "en-GB", "country": "GB", "device_id": f"d-{uuid.uuid4().hex[:8]}",
    })
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    sid = f"feed-{uuid.uuid4().hex[:8]}"

    # Seed via direct DB so chat-quota isn't in the picture
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
        msgs = [
            ("My landlord won't return my £900 deposit.", "Section 21..."),
            ("It's been 7 weeks since I moved out.", "TDP deadlines apply..."),
            ("What can I do legally?", "Small claims court is your route..."),
        ]
        for um, ar in msgs:
            await db.conversations.insert_one({
                "id": str(uuid.uuid4()), "user_id": u["id"], "session_id": sid,
                "category": "property",
                "user_message": encrypt_text(um),
                "assistant_response": encrypt_text(ar),
                "language": "en-GB", "model_used": "haiku",
                "created_at": now,
            })

    asyncio.run(go())
    # Hit /timeline → auto-promote runs
    requests.get(f"{API}/timeline", headers=headers)
    cases = requests.get(f"{API}/cases", headers=headers).json()["cases"]
    assert len(cases) >= 1
    return headers, cases[0]["id"], sid


def test_case_timeline_feed_returns_merged_events():
    headers, case_id, sid = _new_user_with_case()
    r = requests.get(f"{API}/cases/{case_id}/timeline", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["case"]["id"] == case_id
    events = body["events"]
    # Must contain: case_opened (anchor) + item_chat + 3 lex_turn events = 5
    kinds = [e["kind"] for e in events]
    assert "case_opened" in kinds
    assert "item_chat" in kinds
    assert kinds.count("lex_turn") == 3
    # Chronological order
    ats = [e["at"] for e in events if e.get("at")]
    assert ats == sorted(ats)


def test_case_timeline_unknown_case_returns_404():
    headers, _, _ = _new_user_with_case()
    r = requests.get(f"{API}/cases/does-not-exist/timeline", headers=headers)
    assert r.status_code == 404


def test_case_export_pdf_produces_valid_pdf():
    headers, case_id, _ = _new_user_with_case()
    r = requests.get(f"{API}/cases/{case_id}/export-pdf", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    body = r.content
    assert body.startswith(b"%PDF"), "Response is not a valid PDF"
    # New handover-style PDF should be substantially larger than the old basic one
    assert len(body) > 4000


def test_case_export_pdf_filename_is_safe():
    """Filename should include a slug of the case name + case id prefix."""
    headers, case_id, _ = _new_user_with_case()
    r = requests.get(f"{API}/cases/{case_id}/export-pdf", headers=headers)
    cd = r.headers.get("content-disposition", "")
    assert "ai-advocate" in cd.lower()
    assert case_id[:8] in cd
    # No shell-unsafe chars
    for bad in ("..", "/", "\\"):
        assert bad not in cd
