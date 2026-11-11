"""Production migration dry-run on a throwaway copy shaped like production (38 approved fact packs, 3 pending
law_watch drafts, no review flags). Simulated only — run with AIA_NO_PAID=1."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

import lex_lessons as LL

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from rollback_fact_review import rollback  # noqa: E402


async def _prod_like():
    name = f"test_mig_{uuid.uuid4().hex[:8]}"
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[name]
    now = datetime.now(timezone.utc).isoformat()
    for pack_id, (cat, items) in LL.PACKS.items():
        for text, url in (items or LL.IMMIGRATION_PACK_V1):
            await db.lex_lessons.insert_one({"id": str(uuid.uuid4()), "text": text, "category": cat, "status": "approved",
                                             "source": "fact_pack", "source_ref": pack_id, "approved_at": now})
        await db.seeds_applied.insert_one({"_id": pack_id, "at": now})
    for t in ("Crime and Policing Act 2026 offence", "Trade union notice duty", "Vaping duty"):
        await db.lex_lessons.insert_one({"id": str(uuid.uuid4()), "text": t, "category": "general", "status": "pending",
                                         "source": "law_watch", "source_ref": None})
    return db, name


def test_production_migration_dry_run_and_rollback():
    async def go():
        db, name = await _prod_like()
        try:
            before = {r["id"]: r for r in await db.lex_lessons.find({}, {"_id": 0}).to_list(100)}
            assert len(before) == 41
            await LL.seed_fact_packs(db)  # what production startup would run after deploy
            after = {r["id"]: r for r in await db.lex_lessons.find({}, {"_id": 0}).to_list(100)}
            assert set(before) <= set(after) and len(after) == 46  # nothing deleted; 5 notes added
            for i, b in before.items():
                a = after[i]
                assert a["text"] == b["text"] and a["status"] == b["status"] and a.get("approved_at") == b.get("approved_at")
                if b["source"] == "fact_pack":
                    assert a["original_text"] == b["text"] and a["review_meta"] and not a.get("reviewed_by")
                else:
                    assert a == b  # pending drafts untouched
            await LL.refresh_lessons(db)
            assert LL.fact_pack_block("employer landlord divorce benefits visa") == "" and LL.lessons_block() == ""
            await LL.seed_fact_packs(db)  # second startup: idempotent
            assert await db.lex_lessons.count_documents({}) == 46
            dry = await rollback(db, apply=False)
            assert dry == {"facts_unmarked": 38, "unsigned_law_notes_removed": 5, "signed_law_notes_kept": 0, "applied": False}
            assert await db.lex_lessons.count_documents({}) == 46
            await rollback(db, apply=True)
            restored = {r["id"]: r for r in await db.lex_lessons.find({}, {"_id": 0}).to_list(100)}
            assert set(restored) == set(before)
            for i, b in before.items():
                r = dict(restored[i])
                r.pop("original_text", None)
                assert r == b
        finally:
            await db.client.drop_database(name)
    asyncio.run(go())


def test_v3_refreshes_unsigned_notes_but_never_signed_ones():
    import fact_review

    async def go():
        db, name = await _prod_like()
        try:
            await db.lex_lessons.insert_many([
                {"id": "n0", "source": "law_note", "note_index": 0, "status": "pending", "text": "old tribunal wording"},
                {"id": "n1", "source": "law_note", "note_index": 1, "status": "approved", "text": "signed wording",
                 "reviewed_by": "founder@aiadvocate.co.uk", "reviewed_at": "2026-11-10"}])
            await LL.seed_fact_packs(db)
            n0 = await db.lex_lessons.find_one({"id": "n0"}, {"_id": 0})
            n1 = await db.lex_lessons.find_one({"id": "n1"}, {"_id": 0})
            assert n0["text"] == fact_review.LAW_NOTES[0][0] and n0["versions"][0]["text"] == "old tribunal wording"
            assert n0["status"] == "pending" and not n0.get("reviewed_by")
            assert "9 November 2026" in n0["text"] and "SI 2026/559" in fact_review.LAW_NOTES[1][0]
            assert n1["text"] == "signed wording" and "versions" not in n1
            assert await db.lex_lessons.count_documents({"source": "law_note"}) == 5
        finally:
            await db.client.drop_database(name)
    asyncio.run(go())
