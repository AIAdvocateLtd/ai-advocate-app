"""Date safeguard — dates are only tied to the legal event the customer linked them to (simulated; no AI calls)."""
import asyncio
import json
from datetime import date

import pytest

import date_guard as G
import deadline_calc as D

FAKE = {}


class FakeChat:
    def __init__(self, *a, **kw):
        pass

    def with_model(self, *a):
        return self

    def with_params(self, **kw):
        return self

    async def send_message(self, msg):
        FAKE["prompt"] = msg.text
        return json.dumps({"calcs": FAKE["calcs"]})


@pytest.fixture(autouse=True)
def _fake(monkeypatch):
    monkeypatch.setattr(D, "LlmChat", FakeChat)


def build(message, calcs, context=""):
    FAKE["calcs"] = calcs
    return asyncio.run(D.build_deadlines(message, context, "x", "england"))


ET = {"type": "employment_tribunal", "event_date": "2026-11-09", "jurisdiction": "england"}


def test_dismissal_only_extractor_copies_date_into_acas():
    # The real-world bug: extractor put the dismissal date into acas_date.
    block, rem = build("My employer dismissed me on 9 November 2026. Can I claim unfair dismissal?",
                       [{**ET, "acas_date": "2026-11-09", "certificate_date": None}])
    assert "ACAS was contacted" not in block and "not given an ACAS notification date" in block
    assert "did not state the ACAS/LRA early conciliation notification date" in block
    assert [r["title"] for r in rem] == ["Latest date to start ACAS Early Conciliation",
                                         "ET1 tribunal claim — normal time limit (can be extended by ACAS Early Conciliation)"]
    assert all(r["due"] == date(2027, 5, 8) for r in rem)
    assert "Never copy the dismissal/decision/notice date into another field" in D.EXTRACT_SYSTEM


def test_dismissal_acas_status_unknown_asks():
    block, rem = build("I was sacked on 9 November 2026, not sure what to do next.", [dict(ET)])
    assert "ask whether ACAS has been contacted" in block and len(rem) == 2


def test_acas_date_explicitly_given():
    block, rem = build("I was dismissed on 9 November 2026 and contacted ACAS on 20 November 2026.",
                       [{**ET, "acas_date": "2026-11-20"}])
    assert "ACAS was contacted on Friday 20 November 2026" in block
    assert "did not state" not in block and "no certificate date is known" in block


def test_certificate_date_explicitly_given():
    msg = ("I was dismissed on 9 November 2026. I notified ACAS on 20 November 2026 and got the certificate on "
           "15 December 2026.")
    block, rem = build(msg, [{**ET, "acas_date": "2026-11-20", "certificate_date": "2026-12-15"}])
    assert "the ET1 claim deadline becomes" in block
    assert "Submit ET1 tribunal claim (after ACAS certificate)" in [r["title"] for r in rem]


def test_certificate_without_acas_is_not_used():
    safe, notes = G.validate([{**ET, "certificate_date": "2026-12-15"}],
                             "I was dismissed on 9 November 2026 and I have a certificate dated 15 December 2026.")
    assert safe[0]["certificate_date"] is None and any("without an ACAS notification date" in n for n in notes)


def test_conflicting_dismissal_dates_ask():
    block, rem = build("I was dismissed on 9 November 2026. Actually my letter says I was dismissed on 12 November 2026.",
                       [dict(ET)])
    assert rem == [] and "more than one date" in block and "NO APP-CALCULATED DATE" in block


def test_dates_from_earlier_customer_messages_count():
    block, rem = build("And I contacted ACAS on 20 November 2026.", [{**ET, "acas_date": "2026-11-20"}],
                       context="My employer dismissed me on 9 November 2026.")
    assert "ACAS was contacted on Friday 20 November 2026" in block


def test_relative_dates_accepted_only_for_linked_event():
    safe, notes = G.validate([{**ET, "event_date": "2026-11-09", "acas_date": "2026-11-09"}],
                             "I was fired last week.")
    assert safe[0]["event_date"] == "2026-11-09" and safe[0]["acas_date"] is None


def test_other_categories_dates_kept_to_their_events():
    # Benefits: decision date must not be reused as an MRN date.
    safe, notes = G.validate([{"type": "benefit_challenge", "decision_date": "2026-11-02", "mrn_date": "2026-11-02"}],
                             "My PIP decision letter is dated 2 November 2026.")
    assert safe[0]["mrn_date"] is None and safe[0]["decision_date"] == "2026-11-02"
    # Housing: notice date not reused as tenancy start date.
    safe, _ = G.validate([{"type": "tenancy_notice", "served_date": "2026-11-01", "tenancy_start_date": "2026-11-01",
                           "jurisdiction": "wales"}], "My landlord served a section 173 notice on 1 November 2026.")
    assert safe[0]["tenancy_start_date"] is None
    # Immigration: an ILR date the customer never gave is dropped and the calculation is skipped.
    safe, notes = G.validate([{"type": "citizenship_after_ilr", "ilr_date": "2026-01-05"}],
                             "My visa started on 5 January 2021. When can I get citizenship?")
    assert safe == [] and any("ILR grant date" in n for n in notes)
    # Family: divorce application date kept when stated.
    safe, _ = G.validate([{"type": "divorce", "application_date": "2026-10-01"}], "I applied for divorce on 1 October 2026.")
    assert safe[0]["application_date"] == "2026-10-01"
    # Civil: debt date kept when stated.
    safe, _ = G.validate([{"type": "limitation", "event_date": "2021-03-04", "claim_kind": "debt", "jurisdiction": "england"}],
                         "He owes me money from a loan I gave on 4 March 2021.")
    assert safe[0]["event_date"] == "2021-03-04"


def test_answer_guard_removes_invented_acas_contact():
    ans = "You contacted ACAS on 9 November 2026, so the clock is paused. The tribunal limit is 6 months less one day."
    out, n = G.guard_answer(ans, "My employer dismissed me on 9 November 2026.")
    assert n == 1 and "You contacted ACAS" not in out and "have not said whether you have contacted ACAS" in out
    ok, n2 = G.guard_answer(ans, "I was dismissed on 9 November 2026 and contacted ACAS the same day.")
    assert n2 == 0 and ok == ans
    cond, n3 = G.guard_answer("If you have contacted ACAS, tell me the date.", "I was dismissed.")
    assert n3 == 0
    out, n4 = G.guard_answer("You have already appealed the decision.", "My PIP was refused on 2 November 2026.")
    assert n4 == 1 and "whether you have appealed" in out


def test_answer_guard_wired_into_finalize():
    import server
    out, rep = asyncio.run(server._lex_finalize(
        "You contacted ACAS on 9 November 2026. Your ET1 deadline is 8 May 2027.", [], {"status": "ok", "sources": []},
        "high", "en", "My employer dismissed me on 9 November 2026.",
        {"customer_text": "My employer dismissed me on 9 November 2026."}))
    assert "You contacted ACAS" not in out and rep["unstated_event_claims_fixed"] == 1


def test_fictional_scenario_no_reminders():
    import server
    msg = "Hypothetically, if someone was dismissed on 9 November 2026, when is the deadline?"
    block, rem = build(msg, [dict(ET)])
    assert rem and server._HYPOTHETICAL_RE.search(msg)  # server drops proposals for hypotheticals
