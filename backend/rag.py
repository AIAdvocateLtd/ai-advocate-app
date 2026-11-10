"""
AI Advocate — Legal RAG (Retrieval-Augmented Grounding) for Lex.

Pulls live legal context from:
  • legislation.gov.uk + bailii.org + judiciary.uk + gov.uk (filtered Tavily search)
  • Broader web (general Tavily search) — only the top-2 hits.

The result is a compact, citation-tagged context string that gets injected into
Lex's system prompt BEFORE the LLM is called. Every fact Lex states should now be
traceable to a real URL.

Usage cap protection
--------------------
Tavily's free tier = 1000 search credits / month. To make sure we NEVER overshoot
that, we keep a per-month counter in MongoDB (`tavily_usage`) and refuse new calls
once the configured `TAVILY_MONTHLY_CAP` (default 900) is reached. When capped,
Lex still answers the user — just without live grounding for the rest of the month.

If TAVILY_API_KEY is unset OR the monthly cap is reached, this module gracefully
returns an empty context. Lex is never blocked.
"""
from __future__ import annotations

import os
import re
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

import httpx

logger = logging.getLogger("rag")

TAVILY_ENDPOINT = "https://api.tavily.com/search"
QUOTA_STATUS_CODES = (402, 429, 432, 433)  # rate limit / plan or pay-as-you-go limit reached

# Official UK legal sources — Tavily is told to *prefer* these so case law /
# statutes outrank random blog spam.
AUTHORITY_DOMAINS = [
    "legislation.gov.uk",
    "bailii.org",
    "judiciary.uk",
    "supremecourt.uk",
    "gov.uk",
    "caselaw.nationalarchives.gov.uk",
]


def _get_key() -> str:
    # Read at call-time so hot-rotating the key (without restart) just works.
    return os.environ.get("TAVILY_API_KEY", "").strip()


def _get_cap() -> int:
    try:
        return int(os.environ.get("TAVILY_MONTHLY_CAP", "900"))
    except ValueError:
        return 900


def is_enabled() -> bool:
    return bool(_get_key())


def _month_bucket() -> str:
    """e.g. '2026-02' — the bucket key for the usage counter."""
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


async def get_usage(db) -> Dict:
    """Return {'month': '2026-02', 'used': 42, 'cap': 900, 'remaining': 858}."""
    if db is None:
        return {"month": _month_bucket(), "used": 0, "cap": _get_cap(), "remaining": _get_cap()}
    bucket = _month_bucket()
    doc = await db.tavily_usage.find_one({"month": bucket}, {"_id": 0, "count": 1}) or {}
    used = int(doc.get("count") or 0)
    cap = _get_cap()
    return {"month": bucket, "used": used, "cap": cap, "remaining": max(0, cap - used)}


async def _under_cap(db) -> bool:
    if db is None:
        return True
    bucket = _month_bucket()
    doc = await db.tavily_usage.find_one({"month": bucket}, {"_id": 0, "count": 1}) or {}
    used = int(doc.get("count") or 0)
    return used < _get_cap()


async def _increment_usage(db, n: int = 1) -> None:
    if db is None or n <= 0:
        return
    bucket = _month_bucket()
    try:
        await db.tavily_usage.update_one(
            {"month": bucket},
            {"$inc": {"count": n}, "$set": {"last_used_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    except Exception as e:
        logger.warning("Failed to increment Tavily usage counter: %s", e)


async def _tavily_search_ex(
    query: str,
    *,
    include_domains: Optional[List[str]] = None,
    max_results: int = 3,
    search_depth: str = "basic",
):
    """One Tavily API call. Returns (results, status) — status: ok | not_configured | quota_exhausted | unavailable."""
    key = _get_key()
    if not key:
        return [], "not_configured"

    payload = {
        "api_key": key,
        "query": query[:380],  # Tavily best-practice: keep < 400 chars
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }
    if include_domains:
        payload["include_domains"] = include_domains

    try:
        import ai_usage
        _t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(TAVILY_ENDPOINT, json=payload)
            _ok = r.status_code == 200
            _credits = (2 if search_depth == "advanced" else 1) if _ok else 0
            ai_usage.record(provider="tavily", model_requested=f"search-{search_depth}", call_site="legal_research",
                            status="ok" if _ok else "error", latency_ms=(time.monotonic() - _t0) * 1000,
                            cost_gbp=round(_credits * ai_usage.TAVILY_GBP_PER_CREDIT, 6),
                            cost_source="estimated_tavily_credit_rate", units={"credits": _credits})
            if r.status_code != 200:
                logger.warning("Tavily %s: %s", r.status_code, r.text[:200])
                return [], ("quota_exhausted" if r.status_code in QUOTA_STATUS_CODES else "unavailable")
            data = r.json()
            results = data.get("results", []) or []
            out = []
            for item in results[:max_results]:
                out.append({
                    "title": (item.get("title") or "").strip(),
                    "url": (item.get("url") or "").strip(),
                    "content": (item.get("content") or "").strip(),
                })
            return out, "ok"
    except Exception as e:
        logger.warning("Tavily call failed: %s", e)
        return [], "unavailable"


async def _tavily_search(query: str, **kw) -> List[Dict]:
    return (await _tavily_search_ex(query, **kw))[0]


def _looks_like_legal_question(text: str) -> bool:
    """Quick filter: don't burn Tavily credits on 'hi' / 'thanks' / smalltalk."""
    if not text:
        return False
    t = text.strip().lower()
    if len(t) < 12:
        return False
    if len(t.split()) < 3:
        return False
    return True


def _format_block(label: str, items: List[Dict], start_index: int = 1) -> str:
    if not items:
        return ""
    lines = [f"### {label}"]
    for i, it in enumerate(items, start_index):
        title = it.get("title") or "(untitled)"
        url = it.get("url") or ""
        cap = 900 if "legislation.gov.uk/" in url and "/section/" in url else 350
        snippet = (it.get("content") or "")[:cap].replace("\n", " ").strip()
        lines.append(f"[{i}] {title}\n    {url}\n    {snippet}")
    return "\n".join(lines)


async def build_rag_context(message: str, country: str = "GB", db=None):
    r = await research(message, country=country, db=db)
    return r["block"], r["citations"]


_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), ""),
    (re.compile(r"https?://\S+"), ""),
    (re.compile(r"\b(?:\+44\s?|0)(?:\d[\s-]?){9,10}\b"), ""),
    (re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", re.I), ""),
    (re.compile(r"\b[A-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b", re.I), ""),
    (re.compile(r"\b(?:my name is|i am called|i'm called|called|named)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", re.I), ""),
    (re.compile(r"\b\d{6,}\b"), ""),
]
NATION_HINT = {"england": " England law", "wales": " Wales law", "scotland": " Scotland law",
               "northern_ireland": " Northern Ireland law"}


def scrub(text: str) -> str:
    """Remove contact details, postcodes, NI numbers, names and long numbers before sending to a search provider."""
    for rx, rep_ in _PII:
        text = rx.sub(rep_, text or "")
    return re.sub(r"\s+", " ", text).strip()


def build_query(message: str, context: str = "", nation: Optional[str] = None, country: str = "GB") -> str:
    q = scrub(message)
    follow_up = re.match(r"^(and|but|so|or|what about|what if|how about|they|he|she|it|then|also|ok|okay)\b", q, re.I)
    if context and (len(q.split()) < 8 or follow_up):
        last = scrub(context.strip().split("\n")[-1])[:160]
        q = f"{last} {q}".strip()
    cc = (country or "GB").upper()
    hint = NATION_HINT.get(nation or "") or (" Scotland law" if cc == "SCT" else " Northern Ireland law" if cc == "NIR"
                                             else " Wales law" if cc == "WAL" else " UK law")
    return f"{q[:300]}{hint}"


async def research(message: str, country: str = "GB", db=None, context: str = "", nation: Optional[str] = None) -> Dict:
    """Returns {status, block, citations, sources}. status: ok | not_needed | not_configured |
    quota_exhausted | unavailable | no_results. `sources` keeps snippets for server-side citation checks."""
    res = {"status": "not_needed", "block": "", "citations": [], "sources": []}
    if not _looks_like_legal_question(message):
        return res
    if not is_enabled():
        return {**res, "status": "not_configured"}
    if db is not None and not await _under_cap(db):
        logger.info("Tavily monthly cap reached — serving Lex without RAG this turn.")
        return {**res, "status": "quota_exhausted"}

    base_q = build_query(message, context, nation, country)
    import legal_sources

    async def _statute():
        try:
            return await legal_sources.grounding_sources(f"{context}\n{message}", nation)
        except Exception as e:
            logger.info("legislation grounding skipped: %s", e)
            return []

    try:
        (official, s1), (web, s2), statute = await asyncio.wait_for(asyncio.gather(
            _tavily_search_ex(base_q, include_domains=AUTHORITY_DOMAINS, max_results=3, search_depth="basic"),
            _tavily_search_ex(base_q, include_domains=None, max_results=2, search_depth="basic"),
            _statute(),
        ), timeout=9.0)
    except asyncio.TimeoutError:
        logger.warning("Tavily RAG block timed out — continuing without grounding.")
        return {**res, "status": "unavailable"}
    except Exception as e:
        logger.warning("RAG gather failed: %s", e)
        return {**res, "status": "unavailable"}
    await _increment_usage(db, sum(1 for st in (s1, s2) if st == "ok"))

    seen = set()

    def dedupe(items):
        out = []
        for it in items:
            u = it.get("url") or ""
            if u and u not in seen:
                seen.add(u)
                out.append(it)
        return out

    official, web = dedupe(statute) + dedupe(official), dedupe(web)
    if not official and not web:
        failed = {s1, s2} - {"ok"}
        status = ("quota_exhausted" if "quota_exhausted" in failed else "unavailable") if failed else "no_results"
        return {**res, "status": status}

    blocks, citations, sources, next_idx = [], [], [], 1
    for label, items, kind in (("OFFICIAL UK LEGAL SOURCES (statute / case law)", official, "official"),
                               ("SUPPORTING WEB SOURCES", web, "web")):
        if not items:
            continue
        blocks.append(_format_block(label, items, start_index=next_idx))
        for it in items:
            citations.append({"n": next_idx, "title": it.get("title") or "(untitled)", "url": it.get("url") or "", "source": kind})
            sources.append({"n": next_idx, "title": it.get("title") or "", "content": it.get("content") or ""})
            next_idx += 1
    body = "\n\n".join(blocks)
    block = (
        "\n\n=== LIVE LEGAL RESEARCH (retrieved just now) ===\n"
        f"{body}\n\n"
        "USE THESE SOURCES: Ground your answer in the material above. When you state "
        "a rule, cite the source like [1] or [2] matching the numbered list — only numbers 1 to "
        f"{next_idx - 1} exist. Only cite a number if that source actually says what you are claiming. If the "
        "retrieved material does NOT cover the user's question, say so and give your "
        "best general guidance — never invent a citation, case, section or URL."
    )
    return {"status": "ok", "block": block, "citations": citations, "sources": sources}
