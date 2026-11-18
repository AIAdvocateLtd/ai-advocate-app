"""Lex 2.0 final legal-accuracy refinements — offline (no AI calls; optional AI source check mocked)."""
import asyncio
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import deadline_calc as dc  # noqa: E402
import high_stakes as H  # noqa: E402
import lex_guidance as G  # noqa: E402
import lex_safety as L  # noqa: E402
import source_ai_check as AI  # noqa: E402


# ---------------------------------------------------------------- deadlines missing / omitted
def test_hint_now_catches_consumer_and_pregnancy_questions():
    for m in ("I bought a £900 laptop 3 weeks ago and it keeps crashing. The shop says I can only have a repair.",
              "I told my employer I was pregnant in August and they cut my hours and then put me on a performance plan.",
              "My brother has been detained and they say he will be removed tomorrow morning."):
        assert dc._HINT_RE.search(m), m


def test_no_calc_block_requires_the_rule():
    assert "You MUST still state the applicable time-limit rule" in dc.NO_CALC_BLOCK
    assert "Do NOT state a precise calendar deadline" in dc.NO_CALC_BLOCK


BLOCK = "\n\nEXACT DATES CALCULATED BY THE APP — use these dates exactly:\n- x\n"
ITEMS = [{"title": "Latest date to start ACAS early conciliation", "due": date(2027, 4, 19)}]


def test_dropped_app_date_is_restored_and_labelled_not_confirmed():
    out, rep = dc.ensure_dates("You should act quickly.\n\n[CONFIDENCE: MEDIUM]", ITEMS, BLOCK)
    assert "Monday 19 April 2027" in out and "not legally confirmed" in out and rep["restored"] == 1
    assert out.index("Dates worked out by the app") < out.index("[CONFIDENCE")


def test_present_date_not_duplicated_and_no_block_no_change():
    a = "The deadline is 19 April 2027."
    assert dc.ensure_dates(a, ITEMS, BLOCK)[0] == a
    assert dc.ensure_dates("Hi", ITEMS, "")[0] == "Hi"
    assert dc.ensure_dates("Hi", ITEMS, dc.NO_CALC_BLOCK)[0] == "Hi"


def test_passed_date_flagged_when_answer_silent():
    out, rep = dc.ensure_dates("Act now.", [], BLOCK + "x ALREADY PASSED: this date was 3 day(s) ago")
    assert rep["passed_flagged"] and "already passed" in out and "does not always mean it is too late" in out
    assert dc.ensure_dates("That date has passed.", [], BLOCK + "ALREADY PASSED")[1]["passed_flagged"] is False


# ---------------------------------------------------------------- parking
def _park(**c):
    return dc._parking({"notice_date": "2026-11-10", **c})


def test_private_parking_england_pofa_and_no_invented_date():
    t, title, d = _park(issuer="private", jurisdiction="england")[0]
    assert d is None and "POPLA" in t and "IAS" in t and "para 9(5)" in t and "will not calculate a date" in t


def test_private_parking_scotland_and_ni_no_keeper_liability():
    assert "does not apply in Scotland" in _park(issuer="private", jurisdiction="scotland")[0][0]
    assert "does not apply in Northern Ireland" in _park(issuer="private", jurisdiction="northern_ireland")[0][0]


def test_council_pcn_nations():
    ni = _park(issuer="council", jurisdiction="northern_ireland")[0]
    assert ni[2] == date(2026, 11, 23) and "Northern Ireland Traffic Penalty Tribunal" in ni[0]
    sc = _park(issuer="council", served="windscreen", jurisdiction="scotland")[0]
    assert "First-tier Tribunal for Scotland" in sc[0]
    en = _park(issuer="council", served="post", jurisdiction="england")[0]
    assert "Traffic Penalty Tribunal" in en[0] and en[2] == date(2026, 11, 30)


def test_parking_guidance_private_vs_council():
    priv = G.matched("I got a £100 parking fine from a private company at a supermarket car park in Leeds", "", "england")
    assert [r[0] for r in priv] == ["parking_private"]
    b = G.block("I got a £100 parking fine from a private company at a supermarket car park in Leeds", "", "england")
    assert "POPLA" in b and "Sch.4" in b and "ParkingEye Ltd v Beavis [2015] UKSC 67" in b
    assert [r[0] for r in G.matched("I got a council PCN in Belfast", "", "northern_ireland")] == ["parking_council_ni"]
    assert "parking_council_scotland" in [r[0] for r in G.matched("Council PCN in Glasgow", "", "scotland")]


# ---------------------------------------------------------------- emergency signposting
def test_detention_emergency_rule_and_help_line():
    b = G.block("My brother has been detained and they say he will be removed tomorrow morning. What can we do tonight?", "", "england")
    assert "Detention Duty Advice Scheme" in b and "Cite only immigration-specific sources" in b and "Never promise removal" in b
    assert "Detention Duty Advice Scheme" in H.HELP["immigration"]


def test_housing_emergency_rule():
    b = G.block("My landlord changed the locks and I have nowhere to sleep tonight", "", "england")
    assert "Protection from Eviction Act 1977" in b and "0808 800 4444" in b


def test_existing_urgent_detection_unchanged():
    hs = H.classify("My brother has been detained and they say he will be removed tomorrow morning. What can we do tonight?")
    assert hs["level"] in ("urgent", "high") and "immigration" in hs["domains"]


# ---------------------------------------------------------------- source quality (layered, free)
SRC = [{"n": 1, "title": "Police caution", "url": "https://www.gov.uk/arrested-your-rights",
        "content": "Police caution: you do not have to say anything but it may harm your defence."},
       {"n": 2, "title": "Notice periods", "url": "https://www.gov.wales/notice-periods",
        "content": "A landlord must give at least six months notice under section 173 for a periodic standard contract."},
       {"n": 3, "title": "Detention advice", "url": "https://www.gov.uk/legal-aid",
        "content": "People held in immigration removal centres can get free legal advice through the Detention Duty Advice Scheme."}]
CITES = [{"n": s["n"], "url": s["url"]} for s in SRC]


def _vc(text, nation="england"):
    return L.verify_citations(text, [dict(c) for c in CITES], SRC, "", nation)


def test_irrelevant_source_marker_removed_and_recorded():
    out, rep = _vc("He can get free legal advice in the removal centre through the Detention Duty Advice Scheme [3][1].")
    assert "[3]" in out and "[1]" not in out
    st = {c["n"]: c["status"] for c in rep["claim_support"]}
    assert st == {3: "source_supported", 1: "unsupported"}


def test_source_for_other_nation_not_accepted():
    out, rep = _vc("A section 173 notice for a periodic contract needs six months' notice [2].", "england")
    assert "[2]" not in out and "not this matter's UK nation" in rep["claim_support"][0]["why"]
    out, rep = _vc("A section 173 notice for a periodic contract needs six months' notice [2].", "wales")
    assert "[2]" in out and rep["claim_support"][0]["status"] == "source_supported"


def test_period_not_in_source_is_uncertain_and_explained():
    out, rep = L.finalize_answer("A section 173 notice for a periodic contract needs two months' notice [2].",
                                 citations=[dict(c) for c in CITES], sources=SRC, research_status="ok", risk="high",
                                 language="en", legal_question=True, nation="wales")
    assert rep["claim_support"][0]["status"] == "uncertain" and "**Source check:** a time period stated next to [2]" in out


def test_existence_vs_support_labels_unchanged():
    import landmark_cases
    import legal_reasoning
    assert "not reviewed by a qualified lawyer" in landmark_cases.REVIEW_STATUS
    src = open(os.path.join(os.path.dirname(L.__file__), "legal_reasoning.py")).read()
    assert "interpretation not verified" in src
    assert "checked only — not whether it is in force" in open(os.path.join(os.path.dirname(L.__file__), "legal_sources.py")).read()


# ---------------------------------------------------------------- optional AI source check (OFF by default, mocked)
class _Coll:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, q):
        return self.doc


class _DB:
    def __init__(self, doc=None):
        self.app_settings = _Coll(doc)


UNC = [{"n": 2, "status": "uncertain", "text": "A section 173 notice needs two months' notice.", "why": "x",
        "raw": "A section 173 notice needs two months' notice [2]."}]
HS = {"level": "urgent"}


def test_ai_check_off_by_default_makes_no_call():
    calls = []

    async def ask(c, p):
        calls.append(c)
        return {"verdict": "unsupported", "why": "x"}
    out, rep = asyncio.run(AI.run(_DB(None), "A section 173 notice needs two months' notice [2].", list(UNC), SRC, HS, True, ask))
    assert calls == [] and rep["enabled"] is False and out.endswith("[2].")


def test_ai_check_when_enabled_qualifies_and_caches():
    AI._cache.clear()
    calls = []

    async def ask(c, p):
        calls.append(p)
        return {"verdict": "unsupported", "why": "passage says six months"}
    db = _DB({"enabled": True})
    out, rep = asyncio.run(AI.run(db, "A section 173 notice needs two months' notice [2].", [dict(u) for u in UNC], SRC, HS, True, ask))
    assert len(calls) == 1 and "six months" in calls[0] and AI.QUALIFIER in out and rep["qualified"] == 1
    assert rep["est_gbp"] == AI.EST_GBP_PER_CLAIM
    out2, rep2 = asyncio.run(AI.run(db, "A section 173 notice needs two months' notice [2].", [dict(u) for u in UNC], SRC, HS, True, ask))
    assert len(calls) == 1 and rep2["cached"] == 1 and rep2["est_gbp"] == 0


def test_ai_check_skips_low_stakes_and_supported_claims():
    calls = []

    async def ask(c, p):
        calls.append(c)
        return {"verdict": "supported", "why": ""}
    db = _DB({"enabled": True})
    asyncio.run(AI.run(db, "x", list(UNC), SRC, {"level": "standard"}, False, ask))
    asyncio.run(AI.run(db, "x", [{**UNC[0], "status": "source_supported"}], SRC, HS, True, ask))
    many = [{**UNC[0], "text": f"claim {i} two months", "raw": f"claim {i} two months [2]."} for i in range(6)]
    AI._cache.clear()
    _, rep = asyncio.run(AI.run(db, " ".join(c["raw"] for c in many), many, SRC, HS, True, ask))
    assert rep["checked"] == AI.MAX_CLAIMS and len(calls) == AI.MAX_CLAIMS


# ---------------------------------------------------------------- wiring
def test_server_wiring():
    src = open(os.path.join(os.path.dirname(L.__file__), "server.py")).read()
    assert src.count('juris["deadline_items"] = auto_reminders') == 2
    assert "deadline_calc.ensure_dates(" in src and "source_ai_check.run(db" in src and "nation=_juris_nation(juris))" in src


def test_topic_precision_for_retest_scenarios():
    from evals.lex_eval_scenarios import SCENARIOS
    by = {s["id"]: s for s in SCENARIOS}
    assert [r[0] for r in G.matched(by["IMM-03"]["q"], "", "england")] == ["immigration_core"]
    for i in ("EMP-03", "EMP-04"):
        assert H.classify(by[i]["q"])["level"] in ("high", "urgent") and "employment" in H.classify(by[i]["q"])["domains"]
    assert "emergency_detention" in [r[0] for r in G.matched(by["IMM-05"]["q"], "", "england")]


# ---------------------------------------------------------------- after the 15-answer retest
def test_et_points_added_only_when_missing():
    q = "My employer in Cardiff hasn't paid my last two months' wages or my holiday pay."
    out, rep = dc.ensure_et_points("Claim at the tribunal: 6 months less one day if on/after 1 Oct, else 3 months.", q, "wales")
    assert rep["added"] == ["series"] and "LAST deduction" in out
    full = "Tribunal: 6 months or 3 months; time runs from the last deduction in the series."
    assert dc.ensure_et_points(full, q, "wales")[1]["added"] == []
    out, rep = dc.ensure_et_points("The tribunal time limit is 3 months.", "I was pregnant and they cut my hours", "england")
    assert rep["added"] == ["date_of_act", "continuing"] and "END of that period" in out
    assert dc.ensure_et_points("The tribunal time limit is 3 months.", "My wages", "northern_ireland")[1]["added"] == []
    assert dc.ensure_et_points("Ask the shop for a refund.", "I bought a laptop", "england")[1]["added"] == []


def test_detention_rule_solicitor_only_court_and_no_police_prompt():
    b = G.block("My brother has been detained and they say he will be removed tomorrow morning.", "", "england")
    assert "OISC advisers cannot" in b and "High Court's duty judge" in b and "police" not in b.lower()
    assert "police" not in H.HELP["immigration"].lower()
