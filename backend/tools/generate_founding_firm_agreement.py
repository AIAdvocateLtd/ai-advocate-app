"""
Generate the AI Advocate FOUNDING FIRM AGREEMENT PDF — a one-page contract you
send to each of the first 20 firms confirming their locked-in £199 founding rate
and benefits.

The PDF has placeholders that you fill in per firm BEFORE sending:
  • {firm_name}
  • {sra_number}
  • {firm_address}
  • {primary_contact}
  • {signed_date}

Either:
  (a) Run from CLI with --firm-name + --sra etc. to produce a personalised PDF, or
  (b) Run with no args to produce a template with placeholders for you to fill in
      manually in a PDF editor before sending.

Output: /app/memory/AI_Advocate_Founding_Firm_Agreement.pdf
"""

import argparse
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle,
)

OUTPUT = "/app/memory/AI_Advocate_Founding_Firm_Agreement.pdf"

GOLD = HexColor("#f7c948")
GOLD_DEEP = HexColor("#b8860b")
DARK = HexColor("#1a1300")
INK = HexColor("#1a1a1a")
MUTED = HexColor("#666666")
BG = HexColor("#fdfaf0")
LINE = HexColor("#e5d99a")


def build(firm_name="[FIRM NAME]",
          sra_number="[SRA NUMBER]",
          firm_address="[FIRM ADDRESS]",
          primary_contact="[PRIMARY CONTACT NAME, JOB TITLE]",
          firm_email="[FIRM EMAIL]",
          signed_date=None):
    if not signed_date:
        signed_date = datetime.now().strftime("%d %B %Y")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title="AI Advocate — Founding Firm Agreement",
        author="AI Advocate Ltd.",
    )

    styles = getSampleStyleSheet()
    H1 = ParagraphStyle(
        "H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=18, textColor=DARK, leading=22, alignment=TA_CENTER,
        spaceAfter=4, spaceBefore=0,
    )
    SUB = ParagraphStyle(
        "SUB", parent=styles["Normal"], fontName="Helvetica",
        fontSize=10, textColor=GOLD_DEEP, alignment=TA_CENTER, leading=13,
        spaceAfter=10,
    )
    H2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=11, textColor=GOLD_DEEP, leading=14, spaceAfter=4,
        spaceBefore=10, letterSpacing=0.5,
    )
    BODY = ParagraphStyle(
        "Body", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9.5, textColor=INK, leading=13, alignment=TA_JUSTIFY,
        spaceAfter=5,
    )
    BULLET = ParagraphStyle(
        "Bullet", parent=BODY, leftIndent=14, bulletIndent=2,
        spaceAfter=3, alignment=TA_LEFT,
    )
    NUM = ParagraphStyle(
        "Numbered", parent=BODY, leftIndent=12, spaceAfter=4,
        alignment=TA_JUSTIFY,
    )
    SMALL = ParagraphStyle(
        "Small", parent=BODY, fontSize=8, textColor=MUTED, leading=10.5,
    )

    story = []

    # ───── HEADER ──────────────────────────────────────────────────────
    # Gold accent bar
    bar = Table([[""]], colWidths=[166 * mm], rowHeights=[3 * mm])
    bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GOLD)]))
    story.append(bar)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<font color="#1a1300"><b>AI ADVOCATE</b></font>',
        ParagraphStyle("brand", parent=BODY, fontSize=15,
                       alignment=TA_CENTER, fontName="Helvetica-Bold",
                       textColor=DARK, spaceAfter=2)))
    story.append(Paragraph(
        '<font color="#b8860b">FOUNDING FIRM AGREEMENT · LIFETIME £199/MO LOCK-IN</font>',
        ParagraphStyle("brand2", parent=BODY, fontSize=9,
                       alignment=TA_CENTER, fontName="Helvetica-Bold",
                       textColor=GOLD_DEEP, spaceAfter=14)))

    # ───── PARTIES ─────────────────────────────────────────────────────
    parties_table = Table([
        ["BETWEEN:",
         Paragraph(f"<b>AI Advocate Ltd.</b><br/>(Company No. [tbd], ICO Registration ZC158457)<br/>"
                   f"Registered in England &amp; Wales<br/>"
                   f'<font color="#666">Hereinafter <b>"AI Advocate"</b></font>',
                   BODY)],
        ["AND:",
         Paragraph(f"<b>{firm_name}</b><br/>"
                   f"SRA Number: {sra_number}<br/>"
                   f"{firm_address}<br/>"
                   f'<font color="#666">Hereinafter <b>"the Firm"</b></font>',
                   BODY)],
    ], colWidths=[20 * mm, 146 * mm])
    parties_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (0, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), GOLD_DEEP),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 8))

    # ───── PREAMBLE ────────────────────────────────────────────────────
    story.append(Paragraph(
        f"<b>Dated:</b> {signed_date}",
        ParagraphStyle("date", parent=BODY, alignment=TA_LEFT, fontSize=9.5)))
    story.append(Spacer(1, 2))
    story.append(Paragraph(
        "AI Advocate is launching a UK consumer + B2B legal-technology platform at "
        "<b>aiadvocate.co.uk</b>. The first 20 partner firms onboarded during the "
        "pre-launch cohort are designated <b>Founding Firms</b> and receive the "
        "lifetime benefits set out below in recognition of their early support.",
        BODY,
    ))

    # ───── BENEFITS ─────────────────────────────────────────────────────
    story.append(Paragraph("1. FOUNDING FIRM BENEFITS", H2))
    benefits = [
        "<b>Lifetime £199/month rate</b> — the Firm is granted the Founding Premium tier at £199 per month, locked-in for the lifetime of the Firm's subscription. AI Advocate will not increase this rate even when public Premium pricing rises (currently £199, anticipated public rate £249–£299 within 12 months of launch).",
        "<b>90-day free trial</b> — the first 90 days are entirely complimentary. No card required. The Firm may cancel at any time during this period with no obligation.",
        "<b>Founding Firm badge</b> — displayed on the Firm's directory listing in perpetuity, signalling early-partner status to all AI Advocate users.",
        "<b>Ranking boost</b> — the Firm's listing receives priority placement in the postcode and specialism searches relevant to its practice.",
        "<b>App Store launch marketing</b> — featured in screenshots and promotional collateral for the AI Advocate iOS / Android launch.",
        "<b>50% revenue-share on direct referrals</b> — when an AI Advocate user instructs the Firm and pays a fee, the standard referral arrangement is 30%. Founding Firms receive 50%.",
        "<b>Two-way Lex integration</b> — clients may share their full AI Advocate chat history with the Firm upon engagement, dramatically reducing initial consultation time.",
        "<b>Quarterly roadmap input</b> — a 30-minute call each quarter with the AI Advocate product team, with binding influence on roadmap priorities.",
        "<b>Direct success-manager contact</b> — a named contact at AI Advocate for any service issues; response time guarantee under 24 hours, Monday–Friday.",
    ]
    for b in benefits:
        story.append(Paragraph(f"▸ {b}", BULLET))

    # ───── FIRM COMMITMENTS ─────────────────────────────────────────────
    story.append(Paragraph("2. THE FIRM'S COMMITMENTS", H2))
    commits = [
        "Maintain a complete firm profile (logo, specialties, opening hours, photo) within the AI Advocate Firm Portal.",
        "Respond to qualified client invites received via AI Advocate within <b>48 working hours</b>.",
        "Provide a 1–2 sentence testimonial after 60 days of the trial, if it is working for the Firm. The Firm reserves the right to decline if the trial is unsatisfactory; AI Advocate may publish the testimonial in marketing collateral with the Firm's name and logo.",
        "Compliance with AI Advocate's Solicitor Code of Conduct (see Schedule A). All SRA / LSS / LSNI numbers will be verified.",
        "Notify AI Advocate within 5 working days of any material change to the Firm's regulatory status (e.g. SRA intervention, name change, merger).",
    ]
    for c in commits:
        story.append(Paragraph(f"▸ {c}", BULLET))

    # ───── TERMS ───────────────────────────────────────────────────────
    story.append(Paragraph("3. TERM AND TERMINATION", H2))
    story.append(Paragraph(
        "3.1 <b>Initial term</b> — 12 months from the date of the first paid month (i.e. after the 90-day trial). "
        "Auto-renews monthly thereafter unless terminated.<br/>"
        "3.2 <b>Cancellation</b> — the Firm may cancel at any time with 30 days' written notice, no fees, no penalty. "
        "If cancelled, the Firm's £199 lifetime rate is forfeit; re-onboarding would be at then-current public pricing.<br/>"
        "3.3 <b>Termination by AI Advocate</b> — only for cause (loss of SRA regulation, material breach of the Solicitor Code of Conduct, "
        "or 60+ days of unanswered client invites). 30 days' notice and cure period.<br/>"
        "3.4 <b>£199 lifetime survival</b> — provided the Firm has not cancelled or been terminated for cause, the £199 rate "
        "remains in force regardless of any future public-pricing changes. This commitment binds AI Advocate and its successors.",
        BODY,
    ))

    # ───── LIABILITY ────────────────────────────────────────────────────
    story.append(Paragraph("4. NON-ADVICE POSITIONING", H2))
    story.append(Paragraph(
        "4.1 The AI Advocate consumer-facing service provides general legal <i>information</i> only and not advice. "
        "AI Advocate is not a regulated provider of legal services in the United Kingdom under the Legal Services Act 2007.<br/>"
        "4.2 Once a user engages the Firm via the AI Advocate platform, the regulated solicitor-client relationship exists "
        "solely between the user and the Firm. AI Advocate is not a party to that engagement.<br/>"
        "4.3 The Firm bears full professional responsibility for any advice or representation provided to users referred via "
        "the AI Advocate platform. AI Advocate's liability is capped at three months of fees paid by the Firm.",
        BODY,
    ))

    # ───── DATA ────────────────────────────────────────────────────────
    story.append(Paragraph("5. DATA PROTECTION", H2))
    story.append(Paragraph(
        "Both parties act as separate data controllers in respect of their own operations. Where the Firm processes personal "
        "data of users introduced via AI Advocate, the Firm is the data controller in respect of that processing. AI Advocate's "
        "Privacy Policy (aiadvocate.co.uk/privacy) and ICO registration (ZC158457) govern its own data handling. "
        "Both parties commit to UK GDPR compliance and to notify each other of any data incident affecting jointly-introduced "
        "users within 72 hours.",
        BODY,
    ))

    # ───── SIGNATURES ─────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(Paragraph("6. SIGNATURES", H2))
    sig_table = Table([
        [Paragraph("<b>For AI Advocate Ltd.</b>", BODY),
         Paragraph(f"<b>For {firm_name}</b>", BODY)],
        [Spacer(1, 14), Spacer(1, 14)],
        [Paragraph('<font color="#666">_______________________</font>', BODY),
         Paragraph('<font color="#666">_______________________</font>', BODY)],
        [Paragraph("<b>Samuel Malick</b><br/>Founder &amp; CEO<br/>AI Advocate Ltd.", BODY),
         Paragraph(f"<b>{primary_contact}</b><br/>{firm_name}<br/>{firm_email}", BODY)],
        [Paragraph(f'<font color="#666">Date: {signed_date}</font>', BODY),
         Paragraph('<font color="#666">Date: __________________</font>', BODY)],
    ], colWidths=[82 * mm, 82 * mm])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(sig_table)

    # ───── FOOTER ─────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        '<font color="#666">AI Advocate Ltd. · ICO Registration ZC158457 · '
        'firms@aiadvocate.co.uk · aiadvocate.co.uk<br/>'
        'This agreement supersedes any prior verbal or written commitments. Governed by the laws of England &amp; Wales. '
        'Disputes subject to the exclusive jurisdiction of the courts of England &amp; Wales.</font>',
        SMALL,
    ))

    # Bottom gold bar
    story.append(Spacer(1, 6))
    bar2 = Table([[""]], colWidths=[166 * mm], rowHeights=[2 * mm])
    bar2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GOLD)]))
    story.append(bar2)

    doc.build(story)
    print(f"✓ Founding Firm Agreement generated: {OUTPUT}")
    print(f"  Size: {os.path.getsize(OUTPUT):,} bytes")
    print(f"  Personalised for: {firm_name}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--firm-name", default="[FIRM NAME]")
    p.add_argument("--sra", default="[SRA NUMBER]")
    p.add_argument("--address", default="[FIRM ADDRESS]")
    p.add_argument("--contact", default="[PRIMARY CONTACT NAME, JOB TITLE]")
    p.add_argument("--email", default="[FIRM EMAIL]")
    p.add_argument("--date", default=None)
    args = p.parse_args()
    build(firm_name=args.firm_name, sra_number=args.sra,
          firm_address=args.address, primary_contact=args.contact,
          firm_email=args.email, signed_date=args.date)
