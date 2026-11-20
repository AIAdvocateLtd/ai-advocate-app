"""Lex 2.0 Phase 2C: official law-change tracking from legislation.gov.uk data (OGL v3). Deterministic, free, run by hand only.
Verifies source FACTS (exists / wording retrieved / recorded status, extent and dates) — never legal interpretations."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
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
    "england_wales": {"label": "England and Wales", "country": "GB", "extent": "E+W", "types": ["ukpga", "uksi", "asc", "anaw", "wsi"]},
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
# Proposed second scope: the provisions behind Lex's official-source rules (lex_guidance). Read-only until you approve it.
PROPOSED_WATCHLIST = [
    {"type": "ukpga", "year": "1996", "number": "18", "section": "23", "jurisdiction": "england_wales", "topics": ["employment"]},
    {"type": "ukpga", "year": "1996", "number": "18", "section": "203", "jurisdiction": "england_wales", "topics": ["employment"]},
    {"type": "ukpga", "year": "2010", "number": "15", "section": "123", "jurisdiction": "england_wales", "topics": ["discrimination", "employment"]},
    {"type": "ukpga", "year": "2004", "number": "34", "section": "214", "jurisdiction": "england_wales", "topics": ["housing"]},
    {"type": "anaw", "year": "2016", "number": "1", "section": "173", "jurisdiction": "england_wales", "topics": ["housing"]},
    {"type": "ukpga", "year": "2015", "number": "15", "section": "22", "jurisdiction": "england_wales", "topics": ["consumer"]},
    {"type": "ukpga", "year": "1980", "number": "58", "section": "28", "jurisdiction": "england_wales", "topics": ["limitation"]},
    {"type": "nisi", "year": "1996", "number": "1919", "section": "140", "jurisdiction": "northern_ireland", "topics": ["employment"]},
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


SCOPES = {"nine_provisions": {"label": "The nine approved provisions only", "feeds": False, "facts": False, "items": None},
          "official_rules_provisions": {"label": "PROPOSED — provisions behind Lex's official-source rules (not yet approved)",
                                        "feeds": False, "facts": False, "items": "PROPOSED_WATCHLIST", "proposed": True},
          "all_17": {"label": "All 17 approved provisions (nine original + eight official-rule provisions)",
                     "feeds": False, "facts": False, "items": "ALL_17"}}
SCHEDULE_SCOPE = "all_17"


def scope_items(sc: dict) -> List[dict]:
    if sc.get("items") == "ALL_17":
        return WATCHLIST + PROPOSED_WATCHLIST
    return PROPOSED_WATCHLIST if sc.get("items") == "PROPOSED_WATCHLIST" else WATCHLIST
SWITCH_MINUTES, TOKEN_MINUTES = 30, 15


def kill_switch() -> bool:
    """Emergency stop outside the app: LAW_WATCH_KILL_SWITCH=1 blocks every tracker write regardless of the admin switch."""
    return os.environ.get("LAW_WATCH_KILL_SWITCH") == "1"


async def stopped(db) -> bool:
    """Server kill switch OR the admin's in-app emergency stop."""
    if kill_switch():
        return True
    doc = await db.law_watch_settings.find_one({"_id": "emergency_stop"}) or {}
    return bool(doc.get("on"))


async def set_emergency_stop(db, on: bool, actor: str) -> bool:
    now = _now().isoformat()
    await db.law_watch_settings.update_one({"_id": "emergency_stop"}, {"$set": {"on": on, "by": actor, "at": now}}, upsert=True)
    if on:
        await db.law_watch_settings.update_one({"_id": "writes"}, {"$set": {"enabled": False, "until": None, "by": actor, "at": now}})
        await db.law_watch_settings.update_one({"_id": "schedule"}, {"$set": {"enabled": False, "by": actor, "at": now}})
    await db.law_watch_audit.insert_one({"_id": str(uuid.uuid4()), "at": now, "actor": actor,
                                         "action": "emergency_stop_on" if on else "emergency_stop_off"})
    return on


async def switch_state(db) -> dict:
    """Admin write switch, stored in law_watch_settings. Absent = OFF. Expires by itself after SWITCH_MINUTES."""
    doc = await db.law_watch_settings.find_one({"_id": "writes"}) or {}
    until = doc.get("until") or ""
    stop = await stopped(db)
    on = bool(doc.get("enabled")) and until > _now().isoformat() and not stop
    sched = await schedule_state(db)
    return {"enabled": on, "until": until if on else None, "changed_by": doc.get("by"), "changed_at": doc.get("at"),
            "kill_switch": stop, "monitoring_scheduled": sched["enabled"], "schedule": sched,
            "customer_notifications": False}


async def schedule_state(db) -> dict:
    """Daily monitoring switch, stored in law_watch_settings. Absent = OFF. The kill switch always wins."""
    doc = await db.law_watch_settings.find_one({"_id": "schedule"}) or {}
    return {"enabled": bool(doc.get("enabled")) and not await stopped(db), "scope": SCHEDULE_SCOPE, "time": "06:00 Europe/London",
            "changed_by": doc.get("by"), "changed_at": doc.get("at"), "last_run": doc.get("last_run")}


async def baseline_missing(db) -> List[str]:
    keys = [item_key(it) for it in scope_items(SCOPES[SCHEDULE_SCOPE])]
    have = {d["key"] async for d in db.law_watch_records.find({"key": {"$in": keys}}, {"key": 1})}
    return [k for k in keys if k not in have]


async def set_schedule(db, enabled: bool, actor: str, token: str = "", secret: str = "") -> dict:
    """Turning ON needs: kill switch off, writes switch ON, the full 17-law baseline saved, and a fresh single-use
    dry-run approval code for the 17-law scope from the same admin. OFF always works."""
    now = _now().isoformat()
    if enabled:
        if await stopped(db):
            return {"refused": "Emergency stop is on — monitoring cannot be enabled."}
        if not (await switch_state(db))["enabled"]:
            return {"refused": "Turn tracker writes on first (30-minute window)."}
        missing = await baseline_missing(db)
        if missing:
            return {"refused": f"The 17-law baseline is not complete ({len(missing)} missing). Save the baseline first."}
        data, err = read_token(token, actor, secret)
        if err:
            return {"refused": err}
        if data["scope"] != SCHEDULE_SCOPE:
            return {"refused": "Use an approval code from a 17-law dry run."}
        try:
            await db.law_watch_audit.insert_one({"_id": "sched:" + hashlib.sha256(token.encode()).hexdigest()[:32], "at": now,
                                                 "actor": actor, "action": "schedule_on", "scope": SCHEDULE_SCOPE})
        except Exception:
            return {"refused": "This approval code has already been used. Run a new dry run."}
    else:
        await db.law_watch_audit.insert_one({"_id": str(uuid.uuid4()), "at": now, "actor": actor, "action": "schedule_off"})
    await db.law_watch_settings.update_one({"_id": "schedule"}, {"$set": {"enabled": enabled, "by": actor, "at": now}}, upsert=True)
    return await schedule_state(db)


async def enable_monitoring(db, actor: str, fetch=None) -> dict:
    """One-switch ON (admin has re-entered their password): needs no emergency stop, the full 17-law baseline, and a
    fresh read-only check that reached every official record. Writes nothing to legal records."""
    if await stopped(db):
        return {"refused": "Emergency stop is on — turn it off first."}
    missing = await baseline_missing(db)
    if missing:
        return {"refused": f"The 17-law starting record is incomplete ({len(missing)} missing) — use Maintenance to save it."}
    sc = SCOPES[SCHEDULE_SCOPE]
    rep = await run_check(db, fetch, dry_run=True, items=scope_items(sc), feeds=sc["feeds"], facts=sc["facts"],
                          actor=actor, scope=SCHEDULE_SCOPE)
    s = rep["summary"]
    if s["unavailable"] or s["not_found"] or s["held_unverified"] or s["rejected"]:
        return {"refused": "legislation.gov.uk could not be fully checked just now — nothing was changed. Try again later.",
                "summary": s}
    now = _now().isoformat()
    await db.law_watch_audit.insert_one({"_id": str(uuid.uuid4()), "at": now, "actor": actor, "action": "schedule_on",
                                         "method": "monitoring_switch", "scope": SCHEDULE_SCOPE, "check_summary": s})
    await db.law_watch_settings.update_one({"_id": "schedule"}, {"$set": {"enabled": True, "by": actor, "at": now}}, upsert=True)
    return {**await schedule_state(db), "check_summary": s}


async def overview(db) -> dict:
    sched = await schedule_state(db)
    last = sched.get("last_run") or {}
    ok = await db.law_watch_audit.find({"_id": {"$regex": "^daily:"}, "result": {"$in": ["checked", "checked_with_failures"]}},
                                       {"_id": 1, "at": 1, "result": 1, "failed": 1}).sort("at", -1).to_list(1)
    return {"monitoring_on": sched["enabled"], "time": sched["time"], "emergency_stop": await stopped(db),
            "server_kill_switch": kill_switch(), "baseline_complete": not await baseline_missing(db),
            "records": await db.law_watch_records.count_documents({}), "last_run": last or None,
            "last_successful_check": (ok[0]["at"] if ok else None), "last_failures": last.get("failed", 0),
            "awaiting_review": await db.law_update_proposals.count_documents({"status": "awaiting_review"}),
            "pending_amendments": await db.law_watch_records.count_documents({"pending_effects.0": {"$exists": True}}),
            "changed_by": sched.get("changed_by"), "changed_at": sched.get("changed_at")}


def _london_day() -> str:
    from zoneinfo import ZoneInfo
    return _now().astimezone(ZoneInfo("Europe/London")).date().isoformat()


async def scheduled_run(db, run_id: str, fetch=None, notify=None) -> dict:
    """Daily check of all 17 provisions. Does nothing (and writes nothing) while the schedule is OFF. One run per UK day;
    genuine changes go to the professional review queue as awaiting review — never approved."""
    if not (await schedule_state(db))["enabled"]:
        return {"skipped": "schedule_off"}
    day = _london_day()
    try:
        await db.law_watch_audit.insert_one({"_id": f"daily:{day}", "at": _now().isoformat(), "actor": "scheduler",
                                             "action": "scheduled_run", "run_key": run_id, "result": "started"})
    except Exception:
        return {"skipped": "already_ran_today", "day": day}
    sc = SCOPES[SCHEDULE_SCOPE]
    try:
        rep = await run_check(db, fetch, dry_run=False, scheduled=True, items=scope_items(sc), feeds=sc["feeds"],
                              facts=sc["facts"], actor="scheduler", scope=SCHEDULE_SCOPE)
        s = rep["summary"]
        failed = s["unavailable"] + s["not_found"] + s["held_unverified"] + s["rejected"]
        out = {"day": day, "run_id": rep["id"], "result": "checked_with_failures" if failed else "checked",
               "failed": failed, "proposed": len(rep["proposed_updates"]), "saved": len(rep["saved_keys"])}
        problems = [i for i in rep["items"] if i["result"] != "checked"]
    except Exception as e:
        rep, problems = None, []
        out = {"day": day, "result": "error", "error": type(e).__name__, "failed": len(scope_items(sc)), "proposed": 0, "saved": 0}
    await db.law_watch_audit.update_one({"_id": f"daily:{day}"}, {"$set": out})
    await db.law_watch_settings.update_one({"_id": "schedule"}, {"$set": {"last_run": {**out, "at": _now().isoformat()}}})
    if notify and (out["failed"] or out["proposed"]):
        try:
            await notify(*alert_email(out, rep, problems))
            out["notified"] = True
        except Exception:
            out["notified"] = False
    return out


def alert_email(out: dict, rep: Optional[dict], problems: List[dict]) -> Tuple[str, str]:
    from html import escape
    if out["result"] == "error":
        return (f"AI Advocate law tracker: daily check failed ({out['day']})",
                f"<p>The daily legislation.gov.uk check could not run ({escape(out['error'])}). Nothing was saved. "
                "Lex keeps using the last recorded versions. It will try again tomorrow at 6:00am.</p>")
    rows = "".join(f"<li>{escape(p['key'])} — {escape(', '.join(p['changes']))} → {escape(p['becomes'])}</li>"
                   for p in rep["proposed_updates"])
    bad = "".join(f"<li>{escape(p['key'])} — {escape(p['result'].replace('_', ' '))}</li>" for p in problems)
    subj = f"AI Advocate law tracker: {out['proposed']} change(s) to review" if out["proposed"] else \
        f"AI Advocate law tracker: {out['failed']} check(s) failed"
    body = (f"<p>Daily check {out['day']} of the 17 watched provisions.</p>"
            + (f"<p><b>Changes recorded on legislation.gov.uk (awaiting professional review):</b></p><ul>{rows}</ul>" if rows else "")
            + (f"<p><b>Not checked this time (previous record kept):</b></p><ul>{bad}</ul>" if bad else "")
            + "<p>These are official source facts only. Nothing has been approved; review them in Admin → Law tracker.</p>")
    return subj, body


async def set_switch(db, enabled: bool, actor: str) -> dict:
    now = _now()
    await db.law_watch_settings.update_one({"_id": "writes"}, {"$set": {
        "enabled": enabled, "until": (now + timedelta(minutes=SWITCH_MINUTES)).isoformat() if enabled else None,
        "by": actor, "at": now.isoformat()}}, upsert=True)
    await db.law_watch_audit.insert_one({"_id": str(uuid.uuid4()), "at": now.isoformat(), "actor": actor,
                                         "action": "writes_on" if enabled else "writes_off"})
    return await switch_state(db)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def issue_token(code: str, scope: str, actor: str, secret: str) -> dict:
    exp = (_now() + timedelta(minutes=TOKEN_MINUTES)).isoformat()
    payload = base64.urlsafe_b64encode(json.dumps({"code": code, "scope": scope, "actor": actor, "exp": exp}).encode()).decode()
    return {"token": f"{payload}.{_sign(payload, secret)}", "expires_at": exp}


def read_token(token: str, actor: str, secret: str) -> Tuple[Optional[dict], str]:
    payload, _, sig = (token or "").partition(".")
    if not payload or not hmac.compare_digest(sig, _sign(payload, secret)):
        return None, "This approval code is not valid. Run a new dry run."
    data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    if data["exp"] <= _now().isoformat():
        return None, "This approval code has expired. Run a new dry run."
    if data["actor"] != actor:
        return None, "Only the admin who ran the dry run can save it."
    if data["scope"] not in SCOPES:
        return None, "Unsupported scope."
    return data, ""


async def authorised_write(db, token: str, actor: str, secret: str, fetch=None) -> dict:
    """Saves a reviewed dry run: switch ON, kill switch off, valid unexpired single-use token, fresh fetch must match."""
    state = await switch_state(db)
    if not state["enabled"]:
        return {"refused": "Tracker writes are OFF" + (" (emergency stop is on)." if state["kill_switch"] else ".")}
    data, err = read_token(token, actor, secret)
    if err:
        return {"refused": err}
    tid = hashlib.sha256(token.encode()).hexdigest()[:32]
    try:
        await db.law_watch_audit.insert_one({"_id": tid, "at": _now().isoformat(), "actor": actor, "action": "apply",
                                             "scope": data["scope"], "proposal_code": data["code"]})
    except Exception:
        return {"refused": "This approval code has already been used. Run a new dry run."}
    sc = SCOPES[data["scope"]]
    rep = await run_check(db, fetch, dry_run=False, confirm=data["code"], items=scope_items(sc), feeds=sc["feeds"],
                          facts=sc["facts"], actor=actor, scope=data["scope"], authorisation_id=tid)
    await db.law_watch_audit.update_one({"_id": tid}, {"$set": {"result": "refused" if rep["refused"] else "saved",
                                                                 "run_id": rep["id"], "saved_keys": rep["saved_keys"]}})
    return rep


def jurisdiction_for(country: Optional[str], nation: Optional[str]) -> Optional[str]:
    """None for non-UK countries — UK records are never treated as another country's law."""
    if (country or "GB").upper() not in ("GB", "UK"):
        return None
    return NATION_TO_JURIS.get(nation or "", "uk")


async def _fetch(url: str) -> Tuple[int, str]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=5.0), headers=L.UA, follow_redirects=True) as c:
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
        if {e["by"] for e in cur.get("pending_effects") or []} - {e["by"] for e in prev.get("pending_effects") or []}:
            out.append("new_affecting_instrument")
    if (cur.get("commencement") or {}).get("date") != (prev.get("commencement") or {}).get("date") and \
            (cur.get("commencement") or {}).get("date"):
        out.append("commencement_date_recorded")
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
    rec["affecting_instruments"] = sorted({e["by"].rsplit("/id/", 1)[-1] for e in rec["pending_effects"] if e.get("by")})[:10]
    return {"key": key, "result": "checked", "changes": classify(prev, rec), "record": rec}


async def check_new_legislation(db, fetch, year: str) -> List[dict]:
    """Read only. New ids are returned in "_docs"; the caller writes them only when authorised."""
    out = []
    for t in NEW_FEEDS:
        feed = f"{t}/{year}"
        try:
            code, body = await fetch(f"{LEG}/{feed}/data.feed")
        except Exception:
            code, body = 0, ""
        if code != 200 or "<feed" not in body:
            out.append({"feed": feed, "result": "source_unavailable", "_docs": []})
            continue
        baseline = not await db.law_watch_seen.find_one({"feed": feed})
        new = []
        for e in re.findall(r"<entry>(.*?)</entry>", body, re.S)[:50]:
            i_d = re.search(r"<id>https?://www\.legislation\.gov\.uk/id/([a-z]{3,5}/\d{4}/\d{1,5})</id>", e)
            if not i_d or i_d.group(1) in {d["_id"] for d in new} or await db.law_watch_seen.find_one({"_id": i_d.group(1)}):
                continue
            t_m = re.search(r"<title>([^<]*)", e)
            title, kinds = content_guard.inspect(" ".join((t_m.group(1) if t_m else "").split())[:200])
            upd = re.search(r"<updated>([^<]+)", e)
            new.append({"_id": i_d.group(1), "feed": feed, "url": f"{LEG}/{i_d.group(1)}",
                        "title": "[title withheld — suspicious content]" if content_guard.suspicious(kinds) else title,
                        "feed_updated": upd.group(1) if upd else None, "commencement": {"state": "unknown", "date": None,
                        "provenance": "listed in the official new-legislation feed; publication is not commencement"}})
        out.append({"feed": feed, "result": "baseline" if baseline else "checked", "new": [] if baseline else
                    [{k: d[k] for k in ("_id", "title", "url", "commencement")} for d in new], "seen": len(new), "_docs": new})
    return out


async def check_fact_sources(db, fetch) -> List[dict]:
    """Source-existence metadata for Phase 2A-1 records whose source is legislation.gov.uk. Reads lex_lessons only;
    the caller writes to law_watch_fact_checks. Review status and wording of the records are never touched."""
    out = []
    async for r in db.lex_lessons.find({"source_url": {"$regex": r"^https://www\.legislation\.gov\.uk/"}},
                                       {"_id": 0, "id": 1, "source_url": 1}):
        try:
            code, body = await fetch(r["source_url"].rstrip("/") + "/data.xml")
        except Exception:
            code, body = 0, ""
        ok = code == 200 and "<Legislation" in body
        out.append({"lesson_id": r.get("id"), "source_url": r["source_url"], "http_status": code, "checked_at": _now().isoformat(),
                    "A_metadata": {"label": STATUS_A, "verified": ok, "detail": "official source exists" if ok else "not confirmed"},
                    "C_interpretation": {"label": STATUS_C, "verified": False}, "D_professional_review": review_status(None)})
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


REAL_CHANGES = {"repealed", "partly_repealed", "commenced", "status_changed", "wording_amended", "extent_changed",
                "amendment_pending", "pending_changes_applied", "new_affecting_instrument", "commencement_date_recorded",
                "provision_not_found"}


def _act_url(url: str) -> str:
    return re.sub(r"/(?:section|article|regulation)/[^/]+$", "", url or "")


async def linked_knowledge(db, rec: dict) -> dict:
    """Lex knowledge that relies on this provision: official-source rules (lex_guidance) and stored facts (lex_lessons)."""
    import lex_guidance
    url, act = rec["url"].rstrip("/"), _act_url(rec["url"])
    rules = [r[0] for r in lex_guidance.RULES if any(u.rstrip("/") in (url, act) or u.rstrip("/").startswith(url + "/")
                                                     for u in r[4])]
    rx = re.escape(act.split("legislation.gov.uk/")[-1]) + r"(?![0-9])"
    lessons = [d["id"] async for d in db.lex_lessons.find(
        {"$or": [{"review_meta.source_url": {"$regex": rx}}, {"why": {"$regex": rx}}, {"text": {"$regex": rx}}]}, {"id": 1})]
    return {"rules": rules, "lessons": lessons[:50]}


def proposal_for(res: dict, links: dict, now: str) -> dict:
    """A detected source change awaiting professional review. Never an approved legal fact."""
    rec = res["record"]
    return {"_id": res["version_id"], "key": res["key"], "url": rec["url"], "title": rec.get("title"),
            "provision": rec.get("provision"), "jurisdiction": rec.get("jurisdiction_label"), "change_types": res["changes"],
            "commencement": rec.get("commencement"), "affecting_instruments": rec.get("affecting_instruments") or [],
            "detected_at": now, "source_status": "source fact (official metadata verified)",
            "interpretation": "not assessed", "status": "awaiting_review", "linked_rules": links["rules"],
            "linked_lessons": links["lessons"], "decision": None}


DECISIONS = {"approve": "approved", "reject": "rejected", "amend": "amend_requested"}


async def decide_update(db, pid: str, decision: str, review: dict, notes: str, actor: str) -> dict:
    """Qualified reviewer decision on a detected change. Approval needs a full regulated-reviewer record and records the
    review on the source record only — linked Lex facts stay withheld until re-signed in the existing sign-off flow."""
    if decision not in DECISIONS:
        return {"refused": "Unknown decision."}
    p = await db.law_update_proposals.find_one({"_id": pid})
    if not p:
        return {"refused": "No such update."}
    if p["status"] not in ("awaiting_review", "amend_requested"):
        return {"refused": f"This update is already {p['status']}."}
    review = {k: str(review.get(k) or "").strip()[:120] for k in ("reviewer_name", "regulator", "registration_number")}
    review["regulator"] = review["regulator"].upper()
    rs = review_status({**review, "reviewed_at": _now().isoformat()})
    if decision == "approve" and not rs["verified"]:
        return {"refused": "Approval needs the reviewer's name, regulator (e.g. SRA) and registration number."}
    if decision != "approve" and not (review.get("reviewer_name") or "").strip():
        return {"refused": "Please give the reviewer's name."}
    if decision == "amend" and not (notes or "").strip():
        return {"refused": "Please say what needs amending."}
    now = _now().isoformat()
    rec_review = {k: rs.get(k) for k in ("reviewer_name", "regulator", "registration_number", "reviewed_at")}
    dec = {"decision": decision, "notes": (notes or "")[:2000], "by": actor, "at": now,
           "reviewer": rec_review if rs["verified"] else {"reviewer_name": (review.get("reviewer_name") or "")[:120]}}
    won = await db.law_update_proposals.update_one(
        {"_id": pid, "status": {"$in": ["awaiting_review", "amend_requested"]}},
        {"$set": {"status": DECISIONS[decision], "decision": dec}, "$push": {"history": dec}})
    if not won.matched_count:  # another decision landed first
        return {"refused": "This update was decided by someone else just now — reload to see it."}
    if decision == "approve":
        pr = {**rec_review, "scope": "effect of this recorded change"}
        await db.law_watch_records.update_one({"key": p["key"], "version_id": pid}, {"$set": {
            "professional_review": pr, "review_pending": False,
            "verification.D_professional_review": review_status(rec_review)}})
    elif decision == "reject":
        await db.law_watch_records.update_one({"key": p["key"], "version_id": pid}, {"$set": {"review_pending": False,
                                                                                            "change_rejected": True}})
    await db.law_watch_audit.insert_one({"_id": str(uuid.uuid4()), "at": now, "actor": actor, "action": f"update_{decision}",
                                         "proposal": pid})
    return {"ok": True, "status": DECISIONS[decision]}


async def ensure_indexes(db) -> None:
    await db.law_watch_records.create_index("key", unique=True)
    await db.law_watch_records.create_index("url")
    await db.law_watch_history.create_index([("key", 1), ("recorded_at", 1)])
    await db.law_watch_seen.create_index("feed")


def proposal_code(results: List[dict], new_leg: List[dict], fact_checks: List[dict]) -> str:
    """Fingerprint of exactly what an authorised run would write. Any source change gives a different code."""
    prop = {"provisions": sorted([r["key"], r["version_id"]] for r in results if r.get("write") == "new_version"),
            "new_legislation": sorted(d["_id"] for f in new_leg for d in f["_docs"]),
            "fact_checks": sorted([str(f["lesson_id"]), f["A_metadata"]["verified"]] for f in fact_checks)}
    return hashlib.sha256(json.dumps(prop, sort_keys=True).encode()).hexdigest()[:16]


async def _write(db, results: List[dict], prevs: List[Optional[dict]], new_leg: List[dict], fact_checks: List[dict], now: str):
    await ensure_indexes(db)
    for res, prev in zip(results, prevs):
        key, rec = res["key"], res["record"]
        if res["result"] == "not_found" and prev:
            await db.law_watch_records.update_one({"key": key}, {"$set": {"last_checked": now},
                                                                  "$addToSet": {"anomalies": "provision no longer found"}})
        if res.get("write") == "unchanged":
            await db.law_watch_records.update_one({"key": key}, {"$set": {"last_checked": now}})
        if res.get("write") != "new_version":
            continue
        if prev:
            await db.law_watch_history.update_many({"key": key, "superseded_at": None}, {"$set": {"superseded_at": now}})
        rec.update(last_checked=now, version_id=res["version_id"], previous_version_id=(prev or {}).get("version_id"),
                   previous_text_hash=(prev or {}).get("text_hash"), last_change={"at": now, "types": res["changes"]})
        await db.law_watch_history.update_one({"_id": res["version_id"]}, {"$setOnInsert": {
            **{k: rec[k] for k in ("key", "title", "url", "status", "extent", "text_hash", "version_date", "version_start_date",
                                   "pending_effects", "commencement", "previous_version_id")},
            "change_types": res["changes"], "recorded_at": now, "superseded_at": None}}, upsert=True)
        real = set(res["changes"]) & REAL_CHANGES
        rec["review_pending"] = bool(real)
        await db.law_watch_records.update_one({"key": key}, {"$set": rec}, upsert=True)
        if real:
            links = await linked_knowledge(db, rec)
            await db.law_update_proposals.update_one({"_id": res["version_id"]},
                                                     {"$setOnInsert": proposal_for(res, links, now)}, upsert=True)
            if links["lessons"]:  # signed-off facts that rely on a changed provision are withheld until re-reviewed
                await db.lex_lessons.update_many({"id": {"$in": links["lessons"]}, "needs_review": {"$ne": True}}, {"$set": {
                    "needs_review": True, "needs_review_since": now,
                    "needs_review_reason": f"official source changed: {rec.get('title')} {rec.get('provision')}"}})
    for f in new_leg:
        for d in f["_docs"]:
            await db.law_watch_seen.update_one({"_id": d["_id"]}, {"$setOnInsert": {**d, "first_seen": now}}, upsert=True)
    for f in fact_checks:
        await db.law_watch_fact_checks.update_one({"lesson_id": f["lesson_id"]}, {"$set": f}, upsert=True)


async def run_check(db, fetch=None, dry_run: bool = True, confirm: Optional[str] = None, items: Optional[List[dict]] = None,
                    today: Optional[date] = None, feeds: bool = True, facts: bool = True, actor: str = "",
                    scope: Optional[str] = None, authorisation_id: Optional[str] = None, scheduled: bool = False) -> dict:
    """Dry run (default) writes nothing and returns the proposed changes plus a proposal code. A write run fetches once,
    recomputes the code and writes only if it equals `confirm`. Only records with verified official metadata (A) are written."""
    fetch, today = fetch or _fetch, today or _now().date()
    started, now = _now(), _now().isoformat()
    its = items if items is not None else WATCHLIST
    keys = [None if validate_item(it) else item_key(it) for it in its]
    prevs = [await db.law_watch_records.find_one({"key": k}, {"_id": 0}) if k else None for k in keys]
    sem = asyncio.Semaphore(3)  # polite: at most 3 requests at once, one attempt each, no retries

    async def one(it, prev):
        async with sem:
            return await check_item(it, fetch, prev, today)
    results = list(await asyncio.gather(*[one(it, p) for it, p in zip(its, prevs)]))
    for res, prev in zip(results, prevs):
        if res["result"] != "checked":
            continue
        if not res["record"]["verification"]["A_metadata"]["verified"]:
            res["result"] = "held_unverified"  # incomplete / inconsistent official metadata is never written
            continue
        res["version_id"] = _version_id(res["key"], res["record"])
        res["write"] = "unchanged" if res["changes"] == ["unchanged"] or (prev or {}).get("version_id") == res["version_id"] \
            else "new_version"
    new_leg = await check_new_legislation(db, fetch, str(today.year)) if feeds else []
    fact_checks = await check_fact_sources(db, fetch) if facts else []
    code = proposal_code(results, new_leg, fact_checks)
    refused = None
    if not dry_run and not scheduled and confirm != code:
        refused = "Proposal code does not match this check — the official sources or records changed since the dry run, " \
                  "or no code was given. Nothing was written; run a new dry run and review it."
    wrote = not dry_run and not refused
    if wrote:
        await _write(db, results, prevs, new_leg, fact_checks, now)
    changed = [r for r in results if r["changes"] and r["changes"] != ["unchanged"] and r["result"] == "checked"]
    summary = {"checked": sum(r["result"] == "checked" for r in results),
               "unchanged": sum(r.get("write") == "unchanged" for r in results),
               "to_write": sum(r.get("write") == "new_version" for r in results),
               "changed": sum(1 for r in changed if r["changes"] != ["first_recorded"]),
               "first_recorded": sum(r["changes"] == ["first_recorded"] and r["result"] == "checked" for r in results),
               "held_unverified": sum(r["result"] == "held_unverified" for r in results),
               "unavailable": sum(r["result"] == "source_unavailable" for r in results),
               "not_found": sum(r["result"] == "not_found" for r in results),
               "rejected": sum(r["result"] in ("unsupported_jurisdiction", "unsupported_type", "invalid_identifier") for r in results),
               "new_legislation": sum(len(f.get("new") or []) for f in new_leg),
               "fact_sources_checked": len(fact_checks), "fact_sources_confirmed": sum(f["A_metadata"]["verified"] for f in fact_checks)}
    saved = [r["key"] for r in results if r.get("write") == "new_version"] if wrote else []
    proposed = []
    for r in results:
        if r.get("write") == "new_version" and set(r["changes"]) & REAL_CHANGES:
            links = await linked_knowledge(db, r["record"])
            proposed.append({"key": r["key"], "changes": r["changes"], "linked_rules": links["rules"],
                             "linked_lessons": len(links["lessons"]), "becomes": "awaiting professional review"})
    report = {"id": str(uuid.uuid4()), "at": now, "dry_run": dry_run, "written": wrote, "refused": refused,
              "proposal_code": code, "actor": actor, "scope": scope, "authorisation_id": authorisation_id,
              "saved_keys": saved, "summary": summary,
              "items": [{"key": r["key"], "result": r["result"], "changes": r["changes"], "write": r.get("write"),
                         "title": (r["record"] or {}).get("title"), "url": (r["record"] or {}).get("url"),
                         "extent": (r["record"] or {}).get("extent"), "version_date": (r["record"] or {}).get("version_date"),
                         "error": r.get("error"), "status": (r["record"] or {}).get("status"),
                         "commencement": (r["record"] or {}).get("commencement"),
                         "verification": (r["record"] or {}).get("verification")} for r in results],
              "new_legislation": [{k: v for k, v in f.items() if k != "_docs"} for f in new_leg],
              "affected_topics": affected_topics(changed), "notifications_sent": 0, "proposed_updates": proposed,
              "ms": int((_now() - started).total_seconds() * 1000)}
    if wrote:
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
    if rec.get("review_pending"):
        out.append(f"The official record shows a recent change to {lab} that hasn't been reviewed yet — check the current "
                   f"official text before relying on it: {rec['url']}")
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
