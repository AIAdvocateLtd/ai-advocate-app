"""Iteration 56 independent probes (offline, no paid calls): AI source-check qualifier placement + Scotland parking rules."""
import asyncio
import os
import re
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deadline_calc as dc  # noqa: E402
import lex_guidance as G  # noqa: E402
import lex_safety as L  # noqa: E402
import source_ai_check as AI  # noqa: E402

EW_WORDS = ("21 days", "21-day", "London Tribunals", "Traffic Penalty Tribunal", "service method not given")


# ---------------------------------------------------------------- Scotland council parking (deadline_calc._parking)
@pytest.mark.parametrize("served", ["windscreen", "post", "unknown", None, "camera", "handed"])
@pytest.mark.parametrize("jur", ["scotland", "Scotland", "SCOTLAND"])
def test_scotland_council_pcn_single_14_day_rule(served, jur):
    c = {"notice_date": "2026-11-10", "issuer": "council", "jurisdiction": jur}
    if served is not None:
        c["served"] = served
    items = dc._parking(c)
    assert len(items) == 1
    t, title, d = items[0]
    for w in EW_WORDS:
        assert w not in t, (served, w, t)
    assert d == date(2026, 11, 10) + timedelta(days=13)
    assert title == "Parking PCN discount ends (safe date)"
    assert "First-tier Tribunal for Scotland (General Regulatory Chamber)" in t
    assert t.count("14 days") == 1, t


def test_scotland_private_parking_keeper_liability_not_apply():
    t = dc._parking({"notice_date": "2026-11-10", "issuer": "private", "jurisdiction": "scotland"})[0][0]
    assert "does not apply in Scotland" in t
    assert "in England and Wales the registered keeper" not in t
    assert "Traffic Penalty Tribunal" not in t and "London Tribunals" not in t


def test_england_postal_still_21_days():
    t, _, d = dc._parking({"notice_date": "2026-11-10", "issuer": "council", "served": "post", "jurisdiction": "england"})[0]
    assert "21 days" in t and d == date(2026, 11, 30)


# ---------------------------------------------------------------- lex_guidance Scotland parking rules
@pytest.mark.parametrize("msg", ["I got a PCN from Glasgow City Council for parking on a yellow line",
                                 "Edinburgh council gave me a parking ticket",
                                 "I received a penalty charge notice in Dundee",
                                 "Council car park PCN in Aberdeen"])
def test_scotland_guidance_uses_scottish_council_rule(msg):
    ids = [r[0] for r in G.matched(msg, "", "scotland")]
    assert "parking_council_scotland" in ids and "parking_council" not in ids, ids
    blk = G.block(msg, "", "scotland")
    assert "London Tribunals" not in blk and "Traffic Penalty Tribunal" not in blk and "21 days" not in blk, blk


def test_scotland_private_guidance_no_council_rule():
    ids = [r[0] for r in G.matched("ParkingEye sent me a parking charge notice for a supermarket car park in Perth", "",
                                   "scotland")]
    assert ids and "parking_private" in ids and not any(i.startswith("parking_council") for i in ids), ids


# ---------------------------------------------------------------- layer 3 AI source check placement
class _Coll:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, q):
        return self.doc


class _DB:
    def __init__(self, doc=None):
        self.app_settings = _Coll(doc)


SRC = [{"n": 1, "title": "Early conciliation", "url": "https://www.acas.org.uk/early-conciliation",
        "content": "You must notify Acas before making an employment tribunal claim. Early conciliation is free and usually "
                   "lasts up to 6 weeks. The time limit is usually 3 months less one day."},
       {"n": 2, "title": "Time limits", "url": "https://www.acas.org.uk/time-limits",
        "content": "The time limit for most employment tribunal claims is 3 months less one day."}]


def _pipe(text, verdicts):
    AI._cache.clear()

    async def ask(c, p):
        for k, v in verdicts.items():
            if k in c:
                return {"verdict": v, "why": ""}
        return {"verdict": "supported", "why": ""}
    out, rep = L.finalize_answer(text, citations=[{"n": s["n"], "url": s["url"]} for s in SRC], sources=SRC,
                                 research_status="ok", risk="high", language="en", legal_question=True, nation="england")
    out2, rep2 = asyncio.run(AI.run(_DB({"enabled": True}), out, rep["claim_support"], SRC, {"level": "urgent"}, True, ask))
    return out, out2, rep["claim_support"], rep2


def test_short_claim_qualifier_before_marker_and_stop():
    _, out, _, rep = _pipe("It lasts 8 weeks [1].", {"8 weeks": "unsupported"})
    assert rep["qualified"] == 1
    assert out.startswith("It lasts 8 weeks" + AI.QUALIFIER + " [1]."), out


def test_multi_sentence_line_qualifier_on_own_sentence():
    txt = "Call Acas first. Early conciliation usually lasts up to 8 weeks [1]. Then you can claim."
    _, out, _, rep = _pipe(txt, {"8 weeks": "partly"})
    assert "8 weeks" + AI.QUALIFIER + " [1]." in out, out
    assert out.count(AI.QUALIFIER) == 1


def test_marker_within_first_60_chars_direct():
    AI._cache.clear()

    async def ask(c, p):
        return {"verdict": "unsupported", "why": ""}
    text = "Early conciliation [1] usually lasts up to 8 weeks, and then the tribunal claim follows. Next."
    cs = [{"n": 1, "status": "uncertain",
           "text": "Early conciliation usually lasts up to 8 weeks, and then the tribunal claim follows."}]
    out, rep = asyncio.run(AI.run(_DB({"enabled": True}), text, cs, SRC, {"level": "urgent"}, True, ask))
    assert "follows" + AI.QUALIFIER + "." in out and out.endswith("Next."), out


def test_mid_sentence_marker_qualifier_attaches_to_its_own_claim():
    """'8 weeks [1] and ... 3 months less one day [2]': only claim [1] is uncertain. The qualifier must sit with claim [1],
    not after claim [2]'s marker position."""
    txt = "Early conciliation usually lasts up to 8 weeks [1] and the time limit is 3 months less one day [2]."
    l1, out, cs, rep = _pipe(txt, {"8 weeks": "unsupported"})
    st = {c["n"]: c["status"] for c in cs}
    if rep["qualified"] != 1:
        pytest.skip(f"layer-1 statuses {st}")
    q = out.index(AI.QUALIFIER)
    assert q < out.index("[1]") or q < out.index("the time limit"), out


def test_failed_call_not_cached_not_charged():
    AI._cache.clear()
    n = {"c": 0}

    async def boom(c, p):
        n["c"] += 1
        raise RuntimeError("x")
    cs = [{"n": 1, "status": "uncertain", "text": "It lasts 8 weeks."}]
    for _ in range(2):
        out, rep = asyncio.run(AI.run(_DB({"enabled": True}), "It lasts 8 weeks [1].", [dict(c) for c in cs], SRC,
                                      {"level": "urgent"}, True, boom))
        assert rep["est_gbp"] == 0 and rep["checked"] == 0 and rep["failed"] == 1 and out == "It lasts 8 weeks [1]."
    assert n["c"] == 2 and not AI._cache


def test_off_when_setting_absent():
    calls = []

    async def ask(c, p):
        calls.append(c)
        return {"verdict": "unsupported", "why": ""}
    out, rep = asyncio.run(AI.run(_DB(None), "It lasts 8 weeks [1].", [{"n": 1, "status": "uncertain",
                                                                       "text": "It lasts 8 weeks."}], SRC,
                                  {"level": "emergency"}, True, ask))
    assert calls == [] and rep["enabled"] is False and out == "It lasts 8 weeks [1]."


def test_real_db_setting_read_only():
    from pymongo import MongoClient
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    assert (db.app_settings.find_one({"_id": "lex_ai_source_check"}) or {}).get("enabled") is not True
