"""Insert / delete the ONE synthetic TEST-PROPOSAL-1 doc in the preview DB. Usage: python synthetic_proposal.py insert|delete|show"""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
PID = "TEST-PROPOSAL-1"
DOC = {"_id": PID, "status": "awaiting_review", "key": "ukpga/1996/18/section/94",
       "url": "https://www.legislation.gov.uk/ukpga/1996/18/section/94", "title": "Employment Rights Act 1996",
       "provision": "section 94", "jurisdiction": "England and Wales", "change_types": ["wording_amended"],
       "interpretation": "not assessed", "linked_rules": [], "linked_lessons": [], "affecting_instruments": [],
       "detected_at": "2026-01-01T00:00:00+00:00", "decision": None}


async def main(cmd):
    if cmd == "insert":
        await db.law_update_proposals.insert_one(DOC)
    elif cmd == "delete":
        a = await db.law_update_proposals.delete_one({"_id": PID})
        b = await db.law_watch_audit.delete_many({"proposal": PID})
        print("deleted proposal", a.deleted_count, "audit", b.deleted_count)
    print("proposal:", await db.law_update_proposals.find_one({"_id": PID}))
    print("audit:", await db.law_watch_audit.find({"proposal": PID}).to_list(10))
    print("records w/ key:", await db.law_watch_records.count_documents({"key": DOC["key"]}),
          "settings:", await db.law_watch_settings.find_one({"_id": "writes"}))

asyncio.run(main(sys.argv[1]))
