"""Lex 2.0 Phase 1 — endpoint wiring with a fake AI model and recorded legislation responses (no AI, no network).
Run: cd /app/backend && python -m pytest tests/test_lex2_phase1_wiring.py -q"""
import os
import sys
import uuid

import pytest
from starlette.requests import Request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import legal_sources as L  # noqa: E402
from tests.test_lex2_phase1 import fake_fetch  # noqa: E402
from tests.test_stage3_limits import run, db  # noqa: E402

SEEN = {}
WRONG_NATION_ANSWER = "[CONFIDENCE: HIGH]\nYour landlord can use section 21 of the Housing Act 1988 to end the tenancy."


class FakeChat:
    def __init__(self, api_key=None, session_id=None, system_message="", **kw):
        SEEN["system"] = system_message

    def with_model(self, *a):
        return self

    def with_params(self, **kw):
        return self

    async def send_message(self, msg):
        SEEN["prompt"] = msg.text
        return SEEN.get("answer", WRONG_NATION_ANSWER)


def _research(status="ok"):
    async def fake(message, country="GB", db=None, context="", nation=None):
        SEEN["research_args"] = {"message": message, "context": context, "nation": nation}
        if status != "ok":
            return {"status": status, "block": "", "citations": [], "sources": []}
        return {"status": "ok", "block": "\n=== LIVE LEGAL RESEARCH ===\n[1] Scottish tenancy guidance",
                "citations": [{"n": 1, "title": "Private residential tenancies", "url": "https://www.mygov.scot/tenancy", "source": "official"}],
                "sources": [{"n": 1, "title": "Private residential tenancies", "content": "private residential tenancy Scotland"}]}
    return fake


@pytest.fixture(autouse=True)
def _fakes(monkeypatch):
    SEEN.clear()
    L._cache.clear()
    monkeypatch.setattr(L, "_fetch", fake_fetch)
    monkeypatch.setattr(server, "LlmChat", FakeChat)
    monkeypatch.setattr(server, "rag_research", _research())


def _taster(message):
    dev = f"TEST_lex2_{uuid.uuid4().hex}"
    req = Request({"type": "http", "method": "POST", "path": "/api/lex/taster", "query_string": b"",
                   "headers": [(b"x-forwarded-for", f"198.51.100.{uuid.uuid4().int % 250 + 1}, 104.22.56.9, 34.102.193.45".encode())]})
    out = run(server.lex_taster(req, server.TasterMessage(message=message, device_id=dev, language="en-GB", country="GB")))
    run(db.taster_usage.delete_many({"key": {"$regex": "TEST_lex2_|taster_ip:198.51.100."}}))
    run(db.taster_answers.delete_one({"id": out["taster_id"]}))
    return out


def test_taster_gets_jurisdiction_research_deadline_and_legislation_checks():
    out = _taster("Under Scots law, my landlord in Glasgow says I must leave by next week. How long do I have to respond?")
    assert SEEN["research_args"]["nation"] == "scotland"
    assert "LIVE LEGAL RESEARCH" in SEEN["system"] and server.NO_CALC_BLOCK.strip()[:40] in SEEN["system"]
    assert "does not extend to Scotland" in out["response"] and "[CONFIDENCE: MEDIUM]" in out["response"]
    assert out["citations"] and out["model"] == "claude-haiku-4-5"


def test_taster_research_failure_is_disclosed(monkeypatch):
    monkeypatch.setattr(server, "rag_research", _research("quota_exhausted"))
    SEEN["answer"] = "[CONFIDENCE: HIGH]\nYou must respond to the eviction notice at the tribunal."
    out = _taster("My landlord is evicting me and there is a tribunal hearing next week, what do I do?")
    assert "[CONFIDENCE: HIGH]" not in out["response"]


def test_chat_finaliser_runs_legislation_check():
    cites = []
    out, rep = run(server._lex_finalize(WRONG_NATION_ANSWER, cites, {"status": "ok", "sources": []}, "high", "en-GB",
                                        "section 21 notice in Edinburgh", {"applicable": "scotland", "conflict": False}))
    assert "does not extend to Scotland" in out and rep["legislation"]["verdicts"] == ["wrong_jurisdiction"]


def test_letter_grounded_and_notes_outside_letter_body():
    uid = f"TEST_lex2_{uuid.uuid4().hex[:8]}"
    user = {"id": uid, "email": f"{uid}@example.com", "tier": "plus", "subscription_status": "active",
            "country": "GB", "jurisdiction": "scotland"}
    run(db.users.insert_one(dict(user)))
    try:
        SEEN["answer"] = "Dear Landlord,\nUnder section 21 of the Housing Act 1988 you cannot...\nYours faithfully"
        res = run(server.generate_letter(server.LegalLetterRequest(letter_type="deposit return", recipient="Landlord",
                                                                    your_name="A Tenant", details="Deposit not returned, Edinburgh"), user))
        body, notes = res["letter"].split("\n\n-----", 1)
        assert "[⚠" not in body and "does not extend to Scotland" in notes
        assert "LIVE LEGAL RESEARCH" in SEEN["system"] and "do not print [n] markers" not in SEEN["prompt"]
        assert SEEN["research_args"]["nation"] == "scotland"
    finally:
        run(db.users.delete_one({"id": uid}))
        run(db.legal_files.delete_many({"user_id": uid}))
