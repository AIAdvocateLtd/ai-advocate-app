"""Lex 2.0 Phase 1 — official-source grounding & legislation status checks.
Recorded legislation.gov.uk / Find Case Law responses only; no AI calls, no network.
Run: cd /app/backend && python -m pytest tests/test_lex2_phase1.py -q"""
import asyncio
import os
import sys
import time
from urllib.parse import unquote

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import legal_sources as L  # noqa: E402
import lex_safety  # noqa: E402
import rag  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "legislation")
FEEDS = {("1988", "Housing Act"): "feed_1988_HousingAct.xml", ("1996", "Employment Rights Act"): "feed_1996_EmploymentRightsAct.xml",
         ("2010", "Equality Act"): "feed_2010_EqualityAct.xml", ("2025", "Renters' Rights Act"): "feed_2025_RentersRightsAct.xml",
         ("2016", "Private Housing (Tenancies) (Scotland) Act"): "feed_2016_PrivateHousingTenanc.xml"}
REPEALED_XML = ('<Legislation><dct:valid>2026-10-01</dct:valid><Body RestrictExtent="E+W"><P1group RestrictExtent="E+W">'
                '<P1 id="section-5"><Pnumber>5</Pnumber><Text>. . . <CommentaryRef Ref="c1"/></Text></P1></P1group></Body>'
                '<Commentary id="c1"><Para><Text>S. 5 repealed (1.1.2020) by Example Act 2019</Text></Para></Commentary></Legislation>')
CALLS = []
LOOP = asyncio.new_event_loop()
run = LOOP.run_until_complete


def _read(name):
    return open(os.path.join(FIX, name), encoding="utf-8").read()


async def fake_fetch(url, delay=0.0):
    CALLS.append(url)
    if delay:
        await asyncio.sleep(delay)
    if "/data.feed" in url:
        year = url.split("/primary/")[1].split("/")[0]
        title = unquote(url.split("title=")[1])
        f = FEEDS.get((year, title))
        return 200, (_read(f) if f else "<feed></feed>")
    if "caselaw.nationalarchives" in url:
        return (200, _read("tna_uksc_2020_5.xml")) if "/uksc/2020/5/" in url else (404, "")
    if "ukpga/2019/99/section/5" in url:
        return 200, REPEALED_XML
    name = url.split("legislation.gov.uk/")[1].replace("/data.xml", "").replace("/", "_") + ".xml"
    return (200, _read(name)) if os.path.exists(os.path.join(FIX, name)) else (404, "")


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    L._cache.clear()
    CALLS.clear()
    monkeypatch.setattr(L, "_fetch", fake_fetch)
    monkeypatch.delenv("CASELAW_VERIFY_ENABLED", raising=False)


def _check(label_text, nation):
    refs = L.extract_refs(label_text)
    return run(L.check_refs(refs, nation))


def test_extract_refs_pairs_sections_and_strips_leading_words():
    refs = L.extract_refs("Under section 21 of the Housing Act 1988 your landlord must give notice. "
                          "You may also claim under s.94 Employment Rights Act 1996 and the Equality Act 2010.")
    got = {(r["act"], r["section"]) for r in refs}
    assert got == {("Housing Act", "21"), ("Employment Rights Act", "94"), ("Equality Act", None)}


def test_in_force_section_matching_nation():
    r = _check("Section 94 of the Employment Rights Act 1996 protects you.", "scotland")[0]
    assert r["verdict"] == "in_force" and r["url"].endswith("ukpga/1996/18/section/94") and "E+W+S" in r["extent"]


def test_wrong_jurisdiction_both_directions():
    assert _check("Section 21 of the Housing Act 1988 applies.", "scotland")[0]["verdict"] == "wrong_jurisdiction"
    sc = "Section 51 of the Private Housing (Tenancies) (Scotland) Act 2016 applies."
    assert _check(sc, "england")[0]["verdict"] == "wrong_jurisdiction"
    assert _check(sc, "scotland")[0]["verdict"] == "in_force"


def test_amended_partly_repealed_with_official_detail():
    r = _check("Section 21 of the Housing Act 1988 lets landlords evict.", "england")[0]
    assert r["verdict"] == "partly_repealed" and "Renters" in r["detail"] and "1.5.2026" in r["detail"]


def test_fully_repealed_and_prospective():
    FEEDS[("2019", "Example Act")] = None
    L._put("act:example act:2019", {"id": "ukpga/2019/99", "title": "Example Act 2019"}, 60)
    assert _check("Section 5 of the Example Act 2019 says so.", "england")[0]["verdict"] == "repealed"
    assert _check("Section 70 of the Renters' Rights Act 2025 says so.", "england")[0]["verdict"] == "not_in_force"


def test_missing_sources_not_found():
    assert _check("Section 4 of the Made Up Act 2019 applies.", "england")[0]["verdict"] == "not_found"
    assert _check("Section 999 of the Housing Act 1988 applies.", "england")[0]["verdict"] == "not_found"


def test_failed_lookup_never_gives_certainty(monkeypatch):
    async def boom(url):
        raise RuntimeError("network down")
    monkeypatch.setattr(L, "_fetch", boom)
    text = "[CONFIDENCE: HIGH]\nYou can rely on section 94 of the Employment Rights Act 1996."
    out, rep = run(L.check_answer(text, "england", []))
    assert rep["verdicts"] == ["lookup_failed"]
    assert "could not be checked against legislation.gov.uk" in out and "[CONFIDENCE: MEDIUM]" in out


def test_timeout_is_failed_lookup(monkeypatch):
    monkeypatch.setattr(L, "TIMEOUT", 0.05)
    monkeypatch.setattr(L, "_fetch", lambda url: fake_fetch(url, delay=0.5))
    assert _check("Section 94 of the Employment Rights Act 1996.", "england")[0]["verdict"] == "lookup_failed"


def test_chat_answer_qualified_inline_and_status_checked_citation():
    cites = [{"n": 1, "title": "x", "url": "https://www.gov.uk/x", "source": "official"}]
    text = ("[CONFIDENCE: HIGH]\nYour landlord can use section 21 of the Housing Act 1988. "
            "Unfair dismissal is covered by section 94 of the Employment Rights Act 1996.")
    out, rep = run(L.check_answer(text, "scotland", cites))
    assert "Housing Act 1988 [⚠ see legislation check]" in out and "does not extend to Scotland" in out
    assert "[CONFIDENCE: MEDIUM]" in out
    leg = [c for c in cites if c["source"] == "legislation"]
    assert len(leg) == 1 and leg[0]["claim_check"] == "status_checked" and "verified" not in leg[0]["title"].lower()


def test_document_mode_keeps_letter_body_clean():
    letter = "Dear Sir,\nUnder section 21 of the Housing Act 1988 you must...\nYours faithfully"
    out, _ = run(L.check_answer(letter, "scotland", [], document=True))
    body, notes = out.split("\n\n-----", 1)
    assert "[⚠" not in body and "Notes for you — not part of the letter" in notes


def test_misleading_citation_not_presented_as_verified():
    sources = [{"n": 1, "title": "Equality Act 2010", "content": "Equality Act 2010 section 13 direct discrimination"}]
    cites = [{"n": 1, "title": "Equality Act 2010", "url": "https://www.legislation.gov.uk/ukpga/2010/15/section/13"}]
    text = "Under section 13 of the Equality Act 2010 a landlord must return a deposit within 10 days [1]."
    out, _ = lex_safety.verify_citations(text, cites, sources)
    assert cites[0]["claim_check"] == "reference_found_in_source"
    assert cites[0]["claim_check"] not in ("supported", "verified")


def test_cache_reuses_lookups_and_status_ttl_is_short():
    _check("Section 94 of the Employment Rights Act 1996.", "england")
    n = len(CALLS)
    _check("Section 94 of the Employment Rights Act 1996.", "england")
    assert len(CALLS) == n and L.STATUS_TTL <= 6 * 3600


def test_grounding_returns_actual_section_text_with_status():
    items = run(L.grounding_sources("My landlord served notice under section 21 of the Housing Act 1988", "england"))
    assert items and "repealed/changed" in items[0]["title"] and "Without prejudice" in items[0]["content"]


def test_query_scrubs_personal_data_and_uses_context_and_nation():
    q = rag.build_query("and the deposit? email me at jo@x.com or 07700 900123, NI QQ123456C, my name is Jo Bloggs",
                        "My landlord in Leeds LS1 4AP kept my deposit", "england")
    for bad in ("jo@x.com", "07700", "QQ123456C", "LS1", "Bloggs"):
        assert bad not in q
    assert "landlord" in q and q.endswith("England law")


def test_caselaw_off_by_default_then_checked_when_licensed(monkeypatch):
    text = "See R (UNISON) v Lord Chancellor [2017] UKSC 51 and Example v Test [2020] UKSC 5."
    assert run(L.check_case_citations(text)) == [] and not [c for c in CALLS if "caselaw" in c]
    monkeypatch.setenv("CASELAW_VERIFY_ENABLED", "1")
    res = {r["citation"]: r["verdict"] for r in run(L.check_case_citations(text))}
    assert res == {"[2017] UKSC 51": "not_found", "[2020] UKSC 5": "found"}


def test_latency_concurrent_lookups(monkeypatch):
    monkeypatch.setattr(L, "_fetch", lambda url: fake_fetch(url, delay=0.3))
    text = ("Section 94 of the Employment Rights Act 1996. Section 13 of the Equality Act 2010. "
            "Section 21 of the Housing Act 1988.")
    t0 = time.monotonic()
    run(L.check_answer(text, "england", []))
    assert time.monotonic() - t0 < 1.5
