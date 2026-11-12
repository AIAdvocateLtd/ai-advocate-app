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
MAX_REFS, TIMEOUT, TEXT_CAP = 6, 6.0, 4000
EXTENT = {"england": "E", "wales": "W", "scotland": "S", "northern_ireland": "N"}
NATION_LABEL = {"england": "England", "wales": "Wales", "scotland": "Scotland", "northern_ireland": "Northern Ireland"}
OGL = "Contains public sector information licensed under the Open Government Licence v3.0."
BAD = {"not_found", "repealed", "partly_repealed", "not_in_force", "wrong_jurisdiction"}
_cache: Dict[str, Tuple[float, object]] = {}

_WORD = r"(?:[A-Z][A-Za-z'’\-]+|\([A-Z][A-Za-z ]+\))"
_ACT_RE = re.compile(rf"\b({_WORD}(?:\s+(?:{_WORD}|of|and|the|for|to|in|on|from|with))*\s+Act)\s+((?:18|19|20)\d{{2}})\b")
_SEC_RE = re.compile(r"\b(?i:sections?|ss?\.|s)\s?(\d{1,4}[A-Z]{0,2}(?:(?:\s*,\s*|\s+(?i:and|or|&)\s+)\d{1,4}[A-Z]{0,2}\b"
                     r"(?!\s*(?i:months?|days?|weeks?|years?|%)))*)\b")
_SEC_NUM = re.compile(r"\d{1,4}[A-Z]{0,2}")
NAMES = {"E": "England", "W": "Wales", "S": "Scotland", "N": "Northern Ireland"}
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
            for sec in ([n for s in mine for n in _SEC_NUM.findall(s.group(1))] or [None]):
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


def _ancestor_extent(xml: str, idx: int) -> str:
    """Innermost still-open element (Chapter/Part/Body…) carrying RestrictExtent — never a sibling or the whole Act."""
    end, ext = xml.find(">", idx) + 1, ""
    for m in re.finditer(r'<(\w+)\b[^>]*RestrictExtent="([^"]+)"', xml[:end]):
        if f"</{m.group(1)}>" not in xml[m.end():end]:
            ext = m.group(2)
    return ext


def extent_words(ext: str) -> str:
    """'E+W+S' -> 'England, Wales and Scotland (not Northern Ireland)'."""
    got = [k for k in "EWSN" if k in (ext or "").replace("N.I.", "N").split("+")]
    if not got:
        return ""
    names = [NAMES[k] for k in got]
    s = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    missing = [NAMES[k] for k in "EWSN" if k not in got]
    return s + (f" (not {' or '.join(missing)})" if missing else " (all four UK nations)")


_STATUS_WORDS = {"in_force": "in force", "changes_pending": "in force — changes pending", "repealed": "repealed",
                 "partly_repealed": "repealed/changed for some purposes", "not_in_force": "not yet in force",
                 "wrong_jurisdiction": "does not extend to the nation in question"}
_NOT_RETRIEVED = re.compile(r"\b(?:(?:was|were|is|has|have)(?:\s*n['’]t|\s+not)\s+(?:been\s+)?(?:retrieved|included|available|provided|"
                            r"fetched|checked|among)|(?:could|can|did)(?:\s*n['’]t|\s*not)\s+(?:be\s+)?(?:retriev|fetch|access|check|"
                            r"verif|see|find|locat)\w*|unable to (?:retriev|fetch|access|check|verif|find)\w*|not (?:in|among|part of) "
                            r"(?:the )?(?:retrieved |research |live )?(?:sources|research|material))", re.I)
_PARTIAL = re.compile(r"\b(?:incomplete|partial(?:ly)?|truncated|cut off|only (?:the )?(?:first|part|opening)|my own "
                      r"(?:knowledge|understanding)|from memory|general knowledge|training)\b", re.I)
_UK_WIDE = re.compile(r"\b(?:extends?|extending|extent|appl(?:y|ies|ying))\b[^.\n]{0,70}\b(?:Northern Ireland|whole (?:of the )?(?:UK|United "
                      r"Kingdom)|all (?:four|UK) nations|throughout the UK|across the (?:whole )?UK)|\bUK[- ]wide\b", re.I)
_SPLIT = re.compile(r"((?<=[.!?])\s+|\n)")


def _mentions_section(sent: str, sec: str) -> bool:
    return bool(re.search(r"\b(?:sections?|ss?\.?)\s?", sent, re.I) and re.search(rf"(?<![\w.]){re.escape(sec)}\b", sent))


def reconcile(text: str, results: List[dict], document: bool = False) -> Tuple[str, List[str]]:
    """Aligns the drafted answer with the completed checks: no 'not retrieved' claims for sections that were
    retrieved, and no UK-wide / Northern Ireland extent claims the official record contradicts."""
    lines, parts = [], _SPLIT.split(text or "")
    for r in results:
        sec, v = r.get("section"), r.get("verdict")
        if not sec or v in ("not_found", "lookup_failed"):
            continue
        letters = (r.get("extent") or "").replace("N.I.", "N").split("+")
        flagged = False
        for i, sent in enumerate(parts):
            if i % 2 or not _mentions_section(sent, sec) or r["act"].split()[0].lower() not in (text or "").lower():
                continue
            if (_NOT_RETRIEVED.search(sent) or (_PARTIAL.search(sent) and not r.get("truncated"))) and not document:
                lead = re.match(r"^\s*(?:[-*•]\s+|\d+\.\s+)?", sent).group(0)
                parts[i] = (f"{lead}{r['label']} was checked on legislation.gov.uk once this answer was drafted (status: "
                            f"{_STATUS_WORDS.get(v, v)}) and its full wording is linked below. That check confirms the "
                            "provision exists and is in force — it does not confirm this answer's interpretation, so read "
                            "the wording before relying on it.")
            elif r.get("extent") and "N" not in letters and _UK_WIDE.search(sent) and not flagged:
                flagged = True
                lines.append(f"legislation.gov.uk records the territorial extent of “{r['label']}” as {extent_words(r['extent'])}, "
                             "so it does not extend to Northern Ireland. Extent shows where a provision is law; whether it "
                             "applies to your situation is a separate question.")
                if not document:
                    parts[i] = sent.rstrip() + " [⚠ see legislation check]"
    return "".join(parts), lines


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
    ext = re.search(r'RestrictExtent="([^"]+)"', head)
    ext = ext.group(1) if ext else _ancestor_extent(xml, idx)
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
    return {"status": status, "extent": ext, "text": text[:TEXT_CAP], "truncated": len(text) > TEXT_CAP, "detail": detail,
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
                   pending_changes=info.get("pending_changes", False), truncated=info.get("truncated", False))
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
    out, lines = reconcile(text, results, document)
    next_n = max([int(c.get("n", 0)) for c in citations or []] + [0]) + 1
    for r in results:
        line = _note_line(r, nation)
        if line:
            lines.append(line)
            if not document and r["verdict"] in BAD and r["anchor"] in out:
                out = out.replace(r["anchor"], f"{r['anchor']} [⚠ see legislation check]", 1)
        if r["verdict"] in ("in_force", "changes_pending") and r.get("url") and \
                not any((c.get("url") or "").rstrip("/") == r["url"] for c in citations):
            citations.append({"n": next_n, "title": f"{r['label']} — legislation.gov.uk (status checked only: exists and in force"
                              + (f", version {r['version_date']}" if r.get("version_date") else "")
                              + (f"; extent: {extent_words(r['extent'])}" if extent_words(r.get("extent")) else "")
                              + " — does not confirm Lex's interpretation)",
                              "url": r["url"], "source": "legislation", "claim_check": "status_checked"})
            next_n += 1
    case_results = await check_case_citations(out)
    for c in case_results:
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
    rep = {"refs": len(refs), "verdicts": [r["verdict"] for r in results], "urls": [r["url"] for r in results if r.get("url")],
           "results": [{"act": r.get("act"), "year": r.get("year"), "section": r.get("section"), "verdict": r["verdict"]}
                       for r in results], "cases": case_results, "ms": int((time.monotonic() - t0) * 1000)}
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
            wording = "wording retrieved: first part only" if r.get("truncated") else "full wording retrieved"
            items.append({"title": f"{r['label']} (legislation.gov.uk — status: {status}; {wording}; territorial extent: "
                                   f"{extent_words(r.get('extent')) or 'not stated'})",
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
