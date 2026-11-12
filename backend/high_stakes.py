"""Lex 2.0 Phase 2A-3: high-stakes situation recognition + response safeguards (deterministic, no AI, no network).
A matter is high-stakes only when the customer is personally involved — general questions stay ordinary."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

_I = re.I
DOMAINS: Dict[str, Dict[str, re.Pattern]] = {
    "criminal": {
        "topic": re.compile(r"\b(arrest\w*|police|custody|charged|charge me|caution(ed)?|interview under caution|voluntary interview|"
                            r"bail|magistrates|crown court|prosecut\w*|cps|procurator fiscal|accused|allegation|warrant|"
                            r"remand\w*|sentenc\w*|convict\w*|plead\w*|criminal record|offence)\b", _I),
        "urgent": re.compile(r"\b(arrested|in custody|at the police station|being held|detained|held in a cell|charged|"
                             r"warrant|on bail|remand\w*|police (?:want|asked|have asked|are asking) (?:me )?to (?:come|attend|"
                             r"interview|speak)|interview(?:ed)? under caution|voluntary interview|court (?:date|hearing)?)\b", _I),
    },
    "immigration": {
        "topic": re.compile(r"\b(visas?|leave to remain|ilr|indefinite leave|brp|evisa|home office|deport\w*|removal|"
                            r"overstay\w*|asylum|curtail\w*|sponsor\w*|immigration|settlement|euss|settled status|"
                            r"reporting centre|detention centre)\b", _I),
        "urgent": re.compile(r"\b(visa (?:expires|expired|has expired|ends|is ending|runs out|ran out)|overstay\w*|"
                             r"removal (?:directions|notice|window)|detain\w*|deport\w*|refus\w*|curtail\w*|"
                             r"appeal (?:deadline|window)|reporting|section 3c|no leave)\b", _I),
    },
    "housing": {
        "topic": re.compile(r"\b(evict\w*|possession|bailiffs?|enforcement officers?|section (?:8|21|173)|notice to (?:quit|leave)|"
                            r"homeless\w*|locked (?:me )?out|changed the locks?|repossess\w*|rent arrears|landlord|tenan\w*|"
                            r"occupation contract|mortgage arrears)\b", _I),
        "urgent": re.compile(r"\b(bailiffs?|enforcement officers?|eviction (?:date|notice)|possession (?:order|hearing|claim)|"
                             r"warrant of (?:possession|eviction)|homeless\w*|locked (?:me )?out|changed the locks?|"
                             r"on the street|nowhere to (?:go|stay|sleep)|kick(?:ed|ing)? (?:me|us) out|thr(?:ew|own) (?:me|us) out|"
                             r"section (?:8|21|173)|notice to (?:quit|leave)|repossess\w*)\b", _I),
    },
    "court": {
        "topic": re.compile(r"\b(court|hearing|judgment|ccj|claim form|defence|appeal|tribunal|summons|default judgment|"
                            r"strike out|order (?:says|requires|to)|n244|n9|sheriff|simple procedure|small claims?)\b", _I),
        "urgent": re.compile(r"\b(hearing (?:is )?(?:today|tomorrow|on|next)|court (?:is |date )?(?:today|tomorrow|on|next)|"
                             r"served (?:with|on)|default judgment|respond by|reply by|within \d+ days|deadline|"
                             r"order (?:says|requires)|appeal (?:by|within|deadline)|bailiff|enforcement)\b", _I),
    },
    "family": {
        "topic": re.compile(r"\b(divorc\w*|separat\w*|child arrangements?|custody|contact with (?:my|the|our)|non-molestation|"
                            r"occupation order|domestic (?:abuse|violence)|coercive|controlling|social services|"
                            r"social worker|child protection|care proceedings|safeguarding|prohibited steps|abduct\w*|"
                            r"cafcass|financial order|ex-?(?:wife|husband|partner))\b", _I),
        "urgent": re.compile(r"\b(hit(?:s|ting)? me|hurt(?:s|ing)? me|beat\w*|threaten\w*|scared|afraid|frightened|unsafe|"
                             r"not safe|abus\w*|social services|social worker|care proceedings|took (?:my|the|our) (?:child|kids|"
                             r"children|son|daughter|baby)|taken (?:my|the|our) (?:child|kids|children|son|daughter|baby)|"
                             r"abduct\w*|emergency|non-molestation|stalk\w*)\b", _I),
    },
    "employment": {
        "topic": re.compile(r"\b(dismiss\w*|sacked|fired|redundan\w*|employment tribunal|tribunal|acas|disciplinary|grievance|"
                            r"constructive(?:ly)? dismiss\w*|whistleblow\w*|discriminat\w*|unpaid wages|notice pay|"
                            r"settlement agreement)\b", _I),
        "urgent": re.compile(r"\b(dismissed|sacked|fired|let go|made redundant|last day|tribunal|early conciliation|"
                             r"deadline|time limit|settlement agreement|disciplinary (?:hearing|meeting))\b", _I),
    },
    "medical_negligence": {
        "topic": re.compile(r"\b(negligen\w*|misdiagnos\w*|surgery (?:went wrong|error)|operation went wrong|clinical|"
                            r"hospital (?:error|mistake)|gp (?:missed|failed)|birth injur\w*|medical mistake|"
                            r"personal injur\w*|accident at work|injured (?:at|in|by)|hit by a (?:car|vehicle|bus|van|lorry|bike|cyclist)|"
                            r"(?:road|car|traffic) accident)\b", _I),
        "urgent": re.compile(r"\b(injur\w*|died|death|negligen\w*|years ago|limitation|time limit|misdiagnos\w*)\b", _I),
    },
}
_PERSONAL = re.compile(r"\b(i|i'm|im|i've|ive|i'd|i'll|me|my|mine|myself|we|we're|we've|our|us)\b", _I)
_GENERAL = re.compile(r"\b(in general|generally|hypothetical\w*|in theory|for (?:an|my) (?:essay|assignment|coursework|"
                      r"dissertation|exam|novel|story|book|lecture)|just curious|out of interest|what is the law on|"
                      r"how does the law|explain the law)\b", _I)
_TIME = re.compile(r"\b(today|tonight|tomorrow|this (?:week|morning|afternoon|evening)|next (?:week|monday|tuesday|wednesday|"
                   r"thursday|friday|saturday|sunday)|right now|now|immediately|asap|urgent\w*|within \d+ days|"
                   r"in \d+ days|by (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|expires?|deadline)\b", _I)
_DANGER = re.compile(r"\b((?:going|gonna|threaten\w*) to (?:kill|hurt|hit|attack|stab)|(?:is|are|keeps?) (?:hitting|"
                     r"attacking|beating|strangling|choking) me|in (?:immediate )?danger|not safe (?:at home|here|right now)|"
                     r"scared for my (?:life|safety)|fear for my (?:life|safety)|outside my (?:door|house|flat)|"
                     r"(?:has|with) a (?:knife|weapon|gun)|strangl\w*|chok(?:ed|ing) me)\b", _I)
_SELF_HARM = re.compile(r"\b(kill myself|end my life|suicid\w*|self[- ]harm\w*|don'?t want to (?:live|be alive)|"
                        r"take my own life)\b", _I)
_KID = r"(?:child|children|kids?|son|daughter|baby|toddler|grandchild\w*|step-?(?:son|daughter|child))"
_CHILD_RISK = re.compile(
    rf"\b(?:is|are|keeps?|has been|have been|was|were|been)\s+(?:hurting|abusing|hitting|beating|neglecting|harming|"
    rf"threatening|touching)\s+(?:my|our|the|her|his)\s+{_KID}\b|"
    rf"\b{_KID}\b[^.\n]{{0,40}}\b(?:is|are|was|were|has been|have been)\s+(?:being\s+)?(?:abused|neglected|harmed|"
    rf"unsafe|in danger|not safe|at risk)\b|"
    rf"\b(?:abus\w*|neglect\w*|safeguarding concern\w*)\b[^.\n]{{0,30}}\b(?:my|our|the)\s+{_KID}\b", _I)
_NEGATED = re.compile(r"\b(not|never|no longer|isn'?t|wasn'?t|haven'?t|hasn'?t)\s+(?:been\s+|being\s+)?$", _I)
_NATION_DEPENDENT = {"criminal", "housing", "court", "family", "medical_negligence"}


def _hits(rx: re.Pattern, text: str) -> bool:
    return any(not _NEGATED.search(text[max(0, m.start() - 20):m.start()]) for m in rx.finditer(text))


def classify(message: str, context: str = "", category: Optional[str] = None) -> dict:
    """level: emergency | urgent | high | general | standard. Personal involvement is required for urgent/high."""
    msg, ctx = message or "", context or ""
    both = f"{ctx}\n{msg}"
    domains = [d for d, rx in DOMAINS.items() if _hits(rx["topic"], both)]
    if category in ("immigration", "employment", "medical_negligence") and category not in domains:
        domains.append(category)
    if category == "court_prep" and "court" not in domains:
        domains.append("court")
    personal = bool(_PERSONAL.search(msg)) and not (_GENERAL.search(msg) and not _TIME.search(msg))
    danger = _hits(_DANGER, msg)
    self_harm = _hits(_SELF_HARM, msg)
    child = personal and _hits(_CHILD_RISK, msg)
    urgent = [d for d in domains if _hits(DOMAINS[d]["urgent"], msg)]
    timed = bool(_TIME.search(msg))
    if (danger or child) and "family" not in domains:
        domains.append("family")
    if danger or self_harm or child:
        level = "emergency"
    elif domains and personal and (urgent or timed):
        level = "urgent"
    elif domains and personal:
        level = "high"
    elif domains:
        level = "general"
    else:
        level = "standard"
    return {"level": level, "domains": domains, "urgent_domains": urgent, "personal": personal,
            "danger": danger, "self_harm": self_harm, "child_risk": child}


def is_high(hs: Optional[dict]) -> bool:
    return bool(hs) and hs.get("level") in ("emergency", "urgent", "high")


MISSING = {
    "criminal": "whether they have been arrested, charged, or invited to a voluntary interview; the date and police station or "
                "court; whether they already have a solicitor",
    "immigration": "current visa or status and its exact expiry date; whether an in-time application was made; the date and "
                   "wording of any Home Office decision and whether it gives a right of appeal or administrative review",
    "housing": "which UK nation the property is in; the type of tenancy or occupation contract; the type and date of any notice; "
               "whether court papers, a possession order or an eviction notice have been received and their dates",
    "court": "which court or tribunal; the case number; exactly what the order, claim or letter requires; the date it was "
             "served; any hearing date",
    "family": "which UK nation; whether anyone is in immediate danger; the children's ages and current arrangements; any "
              "existing court orders or social services involvement",
    "employment": "whether the work was in Great Britain or Northern Ireland; start date and the exact date employment ended; "
                  "whether Acas (or the LRA in NI) early conciliation has started and the certificate dates",
    "medical_negligence": "the date of the incident and when they first knew it may have been caused by negligence; the "
                          "injured person's age and whether they have capacity; which UK nation",
}
HELP = {
    "criminal": "free, independent legal advice at the police station is available in every UK nation — they can ask for the "
                "duty solicitor at any time, and should not answer questions in an interview without advice",
    "immigration": "an OISC-regulated immigration adviser or an immigration solicitor; legal aid may be available for asylum "
                   "and detention",
    "housing": "Shelter (England: 0808 800 4444), Shelter Cymru, Shelter Scotland, Housing Advice NI or the council's housing "
               "team; free on-the-day legal advice is often available at possession hearings",
    "court": "the court or tribunal office named on the papers, Citizens Advice, or a solicitor; legal aid or free advice "
             "schemes may apply",
    "family": "a family law solicitor (legal aid may be available where there is evidence of domestic abuse) and the "
              "specialist helplines below where safety is a concern",
    "employment": "Acas (0300 123 1100) or the Labour Relations Agency in Northern Ireland, a trade union, or an employment "
                  "solicitor",
    "medical_negligence": "a clinical negligence or personal injury solicitor (many offer free initial assessments) and the "
                          "NHS complaints process",
}


def prompt_block(hs: dict, nation_known: bool, country: Optional[str]) -> str:
    """System-prompt framework for high-stakes matters. Empty for ordinary questions."""
    if not is_high(hs):
        return ""
    doms = hs["domains"] or ["general"]
    lines = [
        f"\n\nHIGH-STAKES MATTER ({hs['level'].upper()}: {', '.join(doms)}). The customer is personally affected. Stay helpful — "
        "do NOT refuse or give a vague answer; give real, practical general legal information. Structure the answer:",
        "1. Their position in plain language (what is happening legally, what it means for them).",
        "2. Label the basis of each key point: 'Current law (checked)' only for provisions in the retrieved legislation.gov.uk "
        "records or app-signed-off facts; 'Official guidance' for retrieved official guidance; 'Your facts' for what the "
        "customer told you; 'Our reading' for interpretation; 'Not confirmed' for anything you could not check. Never invent "
        "legislation, sections, cases, citations or court decisions; if unsure, say so and name the official source to check.",
        "3. Deadlines: distinguish statutory time limits from court-ordered or case-specific deadlines (the papers or order "
        "govern those). Mention exceptions and qualifying conditions that could change the deadline. Never invent a date — "
        "only use dates the customer gave or the app calculated; otherwise explain how the deadline is worked out and say "
        "it is uncertain. Where delay could harm their rights, urge prompt action without false alarm.",
        "4. Missing facts that change the answer — ask for the most important ones (at most 3): "
        + "; ".join(MISSING[d] for d in doms if d in MISSING) + ".",
        "5. Practical options and next steps, most urgent first.",
        "6. When qualified help matters, say so plainly and name where to get it: "
        + "; ".join(HELP[d] for d in doms if d in HELP) + ".",
        "7. Never guarantee success or predict a court outcome definitively; describe likely factors and risks instead.",
        "8. Check effective dates: if a provision is repealed, not yet in force or recently changed, say so.",
    ]
    if (country or "GB").upper() in ("GB", "UK") and not nation_known and any(d in _NATION_DEPENDENT for d in doms):
        lines.append("JURISDICTION: it is not yet known which UK nation's law applies. Ask early (one short question) which UK "
                     "nation the matter is in, and do not give nation-specific deadlines or conclusions until confirmed.")
    if hs.get("level") == "emergency":
        lines.append("SAFETY FIRST: the customer may be at risk now. Open with a short line on getting immediate help "
                     "(the app also adds emergency contacts), then give the legal information.")
    return "\n".join(lines)


EMERGENCY_LEAD = {
    "en": "If you or anyone else is in immediate danger, call 999 now.",
    "es": "Si usted u otra persona está en peligro inmediato, llame ahora al 999.",
    "fr": "Si vous ou quelqu'un d'autre êtes en danger immédiat, appelez le 999 maintenant.",
    "ar": "إذا كنت أنت أو أي شخص آخر في خطر مباشر، اتصل بالرقم 999 الآن.",
    "pl": "Jeśli Ty lub ktoś inny jesteście w bezpośrednim niebezpieczeństwie, zadzwoń teraz pod 999.",
    "de": "Wenn Sie oder jemand anderes in unmittelbarer Gefahr sind, rufen Sie jetzt die 999 an.",
    "hi": "अगर आप या कोई और तुरंत खतरे में है, तो अभी 999 पर कॉल करें।",
    "ur": "اگر آپ یا کوئی اور فوری خطرے میں ہے تو ابھی 999 پر کال کریں۔",
    "it": "Se tu o qualcun altro siete in pericolo immediato, chiama subito il 999.",
    "pt": "Se você ou outra pessoa estiver em perigo imediato, ligue já para o 999.",
    "zh": "如果您或其他人正处于紧急危险中，请立即拨打 999。",
}
_HELPLINES = {
    "abuse": "Domestic abuse (free, 24h): England 0808 2000 247 · Wales Live Fear Free 0808 80 10 800 · Scotland "
             "0800 027 1234 · Northern Ireland 0808 802 1414 · Men's Advice Line 0808 801 0327. If you can't speak on a "
             "999 call, stay on the line and press 55 when prompted (mobile).",
    "child": "Worried about a child: NSPCC 0808 800 5000 · Childline (for children) 0800 1111 · or your local council's "
             "children's services.",
    "self_harm": "If you're thinking about ending your life: Samaritans 116 123 (free, 24h), or call 999 / go to A&E if "
                 "you're in danger now.",
    "police": "At a police station: you have the right to free, independent legal advice — ask for the duty solicitor.",
}


def emergency_note(hs: dict, language: str) -> str:
    lead = EMERGENCY_LEAD.get((language or "en")[:2].lower(), EMERGENCY_LEAD["en"])
    parts = [lead]
    if hs.get("danger") or "family" in hs.get("domains", []):
        parts.append(_HELPLINES["abuse"])
    if hs.get("child_risk"):
        parts.append(_HELPLINES["child"])
    if hs.get("self_harm"):
        parts.append(_HELPLINES["self_harm"])
    return "**Urgent help:** " + " ".join(parts)


_DETAINED = re.compile(r"\b(arrested|in custody|at the police station|being held|held in a cell|detained)\b", _I)
_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
_DATE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTHS})\s+(\d{{4}})\b|\b(\d{{1,2}})/(\d{{1,2}})/(\d{{4}})\b", _I)
_DEADLINE_WORD = re.compile(r"\b(deadline|by|before|no later than|time limit|expires?|must (?:file|submit|respond|reply|"
                            r"appeal|apply|lodge|claim)|last day|due)\b", _I)
_GUARANTEE = [
    (re.compile(r"\byou(?:'ll| will)\s+(?:definitely|certainly|surely|absolutely)\s+(?:win|succeed)\b[^.\n]*", _I),
     "you may have a strong case, but no outcome can be guaranteed"),
    (re.compile(r"\b(?:you are|you're)\s+guaranteed\s+to\s+(?:win|succeed|get)\b[^.\n]*", _I),
     "no outcome can be guaranteed"),
    (re.compile(r"\bthe (court|tribunal|judge)\s+will\s+(?:definitely|certainly|surely)\s+", _I), r"the \1 may "),
    (re.compile(r"\b100\s?% (?:chance|certain|sure)\b", _I), "a reasonable chance (not guaranteed)"),
]


def _dates(text: str) -> set:
    out = set()
    for m in _DATE.finditer(text or ""):
        if m.group(1):
            out.add((int(m.group(1)), m.group(2).lower(), int(m.group(3))))
        else:
            months = _MONTHS.split("|")
            mo = int(m.group(5))
            if 1 <= mo <= 12:
                out.add((int(m.group(4)), months[mo - 1], int(m.group(6))))
    return out


def unconfirmed_deadline_dates(answer: str, allowed_text: str) -> List[str]:
    """Exact dates the answer presents as deadlines that neither the customer nor the app's calculator supplied."""
    allowed = _dates(allowed_text)
    found = []
    for m in _DATE.finditer(answer or ""):
        window = answer[max(0, m.start() - 80):m.end() + 40]
        key = next(iter(_dates(m.group(0))), None)
        if key and key not in allowed and _DEADLINE_WORD.search(window) and m.group(0) not in found:
            found.append(m.group(0))
    return found


def finalize(text: str, hs: Optional[dict], allowed_text: str, language: str) -> Tuple[str, dict]:
    """Deterministic post-checks for high-stakes answers: emergency contacts, guarantee wording, unconfirmed dates."""
    rep = {"level": (hs or {}).get("level", "standard"), "emergency_note": False, "guarantees_softened": 0,
           "unconfirmed_dates": 0, "police_note": False}
    if not is_high(hs):
        return text, rep
    from lex_safety import insert_before_tail
    out = text or ""
    for rx, repl in _GUARANTEE:
        out, n = rx.subn(repl, out)
        rep["guarantees_softened"] += n
    dates = unconfirmed_deadline_dates(out, allowed_text)
    if dates:
        rep["unconfirmed_dates"] = len(dates)
        out = insert_before_tail(out, f"**Date check:** {', '.join(dates)} {'was' if len(dates) == 1 else 'were'} not given "
                                      "by you or calculated by the app, so treat "
                                      f"{'it' if len(dates) == 1 else 'them'} as unconfirmed. Check the exact deadline on "
                                      "your letter, notice or court order, or with an adviser, and act promptly.")
    if "criminal" in hs.get("domains", []) and _DETAINED.search(allowed_text or "") and "duty solicitor" not in out.lower():
        out = insert_before_tail(out, f"**Your rights:** {_HELPLINES['police']}")
        rep["police_note"] = True
    if hs.get("level") == "emergency":
        out = emergency_note(hs, language) + "\n\n" + out
        rep["emergency_note"] = True
    return out, rep
