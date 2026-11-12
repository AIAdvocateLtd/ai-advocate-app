"""Lex 2.0 Phase 2C: official law-change tracking from legislation.gov.uk data (OGL v3). Deterministic, free, run by hand only.
Verifies source FACTS (exists / wording retrieved / recorded status, extent and dates) — never legal interpretations."""
from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional, Tuple

import httpx

import content_guard
import legal_sources as L

LEG = L.LEG
SOURCE = "legislation.gov.uk"
# Other jurisdictions can be added here with their own official source; UK law is never applied to them.
JURISDICTIONS = {
    "england_wales": {"label": "England and Wales", "country": "GB", "extent": "E+W", "types": ["ukpga", "uksi", "asc", "wsi"]},
    "scotland": {"label": "Scotland", "country": "GB", "extent": "S", "types": ["asp", "ssi"]},
    "northern_ireland": {"label": "Northern Ireland", "country": "GB", "extent": "N", "types": ["nia", "nisr", "nisi"]},
    "uk": {"label": "UK-wide", "country": "GB", "extent": "E+W+S+N", "types": ["ukpga", "uksi"]},
}
NATION_TO_JURIS = {"england": "england_wales", "wales": "england_wales", "scotland": "scotland", "northern_ireland": "northern_ireland"}
_TYPES = {t for j in JURISDICTIONS.values() for t in j["types"]}
_PART = {"nisi": "article", "uksi": "regulation", "ssi": "regulation", "wsi": "regulation", "nisr": "regulation"}

# The defined set of official sources this phase checks (free: one request each).
WATCHLIST = [
    {"type": "ukpga", "year": "1996", "number": "18", "section": "94", "jurisdiction": "england_wales", "topics": ["employment"]},
    {"type": "ukpga", "year": "1996", "number": "18", "section": "108", "jurisdiction": "england_wales", "topics": ["employment"]},
    {"type": "ukpga", "year": "1996", "number": "18", "section": "111", "jurisdiction": "england_wales", "topics": ["employment"]},
    {"type": "ukpga", "year": "2010", "number": "15", "section": "13", "jurisdiction": "england_wales", "topics": ["discrimination", "employment"]},
    {"type": "ukpga", "year": "1988", "number": "50", "section": "21", "jurisdiction": "england_wales", "topics": ["housing"]},
    {"type": "ukpga", "year": "2004", "number": "34", "section": "213", "jurisdiction": "england_wales", "topics": ["housing"]},
    {"type": "ukpga", "year": "1989", "number": "41", "section": "1", "jurisdiction": "england_wales", "topics": ["family"]},
    {"type": "asp", "year": "2016", "number": "19", "section": "51", "jurisdiction": "scotland", "topics": ["housing"]},
    {"type": "nisi", "year": "1996", "number": "1919", "section": "126", "jurisdiction": "northern_ireland", "topics": ["employment"]},
]
NEW_FEEDS = ["ukpga", "asp", "asc", "nia"]  # newly published primary legislation, current year
LIMITATIONS = [
    "legislation.gov.uk revised text may not yet include every amendment — see recorded pending changes.",
    "A publication or enactment date is not the date a law takes effect.",
    "A version start date is when that version of the text applies from, not necessarily when the provision first commenced.",
    "Territorial extent shows where a provision is law, not whether it applies to a particular situation.",
    "New-legislation feeds are read from their first page only.",
]
STATUS_A, STATUS_B, STATUS_C, STATUS_D = ("Official source metadata verified", "Statutory wording retrieved",
                                          "Legal interpretation unverified", "Professional legal review completed")
REGULATORS = {"SRA", "BSB", "CILEX", "LAW SOCIETY OF SCOTLAND", "FACULTY OF ADVOCATES", "LAW SOCIETY OF NORTHERN IRELAND", "BAR OF NORTHERN IRELAND"}
_ID = re.compile(r"^[a-z]{3,5}/(?:18|19|20)\d{2}/\d{1,5}$")
_SEC = re.compile(r"^\d{1,4}[A-Z]{0,2}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def write_enabled() -> bool:
    return os.environ.get("LAW_WATCH_WRITE_ENABLED") == "1"


def jurisdiction_for(country: Optional[str], nation: Optional[str]) -> Optional[str]:
    """None for non-UK countries — UK records are never treated as another country's law."""
    if (country or "GB").upper() not in ("GB", "UK"):
        return None
    return NATION_TO_JURIS.get(nation or "", "uk")


async def _fetch(url: str) -> Tuple[int, str]:
    async with httpx.AsyncClient(timeout=8.0, headers=L.UA, follow_redirects=True) as c:
        r = await c.get(url)
        return r.status_code, (r.text if r.status_code == 200 else "")


def item_key(it: dict) -> str:
    return f"{it['type']}/{it['year']}/{it['number']}/{_PART.get(it['type'], 'section')}/{it['section']}"


def validate_item(it: dict) -> Optional[str]:
    if it.get("jurisdiction") not in JURISDICTIONS:
        return "unsupported_jurisdiction"
    if it.get("type") not in JURISDICTIONS[it["jurisdiction"]]["types"] and it.get("type") not in _TYPES:
        return "unsupported_type"
    if not _ID.match(f"{it.get('type')}/{it.get('year')}/{it.get('number')}") or not _SEC.match(str(it.get("section") or "")):
        return "invalid_identifier"
    return None


def _d(s: str) -> Optional[date]:
    try:
        return date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def _attrs(tag: str) -> dict:
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def _effects(xml: str, part: str, num: str) -> List[dict]:
    """Unapplied effects (amendments, repeals, commencements) the source records for THIS provision."""
    short = {"section": "s", "article": "art", "regulation": "reg"}[part]
    rx = re.compile(rf"\b{short}s?\.\s*(?:[\w(), ]*\b)?{re.escape(num)}\b", re.I)
    out = []
    for m in re.finditer(r"<ukm:UnappliedEffect\b([^>]*?)(?:/>|>(.*?)</ukm:UnappliedEffect>)", xml, re.S):
        a = _attrs(m.group(1))
        if not rx.search(a.get("AffectedProvisions", "")):
            continue
        dates = sorted({d for d in re.findall(r'<ukm:InForce\b[^>]*Date="(\d{4}-\d{2}-\d{2})"', m.group(2) or "")})
        out.append({"type": a.get("Type", "")[:80], "affected": a.get("AffectedProvisions", "")[:80],
                    "by": a.get("AffectingURI", "")[:120], "by_provisions": a.get("AffectingProvisions", "")[:60],
                    "in_force_dates": dates, "prospective": 'Prospective="true"' in (m.group(2) or "")})
    return sorted(out, key=lambda e: (e["by"], e["by_provisions"], e["type"]))[:20]


def parse_meta(xml: str, it: dict, today: Optional[date] = None) -> dict:
    """Source facts for one provision. Anything the record does not establish stays None / 'unknown'."""
    today = today or _now().date()
    part, num = _PART.get(it["type"], "section"), str(it["section"])
    sec_xml = xml.replace(f'id="{part}-', 'id="section-') if part != "section" else xml
    info = L.parse_section(sec_xml, num)
    title = re.search(r"<dc:title>(.*?)</dc:title>", xml, re.S)
    title = " ".join(title.group(1).split()) if title else ""
    title, tkinds = content_guard.inspect(title)
    if content_guard.suspicious(tkinds):
        title = "[title withheld — suspicious content]"
    rec = {"title": title, "status": info["status"], "version_date": None, "version_start_date": None, "source_modified": None,
           "extent": info.get("extent") or "", "pending_effects": [], "text_hash": None, "wording_excerpt": "",
           "anomalies": [], "conflicts": [], "content_flags": []}
    if info["status"] == "not_found":
        return rec
    idx = sec_xml.find(f'id="section-{num}"')
    tag = sec_xml[sec_xml.rfind("<", 0, idx):sec_xml.find(">", idx) + 1]
    group = sec_xml.rfind("<P1group", 0, idx)
    head = sec_xml[group:sec_xml.find(">", group) + 1] if group >= 0 else ""
    a = {**_attrs(head), **_attrs(tag)}
    valid = re.search(r"<dct:valid>([^<]+)", xml)
    modified = re.search(r"<dc:modified>([^<]+)", xml)
    rec.update(version_date=valid.group(1).strip() if valid else None, source_modified=modified.group(1).strip() if modified else None,
               version_start_date=a.get("RestrictStartDate"), pending_effects=_effects(xml, part, num))
    end = _d(a.get("RestrictEndDate", ""))
    text, kinds = content_guard.inspect(info.get("text") or "")
    rec["text_hash"] = hashlib.sha256(" ".join(text.split()).encode()).hexdigest() if text else None
    if content_guard.suspicious(kinds):
        rec["content_flags"] = kinds  # wording is never passed on to Lex when the source content looks like instructions
    else:
        rec["wording_excerpt"] = text[:300]
    for label, raw in (("version date", rec["version_date"]), ("version start date", rec["version_start_date"])):
        if raw and not _d(raw):
            rec["anomalies"].append(f"{label} '{raw[:20]}' is not a valid date")
        elif raw and _d(raw) > today and rec["status"] == "in_force":
            rec["anomalies"].append(f"{label} {raw} is in the future but the text is shown as in force")
    if rec["status"] == "not_in_force" and "<Repeal" in sec_xml[idx:idx + 20000]:
        rec["conflicts"].append("recorded as prospective and also carries repeal markup")
    if end and end <= today and rec["status"] == "in_force":
        rec["conflicts"].append(f"version end date {end} has passed but the text is shown as in force")
    return rec


def commencement(rec: dict, today: Optional[date] = None) -> dict:
    """Only what the official record states. A publication / version date is never treated as the commencement date."""
    today = today or _now().date()
    cif = [e for e in rec.get("pending_effects") or [] if "coming into force" in e["type"].lower() or "commence" in e["type"].lower()]
    dates = sorted(d for e in cif for d in e["in_force_dates"] if _d(d))
    if rec["status"] == "not_in_force":
        future = [d for d in dates if _d(d) >= today]
        return {"state": "not_yet_in_force", "date": future[0] if future else None,
                "provenance": "unapplied commencement effect" if future else "provision marked prospective; no date recorded"}
    if rec["status"] in ("repealed", "partly_repealed"):
        return {"state": rec["status"], "date": None, "provenance": "repeal shown in the revised text"}
    if cif:
        return {"state": "partially_commenced", "date": dates[0] if dates else None,
                "provenance": "in force, with recorded commencement effects not yet applied to the text"}
    return {"state": "in_force" if rec["status"] in ("in_force",) else "unknown", "date": None,
            "provenance": "shown in force in the revised text; original commencement date not recorded in this data"}


def verification(rec: dict, http_ok: bool, review: Optional[dict] = None) -> dict:
    """Four separate statuses. C is always unverified; D only with an actual recorded qualified review."""
    a_ok = http_ok and rec["status"] != "not_found" and not rec["conflicts"] and not rec["anomalies"]
    return {"A_metadata": {"label": STATUS_A, "verified": a_ok,
                           "detail": "exists; status/extent/dates read from the official record" if a_ok else
                           "; ".join(rec["conflicts"] + rec["anomalies"]) or "not verified"},
            "B_wording": {"label": STATUS_B, "verified": bool(rec["text_hash"]) and not rec["content_flags"],
                          "hash": rec["text_hash"]},
            "C_interpretation": {"label": STATUS_C, "verified": False},
            "D_professional_review": review_status(review)}


def review_status(review: Optional[dict]) -> dict:
    ok = bool(review and review.get("reviewer_name") and review.get("registration_number") and
              (review.get("regulator") or "").upper() in REGULATORS and review.get("reviewed_at"))
    return {"label": STATUS_D if ok else "No professional legal review recorded", "verified": ok,
            **({k: review[k] for k in ("reviewer_name", "regulator", "registration_number", "reviewed_at")} if ok else {})}


def classify(prev: Optional[dict], cur: dict) -> List[str]:
    if not prev:
        return ["first_recorded"]
    out = []
    if cur["status"] != prev.get("status"):
        out.append({"repealed": "repealed", "partly_repealed": "partly_repealed"}.get(cur["status"]) or
                   ("commenced" if prev.get("status") == "not_in_force" and cur["status"] == "in_force" else "status_changed"))
    if cur.get("text_hash") and prev.get("text_hash") and cur["text_hash"] != prev["text_hash"]:
        out.append("wording_amended")
    if (cur.get("extent") or "") != (prev.get("extent") or ""):
        out.append("extent_changed")
    if _sig(cur.get("pending_effects")) != _sig(prev.get("pending_effects")):
        out.append("amendment_pending" if cur.get("pending_effects") else "pending_changes_applied")
    return out or ["unchanged"]


def _sig(effects) -> str:
    return hashlib.sha256(repr([(e["type"], e["by"], e["by_provisions"], e["in_force_dates"]) for e in effects or []]).encode()).hexdigest()


def _version_id(key: str, rec: dict) -> str:
    return hashlib.sha256(f"{key}|{rec['text_hash']}|{rec['status']}|{rec['extent']}|{rec['version_start_date']}|"
                          f"{_sig(rec['pending_effects'])}".encode()).hexdigest()[:32]


async def check_item(it: dict, fetch, prev: Optional[dict], today: date) -> dict:
    bad = validate_item(it)
    if bad:
        return {"key": f"{it.get('type')}/{it.get('year')}/{it.get('number')}/{it.get('section')}", "result": bad,
                "changes": [], "record": None}
    key = item_key(it)
    url = f"{LEG}/{key}"
    try:
        code, body = await fetch(f"{url}/data.xml")
    except Exception as e:
        code, body = 0, ""
        err = type(e).__name__
    else:
        err = f"HTTP {code}" if code not in (200, 404) else ""
    if code == 200 and "<Legislation" not in body:
        code, err = 0, "incomplete or unexpected response"
    if code not in (200, 404):
        return {"key": key, "result": "source_unavailable", "error": err, "changes": [], "record": None}
    rec = parse_meta(body, it, today) if code == 200 else {"status": "not_found"}
    if rec["status"] == "not_found":
        return {"key": key, "result": "not_found", "changes": ["provision_not_found"] if prev else [], "record": None}
    jur = JURISDICTIONS[it["jurisdiction"]]
    rec.update(key=key, identifier=f"{it['type']}/{it['year']}/{it['number']}", year=it["year"], url=url,
               provision=f"{_PART.get(it['type'], 'section')} {it['section']}", jurisdiction=it["jurisdiction"],
               jurisdiction_label=jur["label"], extent_words=L.extent_words(rec["extent"]), topics=it.get("topics") or [],
               commencement=commencement(rec, today), limitations=LIMITATIONS[:4],
               provenance={"source": SOURCE, "url": f"{url}/data.xml", "licence": L.OGL, "http_status": code})
    rec["verification"] = verification(rec, True, (prev or {}).get("professional_review"))
    return {"key": key, "result": "checked", "changes": classify(prev, rec), "record": rec}


async def check_new_legislation(db, fetch, year: str, dry_run: bool) -> List[dict]:
    out = []
    for t in NEW_FEEDS:
        feed = f"{t}/{year}"
        try:
            code, body = await fetch(f"{LEG}/{feed}/data.feed")
        except Exception:
            code, body = 0, ""
        if code != 200 or "<feed" not in body:
            out.append({"feed": feed, "result": "source_unavailable"})
            continue
        baseline = not await db.law_watch_seen.find_one({"feed": feed})
        new = []
        for e in re.findall(r"<entry>(.*?)</entry>", body, re.S)[:50]:
            i_d = re.search(r"<id>https?://www\.legislation\.gov\.uk/id/([a-z]{3,5}/\d{4}/\d{1,5})</id>", e)
            if not i_d or await db.law_watch_seen.find_one({"_id": i_d.group(1)}):
                continue
            t_m = re.search(r"<title>([^<]*)", e)
            title, kinds = content_guard.inspect(" ".join((t_m.group(1) if t_m else "").split())[:200])
            upd = re.search(r"<updated>([^<]+)", e)
            doc = {"_id": i_d.group(1), "feed": feed, "url": f"{LEG}/{i_d.group(1)}",
                   "title": "[title withheld — suspicious content]" if content_guard.suspicious(kinds) else title,
                   "feed_updated": upd.group(1) if upd else None, "commencement": {"state": "unknown", "date": None,
                   "provenance": "listed in the official new-legislation feed; publication is not commencement"},
                   "first_seen": _now().isoformat()}
            new.append(doc)
            if not dry_run:
                await db.law_watch_seen.update_one({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True)
        out.append({"feed": feed, "result": "baseline" if baseline else "checked", "new": [] if baseline else
                    [{k: d[k] for k in ("_id", "title", "url", "commencement")} for d in new], "seen": len(new)})
    return out


async def check_fact_sources(db, fetch, dry_run: bool) -> List[dict]:
    """Source-existence metadata for Phase 2A-1 records whose source is legislation.gov.uk. Reads lex_lessons only;
    writes to law_watch_fact_checks. Review status and wording of the records are never touched."""
    out = []
    async for r in db.lex_lessons.find({"source_url": {"$regex": r"^https://www\.legislation\.gov\.uk/"}},
                                       {"_id": 0, "id": 1, "source_url": 1}):
        try:
            code, body = await fetch(r["source_url"].rstrip("/") + "/data.xml")
        except Exception:
            code, body = 0, ""
        ok = code == 200 and "<Legislation" in body
        doc = {"lesson_id": r.get("id"), "source_url": r["source_url"], "http_status": code, "checked_at": _now().isoformat(),
               "A_metadata": {"label": STATUS_A, "verified": ok, "detail": "official source exists" if ok else "not confirmed"},
               "C_interpretation": {"label": STATUS_C, "verified": False}, "D_professional_review": review_status(None)}
        out.append(doc)
        if not dry_run:
            await db.law_watch_fact_checks.update_one({"lesson_id": doc["lesson_id"]}, {"$set": doc}, upsert=True)
    return out


def affected_topics(changes: List[dict]) -> List[dict]:
    """Groundwork for future alerts — nothing is sent. Separates the verified change from its possible implications."""
    out = []
    for c in changes:
        if set(c["changes"]) & {"first_recorded", "unchanged"} or not c.get("record"):
            continue
        for t in c["record"]["topics"]:
            out.append({"topic": t, "key": c["key"], "title": c["record"]["title"], "change_types": c["changes"],
                        "statutory_change": "recorded on legislation.gov.uk (source fact)",
                        "implication": "possible effect on this topic — needs further assessment", "customer_alert": False})
    return out


async def ensure_indexes(db) -> None:
    await db.law_watch_records.create_index("key", unique=True)
    await db.law_watch_records.create_index("url")
    await db.law_watch_history.create_index([("key", 1), ("recorded_at", 1)])
    await db.law_watch_seen.create_index("feed")


async def run_check(db, fetch=None, dry_run: bool = True, items: Optional[List[dict]] = None, today: Optional[date] = None,
                    feeds: bool = True, facts: bool = True, actor: str = "") -> dict:
    """Idempotent, auditable and safe to rerun. dry_run=True writes nothing and returns the proposed changes."""
    fetch, today = fetch or _fetch, today or _now().date()
    if not dry_run:
        await ensure_indexes(db)
    started, now = _now(), _now().isoformat()
    results = []
    for it in items if items is not None else WATCHLIST:
        key = item_key(it) if not validate_item(it) else None
        prev = await db.law_watch_records.find_one({"key": key}, {"_id": 0}) if key else None
        res = await check_item(it, fetch, prev, today)
        results.append(res)
        rec = res["record"]
        if dry_run or res["result"] not in ("checked", "not_found"):
            continue
        if res["result"] == "not_found":
            if prev:
                await db.law_watch_records.update_one({"key": key}, {"$set": {"last_checked": now},
                                                                      "$addToSet": {"anomalies": "provision no longer found"}})
            continue
        rec["last_checked"] = now
        if res["changes"] == ["unchanged"]:
            await db.law_watch_records.update_one({"key": key}, {"$set": {"last_checked": now}})
            continue
        vid = _version_id(key, rec)
        if prev and prev.get("version_id") == vid:
            await db.law_watch_records.update_one({"key": key}, {"$set": {"last_checked": now}})
            continue
        if prev:
            await db.law_watch_history.update_many({"key": key, "superseded_at": None}, {"$set": {"superseded_at": now}})
        rec.update(version_id=vid, previous_version_id=(prev or {}).get("version_id"),
                   previous_text_hash=(prev or {}).get("text_hash"), last_change={"at": now, "types": res["changes"]})
        await db.law_watch_history.update_one({"_id": vid}, {"$setOnInsert": {
            **{k: rec[k] for k in ("key", "title", "url", "status", "extent", "text_hash", "version_date", "version_start_date",
                                   "pending_effects", "commencement", "previous_version_id")},
            "change_types": res["changes"], "recorded_at": now, "superseded_at": None}}, upsert=True)
        await db.law_watch_records.update_one({"key": key}, {"$set": rec}, upsert=True)
    new_leg = await check_new_legislation(db, fetch, str(today.year), dry_run) if feeds else []
    fact_checks = await check_fact_sources(db, fetch, dry_run) if facts else []
    changed = [r for r in results if r["changes"] and r["changes"] != ["unchanged"]]
    summary = {"checked": sum(r["result"] == "checked" for r in results),
               "unchanged": sum(r["changes"] == ["unchanged"] for r in results),
               "changed": sum(1 for r in changed if r["changes"] != ["first_recorded"]),
               "first_recorded": sum(r["changes"] == ["first_recorded"] for r in results),
               "unavailable": sum(r["result"] == "source_unavailable" for r in results),
               "not_found": sum(r["result"] == "not_found" for r in results),
               "rejected": sum(r["result"] in ("unsupported_jurisdiction", "unsupported_type", "invalid_identifier") for r in results),
               "new_legislation": sum(len(f.get("new") or []) for f in new_leg),
               "fact_sources_checked": len(fact_checks), "fact_sources_confirmed": sum(f["A_metadata"]["verified"] for f in fact_checks)}
    report = {"id": str(uuid.uuid4()), "at": now, "dry_run": dry_run, "actor": actor, "summary": summary,
              "items": [{"key": r["key"], "result": r["result"], "changes": r["changes"], "error": r.get("error"),
                         "status": (r["record"] or {}).get("status"), "commencement": (r["record"] or {}).get("commencement"),
                         "verification": (r["record"] or {}).get("verification")} for r in results],
              "new_legislation": new_leg, "affected_topics": affected_topics(changed), "notifications_sent": 0,
              "ms": int((_now() - started).total_seconds() * 1000)}
    if not dry_run:
        await db.law_watch_runs.insert_one({**report, "_id": report["id"]})
    return report


# ------------------------------------------------------------------ Lex integration (DB read only, no network, no AI)
_DATE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|"
                   r"december)\s+((?:19|20)\d{2})\b|\b(\d{1,2})/(\d{1,2})/((?:19|20)\d{2})\b", re.I)
_MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september",
                                       "october", "november", "december"), 1)}


def event_dates(text: str) -> List[date]:
    out = []
    for m in _DATE.finditer(text or ""):
        try:
            out.append(date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))) if m.group(2) else
                       date(int(m.group(6)), int(m.group(5)), int(m.group(4))))
        except ValueError:
            continue
    return sorted(set(out))


def notes_for(rec: dict, dates: List[date], today: date) -> List[str]:
    lab = f"“{rec.get('title') or rec['identifier']}, {rec['provision']}”"
    out = []
    if rec.get("conflicts") or rec.get("anomalies"):
        out.append(f"Official records for {lab} are incomplete or inconsistent — treat its status and dates as unconfirmed.")
    start = _d(rec.get("version_start_date") or "")
    early = [d for d in dates if start and d < start]
    if early:
        d = early[0].isoformat()
        out.append(f"The current legislation.gov.uk wording of {lab} applies from {start.isoformat()}. You mention {d}, which is "
                   f"earlier, so a different version may have applied then — see the version as it stood on that date: "
                   f"{rec['url']}/{d}")
    c = rec.get("commencement") or {}
    if c.get("state") == "not_yet_in_force":
        out.append(f"{lab} is recorded as not yet in force" + (f"; the official record gives {c['date']} as the commencement date."
                                                                 if c.get("date") else "; no commencement date is recorded."))
    elif rec.get("pending_effects"):
        dated = sorted({d for e in rec["pending_effects"] for d in e["in_force_dates"] if _d(d) and _d(d) >= today})
        out.append(f"legislation.gov.uk records changes to {lab} that are not yet shown in its text"
                   + (f" (recorded as taking effect from {dated[0]})" if dated else " (no effective date recorded)")
                   + " — the current wording may not be the final position.")
    ch = rec.get("last_change") or {}
    if ch.get("at") and set(ch.get("types") or []) - {"first_recorded"} and \
            (_d(ch["at"]) or date.min) >= today - timedelta(days=90):
        out.append(f"The official record of {lab} changed on {ch['at'][:10]} ({', '.join(t.replace('_', ' ') for t in ch['types'])}). "
                   "The change is a source fact; what it means for your situation has not been assessed.")
    return out


async def annotate(db, leg: dict, country: Optional[str], nation: Optional[str], customer_text: str,
                   today: Optional[date] = None) -> List[str]:
    """Law-change notes for the provisions an answer cites, from stored official records. Never a verification label."""
    if jurisdiction_for(country, nation) is None:
        return []
    urls = [u.rstrip("/") for u in (leg or {}).get("urls") or [] if u]
    if not urls:
        return []
    today, dates = today or _now().date(), event_dates(customer_text)
    lines = []
    async for rec in db.law_watch_records.find({"url": {"$in": urls}}, {"_id": 0}).limit(6):
        lines += notes_for(rec, dates, today)
    if lines:
        lines.append("These notes come from official source records only — they are not a legal interpretation.")
    return lines
