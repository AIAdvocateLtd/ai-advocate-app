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
    "acas.org.uk",
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
        cap = 4000 if "legislation.gov.uk/" in url and "/section/" in url else 1800 if it.get("acas_key") else 350
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


_STOP = set("this that with from have what your about under does would could should which when where will their there been "
             "into them they than then also only just very more most some such like make made were want need know tell "
             "england wales scotland northern ireland britain united kingdom please help".split())
_OFF_TOPIC = re.compile(r"\b(constitution|standing orders|minutes of|agenda|committee meeting|council meeting|scheme of delegation|"
                        r"annual report|press release)\b", re.I)


def _relevant(it: dict, query: str) -> bool:
    """Drops search results that don't match the question (e.g. a council constitution for a dismissal query)."""
    title = it.get("title") or ""
    if _OFF_TOPIC.search(title) and not _OFF_TOPIC.search(query):
        return False
    blob = f"{title} {it.get('url') or ''} {it.get('content') or ''}".lower()
    terms = {w[:5] for w in re.findall(r"[a-z]{4,}", (query or "").lower()) if w not in _STOP}
    return sum(1 for t in terms if t in blob) >= min(2, len(terms))


async def research(message: str, country: str = "GB", db=None, context: str = "", nation: Optional[str] = None) -> Dict:
    """Returns {status, block, citations, sources}. status: ok | not_needed | not_configured |
    quota_exhausted | unavailable | no_results. `sources` keeps snippets for server-side citation checks."""
    res = {"status": "not_needed", "block": "", "citations": [], "sources": []}
    if not _looks_like_legal_question(message):
        return res
    # Paid web search is gated by its key and the monthly cap; the free official lookups below run regardless.
    paid = "ok"
    if not is_enabled():
        paid = "not_configured"
    elif db is not None and not await _under_cap(db):
        logger.info("Tavily monthly cap reached — paid search skipped; free official lookups still run.")
        paid = "quota_exhausted"

    base_q = build_query(message, context, nation, country)
    import legal_sources

    async def _statute():
        try:
            return await legal_sources.grounding_sources(f"{message}\n{context}", nation)
        except Exception as e:
            logger.info("legislation grounding skipped: %s", e)
            return []

    import official_guidance

    async def _guidance():
        try:
            return await official_guidance.guidance_sources(message, context)
        except Exception as e:
            logger.info("acas guidance skipped: %s", e)
            return [], []

    async def _paid(include_domains, n):
        if paid != "ok":
            return [], paid
        try:
            return await asyncio.wait_for(_tavily_search_ex(base_q, include_domains=include_domains, max_results=n,
                                                            search_depth="basic"), timeout=8.5)
        except asyncio.TimeoutError:
            return [], "unavailable"

    try:
        (official, s1), (web, s2), statute, (guidance, g_failed) = await asyncio.wait_for(asyncio.gather(
            _paid(AUTHORITY_DOMAINS, 3), _paid(None, 2), _statute(), _guidance(),
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

    rel_q = scrub(message)
    official = dedupe(statute) + dedupe(guidance) + [it for it in dedupe(official) if _relevant(it, rel_q)]
    g_meta = {"guidance_keys": [it["acas_key"] for it in guidance], "guidance_failed": g_failed,
              "paid_search": "ok" if "ok" in (s1, s2) else (paid if paid != "ok" else "unavailable")}
    web = [it for it in dedupe(web) if _relevant(it, rel_q)]
    if not official and not web:
        failed = {s1, s2} - {"ok"}
        status = (paid if paid != "ok" else ("quota_exhausted" if "quota_exhausted" in failed else "unavailable")) \
            if failed else "no_results"
        return {**res, "status": status, **g_meta}

    blocks, citations, sources, next_idx = [], [], [], 1
    for label, items, kind in (("OFFICIAL UK LEGAL SOURCES (statute / case law)", official, "official"),
                               ("SUPPORTING WEB SOURCES", web, "web")):
        if not items:
            continue
        blocks.append(_format_block(label, items, start_index=next_idx))
        for it in items:
            citations.append({"n": next_idx, "title": it.get("title") or "(untitled)", "url": it.get("url") or "", "source": kind})
            sources.append({"n": next_idx, "title": it.get("title") or "", "content": it.get("content") or "",
                            "guidance": bool(it.get("acas_key"))})
            next_idx += 1
    body = "\n\n".join(blocks)
    if g_meta["paid_search"] != "ok":
        body += ("\n\nNOTE: only the free official lookups above (legislation.gov.uk / acas.org.uk) were available for this "
                 "answer — wider research could not be run. Rely on these sources for what they cover; for anything else, "
                 "say plainly that it could not be checked against current sources just now.")
    block = (
        "\n\n=== LIVE LEGAL RESEARCH (retrieved just now) ===\n"
        f"{body}\n\n"
        "USE THESE SOURCES: Ground your answer in the material above. When you state "
        "a rule, cite the source like [1] or [2] matching the numbered list — only numbers 1 to "
        f"{next_idx - 1} exist. Only cite a number if that source actually says what you are claiming. Legislation and "
        "official guidance take priority: supporting web sources may add context but never override them. The territorial "
        "extent shown for legislation is where it is law — never infer UK-wide or Northern Ireland extent beyond it, and "
        "keep extent separate from whether it applies to the customer in practice. A legislation STATUS CHECK only confirms a "
        "provision exists and is in force; RETRIEVED WORDING shows what it says; neither proves your interpretation — say "
        "which applies, and if you rely on wording you were not given, say so plainly. Sources marked 'acas.org.uk "
        "(official guidance; wording retrieved …)' were fetched from Acas just now — cite them for points about Acas "
        "guidance or the Acas Code. UK FACTS SIGNED OFF BY AI ADVOCATE'S REVIEWER are built-in knowledge, not retrieved text — where retrieved official sources conflict with them, say so. If the "
        "retrieved material does NOT cover the user's question, say so and give your "
        "best general guidance — never invent a citation, case, section or URL."
    )
    return {"status": "ok", "block": block, "citations": citations, "sources": sources, **g_meta}
