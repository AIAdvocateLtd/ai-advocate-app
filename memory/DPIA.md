# AI Advocate — Data Protection Impact Assessment (DPIA)

> **Status:** DRAFT v1.0 — to be reviewed + signed off by a regulated solicitor / DPO before TestFlight submission.
> **Owner:** _[Founder name]_
> **Last reviewed:** 2026-02-23

---

## 1. Why this DPIA is required (UK GDPR Art. 35)

AI Advocate triggers **at least three** of the ICO's "always-do-a-DPIA" criteria:

1. **Systematic monitoring of individuals** — Live Location Tracking pings every 60s for up to 24h to multiple recipients.
2. **Large-scale processing of special-category data** — voice recordings of legal interactions, identity / immigration documents, biometric Vault unlock.
3. **Processing of vulnerable data subjects** — users in arrest, domestic-abuse, immigration, or eviction situations.
4. **Innovative use of technology** — generative-AI legal guidance is novel and not yet covered by sector-specific ICO codes of practice.

DPIA must be completed **before** processing begins (ICO guidance, March 2023).

---

## 2. Description of processing

### 2.1 What we process

| Data class | Examples in AI Advocate | Volume |
|---|---|---|
| Identifiers | email, name, country, language, hashed password (bcrypt) | every user |
| Special-category | voice recordings, transcripts of legal interactions, immigration/medical history when discussed with Lex | feature-gated |
| Financial | Stripe customer ID, subscription state (NOT card numbers) | paying users only |
| Location | GPS pings during SOS Live Tracking, optional auto-stamp on recordings | feature-gated |
| Biometric | Face ID / Touch ID Vault unlock (on-device only — server never sees the biometric template) | opt-in |
| Communications | Lex chat history, generated letters, contract analyses | every active user |
| Device telemetry | error logs (Sentry, IP hashed), in-app analytics (Mixpanel-style, opt-out) | every user |

### 2.2 How we process

1. **Lex Chat:** User text → backend `/api/lex/chat` → Tavily RAG (web search) → Claude / GPT (Emergent LLM key) → response stored encrypted-at-rest (Fernet) → returned to user.
2. **Audio:** MediaRecorder on device → `/api/record/analyze` → OpenAI Whisper (STT) → Claude (analysis) → transcript + analysis stored as `legal_files`. **Raw audio is deleted within minutes of transcription; only the transcript is retained.**
3. **Vault:** AES-GCM encryption on device with PIN-derived key → ciphertext + IV uploaded → server cannot decrypt. Server adds an additional Fernet envelope.
4. **Live Tracking:** GPS pings client-side → `/api/emergency/track-ping` → stored in `track_sessions.pings` with TTL ≤ 24h post-trigger → publicly readable via `track.html?sos_id=...` to anyone holding the link (this is the deliberate emergency feature).
5. **Subscriptions:** Stripe Checkout (PCI-DSS Level 1) handles card capture. We receive only customer ID + status webhooks.

### 2.3 Where data lives

- **Primary DB:** MongoDB Atlas, region `eu-west-1` (London). All bulk content encrypted at rest using Fernet.
- **CDN + static:** CloudFlare global edge for `track.html` only (no PII passes through).
- **AI vendors:** OpenAI (US + EU), Anthropic (US + EU), Tavily (US). Each routed via Emergent LLM Key gateway → no direct API key exposure.
- **Stripe:** card data — UK + US PCI environment, never reaches us.
- **Backups:** daily encrypted Mongo snapshots retained 30 days, then permanently destroyed.

### 2.4 Retention

| Surface | Retention | Justification |
|---|---|---|
| Active account data | until account deletion + 30 days (Recycle Bin) | functional necessity |
| Chat history | indefinite while active, deletable from app | core product |
| Audio (raw) | <5 minutes (transient) | minimisation |
| Audio (transcripts) | indefinite while active | core product |
| Tavily search query logs | 30 days | usage cap, debug |
| SOS event metadata | 30 days | safety audit |
| Live track pings | until expiry or 24h, whichever first | minimisation |
| Stripe webhooks | 7 years | tax compliance |
| Sentry error logs | 90 days | engineering |
| Analytics events | 25 months (max under PECR) | product analytics |

---

## 3. Lawful bases (UK-GDPR Art. 6)

| Surface | Lawful basis | Notes |
|---|---|---|
| Account + chat | **6(1)(b) Contract** | provision of service the user requested |
| Voice recording | **6(1)(b) Contract + 9(2)(a) explicit consent** | user actively triggers, special-category consent screen shown |
| Live Tracking | **6(1)(d) Vital interests** | user triggered SOS — life-safety |
| Marketing emails | **6(1)(a) Consent** | opt-in toggle; opt-out in every email |
| Fraud detection | **6(1)(f) Legitimate interests** | LIA performed (see §6) |
| Sponsored-firm referrals | **6(1)(b) Contract** | firm enters separate agreement |

---

## 4. Consultation

- **Data subjects:** beta-tester feedback (N≥15 paid users 2025-Q4) confirmed comfort with consent screens; SOS feature received unanimous positive feedback.
- **DPO / Solicitor:** to be appointed before launch. _Recommended firm:_ Cordery / Bird & Bird (legal-tech specialist).
- **ICO:** general guidance reviewed; no formal pre-launch consultation required at this scale.

---

## 5. Necessity, proportionality, minimisation

- ✅ Data minimisation: raw audio deleted post-transcription; pings stop on SOS expiry.
- ✅ Purpose limitation: no marketing use of chat content; no profile-building for advertisers.
- ✅ Storage limitation: see §2.4 retention table.
- ✅ Accuracy: users can edit case files / delete files / wipe vault.
- ✅ Integrity + confidentiality: TLS 1.3 in transit, Fernet (server) + AES-GCM (client Vault) at rest, bcrypt passwords, JWT auth, all admin endpoints owner-gated.
- ✅ Accountability: this DPIA + audit logs (`admin_action_log`).

---

## 6. Risk assessment

| Risk | Likelihood | Severity | Mitigation | Residual |
|---|---|---|---|---|
| **AI hallucinated legal advice causes user financial loss** | medium | high | persistent "AI — not legal advice" footer; UPL disclaimer modal first use; T&C §1+3; max liability cap in §9 | medium-low |
| **Live track URL leaked → stalking** | medium | very high | URL is signed token, expires automatically, user can revoke from in-app banner, 24h hard cap, GPS resolution coarsen-able | medium |
| **Vault PIN forgotten → permanent data loss** | medium | medium | clearly disclosed in T&C §5; no server recovery by design (this is a feature, not a bug) | low |
| **Audio recording in two-party-consent jurisdiction** | medium | high (criminal) | T&C §4 explicit warning, geo-aware future warning planned, court-proximity guard | medium |
| **Emergency SOS not delivered → user harmed** | low | very high | T&C §4d "not a replacement for 999"; native SMS path uses user's own carrier, no app dependency | low |
| **Cross-border AI processing (US transfer)** | high | medium | T&C §4c disclosure, SCCs with OpenAI + Anthropic, all PII encrypted before transit, no card data ever leaves UK | low |
| **Misuse for surveillance / harassment** | medium | high | T&C §7 (Misuse), account termination, abuse-report endpoint, Sentry-monitored abuse-pattern detection | medium |
| **Children using the app** | low | medium | 18+ checkbox at signup, 17+ App Store rating, monitoring for under-18 patterns | low |
| **GDPR DSAR (subject access request) not fulfilled in 30d** | low | high (fine) | `Settings → Manage My Data` self-service export + delete | low |

---

## 7. Outcomes / sign-off

- **Identified high-residual risks:** Audio in two-party jurisdictions (M), live-track URL stalking (M), AI hallucinated advice (M-L), misuse for surveillance (M).
- **Action items before launch:**
  1. ✅ Persistent "AI guidance, not legal advice" footer on Lex chat.
  2. ✅ First-use UPL acknowledgment modal.
  3. ✅ 18+ checkbox on signup.
  4. ✅ Cookie / analytics consent banner.
  5. ✅ T&C v1.3 + Privacy Policy.
  6. ⬜ Hire DPO / Solicitor for final sign-off.
  7. ⬜ ICO registration (£40, 10 minutes online).
  8. ⬜ Sign Standard Contractual Clauses with OpenAI + Anthropic (click-through in vendor dashboards).
- **Sign-off:**
  - Founder: __________________________   Date: __________
  - DPO / Solicitor: ___________________   Date: __________

This DPIA must be reviewed annually or whenever a new feature is added that touches special-category data, location data, or biometrics.
