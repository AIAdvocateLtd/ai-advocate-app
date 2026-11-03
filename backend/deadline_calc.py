"""Exact legal deadline maths. An LLM only extracts the facts; Python does the date arithmetic."""
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)
ET_NEW_LIMIT_FROM = date(2026, 10, 1)
UK = ZoneInfo("Europe/London")
Item = Tuple[str, Optional[str], Optional[date]]  # (explanation, reminder title, reminder date)

_HINT_RE = re.compile(
    r"\b(dismiss|sacked|fired|redundan|tribunal|acas|lra|discriminat|wages|ilr|indefinite leave|settle|citizenship|naturalis|"
    r"visa|overstay|expir|section 8|section 21|section 173|notice|evict|possession|landlord|tenan|deposit|debt|owe|contract|"
    r"injur|accident|negligen|limitation|small claim|benefit|universal credit|pip|esa|dwp|reconsideration|appeal|divorce|"
    r"deadline|how long|when can|how much time|time limit|too late)\w*", re.I)
_DATE_RE = re.compile(r"\d|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|\b(today|yesterday|tomorrow|"
                      r"last|next|ago|week|month|year)\b", re.I)


def fmt(d: date) -> str:
    return d.strftime("%A %d %B %Y")


def _d(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _months_less_day(ev: date, months: int) -> date:
    t = ev + relativedelta(months=months)
    return t if t.day != ev.day else t - timedelta(days=1)


def _working_days(start: date, n: int) -> date:
    d = start
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def _et(c) -> List[Item]:
    ev = _d(c.get("event_date"))
    if not ev:
        return []
    if (c.get("jurisdiction") or "").lower().startswith("northern"):
        limit = _months_less_day(ev, 3)
        return [(f"Northern Ireland industrial tribunal: act/dismissal on {fmt(ev)} → 3 months less one day ends {fmt(limit)}. "
                 "Early conciliation is with the Labour Relations Agency (LRA), not ACAS, and must start by then.",
                 "Contact the LRA / tribunal time limit", limit)]
    months = 6 if ev >= ET_NEW_LIMIT_FROM else 3
    limit = _months_less_day(ev, months)
    out: List[Item] = [(f"Employment tribunal (England, Wales, Scotland): act/dismissal on {fmt(ev)} → normal time limit "
                        f"({months} months less one day) ends {fmt(limit)}. ACAS early conciliation must be started on or before this date.",
                        "Contact ACAS (tribunal time limit)", limit)]
    a, b = _d(c.get("acas_date")), _d(c.get("certificate_date"))
    if a and b and b >= a and a <= limit:
        final = max(limit + timedelta(days=(b - a).days), b + relativedelta(months=1))
        out.append((f"With ACAS contacted {fmt(a)} and certificate issued {fmt(b)}, the ET1 claim deadline becomes {fmt(final)}.",
                    "Submit ET1 tribunal claim", final))
    return out


def _citizenship(c) -> List[Item]:
    ilr = _d(c.get("ilr_date"))
    if not ilr:
        return []
    if c.get("married_to_british"):
        return [(f"Citizenship: spouse/civil partner of a British citizen with ILR from {fmt(ilr)} can apply from {fmt(ilr)} "
                 "(also 3 years' UK residence, max 270 days absent, max 90 in the last 12 months).", None, None)]
    when = ilr + relativedelta(months=12)
    return [(f"Citizenship: ILR granted {fmt(ilr)} → earliest naturalisation application {fmt(when)} "
             "(12 months after ILR; also 5 years' residence, max 450 days absent, max 90 in the last 12 months).",
             "Earliest date to apply for British citizenship", when)]


def _ilr(c) -> List[Item]:
    start = _d(c.get("route_start_date"))
    if not start:
        return []
    years = int(c.get("qualifying_years") or 5)
    q = start + relativedelta(years=years)
    early = q - timedelta(days=28)
    return [(f"ILR: {years}-year qualifying period from {fmt(start)} completes {fmt(q)}; earliest application {fmt(early)} "
             "(no more than 28 days early).", "Earliest date to apply for ILR", early)]


def _visa(c) -> List[Item]:
    exp = _d(c.get("expiry_date"))
    if not exp:
        return []
    return [(f"Visa expiry {fmt(exp)}: apply to extend/switch on or before this date so existing permission continues while "
             f"it is decided (section 3C). After it, the person is an overstayer; a late application by {fmt(exp + timedelta(days=14))} "
             "may only be accepted if there was a good reason beyond their control.", "Visa expires — apply before this date", exp)]


def _tenancy_notice(c) -> List[Item]:
    served = _d(c.get("served_date"))
    if not served:
        return []
    j = (c.get("jurisdiction") or "england").lower()
    ts = _d(c.get("tenancy_start_date"))
    if j.startswith("wales"):
        end = served + relativedelta(months=6)
        note = ""
        if ts and served < ts + relativedelta(months=6):
            note = f" Warning: a section 173 notice cannot be given in the first 6 months of occupation (from {fmt(ts)}), so it may be invalid."
        return [(f"Wales section 173 (no-fault) notice served {fmt(served)} → 6 months' notice; the contract-holder does not "
                 f"have to leave before {fmt(end)}.{note}", "Landlord's notice ends", end)]
    if j.startswith("scot"):
        long_stay = bool(ts and served > ts + relativedelta(months=6))
        days = 84 if long_stay else 28
        end = served + timedelta(days=days)
        basis = "tenant there more than 6 months" if long_stay else "tenant there 6 months or less (or start date unknown)"
        return [(f"Scotland notice to leave served {fmt(served)} → {days} days ({basis}; some grounds differ); earliest date the "
                 f"landlord can apply to the First-tier Tribunal: {fmt(end)}.", "Notice to leave ends", end)]
    if j.startswith("northern"):
        if not ts:
            return [("Northern Ireland notice to quit: 4 weeks if the tenancy is under 12 months, 8 weeks if 1–10 years, "
                     "12 weeks if over 10 years — need the tenancy start date to give an exact date.", None, None)]
        yrs = relativedelta(served, ts).years
        weeks = 4 if yrs < 1 else (8 if yrs < 10 else 12)
        end = served + timedelta(weeks=weeks)
        return [(f"Northern Ireland notice to quit served {fmt(served)} → {weeks} weeks' notice; it cannot end before {fmt(end)}.",
                 "Notice to quit ends", end)]
    g = str(c.get("ground") or "").upper().replace("GROUND", "").strip()
    if g in ("1", "1A"):
        earliest = served + relativedelta(months=4)
        extra = ""
        if ts and earliest < ts + relativedelta(months=12):
            earliest = ts + relativedelta(months=12)
            extra = f" Ground {g} cannot take effect in the first 12 months of the tenancy (from {fmt(ts)})."
        return [(f"England section 8 Ground {g} (sell / move in) served {fmt(served)} → 4 months' notice; earliest date a "
                 f"possession claim can start: {fmt(earliest)}.{extra}", "Earliest date landlord can go to court", earliest)]
    if g == "8":
        end = served + timedelta(weeks=4)
        return [(f"England section 8 Ground 8 (3+ months' rent arrears) served {fmt(served)} → 4 weeks' notice; earliest date a "
                 f"possession claim can start: {fmt(end)}. Arrears must still be 3 months at the hearing.",
                 "Earliest date landlord can go to court", end)]
    return []


def _deposit(c) -> List[Item]:
    got = _d(c.get("paid_date"))
    if not got:
        return []
    j = (c.get("jurisdiction") or "england").lower()
    if j.startswith("scot"):
        start = _d(c.get("tenancy_start_date")) or got
        due = _working_days(start, 30)
        return [(f"Scotland: deposit must be lodged in an approved scheme within 30 working days of the tenancy start "
                 f"({fmt(start)}) → by {fmt(due)}. Penalty up to 3× the deposit via the First-tier Tribunal.",
                 "Deposit must be protected by", due)]
    days, where = (28, "Northern Ireland") if j.startswith("northern") else (30, "England & Wales")
    due = got + timedelta(days=days)
    return [(f"{where}: deposit paid {fmt(got)} must be protected (and prescribed information given) within {days} days → by "
             f"{fmt(due)}. Penalty up to 3× the deposit (1–3× in England & Wales).", "Deposit must be protected by", due)]


def _limitation(c) -> List[Item]:
    ev = _d(c.get("event_date"))
    if not ev:
        return []
    kind = (c.get("claim_kind") or "").lower()
    j = (c.get("jurisdiction") or "").lower()
    if "injur" in kind:
        end = ev + relativedelta(years=3)
        return [(f"Personal injury (all UK nations): 3 years from the injury or date of knowledge — from {fmt(ev)} the court "
                 f"claim must be issued by {fmt(end)}. Under-18s: clock starts at 18.", "Personal injury claim time limit", end)]
    yrs, where = (5, "Scotland (prescription)") if j.startswith("scot") else (6, "England, Wales & Northern Ireland")
    end = ev + relativedelta(years=yrs)
    return [(f"{where}: contract/debt claims must be brought within {yrs} years — from {fmt(ev)} that is by {fmt(end)}. "
             "A written acknowledgment or part-payment of a debt can restart the clock.", "Contract / debt claim time limit", end)]


def _benefit(c) -> List[Item]:
    out: List[Item] = []
    dec, mrn = _d(c.get("decision_date")), _d(c.get("mrn_date"))
    if dec and (c.get("jurisdiction") or "").lower().startswith("scot") and c.get("scottish_benefit"):
        due = dec + relativedelta(months=1)
        return [(f"Scotland: decision dated {fmt(dec)} is from Social Security Scotland (e.g. Adult Disability Payment), which has "
                 "its own redetermination deadline — confirm it on the decision letter or mygov.scot. As a safe working date, act by "
                 f"{fmt(due)}.", "Challenge Social Security Scotland decision (check exact deadline)", due)]
    if dec:
        due = dec + relativedelta(months=1)
        out.append((f"Benefits: decision dated {fmt(dec)} → ask for mandatory reconsideration by {fmt(due)} (late requests with "
                    f"good reason up to {fmt(dec + relativedelta(months=13))}).", "Ask for mandatory reconsideration", due))
    if mrn:
        due = mrn + relativedelta(months=1)
        out.append((f"Benefits appeal: Mandatory Reconsideration Notice dated {fmt(mrn)} → appeal must reach the tribunal by "
                    f"{fmt(due)} (late appeals with reasons up to {fmt(mrn + relativedelta(months=13))}).",
                    "Benefit appeal (SSCS1) deadline", due))
    return out


def _divorce(c) -> List[Item]:
    app = _d(c.get("application_date"))
    if not app:
        return []
    co = app + timedelta(weeks=20)
    fo = co + timedelta(weeks=6, days=1)
    return [(f"Divorce (England & Wales): application issued {fmt(app)} → earliest conditional order application "
             f"{fmt(co)} (20 weeks); earliest final order about {fmt(fo)} (6 weeks and 1 day after the conditional order is made, "
             "so later if the conditional order takes longer).", "Earliest date to apply for divorce conditional order", co)]


CALCS = {"employment_tribunal": _et, "citizenship_after_ilr": _citizenship, "ilr_eligibility": _ilr,
         "visa_expiry": _visa, "tenancy_notice": _tenancy_notice, "section8_notice": _tenancy_notice,
         "deposit_protection": _deposit, "limitation": _limitation, "benefit_challenge": _benefit, "divorce": _divorce}

EXTRACT_SYSTEM = """Extract dated legal events from the user's message (and recent context) so software can calculate deadlines.
Resolve relative dates ("last Friday", "next week", "3 weeks ago") using TODAY. Only include items where a date is stated or clearly implied.
jurisdiction is one of england|wales|scotland|northern_ireland (use the user's stated or profile location; default england).
Reply ONLY with JSON: {"calcs": [ ... ]} — empty list if none. Allowed items:
{"type":"employment_tribunal","event_date":"YYYY-MM-DD","acas_date":"YYYY-MM-DD|null","certificate_date":"YYYY-MM-DD|null","jurisdiction":"..."}
{"type":"citizenship_after_ilr","ilr_date":"YYYY-MM-DD","married_to_british":true|false}
{"type":"ilr_eligibility","route_start_date":"YYYY-MM-DD","qualifying_years":5|10}
{"type":"visa_expiry","expiry_date":"YYYY-MM-DD"}
{"type":"tenancy_notice","served_date":"YYYY-MM-DD","ground":"1|1A|8|null","tenancy_start_date":"YYYY-MM-DD|null","jurisdiction":"..."}
{"type":"deposit_protection","paid_date":"YYYY-MM-DD","tenancy_start_date":"YYYY-MM-DD|null","jurisdiction":"..."}
{"type":"limitation","event_date":"YYYY-MM-DD","claim_kind":"contract|debt|personal_injury","jurisdiction":"..."}
{"type":"benefit_challenge","decision_date":"YYYY-MM-DD|null","mrn_date":"YYYY-MM-DD|null","jurisdiction":"...","scottish_benefit":true|false}
(scottish_benefit = true only for Social Security Scotland benefits such as Adult Disability Payment, Child Disability Payment, Scottish Child Payment, or a "PIP-style" disability benefit for someone living in Scotland)
{"type":"divorce","application_date":"YYYY-MM-DD"}"""


def compute(calcs: list) -> List[Item]:
    items: List[Item] = []
    for c in calcs[:6]:
        fn = CALCS.get((c or {}).get("type"))
        if fn:
            try:
                items += fn(c)
            except Exception as e:
                logger.warning(f"deadline calc failed for {c}: {e!r}")
    return items


async def build_deadlines(message: str, context: str, api_key: str, jurisdiction: Optional[str] = None):
    """Returns (prompt_block, [(title, date)] future reminder dates)."""
    if not (_HINT_RE.search(message or "") and _DATE_RE.search(message or "")):
        return "", []
    today = datetime.now(UK).date()
    try:
        chat = LlmChat(api_key=api_key, session_id=f"deadline-{uuid.uuid4()}", system_message=EXTRACT_SYSTEM) \
            .with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=500)
        raw = await chat.send_message(UserMessage(
            text=f"TODAY: {today.isoformat()} ({fmt(today)})\nUSER PROFILE JURISDICTION: {jurisdiction or 'unknown'}\n\n"
                 f"RECENT CONTEXT:\n{(context or '')[-1500:]}\n\nMESSAGE:\n{message[:3000]}"))
        m = re.search(r"\{.*\}", raw or "", re.S)
        calcs = json.loads(m.group(0)).get("calcs", []) if m else []
    except Exception as e:
        logger.warning(f"deadline extraction failed: {e!r}")
        return "", []
    items = compute(calcs)
    if not items:
        return "", []
    block = ("\n\nEXACT DATES CALCULATED BY THE APP — use these dates exactly, do not recalculate or round them. "
             "Say they are based on the dates the user gave and that a regulated adviser should confirm. "
             "Future dates are saved to the user's Reminders automatically and they will be emailed 7, 3 and 1 day before — "
             "mention this briefly:\n- " + "\n- ".join(i[0] for i in items) + "\n")
    reminders = [(t, d) for _, t, d in items if t and d and d >= today]
    return block, reminders


def reminder_due_iso(d: date) -> str:
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=UK).isoformat()
