"""Phase 2A-1 fact review system — simulated only (run with AIA_NO_PAID=1). Uses a throwaway Mongo database."""
import asyncio
import os
import uuid

from motor.motor_asyncio import AsyncIOMotorClient

import fact_review
import lex_lessons as LL
import rag
import server

ADMIN = {"id": "adm", "email": "founder@aiadvocate.co.uk"}


def dep():
    return {}


async def _setup():
    name = f"test_2a1_{uuid.uuid4().hex[:8]}"
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[name]
    await LL.seed_fact_packs(db)  # same code path production used: 38 facts, then the review records
    router, _ = LL.build_router(db, dep, dep, lambda s: s, lambda s: s, "x", lambda: "", None)
    patch = next(r.endpoint for r in router.routes if r.path == "/admin/lex-lessons/{lesson_id}" and "PATCH" in r.methods)
    lst = next(r.endpoint for r in router.routes if r.path == "/admin/lex-lessons" and "GET" in r.methods)
    return db, name, patch, lst


def run_with_db(fn):
    async def go():
        saved = dict(LL._cache)
        db, name, patch, lst = await _setup()
        try:
            await fn(db, patch, lst)
        finally:
            await db.client.drop_database(name)
            LL._cache.clear()
            LL._cache.update(saved)
    asyncio.run(go())


def test_assert_no_paid_mode():
    assert os.environ.get("AIA_NO_PAID") == "1"


def test_all_38_facts_get_records_nothing_signed():
    async def fn(db, patch, lst):
        facts = await db.lex_lessons.find({"source": "fact_pack"}, {"_id": 0}).to_list(100)
        notes = await db.lex_lessons.find({"source": "law_note"}, {"_id": 0}).to_list(10)
        assert len(facts) == 38 and len(notes) == 5
        assert all(f.get("review_meta") and f["text"] == f["original_text"] and not f.get("reviewed_by") for f in facts)
        recs = [f["review_meta"]["recommendation"] for f in facts]
        assert (recs.count("approve"), recs.count("correct"), recs.count("withhold")) == (18, 14, 6)
        assert sum(1 for f in facts if f.get("proposed_text")) == 14
        assert all(n["status"] == "pending" and n["review_meta"]["source_url"] for n in notes)
        await LL.seed_review_records(db)  # idempotent
        assert await db.lex_lessons.count_documents({"source": "law_note"}) == 5
        await LL.refresh_lessons(db)
        assert LL.fact_pack_block("employer dismissed me, landlord, divorce, benefits, visa") == ""
        assert LL.lessons_block() == ""
        rows = (await lst(ADMIN))["lessons"]
        assert not any(r["used_by_lex"] for r in rows)
    run_with_db(fn)


def test_fixed_notes_not_in_prompt_until_signed_off():
    async def fn(db, patch, lst):
        await LL.refresh_lessons(db)
        p = server.lex_system_prompt("en", "GB", "employment", "england")
        assert "RECENT UK LAW CHANGES" not in p and "6 months minus 1 day" not in p
        note = await db.lex_lessons.find_one({"source": "law_note", "text": {"$regex": "^Employment tribunal"}}, {"_id": 0})
        assert "transitional rules may give longer" not in note["text"]
        await patch(note["id"], LL.LessonPatch(status="approved"), ADMIN)
        p = server.lex_system_prompt("en", "GB", "employment", "england")
        assert "6 months minus 1 day" in p and "9 November 2026" in p and "CONFIRMED LESSONS" in p
        row = await db.lex_lessons.find_one({"id": note["id"]}, {"_id": 0})
        assert row["reviewed_by"] == ADMIN["email"] and row["review_meta"]["source_url"].startswith("https://www.acas.org.uk")
        assert row["next_review_at"] == "2027-05-11"
    run_with_db(fn)


def test_correction_signoff_keeps_version_and_metadata_and_edit_clears():
    async def fn(db, patch, lst):
        f = await db.lex_lessons.find_one({"text": {"$regex": "^Divorce in England"}}, {"_id": 0})
        await patch(f["id"], LL.LessonPatch(status="approved", text=f["proposed_text"]), ADMIN)
        row = await db.lex_lessons.find_one({"id": f["id"]}, {"_id": 0})
        assert "43 days" in row["text"] and row["versions"][0]["text"] == f["original_text"]
        assert row["review_meta"]["checked_at"] == fact_review.CHECKED and LL.is_signed_off(row)
        await LL.refresh_lessons(db)
        assert "43 days" in LL.fact_pack_block("divorce") and "SIGNED OFF" in LL.fact_pack_block("divorce")
        await patch(f["id"], LL.LessonPatch(text=row["text"] + " Extra."), ADMIN)
        row = await db.lex_lessons.find_one({"id": f["id"]}, {"_id": 0})
        assert not LL.is_signed_off(row) and len(row["versions"]) == 2
        await LL.refresh_lessons(db)
        assert LL.fact_pack_block("divorce") == ""
        sign = await db.lex_lessons.find_one({"text": {"$regex": "^National Living Wage"}}, {"_id": 0})
        await patch(sign["id"], LL.LessonPatch(status="approved"), ADMIN)  # sign off as stored
        row = await db.lex_lessons.find_one({"id": sign["id"]}, {"_id": 0})
        assert row["text"] == sign["original_text"] and row["next_review_at"] == "2027-04-01" and "versions" not in row
    run_with_db(fn)


def test_withheld_topics_still_researched(monkeypatch):
    import legal_sources
    import official_guidance

    async def tav(q, include_domains=None, max_results=3, search_depth="basic"):
        return [{"title": "Divorce - GOV.UK", "url": "https://www.gov.uk/divorce",
                 "content": "You must wait 20 weeks after your divorce application is issued before applying"}], "ok"

    async def none(*a, **k):
        return []

    async def no_guidance(*a, **k):
        return [], []
    monkeypatch.setattr(rag, "_tavily_search_ex", tav)
    monkeypatch.setattr(rag, "is_enabled", lambda: True)
    monkeypatch.setattr(legal_sources, "grounding_sources", none)
    monkeypatch.setattr(official_guidance, "guidance_sources", no_guidance)
    r = asyncio.run(rag.research("How long does a divorce take in England? I want to apply for divorce."))
    assert r["status"] == "ok" and any(c["url"] == "https://www.gov.uk/divorce" for c in r["citations"])
