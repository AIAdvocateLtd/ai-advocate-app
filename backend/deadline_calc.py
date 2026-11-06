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
    r"deadline|how long|when can|how much time|time limit|too late|court|claim form|defence|ccj|summons|hearing|sheriff)\w*", re.I)
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


_BH_EW = {"2025": ["01-01", "04-18", "04-21", "05-05", "05-26", "08-25", "12-25", "12-26"],
          "2026": ["01-01", "04-03", "04-06", "05-04", "05-25", "08-31", "12-25", "12-28"],
          "2027": ["01-01", "03-26", "03-29", "05-03", "05-31", "08-30", "12-27", "12-28"]}
_BH_SCOT = {"2025": ["01-01", "01-02", "04-18", "05-05", "05-26", "08-04", "12-01", "12-25", "12-26"],
            "2026": ["01-01", "01-02", "04-03", "05-04", "05-25", "08-03", "11-30", "12-25", "12-28"],
            "2027": ["01-01", "01-04", "03-26", "05-03", "05-31", "08-02", "11-30", "12-27", "12-28"]}
_BH_NI = {"2025": _BH_EW["2025"] + ["03-17", "07-14"], "2026": _BH_EW["2026"] + ["03-17", "07-13"],
          "2027": _BH_EW["2027"] + ["03-17", "07-12"]}
BANK_HOLIDAY_YEARS = (2025, 2027)  # official GOV.UK lists; outside this range only weekends are excluded


def bank_holidays(nation: str) -> set:
    table = _BH_SCOT if (nation or "").startswith("scot") else _BH_NI if (nation or "").startswith("northern") else _BH_EW
    return {date.fromisoformat(f"{y}-{md}") for y, mds in table.items() for md in mds}


def _working_days(start: date, n: int, nation: str = "england") -> date:
    hols = bank_holidays(nation)
    d = start
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in hols:
            n -= 1
    return d


def _closed_day_note(d: date, nation: str = "england") -> str:
    if d.weekday() >= 5 or d in bank_holidays(nation):
        what = "a weekend" if d.weekday() >= 5 else "a bank holiday"
        return (f" Note: this date falls on {what} — do not assume the deadline moves to the next working day; act before it.")
    if not (BANK_HOLIDAY_YEARS[0] <= d.year <= BANK_HOLIDAY_YEARS[1]):
        return " (Bank holidays for that year were not checked.)"
    return ""


def _unknown(j) -> bool:
    return (j or "unknown").lower() in ("", "unknown", "none", "null")


def _month_end_note(ev: date, months: int) -> str:
    return (f" Because {fmt(ev)} is near a month end, some advisers count this one day earlier — treat the earlier day as "
            "the safe deadline." if (ev + relativedelta(months=months)).day != ev.day else "")


def _et(c) -> List[Item]:
    ev = _d(c.get("event_date"))
    if not ev:
        return []
    j = (c.get("jurisdiction") or "").lower()
    ni_limit = _months_less_day(ev, 3)
    ni_text = (f"Northern Ireland industrial tribunal: act/dismissal on {fmt(ev)} → 3 months less one day ends {fmt(ni_limit)}. "
               "Early conciliation is with the Labour Relations Agency (LRA), not ACAS, and must start by then."
               + _month_end_note(ev, 3) + _closed_day_note(ni_limit, "northern_ireland"))
    if j.startswith("northern"):
        return [(ni_text, "Contact the LRA / tribunal time limit", ni_limit)]
    months = 6 if ev >= ET_NEW_LIMIT_FROM else 3
    limit = _months_less_day(ev, months)
    gb_text = (f"Employment tribunal (England, Wales, Scotland): act/dismissal on {fmt(ev)} → normal time limit "
               f"({months} months less one day) ends {fmt(limit)}. ACAS early conciliation must be started on or before this date."
               + _month_end_note(ev, months) + _closed_day_note(limit))
    if _unknown(j):
        safe = min(limit, ni_limit)
        return [(f"UK nation of the workplace not confirmed. {gb_text} {ni_text} Until confirmed, treat {fmt(safe)} as the "
                 "safe date.", "Contact ACAS/LRA (tribunal time limit — safe date)", safe)]
    if months == 3 and limit >= date(2026, 10, 1):
        gb_text += (" The limit rose to 6 months for matters from 1 October 2026; transitional rules may give this claim longer, "
                    "so treat this as the safe date — if it has passed, do not assume the claim is out of time: contact ACAS and get "
                    "advice urgently.")
    out: List[Item] = [(gb_text, "Contact ACAS (tribunal time limit)", limit)]
    a, b = _d(c.get("acas_date")), _d(c.get("certificate_date"))
    if a and a > limit:
        out.append((f"ACAS was contacted on {fmt(a)}, after the normal time limit ended — the early-conciliation extension does "
                    "not apply, so the claim may already be out of time. Get urgent advice (late claims are only allowed in "
                    "limited circumstances).", None, None))
    elif a and b and b >= a:
        final = max(limit + timedelta(days=(b - a).days), b + relativedelta(months=1))
        out.append((f"With ACAS contacted {fmt(a)} and certificate issued {fmt(b)}, the ET1 claim deadline becomes {fmt(final)}."
                    + _closed_day_note(final), "Submit ET1 tribunal claim", final))
    elif a and not b:
        out.append((f"ACAS was contacted on {fmt(a)} but no certificate date is known yet: the clock is paused during "
                    "conciliation, so the final ET1 deadline can only be calculated once the certificate is issued (it will be "
                    "at least one month after the certificate date). Do not rely on any exact ET1 date until then.", None, None))
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
             "may only be accepted if there was a good reason beyond their control." + _closed_day_note(exp), "Visa expires — apply before this date", exp)]


def _all_nations(fn, c, what: str) -> List[Item]:
    parts = [t for n in ("england", "wales", "scotland", "northern_ireland") for t, _, _ in fn({**c, "jurisdiction": n})]
    if not parts:
        return [(f"{what}: the UK nation where the property is has not been confirmed and the rules differ — no exact date "
                 "can be given until it is.", None, None)]
    return [(f"{what}: the UK nation where the property is has not been confirmed, and the rules differ. If it is in — "
             + " | ".join(parts) + " Confirm the nation before relying on any date.", None, None)]


def _tenancy_notice(c) -> List[Item]:
    served = _d(c.get("served_date"))
    if not served:
        return []
    if _unknown(c.get("jurisdiction")):
        return _all_nations(_tenancy_notice, c, "Landlord's notice")
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
    if _unknown(c.get("jurisdiction")):
        return _all_nations(_deposit, c, "Deposit protection")
    j = (c.get("jurisdiction") or "england").lower()
    if j.startswith("scot"):
        start = _d(c.get("tenancy_start_date")) or got
        due = _working_days(start, 30, "scotland")
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
    if _unknown(j):
        end = ev + relativedelta(years=5)
        return [(f"Contract/debt claims: 6 years in England, Wales & Northern Ireland, but 5 years (prescription) in Scotland — "
                 f"the UK nation is not confirmed, so from {fmt(ev)} treat {fmt(end)} as the safe date. A written "
                 "acknowledgment or part-payment of a debt can restart the clock.", "Contract / debt claim time limit (safe date)", end)]
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
    j = (c.get("jurisdiction") or "").lower()
    if j.startswith("scot") or j.startswith("northern"):
        return [("Divorce timings in Scotland and Northern Ireland follow different rules from England & Wales — the app does "
                 "not calculate them; check with the court or a family solicitor.", None, None)]
    co = app + timedelta(weeks=20)
    fo = co + timedelta(weeks=6, days=1)
    reminder = "Earliest date to apply for divorce conditional order" if j in ("england", "wales") else None
    return [(f"Divorce (England & Wales): application issued {fmt(app)} → earliest conditional order application "
             f"{fmt(co)} (20 weeks); earliest final order about {fmt(fo)} (6 weeks and 1 day after the conditional order is made, "
             "so later if the conditional order takes longer).", reminder, co if reminder else None)]


CALCS = {"employment_tribunal": _et, "citizenship_after_ilr": _citizenship, "ilr_eligibility": _ilr,
         "visa_expiry": _visa, "tenancy_notice": _tenancy_notice, "section8_notice": _tenancy_notice,
         "deposit_protection": _deposit, "limitation": _limitation, "benefit_challenge": _benefit, "divorce": _divorce}

EXTRACT_SYSTEM = """Extract dated legal events from the user's message (and recent context) so software can calculate deadlines.
Resolve relative dates ("last Friday", "next week", "3 weeks ago") using TODAY. Only include items where a date is stated or clearly implied.
jurisdiction is one of england|wales|scotland|northern_ireland|unknown — the nation where the matter is (property / workplace /
court). Use APP JURISDICTION if it is not "unknown"; otherwise use only what the user clearly states; if unclear use "unknown".
Never guess a date that is not stated or clearly implied — leave the item out instead.
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
    if not _HINT_RE.search(message or ""):
        return "", []
    if not _DATE_RE.search(message or ""):
        return NO_CALC_BLOCK, []
    today = datetime.now(UK).date()
    try:
        chat = LlmChat(api_key=api_key, session_id=f"deadline-{uuid.uuid4()}", system_message=EXTRACT_SYSTEM) \
            .with_model("anthropic", "claude-haiku-4-5-20251001").with_params(max_tokens=500)
        raw = await chat.send_message(UserMessage(
            text=f"TODAY: {today.isoformat()} ({fmt(today)})\nAPP JURISDICTION: {jurisdiction or 'unknown'}\n\n"
                 f"RECENT CONTEXT:\n{(context or '')[-1500:]}\n\nMESSAGE:\n{message[:3000]}"))
        m = re.search(r"\{.*\}", raw or "", re.S)
        calcs = json.loads(m.group(0)).get("calcs", []) if m else []
    except Exception as e:
        logger.warning(f"deadline extraction failed: {e!r}")
        return "", []
    items = compute(calcs)
    if not items:
        return NO_CALC_BLOCK, []
    block = ("\n\nEXACT DATES CALCULATED BY THE APP — use these dates exactly, do not recalculate or round them. "
             "Say they are based on the dates the user gave and that a regulated adviser should confirm. "
             "Future dates are saved to the user's Reminders automatically and they will be emailed 7, 3 and 1 day before — "
             "mention this briefly:\n- " + "\n- ".join(i[0] for i in items) +
             "\nOnly the dates above are app-calculated. Any other deadline: explain the rule and what to check, "
             "but do not state a precise calendar date.\n")
    reminders = [(t, d) for _, t, d in items if t and d and d >= today]
    return block, reminders


NO_CALC_BLOCK = (
    "\n\nDEADLINES — NO APP-CALCULATED DATE THIS TURN: the app could not calculate an exact deadline (the triggering date, "
    "the UK nation or the type of deadline is missing or not supported). Do NOT state a precise calendar deadline. "
    "Explain the rule in general terms (e.g. '3 months less one day from the dismissal'), say exactly which facts are needed "
    "(e.g. the date the notice or claim form was received, how it was served, the date on the decision letter, the UK nation), "
    "and tell the customer to check the date on their papers or with the court/tribunal/adviser. Court papers usually state "
    "the response deadline — tell them to act on that.\n")


def reminder_due_iso(d: date) -> str:
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=UK).isoformat()
