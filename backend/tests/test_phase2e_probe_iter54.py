# Iteration 54 independent probes for Lex 2.0 Phase 2E corrections (no paid calls; legislation _fetch mocked).
import asyncio
import os
from datetime import date

import pytest

os.environ.setdefault("AIA_NO_PAID", "1")
import deadline_calc as dc  # noqa: E402
import landmark_cases as LC  # noqa: E402
import legal_sources as LS  # noqa: E402
import lex_guidance as G  # noqa: E402
import lex_safety as S  # noqa: E402

T = date(2026, 11, 18)


def run(c):
    return asyncio.get_event_loop().run_until_complete(c) if False else asyncio.new_event_loop().run_until_complete(c)


# ---------------------------------------------------------------- guidance: nation + country filtering
def test_guidance_nation_filtering():
    assert "section 173" not in G.block("My landlord sent a section 21 notice", "", "england")
    assert "Labour Relations Agency" not in G.block("I was dismissed", "", "england")
    assert "Labour Relations Agency" in G.block("I was dismissed", "", "northern_ireland")
    ni = [r[0] for r in G.matched("I was dismissed", "", "northern_ireland")]
    assert "et_time_limits" not in ni
    assert "section 173" not in G.block("My landlord sent a section 21 notice", "", None)


@pytest.mark.parametrize("country", ["ES", "US", "IE", "FR"])
def test_guidance_not_for_non_uk(country):
    assert G.block("I was sacked and my landlord evicted me, PCN parking divorce visa", "", "england", "openai", country) == ""


def test_guidance_lowercase_gb_and_none():
    assert "OFFICIAL-SOURCE RULES" in G.block("I was sacked", "", "england", None, "gb")
    assert "OFFICIAL-SOURCE RULES" in G.block("I was sacked", "", "england", None, None)


def test_guidance_no_write_to_lessons():
    src = open(G.__file__).read()
    assert "lex_lessons" not in src and "db." not in src


def test_rule_regex_false_positives():
    # 'current' must not trigger rent rules; 'courtesy' should ideally not trigger Scotland court rule
    assert G.matched("What is the current rate of inflation?", "", "wales") == []


def test_case_list_false_positive_parkinsons():
    b = G.block("My mother has Parkinson's disease, what benefits can she get?", "", "england")
    assert "ParkingEye" not in b, "PROBE: 'Parkinson' triggers parking case list"


# ---------------------------------------------------------------- citation guard
def g(text, src="", cust=""):
    return S.guard_case_refs(text, src, cust)


def test_landmark_kept_and_volume_cite_kept():
    out, rem, lab, marks = g("Under Bolam v Friern Hospital Management Committee [1957] 1 WLR 582 the test applies.")
    assert "[1957] 1 WLR 582" in out and rem == 0 and marks


def test_invented_case_removed_no_fragments():
    out, rem, _, _ = g("See Smith v Jonesworth Ltd [2019] EWCA Civ 1234 and Brown v Greenacre [1957] 1 WLR 99.")
    assert rem == 2 and "[2019]" not in out and "[1957]" not in out and "WLR" not in out


def test_wrong_cite_on_real_case_stripped():
    out, rem, _, _ = g("ParkingEye Ltd v Beavis [2019] UKSC 12 is the key case.")
    assert "[2019] UKSC 12" not in out and "ParkingEye Ltd v Beavis" in out and rem == 1


def test_wrong_cite_prefix_of_real_cite_stripped():
    # [2015] UKSC 6 is NOT ParkingEye's citation (it is [2015] UKSC 67)
    out, rem, _, _ = g("ParkingEye Ltd v Beavis [2015] UKSC 6 is the key case.")
    assert "UKSC 6 " not in out + " ", f"PROBE: prefix of real citation accepted: {out}"


def test_customer_quoted_fake_labelled():
    out, rem, lab, _ = g("You mentioned Smith v Jonesworth Ltd; it is not a case I can find.",
                         cust="what about Smith v Jonesworth Ltd?")
    assert lab == 1 and "unverified case reference" in out


def test_separate_mentions_do_not_support():
    out, rem, _, _ = g("Following Patel v Mirza the claim fails.", src="Mr Patel wrote to the court. Later Mirza replied v the rules.")
    # separate mentions in one line within 60 chars might still pass; ensure real separate lines don't
    out2, rem2, _, _ = g("Patel v Mirzaco applies.", src="patel lived here.\nthe mirzaco shop closed.")
    assert rem2 == 1


def test_sports_and_ordinary_v_sentences():
    out, rem, _, _ = g("England v Wales is on Saturday.")
    assert out == "England v Wales is on Saturday." and rem == 0
    out, rem, _, _ = g("I watched Arsenal v Chelsea with my landlord before he evicted me.")
    assert rem == 0, f"PROBE false positive on ordinary sentence: {out}"


def test_sources_line_pruned():
    text = "Smith v Jonesworth Ltd [2019] EWCA Civ 1234 applies.\n[SOURCES: Smith v Jonesworth Ltd [2019] EWCA Civ 1234; Housing Act 1988]"
    out, rep = S.verify_citations(text, [], [], "")
    assert "Jonesworth" not in out and "Housing Act 1988" in out and rep["sources_line_pruned"] == 1


# ---------------------------------------------------------------- legislation (mocked fetch)
def _feed(title, ident):
    return f"<feed><entry><id>http://www.legislation.gov.uk/id/{ident}</id><title>{title}</title></entry></feed>"


def test_si_regex_false_positives():
    labels = [r["label"] for r in LS.extract_sis(
        "Under the Immigration Rules 2024 and the Civil Procedure Rules 1998 you may apply.")]
    assert labels == []
    labels = [r["label"] for r in LS.extract_sis("The court made a Child Arrangements Order 2025 last year.")]
    assert labels == [], f"PROBE: court order treated as SI: {labels}"


def test_ssi_number_not_looked_up_as_uksi():
    refs = LS.extract_sis("See S.S.I. 2026/12 for Scotland.")
    assert not any(r.get("si_num") == "2026/12" for r in refs), f"PROBE: SSI read as UK SI {refs}"


def test_not_found_act_with_lead_words_pruned_from_sources(monkeypatch):
    async def fetch(url):
        return 200, "<feed></feed>"
    monkeypatch.setattr(LS, "_fetch", fetch)
    LS._cache.clear()
    text = "Under the Tenant Fairness Act 2021, section 5, you are protected.\n[SOURCES: Tenant Fairness Act 2021 s.5; Housing Act 1988]"
    out, rep = run(LS.check_answer(text, "england", []))
    src_line = [ln for ln in out.splitlines() if ln.startswith("[SOURCES")][0]
    assert "not_found" in rep["verdicts"]
    assert "Tenant Fairness" not in src_line, f"PROBE: not-found Act left in SOURCES: {src_line}"


def test_welsh_bilingual_si_and_existence_label(monkeypatch):
    async def fetch(url):
        return 200, ('<feed><entry><id>http://www.legislation.gov.uk/id/wsi/2022/1</id><title><span xml:lang="en">The Renting '
                     'Homes (Wales) Regulations 2022</span><span xml:lang="cy">Rheoliadau</span></title></entry></feed>')
    monkeypatch.setattr(LS, "_fetch", fetch)
    LS._cache.clear()
    cits = []
    out, rep = run(LS.check_answer("The Renting Homes (Wales) Regulations 2022 apply.", "wales", cits))
    assert rep["statutory_instruments"][0]["verdict"] == "si_exists"
    assert any("existence checked only" in c["title"] for c in cits)
    assert LS.ACT_TTL == 3 * 86400


# ---------------------------------------------------------------- deadlines
def test_relative_dates_capitalised_last_week():
    r = dc.relative_dates("Last Week my boss sacked me", T)
    assert r and "between" in r[0]


def test_relative_dates_last_month_caps():
    assert dc.relative_dates("LAST MONTH I was dismissed", T)


def test_et_unknown_nation_safe_date_and_claim_warning():
    items = dc._et({"event_date": "2026-10-20", "jurisdiction": "unknown", "claim_type": "unknown"})
    assert items[0][2] == date(2027, 1, 19)  # NI 3 months less one day = safe
    assert "CLAIM TYPE NOT CONFIRMED" in items[0][0], "PROBE: unknown nation path drops claim-type warning"


def test_et_dates_boundary():
    on = dc._et({"event_date": "2026-10-01", "jurisdiction": "england", "claim_type": "unfair_dismissal"})[0]
    before = dc._et({"event_date": "2026-09-30", "jurisdiction": "england", "claim_type": "unfair_dismissal"})[0]
    assert on[2] == date(2027, 3, 31) and "SI 2026/954" in on[0]
    assert before[2] == date(2026, 12, 29) and "transitional rules may give longer" not in before[0]


def test_et_ni_and_passed_annotation():
    ni = dc._et({"event_date": "2026-10-20", "jurisdiction": "northern_ireland", "claim_type": "unfair_dismissal"})
    assert "LRA" in ni[0][0] and "does not apply" in ni[0][0]
    a = dc.compute_annotated([{"type": "employment_tribunal", "event_date": "2026-06-01", "jurisdiction": "england",
                               "claim_type": "unfair_dismissal", "approx": True}], T)
    t = a[0][0]
    assert "ALREADY PASSED" in t and "never say the claim is definitely out of time" in t and "APPROXIMATE" in t
    assert "INDEPENDENT CHECK" in t


def test_urgent_and_parking_unknown_service():
    a = dc.annotate("court_claim", [("x", "t", date(2026, 11, 22))], T, False)[0][0]
    assert "URGENT" in a and "INDEPENDENT CHECK" in a
    p = dc.compute_annotated([{"type": "parking_notice", "notice_date": "2026-10-01", "issuer": "council", "served": "unknown",
                               "jurisdiction": "england"}], T)
    assert p[0][2] is None and "ALREADY PASSED" in p[0][0]


def test_build_deadlines_with_mocked_extraction_capitalised_relative(monkeypatch):
    class FakeChat:
        def __init__(self, *a, **k): pass
        def with_model(self, *a): return self
        def with_params(self, **k): return self
        async def send_message(self, m):
            return '{"calcs":[{"type":"employment_tribunal","event_date":"2026-11-04","jurisdiction":"england","claim_type":"unfair_dismissal","approx":true}]}'
    monkeypatch.setattr(dc, "LlmChat", FakeChat)
    block, rem = run(dc.build_deadlines("I was dismissed Last Week, what is the tribunal deadline?", "", "k", "england"))
    assert "EXACT DATES" in block


def test_court_order_not_si():
    labels = [r["label"] for r in LS.extract_sis("The court made a Child Arrangements Order 2025 last year.")]
    assert labels == [], f"PROBE: court order treated as SI: {labels}"


def test_immigration_rules_alone_skipped():
    assert LS.extract_sis("Under the Immigration Rules 2024 you may apply.") == []


# ---------------------------------------------------------------- chat wiring (mocked model)
from tests.test_lex2_2a2_injection import _stream, _fakes, events  # noqa: E402,F401
from tests.test_lex2_2a3_high_stakes import mk  # noqa: E402,F401


class _FakeExtract:
    def __init__(self, *a, **k): pass
    def with_model(self, *a): return self
    def with_params(self, **k): return self
    async def send_message(self, m):
        return ('{"calcs":[{"type":"employment_tribunal","event_date":"2026-11-04","jurisdiction":"england",'
                '"claim_type":"unfair_dismissal","approx":true}]}')


def test_chat_non_uk_user_gets_no_guidance(mk, monkeypatch):  # noqa: F811
    _, seen = _stream(mk("plus"), monkeypatch, "Answer.", message="I was sacked by my employer, can I go to tribunal?",
                      country="ES")
    sysm = seen["messages"][0]["content"]
    assert "OFFICIAL-SOURCE RULES" not in sysm and "SOURCED CASE LIST" not in sysm


def test_chat_glasgow_resident_cardiff_flat_gets_wales_rule(mk, monkeypatch):  # noqa: F811
    _, seen = _stream(mk("pro"), monkeypatch, "Answer.",
                      message="I live in Glasgow but the flat I rent is in Cardiff and my landlord gave me a section 21 notice")
    sysm = seen["messages"][0]["content"]
    assert "section 173" in sysm


def test_chat_capitalised_last_week_keeps_guidance(mk, monkeypatch):  # noqa: F811
    monkeypatch.setattr(dc, "LlmChat", _FakeExtract)
    _, seen = _stream(mk("free"), monkeypatch, "Answer.",
                      message="I was dismissed Last Week by my employer in Leeds. What is my tribunal deadline?")
    sysm = seen["messages"][0]["content"]
    assert "OFFICIAL-SOURCE RULES" in sysm, "PROBE: guidance block lost when deadline builder raises"
    assert "EXACT DATES CALCULATED" in sysm


def test_chat_lowercase_last_week_control(mk, monkeypatch):  # noqa: F811
    monkeypatch.setattr(dc, "LlmChat", _FakeExtract)
    _, seen = _stream(mk("free"), monkeypatch, "Answer.",
                      message="I was dismissed last week by my employer in Leeds. What is my tribunal deadline?")
    sysm = seen["messages"][0]["content"]
    assert "OFFICIAL-SOURCE RULES" in sysm and "EXACT DATES CALCULATED" in sysm
