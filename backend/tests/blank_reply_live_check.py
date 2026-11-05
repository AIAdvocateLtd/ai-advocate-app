"""Live check that Free/Plus/Pro/Deep Think Lex replies are complete (fictional, preview). Run: python tests/blank_reply_live_check.py"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import httpx  # noqa: E402
from stage2_live_check import API, make_user, login, chat, spend  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

COMPLEX = ("Fictional: my landlord in Leeds served a section 8 notice on 2 November 2026 for 2 months' arrears, never protected "
           "my £900 deposit, ignored black mould for a year, and told me he doesn't rent to people on Universal Credit. "
           "What are ALL my options, deadlines, and what should I do this week?")
CASES = [  # (user, label, message, language, stream, deep_think)
    ("free", "free_simple_stream", "Can my landlord enter my flat without telling me?", "en-GB", True, False),
    ("free", "free_complex_stream", COMPLEX, "en-GB", True, False),
    ("free", "free_complex_regular", COMPLEX, "en-GB", False, False),
    ("free", "free_welsh_stream", "Ffuglen: rhoddodd fy landlord yng Nghaerdydd hysbysiad adran 173 i mi ac nid yw wedi diogelu fy mlaendal. Beth yw fy opsiynau?", "cy-GB", True, False),
    ("free2", "free_urdu_stream", "فرضی: میرے مالک مکان نے مجھے بے دخلی کا نوٹس دیا اور میری جمع شدہ رقم محفوظ نہیں کی۔ میرے اختیارات کیا ہیں؟", "ur-PK", True, False),
    ("plus", "plus_complex_stream", COMPLEX, "en-GB", True, False),
    ("plus", "plus_regular", "Fictional: my employer hasn't paid my last month's wages. What can I do?", "en-GB", False, False),
    ("pro", "pro_simple_stream", "Can my landlord enter my flat without telling me?", "en-GB", True, False),
    ("pro", "pro_complex_stream", COMPLEX, "en-GB", True, False),
    ("pro", "pro_complex_regular", COMPLEX, "en-GB", False, False),
    ("pro", "deep_think_stream", COMPLEX, "en-GB", True, True),
]


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    since = datetime.now(timezone.utc).isoformat()
    ids = {"free": await make_user(db, "blank.free@stage2-fictional-test.co.uk", {}),
           "free2": await make_user(db, "blank.free2@stage2-fictional-test.co.uk", {}),
           "plus": await make_user(db, "blank.plus@stage2-fictional-test.co.uk", {"tier": "plus", "subscription_status": "active"}),
           "pro": await make_user(db, "blank.pro@stage2-fictional-test.co.uk", {"comp_pro_until": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()})}
    out = []
    async with httpx.AsyncClient() as c:
        hs = {k: await login(c, f"blank.{k}@stage2-fictional-test.co.uk") for k in ids}
        for who, label, msg, lang, stream, dt in CASES:
            try:
                if stream:
                    body = {"message": msg, "language": lang, "country": "GB", "deep_think": dt}
                    r = await chat(c, hs[who], msg, stream=True) if not dt and lang == "en-GB" else None
                    if r is None:
                        events, done = [], {}
                        async with c.stream("POST", f"{API}/lex/chat/stream", json=body, headers=hs[who], timeout=240) as s:
                            async for line in s.aiter_lines():
                                if line.startswith("data: "):
                                    e = json.loads(line[6:])
                                    events.append(e["type"])
                                    if e["type"] in ("done", "error"):
                                        done = e if e["type"] == "error" or not done else done
                                    if e["type"] == "done" and e.get("full_text") is not None:
                                        done = e
                        text = done.get("full_text") or ""
                    else:
                        text = r["response"]
                else:
                    r = await chat(c, hs[who], msg)
                    text = r["response"]
                cut = 'Reply "continue"' in text or "continue" in text[-120:].lower()
                out.append({"case": label, "chars": len(text), "blank": not text.strip(), "cut_note": cut,
                            "ending_markers": "[CONFIDENCE" in text, "pass": bool(text.strip()) and len(text) > 150})
            except Exception as e:
                out.append({"case": label, "error": repr(e)[:200], "pass": False})
            print(json.dumps(out[-1], ensure_ascii=False))
    await asyncio.sleep(1)
    cost, rows = await spend(db, list(ids.values()), since)
    lex = [r for r in rows if r.get("model_requested") in ("claude-haiku-5-5", "claude-sonnet-5-5", "gpt-5.2", "claude-sonnet-4-5-20250929")]
    summary = {"cost_gbp": cost, "lex_rows": [{k: r.get(k) for k in ("model_requested", "call_site", "attempt", "finish_reason",
                                                                      "reasoning_tokens", "tokens_out", "output_chars", "cost_gbp")} for r in lex],
               "passed": sum(o["pass"] for o in out), "total": len(out), "results": out}
    json.dump(summary, open("/app/test_reports/blank_reply_live_results.json", "w"), indent=1, ensure_ascii=False)
    for r in summary["lex_rows"]:
        print(r)
    print("PASSED", summary["passed"], "/", summary["total"], "cost £", cost)
    await db.users.delete_many({"id": {"$in": list(ids.values())}})
    for coll in ("conversations", "reminders", "usage"):
        await getattr(db, coll).delete_many({"user_id": {"$in": list(ids.values())}})


asyncio.run(main())
