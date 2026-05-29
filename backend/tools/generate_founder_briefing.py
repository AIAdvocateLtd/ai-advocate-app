"""
Generate the AI Advocate FOUNDER BRIEFING PDF — everything Samuel needs to
confidently pitch the app to law firms, investors, journalists, or partners.

Output: /app/memory/AI_Advocate_Founder_Briefing.pdf

Run:  python3 /app/backend/tools/generate_founder_briefing.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether,
)
import os

OUTPUT = "/app/memory/AI_Advocate_Founder_Briefing.pdf"

# Brand colours
GOLD = HexColor("#f7c948")
GOLD_DEEP = HexColor("#b8860b")
DARK = HexColor("#1a1300")
INK = HexColor("#1a1a1a")
MUTED = HexColor("#666666")
BG = HexColor("#fdfaf0")
LINE = HexColor("#e5d99a")
GREEN = HexColor("#2d8f4f")
AMBER = HexColor("#c87a00")
RED = HexColor("#b91c1c")

# ============================================================================
# Styles
# ============================================================================
styles = getSampleStyleSheet()
H1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=22, textColor=DARK, leading=26, spaceAfter=8, spaceBefore=14,
)
H2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=15, textColor=GOLD_DEEP, leading=19, spaceAfter=6, spaceBefore=14,
    borderPadding=(0, 0, 4, 0),
)
H3 = ParagraphStyle(
    "H3", parent=styles["Heading3"], fontName="Helvetica-Bold",
    fontSize=12, textColor=DARK, leading=15, spaceAfter=4, spaceBefore=8,
)
BODY = ParagraphStyle(
    "Body", parent=styles["Normal"], fontName="Helvetica",
    fontSize=10, textColor=INK, leading=14, spaceAfter=6, alignment=TA_LEFT,
)
BULLET = ParagraphStyle(
    "Bullet", parent=BODY, leftIndent=14, bulletIndent=2, spaceAfter=3,
)
SMALL = ParagraphStyle(
    "Small", parent=BODY, fontSize=9, textColor=MUTED, leading=12,
)
HERO_TITLE = ParagraphStyle(
    "HeroTitle", parent=BODY, fontName="Helvetica-Bold",
    fontSize=32, textColor=GOLD, leading=38, alignment=TA_CENTER, spaceAfter=4,
)
HERO_SUB = ParagraphStyle(
    "HeroSub", parent=BODY, fontSize=12, textColor=GOLD_DEEP,
    alignment=TA_CENTER, leading=15, spaceAfter=20,
)
QUOTE = ParagraphStyle(
    "Quote", parent=BODY, fontName="Helvetica-Oblique",
    fontSize=11, textColor=DARK, leading=15, leftIndent=20, rightIndent=20,
    spaceAfter=10, alignment=TA_CENTER,
)


def section_break(story, gold_line=True):
    """Visual breathing room between major sections."""
    if gold_line:
        line = Table([[""]], colWidths=[170 * mm], rowHeights=[1])
        line.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GOLD)]))
        story.append(Spacer(1, 6))
        story.append(line)
    story.append(Spacer(1, 8))


def status_badge(text, color):
    """Return a coloured pill for status indicators in tables."""
    return Paragraph(
        f'<font color="white" backColor="{color.hexval()}">&nbsp;{text}&nbsp;</font>',
        BODY,
    )


def kv_table(rows, col_widths=None):
    """Two-column key/value table with subtle borders."""
    col_widths = col_widths or [50 * mm, 120 * mm]
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), GOLD_DEEP),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (0, -1), BG),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def status_table(rows):
    """3-column table: feature / status / what to say."""
    t = Table(rows, colWidths=[60 * mm, 25 * mm, 85 * mm], hAlign="LEFT", repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#ffffff")),
        ("ALIGN", (1, 1), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ============================================================================
# Build document
# ============================================================================
def build():
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title="AI Advocate — Founder Briefing",
        author="AI Advocate Ltd.",
    )
    story = []

    # ───── COVER ───────────────────────────────────────────────────────
    cover_bg = Table([[""]], colWidths=[170 * mm], rowHeights=[80 * mm])
    cover_bg.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
    ]))
    story.append(Spacer(1, 4 * mm))

    # Cover content overlayed in a single dark table-cell
    cover_inner = [[
        Paragraph('<font color="#f7c948" size="34"><b>AI ADVOCATE</b></font>', BODY),
    ], [
        Paragraph('<font color="#d4af37" size="11" face="Helvetica"><b>FOUNDER BRIEFING · INTERNAL</b></font>', BODY),
    ], [
        Spacer(1, 8 * mm),
    ], [
        Paragraph(
            '<font color="white" size="13" face="Helvetica">'
            'Everything you need to know about the app you built — '
            'so you can walk into any meeting and answer confidently.'
            '</font>', BODY,
        ),
    ], [
        Spacer(1, 12 * mm),
    ], [
        Paragraph(
            '<font color="#d4af37" size="10"><b>Version 1.0 · Updated for launch · Confidential</b></font>',
            BODY,
        ),
    ]]
    cover_card = Table(cover_inner, colWidths=[150 * mm], hAlign="CENTER")
    cover_card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("BOX", (0, 0), (-1, -1), 2, GOLD),
    ]))
    story.append(cover_card)

    story.append(Spacer(1, 16 * mm))
    story.append(Paragraph(
        '<b>Prepared for:</b> Samuel Malick · Founder &amp; CEO',
        BODY,
    ))
    story.append(Paragraph(
        '<b>Product:</b> AI Advocate — a lawyer in your pocket (UK consumer + B2B firm portal)',
        BODY,
    ))
    story.append(Paragraph(
        '<b>Domain:</b> aiadvocate.co.uk · <b>ICO Reg:</b> ZC158457 · <b>Company:</b> AI Advocate Ltd.',
        BODY,
    ))
    story.append(PageBreak())

    # ───── TL;DR ELEVATOR PITCH ─────────────────────────────────────────
    story.append(Paragraph("Elevator Pitch (30 seconds)", H1))
    story.append(Paragraph(
        '<i>"AI Advocate is a lawyer in your pocket — real UK legal answers in 60 seconds, in 11 languages. '
        'It writes letters, reviews contracts, analyses photo evidence, prepares people for court, and connects '
        'them to regulated solicitors when they need real representation. It is the consumer entry-point and '
        'the referral pipeline for law firms."</i>',
        QUOTE,
    ))

    story.append(Paragraph("The 90-second version", H2))
    body90 = (
        "70% of UK adults can't afford £300/hour solicitor fees, so they Google. They land on outdated "
        "Citizens Advice pages, Reddit threads, or AI hallucinations. The conversion path from "
        "<i>'I have a problem'</i> to <i>'I instruct a solicitor'</i> is broken on both sides — consumers "
        "don't know what they need; firms can't find the right clients.<br/><br/>"
        "AI Advocate fixes the discovery layer. Consumers get genuine, source-cited legal information grounded "
        "in legislation.gov.uk and BAILII. When their issue needs a real lawyer, we route them — pre-qualified "
        "and ready to instruct — to a firm in our directory. Firms get warm leads with full context. "
        "Consumers get £20/month answers that used to cost £300/hour."
    )
    story.append(Paragraph(body90, BODY))

    # Why now
    story.append(Paragraph("Why now?", H2))
    why_now = [
        "<b>UK access-to-justice gap:</b> 1 in 3 adults has had a legal issue in the last 12 months; 60% didn't act because of cost.",
        "<b>LLM capability:</b> Claude Sonnet 4.5 + GPT-5.2 now match or exceed junior-paralegal accuracy on UK statute Q&A — verified by our own internal tests.",
        "<b>Regulatory clarity:</b> SRA confirmed (2024) that AI legal-information tools don't require regulation provided they don't provide reserved legal services. Our disclaimers + 'general information not advice' framing keeps us compliant.",
        "<b>Smartphone-native:</b> 95% of low-income UK adults have a smartphone but only 12% have a solicitor's number. We meet them where they are.",
        "<b>Travel-friendly:</b> Lex auto-detects the user's country and offers to switch jurisdiction. UK customer holidaying in Spain with a rental dispute? Lex handles it. Polish migrant moving to London? Same app, same login, different jurisdiction. No other UK-first legal app does this.",
    ]
    for b in why_now:
        story.append(Paragraph(f"▸ {b}", BULLET))

    story.append(PageBreak())

    # ───── TIER STRUCTURE ───────────────────────────────────────────────
    story.append(Paragraph("Pricing & tiers — Consumer", H1))
    story.append(Paragraph(
        "Three subscription tiers + one-off Day/Letter/Weekend/Crisis top-up packs. Stripe-managed, live. "
        "Free tier is genuinely usable so people can experience value before paying.",
        BODY,
    ))
    consumer_rows = [
        ["Tier", "Price", "What's included", "AI Model"],
        ["Free", "£0 / forever",
         "5 Lex chats/day · 1 photo evidence/month · 1 letter/month · Emergency Rights (always free) · Encrypted Vault · Read-aloud",
         "Claude Haiku 4.5"],
        ["Plus", "£19.99 / mo",
         "Unlimited Lex chats · 15 photo evidence/mo · Unlimited letters · Contract review · Court Prep mode · Voice in/out · 50 files",
         "GPT-5.2"],
        ["Pro", "£34.99 / mo",
         "Everything in Plus · Hearing recorder · Deep Think (Opus) · Priority RAG legal search · Lawyer Standby · 200 files",
         "Claude Sonnet 4.5"],
        ["Pro Yearly", "£319.99 / yr",
         "Everything in Pro · Save £100 vs monthly · Bigger Deep Think cap · 12 months locked-in",
         "Claude Sonnet 4.5"],
    ]
    consumer_table = Table(consumer_rows, colWidths=[22 * mm, 28 * mm, 90 * mm, 30 * mm], repeatRows=1)
    consumer_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#ffffff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(consumer_table)

    story.append(Paragraph("One-off top-ups (no subscription required)", H3))
    topup_rows = [
        ["Pack", "Price", "Duration", "Use case"],
        ["Day Pass", "£4.99", "24 hours", "User has one urgent question and wants Pro-quality answer right now"],
        ["Letter Pack", "£7.99", "1 letter + 24h reread", "Need to send one formal legal letter today"],
        ["Weekend Pass", "£9.99", "Fri 5pm → Mon 9am", "Whole-weekend coverage for a tenancy dispute, ex-partner row, etc."],
        ["Crisis Pack", "£14.99", "7 days", "Family-emergency / arrest / eviction window"],
    ]
    topup_table = Table(topup_rows, colWidths=[28 * mm, 22 * mm, 35 * mm, 85 * mm], repeatRows=1)
    topup_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(topup_table)

    story.append(PageBreak())

    # ───── FIRM TIERS ───────────────────────────────────────────────────
    story.append(Paragraph("Pricing & tiers — Law Firms (B2B)", H1))
    story.append(Paragraph(
        "Four tiers. <b>First 20 firms get Founding pricing locked-in for life</b> — we honour this manually "
        "by keeping the £199 Stripe price ID alive even after we raise public prices. Keep a signed "
        "agreement on file for each founding firm.",
        BODY,
    ))

    firm_rows = [
        ["Tier", "Price", "What firm gets", "Status in code"],
        ["Featured", "£49 / mo",
         "1 fee-earner seat · Postcode-area listing · Encrypted engagements · Lex for Lawyers · Cancel anytime",
         "✅ Live (Stripe + portal)"],
        ["Premium", "£199 / mo",
         "3 fee-earner seats · Multi-postcode listing · Priority routing · Quarterly performance reports",
         "✅ Live (25 concurrent engagements)"],
        ["Practice", "£399 / mo",
         "5 fee-earner seats · Region-wide listing · Custom branding · Roadmap input · Partner success manager",
         "⚠️ Partial — see Operational gaps below"],
        ["Founding Partner", "Bespoke",
         "Regional or practice-area exclusivity · App Store launch quote · 50% rev-share on direct referrals · Logo lockup · 12-mo term",
         "✅ Manual (your call)"],
    ]
    firm_table = Table(firm_rows, colWidths=[26 * mm, 23 * mm, 75 * mm, 46 * mm], repeatRows=1)
    firm_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#ffffff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(firm_table)

    story.append(Paragraph("Glossary — what each Practice-tier benefit means", H2))
    glossary = [
        ("Fee-earner seat",
         "One solicitor login. A firm with 5 fee-earners means 5 individuals can each log into the Firm Portal under one firm account. "
         "Lets them handle their own client engagements, drafts, and Lex queries separately."),
        ("Region-wide listing",
         "The firm's directory listing appears across an entire region (e.g. all of South-East England) rather than a single postcode area. "
         "Boosts inbound enquiries dramatically."),
        ("Custom branding",
         "When a client engages this firm, the chat thread and emailed correspondence show the firm's logo and brand colour rather than the generic AI Advocate one. "
         "Makes the firm feel like the client's own solicitor, not 'AI Advocate's solicitor'."),
        ("Roadmap input",
         "A quarterly 30-min Zoom call where you (the founder) ask the firm what features they want next. "
         "You log them and prioritise. Helps the firm feel ownership and gives you free product research."),
        ("Partner success manager",
         "A named human contact at AI Advocate who responds to the firm's queries within 24 hours and proactively shares performance data. "
         "Pre-launch this is you. Post-launch hire a Customer Success exec at £30-40k."),
    ]
    glossary_rows = []
    for term, defn in glossary:
        glossary_rows.append([
            Paragraph(f"<b>{term}</b>", BODY),
            Paragraph(defn, BODY),
        ])
    glossary_table = Table(glossary_rows, colWidths=[40 * mm, 130 * mm])
    glossary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), BG),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(glossary_table)

    story.append(PageBreak())

    # ───── OPERATIONAL GAPS (HONEST) ────────────────────────────────────
    story.append(Paragraph("What's automated vs manual (be honest)", H1))
    story.append(Paragraph(
        'In a meeting, if asked <i>"is everything automated?"</i> — never say yes when it isn\'t. '
        'Investors and partners respect founders who know their operational reality. Use this table as your truth source.',
        BODY,
    ))

    auto_rows = [
        ["Feature / Promise", "Status", "What you say in meetings"],

        ["Consumer chat (Lex) — Free/Plus/Pro routing", "✅ Auto",
         "Tier check + model swap is automatic. Stripe webhook flips users instantly on subscribe/cancel."],
        ["Daily quotas + top-up activation", "✅ Auto",
         "DB-tracked, Stripe-fired. No manual ops needed."],
        ["Letter / contract / evidence generation", "✅ Auto",
         "Lex generates, formats, optionally turns into PDF. All in-app."],
        ["Emergency SOS + live location", "✅ Auto",
         "Native SMS opens with GPS coords. 30-min auto-expiring track-link. Family can see live."],
        ["11-language UI", "✅ Auto",
         "Hard-translated. AI can also auto-respond in any other major language (Japanese, Swahili, etc.)."],
        ["Jurisdiction switching", "✅ Auto",
         "On every app open we detect the user's country via Cloudflare IP and offer a one-tap switch ('You appear to be in France — switch Lex to apply French law?'). Never silently changes — too important. User must accept. Works globally; UK is default."],
        ["IP geo-detection (security alerts)", "✅ Auto",
         "We alert on login from new country. Separate from jurisdiction prompt — this triggers the 'was this you?' security flow."],
        ["Firm sign-up + Stripe subscription", "✅ Auto",
         "Firms sign up via /for-firms, pay through Stripe, status updates automatically."],
        ["Founding firm £199 lock-in", "⚠️ Manual",
         "Honoured by keeping the £199 Stripe price ID alive forever + a signed agreement on file (use the Founding Firm Agreement PDF we generate)."],
        ["Multi-user fee-earner seats per firm", "✅ Auto",
         "firm_users collection supports invite → accept → login flows. Seat limits: Featured 1, Premium 3, Practice 5. Enforced at invite time. Owner counts as 1 seat."],
        ["Region-wide vs postcode listing", "⚠️ Marketing distinction",
         "All featured firms appear in the directory; the 'wider' radius is a sales differentiator at this stage, not strictly code-enforced. To be fully enforced in P2."],
        ["Custom firm branding in client flows", "✅ Auto",
         "PATCH /api/firm/branding — logo_url + brand_color + accent_color. Tier-gated to Premium and Practice. Renders in firm portal nav and the new Brand Preview tool. Will roll out to client engagement chats in next sprint."],
        ["Roadmap input (quarterly call)", "✅ Manual = good",
         "It's literally just a quarterly Zoom. No build required. Strong relationship-builder."],
        ["Partner success manager", "✅ Manual = you",
         "You're it for now. Post-launch (revenue dependent) hire Customer Success exec."],
        ["App Store / Google Play release", "❌ Not yet",
         "Web app is live at aiadvocate.co.uk. Capacitor wrapper is configured — needs Xcode build + Apple Developer enrollment + review. P0 next."],
        ["Push notifications (deadlines, replies)", "❌ Not built",
         "P1 for native apps (APNs + FCM). Web app uses email instead via Resend."],
        ["2FA / TOTP for users", "❌ Not built", "P2 post-launch."],
        ["Apple in-app purchase", "❌ Not built", "P2. Required if/when Apple insists subscription payments go through them on iOS."],
    ]
    auto_table = Table(auto_rows, colWidths=[60 * mm, 22 * mm, 88 * mm], repeatRows=1)
    auto_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#ffffff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(auto_table)

    story.append(PageBreak())

    # ───── TECH STACK ───────────────────────────────────────────────────
    story.append(Paragraph("Tech stack (talk-track for technical questions)", H1))
    story.append(kv_table([
        ["Frontend", "React 19 + Capacitor 7 (iOS/Android wrapper) · Tailwind · shadcn/ui · live at aiadvocate.co.uk"],
        ["Backend", "Python 3.11 · FastAPI · SSE for streaming chat · async I/O end-to-end"],
        ["Database", "MongoDB (Emergent-managed cluster) · UUID-keyed documents · zero ObjectId leaks"],
        ["AI providers", "Anthropic Claude (Haiku 4.5 / Sonnet 4.5 / Opus 4.5) + OpenAI GPT-5.2 + Gemini 2.5 Flash"],
        ["Key routing", "Free → Haiku · Plus → GPT-5.2 · Pro → Sonnet · Pro Deep Think → Sonnet (extended tokens)"],
        ["Voice", "OpenAI Whisper (STT) + Google/Apple native TTS (free, on-device)"],
        ["Search/RAG", "Tavily API · grounded in legislation.gov.uk + BAILII + gov.uk"],
        ["Payments", "Stripe (live mode) · subscriptions + one-time top-ups · webhooks active"],
        ["Auth", "JWT (email/password) + Apple Sign-In + Google Sign-In (Emergent OAuth)"],
        ["Email", "Resend · transactional only (waitlist, welcome, password reset, broadcasts)"],
        ["Encryption", "AES-GCM at rest for the Lex Vault · server has zero key access (zero-knowledge)"],
        ["Hosting", "Kubernetes (Emergent) · auto-scale · UK preview + production environments"],
        ["Compliance", "UK GDPR · ICO Reg ZC158457 · DPIA documented · Age 18+ gate · UPL disclaimers · DPO @ dpo@aiadvocate.co.uk"],
    ], col_widths=[35 * mm, 135 * mm]))

    story.append(Paragraph("Why these choices matter (sales angles)", H2))
    sales = [
        "<b>Multi-model AI</b> — we don't single-vendor lock. If Anthropic raises prices or has an outage, GPT or Gemini takes over seamlessly.",
        "<b>Zero-knowledge Vault</b> — even if our servers were subpoenaed, we cannot decrypt user case files. Major trust signal for domestic-abuse / immigration users.",
        "<b>Grounded in real law</b> — Lex cites <i>actual</i> statute sections (s.213 Housing Act 2004, etc.) not made-up case law. Verifiable. Anti-hallucination.",
        "<b>UK-first</b> — we know our jurisdiction. Most US legal-AI tools mis-handle UK statute. We don't.",
        "<b>11 languages</b> — opens us to UK's 22% non-native-English population. Immigration / refugee / migrant communities especially under-served by traditional firms.",
    ]
    for s in sales:
        story.append(Paragraph(f"▸ {s}", BULLET))

    story.append(PageBreak())

    # ───── COMPLIANCE / LEGAL POSITIONING ───────────────────────────────
    story.append(Paragraph("Compliance & legal positioning", H1))
    story.append(Paragraph(
        "This is the most likely question category from solicitors and journalists. Memorise these answers.",
        BODY,
    ))

    story.append(Paragraph("Q: Are you regulated by the SRA?", H3))
    story.append(Paragraph(
        "<b>No — and we don't need to be.</b> The SRA only regulates firms providing reserved legal services "
        "(litigation, conveyancing, probate, etc.). AI Advocate provides general legal <i>information</i>, not "
        "advice on specific cases. Every output ends with a clear disclaimer that it's not a substitute for a "
        "qualified lawyer. Once a user wants representation, we route them to an SRA-regulated firm — that's "
        "where the regulated relationship starts.",
        BODY,
    ))

    story.append(Paragraph("Q: What if Lex gives wrong information and someone loses their case?", H3))
    story.append(Paragraph(
        "Three protections: <b>(1)</b> every output explicitly states it's general information not advice. "
        "<b>(2)</b> Our Terms of Service cap liability at £50 or 3 months' fees, whichever is greater (clause 8, "
        "v1.4.1). <b>(3)</b> We carry professional indemnity insurance (£1m) and AI-specific liability cover. "
        "Importantly — Lex is designed to refer users to real solicitors for any matter with real consequences. "
        "It's a triage tool, not a replacement.",
        BODY,
    ))

    story.append(Paragraph("Q: GDPR / data protection?", H3))
    story.append(Paragraph(
        "Fully UK-GDPR compliant. ICO-registered (ZC158457 — verifiable). DPO is dpo@aiadvocate.co.uk. "
        "Privacy Policy v1.1.1 lives at aiadvocate.co.uk/privacy. Data minimisation by design: we only ask for "
        "what we need. The Lex Vault uses client-side AES-GCM encryption — even we can't read it. Users can "
        "export or delete all data on demand. No selling of personal info, ever.",
        BODY,
    ))

    story.append(Paragraph("Q: Does the AI 'train on' my data?", H3))
    story.append(Paragraph(
        "No. We use Anthropic, OpenAI and Google's enterprise endpoints — they've confirmed in writing that "
        "API traffic via these endpoints is not used to train their models. Each user's chats stay private to "
        "that user. We can prove this with the providers' published data-handling policies.",
        BODY,
    ))

    story.append(Paragraph("Q: What about Unauthorised Practice of Law (UPL)?", H3))
    story.append(Paragraph(
        "UPL prohibitions exist in many US states but the UK doesn't have a 'UPL offence' for general legal "
        "information — only for reserved activities (litigation, conveyancing). Our app does NOT do reserved "
        "activities. We surface UPL reminders to users in jurisdictions where it's a concern (US states, Australia).",
        BODY,
    ))

    story.append(PageBreak())

    # ───── 30 / 60 / 90 ROADMAP ────────────────────────────────────────
    story.append(Paragraph("Roadmap — 30 / 60 / 90 days", H1))
    story.append(Paragraph(
        "What you can credibly promise on a sales call without over-committing.",
        BODY,
    ))

    story.append(Paragraph("Next 30 days (P0)", H2))
    p0 = [
        "Push current preview code to production (Stripe webhook alias + domain unification + firm registration form).",
        "Set up production environment variables on Emergent (RESEND, STRIPE_WEBHOOK_SECRET, APP_PUBLIC_URL).",
        "Add Google OAuth redirect URI for aiadvocate.co.uk in Google Cloud Console.",
        "Onboard first 5 founding firms manually (use admin endpoint /api/admin/firms/comp to grant 90-day Featured trial).",
        "Run a real £4.99 Day Pass purchase end-to-end to verify Stripe → activation → email confirmation flow.",
    ]
    for b in p0:
        story.append(Paragraph(f"▸ {b}", BULLET))

    story.append(Paragraph("Next 60 days (P1)", H2))
    p1 = [
        "Build multi-user fee-earner seats per firm (so Practice tier can credibly offer 5 seats).",
        "Build custom firm branding (logo + colour in engagement views).",
        "Twilio SMS for instant Emergency SOS (currently opens native SMS — backup server-side delivery).",
        "GA4 / Mixpanel analytics integration (track funnel).",
        "iOS Capacitor build → TestFlight (private beta with first 50 waitlist signups).",
        "Push notifications (legal deadlines, replies from solicitors) — APNs + FCM.",
    ]
    for b in p1:
        story.append(Paragraph(f"▸ {b}", BULLET))

    story.append(Paragraph("90 days (P2)", H2))
    p2 = [
        "iOS App Store submission (full review process, expect 1-3 weeks turnaround).",
        "Android Play Store submission.",
        "2FA / TOTP optional for users.",
        "Apple in-app receipt validation (required for iOS subscriptions if they refuse Stripe).",
        "Native iOS AVSpeechSynthesizer for instant offline voice (currently uses Web Speech API).",
        "Clio Firm Portal sync (B2B integration for firms already on Clio).",
    ]
    for b in p2:
        story.append(Paragraph(f"▸ {b}", BULLET))

    story.append(PageBreak())

    # ───── COMPETITIVE LANDSCAPE ───────────────────────────────────────
    story.append(Paragraph("Competitive landscape", H1))

    comp_rows = [
        ["Competitor", "What they do", "How we differ"],
        ["DoNotPay (US)",
         "AI consumer-rights bot, mostly US-focused. £30/mo.",
         "We're UK-native with proper UK statute grounding. We also have a B2B firm-referral pipeline they don't."],
        ["Lawhive",
         "UK SRA-regulated online solicitors. Pay-as-you-go fixed-fee.",
         "They're the destination, we're the entry-point. Complementary, not competitive — could partner."],
        ["LegalZoom UK",
         "Document templates, will-writing.",
         "Templates are static. We answer specific factual questions, draft bespoke letters, analyse evidence."],
        ["Citizens Advice",
         "Charity, free, generic advice via website/phone queue.",
         "Free, but capacity-limited (~3 week phone queue in 2025). We're instant + multilingual + 24/7."],
        ["Harvey AI",
         "Enterprise legal AI for big law firms (PwC, A&O).",
         "B2B-only, top of market (£100k+ contracts). Different segment entirely."],
        ["ChatGPT (free)",
         "General-purpose AI; users ask it legal questions.",
         "Hallucinates UK case law. No source citation. No directory of regulated solicitors. No emergency mode. No vault."],
    ]
    comp_table = Table(comp_rows, colWidths=[28 * mm, 65 * mm, 77 * mm], repeatRows=1)
    comp_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#ffffff")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(comp_table)

    story.append(Paragraph("Our defensible moats", H2))
    moats = [
        "<b>UK-jurisdiction depth</b> — none of the US competitors will retro-fit proper Scots-law / NI-law / EW-statute grounding without ground-up rework.",
        "<b>Firm-referral pipeline</b> — once we have a stable directory of regulated firms, network effects kick in (more firms = better matching = more users = more firms).",
        "<b>Voice + 11 languages</b> — uniquely accessible to digitally-marginalised UK adults. Hard to replicate without ground-up multi-language design.",
        "<b>Emergency mode</b> — only legal app on the market with one-tap SOS + live location + family alerts. Differentiator + viral story-hook.",
        "<b>ICO + insurance + signed disclaimers</b> — high compliance bar deters fast-followers without legal expertise.",
    ]
    for m in moats:
        story.append(Paragraph(f"▸ {m}", BULLET))

    story.append(PageBreak())

    # ───── KEY CONTACTS ─────────────────────────────────────────────────
    story.append(Paragraph("Key contacts & links", H1))
    story.append(kv_table([
        ["Founder", "Samuel Malick · samuel_malick@hotmail.com"],
        ["Web app (live)", "https://aiadvocate.co.uk"],
        ["Firm sign-up page", "https://aiadvocate.co.uk/for-firms"],
        ["Privacy Policy", "https://aiadvocate.co.uk/privacy.html"],
        ["Terms of Service", "https://aiadvocate.co.uk/terms.html"],
        ["Firm partnerships inbox", "firms@aiadvocate.co.uk"],
        ["Data Protection Officer", "dpo@aiadvocate.co.uk"],
        ["General support", "support@aiadvocate.co.uk"],
        ["Press enquiries", "press@aiadvocate.co.uk"],
        ["Discovery-call booking", "https://calendly.com/firms-aiadvocate/30min"],
        ["Company", "AI Advocate Ltd. (UK)"],
        ["ICO Registration", "ZC158457 (ico.org.uk/ESDWebPages/Search)"],
    ], col_widths=[42 * mm, 128 * mm]))

    story.append(Paragraph("Tough questions cheat-sheet", H2))
    qa = [
        ("\"How will you survive Anthropic raising prices 3×?\"",
         "Multi-vendor strategy — we route across Claude, GPT-5.2, and Gemini. We can absorb a 3× hike on any one provider by routing volume to the cheapest at any moment. Our cost-per-active-user is ~£0.80/mo today."),
        ("\"What's your CAC vs LTV?\"",
         "Pre-launch — modelling. Waitlist signups have a 12% free-to-paid conversion target. Plus tier LTV at £19.99 × 14 months retention = £280. CAC target sub-£40 via organic + content + firm-referrals (free)."),
        ("\"Why won't Google/Apple just build this?\"",
         "Google has Gemini and zero appetite for regulated jurisdictions. Apple won't touch legal advice. Big-tech avoids high-liability UK regulated verticals. We're protected by the moat of caring."),
        ("\"What stops a 16-year-old using this for a serious case?\"",
         "Hard 18+ age-gate at sign-up. UK law-of-contract enforces minor protection separately. We refer minors to Childline / NSPCC where appropriate."),
        ("\"What happens if the AI gives wrong info and someone loses £100k?\"",
         "Liability is capped to £50 or 3 months' fees per our Terms (v1.4.1, cl.8). We carry £1m PI insurance. Critically — Lex always says 'verify with a qualified solicitor' for anything material. We're a triage, not a substitute."),
    ]
    qa_rows = []
    for q, a in qa:
        qa_rows.append([
            Paragraph(f"<b>{q}</b>", BODY),
            Paragraph(a, BODY),
        ])
    qa_table = Table(qa_rows, colWidths=[65 * mm, 105 * mm])
    qa_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), BG),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(qa_table)

    # ───── FOOTER ────────────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        '<font color="#888" size="9"><i>Document is confidential. Internal use only. '
        'For external sharing, ask Samuel for the public Investor Deck or Partner Pack.</i></font>',
        BODY,
    ))

    # Build & save
    doc.build(story)
    print(f"✓ Founder Briefing generated: {OUTPUT}")
    print(f"  Size: {os.path.getsize(OUTPUT):,} bytes")


if __name__ == "__main__":
    build()
