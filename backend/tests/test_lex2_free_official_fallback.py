"""Free official lookups continue when paid web search can't run (simulated; run with AIA_NO_PAID=1)."""
import asyncio

import legal_sources
import official_guidance
import rag

Q = "My employer dismissed me for poor performance. Employment Rights Act 1996, section 98. Does the Acas Code apply?"
LEG = [{"title": "Employment Rights Act 1996, section 98 (legislation.gov.uk — status: in force; full wording retrieved)",
        "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/98", "content": "98 General. (4) ... reasonably ..."}]
ACAS = [{"title": "Acas Code of Practice — acas.org.uk (official guidance; wording retrieved 11 November 2026)",
         "url": "https://www.acas.org.uk/acas-code-of-practice-on-disciplinary-and-grievance-procedures/html",
         "content": "Disciplinary situations include misconduct and/or poor performance.", "acas_key": "code"}]


def _free(monkeypatch, leg=LEG, acas=ACAS, failed=()):
    async def g(*a, **k):
        return list(leg)

    async def a(*x, **k):
        return list(acas), list(failed)
    monkeypatch.setattr(legal_sources, "grounding_sources", g)
    monkeypatch.setattr(official_guidance, "guidance_sources", a)


def _paid_must_not_run(monkeypatch):
    calls = []

    async def tav(*a, **k):
        calls.append(1)
        return [], "ok"
    monkeypatch.setattr(rag, "_tavily_search_ex", tav)
    return calls


class CapDB:
    """Monthly paid-search cap already reached."""
    class _C:
        async def find_one(self, *a, **k):
            return {"count": 10 ** 9}

        async def update_one(self, *a, **k):
            raise AssertionError("usage must not be incremented when paid search is skipped")
    tavily_usage = _C()


def test_cap_reached_free_lookups_still_used(monkeypatch):
    _free(monkeypatch)
    calls = _paid_must_not_run(monkeypatch)
    monkeypatch.setattr(rag, "is_enabled", lambda: True)
    monkeypatch.setattr(rag, "_under_cap", lambda db: asyncio.sleep(0, result=False))
    r = asyncio.run(rag.research(Q, db=CapDB()))
    assert calls == [] and r["status"] == "ok" and r["paid_search"] == "quota_exhausted"
    assert [c["url"] for c in r["citations"]] == [LEG[0]["url"], ACAS[0]["url"]]
    assert "only the free official lookups above" in r["block"] and "could not be checked" in r["block"]
    assert r["guidance_keys"] == ["code"]


def test_no_search_key_free_lookups_still_used(monkeypatch):
    _free(monkeypatch)
    calls = _paid_must_not_run(monkeypatch)
    monkeypatch.setattr(rag, "is_enabled", lambda: False)
    r = asyncio.run(rag.research(Q))
    assert calls == [] and r["status"] == "ok" and r["paid_search"] == "not_configured"


def test_nothing_reachable_discloses(monkeypatch):
    _free(monkeypatch, leg=[], acas=[], failed=["code"])
    _paid_must_not_run(monkeypatch)
    monkeypatch.setattr(rag, "is_enabled", lambda: True)
    monkeypatch.setattr(rag, "_under_cap", lambda db: asyncio.sleep(0, result=False))
    r = asyncio.run(rag.research(Q, db=CapDB()))
    assert r["status"] == "quota_exhausted" and r["citations"] == [] and r["guidance_failed"] == ["code"]
    import lex_safety
    blk = lex_safety.research_block(r["status"], "high", ["employment"])
    assert "MUST NOT say or imply that you checked" in blk
    import official_guidance as G
    out, notes = G.disclose("The Acas Code of Practice covers poor performance.", r["guidance_keys"], r["guidance_failed"])
    assert notes and "could not be retrieved" in notes[0]


def test_paid_search_normal_when_available(monkeypatch):
    _free(monkeypatch)
    calls = []

    async def tav(q, include_domains=None, max_results=3, search_depth="basic"):
        calls.append(include_domains)
        return [], "ok"
    monkeypatch.setattr(rag, "_tavily_search_ex", tav)
    monkeypatch.setattr(rag, "is_enabled", lambda: True)
    r = asyncio.run(rag.research(Q))
    assert len(calls) == 2 and r["paid_search"] == "ok" and "only the free official lookups" not in r["block"]


def test_free_lookups_bounded_and_cached():
    assert legal_sources.MAX_REFS == 6 and official_guidance.MAX_PAGES == 2
    assert official_guidance.OK_TTL == 24 * 3600 and legal_sources.STATUS_TTL >= 3600
