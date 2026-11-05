"""Lex learning loop: feedback -> AI-drafted lessons -> founder approval -> injected into every Lex prompt."""
import asyncio
import difflib
import json
import time
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
LESSON_MODEL = ("anthropic", "claude-sonnet-5-5")
from lex_output import gen_params  # noqa: E402
MAX_LESSONS_IN_PROMPT = 80
_cache = {"block": "", "packs": {}, "at": 0.0}
_job_lock = asyncio.Lock()
REPORTS_PER_USER_PER_DAY = 10


def lessons_block() -> str:
    return _cache["block"]


async def refresh_if_stale(db, max_age: int = 300) -> None:
    if time.time() - _cache["at"] > max_age:
        await refresh_lessons(db)


async def refresh_lessons(db) -> None:
    _cache["at"] = time.time()
    rows = await db.lex_lessons.find({"status": "approved"}, {"_id": 0, "text": 1, "source": 1, "category": 1}) \
        .sort("approved_at", -1).to_list(300)
    packs: dict = {}
    for r in rows:
        if r.get("source") == "fact_pack":
            packs.setdefault(r.get("category") or "general", []).append(r["text"])
    _cache["packs"] = packs
    rows = [r for r in rows if r.get("source") != "fact_pack"][:MAX_LESSONS_IN_PROMPT]
    if not rows:
        _cache["block"] = ""
        return
    lines = "\n".join(f"- {r['text']}" for r in rows)
    _cache["block"] = ("CONFIRMED LESSONS (checked by AI Advocate's review team — always follow these, "
                       "they override your training knowledge):\n" + lines + "\n\n")


TOPIC_RE = {
    "immigration": re.compile(r"\b(visas?|ilr|indefinite leave|settle(d|ment)|citizen\w*|naturalis\w*|home office|asylum|"
                              r"refugees?|overstay\w*|immigra\w*|passports?|brp|evisa|sponsor\w*|graduate route)\b", re.I),
    "employment": re.compile(r"\b(employ\w*|jobs?|dismiss\w*|sacked|fired|redundan\w*|tribunal|acas|lra|wages?|salary|"
                             r"sick pay|ssp|maternity|paternity|holiday pay|annual leave|notice period|boss|manager|workplace|"
                             r"discriminat\w*|minimum wage|living wage)\b", re.I),
    "housing": re.compile(r"\b(landlords?|tenan\w*|rent(s|ed|ing|al)?|evict\w*|deposits?|lease|section (8|21|173)|"
                          r"notice to (quit|leave)|housing|mould|damp|repairs?|letting agent|occupation contract)\b", re.I),
    "family": re.compile(r"\b(divorc\w*|separat\w*|marri\w*|civil partner\w*|custody|child arrangements?|"
                         r"child maintenance|cms|mediation|miam|family court|financial order|ex-?(wife|husband|partner))\b", re.I),
    "benefits": re.compile(r"\b(benefits?|universal credit|uc|pip|esa|dwp|jobseeker\w*|pension credit|child benefit|"
                           r"carer'?s allowance|disability payment|adp|reconsideration|sanction\w*|benefit cap|two.child)\b", re.I),
}


def fact_pack_block(message: str, context: str = "") -> str:
    text = f"{message}\n{context}"
    picked = [cat for cat, rx in TOPIC_RE.items() if rx.search(text)]
    lines = [t for cat in picked for t in _cache.get("packs", {}).get(cat, [])]
    if not lines:
        return ""
    return ("\n\nVERIFIED UK FACTS (current as of the date above — use these exactly; if the user's UK nation is unclear "
            "and the rules differ, ask or give each nation's rule):\n- " + "\n- ".join(lines) + "\n")


class FeedbackIn(BaseModel):
    session_id: Optional[str] = None
    rating: str  # up | down | wrong
    note: Optional[str] = ""
    question: Optional[str] = ""
    answer: Optional[str] = ""


class LessonIn(BaseModel):
    text: str
    category: Optional[str] = "general"


class LessonPatch(BaseModel):
    status: Optional[str] = None
    text: Optional[str] = None


def _parse_json_list(raw: str) -> list:
    m = re.search(r"\[.*\]", raw or "", re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return [d for d in data if isinstance(d, dict) and (d.get("lesson") or "").strip()]
    except Exception:
        return []


async def _llm(api_key: str, system: str, prompt: str) -> str:
    _gen = gen_params(LESSON_MODEL[1], 1500)
    chat = LlmChat(api_key=api_key, session_id=f"lessons-{uuid.uuid4()}", system_message=system) \
        .with_model(*LESSON_MODEL).with_params(max_tokens=_gen[0], **_gen[1])
    return await chat.send_message(UserMessage(text=prompt))


DRAFT_SYSTEM = (
    "You maintain a list of short, general, verified UK legal rules that an AI legal assistant called Lex must always follow. "
    "Write each lesson as one or two plain sentences stating the correct general rule (no personal details, no names). "
    "Only propose a lesson if you are confident it is accurate UK law as of today. If nothing general and certain can be "
    "learned, return []. Reply ONLY with a JSON list like "
    '[{"lesson": "...", "category": "immigration|employment|housing|family|consumer|debt|wills|criminal|general", "why": "..."}]'
)


async def _insert_drafts(db, drafts: list, source: str, source_ref: Optional[str] = None) -> int:
    n = 0
    existing = [r["text"].lower() for r in await db.lex_lessons.find(
        {"status": {"$in": ["approved", "pending"]}}, {"_id": 0, "text": 1}).to_list(500)]
    for d in drafts[:5]:
        text = d["lesson"].strip()[:600]
        if any(difflib.SequenceMatcher(None, text.lower(), e).ratio() > 0.7 for e in existing):
            continue
        existing.append(text.lower())
        await db.lex_lessons.insert_one({
            "id": str(uuid.uuid4()), "text": text, "category": (d.get("category") or "general")[:40],
            "why": (d.get("why") or "")[:600], "status": "pending", "source": source, "source_ref": source_ref,
            "created_at": datetime.now(timezone.utc).isoformat(), "approved_at": None,
        })
        n += 1
    return n


async def _existing_lessons_text(db) -> str:
    rows = await db.lex_lessons.find({"status": {"$in": ["approved", "pending"]}}, {"_id": 0, "text": 1}).to_list(200)
    return "\n".join(f"- {r['text']}" for r in rows) or "(none)"


IMMIGRATION_PACK_V1 = [
    ("Spouse/partner visa financial requirement: new applications need at least £29,000 a year gross (usually combined income "
     "of the couple; same figure with or without children). Couples first granted under the old rules before 11 April 2024 keep "
     "the £18,600 rules when extending on that route. If the British/settled partner receives certain disability or carer's "
     "benefits, the income threshold does not apply (adequate maintenance instead).", "https://www.gov.uk/uk-family-visa/proof-income-partner"),
    ("Spouse/partner visa English: currently A1 for the first visa, A2 for the extension, and B1 plus the Life in the UK test for "
     "settlement — earned-settlement reforms may raise these, so tell users to check GOV.UK before applying.", "https://www.gov.uk/uk-family-visa/knowledge-of-english"),
    ("Skilled Worker visa (sponsorship certificates from 22 July 2025): salary must be at least £41,700 a year or the job's going "
     "rate, whichever is higher. Lower options: £33,400 for new entrants, Immigration Salary List jobs and STEM PhDs; £37,500 for "
     "relevant non-STEM PhDs. Many health and education roles have a £25,000 floor (full going rate still required).", "https://www.gov.uk/skilled-worker-visa/your-job"),
    ("Skilled Worker, Scale-up and High Potential Individual visas: new applications from 8 January 2026 need English at B2. "
     "People extending a Skilled Worker visa first granted under the B1 requirement stay at B1.", "https://www.gov.uk/government/publications/english-language-requirement-levels-for-immigration-applications"),
    ("Settlement (ILR) — CURRENT LAW: most routes (e.g. Skilled Worker, spouse/partner) still lead to ILR after 5 years; long "
     "residence is 10 years. On 2 November 2026 the Home Secretary announced 'earned settlement' making 10 years the standard "
     "(5 years for some higher earners and public-service workers), with rule changes from December 2026 phased in during 2027. "
     "It is not law until the Immigration Rules take effect — never tell users the 10-year rule already applies to them; flag "
     "possible transitional protection and suggest a regulated adviser.", "https://www.gov.uk/government/news/home-secretary-unveils-new-rules-for-migrants-settling-in-the-uk"),
    ("ILR timing and fee: apply no earlier than 28 days before completing the qualifying period (earlier applications can be "
     "refused). ILR fee is £3,226 per person from 8 April 2026; ILR applicants do not pay the Immigration Health Surcharge.", "https://www.gov.uk/government/publications/visa-regulations-revised-table"),
    ("British citizenship absences (naturalisation): no more than 450 days outside the UK in the 5-year period and no more than "
     "90 days in the final 12 months. Spouse/civil partner route: 3 years, max 270 days absent, max 90 in the last 12 months. "
     "Small excesses can be disregarded at Home Office discretion. Applicants also need the Life in the UK test and English at "
     "B1 (unless exempt).", "https://www.gov.uk/government/publications/form-an-guidance/form-an-guidance-accessible"),
    ("British citizenship fee: adult naturalisation costs £1,709 plus a £130 citizenship ceremony fee (£1,839 total). Child "
     "registration is £1,000. The application fee is not refunded if refused.", "https://www.gov.uk/government/publications/fees-for-citizenship-applications"),
    ("Immigration Health Surcharge: £1,035 per year for most applicants; £776 per year for students, their dependants, Youth "
     "Mobility Scheme applicants and under-18s.", "https://www.gov.uk/healthcare-immigration-application/how-much-pay"),
    ("Visa expiry and overstaying: if someone applies to extend or switch BEFORE their permission expires, their existing "
     "permission and conditions continue while it is decided and any appeal is pending (section 3C Immigration Act 1971). There is "
     "NO general grace period — from the day after expiry they are an overstayer. A late application made within 14 days may only "
     "be accepted if there was a good reason beyond their control. Overstaying can lead to future refusals and re-entry bans, so "
     "recommend urgent regulated advice.", "https://www.gov.uk/government/publications/applications-from-overstayers-non-family-routes"),
    ("Switching visas inside the UK: visitors cannot switch to Skilled Worker, Student or most other routes from inside the UK — "
     "they must leave and apply from abroad (very limited family exceptions). Many other visa holders can switch in-country if "
     "they meet the new route's rules; always check the specific route's 'switch to this visa' page on GOV.UK.", "https://www.gov.uk/skilled-worker-visa/switch-to-this-visa"),
    ("Graduate visa: applications made on or before 31 December 2026 get 2 years; applications made on or after 1 January 2027 "
     "get 18 months. The application date, not the decision date, decides which applies.", "https://www.gov.uk/graduate-visa"),
    ("Proof of status: the UK has replaced most physical documents (BRPs) with eVisas — people prove their status online via "
     "their UKVI account and share codes; advise users to keep their UKVI account details up to date.", "https://www.gov.uk/evisa"),
]


from fact_packs import EMPLOYMENT_PACK_V1, HOUSING_PACK_V1, FAMILY_PACK_V1, BENEFITS_PACK_V1  # noqa: E402

PACKS = {"immigration_pack_v1": ("immigration", None), "employment_pack_v1": ("employment", EMPLOYMENT_PACK_V1),
         "housing_pack_v1": ("housing", HOUSING_PACK_V1), "family_pack_v1": ("family", FAMILY_PACK_V1),
         "benefits_pack_v1": ("benefits", BENEFITS_PACK_V1)}


async def seed_fact_packs(db) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for pack_id, (category, items) in PACKS.items():
        if await db.seeds_applied.find_one({"_id": pack_id}):
            continue
        for text, url in (items or IMMIGRATION_PACK_V1):
            await db.lex_lessons.insert_one({
                "id": str(uuid.uuid4()), "text": text, "category": category, "why": f"Fact pack · {url}",
                "status": "approved", "source": "fact_pack", "source_ref": pack_id,
                "created_at": now, "approved_at": now,
            })
        await db.seeds_applied.insert_one({"_id": pack_id, "at": now})


def build_router(db, get_user, require_admin, encrypt_text, decrypt_text, api_key, today_line, tavily_search):
    router = APIRouter()

    async def draft_from_report(fb_id: str):
        fb = await db.lex_feedback.find_one({"id": fb_id})
        if not fb:
            return
        try:
            prompt = (f"{today_line()}A user reported that this Lex answer was wrong.\n\nQUESTION:\n{decrypt_text(fb.get('question'))}\n\n"
                      f"LEX ANSWER:\n{decrypt_text(fb.get('answer'))}\n\nUSER'S NOTE:\n{fb.get('note') or '(none)'}\n\n"
                      f"EXISTING LESSONS (do not duplicate):\n{await _existing_lessons_text(db)}\n\n"
                      "If the answer contains a real legal error, write the general rule Lex should have followed.")
            drafts = _parse_json_list(await _llm(api_key, DRAFT_SYSTEM, prompt))
            await _insert_drafts(db, drafts, "report", fb_id)
        except Exception as e:
            logger.warning(f"lesson draft from report failed: {e!r}")
        await db.lex_feedback.update_one({"id": fb_id}, {"$set": {"processed": True}})

    async def weekly_job():
        if _job_lock.locked():
            return
        async with _job_lock:
            await _weekly_job_inner()

    async def _weekly_job_inner():
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            downs = await db.lex_feedback.find(
                {"rating": "down", "processed": {"$ne": True}, "created_at": {"$gte": since}}, {"_id": 0}).to_list(25)
            if downs:
                pairs = "\n\n".join(
                    f"#{k+1} Q: {decrypt_text(d.get('question'))[:800]}\nA: {decrypt_text(d.get('answer'))[:1500]}"
                    for k, d in enumerate(downs))
                prompt = (f"{today_line()}Users gave these Lex answers a thumbs-down. Look for real legal errors or outdated rules.\n\n"
                          f"{pairs}\n\nEXISTING LESSONS (do not duplicate):\n{await _existing_lessons_text(db)}")
                await _insert_drafts(db, _parse_json_list(await _llm(api_key, DRAFT_SYSTEM, prompt)), "thumbs_down")
                await db.lex_feedback.update_many({"id": {"$in": [d["id"] for d in downs]}}, {"$set": {"processed": True}})

            month = datetime.now(timezone.utc).strftime("%B %Y")
            queries = [f"new UK law comes into force {month}", f"UK legislation changes {month} employment housing immigration",
                       f"GOV.UK guidance change {month} consumer benefits family law"]
            results = []
            for q in queries:
                results += await tavily_search(q, include_domains=["gov.uk", "legislation.gov.uk", "lawgazette.co.uk"],
                                               max_results=4)
            if results:
                news = "\n\n".join(f"{r['title']} ({r['url']})\n{r['content'][:700]}" for r in results)
                prompt = (f"{today_line()}Recent UK legal news from official sources:\n\n{news}\n\n"
                          f"EXISTING LESSONS (do not duplicate):\n{await _existing_lessons_text(db)}\n\n"
                          "Propose lessons ONLY for confirmed changes to UK law or official rules that the public would ask about. "
                          "Include the date the change applies from. In 'why', include the source URL.")
                await _insert_drafts(db, _parse_json_list(await _llm(api_key, DRAFT_SYSTEM, prompt)), "law_watch")
        except Exception as e:
            logger.exception(f"weekly lex learning job failed: {e!r}")

    @router.post("/lex/feedback")
    async def lex_feedback(data: FeedbackIn, user: dict = Depends(get_user)):
        if data.rating not in ("up", "down", "wrong"):
            raise HTTPException(400, "Invalid rating")
        if data.rating == "wrong":
            since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            if await db.lex_feedback.count_documents(
                    {"user_id": user["id"], "rating": "wrong", "created_at": {"$gte": since}}) >= REPORTS_PER_USER_PER_DAY:
                raise HTTPException(429, "Thanks — you've sent a lot of reports today. Please try again tomorrow.")
        fb_id = str(uuid.uuid4())
        await db.lex_feedback.insert_one({
            "id": fb_id, "user_id": user["id"], "session_id": data.session_id, "rating": data.rating,
            "note": (data.note or "")[:1000],
            "question": encrypt_text((data.question or "")[:4000]), "answer": encrypt_text((data.answer or "")[:8000]),
            "processed": data.rating == "up", "created_at": datetime.now(timezone.utc).isoformat(),
        })
        if data.rating == "wrong":
            asyncio.create_task(draft_from_report(fb_id))
        return {"ok": True}

    @router.get("/admin/lex-lessons")
    async def list_lessons(admin: dict = Depends(require_admin)):
        rows = await db.lex_lessons.find({"status": {"$ne": "rejected"}}, {"_id": 0}).sort("created_at", -1).to_list(300)
        rows.sort(key=lambda r: r["status"] != "pending")
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        stats = {k: await db.lex_feedback.count_documents({"rating": k, "created_at": {"$gte": since}})
                 for k in ("up", "down", "wrong")}
        return {"lessons": rows, "stats_30d": stats}

    @router.post("/admin/lex-lessons")
    async def add_lesson(data: LessonIn, admin: dict = Depends(require_admin)):
        text = data.text.strip()[:600]
        if len(text) < 10:
            raise HTTPException(400, "Lesson is too short")
        now = datetime.now(timezone.utc).isoformat()
        await db.lex_lessons.insert_one({"id": str(uuid.uuid4()), "text": text, "category": data.category or "general",
                                         "why": "Added manually", "status": "approved", "source": "manual",
                                         "created_at": now, "approved_at": now})
        await refresh_lessons(db)
        return {"ok": True}

    @router.patch("/admin/lex-lessons/{lesson_id}")
    async def update_lesson(lesson_id: str, data: LessonPatch, admin: dict = Depends(require_admin)):
        upd = {}
        if data.text is not None:
            upd["text"] = data.text.strip()[:600]
        if data.status is not None:
            if data.status not in ("approved", "rejected", "pending"):
                raise HTTPException(400, "Invalid status")
            upd["status"] = data.status
            upd["approved_at"] = datetime.now(timezone.utc).isoformat() if data.status == "approved" else None
        r = await db.lex_lessons.update_one({"id": lesson_id}, {"$set": upd})
        if not r.matched_count:
            raise HTTPException(404, "Lesson not found")
        await refresh_lessons(db)
        return {"ok": True}

    @router.delete("/admin/lex-lessons/{lesson_id}")
    async def delete_lesson(lesson_id: str, admin: dict = Depends(require_admin)):
        await db.lex_lessons.delete_one({"id": lesson_id})
        await refresh_lessons(db)
        return {"ok": True}

    @router.post("/admin/lex-lessons/run-now")
    async def run_now(admin: dict = Depends(require_admin)):
        asyncio.create_task(weekly_job())
        return {"ok": True, "queued": True}

    return router, weekly_job
