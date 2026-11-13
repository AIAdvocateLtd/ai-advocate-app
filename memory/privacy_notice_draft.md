# AI Advocate — Privacy Notice: proposed corrections (DRAFT, not published)

Prepared 2026-11-13 from code inspection. Items marked **[CONFIRM]** need confirmation from you, the supplier or a professional adviser before publishing. Nothing here is legal advice.

## 1. Corrections to "Third parties we share with"
Replace the current list with:

- **Emergent (Emergent Labs)** — hosts the app and database, and routes AI requests to the model providers below. **[CONFIRM: hosting/database region, sub-processor list, data processing agreement]**
- **Anthropic (Claude)** — answers Lex questions for Free (Claude Haiku) and Pro / Deep Think (Claude Sonnet) customers.
- **OpenAI** — answers Lex questions for **Plus** customers (GPT-5.2), and transcribes audio recordings (Whisper). *(Current notice wrongly says OpenAI is used only for transcription.)*
- **Google (Gemini)** — reads photos and scanned documents (e.g. contracts, forms) when you upload them.
- **Tavily** — web research: Lex sends short search queries built from your question to find official sources. **[CONFIRM: Tavily retention + location]**
- **Resend** — sends account, reminder and data-export emails (your data export is emailed as an attachment).
- **Stripe** — payments and subscriptions (we never see full card numbers).
- **PostHog (EU)** — optional usage analytics, only if you switch it on; no chat content.
- **Sentry** — error monitoring (technical error details; we aim to exclude chat content). **[CONFIRM: Sentry region and scrubbing settings]**
- **Cloudflare** — website delivery, security and bot protection (Turnstile).
- **Apple / Google sign-in** — only if you choose them.
- **legislation.gov.uk, ACAS, GOV.UK** — Lex looks up public legal sources; no personal data is sent beyond the search terms.

Keep: "We do NOT sell your data."
Remove: "Anthropic does NOT train on Universal-Key API traffic" unless confirmed in writing **[CONFIRM with Emergent/Anthropic]**.

## 2. Corrections to "What we collect"
- Replace "Lex chat content … Encrypted at rest" with: "Lex chat content is encrypted at rest. Some conversations created before encryption was introduced are being migrated." **[after migration is done, remove the second sentence]**
- Add: "Documents you upload to Lex: we keep the extracted text so Lex can refer to it in your conversation." **[CONFIRM retention period — none currently set]**
- Add: "Emergency features: your emergency profile, emergency events and, if you share it, your location."
- Add: "Evidence and witness features: file details (not the files themselves), witness statements and invitations you send."
- Correct "Case files: … uploaded documents" — case attachments and recorded evidence store the file name, details and a fingerprint, not the file itself.

## 3. Corrections to "Data retention"
Replace with:
- "Active accounts: kept while you use AI Advocate. You can delete conversations and cases at any time (deleted items are kept in a recycle bin for 30 days)."
- "When you delete your account: your personal and legal information is deleted immediately. If any part fails, it is completed automatically within 24 hours."
- "We keep, without your name or email: AI usage and cost totals (to run spending limits), records of gift payments (UK tax law: 6 years), and audit records of complimentary access and analytics deletions."
- "Payment records are held by Stripe for tax and accounting purposes." **[CONFIRM retention period with accountant — typically 6 years from the end of the financial year]**
- Remove "personal data permanently erased within 30 days" (no 30-day process exists; deletion is immediate).

## 4. Corrections to "International transfers"
Replace "Our servers are in the EU" with:
"Our hosting and database provider's location: **[CONFIRM with Emergent]**. AI providers (Anthropic, OpenAI, Google) and some other suppliers process data in the United States. Where data leaves the UK we rely on **[CONFIRM: UK International Data Transfer Agreement / UK Addendum to EU SCCs / UK–US Data Bridge, per supplier]**."

## 5. Corrections to "Your rights"
- Access / portability: "Settings → Export My Data emails you a readable web page and a machine-readable JSON file." (It is not a PDF; the web page can be printed to PDF.)
- Note: very large accounts (more than 2,000 conversations) receive the first 2,000 and can request the rest from support.

## 6. Items needing confirmation before publishing
1. Hosting/database location and Emergent data processing agreement + sub-processors.
2. International transfer mechanism for each US supplier.
3. AI providers' training/retention terms for API traffic.
4. Tavily and Sentry retention and region.
5. Retention period for uploaded-document text.
6. Financial-record retention period (accountant).
7. Whether a Data Protection Officer is actually appointed (notice lists dpo@aiadvocate.co.uk) and whether privacy@ / dpo@ mailboxes exist.
8. ICO registration ZC158457 is current.
