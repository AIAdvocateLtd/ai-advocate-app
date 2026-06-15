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
        # Special tight style used INSIDE table cells so long sentences wrap
        # cleanly instead of overflowing off the right edge of the page.
        "cell": ParagraphStyle(
            "cell", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.5, leading=11, textColor=black, alignment=TA_LEFT,
        ),
        "cell_head": ParagraphStyle(
            "cell_head", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8.5, leading=11, textColor=DARK, alignment=TA_LEFT,
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

    def P(text, style_name):
        return Paragraph(text, s[style_name])

    # ---- Cover header ----
    flow.append(P("AI ADVOCATE LTD. &middot; SOLICITOR BRIEF", "eyebrow"))
    flow.append(P("Pre-launch Legal Review &amp; Opinion Engagement", "h1"))
    flow.append(Spacer(1, 4))
    flow.append(P(f"<b>Date:</b> {today}", "small"))
    flow.append(P("<b>Prepared by:</b> AI Advocate Ltd. (the &ldquo;Client&rdquo;)", "small"))
    flow.append(P("<b>For the attention of:</b> Instructed UK Solicitor / Counsel", "small"))
    flow.append(Spacer(1, 14))

    # ---- 1. Introduction ----
    flow.append(P("1. About AI Advocate", "h2"))
    flow.append(P(
        "AI Advocate is a consumer-facing, multilingual UK legal-information application "
        "(&ldquo;a lawyer in your pocket&rdquo;) that combines a tiered-LLM AI legal assistant "
        "(&ldquo;Lex&rdquo; &mdash; Claude Haiku on Free, GPT-5.2 on Plus, Claude Sonnet on Pro), "
        "evidence analysis, encrypted document vault, deadline tracking, emergency rights "
        "flows, and a directory of UK regulated law firms. The app is sold as a subscription "
        "via Apple App Store, Google Play Store, and the web with Stripe, and offers a free "
        "tier. It is intended to launch in the United Kingdom under the domain "
        "<b>aiadvocate.co.uk</b>.",
        "body",
    ))
    flow.append(P(
        "Since the previous draft of this brief (May 2025) the product has expanded in five "
        "ways that materially affect the UPL analysis below and should be specifically "
        "endorsed in your opinion:",
        "body",
    ))
    for item in [
        "<b>Universal Document Upload (&#128206;)</b> &mdash; users may attach photographs, "
        "PDFs, or Word documents (5 pages/day Free, 25/day Plus, 100/day Pro) to a Lex chat. "
        "The text is extracted (OCR via Gemini Nano Banana for images, <i>pypdf</i>/<i>docx2txt</i> "
        "for text formats) and fed into the model&rsquo;s context window. The user retains the "
        "uploaded file in their encrypted Vault.",
        "<b>Letter Reader / Counter Letter / &ldquo;Send by email&rdquo; flow</b> &mdash; "
        "when a user uploads a solicitor letter, debt demand, parking ticket, eviction notice, "
        "etc., Lex returns (i) a plain-English summary, (ii) a draft response letter, "
        "(iii) a counter-letter outcome ladder. The user may then tap &ldquo;Send by email&rdquo;, "
        "which opens their device&rsquo;s default mail client (<i>mailto:</i>) with the draft "
        "pre-filled. <b>AI Advocate does not dispatch communications on the user&rsquo;s "
        "behalf, does not retain the recipient address, and does not represent the user "
        "in any capacity.</b>",
        "<b>Predict Outcome / Devil&rsquo;s Advocate / &ldquo;What happens if I do nothing?&rdquo;</b> "
        "&mdash; three predictive features that model the user&rsquo;s case against UK precedents, "
        "simulate opposing counsel&rsquo;s arguments, and project the consequences of inaction. "
        "All outputs are framed as <i>general legal information modelled against published "
        "precedent</i>, never as advice or representation, and every output carries the standard "
        "footer disclaimer.",
        "<b>&pound;49 Solicitor Sanity Check (human-in-the-loop)</b> &mdash; the most "
        "material UPL-safeguard mechanism in the product. For &pound;49 the user can request "
        "that an <b>SRA-regulated UK solicitor</b> reviews Lex&rsquo;s drafted response or "
        "case analysis within 24 hours. The reviewing solicitor (a) confirms accuracy, "
        "(b) edits where needed, (c) accepts professional accountability for the reviewed "
        "output. This is a one-off purchase (not a subscription tier) accessible from "
        "Letter Reader, Case Files, and the Lex chat interface. <b>This mechanism converts "
        "AI Advocate from a pure AI-information product into a hybrid AI-triage / "
        "human-counsel product on demand, and we would specifically like your opinion "
        "endorsing it as a UPL-compliant escalation path.</b>",
        "<b>One-off Doc Pack top-up (&pound;4.99)</b> &mdash; consumable Stripe purchase "
        "granting 5 additional document analyses; does not change the underlying UPL "
        "posture but is a new payment surface.",
        "<b>Charity partnership model (in active outreach: Citizens Advice, Shelter, "
        "StepChange, AdviceUK, Turn2us)</b> &mdash; AI Advocate routes signposted users via "
        "co-branded landing pages and donates 10% of net subscription revenue from "
        "referred users back to the originating charity as unrestricted income. This "
        "model is contractual (per-charity MoU) and does not change the user&rsquo;s "
        "relationship with AI Advocate; it is a B2B revenue-share, not an "
        "advice-provision arrangement.",
    ]:
        flow.append(Paragraph(f"&bull; {item}", s["list"]))
    flow.append(P(
        "We are pre-launch (web live; iOS/Android Capacitor builds in submission) and are "
        "instructing you to perform a formal legal review of our consumer-facing documents "
        "and confirm regulatory compliance. Time-sensitive: targeted App Store / Play Store "
        "submission within 4&ndash;6 weeks.",
        "body",
    ))

    # ---- 2. Documents enclosed ----
    flow.append(P("2. Documents enclosed for your review", "h2"))
    # All cells wrapped in Paragraph so long URLs / labels word-wrap inside the cell.
    table_data = [
        [P("#", "cell_head"), P("Document", "cell_head"), P("Path / URL", "cell_head")],
        [P("1", "cell"), P("Terms of Service (v1.3)", "cell"), P("https://aiadvocate.co.uk/terms.html", "cell")],
        [P("2", "cell"), P("Privacy Policy", "cell"), P("https://aiadvocate.co.uk/privacy.html", "cell")],
        [P("3", "cell"), P("Data Protection Impact Assessment (DPIA)", "cell"), P("/app/memory/DPIA.md (attached as PDF)", "cell")],
        [P("4", "cell"), P("Cookie Consent &amp; PECR notice", "cell"), P("In-app banner + privacy.html &sect;Cookies", "cell")],
        [P("5", "cell"), P("In-app UPL acknowledgement flow", "cell"), P("Screenshots attached (Lex first-use modal)", "cell")],
    ]
    t = Table(table_data, colWidths=[10 * mm, 70 * mm, 86 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f4ecd6")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 6))

    # ---- 3. Scope of work ----
    flow.append(P("3. Scope of work — what we need from you", "h2"))
    flow.append(P("We are instructing you to provide:", "body"))

    flow.append(P("(a) Legal Opinion Letter on the Terms of Service and Privacy Policy", "h3"))
    flow.append(P(
        "A signed written opinion confirming that the attached Terms of Service and Privacy Policy "
        "are fit for purpose under the laws of England and Wales, including but not limited to:",
        "body",
    ))
    for item in [
        "Consumer Rights Act 2015 (clarity, fairness of terms, no unfair contract terms under &sect;62);",
        "Consumer Contracts (Information, Cancellation and Additional Charges) Regulations 2013 (14-day cooling-off period for distance contracts, currently reflected in &sect;6);",
        "UK GDPR &amp; Data Protection Act 2018 (lawful bases, transparency, data subject rights, international transfer mechanisms);",
        "Privacy and Electronic Communications Regulations 2003 (PECR) &mdash; cookies, analytics, marketing communications;",
        "Electronic Commerce (EC Directive) Regulations 2002 &mdash; information society service requirements.",
    ]:
        flow.append(Paragraph(f"&bull; {item}", s["list"]))

    flow.append(P("(b) UPL &amp; Legal Services Act 2007 Compliance Confirmation", "h3"))
    flow.append(P(
        "A formal written confirmation that AI Advocate&rsquo;s positioning &mdash; as an "
        "<i>information</i> service rather than a <i>regulated legal advice</i> service &mdash; "
        "is sufficient to avoid being a &ldquo;reserved legal activity&rdquo; under section 12 "
        "of the Legal Services Act 2007. We rely on the following safeguards, which we ask you "
        "to specifically endorse or amend:",
        "body",
    ))
    for item in [
        "Persistent &ldquo;AI-generated legal information, not legal advice&rdquo; footer on every Lex chat surface;",
        "First-use UPL acknowledgement modal that the user must dismiss before using Lex (per-device);",
        "Explicit statement in Terms &sect;1 and &sect;3 that AI Advocate is not a solicitor and does not establish a solicitor-client relationship;",
        "In-app referral to a directory of <b>SRA-regulated</b> UK solicitors when the user&rsquo;s matter warrants regulated advice;",
        "<b>&pound;49 Solicitor Sanity Check escalation</b> &mdash; on-demand human-in-the-loop "
        "review by an SRA-regulated UK solicitor for any Lex-drafted response. The reviewing "
        "solicitor accepts professional accountability for the reviewed output. We consider "
        "this the strongest single UPL safeguard in the product.",
        "Emergency SOS flow that explicitly states the app is not a replacement for 999/112/911 services;",
        "<b>Document analysis &amp; drafted replies are framed as user-authored:</b> the &ldquo;Send by email&rdquo; button opens the user&rsquo;s own mail client with the draft pre-filled, requiring the user to add the recipient address and press <i>Send</i>. AI Advocate never dispatches, receives, or relays correspondence on the user&rsquo;s behalf, and has no agency or apparent authority to represent the user.",
    ]:
        flow.append(Paragraph(f"&bull; {item}", s["list"]))

    flow.append(P("(c) DPIA sign-off (UK GDPR Article 35)", "h3"))
    flow.append(P(
        "Review of the enclosed Data Protection Impact Assessment and signature of "
        "<b>Section 8 &mdash; Sign-off</b>. We expect minor revisions; the document already covers "
        "lawful bases, special-category data, retention, international transfers, residual risks "
        "and mitigations. We are happy to action your comments and re-circulate.",
        "body",
    ))

    flow.append(P("(d) Recommended amendments (optional)", "h3"))
    flow.append(P(
        "Any drafting amendments you feel are necessary to the Terms, Privacy Policy, or DPIA. "
        "Please supply mark-up (PDF or Word redline) and we will incorporate before submission to "
        "Apple App Store and Google Play Console.",
        "body",
    ))

    flow.append(PageBreak())

    # ---- 4. Key facts ----
    flow.append(P("4. Key facts about the service", "h2"))
    # Each "Detail" cell is wrapped in Paragraph("cell") so the text wraps inside
    # the column instead of bleeding off the right edge of the page.
    facts_rows = [
        ("Jurisdiction served",
         "Primarily United Kingdom; multilingual (11 languages) but legal scope is UK-only."),
        ("Regulator (data)",
         "ICO &mdash; registration in progress prior to launch."),
        ("Data controller",
         "AI Advocate Ltd. (UK company)."),
        ("LLM provider",
         "Anthropic (Claude 4.5 Sonnet / Haiku / Opus) via UK/EU-hosted gateway; "
         "no user data used for model training (contractual)."),
        ("Encryption at rest",
         "AES-GCM client-side (Vault) + Fernet server-side envelope; "
         "AWS-style KMS-equivalent key management."),
        ("Special-category data",
         "Possible &mdash; legal matters can include health, sexuality, ethnicity. "
         "Lawful basis: <b>explicit consent</b> + <b>substantial public interest</b> "
         "(Schedule 1, Part 2 &sect;6 DPA 2018)."),
        ("Children",
         "Strictly 18+. Age-gate at signup. Apple/Google rated 17+."),
        ("Payments",
         "Stripe (web), Apple IAP (iOS), Google Play Billing (Android). "
         "7-day free trial then &pound;19.99 / &pound;34.99 monthly or &pound;319.99 annual."),
        ("Subprocessors",
         "Anthropic, OpenAI (whisper/TTS only), Google Gemini (image OCR via Nano Banana), "
         "Tavily (web search RAG), Stripe, MongoDB Atlas, Resend, Sentry, PostHog "
         "(GDPR-managed: user-initiated analytics deletion endpoint live)."),
        ("UPL safeguards",
         "(i) Persistent in-chat disclaimer; (ii) first-use modal; "
         "(iii) referral to SRA-regulated solicitors; (iv) &sect;1 &amp; &sect;3 of Terms; "
         "(v) DPIA risk table row; (vi) drafted replies dispatched only by the user via "
         "their own mail client (mailto:)."),
        ("Document upload",
         "User-attached images / PDFs / Word files; OCR&rsquo;d and fed into the LLM "
         "context window. Limits: 5 pages/day Free, 25/day Plus, 100/day Pro. "
         "Files stored encrypted in user-owned Vault; can be deleted on demand. "
         "Per-account &pound;4.99 Doc Pack top-up available (consumable)."),
        ("Drafted communications",
         "Lex generates a draft response letter; user reviews on-device, then "
         "either copies the text or taps &ldquo;Send by email&rdquo; which opens "
         "<i>their own</i> mail client pre-filled. AI Advocate does not transmit "
         "or store outbound correspondence."),
        ("Solicitor Sanity Check",
         "Optional &pound;49 on-demand human review by an SRA-regulated UK solicitor "
         "of any Lex-drafted response. Reviewing solicitor accepts professional "
         "accountability for the output. <b>Please specifically endorse this "
         "mechanism in your opinion as a UPL-compliant escalation path.</b>"),
        ("Predictive features",
         "Predict Outcome, Devil&rsquo;s Advocate, and &ldquo;What happens if I do nothing?&rdquo; "
         "simulator. All framed as general legal information modelled against "
         "published UK precedent; never as advice or representation."),
        ("Charity partnerships",
         "Active outreach to Citizens Advice, Shelter, StepChange, AdviceUK, "
         "Turn2us. Per-charity MoU includes co-branded landing pages, free "
         "7-day Pro trials for referred users, and 10% of net subscription "
         "revenue from converting referrals donated back as unrestricted "
         "charitable income. No data exchange; B2B revenue-share only."),
    ]
    facts_data = [[P("Topic", "cell_head"), P("Detail", "cell_head")]]
    for topic, detail in facts_rows:
        facts_data.append([P(topic, "cell"), P(detail, "cell")])

    t2 = Table(facts_data, colWidths=[50 * mm, 116 * mm], repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#f4ecd6")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    flow.append(t2)

    # ---- 5. Timeline (no fee proposal — solicitor is a personal contact, may
    # quote pro bono / mate's rate, and we don't want to anchor the conversation
    # around a number) ----
    flow.append(P("5. Timeline", "h2"))
    flow.append(P(
        "Target turnaround: <b>14 calendar days</b> from the date you confirm engagement. "
        "We will treat sooner as a bonus; later as a hard blocker on App Store submission. "
        "Happy to align on engagement terms (hourly, fixed, or otherwise) at your convenience.",
        "body",
    ))

    # ---- 6. Deliverables ----
    flow.append(P("6. Deliverables we expect", "h2"))
    for item in [
        "<b>Signed Legal Opinion Letter</b> (PDF, on your firm&rsquo;s letterhead) covering Sections 3(a) and 3(b) above.",
        "<b>Signed DPIA Section 8</b> &mdash; included in our PDF, returned signed.",
        "<b>Redline / mark-up</b> (PDF or .docx) of any amendments to Terms, Privacy, or DPIA.",
        "<b>Engagement letter</b> (your standard form) for our records.",
    ]:
        flow.append(Paragraph(f"&bull; {item}", s["list"]))

    # ---- 7. Contact ----
    flow.append(P("7. Contact &amp; next steps", "h2"))
    flow.append(P(
        "Please reply to <b>support@aiadvocate.co.uk</b> with: (i) confirmation you accept the "
        "engagement and (ii) any clarifying questions. We will return your engagement letter "
        "signed by close of the next business day.",
        "body",
    ))
    flow.append(P(
        "We genuinely appreciate your time and look forward to working with you on what we hope "
        "will be a meaningful product for UK consumers needing affordable access to legal "
        "information.",
        "body",
    ))

    flow.append(Spacer(1, 24))
    flow.append(P("_______________________________", "small"))
    flow.append(P("For and on behalf of <b>AI Advocate Ltd.</b>", "small"))
    flow.append(P(f"Date: {today}", "small"))

    doc.build(flow)
    print(f"PDF written: {OUTPUT_PATH}")


if __name__ == "__main__":
    build_pdf()
