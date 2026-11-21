"""UK immigration scope limit: AI Advocate is not authorised by the Immigration Advice Authority (IAA), so customer
routes give general information only — no individual eligibility findings, strategy, refusal/appeal advice or
representations (Immigration and Asylum Act 1999, Part V). Deterministic: prompt rule + answer check + route refusals."""
import re
from typing import Optional, Tuple

_I = re.I
_IMM = re.compile(
    r"\b(visas?|visto|visado|wiz[aęy]|leave to remain|indefinite leave|ilr|brp|biometric residence|e-?visa|"
    r"the home office|home office (?:letter|decision|refus\w*|interview|caseworker|application)|ukvi|deport\w*|asylum|"
    r"asile|asilo|azyl\w*|refugee status|immigration|immigrant|euss|(?:pre-)?settled status|overstay\w*|naturali[sz]\w*|"
    r"british citizenship|citizenship application|spouse visa|partner visa|family visa|appendix fm|skilled worker|"
    r"graduate route|certificate of sponsorship|right to remain|removal (?:centre|directions)|detention centre|"
    r"immigration bail|section 3c|aufenthalt\w*|titre de séjour|permesso di soggiorno|karta pobytu|zezwoleni\w* na pobyt)\b",
    _I)
_UK_ONLY = re.compile(r"\b(home office|ukvi|ilr|indefinite leave|brp|euss|settled status|appendix fm|section 3c|"
                      r"british citizenship|leave to remain|\buk\b|united kingdom|britain|england|scotland|wales|"
                      r"northern ireland)\b", _I)

BLOCKED_TEMPLATES = {"immigration_letter", "asylum_statement"}
BLOCKED_PRACTICE = {"immigration"}

ADVISERS = ("Find a regulated immigration adviser (Immigration Advice Authority register): "
            "https://www.gov.uk/find-an-immigration-adviser · Immigration solicitors (Law Society): "
            "https://solicitors.lawsociety.org.uk · Legal aid (often available for asylum and detention): "
            "https://www.gov.uk/check-legal-aid · Official rules and guidance: https://www.gov.uk/browse/visas-immigration")
REFUSAL = ("UK immigration: AI Advocate can only give general information about UK immigration rules. It cannot assess "
           "your own case, prepare Home Office or tribunal documents, or advise on a refusal or appeal — only an adviser "
           "regulated by the Immigration Advice Authority, a solicitor or a barrister can. If a decision letter gives you a "
           "deadline, contact one straight away. " + ADVISERS)
NOTE = ("**UK immigration — general information only:** Lex can explain the official rules, but it cannot tell you "
        "whether you qualify, which route or strategy to choose, or whether or how to challenge a refusal, and it cannot "
        "prepare applications or representations for you. Only an adviser regulated by the Immigration Advice Authority "
        "(IAA), a solicitor or a barrister can advise on your own case. If a Home Office decision gives you a deadline, "
        "contact one straight away.\n" + ADVISERS.replace(" · ", "\n- ").replace("Find a", "- Find a", 1))

PROMPT = (
    "\n\nUK IMMIGRATION — GENERAL INFORMATION ONLY (legal requirement: AI Advocate is not authorised by the Immigration "
    "Advice Authority). You MAY explain in general terms what the Immigration Rules and official GOV.UK guidance say, "
    "how routes, requirements, fees and processes generally work, what a type of document or decision generally means, "
    "and where to find official guidance. You must NOT: say whether this customer qualifies, is eligible, or is likely to "
    "be granted or refused; recommend which visa, route or application they should make or when; advise whether or how "
    "to challenge a refusal (appeal, administrative review, judicial review, fresh claim) or what to argue; draft, check "
    "or improve applications, personal statements, cover or representations letters; or act for them. Phrase rules "
    "generally ('applicants usually need…'), never as a conclusion about this person. If they ask for any of that, say "
    "plainly that you can only give general information and that a regulated immigration adviser (IAA), solicitor or "
    "barrister must advise on their case — the app adds the official links, so do not write any adviser website or URL yourself. This rule OVERRIDES any HIGH-STAKES answer structure: "
    "describe the general legal position (not 'your position'), do not ask for facts to assess their case, and limit "
    "next steps to reading the decision letter's stated deadline, official guidance and contacting a regulated adviser "
    "urgently.")
SHORT_RULE = ("\n\nUK IMMIGRATION: give general information only — never assess a customer's own eligibility or chances, "
              "recommend a visa route or strategy, advise on a refusal or appeal, or draft Home Office or tribunal "
              "documents; refer them to an IAA-regulated adviser or solicitor.")

_PERSONAL = [re.compile(p, _I) for p in (
    r"\byou(?:'d| would| will|'ll| should| do| may| might| could| probably| likely| definitely| certainly| clearly)*\s+"
    r"(?:not\s+)?(?:qualify|be eligible|meet (?:the|all|these|those|its) (?:requirements|criteria|conditions)|"
    r"satisfy (?:the|all|these) (?:requirements|criteria)|be granted|be refused|get (?:ilr|the visa|settlement|leave))\b",
    r"\byou(?:'re| are)\s+(?:not\s+)?(?:likely\s+|probably\s+|clearly\s+|definitely\s+)?(?:eligible|entitled to "
    r"(?:apply|ilr|settle\w*|a visa|remain))\b",
    r"\byou (?:do not|don't|won't|will not|cannot|can't) (?:qualify|meet the requirements|be eligible)\b",
    r"\b(?:i|we|lex) (?:would |strongly )?(?:recommend|suggest|advise)(?: that)? you(?! (?:to )?(?:speak|talk|contact|get|"
    r"seek (?:advice|help)|see|consult|check|use|find|call|read|look|act|keep))\b",
    r"\byou should (?:apply|appeal|re-?apply|submit|request|switch|withdraw|lodge|make an? (?:application|appeal|claim)|"
    r"seek (?:an? )?(?:administrative|judicial) review|argue|claim asylum|challenge)\b",
    r"\byour (?:best|strongest|safest|most realistic) (?:option|route|strategy|chance|bet|approach)\b",
    r"\b(?:your|the) (?:application|appeal|claim|case) (?:is (?:likely|unlikely) to|will|would|should) (?:succeed|be "
    r"(?:granted|refused|successful|allowed|dismissed)|fail)\b",
    r"\byou have (?:a |an )?(?:very )?(?:strong|good|weak|reasonable|excellent|poor|realistic) (?:case|chance|claim|grounds|prospects)\b",
)]
_SENT = re.compile(r"(?<=[.!?])\s+")


def applies(text: str, country: Optional[str], category: Optional[str] = None) -> bool:
    t = text or ""
    if not (category == "immigration" or _IMM.search(t)):
        return False
    return (country or "GB").strip().upper() in ("GB", "UK", "") or bool(_UK_ONLY.search(t))


def enforce(answer: str) -> Tuple[str, int]:
    """Removes sentences that assess the customer's own immigration position, then adds the signposting note."""
    lines, n = [], 0
    for line in (answer or "").split("\n"):
        keep = []
        for s in _SENT.split(line):
            if any(rx.search(s) for rx in _PERSONAL):
                n += 1
            else:
                keep.append(s)
        new = " ".join(keep)
        if keep or not line.strip():
            lines.append(new if keep else line)
        elif re.match(r"\s*(?:[-*•]|\d+[.)])\s*", line) is None:
            lines.append("")
    out = "\n".join(lines)
    if "general information only" not in out:
        import lex_safety
        out = lex_safety.insert_before_tail(out, NOTE)
    return out, n
