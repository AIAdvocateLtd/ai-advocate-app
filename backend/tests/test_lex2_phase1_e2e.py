"""Lex 2.0 Phase 1 sign-off: contract routes + streamed chat end-to-end with simulated AI and recorded legislation.
No AI calls, no network. Run: cd /app/backend && python -m pytest tests/test_lex2_phase1_e2e.py -q"""
import io
import json
import os
import sys
import uuid
from types import SimpleNamespace as NS

import pytest
from fastapi import UploadFile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import legal_sources as L  # noqa: E402
from tests.test_lex2_phase1 import fake_fetch  # noqa: E402
from tests.test_lex2_phase1_wiring import FakeChat, SEEN, _research  # noqa: E402
from tests.test_stage3_limits import run, db  # noqa: E402

MIXED = ("Your landlord relied on section 21 of the Housing Act 1988. "
         "Separately, section 94 of the Employment Rights Act 1996 protects employees.\n\n[CONFIDENCE: HIGH]")


@pytest.fixture(autouse=True)
def _fakes(monkeypatch):
    SEEN.clear()
    L._cache.clear()
    monkeypatch.setattr(L, "_fetch", fake_fetch)
    monkeypatch.setattr(server, "LlmChat", FakeChat)
    monkeypatch.setattr(server, "rag_research", _research())


@pytest.fixture
def user():
    uid = f"TEST_lex2e2e_{uuid.uuid4().hex[:8]}"
    u = {"id": uid, "email": f"{uid}@example.com", "tier": "plus", "subscription_status": "active",
         "country": "GB", "jurisdiction": "scotland", "email_verified": True}
    run(db.users.insert_one(dict(u)))
    yield run(db.users.find_one({"id": uid}, {"_id": 0}))
    for c in ("users", "legal_files", "contract_analyses", "conversations", "chat_sessions", "usage", "s3_events",
              "s3_consumptions", "llm_usage", "reminders"):
        run(db[c].delete_many({"$or": [{"id": uid}, {"user_id": uid}]}))


def _upload(text="This tenancy agreement is between the landlord and tenant. Rent is due monthly."):
    return UploadFile(file=io.BytesIO(text.encode()), filename="contract.txt", headers={"content-type": "text/plain"})


def test_contracts_analyze_text_route(user):
    SEEN["answer"] = MIXED
    res = run(server.analyze_contract(file=_upload(), language="en-GB", country="GB", user=user))
    a = res["analysis"]
    assert "Housing Act 1988 [⚠ see legislation check]" in a and "does not extend to Scotland" in a
    assert L.OGL in a and "[CONFIDENCE: MEDIUM]" in a
    saved = run(db.legal_files.find_one({"id": res["id"]}, {"_id": 0, "analysis": 1}))
    assert saved["analysis"] == a


def test_contract_analyze_json_route_single_file(user, monkeypatch):
    async def fake_extract(path, mime):
        return "This tenancy agreement is between the landlord and tenant. Rent is due monthly in advance."
    monkeypatch.setattr(server, "_extract_contract_text", fake_extract)
    SEEN["answer"] = json.dumps({"contract_type": "lease", "plain_english_summary": "A lease. " + MIXED,
                                 "red_flags": [], "amber_flags": [], "verdict_one_liner": "OK"})
    res = run(server.contract_analyze(file=_upload(), language="en-GB", country="GB", doc_ids=None, user=user))
    flags = [f for f in res["amber_flags"] if f.startswith("Legislation check:")]
    assert len(flags) == 1 and "does not extend to Scotland" in flags[0]
    assert res["legislation_check"] and res["verdict_one_liner"] == "OK"


def test_contract_analyze_multipage_path_flags_unfound_act(user):
    SEEN["answer"] = json.dumps({"contract_type": "service", "plain_english_summary": "Section 4 of the Made Up Act 2019 applies.",
                                 "amber_flags": []})
    res = run(server._analyse_contract_text("Some contract text long enough to analyse properly here.", "x.pdf",
                                            "application/pdf", None, "en-GB", "GB", user["id"]))
    assert any("could not be found on legislation.gov.uk" in f for f in res["amber_flags"])


def _stream(user, monkeypatch, answer):
    async def acompletion(**kw):
        async def gen():
            for part in (answer[: len(answer) // 2], answer[len(answer) // 2:]):
                yield NS(choices=[NS(delta=NS(content=part), finish_reason=None)], usage=None, model="fake")
            yield NS(choices=[NS(delta=NS(content=None), finish_reason="stop")],
                     usage=NS(prompt_tokens=10, completion_tokens=20, completion_tokens_details=None), model="fake")
        return gen()
    import litellm
    monkeypatch.setattr(litellm, "acompletion", acompletion)
    server.stage3.begin_request()
    resp = run(server.lex_chat_stream(server.ChatMessage(message=f"My landlord in Edinburgh wants me out {uuid.uuid4().hex[:4]}",
                                                         country="GB", category="property"), user))

    async def collect():
        return [json.loads(c[5:].strip()) for chunk in [x async for x in resp.body_iterator]
                for c in (chunk if isinstance(chunk, str) else chunk.decode()).split("\n\n") if c.startswith("data:")]
    return run(collect())


def test_streamed_chat_legislation_check(user, monkeypatch):
    ev = _stream(user, monkeypatch, MIXED)
    types = [e["type"] for e in ev]
    assert types[0] == "meta" and "token" in types and types[-1] == "done" and "error" not in types
    done = ev[-1]
    assert done["full_text"].strip() and "does not extend to Scotland" in done["full_text"]
    assert "Housing Act 1988 [⚠ see legislation check]" in done["full_text"] and L.OGL in done["full_text"]
    leg = [c for c in done["citations"] if c.get("source") == "legislation"]
    assert len(leg) == 1 and "Employment Rights Act 1996" in leg[0]["title"] and leg[0]["claim_check"] == "status_checked"


def test_streamed_chat_timeout_disclosed_not_verified(user, monkeypatch):
    monkeypatch.setattr(L, "TIMEOUT", 0.05)
    monkeypatch.setattr(L, "_fetch", lambda url: fake_fetch(url, delay=0.5))
    ev = _stream(user, monkeypatch, MIXED)
    done = ev[-1]
    assert done["type"] == "done" and "could not be checked against legislation.gov.uk" in done["full_text"]
    assert "[CONFIDENCE: HIGH]" not in done["full_text"]
    assert not [c for c in done["citations"] if c.get("source") == "legislation"]


def test_caselaw_disabled_in_this_environment():
    assert os.environ.get("CASELAW_VERIFY_ENABLED") != "1" and not L.caselaw_enabled()


def test_tier_models_unchanged():
    assert server.lex_model_for_tier("free")[:2] == ("anthropic", "claude-haiku-5-5")
    assert server.lex_model_for_tier("plus")[:2] == ("openai", "gpt-5.2")
    assert server.lex_model_for_tier("pro")[:2] == server.lex_model_for_tier("pro", True)[:2] == ("anthropic", "claude-sonnet-5-5")
