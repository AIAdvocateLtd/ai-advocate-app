"""Blank / cut-off Lex reply fix — mocked AI (no cost). Run: cd /app/backend && python -m pytest tests/test_blank_reply_fix.py -q"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx  # noqa: E402
import litellm  # noqa: E402
import server  # noqa: E402
import lex_output  # noqa: E402
from emergentintegrations.llm import chat as eichat  # noqa: E402

LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(LOOP)
MSG = "hello there, quick general question about letters"


def test_gen_params():
    assert lex_output.gen_params("claude-haiku-5-5", 1200) == (2000, {"extra_body": {"thinking": {"type": "disabled"}}})
    mx, ex = lex_output.gen_params("claude-sonnet-5-5", 1400)
    assert mx == 2600 and ex["extra_body"]["thinking"]["budget_tokens"] == 1024
    mx, ex = lex_output.gen_params("claude-sonnet-5-5", 3500, True)
    assert mx == 4000 and ex["extra_body"]["thinking"]["budget_tokens"] == 1500
    assert lex_output.gen_params("gpt-5.2", 1400) == (1400, {})
    for tier, dt in (("free", False), ("plus", False), ("pro", False), ("pro", True)):   # routing unchanged
        assert server.lex_model_for_tier(tier, dt) == {("free", False): ("anthropic", "claude-haiku-5-5", 1200),
                                                         ("plus", False): ("openai", "gpt-5.2", 1400),
                                                         ("pro", False): ("anthropic", "claude-sonnet-5-5", 1400),
                                                         ("pro", True): ("anthropic", "claude-sonnet-5-5", 3500)}[(tier, dt)]


def _resp(text, finish):
    return litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": text}, "finish_reason": finish}],
                                 usage={"prompt_tokens": 100, "completion_tokens": 50}, model="m")


def _chunks(texts, finish):
    async def gen():
        for t in texts:
            yield NS(usage=None, model="m", choices=[NS(finish_reason=None, delta=NS(content=t))])
        yield NS(usage=None, model="m", choices=[NS(finish_reason=finish, delta=NS(content=None))])
        yield NS(usage=NS(prompt_tokens=100, completion_tokens=1200, completion_tokens_details=NS(reasoning_tokens=1200)),
                 model="m", choices=[])
    return gen()


@pytest.fixture
def env(monkeypatch):
    db = server.db
    loop = LOOP
    asyncio.set_event_loop(LOOP)
    base = loop.run_until_complete(db.users.find_one({"email": "test@advocate.app"}))
    uid = f"blanktest-{uuid.uuid4()}"
    user = {k: v for k, v in base.items() if k != "_id"}
    user.update(id=uid, email=f"{uid}@stage2-fictional-test.co.uk", tier="free")
    loop.run_until_complete(db.users.insert_one(dict(user)))
    server.app.dependency_overrides[server.get_user] = lambda: user
    calls = {"completion": [], "stream": []}
    yield loop, uid, calls, monkeypatch
    server.app.dependency_overrides.pop(server.get_user, None)
    loop.run_until_complete(asyncio.sleep(0.2))
    loop.run_until_complete(db.llm_usage.delete_many({"model_actual": "m"}))
    for coll in ("users", "conversations", "usage", "reminders"):
        loop.run_until_complete(getattr(db, coll).delete_many({"id" if coll == "users" else "user_id": uid}))


def _count(loop, uid):
    d = loop.run_until_complete(server.db.usage.find_one({"user_id": uid, "feature": "lex_chat",
                                                          "bucket": datetime.now(timezone.utc).strftime("%Y-%m-%d")}))
    return (d or {}).get("count", 0)


async def _post(path, body):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://t") as c:
        return await c.post("/api" + path, json=body, headers={"Authorization": "Bearer x"}, timeout=60)


def _mock_completion(monkeypatch, calls, seq):
    def fake(**kw):
        calls["completion"].append(kw)
        return _resp(*seq[min(len(calls["completion"]) - 1, len(seq) - 1)])
    monkeypatch.setattr(eichat.litellm, "completion", fake)


def test_regular_blank_primary_uses_fallback(env):
    loop, uid, calls, mp = env
    _mock_completion(mp, calls, [("", "length"), ("Here is a full answer from the backup model.", "stop")])
    r = loop.run_until_complete(_post("/lex/chat", {"message": MSG, "language": "en-GB", "country": "GB"}))
    assert r.status_code == 200 and "full answer" in r.json()["response"]
    assert calls["completion"][0]["extra_body"] == {"thinking": {"type": "disabled"}}      # Free: thinking off
    assert calls["completion"][1]["model"] == "claude-sonnet-4-5-20250929"
    assert _count(loop, uid) == 1


def test_regular_both_blank_refunds_and_no_blank_saved(env):
    loop, uid, calls, mp = env
    _mock_completion(mp, calls, [("", "length"), ("  ", "length")])
    r = loop.run_until_complete(_post("/lex/chat", {"message": MSG, "language": "en-GB", "country": "GB"}))
    assert r.status_code == 503 and "not been counted" in r.json()["detail"]
    assert _count(loop, uid) == 0
    assert loop.run_until_complete(server.db.conversations.count_documents({"user_id": uid})) == 0


def test_regular_cut_off_gets_note(env):
    loop, uid, calls, mp = env
    _mock_completion(mp, calls, [("A long answer that stops mid", "length")])
    r = loop.run_until_complete(_post("/lex/chat", {"message": MSG, "language": "en-GB", "country": "GB"}))
    assert r.status_code == 200 and 'Reply "continue"' in r.json()["response"]
    assert len(calls["completion"]) == 1


def _stream(loop, body):
    async def go():
        events = []
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://t") as c:
            async with c.stream("POST", "/api/lex/chat/stream", json=body, headers={"Authorization": "Bearer x"}, timeout=60) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
        return events
    return loop.run_until_complete(go())


def _mock_stream(monkeypatch, calls, texts, finish):
    async def fake(**kw):
        calls["stream"].append(kw)
        return _chunks(texts, finish)
    monkeypatch.setattr(litellm, "acompletion", fake)


def test_stream_blank_uses_fallback(env):
    loop, uid, calls, mp = env
    _mock_stream(mp, calls, [], "length")
    _mock_completion(mp, calls, [("Backup model full answer.", "stop")])
    ev = _stream(loop, {"message": MSG, "language": "en-GB", "country": "GB"})
    done = [e for e in ev if e["type"] == "done"][-1]
    assert "Backup model full answer" in done["full_text"]
    assert calls["stream"][0]["extra_body"] == {"thinking": {"type": "disabled"}} and calls["stream"][0]["max_tokens"] == 2000
    loop.run_until_complete(asyncio.sleep(0.3))
    rows = loop.run_until_complete(server.db.llm_usage.find({"call_site": "lex_stream", "model_requested": "claude-haiku-5-5",
                                                             "model_actual": "m"}).sort("ts", -1).to_list(1))
    assert rows and rows[0]["finish_reason"] == "length" and rows[0]["reasoning_tokens"] == 1200 and rows[0]["output_chars"] == 0


def test_stream_both_blank_error_and_refund(env):
    loop, uid, calls, mp = env
    _mock_stream(mp, calls, [], "length")
    _mock_completion(mp, calls, [("", "stop")])
    ev = _stream(loop, {"message": MSG, "language": "en-GB", "country": "GB"})
    assert any(e["type"] == "error" and e.get("code") == "lex_incomplete" and "not been counted" in e["message"] for e in ev)
    assert _count(loop, uid) == 0
    assert loop.run_until_complete(server.db.conversations.count_documents({"user_id": uid})) == 0


def test_stream_cut_off_note_in_final_text(env):
    loop, uid, calls, mp = env
    _mock_stream(mp, calls, ["Part one of the answer ", "and then it stops"], "length")
    ev = _stream(loop, {"message": MSG, "language": "cy-GB", "country": "GB"})
    done = [e for e in ev if e["type"] == "done"][-1]
    assert "Part one" in done["full_text"] and "continue" in done["full_text"].lower()
    assert len(calls["completion"]) == 0


def test_stream_pro_gets_thinking_budget(env):
    loop, uid, calls, mp = env
    loop.run_until_complete(server.db.users.update_one({"id": uid}, {"$set": {"tier": "pro"}}))
    u = {**server.app.dependency_overrides[server.get_user](), "tier": "pro", "comp_pro_until": "2099-01-01T00:00:00+00:00"}
    server.app.dependency_overrides[server.get_user] = lambda: u
    _mock_stream(mp, calls, ["Complete answer."], "stop")
    _stream(loop, {"message": MSG, "language": "en-GB", "country": "GB"})
    kw = calls["stream"][0]
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["max_tokens"] == 2600 and kw["extra_body"]["thinking"]["budget_tokens"] == 1024


def test_free_gets_concise_suffix_pro_does_not(env):
    loop, uid, calls, mp = env
    _mock_stream(mp, calls, ["Short complete answer. [CONFIDENCE: HIGH]"], "stop")
    _stream(loop, {"message": MSG, "language": "en-GB", "country": "GB"})
    assert calls["stream"][0]["messages"][-1]["content"].endswith(lex_output.CONCISE_SUFFIX)
    assert lex_output.concise_suffix("claude-sonnet-5-5") == "" and lex_output.concise_suffix("gpt-5.2") == ""
    saved = loop.run_until_complete(server.db.conversations.find_one({"user_id": uid}))
    assert "Answer format" not in (server.decrypt_text(saved["user_message"]) or "")


def test_et_transitional_caveat():
    import deadline_calc as dc
    t = dc.compute([{"type": "employment_tribunal", "event_date": "2026-08-01", "jurisdiction": "england"}])[0][0]
    assert "transitional rules" in t and "do not assume the claim is out of time" in t
    assert "Wages Act 1986 was repealed" in server.LEX_LAW_UPDATES
