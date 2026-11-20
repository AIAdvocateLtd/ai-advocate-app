"""Lex 2.0: EU law from official EU sources (Publications Office Cellar / EUR-Lex), clearly separated from UK law and from
national law. Free, no AI calls. National implementing law of EU member states is NOT retrieved yet (disclosed)."""
import asyncio
import logging
import re
import time
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)
CELLAR = "http://publications.europa.eu/resource/celex/"
SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
EURLEX = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"
UA = {"User-Agent": "AIAdvocate/1.0 (+https://aiadvocate.co.uk; support@aiadvocate.co.uk)"}
EU_COUNTRIES = {"ES": "Spain", "FR": "France", "PL": "Poland", "DE": "Germany", "IT": "Italy", "PT": "Portugal"}
TTL, FAIL_TTL, TIMEOUT, MAX_ACTS, TEXT_CAP = 7 * 86400, 300, 8.0, 2, 2500
_cache: Dict[str, Tuple[float, object]] = {}


def A(celex, kind, label, articles, uk_path=None):
    return {"celex": celex, "kind": kind, "label": label, "articles": articles, "uk_path": uk_path}


TOPICS = [
    (r"refund|faulty|broken|defective|not as described|warranty|guarantee|consumer|online (?:order|purchase)|cancel (?:my|an?) order|cooling.off", [
        A("32011L0083", "directive", "Consumer Rights Directive 2011/83/EU", [9]),
        A("32019L0771", "directive", "Sale of Goods Directive (EU) 2019/771", [10, 13])]),
    (r"flight|airline|delayed|denied boarding|cancelled (?:flight|my flight)", [
        A("32004R0261", "regulation", "Air Passenger Rights Regulation (EC) No 261/2004", [5, 7], "eur/2004/261")]),
    (r"gdpr|personal data|data protection|subject access|my data", [
        A("32016R0679", "regulation", "General Data Protection Regulation (EU) 2016/679", [15, 17], "eur/2016/679")]),
    (r"holiday|annual leave|working hours|working time|rest break", [
        A("32003L0088", "directive", "Working Time Directive 2003/88/EC", [7])]),
    (r"residence|right to live|registration certificate|move to (?:spain|france|poland|germany|italy|portugal)|free movement", [
        A("32004L0038", "directive", "Citizens' Rights Directive 2004/38/EC", [6, 7])]),
    (r"which country.{0,20}court|cross.border|sue (?:a|the) (?:company|business|trader) (?:in|from)|jurisdiction", [
        A("32012R1215", "regulation", "Brussels I (recast) Regulation (EU) No 1215/2012", [4, 18]),
        A("32008R0593", "regulation", "Rome I Regulation (EC) No 593/2008", [6], "eur/2008/593")]),
    (r"package holiday|package travel|tour operator", [
        A("32015L2302", "directive", "Package Travel Directive (EU) 2015/2302", [13, 14])]),
]
_COMPILED = [(re.compile(rx, re.I), acts) for rx, acts in TOPICS]
_MENTIONS_EU = re.compile(r"\bEU\b|european union|\bdirective\b|eu regulation|eu law|\bgdpr\b|brussels i|rome i|261/2004", re.I)
_NAMES = re.compile(r"\b(spain|spanish|france|french|poland|polish|germany|german|italy|italian|portugal|portuguese|"
                    r"england|scotland|wales|northern ireland|\buk\b|united kingdom|britain|british)\b", re.I)
_UK_WORDS = {"england", "scotland", "wales", "northern ireland", "uk", "united kingdom", "britain", "british"}


def _get(k):
    v = _cache.get(k)
    return v[1] if v and v[0] > time.time() else None


def _put(k, v, ttl):
    _cache[k] = (time.time() + ttl, v)
    return v


def pick(text: str) -> List[dict]:
    out = []
    for rx, acts in _COMPILED:
        if rx.search(text or ""):
            out += [a for a in acts if a not in out]
    return out[:MAX_ACTS]


def wanted(text: str, country: str) -> bool:
    c = (country or "GB").upper()
    return c in EU_COUNTRIES or (c == "GB" and bool(_MENTIONS_EU.search(text or "")))


def _articles(html: str, nums: List[int]) -> str:
    t = re.sub(r"<[^>]+>", " ", html)
    t = re.sub(r"\s+", " ", t)
    out = []
    for n in nums:
        m = next((x for x in re.finditer(rf"\bArticle {n} (?=[A-Z]|\d\. )", t) if not t.startswith("Article", x.end())), None)
        if not m:
            continue
        nxt = re.search(rf"\bArticle {n + 1} (?=[A-Z]|\d\. )", t[m.end():])
        seg = t[m.start(): m.end() + (nxt.start() if nxt else 1500)]
        out.append(seg[:1200])
    return " … ".join(out)[:TEXT_CAP]


async def _in_force(client: httpx.AsyncClient, celex: str) -> Optional[bool]:
    q = ('PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> SELECT ?f WHERE { ?w cdm:resource_legal_id_celex '
         f'"{celex}"^^<http://www.w3.org/2001/XMLSchema#string> . ?w cdm:resource_legal_in-force ?f }} LIMIT 1')
    r = await client.get(SPARQL, params={"query": q}, headers={**UA, "Accept": "application/sparql-results+json"})
    b = r.json()["results"]["bindings"] if r.status_code == 200 else []
    return (b[0]["f"]["value"] in ("1", "true")) if b else None


async def read_act(act: dict) -> dict:
    key = f"eu:{act['celex']}"
    hit = _get(key)
    if hit is not None:
        return hit
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as c:
            r, force = await asyncio.gather(
                c.get(CELLAR + act["celex"], headers={**UA, "Accept": "application/xhtml+xml, text/html;q=0.9", "Accept-Language": "eng"}),
                _in_force(c, act["celex"]))
        if r.status_code != 200:
            raise RuntimeError(f"cellar {r.status_code}")
        return _put(key, {**act, "text": _articles(r.text, act["articles"]), "in_force": force}, TTL)
    except Exception as e:
        logger.info("EU lookup failed %s: %r", act["celex"], e)
        return _put(key, {**act, "failed": True}, FAIL_TTL)


def as_source(r: dict, country: str) -> dict:
    c = (country or "GB").upper()
    status = {True: "in force in the EU", False: "NO LONGER IN FORCE in the EU", None: "EU in-force status not confirmed"}[r.get("in_force")]
    if c == "GB":
        where = ("EU law — NOT UK law. Since 1 January 2021 EU law does not apply directly in the UK; any UK version "
                 "is UK 'assimilated law' on legislation.gov.uk and may differ")
    elif r["kind"] == "directive":
        where = (f"EU directive — it applies in {EU_COUNTRIES[c]} through {EU_COUNTRIES[c]}'s own implementing law, which was "
                 f"NOT retrieved (official {EU_COUNTRIES[c]} national-law sources are not connected yet)")
    else:
        where = f"EU regulation — directly applicable in {EU_COUNTRIES[c]}; national rules may add detail and were NOT retrieved"
    arts = ", ".join(f"Art {a}" for a in r["articles"])
    return {"title": f"{r['label']} — {arts} (official EU text, Publications Office/EUR-Lex; original version as adopted, "
                     f"later amendments may not be shown; {status}; {where})",
            "url": EURLEX + r["celex"], "content": r.get("text", ""), "eu": True}


def cross_border_note(text: str, country: str) -> str:
    names = {m.lower() for m in _NAMES.findall(text or "")}
    eu_named = {n for n in names if n not in _UK_WORDS}
    c = (country or "GB").upper()
    if (c == "GB" and eu_named) or (c in EU_COUNTRIES and names & _UK_WORDS):
        return ("CROSS-BORDER: the question involves the UK and an EU country. First identify which country's law governs "
                "the issue (where the contract, property, job or court is — not just where the customer lives now). Lex has "
                "official sources only for UK legislation and EU law; national law of EU countries was NOT retrieved — say so, "
                "and never apply UK law or general EU rules in place of that country's national law.")
    return ""


async def eu_sources(text: str, country: str) -> dict:
    """{'sources', 'status': ok|no_match|unavailable|not_wanted, 'note'}"""
    note = cross_border_note(text, country)
    if not wanted(text, country):
        return {"sources": [], "status": "not_wanted", "note": note}
    acts = pick(text)
    if not acts:
        return {"sources": [], "status": "no_match", "note": note}
    res = await asyncio.gather(*(read_act(a) for a in acts))
    good = [r for r in res if not r.get("failed")]
    srcs = [as_source(r, country) for r in good]
    if (country or "GB").upper() == "GB":
        srcs += [{"title": f"UK version of the {r['label']} (legislation.gov.uk — UK 'assimilated law'; wording NOT retrieved; "
                           "check its current status before relying on it)", "url": f"https://www.legislation.gov.uk/{r['uk_path']}",
                  "content": "", "search_match": True} for r in good if r.get("uk_path")]
    return {"sources": srcs, "status": "ok" if good else "unavailable", "note": note,
            "failed": len(acts) - len(good)}


def national_gap_note(country: str) -> str:
    c = (country or "GB").upper()
    if c == "GB":
        return ""
    name = EU_COUNTRIES.get(c)
    return (f"SOURCE LIMITS: official {name or c} national legislation is not connected to Lex yet. "
            + ("Only EU-level law (above, if any) was retrieved from official sources. " if name else "")
            + "Do not present national rules as checked against official sources; say plainly that national law could not "
              "be verified and recommend a qualified local lawyer for anything important.")
