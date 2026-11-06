"""Live validation of Free-tier concise answers + legal text fixes via the real endpoints (fictional). python tests/free_tier_live_validation.py"""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import httpx  # noqa: E402
from stage2_live_check import API, make_user, login, spend  # noqa: E402
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

COMPLEX = ("Fictional: my landlord in Leeds served a section 8 notice on 2 November 2026 for 2 months' arrears, never protected "
           "my £900 deposit, ignored black mould for a year, and told me he doesn't rent to people on Universal Credit. "
           "What are ALL my options, deadlines, and what should I do this week?")
FREE_ALL = [("en_complex", "en-GB", COMPLEX),
        ("en_dismissal", "en-GB", "Fictional: I was dismissed on 2 November 2026 after 3 years with no warning or meeting. Can I claim and what should I do?"),
        ("cy", "cy-GB", "Ffuglen: rhoddodd fy landlord yng Nghaerdydd hysbysiad adran 173 i mi, nid yw wedi diogelu fy mlaendal, ac mae llwydni du ym mhob ystafell. Beth yw fy holl opsiynau a therfynau amser?"),
        ("ur", "ur-PK", "فرضی: میرے مالک مکان نے مجھے بے دخلی کا نوٹس دیا، میری جمع شدہ رقم محفوظ نہیں کی، اور گھر میں سیاہ پھپھوندی ہے۔ میرے تمام اختیارات اور آخری تاریخیں کیا ہیں؟"),
        ("ar", "ar-SA", "افتراضي: أعطاني المالك إشعار إخلاء، ولم يحمِ وديعتي، وهناك عفن أسود في كل غرفة. ما هي كل خياراتي والمواعيد النهائية؟"),
        ("pl", "pl-PL", "Fikcyjnie: właściciel w Leeds dał mi wypowiedzenie z sekcji 8, nie zabezpieczył kaucji i ignoruje czarną pleśń. Jakie mam wszystkie opcje i terminy?"),
        ("zh", "zh-CN", "虚构：我在利兹的房东给了我第8条通知，没有保护我的押金，还无视黑霉问题。我有哪些选择和期限？"),
        ("hi", "hi-IN", "काल्पनिक: लीड्स में मेरे मकान मालिक ने सेक्शन 8 नोटिस दिया, मेरी जमा राशि सुरक्षित नहीं की, और काली फफूंद को नज़रअंदाज़ किया। मेरे सभी विकल्प और समय-सीमाएँ क्या हैं?"),
        ("en_wages", "en-GB", "Fictional: my employer in Manchester deducted £300 from my wages without asking. What law protects me and what can I do?"),
        ("en_et_transitional", "en-GB", "Fictional: I was unfairly dismissed in England on 1 August 2026 after 4 years. Am I out of time to claim?")]
FREE = [q for q in FREE_ALL if q[0] in ("en_complex", "en_dismissal", "cy", "ur", "hi")] + [
    ("cy2", "cy-GB", "Ffuglen: cefais fy niswyddo yng Nghasnewydd ar 2 Tachwedd 2026 ar ôl 3 blynedd heb rybudd. Beth ddylwn i ei wneud a beth yw'r terfyn amser?"),
    ("ur2", "ur-PK", "فرضی: مجھے 2 نومبر 2026 کو لندن میں بغیر کسی وارننگ کے نوکری سے نکال دیا گیا۔ میں 3 سال سے کام کر رہا تھا۔ میں کیا کر سکتا ہوں اور آخری تاریخ کیا ہے؟"),
    ("hi2", "hi-IN", "काल्पनिक: मेरा वीज़ा 20 दिसंबर 2026 को समाप्त हो रहा है और मेरे नियोक्ता ने मुझे नौकरी से निकाल दिया। मेरे विकल्प क्या हैं?")]
CUT_WORDS = ("continue", "continuar", "continuer", "kontynuuj", "جاری رکھیں", "تابع", "继续", "जारी रखें", "parhau")


async def stream(c, h, msg, lang):
    done = {}
    async with c.stream("POST", f"{API}/lex/chat/stream", json={"message": msg, "language": lang, "country": "GB"}, headers=h, timeout=240) as r:
        async for line in r.aiter_lines():
            if line.startswith("data: "):
                e = json.loads(line[6:])
                if e["type"] == "error":
                    return {"error": e.get("message")}
                if e["type"] == "done" and e.get("full_text") is not None:
                    done = e
    return {"text": done.get("full_text", "")}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    since = datetime.now(timezone.utc).isoformat()
    ids = [await make_user(db, f"concise.free{i}@stage2-fictional-test.co.uk", {}) for i in range(3)]
    out = []
    async with httpx.AsyncClient() as c:
        hs = [await login(c, f"concise.free{i}@stage2-fictional-test.co.uk") for i in range(3)]
        for k, (name, lang, msg) in enumerate(FREE):
            r = await stream(c, hs[k // 3], msg, lang)
            t = r.get("text", "")
            row = {"q": name, "chars": len(t), "blank": not t.strip(), "has_end_markers": "[CONFIDENCE" in t,
                   "cut_note": any(w in t[-160:] for w in CUT_WORDS) and "[CONFIDENCE" not in t, "error": r.get("error"), "text": t}
            if name == "en_wages":
                row["cites_wages_act_1986_as_current"] = bool(re.search(r"Wages Act 1986", t)) and "repeal" not in t.lower()
                row["mentions_era_1996"] = "Employment Rights Act 1996" in t
            if name == "en_et_transitional":
                row["says_definitely_out_of_time"] = bool(re.search(r"you are (definitely |now )?out of time|too late to claim", t, re.I))
                row["mentions_transitional_or_advice"] = bool(re.search(r"transitional|ACAS|advice", t, re.I))
            out.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "text"}, ensure_ascii=False))
    await asyncio.sleep(1)
    cost, rows = await spend(db, ids, since)
    lex = [r for r in rows if r.get("call_site") == "lex_stream"]
    summary = {"cost_gbp": cost, "complete": sum(o["has_end_markers"] for o in out), "total": len(out),
               "finish": [r.get("finish_reason") for r in lex], "tokens_out": [r.get("tokens_out") for r in lex], "results": out}
    json.dump(summary, open("/app/test_reports/free_tier_live_validation.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}))
    await db.users.delete_many({"id": {"$in": ids}})
    for coll in ("conversations", "reminders", "usage"):
        await getattr(db, coll).delete_many({"user_id": {"$in": ids}})


asyncio.run(main())
