"""Lex 2.0 Phase 1: official-source grounding and status checks (legislation.gov.uk, OGL v3).
No AI calls. Case-law lookups (Find Case Law) stay OFF unless CASELAW_VERIFY_ENABLED=1 (licence required)."""
import asyncio, logging, os, re, time
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
import httpx

logger = logging.getLogger(__name__)
LEG = "https://www.legislation.gov.uk"
TNA = "https://caselaw.nationalarchives.gov.uk"
UA = {"User-Agent": "AIAdvocate/1.0 (+https://aiadvocate.co.uk; support@aiadvocate.co.uk)"}
ACT_TTL, STATUS_TTL, FAIL_TTL = 7 * 86400, 6 * 3600, 300
MAX_REFS, TIMEOUT = 6, 6.0
EXTENT = {"england": "E", "wales": "W", "scotland": "S", "northern_ireland": "N"}
NATION_LABEL = {"england": "England", "wales": "Wales", "scotland": "Scotland", "northern_ireland": "Northern Ireland"}
OGL = "Contains public sector information licensed under the Open Government Licence v3.0."
BAD = {"not_found", "repealed", "partly_repealed", "not_in_force", "wrong_jurisdiction"}
_cache: Dict[str, Tuple[float, object]] = {}

_WORD = r"(?:[A-Z][A-Za-z'’\-]+|\([A-Z][A-Za-z ]+\))"
_ACT_RE = re.compile(rf"\b({_WORD}(?:\s+(?:{_WORD}|of|and|the|for|to|in|on|from|with))*\s+Act)\s+((?:18|19|20)\d{{2}})\b")
_SEC_RE = re.compile(r"\b(?i:sections?|ss?\.|s)\s?(\d{1,4}[A-Z]{0,2})\b")
_LEAD = {"Under", "The", "See", "Section", "Sections", "Part", "Schedule", "In", "By", "And", "Per", "S", "Ss", "Your",
         "This", "That", "Their", "Its", "Our", "If", "As", "Both", "Also"}
_SENT = re.compile(r"(?<=[.!?])\s+|\n")


def _get(key):
    hit = _cache.get(key)
    return hit[1] if hit and hit[0] > time.monotonic() else None


def _put(key, val, ttl):
    _cache[key] = (time.monotonic() + ttl, val)
    return val


async def _fetch(url: str) -> Tuple[int, str]:
    async with httpx.AsyncClient(timeout=4.0, headers=UA, follow_redirects=True) as c:
        r = await c.get(url)
        return r.status_code, (r.text if r.status_code == 200 else "")


def _norm_title(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "").replace("’", "'")).strip().lower()


def extract_refs(text: str) -> List[dict]:
    """Act + section references, paired within a sentence. Capped at MAX_REFS."""
    out, seen = [], set()
    for sent in _SENT.split(text or ""):
        acts = list(_ACT_RE.finditer(sent))
        if not acts:
            continue
        secs = list(_SEC_RE.finditer(sent))
        for a in acts:
            words = a.group(1).split()
            while len(words) > 2 and (words[0] in _LEAD or words[0].lower() in ("of", "and", "the")):
                words = words[1:]
            a_title, year = " ".join(words), a.group(2)
            mine = [s for s in secs if min(acts, key=lambda x: abs(x.start() - s.start())) is a]
            for sec in ([s.group(1) for s in mine] or [None]):
                key = (a_title.lower(), year, sec)
                if key not in seen:
                    seen.add(key)
                    out.append({"act": a_title, "year": year, "section": sec,
                                "label": f"{a_title} {year}" + (f", section {sec}" if sec else ""),
                                "anchor": a.group(0)})
    return out[:MAX_REFS]


async def resolve_act(title: str, year: str) -> Optional[dict]:
    """legislation.gov.uk id for an exact Act title + year. None if not found; raises on network failure."""
    key = f"act:{_norm_title(title)}:{year}"
    cached = _get(key)
    if cached is not None:
        return cached or None
    words = title.split()
    for i in range(len(words) - 1):
        cand = " ".join(words[i:])
        if i and not cand[0].isupper():
            continue
        code, body = await _fetch(f"{LEG}/primary/{year}/data.feed?title={quote(cand)}")
        if code != 200:
            raise RuntimeError(f"legislation feed {code}")
        for e in re.findall(r"<entry>(.*?)</entry>", body, re.S):
            t = re.search(r"<title>([^<]*)", e)
            i_d = re.search(r"<id>https?://www\.legislation\.gov\.uk/id/([^<]+)</id>", e)
            if t and i_d and _norm_title(t.group(1)) == _norm_title(f"{cand} {year}"):
                return _put(key, {"id": i_d.group(1), "title": re.sub(r"\s+", " ", t.group(1)).strip()}, ACT_TTL)
    _put(key, {}, ACT_TTL)
    return None


def _strip(xml: str) -> str:
    xml = re.sub(r"<(CommentaryRef|Citation)[^>]*/>", "", xml)
    return re.sub(r"\s+([,.;:)])", r"\1", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))).replace("( ", "(").strip()


def parse_section(xml: str, section: str) -> dict:
    """Extent, status and text of one section from legislation.gov.uk CLML (current revised version)."""
    idx = xml.find(f'id="section-{section}"')
    if idx < 0:
        return {"status": "not_found"}
    g0 = xml.rfind("<P1group", 0, idx)
    g0 = g0 if g0 >= 0 else idx
    g1 = xml.find("</P1group>", idx)
    seg = xml[g0:(g1 if g1 > 0 else idx + 20000)]
    head = seg[:seg.find(">") + 1]
    ext = re.search(r'RestrictExtent="([^"]+)"', head) or re.search(r'RestrictExtent="([^"]+)"', xml[xml.find("<Body"):idx])
    text = _strip(xml[idx - 4 if xml[idx - 4:idx].startswith("<") else idx:(g1 if g1 > 0 else idx + 8000)])
    text = re.sub(r'^id="section-[^"]+"[^>]*>\s*', "", text)
    detail = ""
    if 'Status="Prospective"' in head or 'Status="Prospective"' in seg[:600]:
        status = "not_in_force"
    elif re.fullmatch(r"[\d\w]{0,5}\s*(?:\.\s?){3,}|[\d\w]{0,5}\s*…", text.strip()) or len(re.sub(r"[.\s…]", "", text)) < 6:
        status = "repealed"
    elif "<Repeal" in seg:
        status = "partly_repealed"
    else:
        status = "in_force"
    if status in ("repealed", "partly_repealed"):
        ref = re.search(r'<Repeal[^>]*CommentaryRef="([^"]+)"', seg) or re.search(r'CommentaryRef Ref="([^"]+)"', seg)
        m = ref and re.search(rf'<Commentary id="{re.escape(ref.group(1))}"[^>]*>(.*?)</Commentary>', xml, re.S)
        detail = _strip(m.group(1))[:220] if m else ""
    pending = bool(re.search(rf'AffectedProvisions="[^"]*\bss?\. (?:[\w(), ]*\b)?{re.escape(section)}\b', xml))
    valid = re.search(r"<dct:valid>([^<]+)", xml)
    return {"status": status, "extent": ext.group(1) if ext else "", "text": text[:1200], "detail": detail,
            "pending_changes": pending, "version_date": valid.group(1) if valid else ""}


async def check_ref(ref: dict, nation: Optional[str]) -> dict:
    res = {**ref, "verdict": "lookup_failed", "url": "", "extent": "", "detail": ""}
    try:
        act = await resolve_act(ref["act"], ref["year"])
        if not act:
            return {**res, "verdict": "not_found"}
        res.update(url=f"{LEG}/{act['id']}", official_title=act["title"])
        if not ref["section"]:
            return {**res, "verdict": "act_exists"}
        key = f"sec:{act['id']}:{ref['section']}"
        info = _get(key)
        if info is None:
            code, body = await _fetch(f"{LEG}/{act['id']}/section/{ref['section']}/data.xml")
            if code == 404:
                info = _put(key, {"status": "not_found"}, STATUS_TTL)
            elif code != 200:
                raise RuntimeError(f"section {code}")
            else:
                info = _put(key, parse_section(body, ref["section"]), STATUS_TTL)
        res.update(url=f"{LEG}/{act['id']}/section/{ref['section']}", extent=info.get("extent", ""),
                   detail=info.get("detail", ""), text=info.get("text", ""), version_date=info.get("version_date", ""),
                   pending_changes=info.get("pending_changes", False))
        verdict, letter = info["status"], EXTENT.get(nation or "")
        extent = info.get("extent", "").replace("N.I.", "N").split("+")
        if verdict != "not_found" and letter and info.get("extent") and letter not in extent:
            verdict = "wrong_jurisdiction"
        elif verdict == "in_force" and info.get("pending_changes"):
            verdict = "changes_pending"
        return {**res, "verdict": verdict}
    except Exception as e:
        logger.info(f"legislation check failed for {ref.get('label')}: {e!r}")
        return res


async def check_refs(refs: List[dict], nation: Optional[str]) -> List[dict]:
    if not refs:
        return []
    try:
        return list(await asyncio.wait_for(asyncio.gather(*[check_ref(r, nation) for r in refs]), timeout=TIMEOUT))
    except asyncio.TimeoutError:
        return [{**r, "verdict": "lookup_failed", "url": ""} for r in refs]


def _note_line(r: dict, nation: Optional[str]) -> Optional[str]:
    lab, v = f"“{r['label']}”", r["verdict"]
    return {
        "not_found": f"{lab} could not be found on legislation.gov.uk — treat this reference as unverified.",
        "repealed": f"{lab} appears on legislation.gov.uk as repealed, so it may no longer apply"
                    + (f" ({r['detail']})" if r.get("detail") else "") + ". Check the current law before relying on it.",
        "partly_repealed": f"{lab} has been repealed or changed for some purposes or places"
                           + (f" ({r['detail']})" if r.get("detail") else "") + ". Check whether it still applies to your situation.",
        "not_in_force": f"{lab} is not yet in force according to legislation.gov.uk.",
        "wrong_jurisdiction": f"{lab} does not extend to {NATION_LABEL.get(nation, 'your nation')} "
                              f"(legislation.gov.uk extent: {r.get('extent')}).",
        "changes_pending": f"legislation.gov.uk lists changes to {lab} that are not yet shown in its text — check the latest position.",
        "lookup_failed": f"{lab} could not be checked against legislation.gov.uk just now — treat it as unverified.",
    }.get(v)


async def check_answer(text: str, nation: Optional[str], citations: List[dict], document: bool = False) -> Tuple[str, dict]:
    """Status-checks every Act/section Lex cites. Problems are qualified inline (chat) and explained in a note;
    in-force sections become 'status checked' citations. Never marks the *claim* as verified."""
    t0 = time.monotonic()
    refs = extract_refs(text)
    results = await check_refs(refs, nation)
    out, lines, next_n = text, [], max([int(c.get("n", 0)) for c in citations or []] + [0]) + 1
    for r in results:
        line = _note_line(r, nation)
        if line:
            lines.append(line)
            if not document and r["verdict"] in BAD and r["anchor"] in out:
                out = out.replace(r["anchor"], f"{r['anchor']} [⚠ see legislation check]", 1)
        if r["verdict"] in ("in_force", "changes_pending") and r.get("url") and \
                not any((c.get("url") or "").rstrip("/") == r["url"] for c in citations):
            citations.append({"n": next_n, "title": f"{r['label']} — legislation.gov.uk (status checked"
                              + (f", version {r['version_date']}" if r.get("version_date") else "") + ")",
                              "url": r["url"], "source": "legislation", "claim_check": "status_checked"})
            next_n += 1
    for c in await check_case_citations(out):
        if c["verdict"] in ("not_found", "lookup_failed"):
            lines.append(f"The case citation “{c['citation']}” could not be confirmed on Find Case Law — treat it as unverified.")
            if not document and c["citation"] in out:
                out = out.replace(c["citation"], f"{c['citation']} [⚠ unverified]", 1)
    if lines:
        head = "Notes for you — not part of the letter" if document else "Legislation check (legislation.gov.uk)"
        block = f"\n\n**{head}:**\n" + "\n".join(f"- {ln}" for ln in lines) + f"\n_{OGL}_"
        if any(r["verdict"] in BAD | {"lookup_failed"} for r in results) or "Find Case Law" in block:
            out = re.sub(r"\[CONFIDENCE:\s*HIGH\]", "[CONFIDENCE: MEDIUM]", out)
        if document:
            out = out.rstrip() + "\n\n-----" + block
        else:
            import lex_safety
            out = lex_safety.insert_before_tail(out, block.strip())
    rep = {"refs": len(refs), "verdicts": [r["verdict"] for r in results], "ms": int((time.monotonic() - t0) * 1000)}
    return out, rep


async def issue_notes(text: str, nation: Optional[str]) -> List[str]:
    """Plain-English problems with cited legislation, for structured (JSON) outputs."""
    return [ln for ln in (_note_line(r, nation) for r in await check_refs(extract_refs(text), nation)) if ln]


async def grounding_sources(text: str, nation: Optional[str], max_sections: int = 2) -> List[dict]:
    """Actual section text for Acts/sections the user names — added to research as official sources."""
    refs = [r for r in extract_refs(text) if r["section"]][:max_sections]
    items = []
    for r in await check_refs(refs, nation):
        if r.get("text") and r["verdict"] not in ("not_found", "lookup_failed"):
            status = {"in_force": "in force", "changes_pending": "in force — changes pending", "repealed": "REPEALED",
                      "partly_repealed": "repealed/changed for some purposes", "not_in_force": "NOT YET IN FORCE",
                      "wrong_jurisdiction": f"does NOT extend to {NATION_LABEL.get(nation, 'this nation')}"}.get(r["verdict"], "")
            items.append({"title": f"{r['label']} (legislation.gov.uk — status: {status}; extent {r.get('extent')})",
                          "url": r["url"], "content": f"{r.get('detail', '')} {r['text']}".strip()})
    return items


# ---------------- Case law (Find Case Law) — OFF until licence confirmed ----------------
_NEUTRAL = re.compile(r"\[((?:19|20)\d{2})\]\s+(UKSC|UKPC|UKHL|EWCA\s+(?:Civ|Crim)|EWHC|EWFC|UKUT|UKFTT|EAT)\s+(\d{1,5})"
                      r"(?:\s+\((\w+)\))?")


def caselaw_enabled() -> bool:
    return os.environ.get("CASELAW_VERIFY_ENABLED") == "1"


def neutral_to_url(m: re.Match) -> Optional[str]:
    year, court, num, div = m.group(1), m.group(2).lower().replace("  ", " "), m.group(3), (m.group(4) or "").lower()
    path = {"uksc": "uksc", "ukpc": "ukpc", "ewfc": "ewfc", "eat": "eat", "ewca civ": "ewca/civ", "ewca crim": "ewca/crim"}.get(
        re.sub(r"\s+", " ", court))
    if court == "ewhc" and div:
        path = f"ewhc/{div}"
    return f"{TNA}/{path}/{year}/{num}" if path else None


async def check_case_citations(text: str) -> List[dict]:
    """Existence check of neutral citations on Find Case Law. Returns [] when disabled."""
    if not caselaw_enabled():
        return []
    out = []
    for m in list(_NEUTRAL.finditer(text or ""))[:4]:
        url = neutral_to_url(m)
        if not url:
            out.append({"citation": m.group(0), "verdict": "unsupported_court"})
            continue
        try:
            code, _ = await _fetch(url + "/data.xml")
            out.append({"citation": m.group(0), "url": url, "verdict": "found" if code == 200 else "not_found"})
        except Exception:
            out.append({"citation": m.group(0), "url": url, "verdict": "lookup_failed"})
    return out
