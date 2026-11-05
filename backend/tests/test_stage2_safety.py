"""Stage 2 unit tests — fictional data, no AI calls. Run: cd /app/backend && python -m pytest tests/test_stage2_safety.py -q"""
import asyncio
import os
import sys
import uuid
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import ai_usage  # noqa: E402
import deadline_calc as dc  # noqa: E402
import lex_safety as ls  # noqa: E402
import rag  # noqa: E402

D = date.fromisoformat


# ------------------------------------------------------------------ jurisdiction
@pytest.mark.parametrize("msg,profile,conflict,applicable", [
    ("My landlord in Cardiff won't return my deposit", "scotland", True, None),          # profile vs property city
    ("I live in Glasgow but the flat I rent is in Cardiff", None, True, None),          # lives vs matter, weak clue only
    ("I got a section 173 notice for my flat", "england", True, None),                  # Welsh legal marker vs England profile
    ("I got a section 173 notice for my flat", "wales", False, None),                   # consistent
    ("My landlord in Wales served a notice", None, False, "wales"),                     # explicit nation, no profile
    ("Under Scots law can my landlord keep my deposit?", "england", False, "scotland"),  # explicit law choice
    ("I was sacked from my job in Glasgow", "england", False, None),                    # employment: GB-wide, no conflict
    ("I was sacked from my job in Belfast", "england", True, None),                     # employment NI differs
    ("My visa expires next month, I live in Belfast", "england", False, None),          # immigration UK-wide
    ("I'm from Newcastle and my landlord kept my deposit", "england", False, None),     # ambiguous place ignored
    ("What notice does my landlord in England and Wales need?", "wales", False, None),  # 'England and Wales' phrase
])
def test_jurisdiction(msg, profile, conflict, applicable):
    r = ls.assess_jurisdiction(msg, "", profile, "GB")
    assert r["conflict"] is conflict, r
    if applicable:
        assert r["applicable"] == applicable
    if conflict:
        assert r["deadline_jurisdiction"] == "unknown" and "ONE short" in r["block"]


def test_jurisdiction_non_uk_untouched():
    assert ls.assess_jurisdiction("my flat in Cardiff", "", "scotland", "US")["block"] == ""


def test_jurisdiction_uses_history():
    r = ls.assess_jurisdiction("what notice do they need?", "My rented flat in Cardiff has damp", "scotland", "GB")
    assert r["conflict"] is True


# ------------------------------------------------------------------ citations
CITES = [{"n": 1, "title": "Housing Act 2004", "url": "https://www.legislation.gov.uk/ukpga/2004/34/section/213", "source": "official"},
         {"n": 2, "title": "Deposits", "url": "https://www.gov.uk/tenancy-deposit-protection", "source": "official"}]
SRCS = [{"n": 1, "title": "Housing Act 2004", "content": "Section 213 Housing Act 2004 requires deposits to be protected."},
        {"n": 2, "title": "Deposits", "content": "Your landlord must put your deposit in a government-backed scheme."}]


def test_nonexistent_citation_numbers_removed():
    out, rep = ls.verify_citations("Deposits must be protected [1]. Penalty is 3x [7]. Also [2, 9].", CITES, SRCS)
    assert "[7]" not in out and "[9]" not in out and "[1]" in out and "[2]" in out
    assert rep["removed_markers"] == 2


def test_unsupported_claim_marker_dropped():
    out, rep = ls.verify_citations("Under the Protection from Eviction Act 1977 you need a court order [2].", CITES, SRCS)
    assert "[2]" not in out and rep["unsupported_markers"] == 1
    assert CITES[1]["claim_check"] == "not_confirmed"


def test_supported_claim_kept():
    out, rep = ls.verify_citations("Section 213 of the Housing Act 2004 applies [1].", CITES, SRCS)
    assert "[1]" in out and CITES[0]["claim_check"] == "supported"


def test_urls_checked():
    text = ("See [the Act](https://www.legislation.gov.uk/ukpga/2004/34/section/213), "
            "https://www.legislation.gov.uk/ukpga/1988/50/section/21, https://www.acas.org.uk, "
            "https://fake-law-blog.example/case and [blog](https://randomsite.com/x).")
    out, rep = ls.verify_citations(text, CITES, SRCS)
    assert "ukpga/2004/34/section/213" in out                         # retrieved → kept
    assert "ukpga/1988/50" not in out and "https://www.legislation.gov.uk" in out  # deep unverified → root
    assert "https://www.acas.org.uk" in out                           # signpost homepage kept
    assert "fake-law-blog" not in out and "randomsite.com" not in out
    assert rep["urls_removed"] == 2 and rep["urls_rerouted"] == 1


def test_no_research_strips_all_numbers_and_adds_notes():
    text = "You will win [1]. See Smith v Imaginary Ltd [2031] UKSC 99.\n\nDisclaimer: general info.\n[CONFIDENCE: HIGH]\n[SOURCES: —]"
    out, rep = ls.finalize_answer(text, citations=[], sources=[], research_status="quota_exhausted", risk="high",
                                  language="en-GB", legal_question=True)
    assert "[1]" not in out and "[CONFIDENCE: MEDIUM]" in out
    assert "couldn't check current official sources" in out and "Source check" in out
    assert out.index("couldn't check") < out.index("Disclaimer:")   # visible: before the disclaimer cut-point
    assert any("Imaginary" in r for r in rep["unverified_case_refs"])


def test_low_risk_failure_no_backstop_unless_false_claim():
    out, _ = ls.finalize_answer("Generally fine.", citations=[], sources=[], research_status="unavailable", risk="low",
                                language="en-GB", legal_question=True)
    assert "Note:" not in out
    out, _ = ls.finalize_answer("I've checked the current legislation and it's fine.", citations=[], sources=[],
                                research_status="unavailable", risk="low", language="en-GB", legal_question=True)
    assert "couldn't check" in out


def test_note_localised():
    out, _ = ls.finalize_answer("Respuesta.", citations=[], sources=[], research_status="no_results", risk="high",
                                language="es-ES", legal_question=True)
    assert "no he podido consultar" in out


def test_research_block_contents():
    b = ls.research_block("quota_exhausted", "high", ["housing"])
    assert "MUST NOT" in b and "HIGH-RISK" in b and "Shelter" in b
    assert ls.research_block("not_needed", "high", ["general"]) == ""
    assert "independently" in ls.research_block("ok", "low", ["general"])


def test_risk_levels():
    assert ls.risk_level("My landlord served a section 21 notice", None) == "high"
    assert ls.risk_level("What does 'force majeure' mean in a contract?", None) == "low"
    assert ls.risk_level("anything", "immigration") == "high"


# ------------------------------------------------------------------ research failure detection
class _Resp:
    def __init__(self, code, body=None):
        self.status_code, self._b, self.text = code, body or {}, str(body)

    def json(self):
        return self._b


@pytest.mark.parametrize("code,status", [(432, "quota_exhausted"), (433, "quota_exhausted"), (429, "quota_exhausted"),
                                         (500, "unavailable"), (401, "unavailable")])
def test_tavily_http_failures(monkeypatch, code, status):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    class C:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): return _Resp(code, {"detail": "x"})
    monkeypatch.setattr(rag.httpx, "AsyncClient", C)
    r = asyncio.run(rag.research("My landlord is keeping my whole deposit, what can I do?", db=None))
    assert r["status"] == status and r["citations"] == [] and r["block"] == ""


def test_tavily_no_results_and_not_configured(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    class C:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): return _Resp(200, {"results": []})
    monkeypatch.setattr(rag.httpx, "AsyncClient", C)
    assert asyncio.run(rag.research("My landlord is keeping my whole deposit, what can I do?"))["status"] == "no_results"
    monkeypatch.setenv("TAVILY_API_KEY", "")
    assert asyncio.run(rag.research("My landlord is keeping my whole deposit, what can I do?"))["status"] == "not_configured"
    assert asyncio.run(rag.research("hi"))["status"] == "not_needed"


def test_tavily_success_keeps_snippets(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")

    class C:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            dom = "gov" if json.get("include_domains") else "web"
            return _Resp(200, {"results": [{"title": f"T-{dom}", "url": f"https://{dom}.example/a", "content": "Housing Act 2004"}]})
    monkeypatch.setattr(rag.httpx, "AsyncClient", C)
    r = asyncio.run(rag.research("My landlord is keeping my whole deposit, what can I do?"))
    assert r["status"] == "ok" and [c["n"] for c in r["citations"]] == [1, 2] and r["sources"][0]["content"]
    assert "only numbers 1 to 2 exist" in r["block"]


# ------------------------------------------------------------------ deadline calculator
def _texts(items):
    return " ".join(t for t, _, _ in items)


def test_et_old_rule_and_month_end():
    items = dc.compute([{"type": "employment_tribunal", "event_date": "2026-03-31", "jurisdiction": "england"}])
    assert items[0][2] == D("2026-06-30") and "month end" in items[0][0]


def test_et_new_six_month_rule():
    items = dc.compute([{"type": "employment_tribunal", "event_date": "2026-10-15", "jurisdiction": "scotland"}])
    assert items[0][2] == D("2027-04-14")


def test_et_acas_extension_and_late_acas():
    ok = dc.compute([{"type": "employment_tribunal", "event_date": "2026-03-03", "acas_date": "2026-05-01",
                      "certificate_date": "2026-06-12", "jurisdiction": "england"}])
    assert ok[1][2] == D("2026-07-14")    # 2 Jun + 42 days paused = 14 Jul (later than certificate + 1 month)
    late = dc.compute([{"type": "employment_tribunal", "event_date": "2026-01-05", "acas_date": "2026-05-01",
                        "certificate_date": "2026-05-20", "jurisdiction": "wales"}])
    assert "after the normal time limit" in _texts(late) and late[1][2] is None
    pending = dc.compute([{"type": "employment_tribunal", "event_date": "2026-09-01", "acas_date": "2026-10-01",
                           "jurisdiction": "england"}])
    assert "no certificate date" in _texts(pending) and pending[1][2] is None


def test_et_unknown_nation_uses_safe_date():
    items = dc.compute([{"type": "employment_tribunal", "event_date": "2026-10-15", "jurisdiction": "unknown"}])
    assert items[0][2] == D("2027-01-14") and "not confirmed" in items[0][0]   # NI 3-month date is earlier
    ni = dc.compute([{"type": "employment_tribunal", "event_date": "2026-10-15", "jurisdiction": "northern_ireland"}])
    assert ni[0][2] == D("2027-01-14") and "LRA" in ni[0][0]


def test_et_deadline_on_weekend_flagged():
    items = dc.compute([{"type": "employment_tribunal", "event_date": "2026-03-07", "jurisdiction": "england"}])
    assert items[0][2] == D("2026-06-06") and "Saturday" in items[0][0]


def test_leap_year_dates():
    ilr = dc.compute([{"type": "ilr_eligibility", "route_start_date": "2024-02-29", "qualifying_years": 5}])
    assert ilr[0][2] == D("2029-02-28") - (D("2029-02-28") - D("2029-01-31"))  # 28 days before 28 Feb 2029 = 31 Jan
    et = dc.compute([{"type": "employment_tribunal", "event_date": "2027-11-30", "jurisdiction": "england"}])
    assert et[0][2] == D("2028-05-29")    # 6 months less a day


def test_scotland_deposit_skips_bank_holidays():
    items = dc.compute([{"type": "deposit_protection", "paid_date": "2026-11-20", "tenancy_start_date": "2026-11-20",
                         "jurisdiction": "scotland"}])
    # 30 working days from Fri 20 Nov 2026 skipping St Andrew's (30 Nov), 25/28 Dec, 1 Jan, 4 Jan → Fri 8 Jan 2027
    assert items[0][2] == D("2027-01-08")


def test_tenancy_unknown_nation_gives_no_single_date():
    items = dc.compute([{"type": "tenancy_notice", "served_date": "2026-11-01", "tenancy_start_date": "2025-01-01",
                         "jurisdiction": "unknown"}])
    assert len(items) == 1 and items[0][2] is None and "Wales" in items[0][0] and "Scotland" in items[0][0]


def test_divorce_outside_england_wales_not_calculated():
    items = dc.compute([{"type": "divorce", "application_date": "2026-06-01", "jurisdiction": "scotland"}])
    assert items[0][2] is None
    ew = dc.compute([{"type": "divorce", "application_date": "2026-06-01", "jurisdiction": "england"}])
    assert ew[0][2] == D("2026-10-19")


def test_limitation_unknown_uses_scotland_safe_date():
    items = dc.compute([{"type": "limitation", "event_date": "2026-01-10", "claim_kind": "debt", "jurisdiction": "unknown"}])
    assert items[0][2] == D("2031-01-10")


def test_visa_expiry_on_bank_holiday_flagged():
    items = dc.compute([{"type": "visa_expiry", "expiry_date": "2026-12-25"}])
    assert "bank holiday" in items[0][0]


def test_missing_dates_return_no_calc_guidance():
    block, rem = asyncio.run(dc.build_deadlines("I got court papers about a debt claim, when do I need to respond?", "", "x"))
    assert block == dc.NO_CALC_BLOCK and rem == []
    assert "Do NOT state a precise calendar deadline" in block
    assert asyncio.run(dc.build_deadlines("What is a peppercorn?", "", "x")) == ("", [])


# ------------------------------------------------------------------ token estimates
def test_estimator_conservative_vs_measured():
    english = "The landlord must protect the deposit within 30 days under the Housing Act 2004. " * 50
    est = ai_usage.estimate_tokens(english, "anthropic", 1)
    assert est > len(english) // 4 * 1.5
    urdu = "میرے مالک مکان نے میری جمع شدہ رقم واپس نہیں کی۔ " * 20
    assert ai_usage.estimate_tokens(urdu, "anthropic") > ai_usage.estimate_tokens(urdu, "openai") * 1.8


def test_usage_rows_label_measured_vs_estimated():
    rows = []

    class Coll:
        async def insert_one(self, d): rows.append(d)

    class DB:
        llm_usage = Coll()
    ai_usage._state["db"] = DB()

    async def go():
        ai_usage.record(provider="anthropic", model_requested="claude-haiku-5-5", tokens_in=100, tokens_out=50)
        ai_usage.record(provider="anthropic", model_requested="claude-haiku-5-5", input_text="hello there", output_text="hi")
        await asyncio.sleep(0.05)
    asyncio.run(go())
    assert rows[0]["measured"] is True and rows[0]["tokens_source"] == "provider"
    assert rows[1]["measured"] is False and rows[1]["tokens_source"] == "estimated_tokenizer_v2"
    assert rows[1]["cost_source"] == "estimated_tokens_x_rate_table"


# ------------------------------------------------------------------ cross-conversation isolation (preview DB, fictional)
def test_cross_memory_off_by_default_and_isolated():
    from motor.motor_asyncio import AsyncIOMotorClient
    import chat_memory

    async def go():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        a, b = f"test-a-{uuid.uuid4()}", f"test-b-{uuid.uuid4()}"
        docs = [{"user_id": a, "session_id": "s1", "user_message": "A: Acme deposit", "assistant_response": "x", "created_at": "2026-01-01"},
                {"user_id": a, "session_id": "s2", "user_message": "A: dismissal", "assistant_response": "y", "created_at": "2026-01-02"},
                {"user_id": b, "session_id": "s1", "user_message": "B: secret", "assistant_response": "z", "created_at": "2026-01-03"}]
        await db.conversations.insert_many([dict(d) for d in docs])
        try:
            ident = lambda x: x  # noqa: E731
            block, idx = await ls.build_cross_memory(db, {"id": a}, "s2", ident)
            assert block == "" and idx == []                                     # off by default
            os.environ["LEX_CROSS_MEMORY_ENABLED"] = "1"
            block, idx = await ls.build_cross_memory(db, {"id": a}, "s2", ident)
            assert block == ""                                                   # flag on but no consent
            block, idx = await ls.build_cross_memory(db, {"id": a, "memory_consent": {"cross_chat": True}}, "s2", ident)
            assert "Acme" in block and "B: secret" not in block and "separate conversation" in block
            hist, _ = await chat_memory.load_recent_history(db, a, "s1", ident)
            assert [h["user"] for h in hist] == ["A: Acme deposit"]              # same session id, other user excluded
        finally:
            os.environ.pop("LEX_CROSS_MEMORY_ENABLED", None)
            await db.conversations.delete_many({"user_id": {"$in": [a, b]}})
    asyncio.run(go())
