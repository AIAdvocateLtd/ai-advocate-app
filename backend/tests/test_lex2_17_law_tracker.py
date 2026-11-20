"""17-law tracker: scope, baseline, schedule gate, daily run, alerts (mocked official sources, isolated test DB).
Run: cd /app/backend && AIA_NO_PAID=1 python -m pytest tests/test_lex2_17_law_tracker.py -q"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import law_watch as W  # noqa: E402
import lex_lessons  # noqa: E402
from tests.test_stage3_limits import run, LOOP  # noqa: E402
from tests.test_lex2_2c_law_watch import TDB, TODAY, clml, effect, Src  # noqa: E402

COLLS = ("law_watch_records", "law_watch_history", "law_watch_runs", "law_watch_seen", "law_watch_fact_checks", "lex_lessons",
         "law_update_proposals", "law_watch_audit", "law_watch_settings")
ITEMS = W.scope_items(W.SCOPES["all_17"])
ADMIN, SECRET = "admin@aiadvocate.co.uk", "test-secret"
EXT = {"england_wales": "E+W", "scotland": "S", "northern_ireland": "N.I."}


def xml_for(it, **kw):
    part = W._PART.get(it["type"], "section")
    return clml(num=it["section"], part=part, extent=kw.pop("extent", EXT[it["jurisdiction"]]),
                title=f"Act {it['type']}/{it['year']}/{it['number']}", **kw)


def pages(over=None):
    over = over or {}
    out = {}
    for it in ITEMS:
        k = W.item_key(it)
        v = over.get(k, {})
        out[f"{W.LEG}/{k}/data.xml"] = v if isinstance(v, (tuple, Exception)) else (200, xml_for(it, **v))
    return out


def baseline(src=None):
    src = src or Src(pages())
    args = dict(items=ITEMS, today=TODAY, feeds=False, facts=False, scope="all_17")
    dry = run(W.run_check(TDB, src, dry_run=True, **args))
    return run(W.run_check(TDB, src, dry_run=False, confirm=dry["proposal_code"], **args))


def enable():
    run(W.set_switch(TDB, True, ADMIN))
    tok = W.issue_token("x" * 16, "all_17", ADMIN, SECRET)["token"]
    return run(W.set_schedule(TDB, True, ADMIN, tok, SECRET))


class Mail:
    def __init__(self):
        self.sent = []

    async def __call__(self, subject, body):
        self.sent.append((subject, body))


def daily(src, mail=None, fresh_day=True):
    if fresh_day:
        run(TDB.law_watch_audit.delete_many({"_id": {"$regex": "^daily:"}}))
    return run(W.scheduled_run(TDB, "run-1", fetch=src, notify=mail))


def count(c):
    return run(TDB[c].count_documents({}))


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    asyncio.set_event_loop(LOOP)
    monkeypatch.delenv("LAW_WATCH_KILL_SWITCH", raising=False)
    for c in COLLS:
        run(TDB[c].delete_many({}))
    yield
    for c in COLLS:
        run(TDB[c].delete_many({}))


def test_seventeen_unique_valid_entries():
    keys = [W.item_key(it) for it in ITEMS]
    assert len(ITEMS) == 17 and len(set(keys)) == 17
    assert all(W.validate_item(it) is None for it in ITEMS)
    assert ITEMS[:9] == W.WATCHLIST and ITEMS[9:] == W.PROPOSED_WATCHLIST
    assert "nisi/1996/1919/article/126" in keys and "anaw/2016/1/section/173" in keys


def test_baseline_records_all_17_without_review_items_and_is_idempotent():
    run(TDB.lex_lessons.insert_one({"id": "L1", "status": "approved", "source": "fact_pack", "text": "x", "reviewed_by": "x",
                                    "reviewed_at": "2026-11-01", "why": "https://www.legislation.gov.uk/ukpga/1996/18/section/94"}))
    rep = baseline()
    assert len(rep["saved_keys"]) == 17 and count("law_watch_records") == 17 and count("law_update_proposals") == 0
    assert lex_lessons.is_signed_off(run(TDB.lex_lessons.find_one({"id": "L1"})))
    again = baseline()
    assert again["saved_keys"] == [] and again["summary"]["unchanged"] == 17
    assert count("law_watch_history") == 17 and count("law_watch_records") == 17


def test_baseline_records_pending_effects_without_review_item():
    baseline(Src(pages({"ukpga/1996/18/section/108": {"effects": effect(kind="substituted", prov="s. 108")}})))
    rec = run(TDB.law_watch_records.find_one({"key": "ukpga/1996/18/section/108"}))
    assert rec["pending_effects"] and rec["review_pending"] is False and count("law_update_proposals") == 0


def test_schedule_off_does_nothing_and_fetches_nothing():
    src = Src(pages())
    assert daily(src) == {"skipped": "schedule_off"}
    assert src.calls == [] and all(count(c) == 0 for c in COLLS)


def test_schedule_enable_gates():
    tok = W.issue_token("x" * 16, "all_17", ADMIN, SECRET)["token"]
    assert "writes on" in run(W.set_schedule(TDB, True, ADMIN, tok, SECRET))["refused"]
    run(W.set_switch(TDB, True, ADMIN))
    assert "baseline" in run(W.set_schedule(TDB, True, ADMIN, tok, SECRET))["refused"]
    baseline()
    nine = W.issue_token("x" * 16, "nine_provisions", ADMIN, SECRET)["token"]
    assert "17-law" in run(W.set_schedule(TDB, True, ADMIN, nine, SECRET))["refused"]
    assert "not valid" in run(W.set_schedule(TDB, True, ADMIN, tok, "wrong"))["refused"]
    assert "Only the admin" in run(W.set_schedule(TDB, True, "other@x.com", tok, SECRET))["refused"]
    assert run(W.set_schedule(TDB, True, ADMIN, tok, SECRET))["enabled"] is True
    assert "already been used" in run(W.set_schedule(TDB, True, ADMIN, tok, SECRET))["refused"]
    assert run(W.set_schedule(TDB, False, ADMIN))["enabled"] is False
    actions = {a["action"] for a in run(TDB.law_watch_audit.find({}).to_list(50))}
    assert {"schedule_on", "schedule_off", "writes_on"} <= actions


def test_kill_switch_blocks_enable_and_runs(monkeypatch):
    baseline()
    assert enable()["enabled"] is True
    monkeypatch.setenv("LAW_WATCH_KILL_SWITCH", "1")
    assert run(W.schedule_state(TDB))["enabled"] is False
    assert daily(Src(pages())) == {"skipped": "schedule_off"}
    tok = W.issue_token("y" * 16, "all_17", ADMIN, SECRET)["token"]
    assert "Emergency stop" in run(W.set_schedule(TDB, True, ADMIN, tok, SECRET))["refused"]


def test_unchanged_daily_run_no_alerts_no_email():
    baseline()
    enable()
    mail = Mail()
    out = daily(Src(pages()), mail)
    assert out["result"] == "checked" and out["proposed"] == 0 and out["failed"] == 0
    assert mail.sent == [] and count("law_update_proposals") == 0


def test_changes_detected_and_distinguished_then_queued_not_approved():
    baseline()
    enable()
    mail = Mail()
    src = Src(pages({"ukpga/1996/18/section/94": {"text": "Amended wording of the right."},
                     "ukpga/1988/50/section/21": {"repeal": True, "status": "Repealed"},
                     "ukpga/2015/15/section/22": {"effects": effect(prov="s. 22", in_force="2027-04-06")}}))
    out = daily(src, mail)
    props = {p["key"]: p for p in run(TDB.law_update_proposals.find({}).to_list(20))}
    assert out["proposed"] == 3 and set(props) == {"ukpga/1996/18/section/94", "ukpga/1988/50/section/21", "ukpga/2015/15/section/22"}
    assert "wording_amended" in props["ukpga/1996/18/section/94"]["change_types"]
    assert "amendment_pending" in props["ukpga/2015/15/section/22"]["change_types"]
    assert props["ukpga/1988/50/section/21"]["change_types"] != props["ukpga/1996/18/section/94"]["change_types"]
    assert all(p["status"] == "awaiting_review" and p["interpretation"] == "not assessed" and p["decision"] is None
               for p in props.values())
    rec = run(TDB.law_watch_records.find_one({"key": "ukpga/1996/18/section/94"}))
    assert rec["review_pending"] is True and rec["verification"]["D_professional_review"]["verified"] is False
    assert len(mail.sent) == 1 and "3 change(s) to review" in mail.sent[0][0] and "Nothing has been approved" in mail.sent[0][1]
    # same day again: no second run, no duplicates
    assert daily(src, mail, fresh_day=False)["skipped"] == "already_ran_today"
    # next day, same sources: nothing new
    again = daily(src, mail)
    assert again["proposed"] == 0 and count("law_update_proposals") == 3 and len(mail.sent) == 1


def test_unavailable_source_keeps_previous_record_and_emails_failure():
    baseline()
    enable()
    mail = Mail()
    out = daily(Src(pages({"ukpga/2010/15/section/13": (503, ""), "asp/2016/19/section/51": TimeoutError()})), mail)
    assert out["result"] == "checked_with_failures" and out["failed"] == 2 and out["proposed"] == 0
    assert run(TDB.law_watch_records.find_one({"key": "ukpga/2010/15/section/13"}))["version_id"]
    assert len(mail.sent) == 1 and "2 check(s) failed" in mail.sent[0][0] and "source unavailable" in mail.sent[0][1]


def test_whole_run_error_is_recorded_and_emailed(monkeypatch):
    baseline()
    enable()
    mail = Mail()

    async def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(W, "run_check", boom)
    out = daily(Src(pages()), mail)
    assert out["result"] == "error" and "failed" in mail.sent[0][0]
    assert run(W.schedule_state(TDB))["last_run"]["result"] == "error"


def test_extent_and_jurisdiction_respected():
    baseline()
    recs = {r["key"]: r for r in run(TDB.law_watch_records.find({}).to_list(20))}
    assert recs["asp/2016/19/section/51"]["jurisdiction"] == "scotland"
    assert recs["nisi/1996/1919/article/140"]["jurisdiction"] == "northern_ireland"
    assert recs["anaw/2016/1/section/173"]["extent"] == "E+W"
    leg = {"urls": [recs["ukpga/1996/18/section/94"]["url"]]}
    assert run(W.annotate(TDB, leg, "US", None, "")) == []


def test_approval_still_needs_regulated_reviewer():
    baseline()
    enable()
    daily(Src(pages({"ukpga/1996/18/section/94": {"text": "Amended."}})))
    pid = run(TDB.law_update_proposals.find_one({}))["_id"]
    assert "registration number" in run(W.decide_update(TDB, pid, "approve", {"reviewer_name": "A"}, "", ADMIN))["refused"]


def test_cron_endpoint_auth_and_off_state():
    import httpx
    import server
    secret = os.environ.get("WEBHOOK_CRON_SECRET") or ""

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://testserver") as c:
            a = await c.post("/api/cron/law-watch", json={})
            b = await c.post("/api/cron/law-watch", json={}, headers={"Authorization": "Bearer wrong"})
            ok = await c.post("/api/cron/law-watch", json={"run_id": "t"}, headers={"Authorization": f"Bearer {secret}"})
            return a.status_code, b.status_code, ok.status_code, ok.json()
    a, b, code, body = run(go())
    assert secret and a == 401 and b == 401 and code == 200 and body == {"ok": True, "skipped": "schedule_off"}


def test_one_switch_monitoring_on_off_and_emergency_stop():
    assert "incomplete" in run(W.enable_monitoring(TDB, ADMIN, fetch=Src(pages())))["refused"]
    baseline()
    bad = run(W.enable_monitoring(TDB, ADMIN, fetch=Src(pages({"ukpga/2010/15/section/13": (503, "")}))))
    assert "could not be fully checked" in bad["refused"] and not run(W.schedule_state(TDB))["enabled"]
    ok = run(W.enable_monitoring(TDB, ADMIN, fetch=Src(pages())))
    assert ok["enabled"] is True and ok["check_summary"]["unchanged"] == 17
    assert count("law_update_proposals") == 0 and count("law_watch_history") == 17
    ov = run(W.overview(TDB))
    assert ov["monitoring_on"] and ov["baseline_complete"] and ov["records"] == 17 and ov["emergency_stop"] is False
    run(W.set_switch(TDB, True, ADMIN))
    run(W.set_emergency_stop(TDB, True, ADMIN))
    assert run(W.schedule_state(TDB))["enabled"] is False and run(W.switch_state(TDB))["enabled"] is False
    assert daily(Src(pages())) == {"skipped": "schedule_off"}
    assert "Emergency stop" in run(W.enable_monitoring(TDB, ADMIN, fetch=Src(pages())))["refused"]
    run(W.set_emergency_stop(TDB, False, ADMIN))
    assert run(W.schedule_state(TDB))["enabled"] is False  # releasing the stop does not silently restart monitoring
    acts = [a["action"] for a in run(TDB.law_watch_audit.find({}).to_list(50))]
    assert {"schedule_on", "emergency_stop_on", "emergency_stop_off"} <= set(acts)
