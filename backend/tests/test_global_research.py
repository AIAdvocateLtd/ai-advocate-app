"""Lex 2.0 global research engine — acceptance tests. Live calls go only to free official sources (gesetze-im-internet.de,
BOE, Normattiva, Sejm ELI, govinfo/eCFR, legislation.gov.uk). AI and Tavily are mocked. Retrieval success is NOT proof
that Lex's legal interpretation is correct — these tests check jurisdiction, retrieval, labelling and honesty."""
import asyncio
import time

import pytest

import global_law as G
import national_law as N
import rag

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


_LOOP = asyncio.new_event_loop()


def run(c):
    return _LOOP.run_until_complete(c)


# ---------- jurisdiction identification (ordinary questions, no legislation named) ----------
@pytest.mark.parametrize("q,sel,primary,others,state", [
    ("My landlord in Berlin wants me out of my flat", "GB", "DE", {"GB"}, None),
    ("Mi casero en Madrid no me devuelve la fianza", "ES", "ES", set(), None),
    ("Mój pracodawca w Warszawie mnie zwolnił", "GB", "PL", {"GB"}, None),
    ("My landlord in Texas won't return my security deposit", "US", "US", set(), "TX"),
    ("I rent an apartment in NYC and the heating is broken", "US", "US", set(), "NY"),
    ("My employer in Baghdad fired me", "GB", "IQ", {"GB"}, None),
    ("Does German law let my landlord in London keep the deposit?", "GB", "DE", {"GB"}, None),
    ("My boss fired me yesterday", "FR", "FR", set(), None),
    ("Il padrone di casa a Roma vuole sfrattarmi", "IT", "IT", set(), None),
    ("I live in Spain and bought a phone from a German shop", "ES", "ES", {"DE"}, None),
    ("I live in Poland and work for a German company", "GB", "PL", {"DE", "GB"}, None),
])
def test_detects_governing_jurisdiction(q, sel, primary, others, state):
    p = G.detect(q, sel)
    assert p["primary"] == primary
    assert others <= set(p["all"]) - {primary}
    assert p["us_state"] == state
    assert p["cross_border"] == bool(others)


def test_jurisdiction_from_earlier_turn():
    p = G.plan_for("What notice do they have to give?", "I rent a flat in Lisbon", "GB")
    assert p["primary"] == "PT" and p["how"] == "named earlier in the conversation"


def test_language_alone_does_not_change_jurisdiction():
    assert G.detect("Mein Arbeitgeber hat mir gekündigt", "GB")["primary"] == "GB"


def test_coverage_register_is_honest(monkeypatch):
    monkeypatch.delenv("LEGIFRANCE_CLIENT_ID", raising=False)
    assert {j: G.coverage(j) for j in ("GB", "DE", "ES", "IT", "PL", "US")} == dict.fromkeys(
        ("GB", "DE", "ES", "IT", "PL", "US"), "verified")
    assert G.coverage("FR") == "official_site_search"  # Légifrance keys not yet supplied
    assert G.coverage("PT") == "official_site_search" and G.coverage("US", "OH") == "official_site_search"
    assert G.coverage("US", "TX") == "verified" and G.coverage("US", "FL") == "verified"  # direct official state sources
    assert G.coverage("IQ") == "general_only" and G.coverage("CN") == "general_only"


# ---------- live official retrieval of every mapped provision ----------
def test_every_mapped_provision_is_retrievable_from_the_official_source():
    refs = [r for j, m in N.MAP.items() if j != "FR" for rs in m.values() for r in rs]
    sem = asyncio.Semaphore(6)

    async def one(r):
        async with sem:
            return await N.read(r, wait=60)

    async def go():
        return await asyncio.gather(*(one(r) for r in refs))
    res = run(go())
    bad = [(r["j"], r["law"], r["art"], r.get("error")) for r in res if r.get("failed")]
    assert not bad, bad
    for r in res:
        assert r["text"] and r["url"].startswith("https://") and r["version"]
        assert r["status"] in ("in_force", "unknown"), (r["label"], r["status"])


@pytest.mark.parametrize("ref,must", [
    (N.R("DE", "bgb", "573c", "BGB"), "dritten Werktag"),
    (N.R("DE", "kschg", "4", "KSchG"), "drei Wochen"),
    (N.R("ES", N.LRJS, "103", "LRJS"), "veinte días"),
    (N.R("ES", N.LAU, "36", "LAU"), "fianza"),
    (N.R("IT", "legge:1966-07-15;604", "6", "L.604/1966"), "sessanta giorni"),
    (N.R("PL", N.KP, "264", "Kodeks pracy"), "21 dni"),
    (N.R("US", "usc:15", "1692g", "FDCPA"), "thirty-day"),
    (N.R("US", "usc:29", "255", "Portal-to-Portal Act"), "two years"),
    (N.R("US", "cfr:12", "1026.13", "Reg Z"), "billing error"),
])
def test_retrieved_wording_matches_independently_checkable_rules(ref, must):
    r = run(N.read(ref, wait=60))
    assert not r.get("failed"), r.get("error")
    assert must.lower() in r["text"].lower()


def test_dates_and_amendment_warnings_are_reported():
    es = run(N.read(N.R("ES", N.ET, "56", "ET"), wait=60))
    assert "version in force since" in es["version"]
    us = run(N.read(N.R("US", "usc:15", "1692g", "FDCPA"), wait=60))
    assert "annual edition" in us["version"] and "may not be shown" in us["version"]
    pl = run(N.read(N.R("PL", N.PK_CONS, "27", "UPK"), wait=60))
    assert "consolidated text" in pl["version"]
    assert ("WARNING" in pl["version"]) == bool(pl.get("changes_pending"))


def test_wrong_article_is_never_accepted():
    r = run(N.read(N.R("DE", "bgb", "9999", "BGB"), wait=30))
    assert r.get("failed")
    r = run(N.read(N.R("IT", N.CONS_IT, "9999", "CdC"), wait=30))
    assert r.get("failed")  # Normattiva falls back to another article; the check must reject it


# ---------- the engine end-to-end (AI + Tavily mocked) ----------
@pytest.fixture
def no_ai(monkeypatch):
    calls = []

    async def fake(*a, **k):
        calls.append(a)
        return None
    monkeypatch.setattr(G, "_discover", fake)
    return calls


def test_german_question_uses_official_text_without_any_ai_call(no_ai):
    out = run(G.research("Mein Vermieter hat mir wegen Eigenbedarf gekündigt", "", "DE", paid_ok=False))
    assert out["national_ok"].get("DE", 0) >= 2 and not no_ai
    assert all("gesetze-im-internet.de" in s["url"] for s in out["sources"])
    assert any("§ 573" in s["title"] for s in out["sources"])
    assert any("GERMANY LAW" in n for n in out["notes"])


def test_cross_border_keeps_systems_separate(no_ai):
    out = run(G.research("My landlord in Berlin wants me out, I am British", "", "GB", paid_ok=False))
    assert out["plan"]["cross_border"]
    assert any(n.startswith("CROSS-BORDER") for n in out["notes"])
    assert any("national law" in s["title"] for s in out["sources"])


def test_us_state_question_never_answered_with_federal_law(no_ai):
    out = run(G.research("My landlord in Ohio won't return my security deposit", "", "US", paid_ok=False))
    assert not out["sources"]
    note = " ".join(out["notes"])
    assert "Ohio" in note and "Federal law does NOT answer a state-law question" in note
    assert "could NOT retrieve Ohio legislation" in note


def test_us_state_unknown_asks_for_state(no_ai):
    out = run(G.research("My landlord won't give back my deposit", "", "US", paid_ok=False))
    assert any("US STATE NOT IDENTIFIED" in n for n in out["notes"])


def test_us_federal_point_uses_federal_source_even_with_state_named(no_ai):
    out = run(G.research("A debt collector in Florida keeps calling me at work", "", "US", paid_ok=False))
    assert any("govinfo.gov" in s["url"] for s in out["sources"])
    assert any("US FEDERAL LAW" in n for n in out["notes"])


def test_tavily_unavailable_is_disclosed_not_fabricated(no_ai):
    out = run(G.research("O senhorio quer terminar o meu contrato de arrendamento", "", "PT", paid_ok=False))
    assert not out["sources"] and out["meta"]["site"]["PT"] == "search_unavailable"
    assert any("SOURCE LIMITS — PORTUGAL" in n and "unavailable just now" in n for n in out["notes"])


def test_country_without_connection_is_general_information_only(no_ai):
    out = run(G.research("My employer in Baghdad fired me without notice", "", "IQ", paid_ok=False))
    assert not out["sources"]
    assert any("no verified official legal-source connection for Iraq" in n for n in out["notes"])


def test_source_outage_is_disclosed(no_ai, monkeypatch):
    async def down(c, ref):
        raise RuntimeError("simulated outage")
    monkeypatch.setitem(N.CONNECTORS, "ES", down)
    N._cache.clear()
    out = run(G.research("Me han despedido, ¿qué plazo tengo?", "", "ES", paid_ok=False))
    N._cache.clear()
    assert not out["sources"]
    assert any("official lookup returned nothing usable" in n for n in out["notes"])


def test_ai_suggestions_are_kept_only_if_the_official_source_confirms_them(monkeypatch):
    async def fake(text, sel, db):
        return {"primary": "DE", "refs": [{"j": "DE", "law": "bgb", "art": "9998"}, {"j": "DE", "law": "BGB", "art": "626"}]}
    monkeypatch.setattr(G, "_discover", fake)
    out = run(G.research("Mein Chef hat mich heute rausgeworfen, ohne Grund", "", "DE", paid_ok=False))
    assert out["meta"]["ai_used"] and out["meta"]["ai_refs"] == 2 and out["meta"]["ai_verified"] == 1
    (src,) = [s for s in out["sources"] if "AI research step" in s["title"]]
    assert "§ 626" in src["title"] and "CONFIRMED to exist" in src["title"] and "relevance to these facts not confirmed" in src["title"]


def test_uk_gap_uses_ai_step_and_checks_legislation_gov_uk(monkeypatch):
    async def fake(text, sel, db):
        return {"primary": "GB", "refs": [{"j": "GB", "act": "Employment Rights Act", "year": "1996", "section": "94"},
                                           {"j": "GB", "act": "Imaginary Rights Act", "year": "2031", "section": "1"}]}
    monkeypatch.setattr(G, "_discover", fake)
    out = run(G.research("My boss keeps changing my shifts at short notice", "", "GB", paid_ok=False, uk_gap=True))
    assert out["meta"]["ai_verified"] == 1
    assert out["sources"][0]["url"].startswith("https://www.legislation.gov.uk/")


def test_ai_step_can_be_switched_off(monkeypatch):
    called = []

    async def fake(*a):
        called.append(1)
        return None

    class Settings:
        async def find_one(self, q):
            return {"enabled": False}

    class DB:
        app_settings = Settings()
    monkeypatch.setattr(G, "_discover", fake)
    run(G.research("Mein Chef hat mich rausgeworfen", "", "DE", db=DB(), paid_ok=False))
    assert not called


# ---------- automatic source records ----------
class _Coll:
    def __init__(self):
        self.docs, self.inserted = {}, []

    async def find_one(self, q, p=None):
        return self.docs.get(q["_id"])

    async def update_one(self, q, u, upsert=False):
        d = self.docs.setdefault(q["_id"], {})
        d.update(u["$set"])

    async def insert_one(self, d):
        self.inserted.append(d)


class _DB:
    def __init__(self):
        self.legal_source_records, self.legal_source_changes = _Coll(), _Coll()


def test_source_versions_are_fingerprinted_and_changes_queued_for_review():
    db = _DB()
    N.set_db(db)
    ref = N.R("DE", "bgb", "573", "BGB")
    try:
        run(N._record(ref, {"text": "Fassung A", "url": "u", "status": "in_force"}))
        run(N._record(ref, {"text": "Fassung A", "url": "u", "status": "in_force"}))
        assert not db.legal_source_changes.inserted
        run(N._record(ref, {"text": "Fassung B", "url": "u", "status": "in_force"}))
    finally:
        N.set_db(None)
    (chg,) = db.legal_source_changes.inserted
    assert chg["status"] == "needs_review" and "qualified reviewer" in chg["note"]


# ---------- integration with Lex's research pipeline, cost and latency ----------
def test_rag_routes_foreign_questions_to_national_sources_not_uk_web_search(monkeypatch, no_ai):
    tav = []

    async def fake_tavily(q, **k):
        tav.append(k.get("include_domains"))
        return [], "ok"
    monkeypatch.setattr(rag, "_tavily_search_ex", fake_tavily)
    monkeypatch.setattr(rag, "is_enabled", lambda: True)
    rag._quota_until[0] = 0
    r = run(rag.research("Mi casero no me devuelve la fianza del piso", country="ES"))
    assert not tav  # UK-domain and general web searches skipped; BOE answered
    assert any("boe.es" in c["url"] for c in r["citations"])
    assert "JURISDICTION ANALYSIS" in r["block"] and r["paid_search"] == "not_needed"
    assert r["global_research"]["det_ok"] >= 1


def test_cached_lookups_are_fast():
    ref = N.R("DE", "bgb", "551", "BGB")
    run(N.read(ref, wait=60))
    t = time.monotonic()
    run(N.read(ref))
    assert time.monotonic() - t < 0.05
    t = time.monotonic()
    out = run(G.research("Mein Vermieter behält die Kaution", "", "DE", paid_ok=False))
    assert out["sources"] and time.monotonic() - t < 2.0


def test_national_citations_in_answers_are_checked_against_official_sources():
    cites = []
    text = "Nach § 573 BGB muss ... und nach § 9997 BGB gilt ... sowie 15 U.S.C. § 1692g."
    out, rep = run(N.check_citations(text, cites))
    assert rep["verdicts"] == ["found", "not_found", "found"]
    assert "§ 9997 BGB [⚠ unverified]" in out and "National law check" in out
    assert any("gesetze-im-internet.de/bgb/__573" in c["url"] for c in cites)
    assert all("does not confirm Lex's interpretation" in c["title"] for c in cites)


def test_each_retrieved_provision_has_its_own_link_so_none_is_dropped(no_ai):
    run(N.read(N.R("PL", N.KP, "264", "Kodeks pracy"), wait=60))  # production prewarms at start-up
    out = run(G.research("Pracodawca mnie zwolnił, ile mam czasu na odwołanie?", "", "PL", paid_ok=False))
    urls = [s["url"] for s in out["sources"]]
    assert len(urls) == len(set(urls)) >= 3
    assert any("21 dni" in s["content"] for s in out["sources"])


def test_official_text_overrides_memory_and_deadlines_are_not_invented(no_ai):
    out = run(G.research("Pracodawca mnie zwolnił, ile mam czasu?", "", "PL", paid_ok=False))
    notes = " ".join(out["notes"])
    assert "OVERRIDES YOUR MEMORY" in notes and "never the remembered rule" in notes
    assert "NATIONAL DEADLINES" in notes and "do not give a number from memory" in notes


def test_slow_national_research_never_wipes_the_other_sources(monkeypatch):
    async def slow(*a, **k):
        await asyncio.sleep(30)
    monkeypatch.setattr(G, "research", slow)
    monkeypatch.setattr(rag, "is_enabled", lambda: False)
    t = time.monotonic()
    r = run(rag.research("Mi casero no me devuelve la fianza", country="ES"))
    assert time.monotonic() - t < 9.8
    assert "did not finish in time" in r["block"]


def test_german_source_outage_falls_back_to_federal_neuris_service():
    N._cache.clear()
    N._gii_down[0] = time.time() + 600  # gesetze-im-internet.de unreachable (seen from production network)
    try:
        r = run(N.read(N.R("DE", "kschg", "4", "KSchG"), wait=60))
        assert not r.get("failed") and "rechtsinformationen.bund.de" in r["url"] and "drei Wochen" in r["text"]
        b = run(N.read(N.R("DE", "bgb", "573", "BGB"), wait=60))
        assert not b.get("failed") and "official XML from gesetze-im-internet.de" in b["version"]  # BGB not on NeuRIS: bundled copy
    finally:
        N._gii_down[0] = 0
        N._cache.clear()


def test_german_civil_code_served_from_bundled_official_download_when_live_sources_fail(monkeypatch):
    N._cache.clear()
    N._gii_down[0] = time.time() + 600

    async def neuris_down(c, ref):
        raise RuntimeError("law not found on NeuRIS")
    monkeypatch.setattr(N, "_de_neuris", neuris_down)
    try:
        r = run(N.read(N.R("DE", "bgb", "573c", "BGB"), wait=60))
        assert not r.get("failed") and "dritten Werktag" in r["text"]
        assert "official XML from gesetze-im-internet.de" in r["version"] and "newer changes cannot be ruled out" in r["version"]
        assert run(N.read(N.R("DE", "bgb", "99999", "BGB"), wait=30)).get("failed")  # absent provision still rejected
    finally:
        N._gii_down[0] = 0
        N._cache.clear()


# ---------- source-driven national deadlines ----------
import national_deadlines as D
from datetime import date as _d


@pytest.mark.parametrize("j,trigger,expected,shifted", [
    ("PL", _d(2026, 3, 3), _d(2026, 3, 24), False),
    ("PL", _d(2026, 10, 10), _d(2026, 11, 2), True),   # 31 Oct is Saturday, 1 Nov holiday/Sunday
    ("DE", _d(2026, 10, 2), _d(2026, 10, 23), False),  # same weekday three weeks later (§ 188(2) BGB)
    ("DE", _d(2025, 12, 4), _d(2025, 12, 29), True),   # 25/26 Dec holidays, then weekend (§ 193 BGB)
    ("ES", _d(2026, 12, 1), _d(2026, 12, 31), False),  # 20 días hábiles, 8 and 25 Dec excluded
    ("IT", _d(2026, 3, 2), _d(2026, 5, 1), False),
])
def test_deadline_arithmetic(j, trigger, expected, shifted):
    c = D.compute(j, trigger)
    assert c["end"] == expected and bool(c["shifted_from"]) == shifted


def test_deadline_dates_are_switched_off_by_default(monkeypatch):
    monkeypatch.delenv("LEX_NATIONAL_DEADLINE_CALC", raising=False)
    src = [{"j": "PL", "law": "DU/1974/141", "art": "264", "label": "Kodeks pracy — Art. 264", "text": "w ciągu 21 dni od dnia doręczenia"}]
    note = D.block("PL", src, "Dostałem wypowiedzenie 3 marca 2026", _d(2026, 3, 10))
    assert "SWITCHED OFF pending qualified legal review" in note and "“21 dni”" in note
    assert "24/03/2026" not in note and "ESTIMATE" not in note and "art. 115" not in note


def test_deadline_estimate_only_with_retrieved_source_and_explicit_date(monkeypatch):
    monkeypatch.setenv("LEX_NATIONAL_DEADLINE_CALC", "on")
    src = [{"j": "PL", "law": "DU/1974/141", "art": "264", "label": "Kodeks pracy — Art. 264", "text": "w ciągu 21 dni od dnia doręczenia"}]
    est = D.block("PL", src, "Dostałem wypowiedzenie 3 marca 2026", _d(2026, 3, 10))
    assert "APP ESTIMATE, NOT A VERIFIED DATE" in est and "24/03/2026" in est and "art. 265" in est
    assert "do NOT give a calendar date" in D.block("PL", src, "Dostałem wypowiedzenie w zeszłym tygodniu")
    assert "was not retrieved" in D.block("PL", [], "3 marca 2026")
    wrong = [{**src[0], "text": "w ciągu 7 dni"}]  # source text does not contain the expected period
    assert "was not retrieved and checked" in D.block("PL", wrong, "3 marca 2026")


def test_engine_adds_deadline_note_for_dismissal_with_official_text(no_ai, monkeypatch):
    monkeypatch.setenv("LEX_NATIONAL_DEADLINE_CALC", "on")
    out = run(G.research("Mein Arbeitgeber hat mir gekündigt, Zugang am 02.10.2026. Bis wann Klage?", "", "DE", paid_ok=False))
    note = next(n for n in out["notes"] if n.startswith("SOURCE-DRIVEN DEADLINE"))
    assert "23/10/2026" in note and "NOT A VERIFIED DATE" in note


def test_engine_never_computes_dates_while_switched_off(no_ai, monkeypatch):
    monkeypatch.delenv("LEX_NATIONAL_DEADLINE_CALC", raising=False)
    out = run(G.research("Mein Arbeitgeber hat mir gekündigt, Zugang am 02.10.2026. Bis wann Klage?", "", "DE", paid_ok=False))
    joined = " ".join(out["notes"])
    assert "SWITCHED OFF" in joined and "23/10/2026" not in joined


def test_family_inheritance_immigration_route_to_official_sources(no_ai):
    cases = [("Wir lassen uns scheiden, wie lange muss das Trennungsjahr sein?", "DE", "1566"),
             ("Mi padre murió, ¿qué parte de la herencia es la legítima?", "ES", "808"),
             ("Chcę odrzucić spadek, ile mam czasu?", "PL", "1015"),
             ("Come ottengo il permesso di soggiorno di lungo periodo?", "IT", "Art. 9"),
             ("Can I apply for asylum after one year in the US?", "US", "1158")]
    for q, c, must in cases:
        out = run(G.research(q, "", c, paid_ok=False))
        assert any(must in s["title"] for s in out["sources"]), (q, [s["title"][:60] for s in out["sources"]])


def test_us_state_direct_official_text_for_texas(no_ai):
    out = run(G.research("My landlord in Texas won't return my security deposit", "", "US", paid_ok=False))
    assert any("tcss.legis.texas.gov" in s["url"] and "92.103" in s["title"] for s in out["sources"])
    assert not any("govinfo" in s["url"] for s in out["sources"])


def test_unreviewed_dates_are_removed_from_answers_while_switched_off():
    ans = "Masz 21 dni. Ostatni dzień to 24 marca 2026 (dostałeś pismo 3 marca 2026). Also 2026-03-24 and 24.03.2026."
    out, n = D.guard(ans, "Wypowiedzenie doręczono mi 3 marca 2026")
    assert n == 3 and "24 marca 2026" not in out and "24.03.2026" not in out and "3 marca 2026" in out
    assert "does not yet calculate exact deadline dates" in out


def test_dates_in_retrieved_official_text_are_kept():
    src = "Ustawa z dnia 26 czerwca 1974 r. Kodeks pracy ... Kündigungsschutzgesetz vom 25. August 1969"
    ans = "Kodeks pracy z dnia 26 czerwca 1974 r.; KSchG vom 25. August 1969. Ostatni dzień to 24 marca 2026."
    out, n = D.guard(ans, "Zwolniono mnie", src)
    assert n == 1 and "26 czerwca 1974" in out and "25. August 1969" in out and "24 marca 2026" not in out



def test_deadline_gate_flag_reaches_the_answer_checks(no_ai, monkeypatch):
    monkeypatch.delenv("LEX_NATIONAL_DEADLINE_CALC", raising=False)
    out = run(G.research("Pracodawca mnie zwolnił 3 marca 2026, do kiedy odwołanie?", "", "PL", paid_ok=False))
    assert out["meta"]["deadline_gate"] is True


def test_periods_must_appear_in_the_cited_official_text():
    blk = ("[1] Kodeks pracy — Art. 264\n    https://x#art-264\n    " + "Odwołanie wnosi się do sądu pracy w ciągu 21 dni od dnia "
           "doręczenia pisma wypowiadającego umowę o pracę. " * 2 + "\n[2] KSchG § 4\n    https://y\n    " +
           "Klage innerhalb von drei Wochen nach Zugang der schriftlichen Kündigung erheben. " * 2)
    out, n = N.check_periods("Masz 7 dni [1]. Albo 21 dni [1]. Binnen 3 Wochen [2], nicht 4 Wochen [2].", blk)
    assert n == 2 and "7 dni [⚠ not in the cited source]" in out and "4 Wochen [⚠" in out
    assert "21 dni [⚠" not in out and "3 Wochen [⚠" not in out


def test_polish_dismissal_wording_without_the_word_employer_is_recognised():
    assert "dismissal" in N.topics("Wypowiedzenie doręczono mi 3 marca 2026. Jaki jest ostatni dzień na odwołanie?")
    assert "dismissal" not in N.topics("Dostałem wypowiedzenie najmu mieszkania")
