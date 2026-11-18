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
    r"deadline|how long|when can|how much time|time limit|too late|court|claim form|defence|ccj|summons|hearing|sheriff|"
    r"parking|pcn|penalty charge|refund|faulty|reject|cancel\w* (?:my|the|an|our|this) (?:order|purchase|contract|booking))\w*", re.I)
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
               "Early conciliation is with the Labour Relations Agency (LRA, 03300 552 220, lra.org.uk), not ACAS, and must start by "
               "then. The Great Britain change to 6 months (Employment Rights Act 2025) does not apply to most Northern Ireland "
               "industrial tribunal claims."
               + _month_end_note(ev, 3) + _closed_day_note(ni_limit, "northern_ireland"))
    if j.startswith("northern"):
        return [(ni_text, "Latest date to start LRA early conciliation", ni_limit),
                ("Industrial tribunal claim: the normal time limit is the same date, but starting LRA early conciliation in time "
                 "extends it — recalculate once the LRA certificate is issued.",
                 "Industrial tribunal claim — normal time limit (can be extended by LRA early conciliation)", ni_limit)]
    months = 6 if ev >= ET_NEW_LIMIT_FROM else 3
    limit = _months_less_day(ev, months)
    gb_text = (f"Employment tribunal (England, Wales, Scotland): act/dismissal on {fmt(ev)} → normal time limit "
               f"({months} months less one day) ends {fmt(limit)}. ACAS early conciliation must be started on or before this date."
               + _month_end_note(ev, months) + _closed_day_note(limit))
    if _unknown(j):
        safe = min(limit, ni_limit)
        return [(f"UK nation of the workplace not confirmed. {gb_text} {ni_text} Until confirmed, treat {fmt(safe)} as the "
                 "safe date.", "Latest date to start ACAS/LRA early conciliation (safe date)", safe)]
    if months == 3:
        gb_text += (" The 6-month limit (Employment Rights Act 2025 s.152 and Sch.12, in force 1 October 2026 under SI 2026/954) "
                    "does not apply where the act or dismissal was before 1 October 2026, so the 3-month limit applies to this "
                    "date (a few claims, such as statutory redundancy pay and equal pay, already had 6 months).")
    else:
        gb_text += (" This uses the 6-month limit that applies where the act or dismissal is on or after 1 October 2026 "
                    "(Employment Rights Act 2025 s.152 and Sch.12; SI 2026/954).")
    if j.startswith("scot"):
        bc = 6 if ev >= date(2026, 11, 9) else 3
        gb_text += (f" Exception: a breach of contract claim in Scotland has {bc} months less one day for a breach on this date "
                    "(the Scottish breach-of-contract change took effect on 9 November 2026, Acas).")
    gb_text += (" If this is one of a series of deductions from wages, or conduct extending over a period (e.g. continuing "
                "discrimination), time usually runs from the last deduction or the end of that period — which may be later and "
                "may fall under a different limit; get advice.")
    out: List[Item] = [(gb_text, "Latest date to start ACAS Early Conciliation", limit)]
    a, b = _d(c.get("acas_date")), _d(c.get("certificate_date"))
    if a and a > limit:
        out.append((f"ACAS was contacted on {fmt(a)}, after the normal time limit ended — the early-conciliation extension does "
                    "not apply, so the claim may already be out of time. Get urgent advice (late claims are only allowed in "
                    "limited circumstances).", None, None))
    elif a and b and b >= a:
        final = max(limit + timedelta(days=(b - a).days), b + relativedelta(months=1))
        out.append((f"With ACAS contacted {fmt(a)} and certificate issued {fmt(b)}, the ET1 claim deadline becomes {fmt(final)}."
                    + _closed_day_note(final), "Submit ET1 tribunal claim (after ACAS certificate)", final))
    elif a and not b:
        out.append((f"ACAS was contacted on {fmt(a)} but no certificate date is known yet: the clock is paused during "
                    "conciliation, so the final ET1 deadline can only be calculated once the certificate is issued (it will be "
                    "at least one month after the certificate date). Do not rely on any exact ET1 date until then.", None, None))
    else:
        out.append((f"Tribunal claim (ET1): {fmt(limit)} is the normal time limit before any extension. ACAS Early Conciliation is "
                    "normally required first; starting it on or before that date pauses the clock, and the ET1 deadline is then "
                    "recalculated from the ACAS certificate (at least one month after the certificate date). Keep the ACAS date "
                    "and the ET1 date separate. The customer has not given an ACAS notification date: any Early Conciliation "
                    "adjustment cannot be calculated until the ACAS notification and certificate dates are known — ask whether "
                    "ACAS has been contacted and, if so, on what date.", "ET1 tribunal claim — normal time limit (can be extended by ACAS Early Conciliation)",
                    limit))
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


def _cpr_due(d: date) -> date:
    """CPR 2.8(5): if the period ends on a day the court office is closed, filing on the next open day is in time."""
    hols = bank_holidays("england")
    while d.weekday() >= 5 or d in hols:
        d += timedelta(days=1)
    return d


def _court_claim(c) -> List[Item]:
    """England & Wales Part 7 claim: deemed service CPR 6.14 (claim form: 2nd business day after posting/leaving/sending)
    and 6.26 (particulars served separately by first-class post: 2nd day after posting, or next business day).
    Acknowledgment of service or defence within 14 days after service of the particulars (CPR 9.2, 10.3(1));
    defence within 28 days after service of the particulars if an acknowledgment is filed (CPR 15.4(1)); parties may agree
    up to 28 more days (CPR 15.5). Exact dates only when the service facts are known."""
    j = (c.get("jurisdiction") or "").lower()
    if j.startswith("scot"):
        return [("Scotland (simple procedure / sheriff court): the court sets the response deadline in the timetable sent with "
                 "the claim — the app does not calculate it. Act on the 'last date for response' on the papers, today if possible.",
                 None, None)]
    if j.startswith("northern"):
        return [("Northern Ireland: county court and small claims response times follow NI court rules and the papers — the app "
                 "does not calculate them. Check the date on the civil bill or claim notice and get advice promptly.", None, None)]
    if _unknown(j):
        return [("Court claim: the UK nation is not confirmed and court rules differ (England & Wales, Scotland and Northern "
                 "Ireland each have their own) — no exact response date can be given until it is.", None, None)]
    rule = ("Rule (CPR 9–15): file an acknowledgment of service or a defence within 14 days after service of the particulars "
            "of claim; if you acknowledge service in time, the defence is due 28 days after service of the particulars (the "
            "claimant can agree up to 28 days more, CPR 15.5). If nothing is filed, the claimant can ask for judgment in default.")
    if str(c.get("outside_uk")).lower() == "true" or str(c.get("claim_part")) == "8" or \
            str(c.get("particulars_to_follow")).lower() == "true":
        why = ("the claim was served outside the UK" if str(c.get("outside_uk")).lower() == "true" else
               "it is a Part 8 claim (different response rules)" if str(c.get("claim_part")) == "8" else
               "the particulars of claim are to follow — time runs from when they are served")
        return [(f"England & Wales court claim: the app cannot confirm a date because {why}. {rule}", None, None)]
    served = _d(c.get("service_date"))
    posted = _d(c.get("posted_date"))
    sep = str(c.get("particulars_separate")).lower() == "true"
    if not served and posted and not sep:
        served = _working_days(posted, 2)  # CPR 6.14: second business day after the step
    elif not served and posted and sep:
        served = _cpr_due(posted + timedelta(days=2))  # CPR 6.26 first-class post
    if served:
        aos, dfc = _cpr_due(served + timedelta(days=14)), _cpr_due(served + timedelta(days=28))
        basis = "date of service stated on the court papers" if c.get("service_date") else f"posted/sent {fmt(posted)}"
        out = [(f"England & Wales court claim — deemed served {fmt(served)} ({basis}). Acknowledgment of service (or defence/"
                f"admission) by {fmt(aos)}. If you acknowledge service in time, defence by {fmt(dfc)}. Dates move to the next "
                "court working day only when the last day is a weekend or bank holiday (CPR 2.8). Check the response pack.",
                "Court claim: acknowledge or defend by", aos)]
        if str(c.get("aos_filed")).lower() == "true":
            out.append((f"Acknowledgment filed: defence due {fmt(dfc)}.", "Court claim: defence due", dfc))
        return out
    issued, got = _d(c.get("issue_date")), _d(c.get("received_date"))
    seen = f"issued {fmt(issued)}" if issued else f"received {fmt(got)}" if got else "received"
    return [(f"England & Wales court claim {seen}: the response deadline runs from the date of SERVICE, which the rules "
             "deem from the date the claim was posted or sent (not the issue date, and not necessarily the day it arrived). "
             "The app cannot confirm an exact date until you give the date of service shown on the court's notice of issue, "
             f"or the date it was posted and how. {rule} Treat this as urgent and respond as early as you can.", None, None)]


def _parking(c) -> List[Item]:
    """Council PCNs (England & Wales TMA 2004 regs; Scotland): reduced rate within 14 days of service (21 days for postal/camera
    PCNs in England & Wales); formal representations within 28 days of a Notice to Owner. Private 'parking charges' are contractual."""
    nd = _d(c.get("notice_date"))
    if not nd:
        return []
    issuer, served = (c.get("issuer") or "unknown").lower(), (c.get("served") or "unknown").lower()
    j = (c.get("jurisdiction") or "").lower()
    if issuer != "council":
        return [(f"Parking notice dated {fmt(nd)}: {'a private parking charge' if issuer == 'private' else 'it is not clear whether this is a council PCN or a private parking charge'}"
                 " — private operators set their own appeal and discount periods (often 14 days for the discount and 28 days to "
                 "appeal), and Scotland has no keeper-liability law for private parking. The app cannot confirm an exact date: "
                 "check the dates printed on the notice.", None, None)]
    if _unknown(j) or j.startswith("northern"):
        return [(f"Council penalty charge notice dated {fmt(nd)}: the discount and challenge periods depend on the UK nation and "
                 "how it was served — confirm these; the dates on the notice apply.", None, None)]
    if served == "windscreen":
        last = nd + timedelta(days=13)
        return [(f"Council PCN fixed to the vehicle on {fmt(nd)}: the reduced (50%) rate is available for 14 days beginning with "
                 f"that date — SAFE WORKING DATE {fmt(last)}. An informal challenge made in that period usually keeps the "
                 "discount open; formal representations are made within 28 days of any Notice to Owner.",
                 "Parking PCN discount ends (safe date)", last)]
    if served == "post" and not j.startswith("scot"):
        last = nd + timedelta(days=20)
        return [(f"Council PCN sent by post, dated {fmt(nd)}: the reduced rate is available for 21 days beginning with the date of "
                 f"service, which is after the date on the notice — SAFE WORKING DATE {fmt(last)}. Representations: within 28 days "
                 "of service.", "Parking PCN discount ends (safe date)", last)]
    win, post = nd + timedelta(days=13), nd + timedelta(days=20)
    return [(f"Council PCN dated {fmt(nd)}, service method not given: if it was fixed to the vehicle or handed over, the "
             f"reduced (50%) rate ran for 14 days beginning with that date — SAFE WORKING DATE {fmt(win)}; if it was sent by post "
             "(camera/CCTV), the 21 days run from the date of service, which is later than the date on the notice"
             + ("" if j.startswith("scot") else f" — at least until {fmt(post)}") + ". Check how it arrived. Formal "
             "representations are made within 28 days of a Notice to Owner (or of service of a postal PCN)."
             + (f" ALREADY PASSED on the 'fixed to the vehicle' timing (today is {fmt(datetime.now(UK).date())}) — say so plainly; "
                "the discount may also have ended if it was posted." if datetime.now(UK).date() > win else ""), None, None)]


def _consumer(c) -> List[Item]:
    """Consumer Rights Act 2015 s.22 (30-day short-term right to reject) and Consumer Contracts Regulations 2013 reg 30-31
    (14-day cancellation for online/distance contracts) — UK-wide."""
    kind = (c.get("kind") or "").lower()
    got, made = _d(c.get("delivery_date")), _d(c.get("contract_date"))
    if kind == "faulty_goods" and got:
        end = got + timedelta(days=30)
        return [(f"Faulty goods delivered {fmt(got)}: short-term right to reject for a full refund within 30 days → by {fmt(end)} "
                 "(shorter for perishable goods). After that you can still ask for a repair or replacement.",
                 "Last day to reject faulty goods", end)]
    if kind == "online_cancel" and got:
        end = got + timedelta(days=14)
        return [(f"Online/distance purchase delivered {fmt(got)}: 14-day cancellation period starting the day after delivery → "
                 f"tell the seller by {fmt(end)}. Some items are excluded (e.g. personalised or sealed hygiene goods once opened); "
                 "if the seller did not give cancellation information, the period can be extended.", "Last day to cancel online order", end)]
    if kind == "service_cancel" and made:
        end = made + timedelta(days=14)
        return [(f"Service agreed online/at a distance on {fmt(made)}: 14-day cancellation period starting the day after → by "
                 f"{fmt(end)}. If you asked for the service to start sooner you may have to pay for what was provided.",
                 "Last day to cancel service", end)]
    return [("Consumer deadline: the app needs the type of problem (faulty goods, cancelling an online order or a service) and "
             "the delivery or contract date to calculate it.", None, None)]


CALCS = {"employment_tribunal": _et, "citizenship_after_ilr": _citizenship, "ilr_eligibility": _ilr,
         "visa_expiry": _visa, "tenancy_notice": _tenancy_notice, "section8_notice": _tenancy_notice,
         "deposit_protection": _deposit, "limitation": _limitation, "benefit_challenge": _benefit, "divorce": _divorce,
         "court_claim": _court_claim, "parking_notice": _parking, "consumer_purchase": _consumer}

EXTRACT_SYSTEM = """Extract dated legal events from the user's message (and recent context) so software can calculate deadlines.
Resolve relative dates ("last Friday", "next week", "3 weeks ago") using TODAY. Only include items where a date is stated or clearly implied.
jurisdiction is one of england|wales|scotland|northern_ireland|unknown — the nation where the matter is (property / workplace /
court). Use APP JURISDICTION if it is not "unknown"; otherwise use only what the user clearly states; if unclear use "unknown".
Never guess a date that is not stated or clearly implied — leave the item out instead.
Add "approx": true to an item when its trigger date was worked out from a relative or vague phrase ("3 weeks ago", "last month",
"in August") rather than stated as a calendar date; otherwise "approx": false.
Each date field must come from the customer's words about THAT event: acas_date only if they say they contacted/notified
ACAS (or the LRA) and when; certificate_date only if they mention the certificate and its date; mrn_date only for a mandatory
reconsideration notice. Never copy the dismissal/decision/notice date into another field — use null.
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
{"type":"divorce","application_date":"YYYY-MM-DD"}
{"type":"court_claim","issue_date":"YYYY-MM-DD|null","received_date":"YYYY-MM-DD|null","service_date":"YYYY-MM-DD|null","posted_date":"YYYY-MM-DD|null","particulars_separate":true|false|null,"particulars_to_follow":true|false|null,"aos_filed":true|false|null,"claim_part":"7|8|null","outside_uk":true|false|null,"jurisdiction":"..."}
(service_date only if the customer quotes a date of service / "deemed served" date from the court papers; posted_date = date the claim was posted or sent; received_date = when it arrived)
{"type":"parking_notice","notice_date":"YYYY-MM-DD","issuer":"council|private|unknown","served":"windscreen|post|unknown","jurisdiction":"..."}
{"type":"consumer_purchase","kind":"faulty_goods|online_cancel|service_cancel","delivery_date":"YYYY-MM-DD|null","contract_date":"YYYY-MM-DD|null"}"""


REVIEW_KINDS = {"court_claim": "court procedural deadline", "employment_tribunal": "tribunal limitation date"}
_REL = re.compile(r"\b(?:(a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,3})\s+(day|week|month|year)s?"
                  r"\s+ago|yesterday|last (week|month))\b", re.I)
_NUM = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12}


def relative_dates(text: str, today: date) -> List[str]:
    """Deterministic reading of 'N weeks ago' style phrases (approximate — the customer should confirm the exact date)."""
    out = []
    for m in _REL.finditer(text or ""):
        w = m.group(0).lower()
        if w == "yesterday":
            out.append(f"'yesterday' = {fmt(today - timedelta(days=1))}")
            continue
        if m.group(3):
            span = {"week": (timedelta(days=13), timedelta(days=7)), "month": None}[m.group(3)]
            if span:
                out.append(f"'{w}' ≈ between {fmt(today - span[0])} and {fmt(today - span[1])}")
            else:
                last = today.replace(day=1) - timedelta(days=1)
                out.append(f"'{w}' ≈ between {fmt(last.replace(day=1))} and {fmt(last)}")
            continue
        n, unit = _NUM.get(m.group(1).lower()) or int(m.group(1)), m.group(2).lower()
        exact = today - {"day": relativedelta(days=n), "week": relativedelta(weeks=n), "month": relativedelta(months=n),
                         "year": relativedelta(years=n)}[unit]
        slack = {"day": 0, "week": 3, "month": 7, "year": 30}[unit]
        out.append(f"'{w}' ≈ {fmt(exact)}" + (f" (could be a few days either side, {fmt(exact - timedelta(days=slack))} to "
                                             f"{fmt(exact + timedelta(days=slack))})" if slack else ""))
    return list(dict.fromkeys(out))[:4]


def annotate(kind: str, items: List[Item], today: date, approx: bool) -> List[Item]:
    out = []
    for text, title, d in items:
        if d and d < today:
            text += (f" ALREADY PASSED: this date was {(today - d).days} day(s) ago (today is {fmt(today)}). Say so plainly — "
                     "do not present it as a future deadline — and explain what may still be possible"
                     + (" (a tribunal can sometimes accept a late claim — 'not reasonably practicable' for unfair dismissal, "
                        "'just and equitable' for discrimination — never say the claim is definitely out of time; contact "
                        "ACAS/LRA and get advice urgently)" if kind == "employment_tribunal" else
                        " (the full charge now applies unless the council re-offers the discount; challenge rights may remain)"
                        if kind == "parking_notice" else "") + ".")
        elif d and (d - today).days <= 7:
            text += f" URGENT: only {(d - today).days} day(s) left (today is {fmt(today)}) — say this prominently."
        if approx and d:
            text += " This is based on an APPROXIMATE date worked out from the customer's wording — ask for the exact date."
        if kind in REVIEW_KINDS and d:
            text += (f" INDEPENDENT CHECK: this is a high-risk {REVIEW_KINDS[kind]} worked out by the app — tell the customer to "
                     "have it confirmed by the court/tribunal, Acas/LRA, or a solicitor or adviser before relying on it.")
        out.append((text, title, d))
    return out


def compute_annotated(calcs: list, today: date) -> List[Item]:
    items: List[Item] = []
    for c in calcs[:6]:
        fn = CALCS.get((c or {}).get("type"))
        if fn:
            try:
                items += annotate(c["type"], fn(c), today, str(c.get("approx")).lower() == "true")
            except Exception as e:
                logger.warning(f"deadline calc failed for {c}: {e!r}")
    return items


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
    import date_guard
    calcs, guard_notes = date_guard.validate(calcs, f"{context or ''}\n{message}")
    facts = ("\nDATE SAFEGUARD (the app checked which dates the customer actually gave):\n- " + "\n- ".join(guard_notes) +
             "\n") if guard_notes else ""
    facts += ("Each date belongs only to the event it is stated for. Never say the customer contacted ACAS, received a "
              "certificate, appealed, asked for reconsideration or submitted a claim — or give a date for it — unless they "
              "said so. If an important date is missing or unclear, ask for it.\n")
    rel = relative_dates(message, today)
    if rel:
        facts += ("RELATIVE DATES (approximate, worked out by the app from today's date): " + "; ".join(rel) +
                  ". Use these only as approximate dates and ask the customer for the exact date before relying on a deadline.\n")
    items = compute_annotated(calcs, today)
    if not items:
        return NO_CALC_BLOCK + facts, []
    block = ("\n\nEXACT DATES CALCULATED BY THE APP — use these dates exactly, do not recalculate or round them. "
             "Say they are based on the dates the user gave and that a regulated adviser should confirm. "
             "Nothing has been saved: the app will OFFER to add future dates to Reminders only after the customer confirms "
             "this is their real situation — do NOT say any reminder was saved or that emails will be sent. Keep the ACAS/LRA "
             "early-conciliation date separate from the tribunal claim deadline; for a dismissal, ask the customer to confirm "
             "the effective date of termination. Never reassure about time (e.g. 'you have plenty of time', 'no rush') — state "
             "the date and urge prompt action. Great Britain employment time limits end at 11:59pm UK time on the last day (Acas); "
             "never give 9am or any other time as a legal cut-off, and for other deadlines do not state a cut-off time:\n- " + "\n- ".join(i[0] for i in items) +
             "\nOnly the dates above are app-calculated. Any other deadline: explain the rule and what to check, "
             "but do not state a precise calendar date.\n" + facts)
    return block, [{"title": t, "due": d, "note": reminder_note(t)} for _, t, d in items if t and d and d >= today]


ET_NOTE = ("Based on the dismissal date you gave — confirm your effective date of termination (on your dismissal letter or "
           "payslip). Starting ACAS Early Conciliation (LRA in Northern Ireland) in time extends the tribunal claim deadline; "
           "recalculate once you have the certificate. Check with a regulated adviser.")


def reminder_note(title: str) -> str:
    if re.search(r"ACAS|LRA|ET1|tribunal", title or ""):
        return ET_NOTE
    return "Worked out by Lex from the dates you gave. Check with a regulated adviser."


NO_CALC_BLOCK = (
    "\n\nDEADLINES — NO APP-CALCULATED DATE THIS TURN: the app could not calculate an exact deadline (the triggering date, "
    "the UK nation or the type of deadline is missing or not supported). Do NOT state a precise calendar deadline. "
    "Explain the rule in general terms (e.g. '3 months less one day from the dismissal'), say exactly which facts are needed "
    "(e.g. the date the notice or claim form was received, how it was served, the date on the decision letter, the UK nation), "
    "and tell the customer to check the date on their papers or with the court/tribunal/adviser. Court papers usually state "
    "the response deadline — tell them to act on that.\n")


def reminder_due_iso(d: date) -> str:
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=UK).isoformat()


def deadline_iso(d: date) -> str:
    """Legal deadline = end of the last day, UK local time (GMT or BST as applicable)."""
    return datetime(d.year, d.month, d.day, 23, 59, tzinfo=UK).isoformat()


ACAS_TL_URL = "https://www.acas.org.uk/employment-tribunal-time-limits"


def deadline_label(d: date, title: str) -> dict:
    """What the customer is shown about the cut-off time. Only GB employment limits have an authoritative 11:59pm
    (Acas: the time limit 'ends at 11:59pm' on the last day); everything else is labelled as needing confirmation."""
    day = datetime(d.year, d.month, d.day, 23, 59, tzinfo=UK)
    when = f"{fmt(d)}"
    gb_et = bool(re.search(r"ACAS|ET1", title or "")) and not re.search(r"LRA|Industrial", title or "")
    if gb_et and "ACAS" in title and "ET1" not in title:
        basis = ("Legal deadline: the time limit ends at 11:59pm UK time on this day (Acas guidance). Notifying Acas online "
                 "can be done at any time; the Acas phone line is only open during its opening hours, so do not leave it "
                 "to the last day.")
    elif gb_et:
        basis = ("Legal deadline: the time limit ends at 11:59pm UK time on this day (Acas guidance), unless Early "
                 "Conciliation has extended it. Submit the ET1 online well before then.")
    else:
        basis = ("Legal deadline date only — the exact cut-off time has not been confirmed. Check the time on your papers or "
                 "with the court, tribunal or office, and act well before the day.")
    return {"deadline_label": f"{when}, 11:59pm UK time ({day.tzname()})" if gb_et else f"{when} — cut-off time to be confirmed",
            "deadline_time_confirmed": gb_et, "deadline_basis": basis,
            "deadline_source": ACAS_TL_URL if gb_et else "",
            "reminder_schedule": "Reminder emails at 8am UK time, 7, 3 and 1 days before"}
