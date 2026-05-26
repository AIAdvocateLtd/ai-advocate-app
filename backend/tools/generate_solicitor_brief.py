"""
Generates the Solicitor Brief PDF for AI Advocate.

The PDF is a professional cover letter + scope-of-work brief that the founder
sends to a UK solicitor to commission a legal opinion on:
  (a) Terms of Service
  (b) Privacy Policy
  (c) DPIA (Data Protection Impact Assessment)
  (d) UPL (Unauthorised Practice of Law) compliance under the Legal Services Act 2007

Output: /app/memory/AI_Advocate_Solicitor_Brief.pdf

Run: python /app/backend/tools/generate_solicitor_brief.py
"""

import os
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)


OUTPUT_PATH = "/app/memory/AI_Advocate_Solicitor_Brief.pdf"

GOLD = HexColor("#b8860b")
DARK = HexColor("#1a1300")
GREY = HexColor("#555555")


def _styles():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=22, leading=26, textColor=DARK, spaceAfter=8, alignment=TA_LEFT,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=13, leading=18, textColor=GOLD, spaceBefore=14, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=11, leading=15, textColor=DARK, spaceBefore=10, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=10.5, leading=15, textColor=black, spaceAfter=8, alignment=TA_JUSTIFY,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9, leading=13, textColor=GREY, alignment=TA_LEFT,
        ),
        "eyebrow": ParagraphStyle(
            "eyebrow", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8.5, leading=11, textColor=GOLD, spaceAfter=2, alignment=TA_LEFT,
        ),
        "list": ParagraphStyle(
            "list", parent=base["BodyText"], fontName="Helvetica",
            fontSize=10.5, leading=15, textColor=black,
            leftIndent=14, bulletIndent=2, spaceAfter=4,
        ),
    }


def build_pdf():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    doc = SimpleDocTemplate(
        OUTPUT_PATH, pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title="AI Advocate — Solicitor Brief",
        author="AI Advocate Ltd.",
    )
    s = _styles()
    today = datetime.now(timezone.utc).strftime("%d %B %Y")
    flow = []

    # ---- Cover header ----
    flow.append(Paragraph("AI ADVOCATE LTD. · SOLICITOR BRIEF", s["eyebrow"]))
    flow.append(Paragraph("Pre-launch Legal Review &amp; Opinion Engagement", s["h1"]))
    flow.append(Spacer(1, 4))
    flow.append(Paragraph(f"<b>Date:</b> {today}", s["small"]))
    flow.append(Paragraph("<b>Prepared by:</b> AI Advocate Ltd. (the &ldquo;Client&rdquo;)", s["small"]))
    flow.append(Paragraph("<b>For the attention of:</b> Instructed UK Solicitor / Counsel", s["small"]))
    flow.append(Spacer(1, 14))

    # ---- 1. Introduction ----
    flow.append(Paragraph("1. About AI Advocate", s["h2"]))
    flow.append(Paragraph(
        "AI Advocate is a consumer-facing, multilingual UK legal-information application "
        "(&ldquo;a lawyer in your pocket&rdquo;) that combines a Claude-based AI legal assistant "
        "(&ldquo;Lex&rdquo;), evidence analysis, encrypted document vault, deadline tracking, "
        "emergency rights flows, and a directory of UK regulated law firms. The app is sold "
        "as a subscription via Apple App Store, Google Play Store, and the web with Stripe, "
        "and offers a free tier. It is intended to launch in the United Kingdom under the "
        "domain <b>aiadvocate.co.uk</b>.",
        s["body"],
    ))
    flow.append(Paragraph(
        "We are pre-launch and are instructing you to perform a formal legal review of "
        "our consumer-facing documents and confirm regulatory compliance, prior to App "
        "Store submission. Time-sensitive: targeted launch within 4&ndash;6 weeks.",
        s["body"],
    ))

    # ---- 2. Documents enclosed ----
    flow.append(Paragraph("2. Documents enclosed for your review", s["h2"]))
    table_data = [
        ["#", "Document", "Path / URL"],
        ["1", "Terms of Service (v1.3)", "https://aiadvocate.co.uk/terms.html"],
        ["2", "Privacy Policy", "https://aiadvocate.co.uk/privacy.html"],
        ["3", "Data Protection Impact Assessment (DPIA)", "/app/memory/DPIA.md (attached as PDF)"],
        ["4", "Cookie Consent &amp; PECR notice", "In-app banner + privacy.html §Cookies"],
        ["5", "In-app UPL acknowledgement flow", "Screenshots attached (Lex first-use modal)"],
    ]
    t = Table(table_data, colWidths=[10 * mm, 70 * mm, 86 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f4ecd6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), DARK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 6))

    # ---- 3. Scope of work ----
    flow.append(Paragraph("3. Scope of work — what we need from you", s["h2"]))
    flow.append(Paragraph("We are instructing you to provide:", s["body"]))

    flow.append(Paragraph("(a) Legal Opinion Letter on the Terms of Service and Privacy Policy", s["h3"]))
    flow.append(Paragraph(
        "A signed written opinion confirming that the attached Terms of Service and Privacy Policy "
        "are fit for purpose under the laws of England and Wales, including but not limited to:",
        s["body"],
    ))
    for item in [
        "Consumer Rights Act 2015 (clarity, fairness of terms, no unfair contract terms under §62);",
        "Consumer Contracts (Information, Cancellation and Additional Charges) Regulations 2013 (14-day cooling-off period for distance contracts, currently reflected in §6);",
        "UK GDPR &amp; Data Protection Act 2018 (lawful bases, transparency, data subject rights, international transfer mechanisms);",
        "Privacy and Electronic Communications Regulations 2003 (PECR) — cookies, analytics, marketing communications;",
        "Electronic Commerce (EC Directive) Regulations 2002 — information society service requirements.",
    ]:
        flow.append(Paragraph(f"&bull; {item}", s["list"]))

    flow.append(Paragraph("(b) UPL &amp; Legal Services Act 2007 Compliance Confirmation", s["h3"]))
    flow.append(Paragraph(
        "A formal written confirmation that AI Advocate&rsquo;s positioning &mdash; as an "
        "<i>information</i> service rather than a <i>regulated legal advice</i> service &mdash; "
        "is sufficient to avoid being a &ldquo;reserved legal activity&rdquo; under section 12 "
        "of the Legal Services Act 2007. We rely on the following safeguards, which we ask you "
        "to specifically endorse or amend:",
        s["body"],
    ))
    for item in [
        "Persistent &ldquo;AI-generated legal information, not legal advice&rdquo; footer on every Lex chat surface;",
        "First-use UPL acknowledgement modal that the user must dismiss before using Lex (per-device);",
        "Explicit statement in Terms §1 and §3 that AI Advocate is not a solicitor and does not establish a solicitor-client relationship;",
        "In-app referral to a directory of <b>SRA-regulated</b> UK solicitors when the user&rsquo;s matter warrants regulated advice;",
        "Emergency SOS flow that explicitly states the app is not a replacement for 999/112/911 services.",
    ]:
        flow.append(Paragraph(f"&bull; {item}", s["list"]))

    flow.append(Paragraph("(c) DPIA sign-off (UK GDPR Article 35)", s["h3"]))
    flow.append(Paragraph(
        "Review of the enclosed Data Protection Impact Assessment and signature of "
        "<b>Section 8 &mdash; Sign-off</b>. We expect minor revisions; the document already covers "
        "lawful bases, special-category data, retention, international transfers, residual risks "
        "and mitigations. We are happy to action your comments and re-circulate.",
        s["body"],
    ))

    flow.append(Paragraph("(d) Recommended amendments (optional)", s["h3"]))
    flow.append(Paragraph(
        "Any drafting amendments you feel are necessary to the Terms, Privacy Policy, or DPIA. "
        "Please supply mark-up (PDF or Word redline) and we will incorporate before submission to "
        "Apple App Store and Google Play Console.",
        s["body"],
    ))

    flow.append(PageBreak())

    # ---- 4. Key facts you should know ----
    flow.append(Paragraph("4. Key facts about the service", s["h2"]))
    facts_data = [
        ["Topic", "Detail"],
        ["Jurisdiction served", "Primarily United Kingdom; multilingual (11 languages) but legal scope is UK-only."],
        ["Regulator (data)", "ICO &mdash; registration in progress prior to launch."],
        ["Data controller", "AI Advocate Ltd. (UK company)."],
        ["LLM provider", "Anthropic (Claude 4.5 Sonnet / Haiku / Opus) via UK/EU-hosted gateway; no user data used for model training (contractual)."],
        ["Encryption at rest", "AES-GCM client-side (Vault) + Fernet server-side envelope; AWS-style KMS-equivalent key management."],
        ["Special-category data", "Possible &mdash; legal matters can include health, sexuality, ethnicity. Lawful basis: <b>explicit consent</b> + <b>substantial public interest</b> (Schedule 1, Part 2 §6 DPA 2018)."],
        ["Children", "Strictly 18+. Age-gate at signup. Apple/Google rated 17+."],
        ["Payments", "Stripe (web), Apple IAP (iOS), Google Play Billing (Android). 7-day free trial then £19.99 / £34.99 monthly or £319.99 annual."],
        ["Subprocessors", "Anthropic, OpenAI (whisper/TTS only), Tavily (web search RAG), Stripe, MongoDB Atlas, Resend (if enabled), Sentry, PostHog."],
        ["UPL safeguards", "(i) Persistent in-chat disclaimer; (ii) first-use modal; (iii) referral to SRA-regulated solicitors; (iv) §1 &amp; §3 of Terms; (v) DPIA risk table row."],
    ]
    t2 = Table(facts_data, colWidths=[50 * mm, 116 * mm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f4ecd6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), DARK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.4, GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    flow.append(t2)

    # ---- 5. Timeline & fees ----
    flow.append(Paragraph("5. Timeline &amp; fee proposal", s["h2"]))
    flow.append(Paragraph(
        "Please provide your fixed-fee quotation for the scope at section 3. Indicative budget: "
        "<b>£500 &ndash; £1,500</b> based on quotes received from comparable boutique tech-law firms. "
        "We can engage on either an hourly or fixed-fee basis &mdash; whichever you prefer.",
        s["body"],
    ))
    flow.append(Paragraph(
        "Target turnaround: <b>14 calendar days</b> from the date you confirm engagement. "
        "We will treat sooner as a bonus; later as a hard blocker on App Store submission.",
        s["body"],
    ))

    # ---- 6. Deliverables we expect ----
    flow.append(Paragraph("6. Deliverables we expect", s["h2"]))
    for item in [
        "<b>Signed Legal Opinion Letter</b> (PDF, on your firm&rsquo;s letterhead) covering Sections 3(a) and 3(b) above.",
        "<b>Signed DPIA Section 8</b> &mdash; included in our PDF, returned signed.",
        "<b>Redline / mark-up</b> (PDF or .docx) of any amendments to Terms, Privacy, or DPIA.",
        "<b>Engagement letter</b> (your standard form) for our records.",
    ]:
        flow.append(Paragraph(f"&bull; {item}", s["list"]))

    # ---- 7. Contact ----
    flow.append(Paragraph("7. Contact &amp; next steps", s["h2"]))
    flow.append(Paragraph(
        "Please reply to <b>support@aiadvocate.co.uk</b> with: (i) confirmation you accept the "
        "engagement; (ii) your fee quotation; (iii) any clarifying questions. We will return your "
        "engagement letter signed by close of the next business day.",
        s["body"],
    ))
    flow.append(Paragraph(
        "We genuinely appreciate your time and look forward to working with you on what we hope "
        "will be a meaningful product for UK consumers needing affordable access to legal "
        "information.",
        s["body"],
    ))

    flow.append(Spacer(1, 24))
    flow.append(Paragraph("_______________________________", s["small"]))
    flow.append(Paragraph("For and on behalf of <b>AI Advocate Ltd.</b>", s["small"]))
    flow.append(Paragraph(f"Date: {today}", s["small"]))

    doc.build(flow)
    print(f"PDF written: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
