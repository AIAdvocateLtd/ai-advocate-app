"""Lex 2.0: finds the relevant UK law from a plain-English question (no Act named) via a checked topic map and the
official legislation.gov.uk search, then reads the provisions (wording, status, extent, pending changes). No AI calls."""
import asyncio
import logging
import re
from typing import List, Optional
from urllib.parse import quote

import legal_sources as L

logger = logging.getLogger(__name__)
EW, S, NI = ("england", "wales"), ("scotland",), ("northern_ireland",)
GB = EW + S
ALL = GB + NI
MAX_PROVISIONS, SEARCH_RESULTS, TIMEOUT = 4, 3, 7.0


def P(path, label, nations):
    return {"path": path, "label": label, "nations": nations}


# Each topic: trigger pattern + provisions in priority order. Every path is checked live by tests/test_legal_research.py.
TOPICS = [
    ("unfair_dismissal", r"dismiss|sacked|fired\b|let go|terminat\w* (?:my|me|from)|lost my job|disciplinary", [
        P("ukpga/1996/18/section/94", "Employment Rights Act 1996 s.94 (right not to be unfairly dismissed)", GB),
        P("ukpga/1996/18/section/98", "Employment Rights Act 1996 s.98 (fairness of dismissal)", GB),
        P("ukpga/1996/18/section/108", "Employment Rights Act 1996 s.108 (qualifying period)", GB),
        P("ukpga/1996/18/section/111", "Employment Rights Act 1996 s.111 (time limit for claims)", GB),
        P("nisi/1996/1919/article/126", "Employment Rights (Northern Ireland) Order 1996 art.126", NI),
        P("nisi/1996/1919/article/130", "Employment Rights (Northern Ireland) Order 1996 art.130 (fairness)", NI),
        P("nisi/1996/1919/article/145", "Employment Rights (Northern Ireland) Order 1996 art.145 (time limit)", NI)]),
    ("redundancy", r"redundan", [
        P("ukpga/1996/18/section/139", "Employment Rights Act 1996 s.139 (meaning of redundancy)", GB),
        P("ukpga/1996/18/section/135", "Employment Rights Act 1996 s.135 (right to redundancy pay)", GB),
        P("ukpga/1996/18/section/162", "Employment Rights Act 1996 s.162 (amount of redundancy pay)", GB)]),
    ("discrimination", r"discriminat|harass|racis|sexis|disabilit|pregnan|maternity|religio|sexual orientation|equal pay", [
        P("ukpga/2010/15/section/13", "Equality Act 2010 s.13 (direct discrimination)", GB),
        P("ukpga/2010/15/section/26", "Equality Act 2010 s.26 (harassment)", GB),
        P("ukpga/2010/15/section/39", "Equality Act 2010 s.39 (employees and applicants)", GB),
        P("ukpga/2010/15/section/123", "Equality Act 2010 s.123 (time limits)", GB)]),
    ("wages", r"unpaid wage|not (?:been )?paid|wages|deduct\w* from my pay|holiday pay|owed (?:me )?(?:money|pay)|minimum wage", [
        P("ukpga/1996/18/section/13", "Employment Rights Act 1996 s.13 (unauthorised deductions)", GB),
        P("ukpga/1996/18/section/23", "Employment Rights Act 1996 s.23 (complaints to tribunal)", GB),
        P("ukpga/1998/39/section/1", "National Minimum Wage Act 1998 s.1", ALL),
        P("uksi/1998/1833/regulation/13", "Working Time Regulations 1998 reg.13 (annual leave)", GB)]),
    ("notice_period", r"notice period|how much notice", [
        P("ukpga/1996/18/section/86", "Employment Rights Act 1996 s.86 (minimum notice)", GB)]),
    ("eviction", r"evict|section 21|section 8\b|possession|notice to (?:quit|leave)|(?:have|need|told|asked) to (?:move out|leave the (?:flat|house|property))|move out|landlord (?:wants|told|says)\w* (?:me )?(?:to )?(?:leave|out|move)|kicked out|locked out", [
        P("ukpga/1988/50/section/21", "Housing Act 1988 s.21 (no-fault possession — check status)", ("england",)),
        P("ukpga/1988/50/section/8", "Housing Act 1988 s.8 (notice of possession proceedings)", ("england",)),
        P("ukpga/1977/43/section/1", "Protection from Eviction Act 1977 s.1 (unlawful eviction and harassment)", EW),
        P("anaw/2016/1/section/173", "Renting Homes (Wales) Act 2016 s.173 (landlord's notice)", ("wales",)),
        P("asp/2016/19/section/51", "Private Housing (Tenancies) (Scotland) Act 2016 s.51 (eviction orders)", S)]),
    ("deposit", r"deposit", [
        P("ukpga/2004/34/section/213", "Housing Act 2004 s.213 (deposit protection)", ("england",)),
        P("ukpga/2004/34/section/214", "Housing Act 2004 s.214 (failure to protect)", ("england",)),
        P("anaw/2016/1/section/45", "Renting Homes (Wales) Act 2016 s.45 (deposit schemes)", ("wales",)),
        P("ssi/2011/176/regulation/3", "Tenancy Deposit Schemes (Scotland) Regulations 2011 reg.3", S),
        P("ssi/2011/176/regulation/10", "Tenancy Deposit Schemes (Scotland) Regulations 2011 reg.10 (sanctions)", S)]),
    ("disrepair", r"repair|damp|mould|mold|leak|disrepair|heating|uninhabitable|unfit", [
        P("ukpga/1985/70/section/11", "Landlord and Tenant Act 1985 s.11 (repairing obligations)", ("england",)),
        P("ukpga/1985/70/section/9A", "Landlord and Tenant Act 1985 s.9A (fitness for human habitation)", ("england",)),
        P("anaw/2016/1/section/91", "Renting Homes (Wales) Act 2016 s.91 (fitness for human habitation)", ("wales",)),
        P("anaw/2016/1/section/92", "Renting Homes (Wales) Act 2016 s.92 (repairs)", ("wales",)),
        P("asp/2006/1/section/14", "Housing (Scotland) Act 2006 s.14 (repairing standard)", S)]),
    ("consumer", r"refund|faulty|broken|not as described|consumer|return(?:ed)? (?:it|the item|goods)|warranty|defective|bought|purchase", [
        P("ukpga/2015/15/section/9", "Consumer Rights Act 2015 s.9 (satisfactory quality)", ALL),
        P("ukpga/2015/15/section/20", "Consumer Rights Act 2015 s.20 (right to reject)", ALL),
        P("ukpga/2015/15/section/22", "Consumer Rights Act 2015 s.22 (30-day short-term right to reject)", ALL),
        P("ukpga/2015/15/section/24", "Consumer Rights Act 2015 s.24 (price reduction / final right to reject)", ALL),
        P("ukpga/2015/15/section/49", "Consumer Rights Act 2015 s.49 (services with reasonable care and skill)", ALL),
        P("uksi/2013/3134/regulation/29", "Consumer Contracts Regulations 2013 reg.29 (cancellation of online/distance orders)", ALL)]),
    ("immigration", r"visa|immigra|leave to remain|asylum|deport|overstay|home office|indefinite leave|\bilr\b|settle(?:d|ment) status|brp", [
        P("ukpga/1971/77/section/3", "Immigration Act 1971 s.3 (control of entry and stay)", ALL),
        P("ukpga/1971/77/section/3C", "Immigration Act 1971 s.3C (leave continuing while an application is pending)", ALL),
        P("ukpga/2002/41/section/82", "Nationality, Immigration and Asylum Act 2002 s.82 (right of appeal)", ALL)]),
    ("family_children", r"custody|child arrangement|contact with (?:my|the|our) (?:child|son|daughter|kids)|see my (?:child|son|daughter|kids)|residence of (?:my|the) child", [
        P("ukpga/1989/41/section/1", "Children Act 1989 s.1 (welfare of the child)", EW),
        P("ukpga/1989/41/section/8", "Children Act 1989 s.8 (child arrangements orders)", EW),
        P("ukpga/1995/36/section/11", "Children (Scotland) Act 1995 s.11 (orders about parental responsibilities)", S),
        P("nisi/1995/755/article/3", "Children (Northern Ireland) Order 1995 art.3 (welfare of the child)", NI)]),
    ("divorce", r"divorce|dissolution|separat", [
        P("ukpga/1973/18/section/1", "Matrimonial Causes Act 1973 s.1 (divorce)", EW),
        P("ukpga/1976/39/section/1", "Divorce (Scotland) Act 1976 s.1 (grounds of divorce)", S)]),
    ("domestic_abuse", r"domestic abuse|domestic violence|non-molestation|occupation order|abusive (?:partner|husband|wife)", [
        P("ukpga/1996/27/section/42", "Family Law Act 1996 s.42 (non-molestation orders)", EW),
        P("ukpga/1996/27/section/33", "Family Law Act 1996 s.33 (occupation orders)", EW)]),
    ("limitation", r"how long (?:do i have|have i got) to (?:sue|claim)|time limit|limitation period|too late to (?:sue|claim)|small claim|sue (?:them|him|her|my)", [
        P("ukpga/1980/58/section/2", "Limitation Act 1980 s.2 (tort: 6 years)", EW),
        P("ukpga/1980/58/section/5", "Limitation Act 1980 s.5 (contract: 6 years)", EW),
        P("ukpga/1973/52/section/6", "Prescription and Limitation (Scotland) Act 1973 s.6 (5-year prescription)", S)]),
]
_COMPILED = [(k, re.compile(rx, re.I), items) for k, rx, items in TOPICS]


def match_topics(text: str) -> List[str]:
    return [k for k, rx, _ in _COMPILED if rx.search(text or "")]


def pick(text: str, nation: Optional[str]) -> List[dict]:
    """Provisions for the matched topics that apply in the customer's nation (England if unknown)."""
    nat = nation or "england"
    out = []
    for k, rx, items in _COMPILED:
        if rx.search(text or ""):
            out += [{**it, "topic": k} for it in items if nat in it["nations"] and it not in out]
    return out[:MAX_PROVISIONS]


def _norm(xml: str, path: str) -> str:
    for part in ("regulation", "article"):
        if f"/{part}/" in path:
            return xml.replace(f'id="{part}-', 'id="section-')
    return xml


async def read_provision(item: dict, nation: Optional[str]) -> dict:
    """Official wording/status/extent of one provision (cached by legal_sources)."""
    path, sec = item["path"], item["path"].rsplit("/", 1)[-1]
    key = f"prov:{path}"
    info = L._get(key)
    if info is None:
        code, body = await L._fetch(f"{L.LEG}/{path}/data.xml")
        if code == 404:
            info = L._put(key, {"status": "not_found"}, L.STATUS_TTL)
        elif code != 200:
            raise RuntimeError(f"legislation.gov.uk {code}")
        else:
            info = L._put(key, L.parse_section(_norm(body, path), sec), L.STATUS_TTL)
    letter = L.EXTENT.get(nation or "")
    ext = (info.get("extent") or "").replace("N.I.", "N").split("+")
    verdict = info["status"]
    if verdict != "not_found" and letter and info.get("extent") and letter not in ext:
        verdict = "wrong_jurisdiction"
    elif verdict == "in_force" and info.get("pending_changes"):
        verdict = "changes_pending"
    return {**item, **info, "verdict": verdict, "url": f"{L.LEG}/{path}"}


STATUS_WORDS = {"in_force": "in force", "changes_pending": "in force — changes made by later laws are not yet shown in this text",
                "repealed": "REPEALED", "partly_repealed": "repealed or changed for some purposes — check before relying on it",
                "not_in_force": "NOT YET IN FORCE", "wrong_jurisdiction": "does NOT extend to the customer's nation"}


def as_source(r: dict, nation: Optional[str], unconfirmed: bool = False) -> dict:
    guess = (f"; the customer's UK nation is NOT confirmed — this is {L.NATION_LABEL.get(nation or 'england', 'England')} "
             "law, chosen provisionally") if unconfirmed else ""
    wording = "wording retrieved: first part only" if r.get("truncated") else "full wording retrieved"
    ver = f"; revised text current to {r['version_date']}" if r.get("version_date") else ""
    return {"title": f"{r['label']} (legislation.gov.uk — found from the topic of the question; status: "
                     f"{STATUS_WORDS.get(r['verdict'], r['verdict'])}; {wording}; territorial extent: "
                     f"{L.extent_words(r.get('extent')) or 'not stated'}{ver}{guess})",
            "url": r["url"], "content": f"{r.get('detail', '')} {r.get('text', '')}".strip(), "topic_found": True}


_STOP = {"what", "when", "where", "which", "about", "would", "could", "should", "there", "their", "they", "have", "with",
         "from", "this", "that", "your", "will", "been", "does", "into", "after", "before", "because", "still", "just",
         "legal", "rights", "right", "help", "please", "know", "want", "need", "tell", "advice", "they're", "i'm"}


def search_terms(text: str) -> str:
    words = [w for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in _STOP]
    return " ".join(dict.fromkeys(words))[:80]


async def search_acts(text: str) -> List[dict]:
    """Official legislation.gov.uk search (titles only) when the topic map has nothing. Not wording."""
    q = search_terms(text)
    if not q:
        return []
    code, body = await L._fetch(f"{L.LEG}/ukpga/data.feed?text={quote(q)}&results-count={SEARCH_RESULTS}")
    if code != 200:
        raise RuntimeError(f"search {code}")
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", body, re.S)[:SEARCH_RESULTS]:
        t = re.search(r"<title>([^<]+)</title>", e)
        i = re.search(r"<id>http://www\.legislation\.gov\.uk/id/([^<]+)</id>", e)
        if t and i:
            out.append({"title": f"{L._strip(t.group(1))} (legislation.gov.uk search match only — wording NOT retrieved; "
                                 "may not be relevant)", "url": f"{L.LEG}/{i.group(1)}", "content": "", "search_match": True})
    return out


async def topic_sources(text: str, nation: Optional[str], country: str = "GB") -> dict:
    """{'sources': [...], 'topics': [...], 'status': ok|no_match|unavailable|not_uk}. Never claims a check it did not do."""
    if (country or "GB").upper() != "GB":
        return {"sources": [], "topics": [], "status": "not_uk"}
    topics = match_topics(text)
    unconfirmed = not nation
    if unconfirmed:
        import lex_safety
        places = lex_safety._scan(text)["matter"]
        nation = next(iter(places)) if len(places) == 1 else None
    try:
        if topics:
            items = pick(text, nation)
            res = await asyncio.wait_for(asyncio.gather(*(read_provision(i, nation) for i in items), return_exceptions=True),
                                         timeout=TIMEOUT)
            good = [r for r in res if isinstance(r, dict) and r["verdict"] != "not_found"]
            return {"sources": [as_source(r, nation, unconfirmed) for r in good], "topics": topics,
                    "status": "ok" if good else "unavailable", "failed": len(items) - len(good)}
        found = await asyncio.wait_for(search_acts(text), timeout=TIMEOUT)
        return {"sources": found, "topics": [], "status": "search_only" if found else "no_match"}
    except Exception as e:
        logger.info("topic research failed: %r", e)
        return {"sources": [], "topics": topics, "status": "unavailable"}
