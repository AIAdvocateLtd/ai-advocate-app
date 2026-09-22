import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck, Lock, Globe, Sparkles, FileText, Scale, MessageCircle,
  Mic, Briefcase, Check, ChevronRight, Mail, MapPin, ExternalLink, KeyRound,
  Gavel, AlertTriangle, X
} from "lucide-react";

// Re-use icons + brand
const GOLD = "var(--gold)";
const LOGO = "/assets/logo-transparent.png";

// ====== Shared chrome ======
function MarketingHeader() {
  return (
    <header style={{ position: "sticky", top: 0, zIndex: 10, background: "rgba(0,0,0,0.85)", backdropFilter: "blur(10px)", borderBottom: "1px solid var(--line)" }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", padding: "14px 22px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Link to="/" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          <img src={LOGO} alt="AI Advocate" style={{ height: 36 }} />
          <span className="brand-font gold" style={{ fontSize: 17, letterSpacing: "0.05em" }}>AI ADVOCATE</span>
        </Link>
        <nav style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <Link to="/pricing" data-testid="nav-pricing" style={{ color: "var(--text-dim)", textDecoration: "none", fontSize: 13 }}>Pricing</Link>
          <Link to="/security" data-testid="nav-security" style={{ color: "var(--text-dim)", textDecoration: "none", fontSize: 13 }}>Security</Link>
          <Link to="/privacy" data-testid="nav-privacy" style={{ color: "var(--text-dim)", textDecoration: "none", fontSize: 13, display: "none" }}>Privacy</Link>
          <Link to="/app" data-testid="nav-open-app"
                style={{ background: "var(--gold)", color: "#1a1300", padding: "8px 16px", borderRadius: 10, fontSize: 13, fontWeight: 700, textDecoration: "none" }}>
            Sign in
          </Link>
        </nav>
      </div>
    </header>
  );
}

function MarketingFooter() {
  return (
    <footer style={{ borderTop: "1px solid var(--line)", padding: "30px 22px", marginTop: 60 }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 30 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <img src={LOGO} alt="AI Advocate" style={{ height: 28 }} />
            <span className="brand-font gold" style={{ fontSize: 14 }}>AI ADVOCATE</span>
          </div>
          <div style={{ fontSize: 11, color: "var(--text-dim)", lineHeight: 1.6 }}>
            Built in the UK<br />by a legal-tech founder.<br /><br />
            <strong>Not a substitute for a regulated solicitor.</strong>
          </div>
        </div>
        <div>
          <div style={{ color: GOLD, fontSize: 11, fontWeight: 700, textTransform: "uppercase", marginBottom: 10, letterSpacing: "0.05em" }}>Product</div>
          <ul style={{ listStyle: "none", padding: 0, fontSize: 13, lineHeight: 2 }}>
            <li><Link to="/" style={{ color: "var(--text-dim)", textDecoration: "none" }}>Features</Link></li>
            <li><Link to="/pricing" style={{ color: "var(--text-dim)", textDecoration: "none" }}>Pricing</Link></li>
            <li><Link to="/security" style={{ color: "var(--text-dim)", textDecoration: "none" }}>Security</Link></li>
            <li><Link to="/app" style={{ color: "var(--text-dim)", textDecoration: "none" }}>Open the app</Link></li>
          </ul>
        </div>
        <div>
          <div style={{ color: GOLD, fontSize: 11, fontWeight: 700, textTransform: "uppercase", marginBottom: 10, letterSpacing: "0.05em" }}>Legal</div>
          <ul style={{ listStyle: "none", padding: 0, fontSize: 13, lineHeight: 2 }}>
            <li><Link to="/terms" style={{ color: "var(--text-dim)", textDecoration: "none" }}>Terms of Service</Link></li>
            <li><Link to="/privacy" style={{ color: "var(--text-dim)", textDecoration: "none" }}>Privacy Policy</Link></li>
            <li><Link to="/contact" style={{ color: "var(--text-dim)", textDecoration: "none" }}>Contact</Link></li>
            <li><a href="https://ico.org.uk/make-a-complaint/" target="_blank" rel="noreferrer" style={{ color: "var(--text-dim)", textDecoration: "none" }}>ICO complaints ↗</a></li>
          </ul>
        </div>
        <div>
          <div style={{ color: GOLD, fontSize: 11, fontWeight: 700, textTransform: "uppercase", marginBottom: 10, letterSpacing: "0.05em" }}>Contact</div>
          <ul style={{ listStyle: "none", padding: 0, fontSize: 13, lineHeight: 2, color: "var(--text-dim)" }}>
            <li><a href="mailto:support@aiadvocate.co.uk" style={{ color: "var(--text-dim)", textDecoration: "none" }}>support@aiadvocate.co.uk</a></li>
            <li><a href="mailto:firms@aiadvocate.co.uk" style={{ color: "var(--text-dim)", textDecoration: "none" }}>firms@aiadvocate.co.uk</a></li>
            <li><a href="mailto:privacy@aiadvocate.co.uk" style={{ color: "var(--text-dim)", textDecoration: "none" }}>privacy@aiadvocate.co.uk</a></li>
            <li><a href="mailto:dpo@aiadvocate.co.uk" style={{ color: "var(--text-dim)", textDecoration: "none" }}>dpo@aiadvocate.co.uk</a></li>
          </ul>
        </div>
      </div>
      <div style={{ maxWidth: 1180, margin: "30px auto 0", paddingTop: 20, borderTop: "1px solid var(--line)", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 10, color: "var(--text-dim)", fontSize: 11 }}>
        <div>© {new Date().getFullYear()} AI Advocate. All rights reserved.</div>
        <div>Made with ⚖️ in the UK</div>
      </div>
    </footer>
  );
}

// ====== Landing page ======
export function MarketingLanding() {
  return (
    <div data-testid="marketing-landing" style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)" }}>
      <MarketingHeader />

      {/* HERO */}
      <section style={{ padding: "70px 22px 50px", textAlign: "center", maxWidth: 920, margin: "0 auto" }}>
        <div style={{ display: "inline-block", padding: "6px 14px", background: "rgba(247,201,72,0.1)", border: "1px solid var(--gold-deep)", borderRadius: 99, fontSize: 11, color: GOLD, marginBottom: 22, letterSpacing: "0.05em", textTransform: "uppercase" }}>
          ⚖️ Available on web &amp; iOS
        </div>
        <h1 className="brand-font gold" style={{ fontSize: "clamp(36px, 6vw, 64px)", lineHeight: 1.05, marginBottom: 14, letterSpacing: "0.02em" }}>
          Your lawyer<br />in your pocket
        </h1>
        <p style={{ fontSize: "clamp(15px, 2vw, 18px)", color: "var(--text-dim)", lineHeight: 1.6, marginBottom: 30, maxWidth: 620, margin: "0 auto 30px" }}>
          Real legal answers, document drafting, contract negotiation, evidence analysis and a zero-knowledge encrypted vault — all in 11 languages, all from £19.99 / month.
        </p>

        {/* CTA — App Store + Web (Google Play button removed to comply with Apple 2.3.10) */}
        <div data-testid="hero-ctas" style={{ display: "flex", flexWrap: "wrap", gap: 12, justifyContent: "center", marginBottom: 24 }}>
          <a href="#download-ios" data-testid="cta-ios"
             style={{ display: "inline-flex", alignItems: "center", gap: 10, padding: "13px 22px", background: "var(--gold)", color: "#1a1300", borderRadius: 12, textDecoration: "none", fontWeight: 700, fontSize: 14 }}>
            <span style={{ fontSize: 20 }}>🍎</span>
            <span style={{ textAlign: "left", lineHeight: 1.1 }}>
              <span style={{ display: "block", fontSize: 10, opacity: 0.7 }}>Download on the</span>
              App Store
            </span>
          </a>
          <Link to="/app" data-testid="cta-web"
                style={{ display: "inline-flex", alignItems: "center", gap: 10, padding: "13px 22px", background: "transparent", border: "1px solid var(--gold)", color: GOLD, borderRadius: 12, textDecoration: "none", fontWeight: 700, fontSize: 14 }}>
            <Globe size={18} /> Sign up on web
          </Link>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-dim)" }}>7-day free trial · Cancel anytime · No card required for Free tier</div>

        {/* Trust strip */}
        <div data-testid="trust-strip" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginTop: 50, padding: "16px", background: "rgba(247,201,72,0.04)", border: "1px solid var(--gold-deep)", borderRadius: 14 }}>
          {[
            { icon: ShieldCheck, label: "End-to-end encrypted" },
            { icon: KeyRound, label: "Zero-knowledge Vault" },
            { icon: Globe, label: "11 languages" },
            { icon: Lock, label: "GDPR / UK-GDPR" },
            { icon: Sparkles, label: "Built in the UK" },
          ].map(({ icon: Icon, label }, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "center", color: "var(--text-dim)", fontSize: 12 }}>
              <Icon size={16} style={{ color: GOLD }} /> {label}
            </div>
          ))}
        </div>
      </section>

      {/* WHAT LEX CAN DO */}
      <section style={{ padding: "40px 22px", maxWidth: 1180, margin: "0 auto" }}>
        <h2 className="brand-font gold" style={{ fontSize: "clamp(26px, 4vw, 40px)", textAlign: "center", marginBottom: 8 }}>What Lex can do for you</h2>
        <p style={{ textAlign: "center", color: "var(--text-dim)", marginBottom: 36, fontSize: 14 }}>Everything you'd ask a solicitor — without the £350/hour bill.</p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
          {[
            { Icon: MessageCircle, title: "Ask Lex anything", body: "Real legal answers in plain English for employment, property, immigration, family, consumer and medical matters." },
            { Icon: Gavel, title: "Contract Read, Draft & Negotiate", body: "Photograph any contract — Lex picks the bad clauses, drafts redlines, and writes a ready-to-send negotiation email." },
            { Icon: FileText, title: "Letter Auto-Responder", body: "Snap a legal letter and Lex drafts a professional response with the right tone, deadlines and statutory references." },
            { Icon: Scale, title: "Outcome Predictor", body: "Get a realistic % chance of success, similar past cases, and an honest assessment — powered by Opus Deep Think." },
            { Icon: Mic, title: "Hearing Recorder", body: "Capture permitted hearings, get full transcripts and Lex's review of what was said. With built-in court-recording safety guards." },
            { Icon: KeyRound, title: "Lex Vault", body: "End-to-end encrypted storage for evidence, contracts, ID documents. Even we can't read it. Face ID unlock." },
            { Icon: Briefcase, title: "Find a Lawyer", body: "Curated UK directory of regulated solicitors and law firms when Lex thinks you need real human counsel." },
            { Icon: AlertTriangle, title: "Emergency Mode", body: "One-tap 'know your rights' for stops, arrests, evictions, accidents — with offline access." },
          ].map(({ Icon, title, body }, i) => (
            <div key={i} style={{ padding: 18, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: "rgba(247,201,72,0.12)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 12 }}>
                <Icon size={18} style={{ color: GOLD }} />
              </div>
              <div style={{ color: GOLD, fontSize: 14, fontWeight: 700, marginBottom: 6 }}>{title}</div>
              <div style={{ color: "var(--text-dim)", fontSize: 12, lineHeight: 1.6 }}>{body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* PRIVACY MOAT */}
      <section style={{ padding: "60px 22px", background: "linear-gradient(180deg, rgba(247,201,72,0.04), transparent)" }}>
        <div style={{ maxWidth: 920, margin: "0 auto", textAlign: "center" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "6px 14px", background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.3)", borderRadius: 99, fontSize: 11, color: "#86efac", marginBottom: 18, letterSpacing: "0.05em", textTransform: "uppercase" }}>
            <ShieldCheck size={14} /> Privacy promise
          </div>
          <h2 className="brand-font gold" style={{ fontSize: "clamp(24px, 3.5vw, 36px)", marginBottom: 14 }}>
            We can't read your stuff.<br />And that's the point.
          </h2>
          <p style={{ color: "var(--text-dim)", fontSize: 14, lineHeight: 1.7, marginBottom: 26 }}>
            Your Lex chat messages are encrypted at rest with AES-128 + HMAC. Your Vault uses zero-knowledge AES-GCM-256 with a PIN only you know — derived through PBKDF2 with 250,000 iterations. Even if our database leaked, your sensitive documents would be useless ciphertext to the attacker.
          </p>
          <Link to="/security" data-testid="link-security" style={{ display: "inline-flex", alignItems: "center", gap: 6, color: GOLD, fontSize: 13, textDecoration: "none", fontWeight: 600 }}>
            Read our full security breakdown <ChevronRight size={14} />
          </Link>
        </div>
      </section>

      {/* PRICING TEASER */}
      <section style={{ padding: "60px 22px", maxWidth: 1180, margin: "0 auto" }}>
        <h2 className="brand-font gold" style={{ fontSize: "clamp(26px, 4vw, 40px)", textAlign: "center", marginBottom: 36 }}>Simple pricing</h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
          {[
            { name: "Free", price: "£0", period: "forever", highlight: false, bullets: ["Lex chat (limited)", "Letter & Contract reader", "Find a lawyer", "Emergency mode"] },
            { name: "Plus", price: "£19.99", period: "/ month", highlight: false, bullets: ["Everything in Free", "All category chats", "Courtroom practice", "Record legal interactions"] },
            { name: "Pro", price: "£34.99", period: "/ month", highlight: true, bullets: ["Outcome Predictor (Opus)", "Contract Drafter + Negotiate", "Hearing Recorder", "Vault — 200 items"] },
            { name: "Yearly Pro", price: "£319.99", period: "/ year", highlight: false, savings: "Save £100", bullets: ["Everything in Pro", "Bigger Deep Think cap", "12 months locked in"] },
          ].map((p, i) => (
            <div key={i} style={{ position: "relative", padding: 20, background: p.highlight ? "rgba(247,201,72,0.08)" : "var(--bg-card)", border: p.highlight ? "2px solid var(--gold)" : "1px solid var(--line)", borderRadius: 14 }}>
              {p.highlight && <div style={{ position: "absolute", top: -10, left: "50%", transform: "translateX(-50%)", background: "var(--gold)", color: "#1a1300", fontSize: 10, fontWeight: 800, padding: "3px 10px", borderRadius: 99, letterSpacing: "0.05em" }}>MOST POPULAR</div>}
              {p.savings && <div style={{ position: "absolute", top: -10, right: 10, background: "#22c55e", color: "#000", fontSize: 10, fontWeight: 800, padding: "3px 10px", borderRadius: 99 }}>{p.savings}</div>}
              <div style={{ color: GOLD, fontSize: 14, fontWeight: 700, marginBottom: 4 }}>{p.name}</div>
              <div style={{ marginBottom: 14 }}>
                <span style={{ fontSize: 32, color: "var(--text)", fontWeight: 700 }}>{p.price}</span>
                <span style={{ color: "var(--text-dim)", fontSize: 12, marginLeft: 6 }}>{p.period}</span>
              </div>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, color: "var(--text-dim)", fontSize: 12, lineHeight: 2 }}>
                {p.bullets.map((b, j) => (
                  <li key={j} style={{ display: "flex", gap: 6, alignItems: "flex-start" }}><Check size={14} style={{ color: GOLD, flexShrink: 0, marginTop: 3 }} /> {b}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div style={{ textAlign: "center", marginTop: 24 }}>
          <Link to="/pricing" style={{ color: "var(--text-dim)", fontSize: 13, textDecoration: "underline" }}>See full pricing details</Link>
        </div>
      </section>

      {/* FINAL CTA */}
      <section style={{ padding: "60px 22px", textAlign: "center", maxWidth: 720, margin: "0 auto" }}>
        <h2 className="brand-font gold" style={{ fontSize: "clamp(26px, 4vw, 38px)", marginBottom: 14 }}>
          Stop paying £350/hour to ask a question.
        </h2>
        <p style={{ color: "var(--text-dim)", marginBottom: 26, fontSize: 14, lineHeight: 1.6 }}>
          7-day free trial. No card needed for Free. Built in the UK for people who deserve a fair shot at the law.
        </p>
        <Link to="/app" data-testid="final-cta"
              style={{ display: "inline-block", padding: "14px 32px", background: "var(--gold)", color: "#1a1300", borderRadius: 12, textDecoration: "none", fontWeight: 700, fontSize: 15 }}>
          Get started — free
        </Link>
      </section>

      <MarketingFooter />
    </div>
  );
}

// ====== Static legal pages (re-use the in-app text but rendered publicly) ======
function StaticDocPage({ title, content, testid }) {
  return (
    <div data-testid={testid} style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)" }}>
      <MarketingHeader />
      <main style={{ maxWidth: 760, margin: "0 auto", padding: "40px 22px" }}>
        <h1 className="brand-font gold" style={{ fontSize: "clamp(28px, 5vw, 40px)", marginBottom: 30 }}>{title}</h1>
        <div style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.7, color: "var(--text)" }}>
          {content}
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}

export function TermsPage() {
  const TOS = `# Terms of Service

**AI Advocate** ("we", "us", "the App") provides AI-powered general legal information. By using the App, you agree to these terms.

**1. Not legal advice.** AI Advocate is an information service, NOT a regulated legal practice. The AI is not a solicitor, barrister, or qualified lawyer. Nothing in the App creates a solicitor-client relationship. For binding legal advice on your specific case, instruct a regulated solicitor (SRA in England & Wales; LSS in Scotland; LSNI in Northern Ireland; equivalent body in your country).

**2. Eligibility & age.** You must be 18 or older. By signing up, you confirm you are 18+.

**3. Accuracy.** We strive for accuracy but legal information can be wrong, out-of-date, or jurisdiction-specific. You bear the risk of acting on AI output. We are NOT liable for losses arising from reliance on AI responses.

**4. Recording features.** The App provides audio-recording features (Hearing Recorder, Record Legal Interaction). Recording laws vary by country and setting. You — not AI Advocate — are responsible for the legality of any recording you make. Recording in a courtroom is a criminal offence in the UK (Contempt of Court Act 1981 s.9) and most countries.

**5. Vault.** The Lex Vault uses end-to-end encryption with a PIN that only you know. If you lose your PIN, your vault items are PERMANENTLY UNRECOVERABLE. We do not hold a copy.

**6. Subscriptions, free trial & auto-renewal.** Free 7-day trial of paid features on signup. Paid plans renew automatically at £19.99/mo (Plus), £34.99/mo (Pro), or £319.99/yr (Yearly Pro). Cancel any time 24h before renewal. Refunds via the store that processed your payment (Apple/Google/Stripe).

**7. Misuse.** You may not use the App for: harassment, illegal recording, defamation, doxing, or building tools that compete with the App.

**8. Termination.** We may suspend accounts that violate these terms. You may delete your account at any time via Settings → Manage My Data.

**9. Limitation of liability.** To the maximum extent permitted by law, our total liability to you in any 12-month period is capped at the greater of (a) £100 or (b) the subscription fees you paid us in that period.

**10. Governing law.** These terms are governed by the laws of England & Wales. Disputes are subject to the exclusive jurisdiction of the English courts, unless your local consumer-protection law provides otherwise.

**11. Contact.** support@aiadvocate.co.uk

Last updated: 2026-02-18.`;
  return <StaticDocPage title="Terms of Service" content={TOS} testid="page-terms" />;
}

export function PrivacyPage() {
  const PRIVACY = `# Privacy Policy

**AI Advocate** is committed to protecting your privacy. This policy explains what data we collect, why, and your rights under UK-GDPR and EU-GDPR.

## What we collect
- **Account data**: email, name, password hash (bcrypt), country, language preference.
- **Usage data**: which features you use, error logs, anonymous analytics (if enabled).
- **Lex chat content**: your messages + Lex's responses. **Encrypted at rest** in our database using AES-128 + HMAC.
- **Case files**: titles, summaries, uploaded documents. Summaries encrypted at rest.
- **Vault items**: encrypted on YOUR device with your PIN. We cannot read them.
- **Recording features**: audio files you record are sent to OpenAI Whisper for transcription, then DELETED from our servers. Transcript text is kept in your case files.
- **Payment data**: handled entirely by Stripe (PCI-DSS Level 1). We never see your card number.

## Why we collect it
- To provide the legal-information service you signed up for (lawful basis: contract).
- To improve the product (lawful basis: legitimate interest, anonymised aggregates only).
- To comply with tax/legal record-keeping (lawful basis: legal obligation, retention 6 years).

## Third parties we share with
- **Anthropic** (Claude) — your messages are sent to Claude for processing. Anthropic does NOT train on Universal-Key API traffic.
- **OpenAI** — Whisper for audio transcription; data deleted after processing.
- **Google** — Gemini for vision/extraction of contracts/photos.
- **Stripe** — payment processing.
- **Apple / Google** — if you use their sign-in: name, email, sub identifier.
- We do NOT sell your data to advertisers or data brokers, ever.

## Your rights under GDPR / UK-GDPR
- **Access**: request a copy of all your data (Settings → Export My Data).
- **Erasure**: delete your account and all personal data (Settings → Delete My Account).
- **Rectification**: edit your profile.
- **Portability**: export as JSON.
- **Objection / restriction**: email support@aiadvocate.co.uk.
- **Complaint**: lodge a complaint with the ICO at ico.org.uk.

## Security
TLS 1.3 in transit. Bcrypt for passwords. Fernet (AES-128 + HMAC) for sensitive fields at rest. Vault uses client-side AES-GCM-256 with PIN-derived keys (PBKDF2 250k iterations).

## Children
The App is not for users under 18.

## Data retention
Active accounts: indefinitely while you remain a user. Deleted accounts: personal data permanently erased within 30 days (subscription/billing records anonymised after 6 years).

## International transfers
Our servers are in the EU. LLM processing may be in the US under Standard Contractual Clauses.

## Contact
For any privacy question: privacy@aiadvocate.co.uk
Data Protection Officer: dpo@aiadvocate.co.uk

Last updated: 2026-02-18.`;
  return <StaticDocPage title="Privacy Policy" content={PRIVACY} testid="page-privacy" />;
}

export function SecurityPage() {
  const SEC = `# Security

We treat security as a product feature, not an afterthought.

## Encryption in transit
All traffic is encrypted with TLS 1.3.

## Encryption at rest
- **Passwords** — bcrypt with 12 rounds + salt.
- **Lex chat messages** — Fernet (AES-128-CBC + HMAC-SHA256) before being written to our database. Even if our database leaked, an attacker would see ciphertext like \`enc:v1:gAAAA...\`.
- **Case summaries and notes** — same Fernet field-encryption.
- **Lex Vault** — TRIPLE layer: (1) client-side AES-GCM-256 with a PIN-derived key (PBKDF2 with 250,000 SHA-256 iterations), (2) server-side Fernet on top, (3) TLS in transit.

## Zero-knowledge Vault
Your Vault PIN never reaches our servers. We only store a SHA-256(PIN || salt) verifier hash. Without your PIN, your vault items are mathematically unreadable — even to us. If you forget your PIN, your items are permanently lost (we can't help — that's the point).

## Biometric unlock
After PIN setup, you can opt into Face ID / Touch ID / Windows Hello / Android biometric. The PIN is encrypted with a key derived from your device's platform-authenticator credential ID. Biometric mismatch = no decryption.

## Payments
Card data NEVER touches our servers. Stripe (PCI-DSS Level 1) handles all card storage and processing on our behalf.

## LLM providers
We use Anthropic Claude, Google Gemini and OpenAI Whisper via Emergent's Universal Key. Anthropic and OpenAI have confirmed they do NOT train on Universal Key API traffic.

## Reporting a vulnerability
If you find a security issue, please email security@aiadvocate.co.uk. We aim to acknowledge within 48 hours. We do not currently run a paid bug-bounty programme, but we will publicly credit responsible disclosures.

## Compliance
UK-GDPR / EU-GDPR. ICO registration in progress.

Last updated: 2026-02-18.`;
  return <StaticDocPage title="Security" content={SEC} testid="page-security" />;
}

export function PricingPage() {
  return (
    <div data-testid="page-pricing" style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)" }}>
      <MarketingHeader />
      <main style={{ maxWidth: 1180, margin: "0 auto", padding: "60px 22px" }}>
        <h1 className="brand-font gold" style={{ fontSize: "clamp(34px, 5vw, 52px)", textAlign: "center", marginBottom: 12 }}>Pricing</h1>
        <p style={{ textAlign: "center", color: "var(--text-dim)", marginBottom: 40, fontSize: 15 }}>One free tier. One affordable plan. One pro plan. Pay yearly to save £100.</p>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
          {[
            { name: "Free", price: "£0", period: "forever", highlight: false, bullets: ["Lex chat (3 / day)", "Letter reader (3 / month)", "Contract reader (2 / month)", "Snap evidence (3 / month)", "Find a lawyer & legal aid finder", "Emergency Mode (unlimited)", "Lex Vault (5 items)"] },
            { name: "Plus", price: "£19.99", period: "/ month", highlight: false, bullets: ["Everything in Free", "Unlimited Ask Lex", "All category chats (employment, property, immigration, medical, etc.)", "Courtroom practice mode", "Record legal interactions", "Lex Vault (25 items)"] },
            { name: "Pro", price: "£34.99", period: "/ month", highlight: true, bullets: ["Everything in Plus", "Outcome Predictor (Opus Deep Think)", "Contract Drafter + Contract Negotiate", "Live Hearing Recorder + transcription", "30 Deep Think reasoning queries / month", "Lex Vault (200 items)", "Priority AI processing"] },
            { name: "Yearly Pro", price: "£319.99", period: "/ year", highlight: false, savings: "Save £100", bullets: ["Everything in Pro", "50 Deep Think queries / month", "12 months locked in — no monthly faff", "Equivalent to £26.66 / month"] },
          ].map((p, i) => (
            <div key={i} style={{ position: "relative", padding: 22, background: p.highlight ? "rgba(247,201,72,0.08)" : "var(--bg-card)", border: p.highlight ? "2px solid var(--gold)" : "1px solid var(--line)", borderRadius: 14 }}>
              {p.highlight && <div style={{ position: "absolute", top: -10, left: "50%", transform: "translateX(-50%)", background: "var(--gold)", color: "#1a1300", fontSize: 10, fontWeight: 800, padding: "3px 10px", borderRadius: 99 }}>MOST POPULAR</div>}
              {p.savings && <div style={{ position: "absolute", top: -10, right: 10, background: "#22c55e", color: "#000", fontSize: 10, fontWeight: 800, padding: "3px 10px", borderRadius: 99 }}>{p.savings}</div>}
              <div style={{ color: GOLD, fontSize: 16, fontWeight: 700, marginBottom: 4 }}>{p.name}</div>
              <div style={{ marginBottom: 14 }}>
                <span style={{ fontSize: 36, color: "var(--text)", fontWeight: 700 }}>{p.price}</span>
                <span style={{ color: "var(--text-dim)", fontSize: 13, marginLeft: 6 }}>{p.period}</span>
              </div>
              <Link to="/app" style={{ display: "block", textAlign: "center", padding: "10px", background: p.highlight ? "var(--gold)" : "transparent", color: p.highlight ? "#1a1300" : GOLD, border: p.highlight ? "none" : "1px solid var(--gold)", borderRadius: 10, fontWeight: 700, fontSize: 13, textDecoration: "none", marginBottom: 14 }}>
                {p.name === "Free" ? "Sign up free" : "Start 7-day trial"}
              </Link>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, color: "var(--text-dim)", fontSize: 12, lineHeight: 1.9 }}>
                {p.bullets.map((b, j) => (
                  <li key={j} style={{ display: "flex", gap: 6, alignItems: "flex-start" }}><Check size={13} style={{ color: GOLD, flexShrink: 0, marginTop: 4 }} /> {b}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 50, padding: 20, background: "rgba(247,201,72,0.04)", border: "1px solid var(--gold-deep)", borderRadius: 14, fontSize: 13, color: "var(--text-dim)", lineHeight: 1.7 }}>
          <strong style={{ color: GOLD }}>Fair pricing promise.</strong> No hidden fees. No usage-based surcharges. Cancel anytime 24h before renewal. Refunds handled by the store that processed your payment. 7-day free trial available once per account. UK VAT included where applicable.
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}

export function ContactPage() {
  return (
    <div data-testid="page-contact" style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)" }}>
      <MarketingHeader />
      <main style={{ maxWidth: 720, margin: "0 auto", padding: "60px 22px" }}>
        <h1 className="brand-font gold" style={{ fontSize: "clamp(30px, 5vw, 44px)", textAlign: "center", marginBottom: 14 }}>Contact us</h1>
        <p style={{ textAlign: "center", color: "var(--text-dim)", marginBottom: 36, fontSize: 14 }}>We read every message. Usually back within 24 hours (Mon–Fri).</p>

        <div style={{ display: "grid", gap: 12 }}>
          {[
            { Icon: Mail, label: "General support", href: "mailto:support@aiadvocate.co.uk", text: "support@aiadvocate.co.uk" },
            { Icon: Briefcase, label: "Law-firm partnerships", href: "mailto:firms@aiadvocate.co.uk", text: "firms@aiadvocate.co.uk" },
            { Icon: ShieldCheck, label: "Privacy & data requests", href: "mailto:privacy@aiadvocate.co.uk", text: "privacy@aiadvocate.co.uk" },
            { Icon: ShieldCheck, label: "Data Protection Officer (GDPR)", href: "mailto:dpo@aiadvocate.co.uk", text: "dpo@aiadvocate.co.uk" },
            { Icon: KeyRound, label: "Security reports", href: "mailto:security@aiadvocate.co.uk", text: "security@aiadvocate.co.uk" },
          ].map(({ Icon, label, href, text }, i) => (
            <a key={i} href={href} style={{ display: "flex", alignItems: "center", gap: 14, padding: 16, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, textDecoration: "none", color: "var(--text)" }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: "rgba(247,201,72,0.12)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Icon size={18} style={{ color: GOLD }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: "var(--text-dim)", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 3 }}>{label}</div>
                <div style={{ color: GOLD, fontSize: 14, fontWeight: 600 }}>{text}</div>
              </div>
              <ExternalLink size={16} style={{ color: "var(--text-dim)" }} />
            </a>
          ))}
        </div>

        <div style={{ marginTop: 40, padding: 18, background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 12, fontSize: 13, color: "var(--text-dim)", lineHeight: 1.7 }}>
          <strong style={{ color: "#fca5a5" }}>Not a regulated legal practice.</strong> If you have an active urgent legal matter, contact a regulated solicitor in your jurisdiction. In an emergency in the UK, dial 999. For 24-hour free UK legal advice, contact Citizens Advice (citizensadvice.org.uk).
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
