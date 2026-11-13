"""Deterministic check that every date the extractor assigned to a legal event is backed by the customer's own words.
No AI calls. A date is kept only if a sentence the customer wrote links that event to a date."""
import re
from datetime import date
from typing import List, Optional, Tuple

_MONTHS = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_EXPLICIT = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+of)?\s+{_MON}\.?(?:,?\s+(\d{{4}}))?\b"
    rf"|\b{_MON}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b"
    r"|\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", re.I)
_RELATIVE = re.compile(r"\b(today|yesterday|tomorrow|last|next|ago|this (?:week|month|morning)|same day|that day|"
                       r"day after|following day|days? later|weeks? later|earlier this)\b", re.I)
_SENT = re.compile(r"(?<=[.!?;])\s+|\n")

# Per calculation type: field -> words that tie a date to that event.
EVENTS = {
    "employment_tribunal": {
        "event_date": r"dismiss\w*|sacked|fired|let go|terminat\w*|last day|notice (?:period )?end\w*|discriminat\w*|"
                      r"harass\w*|underpaid|not paid|wages|redundan\w*|happened|incident|resign\w*",
        "acas_date": r"\bacas\b|early conciliation|\bconciliat\w*|\blra\b|labour relations agency",
        "certificate_date": r"certificate"},
    "citizenship_after_ilr": {"ilr_date": r"\bilr\b|indefinite leave|settle\w*"},
    "ilr_eligibility": {"route_start_date": r"visa|arriv\w*|came to|moved to|started|granted|route|since|entered"},
    "visa_expiry": {"expiry_date": r"expir\w*|runs? out|valid until|ends?\b|until"},
    "tenancy_notice": {"served_date": r"notice|served|section \d+|received|gave me|given|letter",
                       "tenancy_start_date": r"tenancy (?:start|began)|moved in|started renting|lease (?:start|began)|"
                                             r"start(?:ed)? (?:of )?(?:the )?tenancy|renting since|tenant since"},
    "deposit_protection": {"paid_date": r"deposit|paid",
                           "tenancy_start_date": r"tenancy (?:start|began)|moved in|start(?:ed)? (?:of )?(?:the )?tenancy"},
    "limitation": {"event_date": r"accident|injur\w*|breach\w*|owe\w*|debt|lent|loan|paid|contract|happened|incident|"
                                 r"due|invoice|work|bought|purchas\w*|deliver\w*"},
    "benefit_challenge": {"decision_date": r"decision|decided|letter|refus\w*|award\w*|stopped|sanction\w*|turned down",
                          "mrn_date": r"mandatory reconsideration|reconsideration notice|\bmrn\b"},
    "divorce": {"application_date": r"appl\w*|filed|issued|submitted|started"},
}
PRIMARY = {"employment_tribunal": "event_date", "citizenship_after_ilr": "ilr_date", "ilr_eligibility": "route_start_date",
           "visa_expiry": "expiry_date", "tenancy_notice": "served_date", "deposit_protection": "paid_date",
           "limitation": "event_date", "benefit_challenge": "decision_date", "divorce": "application_date"}
LABEL = {"event_date": "the date of the event (e.g. dismissal)", "acas_date": "the ACAS/LRA early conciliation notification date",
         "certificate_date": "the early conciliation certificate date", "ilr_date": "the ILR grant date",
         "route_start_date": "the visa route start date", "expiry_date": "the visa expiry date",
         "served_date": "the date the notice was served", "tenancy_start_date": "the tenancy start date",
         "paid_date": "the deposit payment date", "decision_date": "the decision letter date",
         "mrn_date": "the mandatory reconsideration notice date", "application_date": "the application date"}


def _d(v) -> Optional[date]:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _parse(m: re.Match) -> Tuple[Optional[int], int, int]:
    g = m.groups()
    if g[0]:
        return (int(g[2]) if g[2] else None), _MONTHS[g[1][:3].lower()], int(g[0])
    if g[3]:
        return (int(g[5]) if g[5] else None), _MONTHS[g[3][:3].lower()], int(g[4])
    if g[6]:
        return int(g[6]), int(g[7]), int(g[8])
    y = int(g[11])
    return (y + 2000 if y < 100 else y), int(g[10]), int(g[9])


def _same(v: date, ymd) -> bool:
    y, mo, d = ymd
    return v.month == mo and v.day == d and (y is None or y == v.year)


def evidence(calc_type: str, customer_text: str) -> dict:
    """field -> {'explicit': [(y,m,d)...], 'relative': bool} from sentences the customer wrote."""
    fields = EVENTS.get(calc_type, {})
    rx = {f: re.compile(p, re.I) for f, p in fields.items()}
    out = {f: {"explicit": [], "relative": False} for f in fields}
    for sent in _SENT.split(customer_text or ""):
        kws = [(f, m.start(), m.end()) for f, r in rx.items() for m in r.finditer(sent)]
        if not kws:
            continue
        for m in _EXPLICIT.finditer(sent):
            f = min(kws, key=lambda k: min(abs(m.start() - k[2]), abs(k[1] - m.end())))[0]
            out[f]["explicit"].append(_parse(m))
        for m in _RELATIVE.finditer(sent):
            f = min(kws, key=lambda k: min(abs(m.start() - k[2]), abs(k[1] - m.end())))[0]
            out[f]["relative"] = True
    return out


def validate(calcs: list, customer_text: str) -> Tuple[list, List[str]]:
    """Drops dates the customer did not link to that event, and calculations whose trigger date is missing or
    conflicting. Returns (safe calcs, notes for Lex)."""
    safe, notes = [], []
    for c in calcs or []:
        c = dict(c or {})
        t = c.get("type")
        if t not in EVENTS:
            continue
        ev = evidence(t, customer_text)
        ok = True
        for field in EVENTS[t]:
            v = _d(c.get(field))
            if not v:
                continue
            e = ev[field]
            distinct = {(y, mo, d) for y, mo, d in e["explicit"]}
            days = {(mo, d) for _, mo, d in distinct}
            if len(days) > 1 and any(_same(v, x) for x in distinct):
                notes.append(f"The customer gave more than one date that could be {LABEL[field]} — the app did not "
                             "calculate from it. Ask which date is correct.")
                c[field] = None
            elif any(_same(v, x) for x in distinct) or (not distinct and e["relative"]):
                continue
            else:
                notes.append(f"The customer did not state {LABEL[field]}. Do NOT assume or state one, and do not reuse "
                             "another event's date for it" + ("; ask whether ACAS has been contacted and, if so, on what date"
                                                             if field == "acas_date" else "; ask for it if it matters") + ".")
                c[field] = None
            if field == PRIMARY[t] and not c.get(field):
                ok = False
        if c.get("certificate_date") and not c.get("acas_date"):
            c["certificate_date"] = None
            notes.append("A certificate date was given without an ACAS notification date — ask for the ACAS notification "
                         "date before calculating any Early Conciliation extension.")
        if ok:
            safe.append(c)
    return safe, list(dict.fromkeys(notes))


# --- answer guard: Lex must not tell the customer they did something they never said
_CLAIMS = [
    (re.compile(r"\byou(?:['’]ve| have)?\s+(?:already\s+)?(?:contacted|notified|called|rang|got in touch with|started early "
                r"conciliation with|started (?:acas )?early conciliation)\b[^.!?\n]{0,30}?(?:\bacas\b|\blra\b|conciliation)", re.I),
     re.compile(r"\bacas\b|conciliat|\blra\b|labour relations", re.I),
     "You have not said whether you have contacted ACAS yet — please tell me if you have, and on what date, because "
     "Early Conciliation can change the tribunal deadline and that adjustment cannot be worked out until the dates are known."),
    (re.compile(r"\byou(?:['’]ve| have)?\s+(?:already\s+)?(?:received|got|been (?:given|issued))\s+(?:your |an |the )?"
                r"(?:acas |early conciliation )?certificate\b", re.I),
     re.compile(r"certificate", re.I),
     "You have not mentioned an Early Conciliation certificate — tell me its date if you have one."),
    (re.compile(r"\byou(?:['’]ve| have)?\s+(?:already\s+)?(?:appealed|lodged an appeal|submitted an appeal)\b", re.I),
     re.compile(r"appeal", re.I), "You have not said whether you have appealed — tell me if you have, and when."),
    (re.compile(r"\byou(?:['’]ve| have)?\s+(?:already\s+)?(?:submitted|filed|lodged|issued|made)\s+(?:your |an |the |a )?"
                r"(?:et1|tribunal claim|claim form|court claim)\b", re.I),
     re.compile(r"\bet1\b|claim", re.I), "You have not said whether a claim has been submitted — tell me if it has, and when."),
    (re.compile(r"\byou(?:['’]ve| have)?\s+(?:already\s+)?(?:asked for|requested|applied for)\s+(?:a )?mandatory reconsideration\b", re.I),
     re.compile(r"reconsideration|\bmrn?\b", re.I),
     "You have not said whether you have asked for mandatory reconsideration — tell me if you have, and when."),
]
_SPLIT = re.compile(r"((?<=[.!?])\s+|\n)")


def guard_answer(answer: str, customer_text: str) -> Tuple[str, int]:
    """Replaces sentences that attribute an unstated legal step (and its date) to the customer."""
    parts, n = _SPLIT.split(answer or ""), 0
    for i in range(0, len(parts), 2):
        for claim, evidence_rx, fix in _CLAIMS:
            if claim.search(parts[i]) and not evidence_rx.search(customer_text or "") and \
                    not re.search(r"\b(if|whether|once|when|unless|have you|haven['’]t|not yet)\b", parts[i], re.I):
                lead = re.match(r"^\s*(?:[-*•]\s+|\d+\.\s+)?", parts[i]).group(0)
                parts[i], n = lead + fix, n + 1
                break
    return "".join(parts), n
