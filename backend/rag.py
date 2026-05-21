"""
AI Advocate — Legal RAG (Retrieval-Augmented Grounding) for Lex.

Pulls live legal context from:
  • legislation.gov.uk + bailii.org + judiciary.uk + gov.uk (filtered Tavily search)
  • Broader web (general Tavily search) — only the top-3 hits.

The result is a compact, citation-tagged context string that gets injected into
Lex's system prompt BEFORE the LLM is called. Every fact Lex states should now be
traceable to a real URL.

If TAVILY_API_KEY is not set, this module gracefully returns an empty context —
Lex still works, just without web grounding. This means the app keeps running
even when the user hasn't activated Tavily yet.
"""
from __future__ import annotations

import os
import asyncio
import logging
from typing import List, Dict, Optional

import httpx

logger = logging.getLogger("rag")

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()
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


def is_enabled() -> bool:
    return bool(TAVILY_API_KEY)


async def _tavily_search(
    query: str,
    *,
    include_domains: Optional[List[str]] = None,
    max_results: int = 3,
    search_depth: str = "basic",
) -> List[Dict]:
    """One Tavily API call. Returns list of {title, url, content} dicts."""
    if not TAVILY_API_KEY:
        return []

    payload = {
        "api_key": TAVILY_API_KEY,
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
    # If it's just one or two words, skip.
    if len(t.split()) < 3:
        return False
    return True


def _format_block(label: str, items: List[Dict]) -> str:
    if not items:
        return ""
    lines = [f"### {label}"]
    for i, it in enumerate(items, 1):
        title = it.get("title") or "(untitled)"
        url = it.get("url") or ""
        snippet = (it.get("content") or "")[:350].replace("\n", " ").strip()
        lines.append(f"[{i}] {title}\n    {url}\n    {snippet}")
    return "\n".join(lines)


async def build_rag_context(message: str, country: str = "GB") -> str:
    """
    Returns a citation-tagged context block to append to Lex's system prompt,
    OR an empty string if RAG is disabled / question is smalltalk.
    """
    if not is_enabled():
        return ""
    if not _looks_like_legal_question(message):
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
        official, web = await asyncio.gather(official_task, web_task)
    except Exception as e:
        logger.warning("RAG gather failed: %s", e)
        return ""

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
    if official:
        blocks.append(_format_block("OFFICIAL UK LEGAL SOURCES (statute / case law)", official))
    if web:
        blocks.append(_format_block("SUPPORTING WEB SOURCES", web))

    body = "\n\n".join(blocks)

    return (
        "\n\n=== LIVE LEGAL RESEARCH (retrieved just now) ===\n"
        f"{body}\n\n"
        "USE THESE SOURCES: Ground your answer in the material above. When you state "
        "a rule, cite the source like [1] or [2] matching the numbered list. If the "
        "retrieved material does NOT cover the user's question, say so and give your "
        "best general guidance — never invent a citation."
    )
