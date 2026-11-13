"""Official Acas guidance fetched directly from acas.org.uk (Open Government Licence). No AI, no paid search.
Cached 24h (re-fetched after that so wording stays current); failures cached 5 min."""
import asyncio
import html
import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)
UA = {"User-Agent": "AIAdvocate/1.0 (+https://aiadvocate.co.uk; support@aiadvocate.co.uk)"}
OK_TTL, FAIL_TTL, TIMEOUT, MAX_PAGES, EXCERPT = 24 * 3600, 300, 5.0, 2, 1800
OGL_ACAS = "Contains Acas guidance (Crown copyright) licensed under the Open Government Licence v3.0."
BASE = "https://www.acas.org.uk"
_EMP = re.compile(r"\b(employ\w*|dismiss\w*|sacked|fired|disciplinar\w*|grievance|acas|tribunal|capability|"
                  r"performance|misconduct|warning|appeal hearing|redundan\w*|notice period)\b", re.I)
# (key, title, path, triggers, name in an answer that means Lex relied on it)
PAGES = [
    ("code", "Acas Code of Practice on disciplinary and grievance procedures",
     "/acas-code-of-practice-on-disciplinary-and-grievance-procedures/html",
     r"acas code|code of practice|disciplinar\w*|grievance|misconduct|poor performance|capability|written warning|"
     r"final warning|right to be accompanied|appeal hearing", r"acas code|code of practice"),
    ("performance", "Acas: Dismissals for capability or conduct", "/performance-management/dismissals-for-capability-or-conduct",
     r"performance|capability|underperform\w*|not good enough at|pip\b|improvement plan", r"capability"),
    ("time_limits", "Acas: Employment tribunal time limits", "/employment-tribunal-time-limits",
     r"time limit|deadline|how long|too late|out of time|tribunal claim|et1|\bclaim\b", r"time limit"),
    ("early_conciliation", "Acas: What early conciliation is", "/early-conciliation",
     r"early conciliation|notify acas|acas certificate|conciliat\w*|contact acas", r"early conciliation"),
    ("dismissals", "Acas: Dismissals", "/dismissals", r"dismiss\w*|sacked|fired|let go", r"dismiss"),
]
_cache: Dict[str, Tuple[float, Optional[dict]]] = {}
_STOP = set("this that with from have what your about under does would could should which when where will their there been "
            "into them they than then also only just very more most some such like make made were want need know tell".split())


def _text(page: str) -> str:
    m = re.search(r"<main.*?</main>", page, re.S)
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<nav.*?</nav>", "", m.group(0) if m else page, flags=re.S)
    t = re.sub(r"</(p|li|h\d|div|tr)>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if len(ln) > 25 and not ln.startswith("Breadcrumbs"))


async def _fetch(url: str) -> Tuple[int, str]:
    async with httpx.AsyncClient(timeout=4.0, headers=UA, follow_redirects=True) as c:
        r = await c.get(url)
        return r.status_code, (r.text if r.status_code == 200 else "")


async def get_page(key: str) -> Optional[dict]:
    """{key,title,url,text,fetched_at} or None if acas.org.uk could not be reached."""
    hit = _cache.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    _, title, path, _, _ = next(p for p in PAGES if p[0] == key)
    url = BASE + path
    try:
        code, body = await _fetch(url)
        text = _text(body) if code == 200 else ""
        if len(text) < 200:
            raise RuntimeError(f"acas {code} / {len(text)} chars")
        val = {"key": key, "title": title, "url": url, "text": text,
               "fetched_at": datetime.now(timezone.utc).strftime("%d %B %Y")}
        _cache[key] = (time.monotonic() + OK_TTL, val)
        return val
    except Exception as e:
        logger.info(f"acas guidance fetch failed for {key}: {e!r}")
        _cache[key] = (time.monotonic() + FAIL_TTL, None)
        return None


def pick(text: str) -> List[str]:
    if not _EMP.search(text or ""):
        return []
    return [p[0] for p in PAGES if re.search(p[3], text, re.I)][:MAX_PAGES]


def excerpt(text: str, query: str, size: int = EXCERPT) -> str:
    """The paragraphs of the page that best match the question, in page order."""
    terms = {w[:5] for w in re.findall(r"[a-z]{4,}", (query or "").lower()) if w not in _STOP}
    paras = text.split("\n")
    scored = sorted(range(len(paras)), key=lambda i: -sum(t in paras[i].lower() for t in terms))
    keep, used = set(), 0
    for i in scored:
        if used + len(paras[i]) > size:
            continue
        keep.add(i)
        used += len(paras[i]) + 1
    return "\n".join(paras[i] for i in sorted(keep))


async def guidance_sources(message: str, context: str = "") -> Tuple[List[dict], List[str]]:
    """(research items, keys that were wanted but could not be retrieved)."""
    keys = pick(f"{message}\n{context[-600:] if context else ''}")
    if not keys:
        return [], []
    try:
        pages = await asyncio.wait_for(asyncio.gather(*[get_page(k) for k in keys]), timeout=TIMEOUT)
    except asyncio.TimeoutError:
        pages = [None] * len(keys)
    items, failed = [], []
    for k, p in zip(keys, pages):
        if not p:
            failed.append(k)
            continue
        items.append({"title": f"{p['title']} — acas.org.uk (official guidance; wording retrieved {p['fetched_at']})",
                      "url": p["url"], "content": excerpt(p["text"], message), "acas_key": k})
    return items, failed


def named_urls(answer: str) -> List[str]:
    """Acas pages the answer relies on by name (kept in the source list even without a [n] marker)."""
    return [BASE + p[2] for p in PAGES if re.search(p[4], answer or "", re.I) and p[0] in ("code",)]


_NOT_SEEN = re.compile(r"\b(?:ha(?:ve|s)\s*n['’]?o?t|did\s*n['’]?o?t|could\s*n['’]?o?t|was\s*n['’]?o?t|not)\s+(?:been\s+)?"
                       r"(?:retriev|fetch|access|check|see|seen|consult|verif)\w*", re.I)


def disclose(answer: str, retrieved_keys: List[str], failed_keys: List[str]) -> Tuple[str, List[str]]:
    """Reconciles the answer with what was actually fetched from acas.org.uk."""
    notes, mentions_code = [], re.search(r"acas code|code of practice", answer or "", re.I)
    if mentions_code and "code" in retrieved_keys:
        parts = re.split(r"((?<=[.!?])\s+|\n)", answer)
        for i in range(0, len(parts), 2):
            if re.search(r"code", parts[i], re.I) and _NOT_SEEN.search(parts[i]):
                lead = re.match(r"^\s*(?:[-*•]\s+|\d+\.\s+)?", parts[i]).group(0)
                parts[i] = (f"{lead}The official Acas Code text was retrieved from acas.org.uk for this answer — see the "
                            "sources below and read the paragraph that applies to you.")
        answer = "".join(parts)
    elif mentions_code and ("code" in failed_keys or "code" not in retrieved_keys):
        notes.append("The official Acas Code of Practice could not be retrieved from acas.org.uk for this answer — points "
                     "about it come from Lex's built-in knowledge and have not been checked against the Code text. Read the "
                     f"Code at {BASE}{PAGES[0][2]} before relying on them.")
    return answer, notes
