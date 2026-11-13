"""Lex 2.0 Phase 2C activation workflow: admin switch, signed single-use proposal codes, nine-provision scope, audit.
Mocked legislation.gov.uk only. Run: cd /app/backend && AIA_NO_PAID=1 python -m pytest tests/test_lex2_2c_activation.py -q"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import server  # noqa: E402
import law_watch as W  # noqa: E402
from tests.test_stage3_limits import run, db, LOOP  # noqa: E402
from tests.test_lex2_2c_law_watch import TDB, Src, clml, feed  # noqa: E402

ADMIN = {"email": server.ADMIN_EMAILS[0]}
COLLS = ("law_watch_records", "law_watch_history", "law_watch_runs", "law_watch_seen", "law_watch_fact_checks",
         "law_watch_settings", "law_watch_audit", "lex_lessons")
SECRET = "test-secret"


def nine_pages(**overrides):
    pages = {}
    for it in W.WATCHLIST:
        pages[f"{W.LEG}/{W.item_key(it)}/data.xml"] = (200, clml(num=it["section"], part=W._PART.get(it["type"], "section")))
    year = str(datetime.now(timezone.utc).year)
    for t in W.NEW_FEEDS:
        pages[f"{W.LEG}/{t}/{year}/data.feed"] = (200, feed((f"{t}/{year}/1", "Some Act 2026")))
    pages.update(overrides)
    return pages


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    asyncio.set_event_loop(LOOP)
    monkeypatch.delenv("LAW_WATCH_KILL_SWITCH", raising=False)
    monkeypatch.setattr(server, "db", TDB)
    monkeypatch.setattr(server, "JWT_SECRET", SECRET)
    for c in COLLS:
        run(TDB[c].delete_many({}))
    yield
    for c in COLLS:
        run(TDB[c].delete_many({}))


def use(monkeypatch, pages):
    src = Src(pages)
    monkeypatch.setattr(W, "_fetch", src)
    return src


def dry():
    return run(server.admin_law_watch_dry_run(server.LawWatchScope(), admin=ADMIN))


def apply(token, admin=ADMIN):
    return run(server.admin_law_watch_apply(server.LawWatchApply(token=token), admin=admin))


def switch(on):
    return run(server.admin_law_watch_switch(server.LawWatchSwitch(enabled=on), admin=ADMIN))


def refused(fn, *a, **k):
    with pytest.raises(HTTPException) as e:
        fn(*a, **k)
    return e.value


# ------------------------------------------------------------------ access control
@pytest.mark.parametrize("method,path", [("get", "/api/admin/law-watch/status"), ("post", "/api/admin/law-watch/switch"),
                                         ("post", "/api/admin/law-watch/dry-run"), ("post", "/api/admin/law-watch/apply"),
                                         ("get", "/api/admin/law-watch/records"), ("get", "/api/admin/law-watch/runs")])
def test_unauthenticated_requests_rejected(method, path):
    c = TestClient(server.app)
    r = c.get(path) if method == "get" else c.post(path, json={})
    assert r.status_code in (401, 403)


def test_non_admin_rejected():
    e = refused(lambda: run(server.require_admin({"email": "customer@example.com"})))
    assert e.status_code == 403


# ------------------------------------------------------------------ switch
def test_writes_off_by_default_and_dry_run_writes_nothing(monkeypatch):
    use(monkeypatch, nine_pages())
    st = run(server.admin_law_watch_status(_=ADMIN))
    assert st["enabled"] is False and st["monitoring_scheduled"] is False and st["customer_notifications"] is False
    d = dry()
    assert d["dry_run"] and d["summary"]["to_write"] == 9 and d["token"] and d["expires_at"]
    assert all(run(TDB[c].count_documents({})) == 0 for c in COLLS)
    assert refused(apply, d["token"]).status_code == 409  # switch OFF -> refused
    assert run(TDB.law_watch_records.count_documents({})) == 0


def test_switch_expires_by_itself_and_turns_off_immediately():
    assert switch(True)["enabled"] and switch(False)["enabled"] is False
    switch(True)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    run(TDB.law_watch_settings.update_one({"_id": "writes"}, {"$set": {"until": past}}))
    assert run(W.switch_state(TDB))["enabled"] is False


def test_emergency_kill_switch_blocks_everything(monkeypatch):
    use(monkeypatch, nine_pages())
    switch(True)
    d = dry()
    monkeypatch.setenv("LAW_WATCH_KILL_SWITCH", "1")
    assert run(W.switch_state(TDB))["enabled"] is False
    assert "emergency stop" in refused(apply, d["token"]).detail
    assert refused(switch, True).status_code == 403
    assert run(TDB.law_watch_records.count_documents({})) == 0


# ------------------------------------------------------------------ proposal codes
def test_full_flow_saves_only_nine_provisions_and_audits(monkeypatch):
    use(monkeypatch, nine_pages())
    switch(True)
    d = dry()
    rep = apply(d["token"])
    assert rep["written"] and len(rep["saved_keys"]) == 9 and rep["scope"] == "nine_provisions" and rep["actor"] == ADMIN["email"]
    assert run(TDB.law_watch_records.count_documents({})) == 9 and run(TDB.law_watch_history.count_documents({})) == 9
    assert run(TDB.law_watch_seen.count_documents({})) == 0 and run(TDB.law_watch_fact_checks.count_documents({})) == 0
    run_doc = run(TDB.law_watch_runs.find_one({}))
    assert run_doc["authorisation_id"] and run_doc["saved_keys"] == rep["saved_keys"]
    acts = [a["action"] for a in run(TDB.law_watch_audit.find({}).sort("at", 1).to_list(10))]
    assert acts == ["writes_on", "apply"]
    a = run(TDB.law_watch_audit.find_one({"action": "apply"}))
    assert a["actor"] == ADMIN["email"] and a["result"] == "saved" and len(a["saved_keys"]) == 9 and a["proposal_code"] == d["proposal_code"]
    for r in run(TDB.law_watch_records.find({}, {"_id": 0}).to_list(20)):
        assert r["verification"]["C_interpretation"]["verified"] is False
        assert r["verification"]["D_professional_review"]["verified"] is False
        assert r["commencement"]["date"] is None and r["provenance"]["source"] == "legislation.gov.uk"


def test_missing_tampered_or_other_admin_code_rejected(monkeypatch):
    use(monkeypatch, nine_pages())
    switch(True)
    d = dry()
    payload, _, sig = d["token"].partition(".")
    assert "not valid" in refused(apply, "x" * 30).detail
    assert "not valid" in refused(apply, payload + "." + "0" * 32).detail
    forged = W.issue_token("deadbeefdeadbeef", "nine_provisions", ADMIN["email"], "wrong-secret")["token"]
    assert "not valid" in refused(apply, forged).detail
    assert "Only the admin" in refused(apply, d["token"], {"email": "other-admin@aiadvocate.co.uk"}).detail
    assert run(TDB.law_watch_records.count_documents({})) == 0


def test_expired_code_rejected(monkeypatch):
    use(monkeypatch, nine_pages())
    switch(True)
    monkeypatch.setattr(W, "TOKEN_MINUTES", -1)
    assert "expired" in refused(apply, dry()["token"]).detail
    assert run(TDB.law_watch_records.count_documents({})) == 0


def test_changed_source_after_dry_run_rejected(monkeypatch):
    use(monkeypatch, nine_pages())
    switch(True)
    d = dry()
    key = f"{W.LEG}/ukpga/1996/18/section/94/data.xml"
    use(monkeypatch, nine_pages(**{key: (200, clml(text="Changed wording."))}))
    assert "does not match" in refused(apply, d["token"]).detail
    assert run(TDB.law_watch_records.count_documents({})) == 0
    assert run(TDB.law_watch_audit.find_one({"action": "apply"}))["result"] == "refused"


def test_code_single_use_and_no_duplicates(monkeypatch):
    use(monkeypatch, nine_pages())
    switch(True)
    d = dry()
    apply(d["token"])
    assert "already been used" in refused(apply, d["token"]).detail
    d2 = dry()
    assert d2["summary"]["to_write"] == 0 and d2["summary"]["unchanged"] == 9
    rep = apply(d2["token"])
    assert rep["saved_keys"] == []
    assert run(TDB.law_watch_records.count_documents({})) == 9 and run(TDB.law_watch_history.count_documents({})) == 9


def test_unavailable_and_unverified_never_saved(monkeypatch):
    import httpx
    use(monkeypatch, nine_pages(**{f"{W.LEG}/ukpga/1989/41/section/1/data.xml": httpx.ReadTimeout("t"),
                                   f"{W.LEG}/ukpga/2010/15/section/13/data.xml": (200, clml(num="13", valid="2099-01-01"))}))
    switch(True)
    d = dry()
    assert d["summary"]["unavailable"] == 1 and d["summary"]["held_unverified"] == 1 and d["summary"]["to_write"] == 7
    rep = apply(d["token"])
    assert len(rep["saved_keys"]) == 7 and "ukpga/1989/41/section/1" not in rep["saved_keys"]
    assert "ukpga/2010/15/section/13" not in rep["saved_keys"]


def test_unsupported_scope_rejected():
    assert refused(lambda: run(server.admin_law_watch_dry_run(server.LawWatchScope(scope="everything"), admin=ADMIN))).status_code == 400


def test_professional_review_needs_switch_on():
    e = refused(lambda: run(server.admin_law_watch_review("ukpga/1996/18/section/94", server.LawWatchReview(
        reviewer_name="A Solicitor", regulator="SRA", registration_number="123456"), admin=ADMIN)))
    assert e.status_code == 403


# ------------------------------------------------------------------ customer data
def test_customer_and_fact_records_unchanged(monkeypatch):
    names = ("users", "cases", "conversations", "lex_lessons", "llm_usage", "subscriptions", "documents")
    before = {c: run(db[c].count_documents({})) for c in names}
    signed = run(db.lex_lessons.count_documents({"reviewed_by": {"$ne": None}}))
    run(TDB.lex_lessons.insert_one({"id": "L1", "status": "approved", "source": "fact_pack", "text": "x", "reviewed_by": None}))
    use(monkeypatch, nine_pages())
    switch(True)
    apply(dry()["token"])
    assert before == {c: run(db[c].count_documents({})) for c in names}
    assert signed == run(db.lex_lessons.count_documents({"reviewed_by": {"$ne": None}}))
    assert run(TDB.lex_lessons.find_one({"id": "L1"}, {"_id": 0})) == {"id": "L1", "status": "approved", "source": "fact_pack",
                                                                       "text": "x", "reviewed_by": None}
    assert run(db.law_watch_records.count_documents({})) == 0  # preview DB untouched
