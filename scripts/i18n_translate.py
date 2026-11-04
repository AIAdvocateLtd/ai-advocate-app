"""Translate /app/scripts/i18n_source.json into /app/frontend/public/i18n/{lang}.json (incremental, resumable).

Usage: cd /app/backend && python3 /app/scripts/i18n_translate.py [lang ...]
"""
import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

KEEP_AS_IS = {"Lex", "AI Advocate", "Lex Vault", "Trustpilot", "Stripe", "Google", "Apple", "GOV.UK", "ACAS"}
LANGS = {"es-ES": "Spanish (Spain)", "fr-FR": "French", "ar-IQ": "Arabic (Modern Standard, Iraqi audience)",
         "pl-PL": "Polish", "de-DE": "German", "hi-IN": "Hindi", "ur-PK": "Urdu", "it-IT": "Italian",
         "pt-PT": "Portuguese (Portugal)", "zh-CN": "Simplified Chinese"}
OUT = Path("/app/frontend/public/i18n")
BATCH_CHARS = 2500
SYSTEM = ("You translate user-interface text for AI Advocate, a UK legal-help app, into {lang}. "
          "Rules: translate naturally and concisely for app buttons/labels/pages. Always translate ordinary English words and feature "
          "names (e.g. Will Writer, Letter Writer, Conveyancing Companion, Contract Hub, Witness Builder, 'not a law firm'). "
          "Keep unchanged ONLY: brand names (AI Advocate, Lex, Lex Vault, Trustpilot, Stripe, Google, Apple), UK legal/official names and form codes (GOV.UK, ACAS, LRA, HMRC, "
          "DWP, HM Land Registry, ET1, TA6, TA10, SDLT, ILR, section 8/21/173, Legal Aid Agency, SRA), emails, URLs, prices and "
          "currency symbols, numbers, emojis and symbols (· → ★ ✓ etc.). Preserve leading/trailing punctuation and spaces exactly. "
          "Fragments (e.g. starting with a comma or ending mid-sentence) must stay fragments. "
          "Input lines are 'NUMBER<TAB>text'. Reply ONLY with the same lines as 'NUMBER<TAB>translation', one per line, same numbers, "
          "no extra text.")


# Headlines split across two styled elements — hand-written so both halves read naturally.
SPLIT_PAIRS = {
    "es-ES": ("La ley en la", "palma de tu mano."), "fr-FR": ("La loi au", "creux de votre main."),
    "it-IT": ("La legge nel", "palmo della tua mano."), "pt-PT": ("A lei na", "palma da sua mão."),
    "de-DE": ("Das Recht in", "Ihrer Hand."), "pl-PL": ("Prawo w", "zasięgu Twojej ręki."),
    "ar-IQ": ("القانون في", "راحة يدك."), "ur-PK": ("قانون آپ کی", "مٹھی میں۔"),
    "hi-IN": ("क़ानून आपकी", "मुट्ठी में।"), "zh-CN": ("法律，", "尽在掌握。"),
}


GLOSSARY = {
    "Will Writer": {"es-ES": "Redactor de Testamentos", "fr-FR": "Rédacteur de testament", "pl-PL": "Kreator testamentu",
                    "de-DE": "Testament-Assistent", "ur-PK": "وصیت نامہ رائٹر", "it-IT": "Redattore di testamento",
                    "pt-PT": "Redator de Testamento", "ar-IQ": "كاتب الوصية", "hi-IN": "वसीयत लेखक", "zh-CN": "遗嘱撰写"},
    "Conveyancing Companion": {"es-ES": "Asistente de Compraventa de Vivienda", "fr-FR": "Assistant achat-vente immobilier",
                               "pl-PL": "Asystent kupna i sprzedaży nieruchomości", "de-DE": "Immobilienkauf-Assistent",
                               "it-IT": "Assistente compravendita immobiliare", "pt-PT": "Assistente de Compra e Venda de Casa",
                               "ur-PK": "جائیداد کی خرید و فروخت کا معاون", "ar-IQ": "رفيق نقل الملكية",
                               "hi-IN": "संपत्ति ख़रीद-बिक्री सहायक", "zh-CN": "房产买卖助手"},
}


async def translate_pairs(lang, done):
    for k in [k for k, v in done.items() if v == k and k not in KEEP_AS_IS]:
        done.pop(k)
    for en, tr in GLOSSARY.items():
        if lang in tr:
            done[en] = tr[lang]
    done.pop("__pair__The law in the", None)
    if lang in SPLIT_PAIRS:
        done["The law in the"], done["palm of your hand."] = SPLIT_PAIRS[lang]


def batches(items):
    cur, size = [], 0
    for s in items:
        if cur and (size + len(s) > BATCH_CHARS or len(cur) >= 40):
            yield cur
            cur, size = [], 0
        cur.append(s)
        size += len(s)
    if cur:
        yield cur


async def translate_batch(lang, items, sem):
    async with sem:
        payload = "\n".join(f"{i}\t{s}" for i, s in enumerate(items))
        for attempt in range(3):
            try:
                chat = LlmChat(api_key=os.environ["EMERGENT_LLM_KEY"], session_id=f"i18n-{uuid.uuid4()}",
                               system_message=SYSTEM.format(lang=LANGS[lang])) \
                    .with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=12000)
                raw = await chat.send_message(UserMessage(text=payload))
                got = {}
                for line in (raw or "").splitlines():
                    m = re.match(r"^\s*(\d+)\t(.*)$", line)
                    if m and int(m.group(1)) < len(items) and m.group(2).strip():
                        got[items[int(m.group(1))]] = m.group(2)
                if len(got) < len(items) * 0.8:
                    raise ValueError(f"only {len(got)}/{len(items)} lines")
                return got
            except Exception as e:
                print(lang, "retry", attempt, repr(e)[:120], flush=True)
                await asyncio.sleep(2)
        return {}


async def run_lang(lang, source, sem):
    path = OUT / f"{lang}.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    if "--fix-same" in sys.argv:
        for k in [k for k, v in done.items() if v == k and re.search(r"[a-z]{3,}", k) and k not in KEEP_AS_IS]:
            done.pop(k)
        for k in [k for k, v in done.items() if re.search(r"\b(Companion|Writer|Hub|Builder|Finder)\b", v)]:
            done.pop(k)
    todo = [s for s in source if s not in done]
    print(lang, "todo", len(todo), flush=True)
    for b in batches(todo):
        done.update(await translate_batch(lang, b, sem))
        path.write_text(json.dumps(done, ensure_ascii=False, separators=(",", ":")))
        print(lang, len(done), flush=True)
    await translate_pairs(lang, done)
    path.write_text(json.dumps(done, ensure_ascii=False, separators=(",", ":")))
    print(lang, "done", len(done), "/", len(source), flush=True)


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = json.loads(Path("/app/scripts/i18n_source.json").read_text())
    langs = [a for a in sys.argv[1:] if not a.startswith("--")] or list(LANGS)
    sem = asyncio.Semaphore(12)
    await asyncio.gather(*(run_lang(lang, source, sem) for lang in langs))


if __name__ == "__main__":
    asyncio.run(main())
