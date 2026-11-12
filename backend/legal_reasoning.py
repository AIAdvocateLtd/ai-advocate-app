"""Lex 2.0 Phase 2B: proportionate legal reasoning, evidence analysis and claim-by-claim label verification.
Deterministic only — reuses the existing model call and the existing legislation / citation checks."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import content_guard
import legal_sources

_I = re.I
_DISPUTE = re.compile(r"\b(dispute|claim|sue|suing|tribunal|court|refus\w*|dismiss\w*|sacked|evict\w*|deposit|owe[sd]?|unpaid|"
                      r"breach\w*|complain\w*|landlord|employer|council|insurer|accus\w*|negligen\w*|withh[eo]ld\w*|"
                      r"won'?t|threat\w*|deny|denies|denied|disagree\w*|blam\w*|fault|compensation|charged me|"
                      r"grievance|discriminat\w*|harass\w*|injur\w*|divorc\w*|custody|arrest\w*|visa)\b", _I)
_FACT = re.compile(r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*|\d{1,2}/\d{1,2}/\d{2,4}|"
                   r"£\s?\d[\d,]*|\d+\s+(?:days|weeks|months|years)|(?:he|she|they|manager|landlord|employer) "
                   r"(?:said|told|emailed|texted|wrote|refused|claimed)|text message|email(?:ed)?|letter|witness\w*|"
                   r"photos?|receipt|contract|recording)\b", _I)


def depth(message: str, context: str = "", hs: Optional[dict] = None, has_evidence: bool = False) -> str:
    """simple | moderate | complex — decides how much structure the answer needs."""
    msg = message or ""
    words = len(msg.split())
    disputes = len({m.group(0).lower() for m in _DISPUTE.finditer(msg)})
    facts = len(_FACT.findall(f"{context}\n{msg}"))
    high = bool(hs) and hs.get("level") in ("emergency", "urgent", "high")
    if has_evidence or (disputes and (words >= 90 or facts >= 4)) or (disputes and facts >= 2 and words >= 35) or \
            (high and words >= 35 and (disputes or facts)):
        return "complex"
    if high or disputes or words >= 30 or facts >= 2:
        return "moderate"
    return "simple"


LABEL_RULES = (
    "Start each key legal point with ONE label: 'Current law (checked)' — only when that exact Act/section is in the "
    "retrieved legislation.gov.uk records and cited [n]; 'Official guidance' — only with a citation [n] to retrieved "
    "official guidance; 'Case law (checked)' — only for a case in the retrieved records; 'Your facts'; 'Our reading' "
    "(interpretation); 'Not confirmed'. The app re-checks every label against its records claim by claim and downgrades "
    "any it cannot match. When you rely on statutory wording, quote the exact words from the retrieved record in "
    "quotation marks; your explanation of what it means stays your interpretation. Never invent Acts, sections, cases, quotations or citations, and never quote statutory wording "
    "(in any language) unless it appears in the retrieved records."
)
_SIMPLE = ("\n\nRESPONSE DEPTH: simple question — answer directly and concisely (a few short paragraphs or bullets). No "
           "report headings. Add a next step only if genuinely useful.")
_MODERATE = ("\n\nRESPONSE DEPTH: moderate — proportionately cover: the law that applies (with its source), how it applies "
             "to the customer's facts, what is uncertain or missing, and practical next steps. ") + LABEL_RULES
_COMPLEX = (
    "\n\nRESPONSE DEPTH: complex dispute — give a structured but readable analysis (show conclusions and the factors "
    "behind them, not your private reasoning). Cover, under short headings, only what is relevant:\n"
    "1. Issues and jurisdiction — the legal questions and which law applies (England & Wales, Scotland, Northern Ireland "
    "or another country). If the law of that place can't be verified here, say so — never apply UK law by default.\n"
    "2. Legal tests — the conditions that must be met, with their source.\n"
    "3. Applying the tests to their facts — distinguish what the law allows from what their evidence can actually prove.\n"
    "4. Their strongest arguments, and the other side's likely arguments and defences — do not simply agree with the "
    "customer; separate agreed facts from disputed ones; never present the other person's motives or unstated facts as "
    "established.\n"
    "5. Evidence — what supports each side, what is missing, and what would be needed.\n"
    "6. Risks and uncertainty — realistic possible outcomes in words; NEVER give percentage chances of success.\n"
    "7. Action plan, most urgent first: immediate steps; evidence to preserve; facts to clarify; official bodies or "
    "procedures; deadlines to verify (never invent dates); informal resolution; formal complaint or legal routes; when a "
    "solicitor or regulated adviser is advisable. Lex cannot itself contact anyone, submit forms or start proceedings.\n"
    "You are an AI legal information assistant, not a solicitor; do not guarantee outcomes. "
) + LABEL_RULES
_EVIDENCE = (
    "\n\nEVIDENCE ANALYSIS (attached documents / case file): work only from the material actually supplied. Where relevant: "
    "identify each document's type and apparent date; key factual assertions; a short chronological timeline; "
    "contradictions between documents or with the customer's account; documents that seem to be missing; firsthand "
    "evidence vs hearsay vs allegation; possible admissions or inconsistencies; how each item connects to the legal "
    "issues; and evidential limits. Do not assume a document is authentic or accurate because it was uploaded, and never "
    "invent documents, conversations, witnesses or quotations."
)


def prompt_block(level: str, has_evidence: bool, high_stakes: bool) -> str:
    block = {"simple": _SIMPLE, "moderate": _MODERATE, "complex": _COMPLEX}.get(level, _SIMPLE)
    if high_stakes and level != "simple":
        block = block.replace(LABEL_RULES, "Use the source labels from the HIGH-STAKES framework; the app re-checks "
                                           "every label claim by claim.")
    return block + (_EVIDENCE if has_evidence else "")


# ---------------------------------------------------------------- evidence helper (deterministic)
_DATE_LINE = re.compile(r"[^\n.]{0,80}\b(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:january|february|march|april|may|june|july|august|"
                        r"september|october|november|december)\s+\d{4}|\d{1,2}/\d{1,2}/\d{4})\b[^\n.]{0,80}", _I)


def dated_lines(text: str, limit: int = 12) -> List[str]:
    """Lines of an attached document that contain a date — a timeline aid, quoted verbatim, never interpreted."""
    out = []
    for m in _DATE_LINE.finditer(text or ""):
        s = " ".join(m.group(0).split())
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- claim-by-claim verification
_LABELS = [
    ("law", re.compile(r"current law \(checked\)|verified (?:current )?(?:law|legislation)", _I), "Current law (not checked)"),
    ("case", re.compile(r"case law \(checked\)|verified case law", _I), "Case law (not confirmed)"),
    ("guidance", re.compile(r"(?<!\()official guidance(?! check)(?! \(not confirmed\))", _I), "Official guidance (not confirmed)"),
]
_CITE = re.compile(r"\[(\d{1,2})\]")
_PERCENT = re.compile(r"\b(?:an?\s+)?(?:about\s+|around\s+|roughly\s+)?\d{1,3}\s?(?:%|per ?cent)\s+(?:chance|likelihood|"
                      r"probability|prospects?)(?:\s+of\s+(?:success|winning|succeeding))?", _I)
_SOLICITOR = re.compile(r"\b(?:as your (?:solicitor|lawyer|barrister)|i am (?:a|your) (?:qualified )?(?:solicitor|lawyer|"
                        r"barrister))\b", _I)


def _units(text: str) -> List[str]:
    return [u for u in re.split(r"(?<=\n)", text or "")]


def _key(r: dict) -> tuple:
    return ((r.get("act") or "").lower(), str(r.get("year") or ""), r.get("section"))


STATUS_ONLY = "Legislation located (in force) — interpretation not independently verified"
TEXT_LOCATED = "Legislation located (provision text retrieved) — interpretation not independently verified"
QUOTE_CHECKED = "Current law (quoted wording checked against the Act)"
_QUOTE = re.compile(r"[\"“]([^\"”]{25,400})[\"”]")
_QUALIFIER = re.compile(r"\b\d+|\b(one|two|three|four|five|six|seven|eight|nine|ten|twelve)\b|\b(unless|except|provided that|"
                        r"only if|within|before|after|deadline|time limit|qualifying|months?|years?|weeks?|days?)\b", _I)


def _norm(t: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (t or "").lower()).split())


def _quote_verified(unit: str, content: str) -> bool:
    """Substantive check (narrow): the claim quotes ≥25 chars that appear word-for-word in the retrieved provision, and
    the rest of the claim adds no periods, numbers, exceptions or deadlines of its own."""
    quotes = _QUOTE.findall(unit)
    if not quotes or not content:
        return False
    body = _norm(content)
    if not all(_norm(q) in body for q in quotes):
        return False
    rest = _QUOTE.sub(" ", re.sub(r"\*\*[^*]+\*\*|\[\d+\]|\b(?:section|s\.)\s*\d+\w*|\b(?:18|19|20)\d\d\b", " ", unit, flags=_I))
    return not _QUALIFIER.search(rest)


def _law_verified(unit: str, leg_results: Dict[tuple, dict], by_n: Dict[int, dict], src_by_url: Dict[str, str]) -> Tuple[str, str]:
    """Never 'checked' for naming an Act/section. quoted = exact quoted wording found in this claim's own cited provision;
    text_located = in force + its cited provision text retrieved; status_only = in force only; unverified otherwise."""
    refs = legal_sources.extract_refs(unit)
    if not refs:
        return "unverified", "no Act/section named in this claim"
    own_urls = set()
    for r in refs:
        res = leg_results.get(_key(r)) or leg_results.get(_key({**r, "section": None})) or {}
        if res.get("verdict") not in ("in_force", "changes_pending"):
            return "unverified", f"{r['label']}: {res.get('verdict') or 'not checked'}"
        own_urls.add((res.get("url") or "").rstrip("/").lower())
    located = False
    for n in map(int, _CITE.findall(unit)):
        c = by_n.get(n) or {}
        url = (c.get("url") or "").rstrip("/")
        content = src_by_url.get(url, "")
        if content and url.lower() in own_urls:  # the citation is THIS claim's own provision, not another source
            if _quote_verified(unit, content):
                return "verified", "quoted wording matches the cited provision text"
            located = True
    if located:
        return "text_located", "in force; cited provision text retrieved; interpretation not verified"
    return "status_only", "in force here, but the cited wording was not retrieved"


def _guidance_verified(unit: str, by_n: Dict[int, dict], src_by_url: Dict[str, str]) -> bool:
    import lex_safety
    for n in map(int, _CITE.findall(unit)):
        c = by_n.get(n) or {}
        url = (c.get("url") or "").rstrip("/")
        if c.get("source") in ("official", "guidance", "legislation") and content_guard.official_url(url):
            content = src_by_url.get(url, "")
            if not content or lex_safety._guidance_supported(unit, content.lower()):
                return True
    return False


def verify_claims(text: str, leg: dict, citations: List[dict], sources: List[dict]) -> Tuple[str, dict]:
    """Each labelled claim is checked on its own: a label is kept only when THAT claim's own Act/section or citation was
    verified — an unrelated check elsewhere in the answer never verifies it. Also removes percentage odds."""
    leg_results = {_key(r): r for r in (leg or {}).get("results", [])}
    found_cases = {c.get("citation") for c in (leg or {}).get("cases", []) if c.get("verdict") == "found"}
    by_n = {int(c["n"]): c for c in citations or [] if str(c.get("n", "")).isdigit()}
    src_by_url = {(s.get("url") or "").rstrip("/"): (s.get("content") or "") for s in sources or []}
    ledger, out = [], []
    for unit in _units(text):
        for kind, rx, downgrade in _LABELS:
            if not rx.search(unit):
                continue
            if kind == "law":
                state, why = _law_verified(unit, leg_results, by_n, src_by_url)
                ok = state == "verified"
                if state != "unverified":
                    ledger.append({"label": kind, "verified": ok, "status_only": not ok, "state": state, "why": why})
                    out.append(rx.sub({"verified": QUOTE_CHECKED, "text_located": TEXT_LOCATED}.get(state, STATUS_ONLY), unit))
                    break
            elif kind == "case":
                ok = any(c and c in unit for c in found_cases)
                why = "found on Find Case Law" if ok else "case not verified"
            else:
                ok = _guidance_verified(unit, by_n, src_by_url)
                why = "cited official source" if ok else "no supporting official citation"
            ledger.append({"label": kind, "verified": ok, "why": why})
            if not ok:
                unit = rx.sub(downgrade, unit)
        else:
            out.append(unit)
    result = "".join(out)
    result, pct = _PERCENT.subn("a realistic chance (no reliable percentage can be given)", result)
    result, sol = _SOLICITOR.subn("as an AI legal information assistant (not a solicitor)", result)
    rep = {"labelled": len(ledger), "verified": sum(1 for c in ledger if c["verified"]),
           "located_only": sum(1 for c in ledger if c.get("status_only")),
           "text_located": sum(1 for c in ledger if c.get("state") == "text_located"),
           "downgraded": sum(1 for c in ledger if not c["verified"] and not c.get("status_only")), "claims": ledger[:20],
           "percentages_removed": pct, "solicitor_claims_fixed": sol}
    return result, rep
