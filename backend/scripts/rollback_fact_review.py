"""Undo the Phase 2A-1 fact review records. Dry-run by default; pass --apply to change data.
Removes only what seed_review_records added (review fields on facts, the 5 law-note items that were never signed off,
and the seed marker). Fact ids, wording, status and any sign-offs a person made are left alone."""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


async def rollback(db, apply: bool) -> dict:
    facts = await db.lex_lessons.count_documents({"source": "fact_pack", "review_meta": {"$exists": True}})
    notes_q = {"source": "law_note", "reviewed_by": {"$in": [None]}}
    notes = await db.lex_lessons.count_documents(notes_q)
    signed_notes = await db.lex_lessons.count_documents({"source": "law_note", "reviewed_by": {"$nin": [None]}})
    if apply:
        await db.lex_lessons.update_many({"source": "fact_pack"}, {"$unset": {"review_meta": "", "proposed_text": ""}})
        await db.lex_lessons.delete_many(notes_q)
        await db.seeds_applied.delete_one({"_id": "fact_review_v2"})
    return {"facts_unmarked": facts, "unsigned_law_notes_removed": notes, "signed_law_notes_kept": signed_notes,
            "applied": apply}


if __name__ == "__main__":
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    print(asyncio.run(rollback(client[os.environ["DB_NAME"]], "--apply" in sys.argv)))
