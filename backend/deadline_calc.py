"""Exact legal deadline maths. An LLM only extracts the facts; Python does the date arithmetic."""
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
ET_NEW_LIMIT_FROM = date(2026, 10, 1)

_HINT_RE = re.compile(
    r"\b(dismiss|sacked|fired|redundan|tribunal|acas|discriminat|wages|ilr|indefinite leave|settle|citizenship|naturalis|"
    r"visa|overstay|expir|section 8|section 21|evict|notice|possession|landlord|debt|owe|contract|injur|accident|negligen|"
    r"limitation|small claim|benefit|universal credit|pip|esa|dwp|reconsideration|appeal|deadline|how long|when can|"
    r"how much time|time limit|too late)\w*", re.I)
_DATE_RE = re.compile(r"\d|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|\b(today|yesterday|tomorrow|"
                      r"last|next|ago|week|month|year)\b", re.I)


def fmt(d: date) -> str:
    return d.strftime("%A %d %B %Y")


def _d(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _et(c) -> List[str]:
    ev = _d(c.get("event_date"))
    if not ev:
        return []
    months = 6 if ev >= ET_NEW_LIMIT_FROM else 3
    t = ev + relativedelta(months=months)
    limit = t if t.day != ev.day else t - timedelta(days=1)
    out = [f"Employment tribunal: act/dismissal on {fmt(ev)} → normal time limit ({months} months less one day) ends "
           f"{fmt(limit)}. ACAS early conciliation must be started on or before this date."]
    a, b = _d(c.get("acas_date")), _d(c.get("certificate_date"))
    if a and b and b >= a and a <= limit:
        ext = limit + timedelta(days=(b - a).days)
        floor = b + relativedelta(months=1)
        final = max(ext, floor)
        out.append(f"With ACAS contacted {fmt(a)} and certificate issued {fmt(b)}, the ET1 claim deadline becomes {fmt(final)}.")
    return out


def _citizenship(c) -> List[str]:
    ilr = _d(c.get("ilr_date"))
    if not ilr:
        return []
    if c.get("married_to_british"):
        return [f"Citizenship: spouse/civil partner of a British citizen with ILR from {fmt(ilr)} can apply from {fmt(ilr)} "
                "(also needs 3 years' UK residence, max 270 days absent, max 90 in the last 12 months)."]
    return [f"Citizenship: ILR granted {fmt(ilr)} → earliest naturalisation application {fmt(ilr + relativedelta(months=12))} "
            "(12 months after ILR; also 5 years' residence, max 450 days absent, max 90 in the last 12 months)."]


def _ilr(c) -> List[str]:
    start = _d(c.get("route_start_date"))
    if not start:
        return []
    years = int(c.get("qualifying_years") or 5)
    q = start + relativedelta(years=years)
    return [f"ILR: {years}-year qualifying period from {fmt(start)} completes {fmt(q)}; earliest application "
            f"{fmt(q - timedelta(days=28))} (no more than 28 days early)."]


def _visa(c) -> List[str]:
    exp = _d(c.get("expiry_date"))
    if not exp:
        return []
    return [f"Visa expiry {fmt(exp)}: apply to extend/switch on or before this date so existing permission continues while "
            f"it is decided (section 3C). After it, the person is an overstayer; a late application by {fmt(exp + timedelta(days=14))} "
            "may only be accepted if there was a good reason beyond their control."]


def _section8(c) -> List[str]:
    served = _d(c.get("served_date"))
    if not served:
        return []
    g = str(c.get("ground") or "").upper().replace("GROUND", "").strip()
    out = []
    if g in ("1", "1A"):
        earliest = served + relativedelta(months=4)
        ts = _d(c.get("tenancy_start_date"))
        if ts and earliest < ts + relativedelta(months=12):
            earliest = ts + relativedelta(months=12)
            out.append(f"Ground {g} cannot take effect in the first 12 months of the tenancy (from {fmt(ts)}).")
        out.insert(0, f"Section 8 Ground {g} (sell / move in) served {fmt(served)} → 4 months' notice; earliest date a "
                      f"possession claim can start: {fmt(earliest)}.")
    elif g == "8":
        out.append(f"Section 8 Ground 8 (3+ months' rent arrears) served {fmt(served)} → 4 weeks' notice; earliest date a "
                   f"possession claim can start: {fmt(served + timedelta(weeks=4))}. Arrears must still be 3 months at the hearing.")
    return out


def _limitation(c) -> List[str]:
    ev = _d(c.get("event_date"))
    kind = (c.get("claim_kind") or "").lower()
    if not ev:
        return []
    scot = (c.get("jurisdiction") or "").lower().startswith("scot")
    if "injur" in kind:
        return [f"Personal injury (England & Wales and Scotland): 3 years from the injury or date of knowledge — from {fmt(ev)} "
                f"the court claim must be issued by {fmt(ev + relativedelta(years=3))}. Under-18s: clock starts at 18."]
    yrs = 5 if scot else 6
    where = "Scotland (prescription)" if scot else "England & Wales"
    return [f"{where}: contract/debt claims must be issued within {yrs} years — from {fmt(ev)} that is by "
            f"{fmt(ev + relativedelta(years=yrs))}. A written acknowledgment or part-payment of a debt can restart the clock."]


def _benefit(c) -> List[str]:
    out = []
    dec, mrn = _d(c.get("decision_date")), _d(c.get("mrn_date"))
    if dec:
        out.append(f"Benefits: decision dated {fmt(dec)} → ask for mandatory reconsideration by {fmt(dec + relativedelta(months=1))} "
                   f"(late requests with good reason up to {fmt(dec + relativedelta(months=13))}).")
    if mrn:
        out.append(f"Benefits appeal: Mandatory Reconsideration Notice dated {fmt(mrn)} → SSCS1 appeal must reach HMCTS by "
                   f"{fmt(mrn + relativedelta(months=1))} (late appeals with reasons up to {fmt(mrn + relativedelta(months=13))}).")
    return out


CALCS = {"employment_tribunal": _et, "citizenship_after_ilr": _citizenship, "ilr_eligibility": _ilr,
         "visa_expiry": _visa, "section8_notice": _section8, "limitation": _limitation, "benefit_challenge": _benefit}

EXTRACT_SYSTEM = """Extract dated legal events from the user's message (and recent context) so software can calculate deadlines.
Resolve relative dates ("last Friday", "next week", "3 weeks ago") using TODAY. Only include items where a date is stated or clearly implied.
Reply ONLY with JSON: {"calcs": [ ... ]} — empty list if none. Allowed items:
{"type":"employment_tribunal","event_date":"YYYY-MM-DD","acas_date":"YYYY-MM-DD|null","certificate_date":"YYYY-MM-DD|null"}
{"type":"citizenship_after_ilr","ilr_date":"YYYY-MM-DD","married_to_british":true|false}
{"type":"ilr_eligibility","route_start_date":"YYYY-MM-DD","qualifying_years":5|10}
{"type":"visa_expiry","expiry_date":"YYYY-MM-DD"}
{"type":"section8_notice","served_date":"YYYY-MM-DD","ground":"1|1A|8","tenancy_start_date":"YYYY-MM-DD|null"}
{"type":"limitation","event_date":"YYYY-MM-DD","claim_kind":"contract|debt|personal_injury","jurisdiction":"england_wales|scotland"}
{"type":"benefit_challenge","decision_date":"YYYY-MM-DD|null","mrn_date":"YYYY-MM-DD|null"}"""


def compute(calcs: list) -> List[str]:
    lines: List[str] = []
    for c in calcs[:6]:
        fn = CALCS.get((c or {}).get("type"))
        if fn:
            try:
                lines += fn(c)
            except Exception as e:
                logger.warning(f"deadline calc failed for {c}: {e!r}")
    return lines


async def build_deadline_block(message: str, context: str, api_key: str) -> str:
    if not (_HINT_RE.search(message or "") and _DATE_RE.search(message or "")):
        return ""
    today = datetime.now(ZoneInfo("Europe/London")).date()
    try:
        chat = LlmChat(api_key=api_key, session_id=f"deadline-{uuid.uuid4()}", system_message=EXTRACT_SYSTEM) \
            .with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=500)
        raw = await chat.send_message(UserMessage(
            text=f"TODAY: {today.isoformat()} ({fmt(today)})\n\nRECENT CONTEXT:\n{(context or '')[-1500:]}\n\nMESSAGE:\n{message[:3000]}"))
        m = re.search(r"\{.*\}", raw or "", re.S)
        calcs = json.loads(m.group(0)).get("calcs", []) if m else []
    except Exception as e:
        logger.warning(f"deadline extraction failed: {e!r}")
        return ""
    lines = compute(calcs)
    if not lines:
        return ""
    return ("\n\nEXACT DATES CALCULATED BY THE APP — use these dates exactly, do not recalculate or round them. "
            "Say they are based on the dates the user gave and that a regulated adviser should confirm:\n- "
            + "\n- ".join(lines) + "\n")
