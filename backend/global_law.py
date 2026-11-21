"""Lex 2.0 global research engine: works out which country's law governs a question, retrieves official national sources
(national_law.py), uses one low-cost AI check only when the simple rules find nothing, searches official government
sites (Tavily) where no direct feed exists, and states exactly what was and was not verified."""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

import national_law as N

logger = logging.getLogger(__name__)
NAMES = {"GB": "the United Kingdom", "US": "the United States", "DE": "Germany", "ES": "Spain", "FR": "France",
         "IT": "Italy", "PL": "Poland", "PT": "Portugal", "IQ": "Iraq", "IN": "India", "PK": "Pakistan", "CN": "China",
         "AE": "the UAE", "AU": "Australia", "CA": "Canada", "IE": "Ireland", "NL": "the Netherlands", "BE": "Belgium"}
EU = {"DE", "ES", "FR", "IT", "PL", "PT", "IE", "NL", "BE"}
_C = {
    "GB": r"uk|united kingdom|britain|england|scotland|wales|northern ireland|london|manchester|birmingham|glasgow|edinburgh|"
          r"cardiff|belfast|leeds|liverpool|bristol|royaume-uni|angleterre|reino unido|inglaterra|regno unito|inghilterra|"
          r"wielka brytania|wielkiej brytanii|anglii|großbritannien|vereinigtes königreich",
    "US": r"united states|usa|u\.s\.|america|estados unidos|états-unis|stati uniti|stanach zjednoczonych|vereinigten staaten",
    "DE": r"germany|deutschland|allemagne|alemania|germania|niemcy|niemczech|alemanha|berlin|münchen|munich|hamburg|frankfurt|"
          r"köln|cologne|stuttgart|düsseldorf|leipzig|dresden",
    "ES": r"spain|españa|espagne|spagna|hiszpania|hiszpanii|espanha|spanien|madrid|barcelona|valencia|seville|sevilla|malaga|"
          r"málaga|bilbao|alicante|mallorca|tenerife",
    "FR": r"france|francia|frankreich|francji|frança|paris|lyon|marseille|toulouse|bordeaux|lille|nantes|strasbourg",
    "IT": r"italy|italia|italie|italien|włochy|włoszech|itália|rome|roma|milan|milano|naples|napoli|turin|torino|florence|firenze|"
          r"bologna|venice|venezia",
    "PL": r"poland|polska|polsce|pologne|polonia|polen|polónia|warsaw|warszawa|warszawie|kraków|krakow|krakowie|wrocław|"
          r"wrocławiu|gdańsk|gdańsku|poznań|poznaniu|łódź|łodzi",
    "PT": r"portugal|portogallo|portugalia|portugalii|lisbon|lisboa|porto|faro|algarve|coimbra|braga|madeira",
    "IQ": r"iraq|irak|baghdad|erbil|basra|mosul|kurdistan region",
    "IN": r"india|delhi|mumbai|bangalore|bengaluru|chennai|kolkata",
    "PK": r"pakistan|karachi|lahore|islamabad",
    "AE": r"uae|united arab emirates|dubai|abu dhabi|sharjah",
    "AU": r"australia|sydney|melbourne|brisbane|adelaide",
    "CA": r"canada|toronto|vancouver|montreal|ottawa|calgary",
    "CN": r"china|beijing|shanghai|shenzhen|guangzhou",
    "IE": r"ireland|dublin|cork|galway|limerick",
}
_CRX = {k: re.compile(rf"(?<![\w-])(?:{v})(?![\w-])", re.I) for k, v in _C.items()}
_LAW_OF = re.compile(r"\b(german|french|spanish|italian|polish|portuguese|american|iraqi|indian|british|english|scottish) law\b", re.I)
_PARTY_OF = re.compile(r"\b(german|french|spanish|italian|polish|portuguese|american|iraqi|indian|british|english|scottish) "
                       r"(?:shop|store|seller|trader|retailer|website|company|firm|business|employer|landlord|bank|airline)\b", re.I)
_DEMONYM = {"german": "DE", "french": "FR", "spanish": "ES", "italian": "IT", "polish": "PL", "portuguese": "PT",
            "american": "US", "iraqi": "IQ", "indian": "IN", "british": "GB", "english": "GB", "scottish": "GB"}
STATES = {
    "AL": ("Alabama", ["alisondb.legislature.state.al.us", "legislature.state.al.us"]), "AK": ("Alaska", ["akleg.gov"]),
    "AZ": ("Arizona", ["azleg.gov"]), "AR": ("Arkansas", ["arkleg.state.ar.us"]),
    "CA": ("California", ["leginfo.legislature.ca.gov"]), "CO": ("Colorado", ["leg.colorado.gov"]),
    "CT": ("Connecticut", ["cga.ct.gov"]), "DE": ("Delaware", ["delcode.delaware.gov"]),
    "FL": ("Florida", ["flsenate.gov", "leg.state.fl.us"]), "GA": ("Georgia", ["legis.ga.gov"]),
    "HI": ("Hawaii", ["capitol.hawaii.gov"]), "ID": ("Idaho", ["legislature.idaho.gov"]), "IL": ("Illinois", ["ilga.gov"]),
    "IN": ("Indiana", ["iga.in.gov"]), "IA": ("Iowa", ["legis.iowa.gov"]), "KS": ("Kansas", ["kslegislature.gov", "ksrevisor.gov"]),
    "KY": ("Kentucky", ["legislature.ky.gov"]), "LA": ("Louisiana", ["legis.la.gov"]), "ME": ("Maine", ["legislature.maine.gov"]),
    "MD": ("Maryland", ["mgaleg.maryland.gov"]), "MA": ("Massachusetts", ["malegislature.gov"]),
    "MI": ("Michigan", ["legislature.mi.gov"]), "MN": ("Minnesota", ["revisor.mn.gov"]), "MS": ("Mississippi", ["legislature.ms.gov"]),
    "MO": ("Missouri", ["revisor.mo.gov"]), "MT": ("Montana", ["leg.mt.gov"]), "NE": ("Nebraska", ["nebraskalegislature.gov"]),
    "NV": ("Nevada", ["leg.state.nv.us"]), "NH": ("New Hampshire", ["gc.nh.gov", "gencourt.state.nh.us"]),
    "NJ": ("New Jersey", ["njleg.state.nj.us", "pub.njleg.gov"]), "NM": ("New Mexico", ["nmonesource.com", "nmlegis.gov"]),
    "NY": ("New York", ["nysenate.gov", "public.leginfo.state.ny.us"]), "NC": ("North Carolina", ["ncleg.gov"]),
    "ND": ("North Dakota", ["ndlegis.gov"]), "OH": ("Ohio", ["codes.ohio.gov"]), "OK": ("Oklahoma", ["oklegislature.gov", "oscn.net"]),
    "OR": ("Oregon", ["oregonlegislature.gov"]), "PA": ("Pennsylvania", ["legis.state.pa.us", "palegis.us"]),
    "RI": ("Rhode Island", ["rilegislature.gov", "webserver.rilegislature.gov"]), "SC": ("South Carolina", ["scstatehouse.gov"]),
    "SD": ("South Dakota", ["sdlegislature.gov"]), "TN": ("Tennessee", ["capitol.tn.gov", "wapp.capitol.tn.gov"]),
    "TX": ("Texas", ["statutes.capitol.texas.gov"]), "UT": ("Utah", ["le.utah.gov"]), "VT": ("Vermont", ["legislature.vermont.gov"]),
    "VA": ("Virginia", ["law.lis.virginia.gov"]), "WA": ("Washington State", ["app.leg.wa.gov"]),
    "WV": ("West Virginia", ["code.wvlegislature.gov"]), "WI": ("Wisconsin", ["docs.legis.wisconsin.gov"]),
    "WY": ("Wyoming", ["wyoleg.gov"]), "DC": ("District of Columbia", ["code.dccouncil.gov"]),
}
_STATE_RX = re.compile(r"(?<![\w-])(" + "|".join(sorted((re.escape(v[0]) for k, v in STATES.items() if k != "WA"), key=len, reverse=True))
                       + r"|washington state|washington,? d\.?c\.?|nyc|los angeles|san francisco|chicago|houston|miami|seattle|"
                         r"boston|atlanta|dallas|phoenix|philadelphia|las vegas|denver)(?![\w-])", re.I)
_CITY_STATE = {"nyc": "NY", "los angeles": "CA", "san francisco": "CA", "chicago": "IL", "houston": "TX", "miami": "FL",
               "seattle": "WA", "boston": "MA", "atlanta": "GA", "dallas": "TX", "phoenix": "AZ", "philadelphia": "PA",
               "las vegas": "NV", "denver": "CO", "washington state": "WA"}
# Official government legislation sites for discovery where no direct feed is connected.
SITE_DOMAINS = {"PT": ["diariodarepublica.pt"], "FR": ["legifrance.gouv.fr"], "AU": ["legislation.gov.au"],
                "CA": ["laws-lois.justice.gc.ca"], "IN": ["indiacode.nic.in"], "IE": ["irishstatutebook.ie"],
                "DE": ["gesetze-im-internet.de"], "ES": ["boe.es"], "IT": ["normattiva.it"], "PL": ["isap.sejm.gov.pl"],
                "US": ["govinfo.gov", "ecfr.gov", "uscode.house.gov"]}
SITE_TOPIC_QUERY = {"PT": {"housing": "NRAU Lei 6/2006 arrendamento urbano denúncia senhorio artigo",
                           "deposit": "Código Civil caução arrendamento artigo", "repairs": "Código Civil artigo 1074 obras arrendado",
                           "faulty_goods": "Decreto-Lei 84/2021 direitos do consumidor falta de conformidade artigo",
                           "online_cancel": "Decreto-Lei 24/2014 direito de livre resolução 14 dias artigo",
                           "dismissal": "Código do Trabalho despedimento ilícito artigo 381 387",
                           "wages": "Código do Trabalho retribuição pagamento artigo", "discrimination": "Código do Trabalho igualdade não discriminação artigo 25"}}
SETTINGS_ID = "lex_ai_discovery"
MODEL = ("anthropic", "claude-haiku-4-5-20251001")
EST_GBP_PER_DISCOVERY = 0.0022  # ~1,400 input + ~180 output tokens on Haiku 4.5 ($1/$5 per M)
DISCOVERY_WAIT, REF_WAIT, DET_WAIT, MAX_AI_REFS, BUDGET = 4.0, 2.5, 4.5, 3, 8.6
_cache: Dict[str, tuple] = {}


def _get(k):
    v = _cache.get(k)
    return v[1] if v and v[0] > time.time() else None


def _put(k, v, ttl):
    _cache[k] = (time.time() + ttl, v)
    return v


def coverage(j: str, state: Optional[str] = None) -> str:
    """verified | official_site_search | general_only — what Lex can actually check for this jurisdiction."""
    if j == "US" and state:
        return "verified" if N.state_enabled(state) else "official_site_search"
    if j == "FR":
        return "verified" if N.france_enabled() else "official_site_search"
    if j in ("GB", "DE", "ES", "IT", "PL", "US"):
        return "verified"
    return "official_site_search" if j in SITE_DOMAINS else "general_only"


def detect(text: str, selected: str) -> dict:
    """Deterministic jurisdiction analysis: places and 'X law' mentions in any supported language, then the customer's
    selected country. Where the customer lives is not treated as decisive."""
    sel = (selected or "GB").upper()
    hits = []
    for code, rx in _CRX.items():
        for m in rx.finditer(text or ""):
            hits.append((m.start(), code))
    for m in _LAW_OF.finditer(text or ""):
        hits.append((m.start() - 10000, _DEMONYM[m.group(1).lower()]))  # 'German law' outranks place names
    for m in _PARTY_OF.finditer(text or ""):
        hits.append((m.start(), _DEMONYM[m.group(1).lower()]))  # 'a German shop / company' = another jurisdiction involved
    st = None
    for m in _STATE_RX.finditer(text or ""):
        w = m.group(1).lower()
        st = _CITY_STATE.get(w) or ("DC" if w.startswith("washington") else next(
            (k for k, v in STATES.items() if v[0].lower() == w), None))
        hits.append((m.start(), "US"))
        break
    found = list(dict.fromkeys(c for _, c in sorted(hits)))
    primary = found[0] if found else sel
    if sel == "US" and not found and not st:
        st = None
    involved = list(dict.fromkeys([primary] + found + ([sel] if found and sel not in found else [])))
    return {"selected": sel, "primary": primary, "all": involved, "cross_border": len(involved) > 1,
            "us_state": st if primary == "US" or "US" in found else None,
            "how": "named in the question" if found else "customer's selected country", "named": found}


async def _discovery_enabled(db) -> bool:
    if db is None:
        return True
    try:
        doc = await db.app_settings.find_one({"_id": SETTINGS_ID}) or {}
        return doc.get("enabled", True) is not False
    except Exception:
        return True


DISCOVERY_SYSTEM = (
    "You are the research planner of a legal-information service. Given a customer's question, identify which country's "
    "law most likely governs it (not simply where the customer lives), any other jurisdictions involved, and up to 3 "
    "specific statutory provisions that an official database should be checked for. Reply with JSON only:\n"
    '{"primary":"<ISO code>","others":["<ISO>"],"us_state":"<2-letter or empty>","issue":"<=12 words",'
    '"refs":[...],"query":"<=10 search words in the official language of the primary jurisdiction"}\n'
    "Codes: GB, US, DE, ES, FR, IT, PL, PT, IQ, IN, PK, CN, AE, AU, CA, IE. Ref formats (only these):\n"
    'GB {"j":"GB","act":"Employment Rights Act","year":"1996","section":"94"}\n'
    'DE {"j":"DE","law":"<gesetze-im-internet slug e.g. bgb, kschg, agg, betrvg, stgb, burlg>","art":"573"}\n'
    'ES {"j":"ES","law":"<BOE id e.g. BOE-A-1994-26003, or the exact law title>","art":"36"}\n'
    'IT {"j":"IT","law":"<Normattiva URN part e.g. legge:1998-12-09;431 or decreto.legislativo:2005-09-06;206; Codice civile = regio.decreto:1942-03-16;262:2>","art":"3"}\n'
    'PL {"j":"PL","law":"<Dziennik Ustaw ELI e.g. DU/1964/93 (Kodeks cywilny), DU/1974/141 (Kodeks pracy)>","art":"673"}\n'
    'FR {"j":"FR","law":"<code name e.g. Code du travail>","art":"L1234-1"}\n'
    'US {"j":"US","law":"usc:<title> or cfr:<title>","art":"<section e.g. 1692g or 1026.13>"} (federal only)\n'
    "Only give refs you are confident exist; they will be checked against the official database and discarded if absent. "
    "US state law: give us_state and no refs. Other countries: no refs. Never invent."
)


async def _discover(text: str, sel: str, db) -> Optional[dict]:
    key = "disc:" + hashlib.sha256(f"{sel}|{text.strip().lower()}".encode()).hexdigest()[:24]
    hit = _get(key)
    if hit is not None:
        return hit
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import ai_usage
    t0 = time.monotonic()
    raw, status = "", "ok"
    try:
        chat = LlmChat(api_key=os.environ.get("EMERGENT_LLM_KEY"), session_id=f"discover-{uuid.uuid4()}",
                       system_message=DISCOVERY_SYSTEM).with_model(*MODEL).with_params(max_tokens=300)
        raw = await asyncio.wait_for(chat.send_message(UserMessage(
            text=f"Customer's selected country: {sel}\nQuestion:\n{text[:1500]}")), timeout=DISCOVERY_WAIT)
        m = re.search(r"\{.*\}", raw or "", re.S)
        out = json.loads(m.group(0)) if m else None
    except Exception as e:
        logger.info("AI discovery failed: %r", e)
        out, status = None, "error"
    try:
        ai_usage.record(provider=MODEL[0], model_requested=MODEL[1], input_chars=len(DISCOVERY_SYSTEM) + len(text[:1500]),
                        output_chars=len(raw or ""), latency_ms=int((time.monotonic() - t0) * 1000), status=status,
                        call_site="global_research_discovery")
    except Exception:
        pass
    if isinstance(out, dict):
        out["refs"] = [r for r in (out.get("refs") or []) if isinstance(r, dict)][:MAX_AI_REFS]
        _put(key, out, 86400)
    return out if isinstance(out, dict) else None


async def _verify_ai_ref(r: dict, nation: Optional[str]) -> Optional[dict]:
    """An AI-suggested provision counts only if the official database returns it."""
    j = str(r.get("j", "")).upper()
    try:
        if j == "GB":
            import legal_sources as L
            ref = {"act": str(r.get("act", "")).strip(), "year": str(r.get("year", "")), "section": str(r.get("section") or "") or None}
            ref["label"] = f"{ref['act']} {ref['year']}" + (f", section {ref['section']}" if ref["section"] else "")
            ref["anchor"] = ref["label"]
            res = await asyncio.wait_for(L.check_ref(ref, nation), timeout=REF_WAIT)
            if res["verdict"] in ("not_found", "lookup_failed") or not res.get("text"):
                return None
            return {"j": "GB", "label": res.get("official_title", ref["act"]) + (f" s.{ref['section']}" if ref["section"] else ""),
                    "url": res["url"], "text": res.get("text", ""), "status": res["verdict"],
                    "version": f"legislation.gov.uk revised text{', ' + res['version_date'] if res.get('version_date') else ''}",
                    "extent": L.extent_words(res.get("extent"))}
        if j not in N.CONNECTORS or not r.get("law") or not r.get("art"):
            return None
        law, art = str(r["law"]).strip(), str(r["art"]).strip().replace("§", "").replace("Art.", "").strip()
        if j == "ES" and not law.startswith("BOE-"):
            law = await asyncio.wait_for(N.boe_find(law), timeout=REF_WAIT) or ""
            if not law:
                return None
        if j == "DE":
            law = law.lower()
        res = await N.read(N.R(j, law, art, law), wait=REF_WAIT)
        return None if res.get("failed") else res
    except Exception as e:
        logger.info("AI ref check failed %s: %r", r, e)
        return None


def _terms(query: str) -> set:
    return {w for w in re.findall(r"[a-zà-ÿ]{5,}", query.lower())} - {"statute", "state", "states", "texas", "artigo", "article"}


def _hits(text: str, query: str) -> int:
    low = (text or "").lower()
    return sum(1 for t in _terms(query) if t in low)


def _best_window(text: str, query: str, size: int = 2500) -> str:
    """The part of a long official page that best matches the question (most distinct question words)."""
    terms = _terms(query)
    low = text.lower()
    if len(text) <= size or not terms:
        return text[:size]
    best, at = -1, 0
    for i in range(0, len(text) - size // 2, 400):
        w = low[i:i + size]
        score = sum(1 for t in terms if t in w) * 10 + sum(w.count(t) for t in terms)
        if score > best:
            best, at = score, i
    return text[at:at + size]


async def site_search(j: str, state: Optional[str], query: str, paid_ok: bool) -> dict:
    """Official-site discovery via Tavily (only official government domains), then reads the page where the site
    allows it. Returns {'sources', 'status', 'calls'}."""
    domains = STATES[state][1] if (j == "US" and state in STATES) else SITE_DOMAINS.get(j)
    if not domains or not query:
        return {"sources": [], "status": "no_site", "calls": 0}
    if not paid_ok:
        return {"sources": [], "status": "search_unavailable", "calls": 0}
    key = "site:" + hashlib.sha256(f"{','.join(domains)}|{query.lower()}".encode()).hexdigest()[:24]
    cached = _get(key)
    if cached is not None:
        return {**cached, "calls": 0}
    import rag
    results, st = await rag._tavily_search_ex(query, include_domains=domains, max_results=3, search_depth="basic")
    if st != "ok":
        return {"sources": [], "status": st, "calls": 0}
    out = []
    async with httpx.AsyncClient(timeout=3.5, headers=N.UA, follow_redirects=True) as c:
        async def read_page(it):
            host = (urlparse(it.get("url") or "").hostname or "").lower()
            if not any(host == d or host.endswith("." + d) for d in domains):
                return None
            how, text = "search_extract", (it.get("content") or "")
            try:
                r = await c.get(it["url"])
                page = N.clean(r.text) if r.status_code == 200 else ""
                if len(page) > 1500 and _hits(page, query) >= _hits(text, query):  # JS-only shells fall back to the extract
                    how, text = "page_read", page
            except Exception:
                pass
            prov = re.search(r"(?:§+|\bSec(?:tion|\.)|\bArt(?:igo|icle|ículo|\.)|\bArticolo)\s*[\dA-Z][\w.\-]*", f"{it.get('title', '')} {text[:3000]}")
            if how == "page_read":
                text = _best_window(text, f"{query} {it.get('title', '')}")
            return {"title": it.get("title") or it["url"], "url": it["url"], "content": text[:N.TEXT_CAP], "how": how,
                    "provision": prov.group(0) if prov else ""}
        got = await asyncio.gather(*(read_page(it) for it in results))
    for g in got:
        if g:
            out.append(g)
    res = {"sources": out, "status": "ok" if out else "no_results"}
    _put(key, res, 7 * 86400)
    return {**res, "calls": 1}


def _as_source(r: dict, j: str, how: str) -> dict:
    status = {"in_force": "in force", "repealed": "REPEALED", "unknown": "in-force status not confirmed",
              "changes_pending": "in force — changes pending", "partly_repealed": "repealed/changed for some purposes",
              "not_in_force": "NOT YET IN FORCE"}.get(r.get("status"), r.get("status") or "status not confirmed")
    found = {"topic": "found from the topic of the question", "ai": "suggested by Lex's AI research step, then CONFIRMED to "
             "exist on the official database — relevance to these facts not confirmed"}[how]
    src = "legislation.gov.uk" if j == "GB" else N.SOURCE_NAME.get(j, "official source")
    ext = f"; territorial extent: {r['extent']}" if r.get("extent") else ""
    law = "US federal law" if j == "US" else "UK legislation" if j == "GB" else \
        f"{STATES[j[3:]][0]} state law" if j.startswith("US-") else f"{NAMES.get(j, j)} national law"
    return {"title": f"{r['label']} ({law} — official text from {src}; {found}; status: {status}; "
                     f"{r.get('version', '')}{ext}; retrieved in the original language)",
            "url": r["url"], "content": r.get("text", ""), "national": j}


def _site_source(s: dict, j: str, state: Optional[str]) -> dict:
    where = STATES[state][0] + " (US state)" if state else NAMES.get(j, j)
    how = ("page read directly from the official site" if s["how"] == "page_read" else
           "text is the search provider's extract — Lex could not open the official page itself")
    prov = f"; provision mentioned: {s['provision']}" if s.get("provision") else "; no specific provision identified"
    return {"title": f"{s['title']} ({where} — found by searching the official government legislation site; {how}{prov}; "
                     "currency and in-force status NOT confirmed)", "url": s["url"], "content": s["content"],
            "national": j, "site_search": True}


def _notes(plan: dict, cov: Dict[str, str], got: Dict[str, int], site: dict, ai: Optional[dict]) -> List[str]:
    p, st = plan["primary"], plan.get("us_state")
    cov = {**cov, "US": "verified"} if "US" in cov else cov  # federal feed; state coverage is handled separately
    lines = [f"JURISDICTION ANALYSIS (Lex research engine — provisional, check it against the facts): the law most likely "
             f"to govern is {NAMES.get(p, p)}{' — ' + STATES[st][0] + ' state law' if p == 'US' and st else ''} "
             f"(basis: {plan['how']}"
             + (f"; AI research step suggested {NAMES.get(ai.get('primary'), ai.get('primary'))}" if ai and ai.get("primary") else "")
             + "). Decide which country's law governs from where the contract, property, job, purchase or court is — "
               "not only where the customer lives — and say which law you are applying."]
    lines.append("NATIONAL DEADLINES: state a time limit only as written in a retrieved official text above, citing it. "
                 "Do not turn it into an exact calendar date as if verified: what starts the clock (receipt, service, "
                 "knowledge), weekend/holiday rules and exceptions have not been checked by Lex. If the customer gave "
                 "dates, any date you work out is an estimate they must confirm urgently with a local lawyer or court. If "
                 "no retrieved text states the period, say the deadline could not be verified from an official source "
                 "and do not give a number from memory.")
    if plan["cross_border"]:
        lines.append("CROSS-BORDER: jurisdictions involved: " + ", ".join(NAMES.get(j, j) for j in plan["all"]) +
                     ". Keep each country's national law, EU law and UK law separate; never apply one country's rules in "
                     "place of another's. Do not silently pick one country: name the jurisdictions that could apply, say "
                     "which you think governs each point and why, and flag the choice-of-law / which-court question as "
                     "uncertain where it is.")
    for j in plan["all"]:
        c = cov.get(j)
        if j == "GB" or c is None:
            continue
        name = "US federal" if j == "US" else NAMES.get(j, j)
        if j == "US" and plan.get("state_issue") and not st:
            lines.append("US STATE NOT IDENTIFIED: this issue is mainly governed by STATE law, which differs between states. "
                         "Ask which state the matter is in; until then give general information only and never present "
                         "federal law as the answer to the state-law point.")
        if j == "US" and st and plan.get("state_issue"):
            n = got.get("US-state", 0)
            lines.append(f"US STATE LAW ({STATES[st][0]}): " + (
                f"{n} provision(s) retrieved from the official {STATES[st][0]} statute source (listed above) — cite them; "
                "this does not confirm your interpretation." if n and N.state_enabled(st) else
                f"{n} result(s) found on the official {STATES[st][0]} legislature site — use them only as labelled; their "
                "currency is not confirmed." if n else
                f"Lex could NOT retrieve {STATES[st][0]} legislation for this answer.") +
                " Federal law does NOT answer a state-law question: never present federal sources as the answer to the "
                "state-law point; say plainly what could not be verified and suggest checking the state statute or a "
                "local attorney.")
        if j == "US" and plan.get("state_issue") and not got.get("US"):
            continue
        if c == "verified" and got.get(j):
            lines.append(f"{name.upper()} LAW: {got[j]} provision(s) retrieved from the official national database "
                         "(listed above, original language). Quote or translate faithfully, cite them, and say the text was "
                         "retrieved from the official source; this does not confirm your interpretation. THE RETRIEVED "
                         "OFFICIAL TEXT OVERRIDES YOUR MEMORY: if what you remember (a period, amount, condition or article "
                         "number) differs from the retrieved text, use the retrieved text and never the remembered rule.")
        elif c == "official_site_search" and got.get(j):
            lines.append(f"{name.upper()}: results come from searching official government sites only — not a verified "
                         "legislation feed. Treat them as unconfirmed pointers; do not call them verified.")
        else:
            reason = {"verified": "the official lookup returned nothing usable for this question",
                      "official_site_search": "the official-site search " + ("is unavailable just now" if site.get(j) in
                                                                               ("quota_exhausted", "search_unavailable", "not_configured", "unavailable") else "found nothing relevant"),
                      "general_only": f"Lex has no verified official legal-source connection for {name}"}[c]
            lines.append(f"SOURCE LIMITS — {name.upper()}: {reason}. Give clearly labelled GENERAL INFORMATION only; do not "
                         "state article numbers, deadlines or amounts as checked; never invent citations; recommend a "
                         "qualified local lawyer for anything important.")
    return lines


def plan_for(message: str, context: str, selected: str) -> dict:
    plan = detect(message, selected)
    if not plan["named"] and context:
        earlier = detect(f"{message}\n{context}", selected)
        if earlier["named"]:
            plan = {**earlier, "how": "named earlier in the conversation"}
    return plan


async def research(message: str, context: str, selected: str, db=None, paid_ok: bool = True,
                   nation: Optional[str] = None, uk_gap: bool = False) -> dict:
    """{'plan', 'sources', 'notes', 'national_ok', 'tavily_calls', 'meta'} for non-UK (or cross-border) questions."""
    t0 = time.monotonic()
    text = f"{message}\n{context}".strip()
    plan = plan_for(message, context, selected)
    topics = N.topics(text)
    st = plan["us_state"]
    cov = {j: coverage(j, st if j == "US" else None) for j in plan["all"]}
    want = [j for j in plan["all"] if j != "GB"][:2]
    meta = {"selected": plan["selected"], "primary": plan["primary"], "all": plan["all"], "cross_border": plan["cross_border"],
            "us_state": st, "topics": topics, "coverage": cov, "det_refs": 0, "det_ok": 0, "ai_used": False,
            "ai_refs": 0, "ai_verified": 0, "site": {}, "tavily_calls": 0}
    uk_ai = uk_gap and plan["primary"] == "GB"  # UK topic map found nothing: let the AI step suggest UK provisions
    if not want and not uk_ai:
        return {"plan": plan, "sources": [], "notes": [], "national_ok": {}, "tavily_calls": 0, "meta": meta}
    state_issue = "US" in want and (not topics or bool(set(topics) & N.US_STATE_TOPICS))
    det = []
    for j in want:
        if j == "US":
            det += [r for r in N.pick("US", text) if r["topic"] not in N.US_STATE_TOPICS]  # federal points only
            if st and state_issue:
                det += N.pick_state(st, text)  # official state statute text where a direct source exists
        elif cov[j] == "verified":
            det += N.pick(j, text)
    meta["det_refs"] = len(det)
    sources, got, ai, checked = [], {}, None, []
    needs_ai = any(cov[j] == "verified" and not any(r["j"] == j for r in det) and not (j == "US" and state_issue)
                   for j in want) or any(cov[j] == "official_site_search" and not topics for j in want) or uk_ai
    use_ai = needs_ai and await _discovery_enabled(db)

    async def _nothing():
        return None
    det_res, ai = await asyncio.gather(asyncio.gather(*(N.read(r, wait=DET_WAIT) for r in det)),
                                       _discover(text, plan["selected"], db) if use_ai else _nothing())
    for r in det_res:
        if not r.get("failed"):
            sources.append(_as_source(r, r["j"], "topic"))
            k = "US-state" if r["j"].startswith("US-") else r["j"]
            got[k] = got.get(k, 0) + 1
    meta["det_ok"] = sum(got.values())
    meta["ai_used"] = use_ai
    if ai:
        if "US" in want and not st and str(ai.get("us_state") or "").upper() in STATES:
            st = plan["us_state"] = str(ai["us_state"]).upper()
            meta["us_state"] = st
        refs = [r for r in ai.get("refs", []) if str(r.get("j", "")).upper() in want + (["GB"] if uk_ai else [])]
        meta["ai_refs"] = len(refs)
        try:
            checked = await asyncio.wait_for(asyncio.gather(*(_verify_ai_ref(r, nation) for r in refs)),
                                             timeout=max(0.5, min(REF_WAIT + 0.5, BUDGET - 2.0 - (time.monotonic() - t0))))
        except asyncio.TimeoutError:
            checked = []
        for r in checked:
            if r and r.get("url") not in {s["url"] for s in sources}:
                sources.append(_as_source(r, r["j"], "ai"))
                got[r["j"]] = got.get(r["j"], 0) + 1
                meta["ai_verified"] += 1
    for j in want:
        jst = st if j == "US" else None
        if j == "US" and (not (jst and state_issue) or got.get("US-state")):
            continue
        if coverage(j, jst) == "general_only" or (coverage(j, jst) == "verified" and got.get(j)):
            continue
        q = (ai or {}).get("query") or next((SITE_TOPIC_QUERY.get(j, {}).get(t) for t in topics
                                             if SITE_TOPIC_QUERY.get(j, {}).get(t)), None)
        if not q:
            import rag
            q = rag.scrub(message)[:200] + (f" {STATES[jst][0]} statute" if jst else f" {NAMES.get(j, j)} law")
        try:
            s = await asyncio.wait_for(site_search(j, jst, q, paid_ok), timeout=max(0.5, BUDGET - (time.monotonic() - t0)))
        except asyncio.TimeoutError:
            s = {"sources": [], "status": "timeout", "calls": 1}
        meta["site"][j] = s["status"]
        meta["tavily_calls"] += s["calls"]
        for it in s["sources"]:
            sources.append(_site_source(it, j, jst))
            k = "US-state" if jst else j
            got[k] = got.get(k, 0) + 1
    plan["state_issue"] = state_issue
    extra_notes = []
    if "dismissal" in topics:
        import national_deadlines
        meta["deadline_gate"] = any(j in national_deadlines.RULES for j in want) and not national_deadlines.calc_enabled()
        retrieved = list(det_res) + [r for r in checked if r]
        for j in want:
            if j in national_deadlines.RULES:
                extra_notes.append(national_deadlines.block(j, retrieved, message, datetime.now(timezone.utc).date()))
    notes = _notes(plan, cov, got, meta["site"], ai) if want else (
        ["UK PROVISIONS FROM THE AI RESEARCH STEP: the topic map had no match, so an AI step suggested the UK provisions "
         "listed above; each was confirmed to exist on legislation.gov.uk and its wording retrieved. Use them only if they "
         "actually fit the customer's facts."] if got.get("GB") else [])
    notes += [x for x in extra_notes if x]
    meta["latency_ms"] = int((time.monotonic() - t0) * 1000)
    meta["sources"] = len(sources)
    return {"plan": plan, "sources": sources, "notes": notes, "national_ok": got, "tavily_calls": meta["tavily_calls"],
            "meta": meta}


async def record_metrics(db, meta: dict, total_ms: int, paid_status: str) -> None:
    if db is None:
        return
    try:
        await db.research_metrics.insert_one({**{k: v for k, v in meta.items()}, "total_ms": total_ms, "paid_search": paid_status,
                                              "created_at": datetime.now(timezone.utc)})
    except Exception as e:
        logger.info("research metrics not stored: %r", e)


async def ensure_indexes(db) -> None:
    await db.research_metrics.create_index("created_at", expireAfterSeconds=180 * 86400)
    await db.legal_source_changes.create_index([("status", 1), ("detected_at", -1)])
