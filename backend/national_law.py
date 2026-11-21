"""Lex 2.0 national-law connectors: official sources for Germany, Spain, Italy, Poland, France (Légifrance keys needed)
and US federal law, all returning one shape. Free public sources, no AI calls. Every retrieved text is fingerprinted in
`legal_source_records` so later changes are detected automatically and queued for review."""
import asyncio
import hashlib
import html
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)
UA = {"User-Agent": "AIAdvocate/1.0 (+https://aiadvocate.co.uk; support@aiadvocate.co.uk)"}
TTL, FAIL_TTL, DOC_TTL, TEXT_CAP, WAIT = 7 * 86400, 900, 7 * 86400, 2500, 5.0
TIMEOUT = httpx.Timeout(25.0, connect=6.0)
_cache: Dict[str, Tuple[float, object]] = {}
_inflight: Dict[str, asyncio.Task] = {}
_db = [None]
SEJM = "https://api.sejm.gov.pl/eli/acts"
PISTE_OAUTH = "https://oauth.piste.gouv.fr/api/oauth/token"
PISTE_API = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"


def set_db(db):
    _db[0] = db


def _get(k):
    v = _cache.get(k)
    return v[1] if v and v[0] > time.time() else None


def _put(k, v, ttl):
    _cache[k] = (time.time() + ttl, v)
    return v


def clean(h: str) -> str:
    h = re.sub(r"<(script|style)\b.*?</\1>", " ", h or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def R(j, law, art, name):
    return {"j": j, "law": law, "art": art, "name": name}


# ---------------- connectors: each returns {heading, text, url, version, status} or raises ----------------
NEURIS = "https://testphase.rechtsinformationen.bund.de"
NEURIS_NAMES = {"kschg": "Kündigungsschutzgesetz", "agg": "Allgemeines Gleichbehandlungsgesetz", "milog": "Mindestlohngesetz",
                "burlg": "Bundesurlaubsgesetz", "tzbfg": "Teilzeit- und Befristungsgesetz", "arbzg": "Arbeitszeitgesetz",
                "entgfg": "Entgeltfortzahlungsgesetz", "betrvg": "Betriebsverfassungsgesetz"}
_gii_down = [0.0]  # gesetze-im-internet.de unreachable until this time -> go straight to NeuRIS


async def _de(c: httpx.AsyncClient, ref: dict) -> dict:
    """gesetze-im-internet.de live -> NeuRIS (federal, test phase) -> bundled official XML download."""
    if time.time() > _gii_down[0]:
        try:
            return await _de_gii(c, ref)
        except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout):
            _gii_down[0] = time.time() + 600
    try:
        return await _de_neuris(c, ref)
    except Exception as e:
        bundled = _de_bundle(ref)
        if bundled:
            return bundled
        raise e


BUNDLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "de")
_bundles: Dict[str, dict] = {}


def _de_bundle(ref: dict) -> Optional[dict]:
    """Official XML from gesetze-im-internet.de, downloaded in preview and shipped with each release
    (scripts_refresh_de_official.py). Used only when the live sources cannot be reached."""
    slug = ref["law"].lower().split("_")[0]
    if slug not in _bundles:
        path = os.path.join(BUNDLE_DIR, f"{slug}.xml.zip")
        if not os.path.exists(path):
            _bundles[slug] = {}
        else:
            import zipfile
            with zipfile.ZipFile(path) as z:
                x = z.read(z.namelist()[0]).decode("utf-8")
            stand = re.search(r"<standtyp>Stand</standtyp><standkommentar>(.*?)</standkommentar>", x)
            build = re.search(r'builddate="(\d{8})', x)
            norms = {}
            for m in re.finditer(r"<norm\b.*?</norm>", x, re.S):
                e = re.search(r"<enbez>(.*?)</enbez>", m.group(0))
                if e:
                    t = re.search(r"<titel[^>]*>(.*?)</titel>", m.group(0), re.S)
                    body = re.search(r"<text[^>]*>(.*?)</text>", m.group(0), re.S)
                    norms[clean(e.group(1))] = (clean(t.group(1)) if t else "", clean(body.group(1)) if body else "")
            b = build.group(1) if build else ""
            _bundles[slug] = {"norms": norms, "stand": clean(stand.group(1)) if stand else "",
                              "built": f"{b[6:8]}/{b[4:6]}/{b[:4]}" if b else "", "built_raw": b}
    doc = _bundles[slug]
    hit = (doc.get("norms") or {}).get(f"§ {ref['art']}") or (doc.get("norms") or {}).get(f"Art {ref['art']}")
    if not hit:
        return None
    age = (time.time() - time.mktime(time.strptime(doc["built_raw"], "%Y%m%d"))) / 86400 if doc.get("built_raw") else 999
    warn = f"; WARNING: this copy is {int(age)} days old — later amendments may be missing" if age > 30 else ""
    head, text = hit
    return {"heading": f"§ {ref['art']} {head}".strip(), "text": text,
            "url": f"https://www.gesetze-im-internet.de/{ref['law']}/__{ref['art']}.html",
            "status": "repealed" if re.search(r"\(weggefallen\)|\(aufgehoben\)", head + text[:40]) else "in_force",
            "version": f"official XML from gesetze-im-internet.de as published {doc['built']} ({doc['stand']}); the live site "
                       f"could not be reached, so newer changes cannot be ruled out{warn}"}


async def _de_neuris(c: httpx.AsyncClient, ref: dict) -> dict:
    """Fallback: the Federal Government's NeuRIS legal information service (test phase). Not every law is there yet
    (e.g. the BGB is missing) — then the lookup fails honestly."""
    slug = ref["law"].lower()
    key = f"neuris:{slug}"
    doc = _get(key)
    if doc is None:
        s = await c.get(f"{NEURIS}/v1/legislation", params={"searchTerm": NEURIS_NAMES.get(slug, slug), "size": 20})
        if s.status_code != 200:
            raise RuntimeError(f"neuris search {s.status_code}")
        item = next((m["item"] for m in s.json().get("member", []) if (m["item"].get("abbreviation") or "").lower() == slug
                     and m["item"].get("legislationLegalForce") == "InForce"), None)
        if not item:
            raise RuntimeError("law not found on NeuRIS (not yet included in the test phase)")
        path = next(e["contentUrl"] for e in item["encoding"] if e["encodingFormat"] == "text/html")
        h = await c.get(NEURIS + path)
        if h.status_code != 200:
            raise RuntimeError(f"neuris text {h.status_code}")
        doc = _put(key, {"html": h.text, "path": path}, DOC_TTL)
    a = re.escape(ref["art"])
    m = re.search(rf'<h2 class="einzelvorschrift"><span class="akn-num" id="art-z{a}_bezeichnung[^"]*">', doc["html"])
    if not m:
        raise RuntimeError("provision not found on page")
    end = doc["html"].find('<h2 class="einzelvorschrift"', m.end())
    seg = doc["html"][m.start(): end if end > 0 else m.start() + 40000]
    head = clean(seg[: seg.find("</h2>")])
    text = clean(seg[seg.find("</h2>"):])
    ver = re.search(r"/(\d{4}-\d{2}-\d{2})/regelungstext", doc["path"])
    return {"heading": head, "text": text, "url": f"{NEURIS}{doc['path']}#art-z{ref['art']}",
            "status": "repealed" if re.search(r"\(weggefallen\)|\(aufgehoben\)", head + text[:40]) else "in_force",
            "version": "consolidated text from the Federal Government's NeuRIS legal information service (test phase)"
                       + (f", version of {ver.group(1)}" if ver else "")}


async def _de_gii(c: httpx.AsyncClient, ref: dict) -> dict:
    url = f"https://www.gesetze-im-internet.de/{ref['law']}/__{ref['art']}.html"
    r = await c.get(url, timeout=httpx.Timeout(20.0, connect=4.0))
    if r.status_code != 200:
        raise RuntimeError(f"gesetze-im-internet {r.status_code}")
    body = r.content.decode("iso-8859-1" if "iso-8859-1" in r.text[:600].lower() else "utf-8", "replace")
    head = clean(" ".join(re.findall(r'<span class="jn(?:enbez|titel)">(.*?)</span>', body, re.S)[:2]))
    paras = clean(" ".join(re.findall(r'<div class="jurAbsatz">(.*?)</div>', body, re.S)))
    if not head or not re.search(rf"§+\s*{re.escape(ref['art'])}\b|Art\.?\s*{re.escape(ref['art'])}\b", head):
        raise RuntimeError("provision not found on page")
    status = "repealed" if re.search(r"\(weggefallen\)|\(aufgehoben\)", head + paras[:40]) else "in_force"
    return {"heading": head, "text": paras, "url": url, "status": status,
            "version": "current consolidated text (Federal Ministry of Justice, gesetze-im-internet.de)"}


def _boe_date(d: str) -> str:
    return f"{d[6:8]}/{d[4:6]}/{d[:4]}" if d and len(d) >= 8 else ""


async def _es(c: httpx.AsyncClient, ref: dict) -> dict:
    api = "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/" + ref["law"]
    for blk in (f"a{ref['art']}", f"art{ref['art']}"):  # block ids differ between acts (the Código Civil uses 'art86')
        r = await c.get(f"{api}/texto/bloque/{blk}", headers={"Accept": "application/xml"})
        if r.status_code == 200:
            break
    if r.status_code != 200:
        raise RuntimeError(f"boe {r.status_code}")
    versions = re.findall(r'<version id_norma="([^"]+)"[^>]*fecha_vigencia="(\d*)"[^>]*>(.*?)</version>', r.text, re.S)
    if not versions:
        raise RuntimeError("article not found")
    norma, since, body = versions[-1]
    paras = [clean(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
    head, text = (paras[0], " ".join(paras[1:])) if paras else ("", "")
    if not re.match(rf"Art[ií]culo {re.escape(ref['art'])}\b", head):
        raise RuntimeError("article heading mismatch")
    meta = await c.get(f"{api}/metadatos", headers={"Accept": "application/json"})
    md = (meta.json().get("data") or [{}])[0] if meta.status_code == 200 else {}
    status = "repealed" if md.get("estatus_derogacion") == "S" or md.get("vigencia_agotada") == "S" else \
        "in_force" if md else "unknown"
    if re.fullmatch(r"\(?\s*(Derogado|Sin contenido|Suprimido)\b.*", text.strip(), re.I):
        status = "repealed"
    upd = f"; consolidation {md.get('estado_consolidacion', {}).get('texto', '').lower()}" if md else ""
    return {"heading": head, "text": text, "url": f"https://www.boe.es/buscar/act.php?id={ref['law']}#a{ref['art']}",
            "status": status, "act_title": md.get("titulo", ""),
            "version": f"consolidated text, version in force since {_boe_date(since)} (amended by {norma}){upd}"}


async def _it(c: httpx.AsyncClient, ref: dict) -> dict:
    url = f"https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:{ref['law']}~art{ref['art']}"
    r = await c.get(url)
    if r.status_code != 200:
        raise RuntimeError(f"normattiva {r.status_code}")
    i = r.text.find("bodyTesto")
    seg = clean(r.text[i:i + 30000]) if i >= 0 else ""
    seg = re.sub(r"^bodyTesto\"\s*>\s*", "", seg)
    seg = seg.split(" articolo precedente")[0].split(" nascondi Approfondimenti")[0]
    m = re.match(rf"Art\.\s*{re.escape(ref['art'])}\b\.?\s*", seg)
    if not m:
        raise RuntimeError("article not found (Normattiva returned a different article)")
    vig = re.search(r"Testo in vigore dal:\s*(?:&nbsp;)?\s*([\d\-]+)", r.text)
    rest = seg[m.end():]
    t = re.match(r"\(\(?[^)]{0,120}\)\)?\.?", rest) or re.match(r"[^.()]{3,110}?(?= 1\. )", rest)
    head = (seg[:m.end()] + (t.group(0) if t else "")).strip()
    status = "repealed" if re.search(r"\bABROGATO\b|\(\(ARTICOLO ABROGATO", seg[:400]) else "in_force"
    return {"heading": head, "text": seg[len(head):].strip(), "url": url, "status": status,
            "version": "current text (Normattiva)" + (f", act text in force from {vig.group(1)}" if vig else "")}


def _eli_key(i: str) -> Tuple[int, int]:
    p = i.split("/")
    return (int(p[1]), int(p[2])) if len(p) == 3 and p[1].isdigit() and p[2].isdigit() else (0, 0)


_pl_loading: Dict[str, asyncio.Task] = {}


async def _pl_doc(c: httpx.AsyncClient, law: str) -> dict:
    """Newest official consolidated text (tekst jednolity) of a Polish act, as plain text. Cached 7 days; one shared
    download per act however many articles are asked for at once."""
    key = f"pl-doc:{law}"
    hit = _get(key)
    if hit:
        return hit
    task = _pl_loading.get(key)
    if task is None or task.done() and task.exception() is not None:
        task = _pl_loading[key] = asyncio.ensure_future(_pl_load(law, key))
    return await asyncio.shield(task)


async def _pl_load(law: str, key: str) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA, follow_redirects=True) as c:
        return await _pl_fetch(c, law, key)


async def _pl_fetch(c: httpx.AsyncClient, law: str, key: str) -> dict:
    r = await c.get(f"{SEJM}/{law}")
    if r.status_code != 200:
        raise RuntimeError(f"sejm {r.status_code}")
    base = r.json()
    cons = sorted((x["id"] for x in base.get("references", {}).get("Inf. o tekście jednolitym", [])), key=_eli_key)
    src = cons[-1] if cons else law
    meta = (await c.get(f"{SEJM}/{src}")).json() if src != law else base
    files = {t["type"]: t["fileName"] for t in meta.get("texts", [])}
    typ = next((t for t in ("T", "U", "O", "I") if t in files), None)
    if not typ:
        raise RuntimeError("no text file")
    pdf = await c.get(f"{SEJM}/{src}/text/{typ}/{files[typ]}")
    if pdf.status_code != 200:
        raise RuntimeError(f"sejm pdf {pdf.status_code}")
    import fitz
    with fitz.open(stream=pdf.content, filetype="pdf") as d:
        text = re.sub(r"\s+", " ", " ".join(p.get_text() for p in d))
    later = [x["id"] for x in base.get("references", {}).get("Akty zmieniające", []) if _eli_key(x["id"]) > _eli_key(src)]
    return _put(key, {"text": text, "src": src, "title": base.get("title", ""), "in_force": base.get("inForce"),
                      "cons_title": meta.get("title", ""), "later": later, "file": f"{SEJM}/{src}/text/{typ}/{files[typ]}"},
                DOC_TTL)


async def _pl(c: httpx.AsyncClient, ref: dict) -> dict:
    doc = await _pl_doc(c, ref["law"])
    m = re.search(rf"Art\. {re.escape(ref['art'])}\. ", doc["text"])
    if not m:
        raise RuntimeError("article not found")
    nxt = re.search(r"Art\. \d+[a-z]?(?:\[\w+\])?\. ", doc["text"][m.end():])
    seg = doc["text"][m.start(): m.end() + (nxt.start() if nxt else 2500)]
    status = "repealed" if re.match(r"Art\. \S+\. \(uchylony\)", seg) else \
        "in_force" if doc["in_force"] == "IN_FORCE" else "unknown"
    later = (f"; WARNING: {len(doc['later'])} amending act(s) were published after this consolidated text, so this "
             "article may since have changed") if doc["later"] else ""
    return {"heading": f"Art. {ref['art']}", "text": seg[len(f'Art. {ref["art"]}. '):], "url": f"{doc['file']}#art-{ref['art']}",
            "status": status, "act_title": doc["title"],
            "version": f"official consolidated text {doc['src']} (Sejm ELI){later}", "changes_pending": bool(doc["later"])}


async def _piste_token(c: httpx.AsyncClient) -> str:
    hit = _get("piste-token")
    if hit:
        return hit
    r = await c.post(PISTE_OAUTH, data={"grant_type": "client_credentials", "scope": "openid",
                                        "client_id": os.environ["LEGIFRANCE_CLIENT_ID"],
                                        "client_secret": os.environ["LEGIFRANCE_CLIENT_SECRET"]})
    if r.status_code != 200:
        raise RuntimeError(f"piste oauth {r.status_code}")
    return _put("piste-token", r.json()["access_token"], int(r.json().get("expires_in", 3600)) - 120)


def france_enabled() -> bool:
    return bool(os.environ.get("LEGIFRANCE_CLIENT_ID") and os.environ.get("LEGIFRANCE_CLIENT_SECRET"))


async def _fr(c: httpx.AsyncClient, ref: dict) -> dict:
    """Légifrance (PISTE API). Needs LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET; untested until keys exist."""
    if not france_enabled():
        raise RuntimeError("Légifrance keys not configured")
    h = {"Authorization": f"Bearer {await _piste_token(c)}", "Accept": "application/json"}
    body = {"fond": "CODE_DATE", "recherche": {
        "champs": [{"typeChamp": "NUM_ARTICLE", "operateur": "ET",
                    "criteres": [{"typeRecherche": "EXACTE", "valeur": ref["art"], "operateur": "ET"}]}],
        "filtres": [{"facette": "NOM_CODE", "valeurs": [ref["law"]]},
                    {"facette": "DATE_VERSION", "singleDate": int(time.time() * 1000)}],
        "pageNumber": 1, "pageSize": 3, "operateur": "ET", "sort": "PERTINENCE", "typePagination": "ARTICLE"}}
    s = await c.post(f"{PISTE_API}/search", json=body, headers=h)
    if s.status_code != 200:
        raise RuntimeError(f"legifrance search {s.status_code}")
    ids = re.findall(r'"id"\s*:\s*"(LEGIARTI\d+)"', s.text)
    if not ids:
        raise RuntimeError("article not found")
    a = await c.post(f"{PISTE_API}/consult/getArticle", json={"id": ids[0]}, headers=h)
    art = (a.json() or {}).get("article") or {}
    if a.status_code != 200 or art.get("num") != ref["art"]:
        raise RuntimeError("article mismatch")
    etat = (art.get("etat") or "").upper()
    since = time.strftime("%d/%m/%Y", time.gmtime(int(art["dateDebut"]) / 1000)) if art.get("dateDebut") else ""
    return {"heading": f"Article {ref['art']} — {ref['law']}", "text": clean(art.get("texteHtml") or art.get("texte") or ""),
            "url": f"https://www.legifrance.gouv.fr/codes/article_lc/{ids[0]}",
            "status": "in_force" if etat.startswith("VIGUEUR") else "repealed" if etat.startswith("ABROGE") else "unknown",
            "version": f"Légifrance consolidated text, version in force from {since}" if since else "Légifrance consolidated text"}


async def _us(c: httpx.AsyncClient, ref: dict) -> dict:
    kind, title = ref["law"].split(":")
    if kind == "usc":
        r = await c.get(f"https://www.govinfo.gov/link/uscode/{title}/{ref['art']}?link-type=html")
        if r.status_code != 200:
            raise RuntimeError(f"govinfo {r.status_code}")
        t = re.sub(r"[\u2010-\u2015]", "-", clean(r.text))
        m = re.search(rf"§\s?{re.escape(ref['art'])}\.\s", t)
        if not m:
            raise RuntimeError("section not found")
        ed = re.search(r"USCODE-(\d{4})", str(r.url))
        hm = re.match(r"§\s?\S+\.\s+[^.(]{2,110}?(?=\s\(a\)|\.\s)", t[m.start():])
        head = hm.group(0) if hm else t[m.start(): m.end()]
        return {"heading": head, "text": t[m.start() + len(head):], "url": str(r.url),
                "status": "repealed" if re.search(r"\b(Repealed|Omitted|Transferred)\b", head) else "in_force",
                "version": f"U.S. Code {ed.group(1) if ed else ''} annual edition (GPO govinfo) — amendments enacted after "
                           "that edition may not be shown"}
    titles = _get("ecfr-dates")
    if not titles:
        tj = await c.get("https://www.ecfr.gov/api/versioner/v1/titles.json")
        titles = _put("ecfr-dates", {str(x["number"]): x["up_to_date_as_of"] for x in tj.json()["titles"]}, 86400)
    day = titles[title]
    r = await c.get(f"https://www.ecfr.gov/api/versioner/v1/full/{day}/title-{title}.xml", params={"section": ref["art"]})
    if r.status_code != 200:
        raise RuntimeError(f"ecfr {r.status_code}")
    head = clean((re.search(r"<HEAD>(.*?)</HEAD>", r.text, re.S) or [None, ""])[1])
    if ref["art"] not in head:
        raise RuntimeError("section not found")
    return {"heading": head, "text": clean(re.sub(r"<HEAD>.*?</HEAD>", " ", r.text, count=1, flags=re.S)),
            "url": f"https://www.ecfr.gov/current/title-{title}/section-{ref['art']}", "status": "in_force",
            "version": f"eCFR, up to date as of {day} (official editorial compilation)"}


def _section(t: str, start_rx: str, next_rx: str, cap: int = 6000) -> Optional[str]:
    m = re.search(start_rx, t)
    if not m:
        return None
    nxt = re.search(next_rx, t[m.end():])
    return t[m.start(): m.end() + (nxt.start() if nxt else cap)]


async def _us_tx(c: httpx.AsyncClient, ref: dict) -> dict:
    """Texas Legislature's official statute files (tcss.legis.texas.gov), one HTML file per code chapter."""
    chapter = ref["art"].split(".")[0]
    url = f"https://tcss.legis.texas.gov/resources/{ref['law']}/htm/{ref['law']}.{chapter}.htm"
    key = f"tx:{url}"
    t = _get(key)
    if t is None:
        r = await c.get(url)
        if r.status_code != 200:
            raise RuntimeError(f"texas {r.status_code}")
        t = _put(key, clean(r.text), DOC_TTL)
    seg = _section(t, rf"Sec\. {re.escape(ref['art'])}\. ", r"\sSec\. \d+[A-Z]?\.\d+[A-Z]?\. ")
    if not seg:
        raise RuntimeError("section not found")
    head = re.match(r"Sec\. \S+ [A-Z0-9 ,;'\-]+?\.", seg)
    head = head.group(0) if head else f"Sec. {ref['art']}"
    return {"heading": head, "text": seg[len(head):].strip(), "url": f"{url}#{ref['art']}", "status": "in_force",
            "version": "current statute text published by the Texas Legislative Council (tcss.legis.texas.gov)"}


async def _us_fl(c: httpx.AsyncClient, ref: dict) -> dict:
    """Florida Senate's official statutes site, current edition."""
    year = time.gmtime().tm_year
    for y in (year, year - 1):
        url = f"https://www.flsenate.gov/Laws/Statutes/{y}/{ref['art']}"
        r = await c.get(url)
        if r.status_code == 200 and ref["art"] in r.text:
            publisher = "Florida Senate"
            break
    else:  # Florida Legislature's Online Sunshine — same official statutes when flsenate.gov is down
        ch, sec = ref["art"].split(".")
        lo = int(ch) // 100 * 100
        url = (f"https://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL={lo:04d}-{lo + 99:04d}/"
               f"{int(ch):04d}/Sections/{int(ch):04d}.{sec}.html")
        r = await c.get(url)
        m = re.search(r"(\d{4}) Florida Statutes", r.text) if r.status_code == 200 else None
        if not m or ref["art"] not in r.text:
            raise RuntimeError(f"florida {r.status_code}")
        y, publisher = m.group(1), "Florida Legislature, Online Sunshine"
    t = clean(r.text)
    seg = _section(t, rf"{re.escape(ref['art'])}\s+[A-Z][^—]{{3,140}}—", r"History\.\s?—|Note\.\s?—", 6000)
    if not seg:
        raise RuntimeError("section not found")
    head, _, body = seg.partition("—")
    return {"heading": head.strip(), "text": body.strip(), "url": url, "status": "in_force",
            "version": f"Florida Statutes {y} edition ({publisher}) — changes after that edition may not be included"}


def ny_enabled() -> bool:
    return bool(os.environ.get("NYSENATE_API_KEY"))


async def _us_ny(c: httpx.AsyncClient, ref: dict) -> dict:
    """New York Senate Open Legislation API (free key: NYSENATE_API_KEY). Untested until the key exists."""
    if not ny_enabled():
        raise RuntimeError("New York Open Legislation key not configured")
    r = await c.get(f"https://legislation.nysenate.gov/api/3/laws/{ref['law']}/{ref['art']}",
                    params={"key": os.environ["NYSENATE_API_KEY"]})
    if r.status_code != 200 or not r.json().get("success"):
        raise RuntimeError(f"ny openleg {r.status_code}")
    res = r.json()["result"]
    if str(res.get("locationId", "")).upper() != ref["art"].upper():
        raise RuntimeError("section mismatch")
    return {"heading": f"§ {res.get('docLevelId') or ref['art']} {res.get('title', '')}".strip(), "text": clean(res.get("text", "")),
            "url": f"https://www.nysenate.gov/legislation/laws/{ref['law']}/{ref['art']}", "status": "in_force",
            "version": f"NY Senate Open Legislation, active date {res.get('activeDate', 'not stated')}"}


CONNECTORS = {"DE": _de, "ES": _es, "IT": _it, "PL": _pl, "FR": _fr, "US": _us, "US-TX": _us_tx, "US-FL": _us_fl, "US-NY": _us_ny}
SOURCE_NAME = {"DE": "gesetze-im-internet.de / NeuRIS, Federal Ministry of Justice", "ES": "BOE — Agencia Estatal Boletín Oficial del Estado",
               "IT": "Normattiva — Italian Government", "PL": "Dziennik Ustaw via Sejm ELI API", "FR": "Légifrance (DILA)",
               "US": "US Government Publishing Office / eCFR", "US-TX": "Texas Legislative Council",
               "US-FL": "Florida Senate", "US-NY": "New York State Senate Open Legislation"}


async def _record(ref: dict, res: dict) -> None:
    """Version history: fingerprint each retrieved provision; a changed fingerprint is queued for professional review."""
    db = _db[0]
    if db is None or not res.get("text"):
        return
    now = datetime.now(timezone.utc).isoformat()
    h = hashlib.sha256(re.sub(r"\s+", " ", res["text"]).encode()).hexdigest()[:24]
    rid = f"{ref['j']}:{ref['law']}:{ref['art']}"
    try:
        old = await db.legal_source_records.find_one({"_id": rid}, {"hash": 1})
        upd = {"$set": {"jurisdiction": ref["j"], "label": res.get("label") or ref.get("name"), "url": res["url"],
                        "status": res.get("status"), "version": res.get("version"), "hash": h, "last_checked": now,
                        "cached": {k: res.get(k) for k in ("heading", "text", "url", "status", "version", "label", "act_title",
                                                             "changes_pending", "retrieved")}, "cached_ts": time.time()},
               "$setOnInsert": {"first_seen": now}}
        if old and old.get("hash") != h:
            upd["$set"]["last_changed"] = now
            upd["$push"] = {"history": {"$each": [{"hash": old.get("hash"), "replaced_at": now}], "$slice": -10}}
            await db.legal_source_changes.insert_one({
                "record_id": rid, "jurisdiction": ref["j"], "label": res.get("label") or ref.get("name"), "url": res["url"],
                "detected_at": now, "status": "needs_review", "old_hash": old.get("hash"), "new_hash": h,
                "note": "Official wording changed since Lex last read it. Not interpreted — a qualified reviewer must check "
                        "whether any guidance is affected."})
        await db.legal_source_records.update_one({"_id": rid}, upd, upsert=True)
    except Exception as e:
        logger.info("source record failed %s: %r", rid, e)


def _label(ref: dict, res: dict) -> str:
    return f"{ref.get('name') or ref['law']} — {res.get('heading') or ref['art']}"


_slots: Dict[str, asyncio.Semaphore] = {}


async def _fetch_once(ref: dict) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=UA, follow_redirects=True) as c:
        return await CONNECTORS[ref["j"]](c, ref)


async def _download(ref: dict, key: str) -> dict:
    t0 = time.time()
    slot = _slots.setdefault(f"{ref['j']}:{id(asyncio.get_running_loop())}", asyncio.Semaphore(3))  # be polite to each source
    try:
        async with slot:
            try:
                res = await _fetch_once(ref)
            except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout):
                await asyncio.sleep(0.5)
                res = await _fetch_once(ref)  # one retry for transient network failures
        res["text"] = res.get("text", "")[:TEXT_CAP]
        res["label"] = _label(ref, res)
        res["retrieved"] = time.strftime("%d %B %Y", time.gmtime())
        res["ms"] = int((time.time() - t0) * 1000)
        await _record(ref, res)
        return _put(key, {**ref, **res}, TTL)
    except Exception as e:
        logger.info("national lookup failed %s %s %s after %.1fs: %r", ref["j"], ref["law"], ref["art"], time.time() - t0, e)
        return _put(key, {**ref, "failed": True, "error": str(e)[:120]}, FAIL_TTL)
    finally:
        _inflight.pop(key, None)


async def read(ref: dict, wait: float = WAIT) -> dict:
    """Cached 7 days. Uncached texts download in the background; the answer waits at most `wait` seconds."""
    key = f"nat:{ref['j']}:{ref['law']}:{ref['art']}"
    hit = _get(key)
    if hit is not None:
        return hit
    if _db[0] is not None:  # survives restarts: last official retrieval stored with its version record
        try:
            doc = await _db[0].legal_source_records.find_one({"_id": f"{ref['j']}:{ref['law']}:{ref['art']}"}, {"cached": 1, "cached_ts": 1})
            if doc and doc.get("cached") and time.time() - doc.get("cached_ts", 0) < TTL:
                return _put(key, {**ref, **doc["cached"]}, TTL - (time.time() - doc["cached_ts"]))
        except Exception as e:
            logger.info("source record read failed: %r", e)
    task = _inflight.get(key) or _inflight.setdefault(key, asyncio.ensure_future(_download(ref, key)))
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=wait)
    except asyncio.TimeoutError:
        return {**ref, "failed": True, "pending": True}


async def boe_find(title: str) -> Optional[str]:
    """BOE identifier for a Spanish law title (official BOE open-data search)."""
    q = '{"query":{"query_string":{"query":"titulo:(%s)"}}}' % " AND ".join(re.findall(r"\w{4,}", title)[:6])
    async with httpx.AsyncClient(timeout=8.0, headers=UA) as c:
        r = await c.get("https://www.boe.es/datosabiertos/api/legislacion-consolidada", params={"query": q, "limit": 3},
                        headers={"Accept": "application/json"})
    data = r.json().get("data") or [] if r.status_code == 200 else []
    return data[0]["identificador"] if data else None


# ---------------- deterministic topic map (multilingual triggers) ----------------
TOPIC_RX = {
    "housing": r"evict|landlord|tenan|lease\b|rent(?:ed|al|ing)?\b|notice to (?:quit|leave|vacate)|move out|Vermieter|Mieter|"
               r"Mietvertrag|Eigenbedarf|Räumung|Kündigung (?:der|meiner) Wohnung|arrendador|arrendatario|inquilino|alquiler|"
               r"desahucio|casero|propriétaire|locataire|\b(?:mon|le|du) bail\b|expulsion|sfratto|disdetta|locator|"
               r"locazione|affitto|inquilin|wynajm|najem|najm|lokator|eksmisj|senhorio|arrendament|despejo|inquilino",
    "deposit": r"deposit|Kaution|fianza|dépôt de garantie|caution\b|cauzion|kaucj|caução",
    "repairs": r"repair|damp|mould|mold|leak|heating|Mietminderung|Mangel der Wohnung|Schimmel|reparaci|humedad|moisissure|"
               r"réparation|riparazion|muffa|naprawa|wilgo|grzyb|reparaç|humidade",
    "faulty_goods": r"faulty|broken|\bbroke\b|stopped working|doesn'?t work|defective|kaputt|funktioniert nicht|no funciona|"
                    r"ne (?:marche|fonctionne) plus|non funziona|nie działa|zepsu|não funciona|avariad|not as described|refund|warranty|guarantee|Mangel|defekt|Gewährleistung|"
                    r"defectuos|garantía|devoluci|défectueux|garantie|remboursement|difettos|garanzia|rimborso|wadliw|"
                    r"reklamacj|rękojmi|zwrot pieniędzy|defeituos|garantia|reembolso",
    "online_cancel": r"cancel (?:my|an?|the) order|online (?:order|purchase)|bought online|withdraw from|cooling.off|"
                     r"Widerruf|desistimiento|rétractation|recesso|odstąpi|zwrot towaru|direito de livre resolução",
    "dismissal": r"dismiss|sacked|fired\b|let go|lost my job|terminat\w* (?:my|me)|Kündigung (?:durch|vom|meines) "
                 r"Arbeit|Arbeitgeber.{0,40}gekündigt|entlassen|Kündigungsschutz|despid|licenciement|licencié|licenzia|zwolnien|zwolnion|wypowiedzenie "
                 r"umowy o pracę|zwolni|wypowiedzeni[a-ząćęłńóśźż]*(?![a-ząćęłńóśźż]| (?:umowy )?najmu)|sąd\w* pracy|odwołani\w* od wypowiedzenia|despedimento|despedid",
    "wages": r"unpaid wage|not (?:been )?paid|wages|overtime|minimum wage|Lohn|Gehalt|Mindestlohn|salario|nómina|"
             r"salaire|stipendio|retribuzion|wynagrodzen|pensja|salário|horas extra",
    "discrimination": r"discriminat|harass|Diskriminier|Belästigung|discrimin|acoso|harcèlement|molestie|dyskrymin|"
                      r"mobbing|molestowan|assédio",
    "family": r"divorc|separat(?:ion|ed)|custody|child support|alimony|spousal (?:support|maintenance)|Scheidung|getrennt|"
              r"Trennungsjahr|Unterhalt|Sorgerecht|divorcio|custodia|pensión (?:alimenticia|compensatoria)|divorzio|"
              r"separazione|affidamento|assegno (?:di mantenimento|divorzile)|rozwód|rozwodu|alimenty|władza rodzicielska|"
              r"opieka nad dzieckiem|divórcio|regulação (?:do exercício )?das responsabilidades parentais|pensão de alimentos",
    "inheritance": r"inherit|\bwill\b(?= (?:says|leaves|left|is|was))|my (?:late|deceased)|estate of|probate|executor|"
                   r"Erbe\b|Erben|Erbschaft|Testament|Pflichtteil|Nachlass|ausschlagen|herencia|heredero|testamento|legítima|"
                   r"eredità|erede|successione|legittima|spadek|spadku|zachowek|testament|herança|herdeiro",
    "immigration": r"visa\b|residence permit|work permit|deport|asylum|green card|citizenship|naturali[sz]|immigra|"
                   r"Aufenthaltstitel|Aufenthaltserlaubnis|Niederlassungserlaubnis|Visum|Abschiebung|Einbürgerung|"
                   r"permiso de residencia|autorización de residencia|arraigo|nacionalidad española|expulsión|"
                   r"permesso di soggiorno|cittadinanza italiana|espulsione|karta pobytu|zezwolenie na pobyt|wiza|"
                   r"obywatelstwo|autorização de residência|nacionalidade",
    "debt_collection": r"debt collect|collection agency|collector",
    "credit_report": r"credit report|credit bureau|credit score|equifax|experian|transunion",
    "family_leave": r"family leave|fmla|medical leave|maternity leave|paternity leave",
    "card_dispute": r"credit card (?:charge|dispute|billing)|billing error|chargeback",
}
_TOPIC_C = {k: re.compile(v, re.I) for k, v in TOPIC_RX.items()}
# US topics that are governed by state law — never answered with federal law.
US_STATE_TOPICS = {"housing", "deposit", "repairs", "faulty_goods", "online_cancel", "dismissal", "family", "inheritance"}

BGB, KSCHG, AGG = "bgb", "kschg", "agg"
LAU, TRLGDCU, ET, LRJS = "BOE-A-1994-26003", "BOE-A-2007-20555", "BOE-A-2015-11430", "BOE-A-2011-15936"
CC_IT, CONS_IT = "regio.decreto:1942-03-16;262:2", "decreto.legislativo:2005-09-06;206"
KC, LOK, PK_CONS, KP = "DU/1964/93", "DU/2001/733", "DU/2014/827", "DU/1974/141"
MAP = {
    "DE": {
        "family": [R("DE", BGB, "1565", "BGB"), R("DE", BGB, "1566", "BGB"), R("DE", BGB, "1570", "BGB"), R("DE", BGB, "1671", "BGB")],
        "inheritance": [R("DE", BGB, "1924", "BGB"), R("DE", BGB, "1931", "BGB"), R("DE", BGB, "2303", "BGB"), R("DE", BGB, "1944", "BGB")],
        "immigration": [R("DE", "aufenthg_2004", "4", "AufenthG"), R("DE", "aufenthg_2004", "9", "AufenthG"),
                        R("DE", "aufenthg_2004", "18b", "AufenthG")],
        "housing": [R("DE", BGB, "573", "BGB"), R("DE", BGB, "573c", "BGB"), R("DE", BGB, "543", "BGB"), R("DE", BGB, "574", "BGB")],
        "deposit": [R("DE", BGB, "551", "BGB")],
        "repairs": [R("DE", BGB, "535", "BGB"), R("DE", BGB, "536", "BGB")],
        "faulty_goods": [R("DE", BGB, "437", "BGB"), R("DE", BGB, "439", "BGB"), R("DE", BGB, "438", "BGB")],
        "online_cancel": [R("DE", BGB, "312g", "BGB"), R("DE", BGB, "355", "BGB"), R("DE", BGB, "357", "BGB")],
        "dismissal": [R("DE", KSCHG, "1", "KSchG"), R("DE", KSCHG, "4", "KSchG"), R("DE", BGB, "622", "BGB"),
                      R("DE", BGB, "623", "BGB")],
        "wages": [R("DE", "milog", "1", "MiLoG"), R("DE", BGB, "611a", "BGB")],
        "discrimination": [R("DE", AGG, "1", "AGG"), R("DE", AGG, "7", "AGG"), R("DE", AGG, "15", "AGG")],
    },
    "ES": {
        "family": [R("ES", "BOE-A-1889-4763", "86", "Código Civil"), R("ES", "BOE-A-1889-4763", "90", "Código Civil"), R("ES", "BOE-A-1889-4763", "97", "Código Civil")],
        "inheritance": [R("ES", "BOE-A-1889-4763", "807", "Código Civil"), R("ES", "BOE-A-1889-4763", "808", "Código Civil"), R("ES", "BOE-A-1889-4763", "930", "Código Civil"),
                        R("ES", "BOE-A-1889-4763", "1008", "Código Civil")],
        "immigration": [R("ES", "BOE-A-2000-544", "31", "Ley Orgánica 4/2000 de extranjería"), R("ES", "BOE-A-2000-544", "32", "Ley Orgánica 4/2000 de extranjería")],
        "housing": [R("ES", LAU, "9", "Ley de Arrendamientos Urbanos"), R("ES", LAU, "10", "Ley de Arrendamientos Urbanos"),
                    R("ES", LAU, "27", "Ley de Arrendamientos Urbanos")],
        "deposit": [R("ES", LAU, "36", "Ley de Arrendamientos Urbanos")],
        "repairs": [R("ES", LAU, "21", "Ley de Arrendamientos Urbanos")],
        "faulty_goods": [R("ES", TRLGDCU, "114", "Ley General para la Defensa de los Consumidores"),
                         R("ES", TRLGDCU, "118", "Ley General para la Defensa de los Consumidores"),
                         R("ES", TRLGDCU, "120", "Ley General para la Defensa de los Consumidores")],
        "online_cancel": [R("ES", TRLGDCU, "102", "Ley General para la Defensa de los Consumidores"),
                          R("ES", TRLGDCU, "104", "Ley General para la Defensa de los Consumidores")],
        "dismissal": [R("ES", ET, "59", "Estatuto de los Trabajadores"), R("ES", ET, "55", "Estatuto de los Trabajadores"),
                      R("ES", ET, "56", "Estatuto de los Trabajadores"), R("ES", LRJS, "103", "Ley Reguladora de la Jurisdicción Social")],
        "wages": [R("ES", ET, "29", "Estatuto de los Trabajadores"), R("ES", ET, "27", "Estatuto de los Trabajadores")],
        "discrimination": [R("ES", ET, "17", "Estatuto de los Trabajadores")],
    },
    "IT": {
        "family": [R("IT", "legge:1970-12-01;898", "3", "Legge 898/1970 (divorzio)"), R("IT", "legge:1970-12-01;898", "5", "Legge 898/1970 (divorzio)"),
                   R("IT", CC_IT, "151", "Codice civile")],
        "inheritance": [R("IT", CC_IT, "536", "Codice civile"), R("IT", CC_IT, "565", "Codice civile"), R("IT", CC_IT, "480", "Codice civile")],
        "immigration": [R("IT", "decreto.legislativo:1998-07-25;286", "5", "Testo unico immigrazione"),
                        R("IT", "decreto.legislativo:1998-07-25;286", "9", "Testo unico immigrazione")],
        "housing": [R("IT", "legge:1998-12-09;431", "2", "Legge 431/1998"), R("IT", "legge:1998-12-09;431", "3", "Legge 431/1998"),
                    R("IT", CC_IT, "1571", "Codice civile")],
        "deposit": [R("IT", "legge:1978-07-27;392", "11", "Legge 392/1978")],
        "repairs": [R("IT", CC_IT, "1575", "Codice civile"), R("IT", CC_IT, "1576", "Codice civile")],
        "faulty_goods": [R("IT", CONS_IT, "133", "Codice del consumo"), R("IT", CONS_IT, "130", "Codice del consumo")],
        "online_cancel": [R("IT", CONS_IT, "52", "Codice del consumo"), R("IT", CONS_IT, "54", "Codice del consumo")],
        "dismissal": [R("IT", "legge:1966-07-15;604", "6", "Legge 604/1966"), R("IT", "legge:1966-07-15;604", "2", "Legge 604/1966"),
                      R("IT", "decreto.legislativo:2015-03-04;23", "3", "D.Lgs. 23/2015")],
        "wages": [R("IT", CC_IT, "2099", "Codice civile")],
        "discrimination": [R("IT", "decreto.legislativo:2006-04-11;198", "25", "Codice delle pari opportunità")],
    },
    "PL": {
        "family": [R("PL", "DU/1964/59", "56", "Kodeks rodzinny i opiekuńczy"), R("PL", "DU/1964/59", "58", "Kodeks rodzinny i opiekuńczy"),
                   R("PL", "DU/1964/59", "60", "Kodeks rodzinny i opiekuńczy")],
        "inheritance": [R("PL", KC, "931", "Kodeks cywilny"), R("PL", KC, "991", "Kodeks cywilny"), R("PL", KC, "1015", "Kodeks cywilny")],
        "immigration": [R("PL", "DU/2013/1650", "98", "Ustawa o cudzoziemcach"), R("PL", "DU/2013/1650", "195", "Ustawa o cudzoziemcach")],
        "housing": [R("PL", LOK, "11", "Ustawa o ochronie praw lokatorów"), R("PL", KC, "673", "Kodeks cywilny"),
                    R("PL", KC, "688", "Kodeks cywilny")],
        "deposit": [R("PL", LOK, "6", "Ustawa o ochronie praw lokatorów")],
        "repairs": [R("PL", KC, "662", "Kodeks cywilny"), R("PL", KC, "664", "Kodeks cywilny")],
        "faulty_goods": [R("PL", PK_CONS, "43c", "Ustawa o prawach konsumenta"), R("PL", PK_CONS, "43d", "Ustawa o prawach konsumenta"),
                         R("PL", PK_CONS, "43e", "Ustawa o prawach konsumenta")],
        "online_cancel": [R("PL", PK_CONS, "27", "Ustawa o prawach konsumenta"), R("PL", PK_CONS, "38", "Ustawa o prawach konsumenta")],
        "dismissal": [R("PL", KP, "264", "Kodeks pracy"), R("PL", KP, "30", "Kodeks pracy"), R("PL", KP, "45", "Kodeks pracy"),
                      R("PL", KP, "36", "Kodeks pracy")],
        "wages": [R("PL", KP, "85", "Kodeks pracy")],
        "discrimination": [R("PL", KP, "18[3a]", "Kodeks pracy")],
    },
    "FR": {
        "dismissal": [R("FR", "Code du travail", "L1232-1", "Code du travail"), R("FR", "Code du travail", "L1234-1", "Code du travail"),
                      R("FR", "Code du travail", "L1471-1", "Code du travail")],
        "faulty_goods": [R("FR", "Code de la consommation", "L217-3", "Code de la consommation"),
                         R("FR", "Code de la consommation", "L217-8", "Code de la consommation")],
        "online_cancel": [R("FR", "Code de la consommation", "L221-18", "Code de la consommation")],
        "repairs": [R("FR", "Code civil", "1719", "Code civil"), R("FR", "Code civil", "1720", "Code civil")],
        "wages": [R("FR", "Code du travail", "L3231-2", "Code du travail")],
        "discrimination": [R("FR", "Code du travail", "L1132-1", "Code du travail")],
    },
    "US": {
        "immigration": [R("US", "usc:8", "1158", "Immigration and Nationality Act (8 U.S.C.)"),
                        R("US", "usc:8", "1229b", "Immigration and Nationality Act (8 U.S.C.)"),
                        R("US", "usc:8", "1255", "Immigration and Nationality Act (8 U.S.C.)")],
        "debt_collection": [R("US", "usc:15", "1692g", "Fair Debt Collection Practices Act (15 U.S.C.)"),
                            R("US", "usc:15", "1692c", "Fair Debt Collection Practices Act (15 U.S.C.)"),
                            R("US", "usc:15", "1692k", "Fair Debt Collection Practices Act (15 U.S.C.)")],
        "credit_report": [R("US", "usc:15", "1681i", "Fair Credit Reporting Act (15 U.S.C.)")],
        "wages": [R("US", "usc:29", "206", "Fair Labor Standards Act (29 U.S.C.)"), R("US", "usc:29", "207", "Fair Labor Standards Act (29 U.S.C.)"),
                  R("US", "usc:29", "255", "Portal-to-Portal Act (29 U.S.C.)")],
        "discrimination": [R("US", "usc:42", "2000e-2", "Civil Rights Act 1964, Title VII (42 U.S.C.)"),
                           R("US", "usc:42", "2000e-5", "Civil Rights Act 1964, Title VII (42 U.S.C.)")],
        "family_leave": [R("US", "usc:29", "2612", "Family and Medical Leave Act (29 U.S.C.)")],
        "card_dispute": [R("US", "cfr:12", "1026.13", "Regulation Z (12 CFR)")],
    },
}
STATE_MAP = {
    "TX": {"deposit": [R("US-TX", "PR", "92.103", "Texas Property Code"), R("US-TX", "PR", "92.104", "Texas Property Code"),
                       R("US-TX", "PR", "92.109", "Texas Property Code")],
           "housing": [R("US-TX", "PR", "24.005", "Texas Property Code"), R("US-TX", "PR", "91.001", "Texas Property Code")],
           "repairs": [R("US-TX", "PR", "92.052", "Texas Property Code"), R("US-TX", "PR", "92.056", "Texas Property Code")]},
    "FL": {"deposit": [R("US-FL", "FS", "83.49", "Florida Statutes")],
           "housing": [R("US-FL", "FS", "83.56", "Florida Statutes"), R("US-FL", "FS", "83.57", "Florida Statutes")],
           "repairs": [R("US-FL", "FS", "83.51", "Florida Statutes"), R("US-FL", "FS", "83.60", "Florida Statutes")]},
    "NY": {"deposit": [R("US-NY", "GOB", "7-108", "NY General Obligations Law")],
           "housing": [R("US-NY", "RPP", "226-C", "NY Real Property Law"), R("US-NY", "RPA", "711", "NY Real Property Actions and Proceedings Law")],
           "repairs": [R("US-NY", "RPP", "235-B", "NY Real Property Law")]},
}


def state_enabled(st: str) -> bool:
    return st in ("TX", "FL") or (st == "NY" and ny_enabled())


def pick_state(st: str, text: str) -> List[dict]:
    if not state_enabled(st):
        return []
    out = []
    for t in topics(text):
        for r in STATE_MAP.get(st, {}).get(t, []):
            if r not in out:
                out.append({**r, "topic": t})
    return out[:MAX_REFS]


MAX_REFS = 4


def topics(text: str) -> List[str]:
    return [k for k, rx in _TOPIC_C.items() if rx.search(text or "")]


def pick(j: str, text: str) -> List[dict]:
    out = []
    for t in topics(text):
        for r in MAP.get(j, {}).get(t, []):
            if r not in out:
                out.append({**r, "topic": t})
    return out[:MAX_REFS]


async def prewarm():
    """Fill the cache in the background so customers rarely wait (free official sources). Each jurisdiction runs in
    parallel, one request at a time; deadline (dismissal) provisions go first."""
    await asyncio.sleep(20)

    async def one(j: str, m: dict):
        refs = [r for rs in m.values() for r in rs]
        refs.sort(key=lambda r: 0 if r in m.get("dismissal", []) else 1)
        for r in refs:
            await read(r, wait=60)
    maps = [(j, m) for j, m in MAP.items() if j != "FR" or france_enabled()]
    maps += [(f"US-{st}", m) for st, m in STATE_MAP.items() if state_enabled(st)]
    await asyncio.gather(*(one(j, m) for j, m in maps), return_exceptions=True)


# ---------------- national citations in Lex's answer: checked against the official source ----------------
_DE_LAWS = "BGB|KSchG|AGG|MiLoG|BetrVG|StGB|ZPO|HGB|BUrlG|ArbZG|TzBfG|EntgFG|MuSchG|BEEG|WEG|BetrKV|StPO|VVG"
_CITE = [
    ("DE", re.compile(rf"§§?\s?(\d+[a-z]?)(?:\s+(?:Abs\.|Absatz|S\.|Satz|Nr\.)\s?\d+\w?)*\s+({_DE_LAWS})\b"),
     lambda m: (m.group(2).lower(), m.group(1))),
    ("US", re.compile(r"\b(\d{1,2})\s+U\.?\s?S\.?\s?C\.?\s*(?:§+|[Ss]ec(?:tion|\.)?)?\s?(\d+[a-z]?(?:[\-–]\d+[a-z]?)?)\b"),
     lambda m: (f"usc:{m.group(1)}", m.group(2).replace("–", "-"))),
    ("US", re.compile(r"\b(\d{1,2})\s+C\.?\s?F\.?\s?R\.?\s*§?\s?(\d+\.\d+)\b"), lambda m: (f"cfr:{m.group(1)}", m.group(2))),
    ("PL", re.compile(r"\bart\.\s?(\d+(?:\[\w+\]|[a-z])?)(?:\s*§\s*\d+)*(?:\s+pkt\s+\d+)?\s+(k\.p\.|Kodeksu pracy|k\.c\.|Kodeksu cywilnego|"
                      r"ustawy o prawach konsumenta|ustawy o ochronie praw lokatorów)", re.I),
     lambda m: ({"k.p.": KP, "kodeksu pracy": KP, "k.c.": KC, "kodeksu cywilnego": KC, "ustawy o prawach konsumenta": PK_CONS,
                 "ustawy o ochronie praw lokatorów": LOK}[m.group(2).lower()], m.group(1))),
    ("ES", re.compile(r"\bart(?:[íi]culo|\.)\s?(\d+(?:\s?bis)?)(?:\.\d+)?\s+(?:del?\s+(?:la\s+)?)?(Estatuto de los Trabajadores|ET|LAU|"
                      r"Ley de Arrendamientos Urbanos|LRJS|Ley Reguladora de la Jurisdicción Social|TRLGDCU|"
                      r"Ley General para la Defensa de los Consumidores(?: y Usuarios)?)\b"),
     lambda m: ({"estatuto de los trabajadores": ET, "et": ET, "lau": LAU, "ley de arrendamientos urbanos": LAU, "lrjs": LRJS,
                 "ley reguladora de la jurisdicción social": LRJS, "trlgdcu": TRLGDCU}.get(m.group(2).lower(), TRLGDCU),
                m.group(1).replace(" ", ""))),
    ("IT", re.compile(r"\bart(?:icolo|\.)\s?(\d+(?:-?bis)?)\s+(?:del\s+)?(c\.c\.|cod\. civ\.|codice civile|codice del consumo)", re.I),
     lambda m: (CC_IT if "civ" in m.group(2).lower() or m.group(2).lower() == "c.c." else CONS_IT, m.group(1).replace("-", ""))),
]
_NOT_FOUND = re.compile(r"not found|mismatch|\b404\b", re.I)
MAX_CITES = 6


def extract_citations(text: str) -> List[dict]:
    out, seen = [], set()
    for j, rx, conv in _CITE:
        for m in rx.finditer(text or ""):
            law, art = conv(m)
            if (j, law, art) not in seen:
                seen.add((j, law, art))
                out.append({**R(j, law, art, m.group(0).strip()), "anchor": m.group(0)})
    return out[:MAX_CITES]


async def check_citations(text: str, citations: List[dict]) -> Tuple[str, dict]:
    """Every national provision Lex cites is looked up on the official source. Confirms existence only — never that
    the provision says what the answer claims. Unfound ones are flagged inline; ones that could not be checked are noted."""
    refs = extract_citations(text)
    if not refs:
        return text, {"refs": 0}
    res = await asyncio.gather(*(read(r, wait=2.5) for r in refs))
    lines, out, n = [], text, max([int(c.get("n", 0)) for c in citations or []] + [0]) + 1
    verdicts = []
    for ref, r in zip(refs, res):
        if not r.get("failed"):
            verdicts.append("found")
            if r["url"] not in {c.get("url") for c in citations}:
                citations.append({"n": n, "title": f"{r['label']} — {SOURCE_NAME[ref['j']]} (existence checked only — does not "
                                  "confirm Lex's interpretation)", "url": r["url"], "source": "national", "claim_check": "status_checked"})
                n += 1
            if r.get("status") == "repealed":
                lines.append(f"“{ref['name']}” appears on the official source as repealed — check the current law before relying on it.")
        elif r.get("pending") or not _NOT_FOUND.search(r.get("error") or ""):
            verdicts.append("lookup_failed")
            lines.append(f"“{ref['name']}” could not be checked against the official source just now — treat it as unverified.")
        else:
            verdicts.append("not_found")
            lines.append(f"“{ref['name']}” could not be found on the official source ({SOURCE_NAME[ref['j']]}) — treat it as unverified.")
            out = out.replace(ref["anchor"], f"{ref['anchor']} [⚠ unverified]", 1)
    if lines:
        import lex_safety
        out = lex_safety.insert_before_tail(out, "**National law check (official sources):**\n" + "\n".join(f"- {x}" for x in lines))
        if "not_found" in verdicts:
            out = re.sub(r"\[CONFIDENCE:\s*HIGH\]", "[CONFIDENCE: MEDIUM]", out)
    return out, {"refs": len(refs), "verdicts": verdicts}


# ---------------- time periods in the answer must appear in the source they cite ----------------
_NUMWORDS = {2: "zwei two dos due dwóch dwa", 3: "drei three tres tre trzech trzy", 4: "vier four cuatro quattro czterech",
             6: "sechs six seis sei sześciu", 7: "sieben seven siete sette siedmiu siedem", 10: "zehn ten diez dieci dziesięciu",
             14: "vierzehn fourteen catorce quattordici czternastu", 15: "fünfzehn fifteen quince quindici",
             20: "zwanzig twenty veinte venti dwudziestu", 21: "einundzwanzig twenty-one veintiún ventuno",
             30: "dreißig thirty treinta trenta trzydziestu", 60: "sechzig sixty sesenta sessanta sześćdziesięciu",
             90: "neunzig ninety noventa novanta", 180: "centottanta ciento ochenta"}
_WORD_VAL = {w: v for v, ws in _NUMWORDS.items() for w in ws.split()}
_UNITS = r"(?:kalendarzowych\s+|roboczych\s+|hábiles\s+)?(?:dni|dnia|tygodni|miesięcy|Tagen?|Wochen|Monaten?|días|semanas|meses|giorni|settimane|mesi|days|weeks|months)\b"
_PERIOD = re.compile(r"\b(\d{1,3}|" + "|".join(sorted((re.escape(w) for w in _WORD_VAL), key=len, reverse=True)) + r")\s+" + _UNITS, re.I)


def _has_value(snippet: str, v: int) -> bool:
    low = snippet.lower()
    return bool(re.search(rf"(?<![\d.,]){v}(?![\d.,]\d)", low)) or any(w in low for w in _NUMWORDS.get(v, "").split())


def check_periods(answer: str, block: str) -> Tuple[str, int]:
    """A time limit followed by a citation [n] must appear in that source's retrieved text; otherwise it is flagged."""
    snippets = {m.group(1): m.group(2) for m in re.finditer(r"^\[(\d+)\] [^\n]*\n\s+\S+\n\s+(.+)$", block or "", re.M)}
    out, bad = answer or "", []
    for m in list(_PERIOD.finditer(out)):
        tok = m.group(1).lower()
        v = int(tok) if tok.isdigit() else _WORD_VAL.get(tok)
        marks = re.match(r"(?:[^\[\n]{0,150}?)((?:\s*\[\d+\])+)", out[m.end():])
        if not v or not marks:
            continue
        cited = [n for n in re.findall(r"\d+", marks.group(1)) if len(snippets.get(n, "")) > 100]
        if cited and not any(_has_value(snippets[n], v) for n in cited) and m.group(0) not in bad:
            bad.append(m.group(0))
    for b in bad:
        out = out.replace(b, f"{b} [⚠ not in the cited source]", 1)
    if bad:
        import lex_safety
        out = lex_safety.insert_before_tail(out, "**Source check:** " + ", ".join(f"“{b}”" for b in bad) + " could not be "
                                            "found in the official text it cites — do not rely on it; check the provision "
                                            "itself or ask a local lawyer.")
    return out, len(bad)
