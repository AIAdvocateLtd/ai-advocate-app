"""Lex 2.0 law-update integration: detected changes -> review proposals -> qualified sign-off (mocked official sources).
Run: cd /app/backend && AIA_NO_PAID=1 python -m pytest tests/test_lex2_law_update_integration.py -q"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import law_watch as W  # noqa: E402
import lex_lessons  # noqa: E402
from tests.test_stage3_limits import run, LOOP  # noqa: E402
from tests.test_lex2_2c_law_watch import TDB, TODAY, ERA, URL, clml, effect, Src, page, check  # noqa: E402

COLLS = ("law_watch_records", "law_watch_history", "law_watch_runs", "law_watch_seen", "law_watch_fact_checks", "lex_lessons",
         "law_update_proposals", "law_watch_audit")
LESSON = {"id": "L1", "status": "approved", "source": "fact_pack", "text": "Unfair dismissal right.", "reviewed_by": "x",
          "reviewed_at": "2026-11-01", "why": "Source: https://www.legislation.gov.uk/ukpga/1996/18/section/94"}
SRA = {"reviewer_name": "Jane Smith", "regulator": "SRA", "registration_number": "123456"}


@pytest.fixture(autouse=True)
def _clean():
    asyncio.set_event_loop(LOOP)
    for c in COLLS:
        run(TDB[c].delete_many({}))
    yield
    for c in COLLS:
        run(TDB[c].delete_many({}))


def _baseline_then_amend(text2="An employee has the right not to be unfairly dismissed, subject to section 108."):
    run(TDB.lex_lessons.insert_one(dict(LESSON)))
    check(Src(page(clml())))
    return check(Src(page(clml(text=text2))))


def _props():
    return run(TDB.law_update_proposals.find({}).to_list(20))


def test_baseline_is_not_a_change_and_creates_no_proposal():
    run(TDB.lex_lessons.insert_one(dict(LESSON)))
    check(Src(page(clml())))
    assert _props() == []
    assert run(TDB.law_watch_records.find_one({"key": W.item_key(ERA)}))["review_pending"] is False
    assert lex_lessons.is_signed_off(run(TDB.lex_lessons.find_one({"id": "L1"})))


def test_amended_wording_creates_review_proposal_and_withholds_linked_fact():
    rep = _baseline_then_amend()
    assert "wording_amended" in rep["items"][0]["changes"]
    props = _props()
    assert len(props) == 1 and props[0]["status"] == "awaiting_review" and props[0]["interpretation"] == "not assessed"
    assert props[0]["linked_lessons"] == ["L1"]
    lesson = run(TDB.lex_lessons.find_one({"id": "L1"}))
    assert lesson["needs_review"] is True and not lex_lessons.is_signed_off(lesson)
    assert run(TDB.law_watch_records.find_one({"key": W.item_key(ERA)}))["review_pending"] is True


def test_duplicate_detection_not_recorded_twice():
    _baseline_then_amend()
    src = Src(page(clml(text="An employee has the right not to be unfairly dismissed, subject to section 108.")))
    rep = check(src)
    assert rep["items"][0]["write"] == "unchanged" and len(_props()) == 1
    assert run(TDB.law_watch_history.count_documents({"key": W.item_key(ERA)})) == 2


def test_amendment_and_commencement_by_statutory_instrument_detected():
    check(Src(page(clml())))
    rep = check(Src(page(clml(effects=effect(kind="substituted", prov="s. 94", in_force="2027-01-01")))))
    ch = rep["items"][0]["changes"]
    assert "amendment_pending" in ch and "new_affecting_instrument" in ch
    p = _props()[0]
    assert p["affecting_instruments"] == ["ukpga/2025/36"]
    rec = run(TDB.law_watch_records.find_one({"key": W.item_key(ERA)}))
    assert rec["affecting_instruments"] == ["ukpga/2025/36"]


def test_repeal_detected_as_proposal():
    check(Src(page(clml())))
    rep = check(Src(page(clml(status="Repealed", repeal=True))))
    assert set(rep["items"][0]["changes"]) & {"repealed", "partly_repealed", "status_changed"} and len(_props()) == 1


def test_incomplete_or_inconsistent_update_never_promoted():
    check(Src(page(clml())))
    rep = check(Src(page(clml(text="Changed wording.", start="2099-01-01"))))
    assert rep["items"][0]["result"] == "held_unverified" and _props() == []
    assert run(TDB.law_watch_records.find_one({"key": W.item_key(ERA)}))["review_pending"] is False


def test_dry_run_previews_proposals_but_writes_nothing():
    run(TDB.lex_lessons.insert_one(dict(LESSON)))
    check(Src(page(clml())))
    dry = check(Src(page(clml(text="New words entirely."))), dry=True)
    assert dry["proposed_updates"] and dry["proposed_updates"][0]["becomes"] == "awaiting professional review"
    assert _props() == [] and not run(TDB.lex_lessons.find_one({"id": "L1"})).get("needs_review")


def test_signoff_requires_qualified_reviewer_and_does_not_reapprove_facts():
    _baseline_then_amend()
    pid = _props()[0]["_id"]
    assert "registration number" in run(W.decide_update(TDB, pid, "approve", {"reviewer_name": "Jane"}, "", "a"))["refused"]
    assert "regulator" in run(W.decide_update(TDB, pid, "approve", {**SRA, "regulator": "Made-up Body"}, "", "a"))["refused"]
    assert "amending" in run(W.decide_update(TDB, pid, "amend", SRA, "", "a"))["refused"]
    assert run(W.decide_update(TDB, pid, "amend", SRA, "Explain section 108 link", "a"))["status"] == "amend_requested"
    assert run(W.decide_update(TDB, pid, "approve", SRA, "ok", "admin@x"))["status"] == "approved"
    rec = run(TDB.law_watch_records.find_one({"key": W.item_key(ERA)}))
    assert rec["professional_review"]["registration_number"] == "123456" and rec["review_pending"] is False
    assert rec["verification"]["C_interpretation"]["verified"] is False
    assert not lex_lessons.is_signed_off(run(TDB.lex_lessons.find_one({"id": "L1"})))  # re-sign separately
    assert "already approved" in run(W.decide_update(TDB, pid, "reject", SRA, "", "a"))["refused"]
    assert len(_props()[0]["history"]) == 2


def test_reject_needs_name_and_clears_pending():
    _baseline_then_amend()
    pid = _props()[0]["_id"]
    assert "name" in run(W.decide_update(TDB, pid, "reject", {}, "", "a"))["refused"]
    assert run(W.decide_update(TDB, pid, "reject", {"reviewer_name": "Jane"}, "wrong", "a"))["status"] == "rejected"


def test_lex_gets_conservative_caution_while_unreviewed():
    _baseline_then_amend()
    notes = run(W.annotate(TDB, {"urls": [URL]}, "GB", "england", "I was dismissed on 1 November 2026", TODAY))
    assert any("hasn't been reviewed yet" in n and URL in n for n in notes)
    assert any("not a legal interpretation" in n for n in notes)
    assert run(W.annotate(TDB, {"urls": [URL]}, "ES", None, "", TODAY)) == []


def test_links_to_official_source_rules():
    links = run(W.linked_knowledge(TDB, {"url": "https://www.legislation.gov.uk/ukpga/1996/18/section/203"}))
    assert "settlement_agreement" in links["rules"]


def test_scopes_and_free_sources_only():
    assert len(W.WATCHLIST) == 9 and W.SCOPES["nine_provisions"]["items"] is None
    assert W.SCOPES["official_rules_provisions"]["proposed"] is True
    assert all(W.validate_item(it) is None for it in W.PROPOSED_WATCHLIST)
    assert W.scope_items(W.SCOPES["nine_provisions"]) is W.WATCHLIST
    assert W.LEG.startswith("https://www.legislation.gov.uk") and W.kill_switch() in (True, False)


def test_writes_still_need_switch_and_token():
    rep = run(W.authorised_write(TDB, "bad-token", "a", "secret"))
    assert rep.get("refused")


def test_admin_routes_registered():
    paths = {r.path for r in server.app.routes}
    assert {"/api/admin/law-updates", "/api/admin/law-updates/{pid}/decision"} <= paths
