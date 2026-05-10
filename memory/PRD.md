# AI Advocate — Product Requirements Document

## Original Problem Statement
"AI Advocate" — an AI lawyer in your pocket. More intelligent than top lawyers. Prioritises tasks, gives legal advice, advises on how to answer when questioned by police or in court, reads contracts and explains jargon. Includes a Siri-like voice button "Lex" — a friendly AI character users can ask any question. 14-day free trial, then subscription. 11 languages. Connected to the most powerful AI law brain. Adapts to laws of different countries based on user location/visit.

**Iteration 2 additions (May 2026):** Camera capture for evidence (contracts, parking tickets, photos of places that benefit a case), location services with on/off toggle, law firm directory + advertise-with-us page using location for nearby suggestions.

## User Personas
- **Citizen with a legal question** — e.g. tenancy dispute, employment grievance, traffic ticket. Wants fast, plain-English advice.
- **Person facing police/court** — needs to know rights, what to (not) say.
- **Contract reader** — wants to understand jargon and red flags before signing.
- **Expat / immigrant** — needs jurisdiction-aware advice, in their native language.
- **Law firm** — wants to advertise services to relevant prospects.

## Core Architecture
- **Frontend:** React 19 (CRA), TailwindCSS, lucide-react icons. Black + gold theme.
- **Backend:** FastAPI on `:8001` (supervisor). All routes under `/api`.
- **DB:** MongoDB (`ai_advocate_db`). Collections: users, conversations, legal_files, law_firms, law_firm_inquiries, law_firm_applications.
- **AI / Voice:**
  - **Lex chat & legal-letter generation** → Claude Sonnet 4.5 via `emergentintegrations.llm.chat.LlmChat` (model: `anthropic/claude-sonnet-4-5-20250929`).
  - **Evidence + contract photo analysis** → Gemini 2.5 Flash (vision) — `gemini/gemini-2.5-flash` (the library limits file attachments to Gemini).
  - **Speech-to-Text** → OpenAI Whisper-1 via `OpenAISpeechToText`.
  - **Text-to-Speech** → OpenAI TTS-1 (voice: `onyx`) via `OpenAITextToSpeech`.
  - All AI accessed through Emergent Universal LLM key (`EMERGENT_LLM_KEY`).
- **Payments:** Stripe Checkout subscription (£14.99/mo or £119.99/yr). Test mode with `sk_test_emergent`.
- **Auth:** JWT (HS256, 30-day exp) email/password (bcrypt-12) + simplified Google sign-in (demo).
- **i18n:** 11 languages (en-GB, es-ES, fr-FR, ar-IQ, pl-PL, de-DE, hi-IN, ur-PK, it-IT, pt-PT, zh-CN). RTL support for ar/ur.

## What's Implemented (May 2026 — MVP v1.2)

### Onboarding & Auth ✅
- Language picker (11 langs, on first launch)
- Terms & Conditions screen with "Lang" toggle
- Email/password signup (auto 14-day trial)
- Email/password login
- Google sign-in (simplified demo — accepts email/name/google_id without verifying Google token)

### Dashboard — Heraldic Crest Icons (Custom SVGs, no boxes) ✨ NEW v1.2
- Clean icon grid (3-column) with custom hand-drawn heraldic SVG icons matching the gold shield logo aesthetic
- 11 features: Ask Lex (speech bubble), Record (classical mic), Snap Evidence (vintage camera), Find a Lawyer (courthouse), My Files (leather book), Generate Letter (scroll + quill), Court Prep (scales of justice), Immigration (globe + passport stamp), Employment (briefcase), Property (pillared house), Medical Negligence (caduceus)
- Sticky bottom nav: 🏠 Home · 📁 Files · 🟡 LEX (raised gold center) · 🏛️ Lawyers · ⚙️ Settings

### PDF Export ✨ NEW v1.2
- Branded PDF with AI Advocate logo header, gold divider, formatted body, page footer
- "Download PDF" button on: Legal Letter result, Snap Evidence result, Recording analysis result, Files modal item view
- Two backend endpoints:
  - `POST /api/pdf/inline` — generate from raw {title, body, subtitle, meta} (used pre-save)
  - `GET /api/pdf/file/{id}` — generate from any saved legal_files entry (letter / evidence / recording / contract). Supports cross-user 404 security.

### Lex Chat with smart suggestions ✅
- Empty state shows 6 clickable example chips covering long-tail use cases (deposit, divorce, defamation, parking, unfair dismissal, wills)
- Voice in (Whisper) + voice out (OpenAI TTS, voice="onyx") — Lex actually speaks back
- Country & language aware; category-specific system prompts

### Settings & Personalisation ✅ *(NEW)*
- Settings modal (gear icon, top bar)
- Location services toggle (browser geolocation; saved on user profile; off by default)
- Country selector (Lex applies that country's law)
- Language switcher (top bar pill)

### Law Firm Directory & Advertising ✅ *(NEW)*
- 12 sample firms seeded across 11 countries (5 sponsored)
- Filters: country, specialty, location radius (haversine)
- Sort: sponsored-first, then distance/rating
- **Inquiry form** (logged-in users → law_firm_inquiries collection)
- **"List your law firm" public application form** → law_firm_applications (status: pending)

### Subscription ✅
- 14-day free trial (auto-applied at signup)
- `has_access` computed flag drives feature gating
- Stripe Checkout (£14.99/mo or £119.99/yr)
- Trial banner shows days remaining; "Subscribe" CTA after expiry
- Demo "Activate (no payment)" button for testing

### Voice (Lex speaks) ✅
- Mic button on Lex chat → Whisper transcribe → Claude reply → TTS audio plays back
- Lex avatar shows pulsing gold ring while recording

### Backend API (35 endpoints) ✅
All under `/api`. Tested with 42 pytest tests (100% pass).

## Tested Status
- **Backend:** 42/42 pytest tests pass (auth, lex chat, voice STT/TTS, contract analysis, evidence analysis, legal letter, record analysis, legal files, languages, subscription checkout/activate/status, lawfirms list/filter/distance, lawfirm inquiry, lawfirm advertise public, location prefs).
- **Frontend:** Manually verified — onboarding, dashboard renders all tiles, Find a Lawyer modal lists sponsored + regular firms with distance, Snap Evidence camera/library upload UI works, settings modal toggles location.

## Backlog / Future Enhancements

### P0 — Production hardening
- Rate-limit + captcha on `/api/lawfirms/advertise` and `/auth/signup` (currently public, unbounded)
- Real Google OAuth (Emergent-managed) instead of demo signup-by-email
- Apple Sign-In (requires Apple Developer account)
- Stripe webhook endpoint to update `subscription_status` on real payment events
- Refresh-token rotation (current JWT is 30-day fixed)

### P1 — Product features
- Live legal updates feed (RSS/news scraper for legislation changes per country) — currently relies on Claude's training data
- PDF export of generated letters & analyses
- Multi-image evidence (case file with multiple photos in one analysis)
- Push notifications (PWA + web push) for trial-end reminders, firm replies
- Admin dashboard to verify law-firm applications & manage sponsorships

### P2 — Nice to have
- Voice cloning / custom Lex voice
- Lex animated avatar (lip-sync TTS)
- Native mobile (React Native or Capacitor wrapper)
- Document OCR for contracts that are image-only (currently Gemini Vision handles it but explicit OCR could be cheaper)
- Conversation summarisation in My Files

## File Structure
```
/app/
├── backend/
│   ├── server.py          # All FastAPI routes (35 endpoints, ~800 lines)
│   ├── .env               # MONGO_URL, DB_NAME, JWT_SECRET, EMERGENT_LLM_KEY, STRIPE_API_KEY
│   ├── requirements.txt
│   └── tests/
│       └── backend_test.py  # 42 pytest tests
├── frontend/
│   ├── src/
│   │   ├── App.js         # Single-file SPA (~770 lines): Onboarding, Auth, Dashboard, all modals
│   │   ├── i18n.js        # 11-language UI strings
│   │   ├── index.css      # Black + gold theme, fonts (Cinzel + Outfit)
│   │   └── App.css
│   └── .env               # REACT_APP_BACKEND_URL
└── memory/
    ├── PRD.md             # This file
    └── test_credentials.md
```

## Important Notes
- **Voice playback** auto-plays after each Lex reply on chat — uses `<audio>` element + Blob URL.
- **Sponsored law firms** are surfaced first in lists; tagged with gold "Sponsored" badge.
- **`/api/lawfirms/advertise` is public by design** — law firms shouldn't need a user account to apply.
- **Vision analysis uses Gemini** because emergentintegrations LlmChat library only supports file attachments via Gemini. Claude is used for text/voice chat where it excels at legal reasoning.
- **Trial gating** happens via `has_access` computed in `user_to_public()`. All AI endpoints (chat, evidence, contract, letter, voice, record) return 402 when has_access=false.
