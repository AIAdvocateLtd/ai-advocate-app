"""Official-source rules for weaknesses found in the Lex 2.0 Phase 2E evaluation (checked 18 Nov 2026 against the linked
GOV.UK / gov.wales / Acas / LRA / legislation.gov.uk pages). NOT reviewed by a qualified lawyer — Lex is told so."""
import re
from typing import List, Optional

CHECKED = "18 November 2026"
LEG = "https://www.legislation.gov.uk"
_GB = {"england", "wales", "scotland", None}

# (id, topic regex, nations it applies to (None = nation unknown), text, sources)
RULES = [
    ("et_time_limits", r"employ|dismiss|sacked|fired|redundan|tribunal|acas|wages?|discriminat|pregnan|holiday pay|unpaid", _GB,
     "Employment tribunal time limits (England, Wales, Scotland) depend on the DATE OF THE ACT (for unfair dismissal, the "
     "effective date of termination), not today's date: on or after 1 October 2026 most claims have 6 months less one day; "
     "before 1 October 2026, 3 months less one day (statutory redundancy pay and equal pay already had 6 months). The change "
     "(Employment Rights Act 2025 s.152 and Sch.12) was commenced on 1 October 2026 by SI 2026/954, which does not apply where "
     "the relevant date is before 1 October 2026. Exception: breach of contract claims in Scotland — 6 months only for a "
     "breach on or after 9 November 2026 (Acas). Conduct extending over a period runs from the end of the period (Equality Act "
     "2010 s.123(3)); a series of deductions runs from the last deduction (Employment Rights Act 1996 s.23(3)). Acas early "
     "conciliation must be started within the limit and pauses it. Never present 6 months as universal, and never tell "
     "someone they are definitely out of time.",
     [f"{LEG}/uksi/2026/954", f"{LEG}/ukpga/2025/36/schedule/12", "https://www.acas.org.uk/employment-tribunal-time-limits"]),
    ("ni_employment", r"employ|dismiss|sacked|fired|redundan|tribunal|acas|lra|wages?|discriminat", {"northern_ireland"},
     "Northern Ireland employment disputes: early conciliation is with the Labour Relations Agency (LRA, 03300 552 220, "
     "lra.org.uk) — NOT Acas — and must be notified before an INDUSTRIAL tribunal claim (not an 'employment tribunal'). The "
     "time limit is generally 3 months less one day from the act; LRA early conciliation can extend it. NI employment law is "
     "devolved: the Employment Rights Act 2025 Great Britain changes (6-month time limit, new qualifying period) do not apply "
     "to most NI claims. Unfair dismissal in NI needs one year's continuous employment (Employment Rights (Northern Ireland) "
     "Order 1996 art.140). Signpost the LRA, nidirect and Advice NI — never Acas or GOV.UK employment tribunal pages.",
     ["https://www.lra.org.uk/resources/early-conciliation", f"{LEG}/nisi/1996/1919/article/140"]),
    ("wales_tenancy", r"landlord|tenan|rent|evict|section 21|section 173|notice|occupation contract|deposit|possession",
     {"wales"},
     "Wales: since 1 December 2022 the Renting Homes (Wales) Act 2016 governs most rentals — tenants are 'contract-holders' "
     "with occupation contracts, and a Housing Act 1988 section 21 notice does not apply to them. The no-fault route is a "
     "section 173 notice: for a periodic standard contract agreed on or after 1 December 2022 it must give at least 6 months' "
     "notice and cannot be given in the first 6 months of occupation; it cannot be given during a fixed term. Contracts that "
     "converted on 1 December 2022 had different transitional rules. A notice is not an eviction — the landlord needs a court "
     "possession order, and some breaches by the landlord (for example written-statement or deposit rules) can prevent a valid "
     "notice. If a Welsh customer mentions 'section 21', explain this and ask for the notice wording and date; never apply "
     "England's section 21 or Renters' Rights Act 2025 rules in Wales. Signpost Shelter Cymru and gov.wales.",
     ["https://www.gov.wales/renting-homes-frequently-asked-questions-tenants", f"{LEG}/anaw/2016/1/section/173"]),
    ("scotland_exceptions", r"park|pcn|keeper|divorc|separat|sue|suing|small claim|court|limitation|time limit|prescription",
     {"scotland"},
     "Scotland differs: private-parking keeper liability under the Protection of Freedoms Act 2012 Sch.4 does not extend to "
     "Scotland; claims up to £5,000 use simple procedure in the sheriff court (not the English small claims track); "
     "personal injury actions have 3 years (Prescription and Limitation (Scotland) Act 1973 s.17) and most contract debts "
     "prescribe after 5 years; divorce is based on irretrievable breakdown, commonly shown by 1 year's separation with "
     "consent or 2 years without (Divorce (Scotland) Act 1976 s.1) — the England & Wales 20-week period does not apply.",
     [f"{LEG}/ukpga/2012/9/schedule/4", f"{LEG}/ukpga/1973/52/section/17", f"{LEG}/ukpga/1976/39/section/1"]),
    ("immigration_core", r"visas?\b|ilr\b|indefinite leave|settled status|pre-settled|home office|abroad|detain|removal|removed tomorrow|deport", {"england", "wales", "scotland", "northern_ireland", None},
     "Immigration (UK-wide): an ordinary visitor visa refusal carries NO right of appeal — appeals exist only where a human "
     "rights or protection claim was refused; otherwise the routes are a fresh application or, if the decision was unlawful, "
     "judicial review (apply promptly). Treat a document that claims an appeal right for a visitor refusal with caution. ILR "
     "continuous residence is usually broken by more than 180 days' absence in any rolling 12-month period (not calendar "
     "year), with limited exceptions for serious or compelling reasons. If someone is detained and facing removal within "
     "hours, the first step is an immigration solicitor tonight (legal aid may be available; urgent judicial review/injunction "
     "applications can be made out of hours) and charities such as Bail for Immigration Detainees — never promise removal "
     "can be stopped.",
     ["https://www.gov.uk/immigration-asylum-tribunal", "https://www.gov.uk/guidance/immigration-rules/immigration-rules-appendix-continuous-residence",
      "https://www.gov.uk/guidance/apply-for-a-judicial-review-in-an-immigration-or-asylum-case"]),
    ("settlement_agreement", r"settlement agreement|compromise agreement|sign by|waive|exit package", _GB | {"northern_ireland"},
     "Settlement agreements (GB): a settlement agreement only validly waives statutory employment claims if it is in writing, "
     "relates to the particular complaints, and the employee has received advice from a named relevant independent adviser "
     "(e.g. a qualified lawyer) with insurance (Employment Rights Act 1996 s.203(3)). The Acas Code recommends at least 10 "
     "calendar days to consider it; an employer's deadline is not a legal time limit, and tribunal time limits keep running. "
     "Employers commonly contribute to the adviser's fee. Never tell the customer to sign or not sign.",
     [f"{LEG}/ukpga/1996/18/section/203", "https://www.acas.org.uk/acas-code-of-practice-settlement-agreements/html"]),
    ("divorce_ew", r"divorc", {"england", "wales"},
     "Divorce in England & Wales (no-fault since 6 April 2022): wait 20 weeks after the application is issued before "
     "applying for the conditional order, then at least 43 days (6 weeks and 1 day) before the final order — at least "
     "about 26 weeks overall, often longer. Sort finances (a financial order) before the final order where possible.",
     ["https://www.gov.uk/divorce"]),
    ("limitation_children_capacity", r"injur|negligen|birth|lacks? capacity|too late|limitation",
     {"england", "wales", None},
     "Limitation for injury claims (England & Wales): normally 3 years from the injury or date of knowledge (Limitation Act "
     "1980 s.11). For a child, time does not start until their 18th birthday, so the claim can usually be brought until "
     "age 21; for someone who lacks mental capacity, time does not run while the incapacity lasts (s.28 and s.38). Never "
     "tell a parent a child's injury claim is time-barred without checking these rules.",
     [f"{LEG}/ukpga/1980/58/section/28", f"{LEG}/ukpga/1980/58/section/11"]),
    ("deposits_england", r"deposit", {"england"},
     "England tenancy deposits: if the landlord failed to protect the deposit or give the prescribed information, the court "
     "must order a payment of not less than the deposit and not more than three times it (Housing Act 2004 s.214(4)); a claim "
     "can still be made after the tenancy ends. The limitation period should be confirmed with an adviser.",
     [f"{LEG}/ukpga/2004/34/section/214"]),
    ("consumer_core", r"faulty|refund|reject|repair|broken|crash|laptop|phone|bought|purchase|invoice|late payment", _GB | {"northern_ireland"},
     "Consumer and payment basics (UK): for faulty goods the short-term right to reject for a full refund lasts 30 days from "
     "delivery/ownership (Consumer Rights Act 2015 s.22); within that period a shop cannot insist on repair only. Between "
     "businesses the Consumer Rights Act does not apply; unpaid commercial invoices can carry statutory interest and fixed "
     "compensation under the Late Payment of Commercial Debts (Interest) Act 1998. State these rules plainly when relevant.",
     [f"{LEG}/ukpga/2015/15/section/22", f"{LEG}/ukpga/1998/20"]),
    ("parking_council", r"pcn\b|penalty charge|parking\b", {"england", "wales"},
     "Council PCNs (England & Wales): the 50% discount runs 14 days from service (21 days for camera/postal PCNs); if it has "
     "passed, the full charge applies unless the council re-offers the discount after an informal challenge. Formal "
     "representations are made within 28 days of the Notice to Owner, then appeal to the independent tribunal (Traffic "
     "Penalty Tribunal, or London Tribunals in London). Unpaid after 28 days → charge certificate (+50%).",
     ["https://www.gov.uk/parking-tickets"]),
]
_RX = {r[0]: re.compile(rf"\b(?:{r[1]})", re.I) for r in RULES}

DIRECTNESS = (
    "\n\nANSWER DIRECTNESS: when a rule appears in the APP-CALCULATED DATES or the OFFICIAL-SOURCE RULES above, or in a "
    "retrieved official source, state it plainly — the rule, the time limit and the Act that sets it — with its status "
    "('official-source rule, not yet reviewed by a lawyer'). Name the governing Act for well-established rules (the app checks "
    "every Act and instrument against legislation.gov.uk). Use 'Not confirmed' only for points that are genuinely uncertain, "
    "recent, disputed or depend on facts you do not have — never as a substitute for a rule you were given.")
PLUS_EXTRA = (
    " Do not answer with a list of 'not confirmed' points: give the customer the actual rule and what it means for them, "
    "then the uncertainty.")


CASE_TOPICS = [
    (r"employ|dismiss|sacked|fired|redundan|tribunal|wages?|holiday pay|discriminat|pregnan|worker|resign", ("employment", "discrimination", "holiday", "worker")),
    (r"negligen|surgery|hospital|gp\b|doctor|consent|injur|birth", ("negligence",)),
    (r"park(?:ing|ed)?\b|penalty charge|charge notice|pcn\b", ("parking",)),
    (r"contract|builder|refund|faulty|invoice|damages|exclusion", ("contract",)),
    (r"landlord|tenan|evict|deposit|possession|homeless|licen[cs]e", ("tenancy", "lease", "possession", "homelessness")),
    (r"cohabit|common.law|divorc|separat|matrimonial|prenup|nuptial", ("cohabitants", "divorce", "nuptial")),
    (r"visa|asylum|deport|removal|home office|immigra|tribunal decision|judicial review", ("immigration", "asylum", "judicial review")),
    (r"claim form|court|default judgment|relief from sanctions|served|service of", ("civil procedure",)),
]


def case_lines(text: str) -> List[str]:
    import landmark_cases
    areas = {a for rx, a_s in CASE_TOPICS if re.search(rf"\b(?:{rx})", text, re.I) for a in a_s}
    picked = [e for e in landmark_cases.CASES if any(a in e[5] for a in areas)]
    return [f"{e[2]} {'; '.join(e[3])} — {e[5]}" for e in picked[:6]]


def matched(message: str, context: str, nation: Optional[str]) -> List[tuple]:
    text = f"{message}\n{context or ''}"
    return [r for r in RULES if nation in r[2] and _RX[r[0]].search(text)]


def block(message: str, context: str, nation: Optional[str], provider: Optional[str] = None, country: Optional[str] = "GB") -> str:
    if (country or "GB").upper() not in ("GB", "UK"):
        return ""
    rules = matched(message, context, nation if nation in ("england", "wales", "scotland", "northern_ireland") else None)
    cases = case_lines(f"{message}\n{context or ''}")
    cases_block = ("\n\nSOURCED CASE LIST (the app has checked that these decisions exist under these citations; NOT reviewed by "
                   "a qualified lawyer). Cite one only if it is directly relevant, using exactly this name and citation, and "
                   "describe only its well-known principle. Never cite any other case unless it appears in the retrieved "
                   "sources:\n- " + "\n- ".join(cases)) if cases else ""
    if not rules:
        return cases_block
    lines = "\n".join(f"- {r[3]} (Sources: {', '.join(r[4])})" for r in rules[:5])
    return cases_block + (f"\n\nOFFICIAL-SOURCE RULES (checked by the app against the official pages listed on {CHECKED}; NOT yet reviewed "
            "by a qualified lawyer — rely on them over older training knowledge, apply only the ones relevant to this "
            "customer's UK nation and facts, and say a regulated adviser should confirm):\n" + lines +
            DIRECTNESS + (PLUS_EXTRA if provider == "openai" else ""))
