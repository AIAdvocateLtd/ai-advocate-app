"""One-off calibration: compare provider-measured input tokens with local estimates across request types.
Uses max_tokens=1 so only input tokens are billed. Run: python tests/token_calibration.py"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
import litellm  # noqa: E402
import tiktoken  # noqa: E402
from emergentintegrations.llm.utils import get_integration_proxy_url  # noqa: E402

KEY = os.environ["EMERGENT_LLM_KEY"]
ENC = tiktoken.get_encoding("o200k_base")
LEGAL = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fact_packs.py")).read()[:9000]

SAMPLES = {
    "short_en": [{"role": "user", "content": "My landlord in Leeds won't return my £900 deposit. What can I do?"}],
    "long_system_legal": [{"role": "system", "content": LEGAL}, {"role": "user", "content": "Summarise the key deadlines."}],
    "multi_turn": [{"role": "system", "content": "You are Lex, a UK legal assistant."}] + [
        {"role": r, "content": c} for _ in range(6) for r, c in (
            ("user", "I was dismissed on 3 March 2026 after 26 months. They said gross misconduct but no hearing happened."),
            ("assistant", "**Unfair dismissal** — with 2+ years' service you can claim. Contact ACAS within 3 months less one day [1]."))],
    "welsh": [{"role": "user", "content": "Mae fy landlord yng Nghaerdydd wedi rhoi hysbysiad adran 173 i mi. Faint o amser sydd gennyf cyn bod rhaid i mi adael y tŷ? " * 6}],
    "urdu_arabic": [{"role": "user", "content": "میرے مالک مکان نے میری جمع شدہ رقم واپس نہیں کی۔ میں کیا کر سکتا ہوں؟ مالك العقار لم يرد وديعتي. " * 6}],
    "json_numbers": [{"role": "user", "content": json.dumps({"calcs": [{"type": "employment_tribunal", "event_date": "2026-03-03",
                                                                        "acas_date": "2026-05-01", "certificate_date": "2026-06-12",
                                                                        "jurisdiction": "england"}] * 12})}],
}
MODELS = ["claude-haiku-5-5", "claude-sonnet-5-5", "gpt-5.2"]


async def measure(model, messages):
    r = await litellm.acompletion(model=model, messages=messages, api_key=KEY, max_tokens=16,
                                  api_base=get_integration_proxy_url() + "/llm", custom_llm_provider="openai")
    return r.usage.prompt_tokens


async def main():
    rows = []
    for name, msgs in SAMPLES.items():
        chars = sum(len(m["content"]) for m in msgs)
        tk = sum(len(ENC.encode(m["content"])) for m in msgs)
        for model in MODELS:
            try:
                real = await measure(model, msgs)
            except Exception as e:
                print(name, model, "ERR", repr(e)[:120])
                continue
            rows.append({"sample": name, "model": model, "chars": chars, "n_msgs": len(msgs), "measured": real,
                         "chars_div_4": chars // 4, "tiktoken": tk})
            print(json.dumps(rows[-1]))
    json.dump(rows, open("/app/memory/token_calibration_results.json", "w"), indent=1)


asyncio.run(main())
