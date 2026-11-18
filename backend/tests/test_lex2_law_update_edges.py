"""Edge cases for Phase 2C law-update proposals (isolated test DB aia_law_watch_test, mocked legislation.gov.uk).
Run: cd /app/backend && AIA_NO_PAID=1 python -m pytest tests/test_lex2_law_update_edges.py -q"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import law_watch as W  # noqa: E402
from tests.test_stage3_limits import run, LOOP  # noqa: E402
from tests.test_lex2_2c_law_watch import TDB, TODAY, ERA, URL, clml, Src, page, check  # noqa: E402
from tests.test_lex2_law_update_integration import COLLS, LESSON, SRA, _baseline_then_amend, _props  # noqa: E402

AMENDED = "An employee has the right not to be unfairly dismissed, subject to section 108."


@pytest.fixture(autouse=True)
def _clean():
    asyncio.set_event_loop(LOOP)
    for c in COLLS:
        run(TDB[c].delete_many({}))
    yield
    for c in COLLS:
        run(TDB[c].delete_many({}))


# decide_update validation
def test_unknown_decision_and_unknown_id():
    _baseline_then_amend()
    pid = _props()[0]["_id"]
    assert run(W.decide_update(TDB, pid, "delete", SRA, "", "a"))["refused"] == "Unknown decision."
    assert run(W.decide_update(TDB, "nope", "approve", SRA, "", "a"))["refused"] == "No such update."


def test_approve_needs_every_reviewer_field():
    _baseline_then_amend()
    pid = _props()[0]["_id"]
    for missing in ("reviewer_name", "regulator", "registration_number"):
        assert run(W.decide_update(TDB, pid, "approve", {**SRA, missing: ""}, "", "a")).get("refused"), missing
    assert _props()[0]["status"] == "awaiting_review"


def test_amend_needs_name_and_notes():
    _baseline_then_amend()
    pid = _props()[0]["_id"]
    assert "name" in run(W.decide_update(TDB, pid, "amend", {}, "notes", "a"))["refused"]
    assert "amending" in run(W.decide_update(TDB, pid, "amend", {"reviewer_name": "J"}, "   ", "a"))["refused"]


def test_rejected_cannot_be_redecided_but_amend_requested_can():
    _baseline_then_amend()
    pid = _props()[0]["_id"]
    assert run(W.decide_update(TDB, pid, "amend", {"reviewer_name": "J"}, "fix", "a"))["status"] == "amend_requested"
    assert run(W.decide_update(TDB, pid, "reject", {"reviewer_name": "J"}, "", "a"))["status"] == "rejected"
    for d in ("approve", "amend", "reject"):
        assert "already rejected" in run(W.decide_update(TDB, pid, d, SRA, "x", "a"))["refused"]
    rec = run(TDB.law_watch_records.find_one({"key": W.item_key(ERA)}))
    assert rec["review_pending"] is False and rec["change_rejected"] is True


def test_regulator_whitespace_and_case_normalised():  # fixed after iteration 57: stripped and upper-cased
    _baseline_then_amend()
    pid = _props()[0]["_id"]
    r = run(W.decide_update(TDB, pid, "approve", {**SRA, "regulator": " sra "}, "", "a"))
    assert r["status"] == "approved"
    rec = run(TDB.law_watch_records.find_one({"key": W.item_key(ERA)}))
    assert rec["professional_review"]["regulator"] == "SRA" and rec["verification"]["D_professional_review"]["verified"]


def test_concurrent_decisions_only_one_wins():  # race: find_one then unconditional update_one
    _baseline_then_amend()
    pid = _props()[0]["_id"]

    async def both():
        return await asyncio.gather(W.decide_update(TDB, pid, "approve", SRA, "", "a"),
                                    W.decide_update(TDB, pid, "reject", {"reviewer_name": "B"}, "", "b"))
    res = run(both())
    oks = [r for r in res if r.get("ok")]
    assert len(oks) == 1, res


# proposal creation
def test_duplicate_proposals_not_created_and_id_is_version_id():
    _baseline_then_amend()
    check(Src(page(clml(text=AMENDED))))  # same version again
    props = _props()
    rec = run(TDB.law_watch_records.find_one({"key": W.item_key(ERA)}))
    assert len(props) == 1 and props[0]["_id"] == rec["version_id"]


def test_held_unverified_never_creates_proposal():
    run(TDB.lex_lessons.insert_one(dict(LESSON)))
    check(Src(page(clml())))
    rep = check(Src(page(clml(text=AMENDED, start="2027-06-01"))))  # future start date while in force -> anomaly
    assert rep["items"][0]["result"] == "held_unverified"
    assert _props() == []
    assert not run(TDB.lex_lessons.find_one({"id": "L1"})).get("needs_review")


def test_dry_run_never_flags_lessons_or_creates_proposals():
    run(TDB.lex_lessons.insert_one(dict(LESSON)))
    check(Src(page(clml())))
    check(Src(page(clml(text=AMENDED))), dry=True)
    assert _props() == [] and not run(TDB.lex_lessons.find_one({"id": "L1"})).get("needs_review")


def test_unlinked_lessons_untouched():
    run(TDB.lex_lessons.insert_one({**LESSON, "id": "L2", "why": "Source: https://www.legislation.gov.uk/ukpga/2010/15/section/13"}))
    _baseline_then_amend()
    assert not run(TDB.lex_lessons.find_one({"id": "L2"})).get("needs_review")


def test_act_number_prefix_false_positive():  # ukpga/1996/18 regex also matches ukpga/1996/180
    run(TDB.lex_lessons.insert_one({**LESSON, "id": "L3", "why": "Source: https://www.legislation.gov.uk/ukpga/1996/180/section/1"}))
    links = run(W.linked_knowledge(TDB, {"url": URL}))
    assert "L3" not in links["lessons"], links


# annotate caution
def test_no_caution_after_rejection_or_for_non_uk():
    _baseline_then_amend()
    pid = _props()[0]["_id"]
    for c in ("US", "IE", "FR"):
        assert run(W.annotate(TDB, {"urls": [URL]}, c, None, "", TODAY)) == []
    run(W.decide_update(TDB, pid, "reject", {"reviewer_name": "J"}, "", "a"))
    notes = run(W.annotate(TDB, {"urls": [URL]}, "GB", "england", "", TODAY))
    assert not any("hasn't been reviewed yet" in n for n in notes)


def test_no_caution_on_baseline():
    check(Src(page(clml())))
    notes = run(W.annotate(TDB, {"urls": [URL]}, "GB", "england", "", TODAY))
    assert not any("hasn't been reviewed yet" in n for n in notes)
