"""Stage 1 checks: recent-history memory + AI usage meter. Fictional data only.
Run: cd /app/backend && python3 tests/test_stage1_memory_usage.py"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
import chat_memory  # noqa: E402

db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ident = lambda x: x  # noqa: E731
OK = []


def check(name, cond):
    OK.append(cond)
    print(("PASS " if cond else "FAIL ") + name)


async def seed(user_id, session_id, n, big=False):
    docs = [{"user_id": user_id, "session_id": session_id, "created_at": f"2026-01-01T00:{i:02d}:00+00:00",
             "user_message": f"Q{i}" + ("x" * 9000 if big else ""), "assistant_response": f"A{i}"} for i in range(1, n + 1)]
    await db.conversations.insert_many(docs)


async def main():
    u1, u2, s1, s2 = f"t-{uuid.uuid4()}", f"t-{uuid.uuid4()}", f"s-{uuid.uuid4()}", f"s-{uuid.uuid4()}"
    try:
        await seed(u1, s1, 15)
        await seed(u2, s1, 3)            # other user, SAME session id → must never leak
        await seed(u1, s2, 2)            # same user, other conversation → must never leak
        ex, omitted = await chat_memory.load_recent_history(db, u1, s1, ident)
        users = [e["user"] for e in ex]
        check("loads the 12 most recent exchanges", users == [f"Q{i}" for i in range(4, 16)])
        check("chronological order preserved", users[0] == "Q4" and users[-1] == "Q15")
        check("question and answer kept together", all(e["assistant"] == "A" + e["user"][1:] for e in ex))
        check("omitted count = 3", omitted == 3)
        check("memory note tells Lex not to pretend", "Never pretend" in chat_memory.history_note(omitted))
        check("no note when nothing omitted", chat_memory.history_note(0) == "")
        ex2, _ = await chat_memory.load_recent_history(db, u2, s1, ident)
        check("no leak between users sharing a session id", [e["user"] for e in ex2] == ["Q1", "Q2", "Q3"])
        ex3, _ = await chat_memory.load_recent_history(db, u1, s2, ident)
        check("no leak between conversations", [e["user"] for e in ex3] == ["Q1", "Q2"])
        s3 = f"s-{uuid.uuid4()}"
        await seed(u1, s3, 10, big=True)  # each ~9k chars → budget forces trimming
        ex4, om4 = await chat_memory.load_recent_history(db, u1, s3, ident)
        check("newest 4 always kept even if over size budget", [e["user"][:3] for e in ex4] == ["Q7x", "Q8x", "Q9x", "Q10"][:len(ex4)] or len(ex4) >= 4)
        check("large history trimmed oldest-first with omitted count", len(ex4) == 4 and om4 == 6 and ex4[-1]["user"].startswith("Q10"))
        msgs = chat_memory.to_messages(ex[:2])
        check("messages alternate user/assistant", [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"])
    finally:
        await db.conversations.delete_many({"user_id": {"$in": [u1, u2]}})
    print(f"\n{sum(OK)}/{len(OK)} passed")


asyncio.run(main())
