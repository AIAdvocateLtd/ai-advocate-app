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
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

import httpx

logger = logging.getLogger("rag")

TAVILY_ENDPOINT = "https://api.tavily.com/search"

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


async def _tavily_search(
    query: str,
    *,
    include_domains: Optional[List[str]] = None,
    max_results: int = 3,
    search_depth: str = "basic",
) -> List[Dict]:
    """One Tavily API call. Returns list of {title, url, content} dicts."""
    key = _get_key()
    if not key:
        return []

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
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(TAVILY_ENDPOINT, json=payload)
            if r.status_code != 200:
                logger.warning("Tavily %s: %s", r.status_code, r.text[:200])
                return []
            data = r.json()
            results = data.get("results", []) or []
            out = []
            for item in results[:max_results]:
                out.append({
                    "title": (item.get("title") or "").strip(),
                    "url": (item.get("url") or "").strip(),
                    "content": (item.get("content") or "").strip(),
                })
            return out
    except Exception as e:
        logger.warning("Tavily call failed: %s", e)
        return []


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
        snippet = (it.get("content") or "")[:350].replace("\n", " ").strip()
        lines.append(f"[{i}] {title}\n    {url}\n    {snippet}")
    return "\n".join(lines)


async def build_rag_context(message: str, country: str = "GB", db=None) -> str:
    """
    Returns a citation-tagged context block to append to Lex's system prompt,
    OR an empty string if RAG is disabled / question is smalltalk / monthly cap hit.

    Pass `db` (the Motor database handle) to enable usage-cap protection.
    """
    if not is_enabled():
        return ""
    if not _looks_like_legal_question(message):
        return ""

    # 🚧 Usage cap — never exceed the configured monthly cap.
    if db is not None and not await _under_cap(db):
        logger.info("Tavily monthly cap reached — serving Lex without RAG this turn.")
        return ""

    # Bias query toward jurisdiction for better UK / Scotland / NI hits.
    jurisdiction_hint = ""
    cc = (country or "GB").upper()
    if cc in ("GB", "UK", "ENG", "WAL"):
        jurisdiction_hint = " UK law"
    elif cc == "SCT":
        jurisdiction_hint = " Scotland law"
    elif cc == "NIR":
        jurisdiction_hint = " Northern Ireland law"

    base_q = f"{message.strip()[:280]}{jurisdiction_hint}"

    calls_made = 0
    try:
        official_task = _tavily_search(
            base_q,
            include_domains=AUTHORITY_DOMAINS,
            max_results=3,
            search_depth="basic",
        )
        web_task = _tavily_search(
            base_q,
            include_domains=None,
            max_results=2,
            search_depth="basic",
        )
        # Whole RAG budget hard-capped at ~9s so a slow Tavily call never tanks
        # Lex's perceived response time.
        official, web = await asyncio.wait_for(
            asyncio.gather(official_task, web_task), timeout=9.0
        )
        calls_made = 2  # we attempted 2 search credits regardless of result count
    except asyncio.TimeoutError:
        logger.warning("Tavily RAG block timed out — continuing without grounding.")
        return ""
    except Exception as e:
        logger.warning("RAG gather failed: %s", e)
        return ""

    # Count the credits we actually consumed (Tavily charges per call attempted,
    # not per result returned).
    if calls_made:
        await _increment_usage(db, calls_made)

    # Dedupe by URL — web search will sometimes return the same authority hit.
    seen = set()
    def dedupe(items):
        out = []
        for it in items:
            u = it.get("url") or ""
            if u and u not in seen:
                seen.add(u)
                out.append(it)
        return out

    official = dedupe(official)
    web = dedupe(web)

    if not official and not web:
        return ""

    blocks = []
    next_idx = 1
    if official:
        blocks.append(_format_block("OFFICIAL UK LEGAL SOURCES (statute / case law)", official, start_index=next_idx))
        next_idx += len(official)
    if web:
        blocks.append(_format_block("SUPPORTING WEB SOURCES", web, start_index=next_idx))

    body = "\n\n".join(blocks)

    return (
        "\n\n=== LIVE LEGAL RESEARCH (retrieved just now) ===\n"
        f"{body}\n\n"
        "USE THESE SOURCES: Ground your answer in the material above. When you state "
        "a rule, cite the source like [1] or [2] matching the numbered list. If the "
        "retrieved material does NOT cover the user's question, say so and give your "
        "best general guidance — never invent a citation."
    )
