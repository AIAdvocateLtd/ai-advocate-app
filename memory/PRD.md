# AI Advocate — Product Requirements

## Product
A multilingual "lawyer in your pocket" mobile-web app. Core: Lex AI chat (Claude 4.5), photo evidence (Gemini), voice in/out, multilingual PDF legal letters, law-firm directory, Stripe subscription. 14-day free trial.

## Brand & UX
- Dark theme, pure-black (#000) background, gold accents (#f7c948), Cinzel serif for headings.
- Heraldic SVG icons (no generic lucide). Lex avatar character used sparingly.
- RTL support for Arabic & Urdu.

## Auth
- Email/password (custom JWT)
- Apple Sign-In (web) — ✅ WORKING (Services ID: `app.aiadvocate.signin`)
- Google Sign-In — code ready, awaiting `GOOGLE_CLIENT_ID`

## AI Stack (Emergent LLM Key)
- **Chat (Lex):** Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- **Vision (Photo + Contract):** Gemini 2.5 Flash
- **Voice:** OpenAI Whisper STT + OpenAI TTS (`onyx` voice)
- **Wake word:** browser-native Web Speech API for "Hey Lex"

## Languages (11)
English, Spanish, French, Arabic, Polish, German, Hindi, Urdu, Italian, Portuguese, Chinese.
Lex auto-detects user's typed language and replies in it (overrides UI language).

## Payments
Stripe (£14.99/mo, £119.99/yr). 14-day trial. Apple/Google IAP planned for native apps.

## Legal
Bulletproof Terms & Privacy (England & Wales governing law + ICC arbitration + GDPR + CCPA). Forced "I Agree" before signup.

---

## Completed (chronological)

### 12 May 2026 — Session 2
- ✅ **Web Apple Sign-In fixed** — combination of: registering new preview domain `ai-law-guide-1.preview.emergentagent.com` in Apple Services ID, adding trailing `/` to redirectURI, and clearing stuck Apple sign-in record on user's device.
- ✅ **Lex brain v2** — system prompt upgraded to: auto-detect user's language and reply in it; step-by-step legal reasoning like a top barrister; explicit ban on hallucinated citations; jurisdiction-aware; ranked action plans.
- ✅ **"Hey Lex" wake word** — continuous Web Speech Recognition on Dashboard; matches multilingual variants (hey/hi/ok/hola/bonjour/你好/etc. + lex/лекс); auto-opens Ask Lex modal and starts mic. Toggle pill in dashboard header (gold dot when active).
- ✅ **Pure-black UI** — `--bg` and `.lex-circle` now `#000`; logo & avatars use `mix-blend-mode: lighten` so the JPG backgrounds blend invisibly into the screen.
- ✅ **De-cluttered chat** — removed both duplicate Lex avatars (header & empty-state) per user request; chat shows only category title + AI Advocate subtitle. Mic stays prominent.
- ✅ **Bulletproof T&C + Privacy** — 22-section Terms + 10-section Privacy summary; governed by England & Wales; mandatory ICC arbitration; class-action waiver; £50 liability cap; AI hallucination disclaimer; no attorney-client relationship; CCPA + GDPR clauses; auto-renewal disclosure.
- ✅ **i18n gap fill** — added ~30 missing keys across all 10 non-English languages (home/lawyers/files labels, suggestions, evidence types, location prompts).

### Earlier
- Lex chat with multi-mode prompts (court prep, contract, employment, property, immigration, medical negligence, record review, legal letter).
- Photo Evidence (Gemini Vision).
- Multilingual PDF letter generation (ReportLab + NotoSans fonts).
- Law-firm directory with geolocation + sponsored slots + inquiry form.
- Stripe checkout + webhook.
- Custom Heraldic SVG icon set.

---

## Backlog

### P1 (next)
- Real Google OAuth — awaiting `GOOGLE_CLIENT_ID` from user
- Capacitor iOS wrap for App Store submission (push notifications, native mic permissions in Info.plist, native IAP)
- "Hey Lex" toggle in Settings modal (currently only pill in header)

### P2 (later)
- Admin dashboard to verify law firms + flip sponsored flags
- Live legal news/updates feed per country (RSS)
- Multi-image evidence analysis
- One-click PDF email send straight from app
- Push notifications for trial reminders + lawyer replies
