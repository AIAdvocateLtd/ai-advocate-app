"""Phase 2A-1 — confidence instructions + only signed-off facts reach Lex. Run with AIA_NO_PAID=1 (no paid calls)."""
import asyncio
import os

import pytest

import lex_lessons as LL
import rag
import server

PROMPT = server.lex_system_prompt("en", "GB", "employment", "england")


class FakeColl:
    def __init__(self, rows):
        self.rows = rows

    def find(self, q, proj=None):
        rows = [r for r in self.rows if all(r.get(k) == v for k, v in q.items())]

        class C:
            def sort(self, *a):
                return self

            async def to_list(self, n):
                return [dict(r) for r in rows]
        return C()


class FakeDB:
    def __init__(self, rows):
        self.lex_lessons = FakeColl(rows)


ROWS = [
    {"text": "FACT-A two-child limit abolished", "source": "fact_pack", "category": "benefits", "status": "approved",
     "approved_at": "x", "needs_review": True},
    {"text": "FACT-B NLW unflagged seed", "source": "fact_pack", "category": "employment", "status": "approved", "approved_at": "x"},
    {"text": "FACT-C signed off", "source": "fact_pack", "category": "employment", "status": "approved", "approved_at": "x",
     "reviewed_by": "founder@aiadvocate.co.uk", "reviewed_at": "2026-11-12"},
    {"text": "LESSON-D admin approved draft", "source": "law_watch", "category": "employment", "status": "approved",
     "approved_at": "x"},
    {"text": "LESSON-E flagged lesson", "source": "law_watch", "category": "employment", "status": "approved",
     "approved_at": "x", "needs_review": True},
    {"text": "LESSON-F pending draft", "source": "law_watch", "category": "employment", "status": "pending"},
    {"text": "LESSON-G unknown source", "source": "import", "category": "employment", "status": "approved", "approved_at": "x"},
]


@pytest.fixture
def lessons():
    saved = dict(LL._cache)
    asyncio.run(LL.refresh_lessons(FakeDB(ROWS)))
    yield
    LL._cache.clear()
    LL._cache.update(saved)


def test_paid_calls_blocked_in_this_run():
    assert os.environ.get("AIA_NO_PAID") == "1"
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    with pytest.raises(RuntimeError, match="AIA_NO_PAID"):
        asyncio.run(LlmChat(api_key="x", session_id="t", system_message="s").send_message(UserMessage(text="hi")))
    results, status = asyncio.run(rag._tavily_search_ex("test", include_domains=None, max_results=1, search_depth="basic"))
    assert results == [] and status != "ok"  # Tavily request was blocked before leaving the machine


def test_overconfidence_instructions_removed():
    for bad in ("perfect recall", "sharper than the top barristers", "could possibly", "ONLY acceptable hedge",
                "Vague hedge-words"):
        assert bad not in PROMPT


def test_direct_answers_and_uncertainty_both_allowed():
    assert "Be direct and confident where the law and the facts are clear and supported" in PROMPT
    assert "say exactly what is uncertain and what the answer depends on" in PROMPT
    assert "Never guarantee an outcome" in PROMPT and "Never invent legislation, cases" in PROMPT
    assert "Answer ordinary legal questions fully" in PROMPT and "Avoid stacked disclaimers" in PROMPT
    assert "REASONING DISCIPLINE" in PROMPT and "[CONFIDENCE: HIGH]" in PROMPT and "Disclaimer:" in PROMPT


def test_only_signed_off_facts_reach_lex(lessons):
    block = LL.fact_pack_block("I was dismissed by my employer and claim benefits")
    assert "FACT-C signed off" in block and "SIGNED OFF BY AI ADVOCATE'S REVIEWER" in block
    assert "FACT-A" not in block and "FACT-B" not in block and "VERIFIED UK FACTS" not in block
    lb = LL.lessons_block()
    assert "LESSON-D" in lb and "LESSON-E" not in lb and "LESSON-F" not in lb and "LESSON-G" not in lb
    assert LL._cache["withheld"] == 4  # A, B, E, G
    full = server.lex_system_prompt("en", "GB", "employment", "england")
    assert "FACT-A" not in full and "LESSON-E" not in full


def test_no_facts_when_none_signed_off():
    saved = dict(LL._cache)
    try:
        asyncio.run(LL.refresh_lessons(FakeDB([r for r in ROWS if r["text"].startswith(("FACT-A", "FACT-B"))])))
        assert LL.fact_pack_block("employer benefits") == "" and LL.lessons_block() == ""
    finally:
        LL._cache.clear()
        LL._cache.update(saved)


def test_signoff_rules():
    assert not LL.is_signed_off({"source": "fact_pack", "status": "approved", "approved_at": "x"})
    assert LL.is_signed_off({"source": "fact_pack", "status": "approved", "reviewed_by": "a", "reviewed_at": "b"})
    assert not LL.is_signed_off({"source": "fact_pack", "status": "approved", "reviewed_by": "a", "reviewed_at": "b",
                                 "needs_review": True})
    assert not LL.is_signed_off({"source": "manual", "status": "pending", "reviewed_by": "a", "reviewed_at": "b"})
    assert LL.is_signed_off({"source": "manual", "status": "approved", "approved_at": "x"})


def test_admin_signoff_and_edit_keep_review_record():
    from motor.motor_asyncio import AsyncIOMotorClient
    lid = "TEST_2a1_fact"

    async def go():
        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        await db.lex_lessons.insert_one({"id": lid, "text": "TEST fact", "source": "fact_pack", "category": "employment",
                                         "status": "approved", "approved_at": "x", "needs_review": True,
                                         "review_reason": "check rate"})
        try:
            def dep():
                return {}
            router, _ = LL.build_router(db, dep, dep, lambda s: s, lambda s: s, "x", lambda: "", None)
            patch = next(r.endpoint for r in router.routes
                         if r.path == "/admin/lex-lessons/{lesson_id}" and "PATCH" in r.methods)
            admin = {"id": "adm", "email": "founder@aiadvocate.co.uk"}
            await patch(lid, LL.LessonPatch(status="approved"), admin)
            row = await db.lex_lessons.find_one({"id": lid}, {"_id": 0})
            assert row["text"] == "TEST fact" and row["reviewed_by"] == "founder@aiadvocate.co.uk"
            assert row["needs_review"] is False and row["review_reason"] == "check rate"
            assert row["review_history"][0]["previous_flag"] == "check rate" and LL.is_signed_off(row)
            await patch(lid, LL.LessonPatch(text="TEST fact edited"), admin)
            row = await db.lex_lessons.find_one({"id": lid}, {"_id": 0})
            assert row["reviewed_by"] is None and not LL.is_signed_off(row)  # edited wording needs a fresh sign-off
        finally:
            await db.lex_lessons.delete_many({"id": lid})
            await LL.refresh_lessons(db)
    asyncio.run(go())


def test_official_research_still_used_and_labelled():
    src = open(rag.__file__).read()
    assert "fetched from Acas just now" in src
    assert "SIGNED OFF BY AI ADVOCATE'S REVIEWER are built-in knowledge, not retrieved text" in src
    assert "may add context but never override them" in src
