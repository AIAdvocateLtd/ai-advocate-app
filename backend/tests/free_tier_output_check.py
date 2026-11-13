"""Priority bug check: can Free-tier (Claude Haiku 5.5, max_tokens=1200) Lex replies come back empty or cut off?
Read-only — fictional prompts, no DB writes except usage meter. Run: python tests/free_tier_output_check.py"""
import asyncio
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
import litellm  # noqa: E402
from emergentintegrations.llm.utils import get_integration_proxy_url  # noqa: E402
import server  # noqa: E402

KEY = os.environ["EMERGENT_LLM_KEY"]
_, MODEL, MAX_TOK = server.lex_model_for_tier("free")
COMPLEX = ("Fictional: my landlord in Leeds served a section 8 notice on 2 November 2026 for 2 months' arrears, never protected "
           "my £900 deposit, ignored black mould for a year, and told me he doesn't rent to people on Universal Credit. "
           "What are ALL my options, deadlines, and what should I do this week?")
CASES = [
    ("en_short", "en-GB", "Can my landlord enter my flat without telling me?", 0),
    ("en_complex", "en-GB", COMPLEX, 0),
    ("en_letter", "en-GB", "Fictional: write me a full formal letter to my landlord demanding repairs for mould, leaking roof and "
                           "broken boiler, citing the law, with a 14-day deadline, plus a step-by-step plan if he ignores it.", 0),
    ("en_long_history", "en-GB", "So given everything above, what exactly should I do next, step by step?", 12),
    ("cy_complex", "cy-GB", "Ffuglen: rhoddodd fy landlord yng Nghaerdydd hysbysiad adran 173 i mi, nid yw wedi diogelu fy "
                            "mlaendal, ac mae llwydni du ym mhob ystafell. Beth yw fy holl opsiynau a therfynau amser?", 0),
    ("ur_complex", "ur-PK", "فرضی: میرے مالک مکان نے مجھے بے دخلی کا نوٹس دیا، میری جمع شدہ رقم محفوظ نہیں کی، اور گھر میں سیاہ "
                            "پھپھوندی ہے۔ میرے تمام اختیارات اور آخری تاریخیں کیا ہیں؟", 0),
    ("ar_complex", "ar-SA", "افتراضي: أعطاني المالك إشعار إخلاء، ولم يحمِ وديعتي، وهناك عفن أسود في كل غرفة. ما هي كل خياراتي والمواعيد النهائية؟", 0),
    ("pl_complex", "pl-PL", "Fikcyjnie: właściciel w Leeds dał mi wypowiedzenie z sekcji 8, nie zabezpieczył kaucji i ignoruje "
                            "czarną pleśń. Jakie mam wszystkie opcje i terminy?", 0),
    ("zh_complex", "zh-CN", "虚构：我在利兹的房东给了我第8条通知，没有保护我的押金，还无视黑霉问题。我有哪些选择和期限？", 0),
    ("hi_complex", "hi-IN", "काल्पनिक: लीड्स में मेरे मकान मालिक ने सेक्शन 8 नोटिस दिया, मेरी जमा राशि सुरक्षित नहीं की, और काली फफूंद को नज़रअंदाज़ किया। मेरे सभी विकल्प और समय-सीमाएँ क्या हैं?", 0),
]


def history(n):
    out = []
    for i in range(n):
        out += [{"role": "user", "content": f"Fictional detail {i + 1}: my landlord also did thing number {i + 1} — " + COMPLEX[:220]},
                {"role": "assistant", "content": "**Noted.** That adds to your disrepair and deposit claims. " * 6}]
    return out


async def run_case(name, lang, msg, hist):
    system = server.lex_system_prompt(lang, "GB", "ask_lex", "england") + server._lessons_block() + server._fact_pack_block(msg)
    msgs = [{"role": "system", "content": system}] + history(hist) + [{"role": "user", "content": server._date_anchor() + msg}]
    t0 = time.monotonic()
    resp = await litellm.acompletion(model=MODEL, messages=msgs, api_key=KEY, max_tokens=MAX_TOK, stream=True,
                                     stream_options={"include_usage": True}, api_base=get_integration_proxy_url() + "/llm",
                                     custom_llm_provider="openai")
    text, finish, usage, reasoning_chunks = [], None, None, 0
    async for ch in resp:
        if getattr(ch, "usage", None) and getattr(ch.usage, "prompt_tokens", None):
            usage = ch.usage
        try:
            c = ch.choices[0]
            if c.delta and getattr(c.delta, "content", None):
                text.append(c.delta.content)
            if getattr(c.delta, "reasoning_content", None):
                reasoning_chunks += 1
            if c.finish_reason:
                finish = c.finish_reason
        except Exception:
            pass
    full = "".join(text)
    det = getattr(usage, "completion_tokens_details", None)
    return {"case": name, "finish_reason": finish, "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "reasoning_tokens": getattr(det, "reasoning_tokens", None) if det else None, "reasoning_chunks": reasoning_chunks,
            "visible_chars": len(full), "has_confidence_tail": "[CONFIDENCE" in full, "empty": not full.strip(),
            "ends": full.rstrip()[-70:].replace("\n", " "), "secs": round(time.monotonic() - t0, 1)}


async def main():
    await server._lessons_refresh_if_stale(server.db, 0)
    out = []
    for c in CASES:
        try:
            r = await run_case(*c)
        except Exception as e:
            r = {"case": c[0], "error": repr(e)[:200]}
        out.append(r)
        print(json.dumps(r, ensure_ascii=False))
    json.dump({"model": MODEL, "max_tokens": MAX_TOK, "results": out}, open("/app/test_reports/free_tier_output_check.json", "w"),
              indent=1, ensure_ascii=False)


asyncio.run(main())
