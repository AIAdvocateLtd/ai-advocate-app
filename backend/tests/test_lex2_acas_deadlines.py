"""Lex 2.0 — official Acas guidance retrieval + legal deadline times (simulated; no paid AI, no paid search).
acas.org.uk and legislation.gov.uk are free public sites; network tests use them read-only."""
import asyncio
import uuid
from datetime import date

import pytest

import deadline_calc as D
import lex_safety
import official_guidance as G
import rag
import server
from tests.test_stage3_limits import run, db


@pytest.fixture(autouse=True)
def _clear():
    G._cache.clear()
    yield
    G._cache.clear()


# ---------------- Issue 1: Acas guidance
def test_acas_code_retrieved_and_excerpt_supports_point():
    items, failed = run(G.guidance_sources("My employer started a disciplinary for poor performance — does the Acas Code apply?"))
    assert not failed and [i["acas_key"] for i in items] == ["code", "performance"]
    code = items[0]
    assert code["url"] == "https://www.acas.org.uk/acas-code-of-practice-on-disciplinary-and-grievance-procedures/html"
    assert "Disciplinary situations include misconduct and/ or poor performance" in code["content"]
    assert "capability procedure" in code["content"] and "official guidance; wording retrieved" in code["title"]


def test_cache_avoids_refetch_and_failure_is_disclosed(monkeypatch):
    calls = []

    async def boom(url):
        calls.append(url)
        raise RuntimeError("acas down")
    monkeypatch.setattr(G, "_fetch", boom)
    items, failed = run(G.guidance_sources("Is poor performance covered by the Acas Code?"))
    items2, _ = run(G.guidance_sources("Is poor performance covered by the Acas Code?"))
    assert items == items2 == [] and failed == ["code", "performance"] and len(calls) == 2  # failure cached
    out, notes = G.disclose("The Acas Code of Practice covers poor performance.", [], failed)
    assert notes and "could not be retrieved" in notes[0] and "not been checked" in notes[0]


def test_ok_cache_reused(monkeypatch):
    run(G.get_page("code"))
    monkeypatch.setattr(G, "_fetch", lambda url: (_ for _ in ()).throw(AssertionError("refetched")))
    assert run(G.get_page("code"))["key"] == "code"


def test_not_retrieved_claim_reconciled():
    out, notes = G.disclose("The Acas Code covers poor performance. I have not retrieved the Code text itself.", ["code"], [])
    assert "not retrieved" not in out and "was retrieved from acas.org.uk" in out and not notes


def test_no_acas_fetch_for_unrelated_questions():
    assert G.pick("My landlord kept my deposit") == []


def test_guidance_citation_must_support_point():
    src = [{"n": 1, "title": "Acas Code", "content": "disciplinary situations include misconduct and/ or poor performance. "
            "capability procedure basic principles of fairness", "guidance": True}]
    cits = [{"n": 1, "title": "Acas Code", "url": "https://www.acas.org.uk/x", "source": "official"}]
    out, rep = lex_safety.verify_citations("Poor performance is a disciplinary situation under the Code [1]. "
                                           "You can claim holiday pay for bank holidays [1].", cits, src)
    assert "Code [1]" in out and "holidays [1]" not in out and rep["unsupported_markers"] == 1


def test_research_includes_acas_and_flags(monkeypatch):
    async def tav(q, include_domains=None, max_results=3, search_depth="basic"):
        return [], "ok"
    monkeypatch.setattr(rag, "_tavily_search_ex", tav)
    monkeypatch.setattr(rag, "is_enabled", lambda: True)
    r = run(rag.research("I was dismissed for poor performance without a disciplinary hearing. Does the Acas Code apply?"))
    assert r["status"] == "ok" and r["guidance_keys"][0] == "code"
    assert any(c["url"].startswith("https://www.acas.org.uk/") for c in r["citations"])
    assert any(s.get("guidance") for s in r["sources"]) and "fetched from Acas just now" in r["block"]


def test_source_list_keeps_cited_and_named_acas_only():
    code_url = G.BASE + G.PAGES[0][2]
    cits = [{"n": 1, "title": "Acas Code", "url": code_url, "source": "official"},
            {"n": 2, "title": "Acas dismissals", "url": "https://www.acas.org.uk/dismissals", "source": "official"}]
    research = {"status": "ok", "sources": [{"n": 1, "title": "Acas Code", "content": "poor performance", "guidance": True},
                                            {"n": 2, "title": "d", "content": "x", "guidance": True}],
                "guidance_keys": ["code", "dismissals"], "guidance_failed": []}
    out, rep = run(server._lex_finalize("Under the Acas Code of Practice, poor performance can be a disciplinary matter.",
                                        cits, research, "high", "en", "dismissed for poor performance", {}))
    assert [c["n"] for c in cits] == [1] and rep["acas_guidance"]["retrieved"] == ["code", "dismissals"]


# ---------------- Issue 2: deadline times
def test_deadline_is_1159pm_uk_with_gmt_bst():
    assert D.deadline_iso(date(2027, 3, 27)) == "2027-03-27T23:59:00+00:00"   # GMT (clocks change 28 Mar 2027)
    assert D.deadline_iso(date(2027, 3, 29)) == "2027-03-29T23:59:00+01:00"   # BST
    assert D.deadline_iso(date(2026, 10, 24)) == "2026-10-24T23:59:00+01:00"  # BST (clocks change 25 Oct 2026)
    assert D.deadline_iso(date(2026, 10, 26)) == "2026-10-26T23:59:00+00:00"  # GMT
    lab = D.deadline_label(date(2027, 3, 29), "Latest date to start ACAS Early Conciliation")
    assert lab["deadline_label"] == "Monday 29 March 2027, 11:59pm UK time (BST)" and lab["deadline_time_confirmed"]
    assert "09:00" not in str(lab) and "9am" not in lab["deadline_label"] and "8am UK time" in lab["reminder_schedule"]


def test_acas_vs_et1_labels_and_uncertain_times():
    ec = D.deadline_label(date(2027, 1, 15), "Latest date to start ACAS Early Conciliation")
    et1 = D.deadline_label(date(2027, 1, 15), "ET1 tribunal claim — normal time limit (can be extended by ACAS Early Conciliation)")
    assert "online" in ec["deadline_basis"] and "phone line" in ec["deadline_basis"]
    assert "Early Conciliation has extended" in et1["deadline_basis"] and et1["deadline_label"].endswith("(GMT)")
    for t in ("Deposit must be protected by", "Latest date to start LRA early conciliation",
              "Latest date to start ACAS/LRA early conciliation (safe date)"):
        lab = D.deadline_label(date(2027, 1, 15), t)
        assert not lab["deadline_time_confirmed"] and "cut-off time to be confirmed" in lab["deadline_label"]


def test_weekend_deadline_and_separate_reminders():
    items = D.compute([{"type": "employment_tribunal", "event_date": "2026-11-09", "jurisdiction": "england"}])
    assert [d for _, _, d in items] == [date(2027, 5, 8)] * 2  # Saturday
    assert "falls on a weekend" in items[0][0] and "do not assume the deadline moves" in items[0][0]
    prop = server._propose_reminders([{"title": t, "due": d, "note": D.reminder_note(t)} for _, t, d in items])
    assert [p["title"] for p in prop] == ["Latest date to start ACAS Early Conciliation",
                                         "ET1 tribunal claim — normal time limit (can be extended by ACAS Early Conciliation)"]
    assert all(p["due_at"] == "2027-05-08T23:59:00+01:00" and "Saturday 08 May 2027, 11:59pm UK time (BST)" == p["deadline_label"]
               for p in prop)


def test_reminders_need_confirmation_and_hypotheticals_blocked():
    src = open(server.__file__).read()
    chat_paths = src[src.index('@api_router.post("/lex/chat")'):src.index("async def _released_stream")]
    assert "db.reminders.insert" not in chat_paths and "_save_auto_reminders" not in src
    assert server._HYPOTHETICAL_RE.search("Hypothetically, if I was dismissed on 9 November 2026")


def test_existing_reminders_unchanged_and_new_fields_optional():
    uid = f"TEST_rem_{uuid.uuid4().hex}"
    old = {"id": f"old-{uid}", "user_id": uid, "title": "Contact ACAS (tribunal time limit)", "due_at": "2027-05-08T09:00:00+01:00",
           "kind": "deadline", "status": "pending", "source": "lex_auto", "description": "old"}
    run(db.reminders.insert_one(dict(old)))
    try:
        user = {"id": uid}
        plain = run(server.create_reminder(server.ReminderCreate(title="Manual", due_at="2027-01-01T10:00:00+00:00"), user))
        assert "deadline_label" not in plain
        new = run(server.create_reminder(server.ReminderCreate(
            title="Latest date to start ACAS Early Conciliation", due_at="2027-05-08T23:59:00+01:00",
            **{k: v for k, v in D.deadline_label(date(2027, 5, 8), "Latest date to start ACAS Early Conciliation").items()
               if k in ("deadline_label", "deadline_basis", "deadline_time_confirmed")}), user))
        assert new["deadline_label"].endswith("11:59pm UK time (BST)") and new["deadline_time_confirmed"] is True
        after = run(db.reminders.find_one({"id": old["id"]}, {"_id": 0}))
        assert after == old
    finally:
        run(db.reminders.delete_many({"user_id": uid}))
