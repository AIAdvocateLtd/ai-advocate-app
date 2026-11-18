"""Optional layer 3 of Lex's citation checks: an AI check of whether a cited source passage supports a high-stakes claim.
OFF by default (app_settings _id "lex_ai_source_check", enabled: false). Runs only for claims the free checks marked
'uncertain', only in high-stakes / deadline answers, at most MAX_CLAIMS per answer, cached by claim+passage. It is an AI
check — never independent professional legal verification. Not activated anywhere without separate approval."""
import hashlib
import json
import logging
import os
import re
import time
import uuid
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)
SETTINGS_ID = "lex_ai_source_check"
MODEL = ("anthropic", "claude-haiku-4-5-20251001")  # the model the app already uses for deadline extraction
MAX_CLAIMS, PASSAGE_CHARS, CACHE_TTL = 3, 3000, 7 * 86400
# Haiku 4.5 list price $1 / $5 per million tokens; ~1,100 input + ~60 output tokens per claim ≈ $0.0014 ≈ £0.0011.
EST_GBP_PER_CLAIM = 0.0011
_cache: dict = {}
SYSTEM = ("You check whether a SOURCE PASSAGE supports a CLAIM made in a UK legal-information answer. Reply with JSON only: "
          '{"verdict":"supported|partly|unsupported","why":"<=20 words"}. "supported" only if the passage itself states the '
          "claim's rule, period or condition; matching words or topic alone is not support. Do not use outside knowledge.")
QUALIFIER = " (the cited source does not clearly support this — treat it as unconfirmed)"


async def enabled(db) -> bool:
    doc = await db.app_settings.find_one({"_id": SETTINGS_ID}) or {}
    return doc.get("enabled") is True


def _passage(claim: str, content: str) -> str:
    """The part of the source most relevant to the claim (reuses the already-retrieved text; no new search)."""
    words = {w[:6] for w in re.findall(r"[a-z]{5,}", claim.lower())}
    paras = [p for p in re.split(r"\n{2,}|(?<=[.!?])\s{2,}", content or "") if p.strip()] or [content or ""]
    paras.sort(key=lambda p: -sum(1 for w in words if w in p.lower()))
    return " ".join(paras)[:PASSAGE_CHARS]


def _locate(out: str, text: str) -> str:
    """The claim's sentence as it appears in the answer, allowing [n] markers between words."""
    words = re.findall(r"\S+", re.sub(r"[.!?]+$", "", text or "").strip())
    if not words:
        return ""
    rx = r"(?:\s*\[\d+\])*\s+".join(re.escape(w) for w in words) + r"(?:\s*\[\d+\])*\s*[.!?]?"
    m = re.search(rx, out)
    return m.group(0) if m else ""


async def _ask(claim: str, passage: str) -> dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"), session_id=f"srccheck-{uuid.uuid4()}", system_message=SYSTEM) \
        .with_model(*MODEL).with_params(max_tokens=120)
    raw = await chat.send_message(UserMessage(text=f"CLAIM:\n{claim}\n\nSOURCE PASSAGE:\n{passage}"))
    m = re.search(r"\{.*\}", raw or "", re.S)
    v = json.loads(m.group(0)) if m else {}
    return {"verdict": v.get("verdict") if v.get("verdict") in ("supported", "partly", "unsupported") else "uncertain",
            "why": str(v.get("why") or "")[:160]}


async def run(db, text: str, claim_support: List[dict], sources: List[dict], hs: Optional[dict], has_deadlines: bool,
              ask=None) -> Tuple[str, dict]:
    rep = {"enabled": False, "checked": 0, "cached": 0, "qualified": 0, "est_gbp": 0.0, "results": []}
    if not await enabled(db):
        return text, rep
    rep["enabled"] = True
    if not ((hs or {}).get("level") in ("emergency", "urgent", "high") or has_deadlines):
        return text, rep
    by_n = {int(s["n"]): s.get("content") or "" for s in sources or [] if str(s.get("n", "")).isdigit()}
    todo = [c for c in claim_support if c.get("status") == "uncertain" and by_n.get(c["n"])][:MAX_CLAIMS]
    ask = ask or _ask
    out = text
    for c in todo:
        raw = c.get("raw") if c.get("raw") and c["raw"] in out else _locate(out, c.get("text", ""))
        if not raw:
            rep["unplaced"] = rep.get("unplaced", 0) + 1  # sentence changed later — skip (no call, no charge)
            continue
        passage = _passage(c["text"], by_n[c["n"]])
        key = hashlib.sha256(f"{c['text']}\n{passage}".encode()).hexdigest()
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            res = hit[1]
            rep["cached"] += 1
        else:
            try:
                res = await ask(c["text"], passage)
            except Exception as e:
                logger.info(f"AI source check failed: {e!r}")
                rep["failed"] = rep.get("failed", 0) + 1
                continue  # not cached, not charged; the claim keeps its free-check status
            _cache[key] = (time.time() + CACHE_TTL, res)
            rep["checked"] += 1
            rep["est_gbp"] = round(rep["est_gbp"] + EST_GBP_PER_CLAIM, 4)
        c["ai_check"] = res["verdict"]
        rep["results"].append({"n": c["n"], **res})
        if res["verdict"] in ("unsupported", "partly"):
            tail = re.search(r"(?:\s*\[\d+\])*\s*[.!?]?\s*$", raw)
            cut = tail.start() if tail else len(raw)
            out = out.replace(raw, raw[:cut] + QUALIFIER + raw[cut:], 1)
            c["status"] = "unsupported" if res["verdict"] == "unsupported" else "uncertain"
            rep["qualified"] += 1
    return out, rep
