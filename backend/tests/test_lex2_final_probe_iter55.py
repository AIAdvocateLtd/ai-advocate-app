"""Iteration 55 independent probes — Lex 2.0 final legal-accuracy refinements (offline, no paid calls).
Each test documents an expected behaviour; failures are reported defects, not test bugs."""
import asyncio
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deadline_calc as dc  # noqa: E402
import high_stakes as H  # noqa: E402
import lex_guidance as G  # noqa: E402
import lex_safety as L  # noqa: E402
import source_ai_check as AI  # noqa: E402

BLOCK = "\n\nEXACT DATES CALCULATED BY THE APP — use these dates exactly:\n- x\n"


# ---------------------------------------------------------------- deadlines: _HINT_RE
def test_hint_positive_variants():
    for m in ("My phone stopped working after 2 weeks, can I get a refund?",
              "I'm pregnant and my manager reduced my hours last month",
              "My husband was detained at Heathrow and faces removal on Friday",
              "They deported my cousin last week, can we appeal?"):
        assert dc._HINT_RE.search(m), m


# ---------------------------------------------------------------- ensure_dates
def test_ensure_dates_zero_padded_day_not_duplicated():
    items = [{"title": "Last day to reject faulty goods", "due": date(2027, 1, 5)}]
    a = "You must reject by Tuesday 05 January 2027."
    assert dc.ensure_dates(a, items, BLOCK)[0] == a
    a2 = "You must reject by 5 January 2027."
    assert dc.ensure_dates(a2, items, BLOCK)[0] == a2


def test_ensure_dates_ordinal_or_us_format_counts_as_present():
    """An answer that states the date as '5th January 2027' or 'January 5, 2027' already has it — no duplicate section."""
    items = [{"title": "Last day to reject faulty goods", "due": date(2027, 1, 5)}]
    for a in ("Reject it by 5th January 2027.", "Reject it by January 5, 2027."):
        out, rep = dc.ensure_dates(a, items, BLOCK)
        assert rep["restored"] == 0, a


def test_ensure_dates_before_sources_tail_and_max4():
    items = [{"title": f"T{i}", "due": date(2027, 2, i + 1)} for i in range(6)]
    out, rep = dc.ensure_dates("Answer.\n\n[CONFIDENCE: LOW]\n[SOURCES: x]", items, BLOCK)
    assert rep["restored"] == 4 and out.index("Dates worked out") < out.index("[CONFIDENCE")
    assert "not legally confirmed" in out


def test_ensure_dates_never_adds_with_nocalc_facts_block():
    items = [{"title": "X", "due": date(2027, 2, 1)}]
    blk = dc.NO_CALC_BLOCK + "RELATIVE DATES (approximate...)"
    assert dc.ensure_dates("Hi", items, blk) == ("Hi", {"restored": 0, "passed_flagged": False})


def test_passed_flag_not_suppressed_by_customer_restating_ago():
    """'You bought it 3 weeks ago' is not the answer acknowledging that a deadline has passed."""
    out, rep = dc.ensure_dates("You bought the laptop 3 weeks ago, so ask the shop for a repair.", [],
                               BLOCK + "ALREADY PASSED: this date was 2 day(s) ago")
    assert rep["passed_flagged"] is True


def test_passed_flag_not_suppressed_by_employment_ended():
    out, rep = dc.ensure_dates("Your employment ended on 1 March; contact ACAS.", [],
                               BLOCK + "ALREADY PASSED: this date was 2 day(s) ago")
    assert rep["passed_flagged"] is True


# ---------------------------------------------------------------- parking
def _park(**c):
    return dc._parking({"notice_date": "2026-11-10", **c})


def test_private_parking_unknown_issuer_england_has_no_date():
    t, title, d = _park(issuer="unknown", jurisdiction="england")[0]
    assert d is None and title is None and "check who issued it" in t


def test_council_wales_windscreen_and_post():
    w = _park(issuer="council", served="windscreen", jurisdiction="wales")[0]
    assert w[2] == date(2026, 11, 23) and "Traffic Penalty Tribunal" in w[0]
    p = _park(issuer="council", served="post", jurisdiction="wales")[0]
    assert p[2] == date(2026, 11, 30)


def test_scotland_postal_pcn_not_described_as_service_method_not_given():
    """A Scottish PCN the customer says came by post must not get the 'service method not given' text or the
    England & Wales 21-day camera/postal rule."""
    t = _park(issuer="council", served="post", jurisdiction="scotland")[0][0]
    assert "service method not given" not in t
    assert "21 days" not in t


def test_scotland_unknown_service_no_21_day_rule():
    t = _park(issuer="council", served="unknown", jurisdiction="scotland")[0][0]
    assert "21 days" not in t, t


def test_ni_private_and_council_guidance_rules():
    assert [r[0] for r in G.matched("Private company parking charge at a retail park in Belfast", "", "northern_ireland")] \
        == ["parking_private"]
    both = [r[0] for r in G.matched("Council car park PCN in Cardiff", "", "wales")]
    assert "parking_council" in both


# ---------------------------------------------------------------- emergency / high-stakes topics
def test_police_detention_stays_criminal():
    hs = H.classify("I was arrested and detained at the police station overnight, they want to interview me under caution")
    assert "criminal" in hs["domains"] and "immigration" not in hs["domains"]


def test_police_detention_does_not_get_immigration_detention_rule():
    rules = [r[0] for r in G.matched("I was arrested and detained at the police station overnight", "", "england")]
    assert "emergency_detention" not in rules, rules


def test_non_immigration_removed_phrases_not_immigration():
    for m in ("I want my name to be removed from the joint tenancy agreement",
              "My landlord says the shed will be removed next week"):
        assert "immigration" not in H.classify(m)["domains"], m


def test_non_immigration_removal_not_emergency_detention():
    for m in ("The removal company damaged my sofa when I moved house",
              "Can the board vote for the removal of a director?"):
        assert "emergency_detention" not in [r[0] for r in G.matched(m, "", "england")], m


def test_immigration_removal_detected():
    hs = H.classify("The Home Office says I will be removed on Friday")
    assert "immigration" in hs["domains"] and hs["level"] in ("urgent", "emergency", "high")


def test_removed_abandoned_car_not_immigration():
    assert "immigration" not in H.classify("The council says the car will be removed from outside my house")["domains"]


def test_pregnant_tenant_not_employment():
    hs = H.classify("My wife is pregnant and our landlord has served a section 21 notice")
    assert "employment" not in hs["domains"], hs


# ---------------------------------------------------------------- source quality layer 1
SRC = [{"n": 1, "title": "Early conciliation", "url": "https://www.acas.org.uk/early-conciliation",
        "content": "You must notify Acas before making an employment tribunal claim. Early conciliation is free and usually "
                   "lasts up to 6 weeks. The time limit is usually 3 months less one day."},
       {"n": 2, "title": "Notice to leave", "url": "https://www.gov.scot/notice-to-leave",
        "content": "A landlord must give a tenant a notice to leave with 28 days notice if the tenant has lived there six months or less."},
       {"n": 3, "title": "Network", "url": "https://www.gov.uk/x",
        "content": "The landlord network notice explains that six months notice is required for section 173."}]
CITES = [{"n": s["n"], "url": s["url"]} for s in SRC]


def _vc(t, nation="england"):
    return L.verify_citations(t, [dict(c) for c in CITES], SRC, "", nation)


def test_paraphrase_keeps_legitimate_marker():
    out, rep = _vc("You have to tell Acas first, before you can bring a tribunal claim [1].")
    assert "[1]" in out, rep["claim_support"]


def test_period_matching_digits_and_words():
    out, rep = _vc("Early conciliation usually lasts up to six weeks [1].")
    assert "[1]" in out and rep["claim_support"][0]["status"] == "source_supported"
    out, rep = _vc("The tribunal time limit is usually three months less one day [1].")
    assert rep["claim_support"][0]["status"] == "source_supported"


def test_wrong_period_flagged_uncertain():
    out, rep = _vc("Early conciliation usually lasts up to 8 weeks [1].")
    assert rep["claim_support"][0]["status"] == "uncertain"


def test_number_word_substring_not_treated_as_found():
    """'two' inside 'network' is not the period 'two months'."""
    out, rep = _vc("Under section 173 the landlord notice is two months [3].")
    assert rep["claim_support"][0]["status"] == "uncertain", rep["claim_support"]


def test_scottish_source_ok_for_scotland_rejected_for_england():
    s = "A landlord must give a notice to leave with 28 days notice [2]."
    assert "[2]" in _vc(s, "scotland")[0]
    assert "[2]" not in _vc(s, "england")[0]


def test_no_nation_known_keeps_marker():
    assert "[2]" in _vc("A landlord must give a notice to leave with 28 days notice [2].", None)[0]


def test_unrelated_sentence_marker_removed():
    out, rep = _vc("Your neighbour's dog barking is a statutory nuisance [1].")
    assert "[1]" not in out and rep["claim_support"][0]["status"] == "unsupported"


# ---------------------------------------------------------------- layer 3 optional AI check (fake db + fake ask)
class _Coll:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, q):
        return self.doc


class _DB:
    def __init__(self, doc=None):
        self.app_settings = _Coll(doc)


def _run(db, text, cs, hs={"level": "urgent"}, dl=True, ask=None):
    return asyncio.run(AI.run(db, text, cs, SRC, hs, dl, ask))


def test_ai_enabled_must_be_literal_true():
    calls = []

    async def ask(c, p):
        calls.append(c)
        return {"verdict": "unsupported", "why": ""}
    for doc in ({"enabled": "true"}, {"enabled": 1}, {"enabled": False}, {}):
        _run(_DB(doc), "x", [{"n": 1, "status": "uncertain", "text": "x 8 weeks"}], ask=ask)
    assert calls == []


def _pipeline(text, verdict):
    """Real layer-1 output (finalize_answer claim_support) fed into layer 3 with a fake ask."""
    AI._cache.clear()

    async def ask(c, p):
        return {"verdict": verdict, "why": ""}
    out, rep = L.finalize_answer(text, citations=[dict(c) for c in CITES], sources=SRC, research_status="ok", risk="high",
                                 language="en", legal_question=True, nation="england")
    return asyncio.run(AI.run(_DB({"enabled": True}), out, rep["claim_support"], SRC, {"level": "standard"}, True, ask))


def test_ai_short_claim_from_real_pipeline_gets_qualifier():
    """Layer-1 claim text drops the marker but keeps the full stop ('... 8 weeks.'), so the 60-char anchor never matches
    '... 8 weeks [1].' — the check is paid for but no qualifier is added."""
    out, rep = _pipeline("Early conciliation usually lasts up to 8 weeks [1].", "partly")
    assert rep["checked"] == 1 and rep["qualified"] == 1 and AI.QUALIFIER in out, out


def test_ai_qualifier_attached_to_the_claim_sentence_not_next_sentence():
    out, rep = _pipeline("Early conciliation is free and it usually lasts up to 8 weeks before you can go on to claim [1]. "
                         "Call Acas today.", "unsupported")
    assert AI.QUALIFIER in out and out.index(AI.QUALIFIER) < out.index("Call Acas"), out


def test_multi_claim_sentence_period_check_is_per_marker():
    """'6 weeks [1] ... 3 months less one day [2]': each source supports its own period — neither should be 'uncertain'."""
    src = [{"n": 1, "title": "EC", "url": "https://www.acas.org.uk/ec", "content": "Early conciliation usually lasts up to 6 weeks."},
           {"n": 2, "title": "TL", "url": "https://www.acas.org.uk/tl", "content": "The time limit is 3 months less one day from dismissal."}]
    out, rep = L.finalize_answer("Early conciliation usually lasts up to 6 weeks [1] and the time limit is 3 months less one day [2].",
                                 citations=[{"n": s["n"], "url": s["url"]} for s in src], sources=src, research_status="ok",
                                 risk="high", language="en", legal_question=True, nation="england")
    assert [c["status"] for c in rep["claim_support"]] == ["source_supported", "source_supported"], rep["claim_support"]


def test_ai_qualifier_found_when_marker_inside_first_60_chars():
    AI._cache.clear()

    async def ask(c, p):
        return {"verdict": "unsupported", "why": ""}
    text = "Early conciliation [1] usually lasts up to 8 weeks, and then the tribunal claim follows."
    claim_text = "Early conciliation usually lasts up to 8 weeks, and then the tribunal claim follows."
    cs = [{"n": 1, "status": "uncertain", "text": claim_text}]
    out, rep = _run(_DB({"enabled": True}), text, cs, ask=ask)
    assert rep["qualified"] == 1 and AI.QUALIFIER in out, out


def test_ai_failed_call_not_cached_or_charged():
    AI._cache.clear()
    n = {"c": 0}

    async def boom(c, p):
        n["c"] += 1
        raise RuntimeError("timeout")
    cs = [{"n": 1, "status": "uncertain", "text": "Early conciliation usually lasts up to 8 weeks."}]
    _run(_DB({"enabled": True}), "Early conciliation usually lasts up to 8 weeks [1].", [dict(c) for c in cs], ask=boom)
    _run(_DB({"enabled": True}), "Early conciliation usually lasts up to 8 weeks [1].", [dict(c) for c in cs], ask=boom)
    assert n["c"] == 2, "a failed check was cached for 7 days, so it is never retried"


def test_ai_never_described_as_professional():
    assert "professional" not in AI.QUALIFIER.lower() and "verified" not in AI.QUALIFIER.lower()
    assert AI.EST_GBP_PER_CLAIM == 0.0011 and AI.MAX_CLAIMS == 3


def test_real_db_setting_absent_or_disabled():
    """Read-only: the real preview DB must not have the AI source check enabled."""
    from pymongo import MongoClient
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    doc = db.app_settings.find_one({"_id": "lex_ai_source_check"}) or {}
    assert doc.get("enabled") is not True
