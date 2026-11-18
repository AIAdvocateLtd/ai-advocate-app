"""Phase 2E targeted legal-accuracy corrections — offline (no AI calls, legislation.gov.uk mocked)."""
import asyncio
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deadline_calc as dc  # noqa: E402
import landmark_cases  # noqa: E402
import legal_sources as LS  # noqa: E402
import lex_guidance as G  # noqa: E402
import lex_safety as L  # noqa: E402
from evals.lex_eval_scenarios import SCENARIOS  # noqa: E402

TODAY = date(2026, 11, 18)


# ---------------------------------------------------------------- employment tribunal limits
def _et(ev, j="england"):
    return " ".join(t for t, _, _ in dc._et({"event_date": ev, "jurisdiction": j}))


def test_et_six_months_on_or_after_1_october_2026():
    t = _et("2026-10-20")
    assert "6 months less one day" in t and "Monday 19 April 2027" in t and "SI 2026/954" in t


def test_et_three_months_before_1_october_and_no_invented_transitional_rule():
    t = _et("2026-09-15")
    assert "3 months less one day" in t and "before 1 October 2026" in t
    assert "transitional rules may give" not in t


def test_et_scotland_breach_of_contract_exception():
    assert "has 3 months less one day for a breach on this date" in _et("2026-11-01", "scotland")
    assert "has 6 months less one day for a breach on this date" in _et("2026-11-10", "scotland")
    assert "9 November 2026" not in _et("2026-11-10", "england")


def test_et_series_and_continuing_acts_note():
    assert "series of deductions" in _et("2026-10-20") and "end of that period" in _et("2026-10-20")


def test_ni_uses_lra_and_not_gb_six_months():
    t = _et("2026-10-20", "northern_ireland")
    assert "Labour Relations Agency" in t and "does not apply to most Northern Ireland" in t and "6 months less" not in t


# ---------------------------------------------------------------- deadline annotations
def test_expired_et_deadline_flagged_without_saying_out_of_time():
    items = dc.annotate("employment_tribunal", dc._et({"event_date": "2026-01-05", "jurisdiction": "england"}), TODAY, False)
    t = items[0][0]
    assert "ALREADY PASSED" in t and "never say the claim is definitely out of time" in t and "INDEPENDENT CHECK" in t


def test_urgent_and_approximate_flags():
    items = dc.annotate("consumer_purchase", [("x", "t", date(2026, 11, 22))], TODAY, True)
    assert "URGENT: only 4 day(s) left" in items[0][0] and "APPROXIMATE date" in items[0][0]


def test_court_claim_flagged_for_independent_review():
    items = dc.annotate("court_claim", dc._court_claim({"jurisdiction": "england", "service_date": "2026-11-20"}), TODAY, False)
    assert "INDEPENDENT CHECK" in items[0][0] and "court procedural deadline" in items[0][0]


def test_parking_unknown_service_gives_rule_not_reminder_and_flags_passed():
    out = dc._parking({"notice_date": "2026-01-01", "issuer": "council", "served": "unknown", "jurisdiction": "england"})
    assert out[0][2] is None and "ALREADY PASSED" in out[0][0] and "21 days run from the date of service" in out[0][0]


def test_relative_dates_resolved_approximately():
    r = " ".join(dc.relative_dates("I bought a laptop 3 weeks ago", TODAY))
    assert "Wednesday 28 October 2026" in r and "either side" in r
    assert dc.relative_dates("I bought it on 3 November", TODAY) == []


def test_extraction_prompt_asks_for_approx_flag():
    assert '"approx": true' in dc.EXTRACT_SYSTEM


# ---------------------------------------------------------------- case citations
def _v(text, src="", cust=""):
    cites = []
    out, rep = L.verify_citations(text, cites, [{"n": 1, "title": "s", "content": src}] if src else [], cust)
    return out, rep, cites


def test_landmark_cases_kept_with_sourced_citation_entry():
    out, rep, cites = _v("In ParkingEye Ltd v Beavis [2015] UKSC 67 the charge was upheld.")
    assert "ParkingEye Ltd v Beavis [2015] UKSC 67" in out and rep["case_refs_removed"] == 0
    assert cites and "not reviewed by a qualified lawyer" in cites[0]["title"] and cites[0]["url"].startswith("https://www.bailii.org")


def test_volume_citations_kept_and_no_fragments():
    t = "See Bolam v Friern Hospital Management Committee [1957] 1 WLR 582 and Bolitho v City and Hackney Health Authority [1998] AC 232."
    out, rep, _ = _v(t)
    assert out == t and rep["case_refs_removed"] == 0


def test_invented_case_with_volume_removed_without_leftovers():
    out, rep, _ = _v("Zork v Blarg [1957] 2 All ER 118 decided it.")
    assert "[1957]" not in out and "Blarg" not in out and "All ER" not in out and rep["case_refs_removed"] == 1


def test_wrong_citation_for_real_case_is_stripped():
    out, _, _ = _v("ParkingEye v Beavis [2019] UKSC 12 says so.")
    assert "ParkingEye v Beavis says so." in out and "[2019]" not in out


def test_fabricated_case_still_rejected_and_separate_party_names_do_not_support():
    out, rep, _ = _v("Smith v Jones [2023] UKSC 99 says refunds in 7 days.", src="Smith appeared. Later Jones spoke.",
                     cust="Smith v Jones [2023] UKSC 99")
    assert "(unverified case reference" in out and rep["case_refs_labelled"] == 1


def test_case_supported_when_source_names_both_parties_together():
    out, rep, _ = _v("Brown v Green [2021] EWCA Civ 1234 applies.", src="In Brown v Green the Court of Appeal held")
    assert "Brown v Green" in out and rep["case_refs_removed"] == 0


def test_unrecognised_case_id_removed_from_sources_line():
    out, rep, _ = _v("Answer.\n[SOURCES: Matrimonial Causes Act 1973 s.1; Ferrara v Ferrara [UKSC 2026/0095]]")
    assert out.endswith("[SOURCES: Matrimonial Causes Act 1973 s.1]") and rep["sources_line_pruned"] == 1


def test_non_case_v_phrases_untouched():
    t = "It is England v Wales on Saturday."
    assert _v(t)[0] == t


def test_landmark_list_shape():
    assert 38 <= len(landmark_cases.CASES) <= 45
    assert all(e[4].startswith("https://www.bailii.org/") and e[3] for e in landmark_cases.CASES)
    assert "professionally verified" not in open(landmark_cases.__file__).read()


# ---------------------------------------------------------------- legislation existence checks (mocked)
WELSH_FEED = ('<feed><entry><id>http://www.legislation.gov.uk/id/anaw/2016/1</id><title type="xhtml"><div>'
              '<span xml:lang="en">Renting Homes (Wales) Act 2016</span> / <span xml:lang="cy">Deddf</span></div></title></entry></feed>')
SI_FEED = ('<feed><entry><id>http://www.legislation.gov.uk/id/uksi/2021/743</id><title>The British Nationality Act 1981 '
           '(Immigration Rules Appendix EU) (Amendment) Regulations 2021</title></entry></feed>')


def _fake(monkeypatch):
    async def fetch(url):
        if "/primary/2016/" in url and "Renting" in url:
            return 200, WELSH_FEED
        if "/secondary/2021/" in url and "British" in url:
            return 200, SI_FEED
        if "data.feed" in url:
            return 200, "<feed></feed>"
        return 404, ""
    LS._cache.clear()
    monkeypatch.setattr(LS, "_fetch", fetch)


def test_welsh_bilingual_title_resolves(monkeypatch):
    _fake(monkeypatch)
    assert asyncio.run(LS.resolve_act("Renting Homes (Wales) Act", "2016"))["id"] == "anaw/2016/1"


def test_statutory_instruments_checked_and_fabrications_pruned(monkeypatch):
    _fake(monkeypatch)
    txt = ("The Consumer Rights (Faulty Laptops) Regulations 2024 give you 45 days.\n"
           "[SOURCES: The British Nationality Act 1981 (Immigration Rules Appendix EU) (Amendment) Regulations 2021; "
           "Consumer Rights (Faulty Laptops) Regulations 2024; Immigration Rules]")
    assert [r["label"] for r in LS.extract_refs(txt)] == []  # Act inside an SI title is not checked on its own
    cites = []
    out, rep = asyncio.run(LS.check_answer(txt, "england", cites))
    assert "[SOURCES: The British Nationality Act 1981 (Immigration Rules Appendix EU) (Amendment) Regulations 2021; Immigration Rules]" in out
    assert "could not be found on legislation.gov.uk under that title" in out and "[⚠ see legislation check]" in out
    assert any("existence checked only" in c["title"] and c["url"].endswith("uksi/2021/743") for c in cites)
    assert {s["verdict"] for s in rep["statutory_instruments"]} == {"si_exists", "not_found"}


def test_short_term_cache_is_days_not_weeks():
    assert LS.ACT_TTL == 3 * 86400


# ---------------------------------------------------------------- official-source rules
def test_wales_tenancy_rule_for_section_21_question():
    b = G.block("My landlord in Swansea sent a section 21 notice. Do I have to leave in 2 months?", "", "wales")
    assert "section 173" in b and "6 months" in b and "does not apply" in b and "NOT yet reviewed" in b


def test_ni_employment_signposts_lra_not_acas_rule():
    ids = [r[0] for r in G.matched("I work in Belfast and was dismissed after 18 months", "", "northern_ireland")]
    assert ids == ["ni_employment"]


def test_gb_dismissal_gets_dated_et_rule_and_plus_extra():
    b = G.block("I was sacked on 20 October 2026", "", "england", "openai")
    assert "on or after 1 October 2026" in b and G.PLUS_EXTRA in b
    assert G.PLUS_EXTRA not in G.block("I was sacked on 20 October 2026", "", "england", "anthropic")


def test_substantive_gaps_covered():
    assert "NO right of appeal" in G.block("My visitor visa was refused", "", "england")
    assert "independent adviser" in G.block("settlement agreement sign by Friday", "", "england")
    assert "20 weeks" in G.block("I want to divorce my husband", "", "england")
    assert "18th birthday" in G.block("My son was injured at birth 9 years ago. Is it too late?", "", "england")


def test_no_uk_rules_for_non_uk_country_or_unrelated_question():
    assert G.block("I was sacked yesterday", "", None, None, "ES") == ""
    assert G.block("Hello", "", "england") == ""


# ---------------------------------------------------------------- wiring and reference standards
def test_server_wiring_and_prompt_example():
    src = open(os.path.join(os.path.dirname(LS.__file__), "server.py")).read()
    assert src.count("lex_guidance.block(") == 5 and "Smith v Jones [2019] EWCA Civ 123" not in src


def test_reference_standards_corrected_and_labelled():
    by = {s["id"]: s for s in SCENARIOS}
    assert any("six-month" in d and "SI 2026/954" in d for d in by["EMP-01"]["deadlines"])
    assert any("3 months as the limit for a dismissal on/after 1 Oct 2026" in f for f in by["EMP-01"]["fail"])
    assert all("NONE has been reviewed by a qualified UK lawyer" in s["reference_status"] for s in SCENARIOS)
    assert all(s["date"] == "2026-11-18" for s in SCENARIOS)


# ---------------------------------------------------------------- chat wiring (mocked model, all tiers)
import pytest  # noqa: E402
from tests.test_lex2_2a2_injection import _stream, _fakes, events  # noqa: E402,F401
from tests.test_lex2_2a3_high_stakes import mk  # noqa: E402,F401


@pytest.mark.parametrize("tier,model_part", [("free", "haiku"), ("plus", "gpt-5.2"), ("pro", "sonnet")])
def test_chat_prompt_gets_official_rules_and_models_unchanged(tier, model_part, mk, monkeypatch):  # noqa: F811
    _, seen = _stream(mk(tier), monkeypatch, "Answer.", message="My landlord in Swansea sent a section 21 notice. Do I have to leave in 2 months?")
    system = seen["messages"][0]["content"]
    assert "OFFICIAL-SOURCE RULES" in system and "section 173" in system and "ANSWER DIRECTNESS" in system
    assert (G.PLUS_EXTRA in system) is (tier == "plus")
    assert model_part in str(seen["model"]).lower()


# ---------------------------------------------------------------- claim types + sourced case list in prompt
def test_et_claim_types_adjust_rule():
    rp = dc._et({"event_date": "2026-09-01", "jurisdiction": "england", "claim_type": "redundancy_pay"})[0]
    assert "6 months less one day" in rp[0] and "s.164" in rp[0]
    sb = dc._et({"event_date": "2026-11-01", "jurisdiction": "scotland", "claim_type": "breach_of_contract"})[0]
    assert "3 months less one day" in sb[0] and "9 November 2026" in sb[0]
    eq = dc._et({"event_date": "2026-10-20", "jurisdiction": "wales", "claim_type": "equal_pay"})
    assert eq[0][2] is None and "s.129" in eq[0][0]
    assert "CLAIM TYPE NOT CONFIRMED" in _et("2026-10-20")
    assert "CLAIM TYPE NOT CONFIRMED" not in " ".join(
        t for t, _, _ in dc._et({"event_date": "2026-10-20", "jurisdiction": "england", "claim_type": "unfair_dismissal"}))
    assert '"claim_type":' in dc.EXTRACT_SYSTEM


def test_sourced_cases_offered_in_prompt_by_topic():
    b = G.block("A private parking company charged me £100", "", "england")
    assert "SOURCED CASE LIST" in b and "ParkingEye Ltd v Beavis [2015] UKSC 67" in b and "NOT reviewed by" in b
    assert "Bolam" in G.block("My GP missed my cancer — negligence?", "", "england")
    assert G.block("A private parking company charged me £100", "", "england", None, "FR") == ""


# ---------------------------------------------------------------- defects found in the 45-answer retest (false "not found")
def test_short_names_commas_and_memorandum_prefix_resolve(monkeypatch):
    feeds = {"/primary/1988/": '<feed><entry><id>http://www.legislation.gov.uk/id/ukpga/1988/50</id><title>Housing Act 1988</title></entry></feed>',
             "/primary/2020/": '<feed><entry><id>http://www.legislation.gov.uk/id/ukpga/2020/11</id><title>Divorce, Dissolution and Separation Act 2020</title></entry></feed>',
             "/secondary/2014/": '<feed><entry><id>http://www.legislation.gov.uk/id/uksi/2014/2604</id><title>The Tribunal Procedure (First-tier Tribunal) (Immigration and Asylum Chamber) Rules 2014</title></entry></feed>',
             "/secondary/2010/": '<feed><entry><id>http://www.legislation.gov.uk/id/uksi/2010/908</id><title>The Assured Tenancies (Amendment)(England) Order 2010</title></entry></feed>'}

    async def fetch(url):
        return 200, next((v for k, v in feeds.items() if k in url), "<feed></feed>")
    LS._cache.clear()
    monkeypatch.setattr(LS, "_fetch", fetch)
    t = ("Divorce, Dissolution and Separation Act 2020 applies. In England, Wales and Scotland the Housing Act 1988 differs.\n"
         "See the First\u2011tier Tribunal (Immigration and Asylum Chamber) Rules 2014 and the Explanatory Memorandum to the "
         "Assured Tenancies (Amendment) (England) Order 2010.")
    assert [r["label"] for r in LS.extract_refs(t)] == ["Divorce, Dissolution and Separation Act 2020", "Housing Act 1988"]
    out, rep = asyncio.run(LS.check_answer(t, "england", []))
    assert {s["verdict"] for s in rep["statutory_instruments"]} == {"si_exists"}
    assert rep["verdicts"][0] == "act_exists" and "could not be found" not in out
    assert LS._title_match("Fake Tribunal Rules 2014", "The Tribunal Procedure (First-tier Tribunal) Rules 2014") is None
