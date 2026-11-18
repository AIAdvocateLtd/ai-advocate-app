"""Builds the Lex 2.0 legal review pack (Markdown + Word) for a qualified UK legal professional.
Run: cd /app/backend && python -m evals.build_review_pack   (reads preview DB fact packs; no AI calls)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

import landmark_cases  # noqa: E402
import lex_guidance  # noqa: E402
from evals.lex_eval_scenarios import SCENARIOS, REFERENCE_STATUS  # noqa: E402

OUT_MD = "/app/memory/lex2_legal_review_pack.md"
OUT_DOCX = "/app/memory/lex2_legal_review_pack.docx"
SIGN = "Decision: [ ] Approve  [ ] Amend  [ ] Reject   Reviewer: ________  Date: ________"

ET_ISSUES = [
    ("ET-1", "Relevant date for conduct extending over a period or a series of deductions that began before and continued after "
             "1 Oct 2026 — does the 6-month limit apply to the whole claim (SI 2026/954 transitional wording)?"),
    ("ET-2", "Scotland breach-of-contract claims: 6 months only for breaches on/after 9 Nov 2026 (sourced from Acas only — the "
             "instrument itself was not located by the app)."),
    ("ET-3", "Statutory redundancy pay (ERA 1996 s.164) treated as 6 months before and after 1 Oct 2026; equal pay (EqA 2010 "
             "s.129) not calculated."),
    ("ET-4", "Qualifying period for ordinary unfair dismissal: 2 years where the EDT is before 1 Jan 2027; 6 months from 1 Jan "
             "2027 (SI 2026/559) — app wording in reference standards only."),
    ("ET-5", "Northern Ireland: 3 months less one day, LRA early conciliation, ERA 2025 GB changes not applicable to most NI "
             "industrial tribunal claims; one year's service for unfair dismissal (ER(NI)O 1996 art.140)."),
    ("ET-6", "Early conciliation extension mechanics (ETA 1996 s.207B) as applied by the calculator; 11:59pm cut-off (Acas)."),
]
CALCS = [
    ("DL-1", "Employment tribunal", "Date of act + claim type + nation: 6 months less one day on/after 1 Oct 2026, 3 months before; "
     "redundancy pay 6 months; Scotland breach of contract 9 Nov 2026; equal pay not calculated; NI 3 months via LRA; "
     "early-conciliation extension; flagged for independent check."),
    ("DL-2", "Court claims (CPR, England & Wales)", "Deemed service CPR 6.14/6.26; acknowledgment 14 days and defence 28 days "
     "after particulars (CPR 10.3, 15.4); flagged for independent check; Scotland/NI not calculated."),
    ("DL-3", "Council PCNs", "England & Wales: 14 days (windscreen) / 21 days (postal) discount; 28 days representations; tribunal "
     "28 days after rejection. Scotland: 14-day discount, First-tier Tribunal 28 days after rejection. NI: 14-day discount "
     "(nidirect), NI Traffic Penalty Tribunal. Unknown service method: no reminder date."),
    ("DL-4", "Private parking", "No date calculated; operator appeal per notice (codes usually 28 days); POPLA/IAS ~28 days after "
     "rejection; PoFA Sch.4 para 9(5) 14-day Notice to Keeper (E&W only)."),
    ("DL-5", "Consumer", "CRA 2015 s.22 30-day short-term right to reject; CCR 2013 14-day cancellation; approximate dates flagged."),
    ("DL-6", "Tenancy notices / section 8 / deposits", "Nation-specific notice periods (incl. Wales s.173 six months) — see "
     "deadline_calc; deposit protection 30 days (England)."),
    ("DL-7", "Limitation", "Limitation Act 1980 periods (PI 3 years, contract 6 years) incl. minors/capacity (s.28); Scotland "
     "prescription and limitation."),
    ("DL-8", "Immigration / benefits / divorce", "Visa expiry, ILR and citizenship eligibility dates; benefit mandatory "
     "reconsideration (1 month); divorce 20 weeks + 43 days (E&W)."),
]


async def _fact_packs():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    rows = await db.lex_lessons.find({"source": "fact_pack", "status": "approved"}, {"_id": 0}).sort("category", 1).to_list(200)
    return [(f"FP-{i + 1:02d}", r.get("category", ""), r.get("text", ""), (r.get("review_meta") or {}).get("source_url")
             or r.get("why", ""), (r.get("review_meta") or {}).get("verdict") or "awaiting sign-off") for i, r in enumerate(rows)]


def _sections(packs):
    sc = [(s["id"], f"{s['area']} · {s['nation']}", f"Q: {s.get('q', '')}\nLaw: {'; '.join(s.get('law') or [])}\n"
           f"Deadlines: {'; '.join(s.get('deadlines') or [])}\nFail modes: {'; '.join(s.get('fail') or [])}"
           + (f"\nCorrected 18 Nov 2026 (was: {s['corrected']['was']}) {s['corrected'].get('note', '')}" if s.get("corrected") else ""),
           ", ".join((s.get("corrected") or {}).get("sources") or []) or "AI-drafted, unsourced") for s in SCENARIOS]
    rules = [(f"R-{i + 1:02d}", r[0], r[3], ", ".join(r[4])) for i, r in enumerate(lex_guidance.RULES)]
    cases = [(f"C-{i + 1:02d}", e[5], f"{e[2]} {'; '.join(e[3])}", e[4]) for i, e in enumerate(landmark_cases.CASES)]
    return [
        ("A. Reference scenarios (40)", REFERENCE_STATUS, [(a, b, c, d) for a, b, c, d in sc]),
        ("B. Official-source rules given to Lex", "Checked against the linked official pages on 18 Nov 2026. In use in preview, "
         "labelled to Lex as not yet reviewed by a lawyer.", rules),
        ("C. Landmark cases (41)", landmark_cases.REVIEW_STATUS, cases),
        ("D. Legacy fact packs (38)", "Held back from Lex until a person signs them off (0 signed off in preview).",
         [(a, b, c, d) for a, b, c, d, _ in packs]),
        ("E. Employment tribunal commencement and transitional issues", "Open questions — interpretation needed.",
         [(a, "ERA 2025 / SI 2026/954", t, "") for a, t in ET_ISSUES]),
        ("F. High-risk deadline calculators", "Deterministic code; every result is labelled not legally confirmed.",
         [(a, b, c, "") for a, b, c in CALCS]),
    ]


INTRO = ("AI Advocate — Lex 2.0 legal review pack (preview build, 18 November 2026).\n\n"
         "Purpose: sign-off by a qualified UK legal professional. Nothing in this pack has been professionally reviewed. "
         "'Sourced' means the app or developer checked that an official page, Act, instrument or judgment exists and says "
         "this; it does NOT confirm the legal interpretation, how it applies to a customer, or that it is complete. AI "
         "evaluation scores are not legal certification.\n\nEvery numbered item below requires a reviewer decision.")


def write_md(sections):
    lines = ["# Lex 2.0 — legal review pack", "", INTRO, ""]
    for title, note, items in sections:
        lines += [f"## {title}", f"_{note}_", ""]
        for ref, cat, body, src in items:
            lines += [f"**{ref}** — {cat}", "", body.replace("\n", "  \n"), ""]
            if src:
                lines += [f"Sources: {src}", ""]
            lines += [SIGN, ""]
    open(OUT_MD, "w").write("\n".join(lines))


def write_docx(sections):
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.styles["Normal"].font.size = Pt(9)
    doc.add_heading("Lex 2.0 — legal review pack", 0)
    for para in INTRO.split("\n\n"):
        doc.add_paragraph(para)
    for title, note, items in sections:
        doc.add_heading(title, 1)
        doc.add_paragraph().add_run(note).italic = True
        t = doc.add_table(rows=1, cols=4)
        t.style = "Table Grid"
        for cell, h in zip(t.rows[0].cells, ("Ref", "Item", "Sources", "Reviewer decision")):
            cell.text = h
        for ref, cat, body, src in items:
            r = t.add_row().cells
            r[0].text, r[1].text, r[2].text = ref, f"{cat}\n{body}", src or "—"
            r[3].text = "[ ] Approve\n[ ] Amend\n[ ] Reject\nReviewer:\nDate:\nNotes:"
    doc.save(OUT_DOCX)


async def main():
    packs = await _fact_packs()
    sections = _sections(packs)
    write_md(sections)
    write_docx(sections)
    print({t: len(i) for t, _, i in sections}, OUT_MD, OUT_DOCX)


if __name__ == "__main__":
    asyncio.run(main())
