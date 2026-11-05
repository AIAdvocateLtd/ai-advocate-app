"""Stage 2 legal-knowledge review: adds needs_review flags to doubtful lex_lessons rows.
Never edits, approves, deletes or overwrites the legal text. Preview DB only.
Run: python scripts/flag_fact_review.py [--dry-run]"""
import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# (text fragment, priority, reason)
FLAGS = [
    ("National Living Wage: £12.71", "low", "Annual figure — re-check against GOV.UK before 1 April 2027."),
    ("Statutory Sick Pay (Great Britain) from 6 April 2026", "medium", "Rate and day-one rule are post-2025 changes; confirm £123.25 and commencement on GOV.UK rates page."),
    ("Statutory Maternity Pay 2026/27", "medium", "Annual rate (£194.32) — confirm on GOV.UK; re-check April 2027."),
    ("ACAS early conciliation (Great Britain)", "medium", "12-week conciliation period from 1 Dec 2025 — confirm commencement and how it interacts with the new 6-month limit."),
    ("Scotland uses the same employment law", "high", "Scotland breach-of-contract date (9 Nov 2026) is days away and appears in a pending AI-drafted item too; confirm the commencement order before relying on it."),
    ("England deposits: must be protected", "medium", "Claim that deposit rules 'also cover assured tenancies from 1 May 2026' needs confirming against Renters' Rights Act commencement regulations."),
    ("England (Renters' Rights Act 2025, from 1 May 2026)", "low", "Source is Shelter, not GOV.UK — add an official source; confirm Ground 8 weekly-rent threshold wording."),
    ("Universal Credit standard allowance 2026/27", "medium", "Annual figures — confirm against DWP benefit rates 2026-27; re-check April 2027."),
    ("Two-child limit: abolished from April 2026", "high", "Major policy change — confirm the abolition is in force (legislation and commencement) and its exact start date."),
    ("Benefit cap 2026/27 (frozen)", "medium", "Earnings exemption (£881/month) and cap figures — confirm on GOV.UK benefit cap page."),
    ("Skilled Worker, Scale-up and High Potential Individual visas: new applications from 8 January 2026 need English at B2", "medium", "Confirm the B2 requirement and transitional rule in the Immigration Rules statement."),
    ("Settlement (ILR) — CURRENT LAW", "high", "Earned-settlement reforms announced 2 Nov 2026 — check the Immigration Rules statement and transitional protection before Lex relies on it."),
    ("ILR timing and fee", "medium", "ILR fee (£3,226 from 8 April 2026) — confirm on the Home Office fees table."),
    ("British citizenship fee", "medium", "Naturalisation fee (£1,709) — confirm on the Home Office fees table."),
    ("Graduate visa: applications made on or before 31 December 2026", "medium", "18-month change from 1 Jan 2027 — confirm the Immigration Rules change has been laid."),
    ("Spouse/partner visa English", "low", "Earned-settlement reforms may change English levels — re-check after the next rules statement."),
]
PENDING_REASON = ("AI-drafted (law watch / report) and not yet verified by a person — check the cited official source before "
                  "approving. Not used in Lex answers while pending.")
HIGH_PENDING = ("Crime and Policing Act 2026", "Earned Settlement", "HC 584", "time limit for bringing most Employment Tribunal")


async def main(dry: bool):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc).isoformat()
    report = []
    async for r in db.lex_lessons.find({"status": {"$in": ["approved", "pending"]}}, {"_id": 0, "id": 1, "text": 1, "status": 1, "source": 1}):
        hit = next(((p, why) for frag, p, why in FLAGS if frag in r["text"]), None)
        if not hit and r["status"] == "pending":
            hit = ("high" if any(h in r["text"] for h in HIGH_PENDING) else "medium", PENDING_REASON)
        if not hit:
            continue
        report.append((r["id"], r["status"], r.get("source"), hit[0], hit[1], r["text"][:90]))
        if not dry:
            await db.lex_lessons.update_one({"id": r["id"]}, {"$set": {
                "needs_review": True, "review_priority": hit[0], "review_reason": hit[1],
                "review_flagged_at": now, "review_flagged_by": "stage2_audit"}})
    for row in report:
        print(" | ".join(str(x) for x in row))
    print(f"{'Would flag' if dry else 'Flagged'} {len(report)} item(s). No text, status or approval was changed.")


asyncio.run(main("--dry-run" in sys.argv))
