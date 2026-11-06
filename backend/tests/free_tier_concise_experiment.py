"""Free-tier conciseness vs cap experiment (fictional; direct model calls with the real Lex prompt). python tests/free_tier_concise_experiment.py"""
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
import litellm  # noqa: E402
from emergentintegrations.llm.utils import get_integration_proxy_url  # noqa: E402
import server  # noqa: E402

KEY = os.environ["EMERGENT_LLM_KEY"]
COMPLEX = ("Fictional: my landlord in Leeds served a section 8 notice on 2 November 2026 for 2 months' arrears, never protected "
           "my £900 deposit, ignored black mould for a year, and told me he doesn't rent to people on Universal Credit. "
           "What are ALL my options, deadlines, and what should I do this week?")
QS = [("en_complex", "en-GB", COMPLEX),
      ("en_dismissal", "en-GB", "Fictional: I was dismissed on 2 November 2026 after 3 years with no warning or meeting. Can I claim and what should I do?"),
      ("en_simple", "en-GB", "Can my landlord enter my flat without telling me?"),
      ("en_letter", "en-GB", "Fictional: write a letter to my landlord asking him to fix the broken boiler within 14 days."),
      ("cy", "cy-GB", "Ffuglen: rhoddodd fy landlord yng Nghaerdydd hysbysiad adran 173 i mi ac nid yw wedi diogelu fy mlaendal. Beth yw fy opsiynau?"),
      ("ur", "ur-PK", "فرضی: میرے مالک مکان نے مجھے بے دخلی کا نوٹس دیا اور میری جمع شدہ رقم محفوظ نہیں کی۔ میرے اختیارات کیا ہیں؟")]
CONCISE = ("\n\n[Answer format for this reply: be concise — at most about 300 words (fewer in non-Latin scripts), short bullets, "
           "the most urgent steps and any deadline first, then the disclaimer line and the [CONFIDENCE]/[SOURCES] lines. "
           "If more detail would help, offer it in one closing sentence. A letter may be up to about 350 words.]")
VARIANTS = [("A_1200", 1200, False), ("B_1200_concise", 1200, True), ("C_1600", 1600, False), ("D_1600_concise", 1600, True)]


async def one(lang, msg, cap, concise):
    system = server.lex_system_prompt(lang, "GB", "ask_lex", "england") + server._lessons_block() + server._fact_pack_block(msg)
    user = server._date_anchor() + msg + (CONCISE if concise else "")
    r = await litellm.acompletion(model="claude-haiku-5-5", messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                                  api_key=KEY, max_tokens=cap, api_base=get_integration_proxy_url() + "/llm", custom_llm_provider="openai",
                                  extra_body={"thinking": {"type": "disabled"}})
    t = r.choices[0].message.content or ""
    return {"finish": r.choices[0].finish_reason, "out_tokens": r.usage.completion_tokens, "in_tokens": r.usage.prompt_tokens,
            "chars": len(t), "complete": r.choices[0].finish_reason == "stop" and "[CONFIDENCE" in t, "text_head": t[:160].replace("\n", " ")}


async def main():
    await server._lessons_refresh_if_stale(server.db, 0)
    rows = []
    for vname, cap, concise in VARIANTS:
        res = await asyncio.gather(*[one(lang, msg, cap, concise) for _, lang, msg in QS], return_exceptions=True)
        for (qn, _, _), r in zip(QS, res):
            row = {"variant": vname, "q": qn, **(r if isinstance(r, dict) else {"error": repr(r)[:150]})}
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "text_head"}, ensure_ascii=False))
    json.dump(rows, open("/app/test_reports/free_tier_concise_experiment.json", "w"), indent=1, ensure_ascii=False)
    for vname, *_ in VARIANTS:
        vs = [r for r in rows if r["variant"] == vname and "error" not in r]
        print(vname, "complete", sum(r["complete"] for r in vs), "/", len(vs), "avg_out", round(sum(r["out_tokens"] for r in vs) / max(1, len(vs))))


asyncio.run(main())
