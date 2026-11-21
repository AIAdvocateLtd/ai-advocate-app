"""Source-driven deadline estimates for selected employment-law time limits (DE, ES, IT, PL). Python does the date maths
only when (1) the governing provision was retrieved from the official source in this research and its text contains
the expected period, and (2) the customer gave an explicit trigger date. Output is always an ESTIMATE that needs
confirmation — trigger-date evidence, regional holidays and exceptions are not verified by the app."""
import os
import re
from datetime import date, timedelta
from typing import List, Optional

import holidays

RULES = {
    "PL": {
        "name": "appeal against dismissal to the labour court (odwołanie od wypowiedzenia)", "ref": ("PL", "DU/1974/141", "264"),
        "must": r"21 dni", "days": 21, "unit": "calendar",
        "trigger": "the day the written notice of termination was delivered to you (doręczenie)",
        "rules": "the delivery day is not counted (art. 111 § 2 Kodeks cywilny); if the last day is a Saturday or public "
                 "holiday the deadline moves to the next working day (art. 115 Kodeks cywilny, applied via art. 300 Kodeks pracy)",
        "exceptions": ["if the employer did not tell you about the right to appeal, or for other reasons outside your control, "
                       "the court can restore a missed deadline on application (art. 265 Kodeks pracy)",
                       "the same 21 days run from delivery of a summary dismissal (rozwiązanie bez wypowiedzenia), art. 264 § 2"]},
    "DE": {
        "name": "claim against dismissal to the labour court (Kündigungsschutzklage)", "ref": ("DE", "kschg", "4"),
        "must": r"drei Wochen", "days": 21, "unit": "calendar",
        "trigger": "the day the written notice of dismissal reached you (Zugang)",
        "rules": "the day of receipt is not counted (§ 187(1) BGB); the period ends on the same weekday three weeks later "
                 "(§ 188(2) BGB); if that day is a Saturday, Sunday or public holiday it moves to the next working day "
                 "(§ 193 BGB) — only nationwide public holidays are applied here, state holidays are NOT",
        "exceptions": ["a late claim can be admitted if you were prevented despite all reasonable care (§ 5 KSchG)",
                       "where a public authority's consent is needed, time runs from notice of that decision (§ 4 sentence 4 KSchG)"]},
    "ES": {
        "name": "claim against dismissal (demanda por despido)", "ref": ("ES", "BOE-A-2015-11430", "59"),
        "must": r"veinte días", "days": 20, "unit": "working",
        "trigger": "the day after the dismissal took effect",
        "rules": "20 working days (días hábiles): Saturdays, Sundays and national public holidays are excluded here — "
                 "regional and local holidays are NOT applied, and how August and 24/31 December are treated must be "
                 "checked with a lawyer",
        "exceptions": ["filing the compulsory conciliation request (papeleta de conciliación) suspends the period (art. 65 LRJS) "
                       "— this is not reflected in the estimate",
                       "this is a strict caducidad period: it cannot normally be extended"]},
    "IT": {
        "name": "out-of-court challenge to dismissal (impugnazione del licenziamento)", "ref": ("IT", "legge:1966-07-15;604", "6"),
        "must": r"sessanta giorni", "days": 60, "unit": "calendar",
        "trigger": "the day you received the written dismissal (or the written reasons, if given later)",
        "rules": "60 calendar days, receipt day not counted; whether a deadline falling on a Sunday or public holiday moves "
                 "to the next working day must be confirmed with a lawyer",
        "exceptions": ["after the challenge, court proceedings (or a conciliation/arbitration request) must follow within "
                       "180 days, otherwise the challenge lapses (art. 6(2) Legge 604/1966)"]},
}
MONTHS = {m: i for i, names in enumerate([
    "january|januar|enero|gennaio|stycznia|styczeń|janeiro", "february|februar|febrero|febbraio|lutego|luty|fevereiro",
    "march|märz|marzo|marca|marzec|março", "april|abril|aprile|kwietnia|kwiecień", "may|mai|mayo|maggio|maja|maj|maio",
    "june|juni|junio|giugno|czerwca|czerwiec|junho", "july|juli|julio|luglio|lipca|lipiec|julho",
    "august|agosto|sierpnia|sierpień", "september|septiembre|settembre|września|wrzesień|setembro",
    "october|oktober|octubre|ottobre|października|październik|outubro",
    "november|noviembre|novembre|listopada|listopad|novembro", "december|dezember|diciembre|dicembre|grudnia|grudzień|dezembro"],
    start=1) for m in names.split("|")}
_NUM = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b")
_TXT = re.compile(r"\b(\d{1,2})\.?\s*(?:de\s+)?(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\s+(?:de\s+)?(\d{4})\b", re.I)


def calc_enabled() -> bool:
    """Off unless LEX_NATIONAL_DEADLINE_CALC=on (to be set only after qualified review of RULES)."""
    return os.environ.get("LEX_NATIONAL_DEADLINE_CALC") == "on"


def explicit_dates(text: str) -> List[date]:
    out = []
    for m in _NUM.finditer(text or ""):
        try:
            out.append(date(int(m[4]), int(m[5]), int(m[6])) if m[4] else date(int(m[3]), int(m[2]), int(m[1])))
        except ValueError:
            pass
    for m in _TXT.finditer(text or ""):
        try:
            out.append(date(int(m[3]), MONTHS[m[2].lower()], int(m[1])))
        except ValueError:
            pass
    return out


def _spans(text: str):
    for rx, conv in ((_NUM, lambda m: date(int(m[4]), int(m[5]), int(m[6])) if m[4] else date(int(m[3]), int(m[2]), int(m[1]))),
                     (_TXT, lambda m: date(int(m[3]), MONTHS[m[2].lower()], int(m[1])))):
        for m in rx.finditer(text or ""):
            try:
                yield m.group(0), conv(m)
            except (ValueError, KeyError):
                pass


def guard(answer: str, message: str, sources: str = "") -> tuple:
    """While calculation is switched off: remove any calendar date the customer did not give and the retrieved official
    sources do not contain (so commencement, enactment and judgment dates from those sources survive)."""
    given = {d for _, d in _spans(f"{message}\n{sources}")}
    out, n = answer or "", 0
    for s, d in sorted(set(_spans(out)), key=lambda x: -len(x[0])):
        if d not in given and s in out:
            out, k = out.replace(s, "[⚠ date removed — not verified]"), out.count(s)
            n += k
    if n:
        import lex_safety
        out = lex_safety.insert_before_tail(out, "**Deadline date:** Lex does not yet calculate exact deadline dates for this "
                                                 "country — the last day depends on when the notice was received and on rules "
                                                 "that have not been professionally verified. Confirm it immediately with a "
                                                 "local lawyer, union or the court.")
    return out, n


def _free(d: date, hol) -> bool:
    return d.weekday() < 5 and d not in hol


def compute(j: str, trigger: date) -> dict:
    r = RULES[j]
    hol = holidays.country_holidays(j, years=range(trigger.year, trigger.year + 2))
    shifted = None
    if r["unit"] == "working":
        d, n = trigger, 0
        while n < r["days"]:
            d += timedelta(days=1)
            if _free(d, hol):
                n += 1
    else:
        d = trigger + timedelta(days=r["days"])
        if j in ("PL", "DE"):  # end moves off Saturdays, Sundays and public holidays (§ 193 BGB / art. 115 KC)
            e = d
            while not _free(e, hol):
                e += timedelta(days=1)
            if e != d:
                shifted, d = d, e
    return {"end": d, "shifted_from": shifted}


def block(j: str, retrieved: List[dict], message: str, today: Optional[date] = None) -> str:
    """Prompt note for this jurisdiction's dismissal time limit, or '' when the rule does not apply."""
    r = RULES.get(j)
    if not r:
        return ""
    src = next((x for x in retrieved if (x.get("j"), x.get("law"), x.get("art")) == r["ref"] and not x.get("failed")), None)
    if not src or not re.search(r["must"], src.get("text", ""), re.I):
        return (f"DEADLINE ({r['name']}): the official provision setting this time limit was not retrieved and checked "
                "for this answer — do not state the period or any date as verified; tell the customer the limit is short "
                "and to get advice immediately.")
    quote = re.search(r["must"], src["text"], re.I).group(0)
    if not calc_enabled():  # owner gate: no app-computed dates until the counting rules are professionally reviewed
        return (f"DEADLINE ({r['name']}): the retrieved official text ({src['label']}) states the period “{quote}” — quote "
                "and cite that wording. Lex's date calculation for this country is SWITCHED OFF pending qualified legal "
                "review: do NOT work out, estimate or state any calendar end date (even if the customer gives dates), and "
                "do not explain detailed counting, weekend/holiday or exception rules as checked. Say the time limit is "
                "short, that the exact last day depends on when the notice was received and on rules Lex has not "
                "verified, and that they must confirm it immediately with a local lawyer, union or the court.")
    head = (f"SOURCE-DRIVEN DEADLINE ({r['name']}): the retrieved official text ({src['label']}) states the period "
            f"(“{re.search(r['must'], src['text'], re.I).group(0)}”). Clock starts: {r['trigger']}. Counting rules: {r['rules']}. "
            f"Exceptions not reflected: {'; '.join(r['exceptions'])}.")
    dates = [d for d in explicit_dates(message) if not today or d <= today]
    if len(dates) != 1:
        return head + (" The customer did not give one clear trigger date, so do NOT give a calendar date — explain how "
                       "the period is counted and ask for the exact date they received the notice.")
    c = compute(j, dates[0])
    end = c["end"].strftime("%d/%m/%Y")
    shift = f" (moved from {c['shifted_from'].strftime('%d/%m/%Y')} because that day is not a working day)" if c["shifted_from"] else ""
    return head + (f" APP ESTIMATE, NOT A VERIFIED DATE: if the trigger date really was {dates[0].strftime('%d/%m/%Y')}, "
                   f"the period would end on {end}{shift}. Present it only as an estimate that depends on when the notice "
                   "was actually received/effective and on holidays/exceptions the app has not checked; urge the customer "
                   "to act well before it and to confirm it with a local lawyer or the court. This calculation is not "
                   "professionally reviewed.")
