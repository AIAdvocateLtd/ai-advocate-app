"""Lex 2.0 topic-based legislation research + EU law + Tavily-exhaustion handling.
Mocked tests run offline; the live test (official sources only, free) checks every mapped reference resolves.
Run: cd /app/backend && AIA_NO_PAID=1 python -m pytest tests/test_legal_research.py -q"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eu_law  # noqa: E402
import legal_research as R  # noqa: E402
import legal_sources as L  # noqa: E402
import official_guidance  # noqa: E402
import rag  # noqa: E402

ORIG_GUIDANCE = official_guidance.guidance_sources
LOOP = asyncio.new_event_loop()
run = LOOP.run_until_complete


def clml(sec, ext="E+W+S", text="The employee has the right.", prospective=False, repeal=False, pending=False):
    st = ' Status="Prospective"' if prospective else ""
    body = "<Repeal CommentaryRef=\"c1\"/>" if repeal else ""
    aff = f'<ukm:UnappliedEffect AffectedProvisions="s. {sec}"/>' if pending else ""
    return (f'<Legislation><dct:valid>2026-10-01</dct:valid>{aff}<P1group RestrictExtent="{ext}"{st}>'
            f'<P1 id="section-{sec}">{text}{body}</P1></P1group><Commentary id="c1">Repealed by X</Commentary></Legislation>')


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    asyncio.set_event_loop(LOOP)
    L._cache.clear()
    eu_law._cache.clear()
    monkeypatch.setattr(rag, "is_enabled", lambda: False)

    async def no_guidance(*a, **k):
        return [], []
    monkeypatch.setattr(official_guidance, "guidance_sources", no_guidance)
    yield


def fake(monkeypatch, pages):
    calls = []

    async def f(url):
        calls.append(url)
        for k, v in pages.items():
            if k in url:
                if isinstance(v, Exception):
                    raise v
                return v
        return 404, ""
    monkeypatch.setattr(L, "_fetch", f)
    return calls


def test_topic_map_without_named_act_and_nation_choice():
    assert R.match_topics("I was sacked yesterday") == ["unfair_dismissal"]
    eng = [p["path"] for p in R.pick("I was sacked yesterday", "england")]
    ni = [p["path"] for p in R.pick("I was sacked yesterday", "northern_ireland")]
    assert eng[0] == "ukpga/1996/18/section/94" and all(p.startswith("nisi/1996/1919") for p in ni)
    wales = [p["path"] for p in R.pick("my landlord kept my deposit", "wales")]
    scot = [p["path"] for p in R.pick("my landlord kept my deposit", "scotland")]
    assert wales == ["anaw/2016/1/section/45"] and all(p.startswith("ssi/2011/176") for p in scot)
    assert "ukpga/2004/34/section/213" not in wales + scot
    assert R.pick("visa expiring, can I stay?", "england")[0]["path"] == "ukpga/1971/77/section/3"
    assert R.pick("refund for a faulty kettle", "scotland")[0]["path"] == "ukpga/2015/15/section/9"


def test_statuses_repealed_prospective_pending_and_wrong_nation(monkeypatch):
    fake(monkeypatch, {"ukpga/1988/50/section/21/": (200, clml("21", "E+W", "…", repeal=True)),
                       "ukpga/1988/50/section/8/": (200, clml("8", "E+W", "Possession grounds.", prospective=True)),
                       "ukpga/1977/43/section/1/": (200, clml("1", "E+W", "Unlawful eviction.", pending=True))})
    out = run(R.topic_sources("my landlord is trying to evict me", "england"))
    titles = " | ".join(s["title"] for s in out["sources"])
    assert out["status"] == "ok"
    assert "REPEALED" in titles or "repealed or changed" in titles
    assert "NOT YET IN FORCE" in titles and "not yet shown in this text" in titles
    r = run(R.read_provision({"path": "ukpga/1977/43/section/1", "label": "x", "nations": ("scotland",)}, "scotland"))
    assert r["verdict"] == "wrong_jurisdiction"


def test_outage_never_claims_research(monkeypatch):
    fake(monkeypatch, {"legislation.gov.uk": RuntimeError("down")})
    out = run(R.topic_sources("I was sacked", "england"))
    assert out["status"] == "unavailable" and out["sources"] == []
    res = run(rag.research("I was sacked after 3 years, is that legal?", country="GB", nation="england"))
    assert res["status"] in ("not_configured", "unavailable", "no_results") and not res["citations"]
    assert "does NOT mean no law applies" in res["block"] and "official lookup failed" in res["block"]


def test_no_match_uses_official_search_labelled(monkeypatch):
    feed = ('<feed><entry><title>Bees Act 1980</title><id>http://www.legislation.gov.uk/id/ukpga/1980/12</id></entry></feed>')
    fake(monkeypatch, {"/ukpga/data.feed": (200, feed)})
    out = run(R.topic_sources("rules on keeping bees in my garden", "england"))
    assert out["status"] == "search_only" and "wording NOT retrieved" in out["sources"][0]["title"]
    assert out["sources"][0]["content"] == ""


def test_tavily_quota_cooldown(monkeypatch):
    monkeypatch.setattr(rag, "is_enabled", lambda: True)
    fake(monkeypatch, {})
    calls = []

    async def tav(*a, **k):
        calls.append(1)
        return [], "quota_exhausted"
    monkeypatch.setattr(rag, "_tavily_search_ex", tav)
    rag._quota_until[0] = 0
    r1 = run(rag.research("I was sacked, is it unfair dismissal?", country="GB", nation="england"))
    n = len(calls)
    r2 = run(rag.research("I was sacked, is it unfair dismissal?", country="GB", nation="england"))
    assert n == 2 and len(calls) == n and r2["paid_search"] == "quota_exhausted"
    assert r1["status"] != "ok" or r1["paid_search"] != "ok"
    rag._quota_until[0] = 0


def test_eu_only_for_eu_chats_or_uk_mentions():
    assert eu_law.wanted("my flight was cancelled", "ES")
    assert not eu_law.wanted("my flight was cancelled", "GB")
    assert eu_law.wanted("what does the EU directive say about refunds", "GB")
    assert not eu_law.wanted("refund please", "US")


def test_eu_labels_keep_uk_eu_and_national_law_separate():
    r = {"celex": "32011L0083", "kind": "directive", "label": "Consumer Rights Directive", "articles": [9], "in_force": True, "text": "x"}
    es = eu_law.as_source(r, "ES")["title"]
    gb = eu_law.as_source(r, "GB")["title"]
    assert "Spain's own implementing law" in es and "NOT retrieved" in es
    assert "NOT UK law" in gb
    assert "not connected" in eu_law.national_gap_note("FR") and eu_law.national_gap_note("GB") == ""
    assert "not connected" in eu_law.national_gap_note("US")
    assert "CROSS-BORDER" in eu_law.cross_border_note("I bought it in France but live in England", "GB")
    assert eu_law.cross_border_note("refund in Leeds", "GB") == ""


def test_acas_guidance_uk_only():
    assert run(ORIG_GUIDANCE("I was dismissed, does the Acas Code apply?", "", "US")) == ([], [])


@pytest.mark.skipif(os.environ.get("LIVE_OFFICIAL") != "1", reason="set LIVE_OFFICIAL=1 to hit free official sources")
def test_live_every_mapped_reference_resolves():
    items = [dict(it) for _, _, its in R.TOPICS for it in its]

    async def go():
        sem = asyncio.Semaphore(4)

        async def one(it):
            async with sem:
                return await R.read_provision(it, it["nations"][0])
        return await asyncio.gather(*(one(i) for i in items))
    res = run(go())
    assert all(r["verdict"] not in ("not_found", "wrong_jurisdiction") for r in res), [r["path"] for r in res if r["verdict"] == "not_found"]
    eu = run(asyncio.gather(*(eu_law.read_act(a) for _, acts in eu_law.TOPICS for a in acts)))
    assert all(not r.get("failed") and r["text"] for r in eu)
