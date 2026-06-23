# AI Advocate — Insurance Quote Brief
**For: Tech PI / E&O + Cyber + Media combined liability**
**Prepared by: Samuel Malick, Founder & CEO**

> Paste the relevant sections into Superscript, Hiscox, Simply Business, Markel, CFC, or Beazley quote forms. Each section is self-contained — copy what's asked, skip the rest.

---

## 1. Business basics

| Field | Answer |
|---|---|
| Legal name | **AI Advocate Ltd.** |
| Companies House No. | **16612244** |
| Trading name | AI Advocate |
| Registered in | England & Wales |
| Year incorporated | 2026 |
| Registered office | _[Insert your registered office address from Companies House]_ |
| Sector | UK consumer + B2B legal-information software (SaaS) |
| Trading start date | Pre-revenue / pre-launch (web app live; App Store launch pending) |
| Website | https://aiadvocate.co.uk |
| Director(s) | Samuel Malick |
| Employees / contractors | 1 (founder) — solo operation pre-launch |
| ICO Registration | **ZC158457** (data controller, verifiable at ico.org.uk) |

---

## 2. Activity description (paste verbatim into "describe your business")

> AI Advocate is a UK-focused legal-information software product. The consumer web/mobile app allows users to interact with an AI assistant ("Lex") that provides **general legal information** — not legal advice — grounded in UK statutes (legislation.gov.uk) and case law (BAILII). Users can also generate legal letters, review contracts, store evidence in an encrypted vault, prepare for court hearings, and access emergency-rights guidance. A separate B2B Firm Portal lets SRA-regulated solicitor firms list themselves in a directory and engage clients introduced via the platform; firms pay a monthly subscription (Featured £49 / Premium £199 / Practice £499 / Founding Partner bespoke). The platform does NOT provide reserved legal services as defined by the Legal Services Act 2007. Every AI output includes a clear disclaimer that it is general information only and not a substitute for a qualified solicitor.

---

## 3. Required cover (tell insurer this is what you want)

| Cover type | Amount sought | Notes |
|---|---|---|
| **Professional Indemnity / Tech E&O** | £1,000,000 (£2m preferred) | Must include cover for **AI-generated outputs**. Some standard policies exclude AI — please confirm wording in writing. |
| **Cyber liability** | £1,000,000 | Including GDPR / ICO investigation costs, breach notification, ransomware, business interruption. |
| **Media liability** | £250,000+ | Defamation, IP infringement, breach of confidence in user-facing content (incl. AI outputs). |
| **Public liability** | £1,000,000 | Standard inclusion if available. |

---

## 4. Revenue & exposure

| Field | Answer |
|---|---|
| Current annual turnover | £0 (pre-launch) |
| Projected Year-1 turnover | £25,000 – £75,000 (consumer subscriptions + first 20 founding firms) |
| Projected Year-2 turnover | £150,000 – £400,000 |
| Largest single client contract | Founding Firm at £199/mo = ~£2,400/yr |
| % UK / % overseas | ~95% UK / ~5% UK residents whose matters touch other jurisdictions |
| B2C vs B2B mix | ~70% B2C consumer subscriptions / 30% B2B firm subscriptions |

---

## 5. Data we hold (cyber section)

| Data category | Stored? | Notes |
|---|---|---|
| Names / emails | Yes | Account credentials. |
| Phone numbers | Yes (optional) | For Emergency SOS contacts. |
| Location data | Yes (with explicit consent) | GPS coordinates for SOS Live Tracking; auto-expires after 30 min. |
| Government IDs | No | We do not collect passports / driving licences. |
| Bank / card details | No | All payments handled by **Stripe** (PCI-DSS Level 1). We never see card data. |
| Health data | Incidental | Users may discuss legal issues involving health (e.g. medical negligence). Treated as special-category data under Art. 9 UK GDPR. |
| Legal case content | Yes | Stored encrypted at rest. The encrypted "Lex Vault" uses **client-side AES-256-GCM** — keys never leave the user's device. Zero-knowledge architecture. |
| Estimated PII records (Year 1) | 5,000 – 25,000 user accounts |
| Estimated PII records (Year 2) | 50,000 – 200,000 user accounts |

---

## 6. Security controls (cyber section — they love this)

- ✅ **Encryption at rest:** AES-256 on MongoDB; AES-256-GCM client-side for the Lex Vault (zero-knowledge).
- ✅ **Encryption in transit:** TLS 1.3 enforced via Cloudflare ingress.
- ✅ **Hosting:** Kubernetes-managed cloud infrastructure (Emergent platform); UK data residency.
- ✅ **Backups:** Daily MongoDB snapshots, 30-day retention.
- ✅ **Authentication:** Bcrypt-hashed passwords; JWT sessions (30-day expiry); WebAuthn biometric unlock; Google + Apple SSO available.
- ✅ **Admin access:** Restricted to founder; passwords stored as bcrypt hashes in environment variables, never in code.
- ✅ **Logging & monitoring:** Sentry for application errors; Cloudflare WAF for ingress; structured backend logs retained 90 days.
- ✅ **Incident response plan:** Documented; 72-hour ICO notification commitment per UK GDPR Art. 33.
- ✅ **Penetration testing:** Quarterly external pen-test planned post-launch (not yet conducted).
- ✅ **Patch management:** Continuous deployment; dependencies monitored via GitHub Dependabot.
- ✅ **Data minimisation:** Collect only what's necessary; right-to-erasure self-serve in user settings.

---

## 7. AI / ML use (this is where you need them to confirm cover)

| Field | Answer |
|---|---|
| Do you use AI / ML? | **Yes** — this is core to the product. |
| AI providers | Anthropic (Claude Sonnet 4.5, Haiku 4.5), OpenAI (GPT-5.2), Google (Gemini 2.5 Flash) — all via their enterprise API endpoints. |
| AI training on user data | **No** — per published API data-handling policies, none of these providers use enterprise-endpoint traffic for training. |
| AI output review | Lex's system prompts enforce: (a) cite real UK statute / case-law sources; (b) refuse to give definitive advice; (c) refer users to qualified solicitors for material matters; (d) include a "not legal advice" disclaimer on every output. Outputs are NOT pre-reviewed by a human before delivery. |
| Hallucination mitigation | Retrieval-Augmented Generation (RAG) grounds answers in legislation.gov.uk + BAILII + gov.uk; Tavily API used for fresh search. |
| AI-specific risks the policy must cover | (1) Incorrect or outdated information leading to user financial loss; (2) Hallucinated case citations; (3) Misclassification of jurisdiction (mitigated by our auto-jurisdiction detection); (4) Defamation in AI-generated content; (5) Copyright infringement in AI outputs. |

---

## 8. Regulatory posture

| Field | Answer |
|---|---|
| Regulated by SRA / FCA / equivalent? | **No** — we do not provide reserved legal services under the Legal Services Act 2007. |
| ICO-registered data controller | **Yes** — Registration No. ZC158457. |
| DPO appointed? | Yes — dpo@aiadvocate.co.uk. |
| GDPR compliant? | Yes — UK GDPR + Data Protection Act 2018; DPIA completed for Vault, SOS, audio recording, AI profiling. |
| Age restriction | 18+; verified at signup. |
| Consumer protection | UK Consumer Contracts Regulations 2013 — 14-day cooling-off honoured; explicit waiver for immediate digital top-ups. |

---

## 9. Claims history

- **Prior claims (last 5 years):** None.
- **Known circumstances that might give rise to a claim:** None.
- **Previous insurance held:** None (first-time policy).

---

## 10. Key contractual commitments (PI exposure)

| Counterparty | Commitment | Annual exposure |
|---|---|---|
| Consumer users | General legal-information service; liability capped at £50 or 3 months' fees (whichever greater) per Terms of Service v1.4.1 cl.8. | Low individually; high in aggregate. |
| Founding Firms (B2B) | Directory listing + lead introduction; 12-month initial term + monthly thereafter; £199/mo locked for life of subscription. AI Advocate's liability to firms is capped at 3 months of fees paid. | ~£2,400 per firm per year. |
| Stripe (payment processor) | Standard merchant agreement; we are not the merchant of record for App Store purchases. | n/a |

---

## 11. Ask the insurer to confirm (in writing)

Before binding, request **explicit written confirmation** of:

1. **AI-generated outputs are covered** under the Tech PI / E&O section (some policies exclude algorithmic decisions or "fully autonomous AI").
2. **Hallucinated legal information** falls within the cover (specifically "errors in information provision" via AI).
3. **GDPR / ICO regulatory investigations** are included under the Cyber section, including defence costs *and* (where insurable) fines.
4. **Wrongful AI output → user financial loss** scenario is a covered claim trigger.
5. **Worldwide claims jurisdiction** — your users may be UK residents but their disputes can be heard abroad (e.g. EU consumer-protection claims).

If the insurer cannot confirm any of these, that policy is not fit for your business.

---

## 12. Useful one-liners for the form

> **"What does your business do?"**
> AI Advocate is a UK SaaS providing general legal information through an AI assistant, plus a directory connecting consumers to SRA-regulated solicitor firms. We do not provide regulated legal services.

> **"Describe your worst-case scenario."**
> An AI output cites a case incorrectly or omits a critical statutory section. The user relies on it in court, loses, and sues for consequential financial loss. We would defend under our liability cap (clause 8 of our Terms) and refer to our PI cover.

> **"What proportion of your work is provided by sub-contractors?"**
> 0% — sole proprietor. All AI processing via Anthropic / OpenAI / Google enterprise API endpoints (no human sub-contractor reviews any AI output).

> **"What is your retention period for client data?"**
> Active accounts: indefinitely while account is active. On account deletion: erased within 30 days from all backups within 90 days. Special-category data minimised; right-to-erasure self-service in Settings.

> **"Have you ever been refused insurance, had a policy cancelled, or had a claim?"**
> No.

---

## 13. Send the brief

When emailing brokers (CFC, Markel) attach this as a PDF. For web forms (Superscript, Hiscox direct, Simply Business), paste section-by-section as the form asks.

**Brokers to contact:**
1. **Superscript** — gosuperscript.com — fastest online quote, SaaS-friendly.
2. **Hiscox direct** — hiscox.co.uk/business-insurance — premium underwriter.
3. **CFC Underwriting** — cfcunderwriting.com — UK tech/cyber specialist; broker-only.
4. **Markel** — markelinternational.com — strong on professional services.
5. **Coalition** — coalitioninc.com/en-gb — cyber-first, AI-friendly.

Aim for **3 quotes** to compare on (a) annual premium, (b) AI-output cover wording, (c) excess/deductible, (d) sub-limits on regulatory defence costs.

---

*Prepared 2026. Update Year-1/Year-2 turnover figures as your launch progresses.*

---

## 14. Broker follow-up response (added 23 June 2026)

**File generated:** `/app/frontend/public/CFC_Broker_Followup_Response.pdf`
**Download URL:** `https://aiadvocate.co.uk/CFC_Broker_Followup_Response.pdf` (after Deploy)

The broker came back asking for explicit yes/no confirmation on several questions
already answered in the original form, plus a revenue clarification (form fields had
rendered "2" instead of "£2,000"). Summary of confirmations sent:

| Q | Question (paraphrased) | Confirmed Answer |
|---|---|---|
| 1.3 | Subsidiaries? | NO |
| 1.4 | Part of a larger corporate group? | NO |
| 1.5 | Financial year end | **31 July** (first accounts 31/07/2026) |
| 1.6 | Revenue — full amounts | UK Current FY £2,000 / Next FY £30,000. Total GR same. Loss (£5,000) current / (£10,000) next. All UK; no USA/overseas revenue. |
| 1.9 | Investment / funding received or planned? | NO — 100% founder-funded, no fundraising in next 12 months |
| 2.3 | Tangible products / installation? | NO |
| 2.4 | Hosting services to clients? | NO |
| 2.6 | Managed services? | NO |
| 3.6 | Subcontractors? | NO |
| 5.2 | Cease-and-desist / IP claim received? | NO |
| 8.1 | Limits of indemnity (E&O £1M/£1k · Cyber £1M/£1k · GL £1M/£250 · D&O £500k/£1k) | CONFIRMED. Also requested £2M E&O quote as comparison + written confirmation that AI-generated outputs are covered. |
| 10 | Awareness of incidents / claims? | NO |

