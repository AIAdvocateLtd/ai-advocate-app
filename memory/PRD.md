# AI Advocate — Product Requirements Document

## Original Problem Statement
"AI Advocate" — a multilingual "lawyer in your pocket" application. Free, Plus (£14.99), and Pro (£34.99) tiers with tiered LLM access. Stripe live subscriptions for consumers + law firms. Vault encryption, evidence analysis, Lex chat, hearing recorder, contract hub, firm portal with case threads, courtroom practice, emergency rights. Native iOS/Android wrap via Capacitor.

## Target Users
- **Consumers** (UK/EU primarily, 11 languages supported) needing legal information
- **Law firms** (B2B Featured £49 / Premium £199 / Practice £399 tiers)
- **Lawyers** working B2B2C via Firm Portal

## Completed Implementation (rolling)

### 2026-02 (Session 1 — pre-launch polish)
- **Splash polish**: replaced glitchy MP4 with user's new spin video, tightened circular mask (no box), trimmed/optimized 5.6MB→119KB. Static poster for instant first-paint.
- **Dashboard tile labels → bright gold** (#f7c948) for heraldic consistency (user pick "C").
- **Icon transparency** + tap-highlight kill (icons float on bg, no tap rectangles).
- **Asset cleanup**: removed ~22MB of unused splash MP4s, icon backups, icon-preview HTML files.
- **Lex voice speed-up**: SILENCE_MS 2200→1200 (saves ~1s on every voice question).
- **Hide "Hey Lex" wake-word toggle** in Settings (UI hidden; code preserved for future SiriKit replacement).
- **Strip Emergent badge + script** from `index.html` — full white-label brand.
- **Static legal pages** (`/privacy.html`, `/terms.html`) — public URLs required for App Store submission.
- **First-run onboarding tour** (3 swipeable cards: Meet Lex → Snap Evidence → Lex Vault) — shows once on first auth visit, localStorage flag `aa_welcomed`.
- **🆕 Free Taster Lex** — 1 free legal question for any visitor, no signup. Rate-limited 7 days per device_id + IP (`/api/lex/taster`). Conversion hook: returns answer + 7-day-trial CTA. Uses Haiku for cost.

### Earlier sessions (recap)
- Live Stripe subscriptions (consumer + 3 firm tiers)
- Firm Portal / Engagements / Case Threads (B2B2C async chat + file sharing)
- Vault hardening: 5-fail lockout, geo-alert banner
- Sentry + PostHog live
- 11-language i18n at 100% coverage
- Embossed 3D Gold icons via Nano Banana
- Full account deletion endpoint (App Store compliance)
- Stripe webhook handles cancellations for both consumer + firm subs

## Pending / Roadmap

### 🆕 OPEN ASK FROM USER (saved 2026-02)
**Speed up Lex voice flow ("Hey Lex" responsiveness)**
- User reports: takes long to stop listening + long to answer
- ✅ **PART A DONE 2026-02**: Reduced `SILENCE_MS` 2200 → 1200 in `App.js:515` (saves ~1s end-of-speech detection on web)
- 🎯 **PART B QUEUED for Capacitor iOS wrap session** — biggest wins, ~4 seconds saved total:
  - Replace OpenAI Whisper STT → Apple `Speech Framework` (on-device, instant, free)
  - Replace OpenAI TTS → Apple `AVSpeechSynthesizer` (on-device, instant, free)
  - Use iOS `SFSpeechRecognizer` end-of-speech detection (smarter than fixed timer)
  - Stream Claude LLM response and start TTS on first sentence
  - Use Haiku for short queries even on Plus tier
  - SiriKit Shortcuts: "Hey Siri, ask AI Advocate…" (replaces wake-word entirely)
- Estimated final perceived response: web ~7s → iOS native ~3s

### P0 — Verification
- User confirms on iPhone: splash circular mask perfect, gold labels look right, Try Lex Free + onboarding flow works

### P1 — Session 2 (Capacitor / native launch)
- Capacitor iOS/Android native wrap (capacitor.config.json already scaffolded)
- Swap Vault `localStorage` → native iOS Keychain / Android Keystore
- SiriKit Shortcuts (replacement for "Hey Lex")
- Apple's on-device Speech + TTS (replaces Whisper/OpenAI TTS on iOS)
- TestFlight beta (5-10 friends, 1 week)
- App Store metadata: screenshots (5 sizes), description, age rating, support URL, privacy/terms URLs (already exist), App Privacy declarations

### P2 — Post-launch (v1.1)
- Lex Confidence Check toggle (sources + confidence score)
- Verified Solicitor Marketplace (one-tap £49 30-min consultation, revenue split)
- Case Lifecycle Tracker (Filed → Awaiting → Hearing → Closed + push notifications)
- 2FA / authenticator-app login
- Trustpilot reviews wall (once 5+ reviews exist)
- iOS Siri Shortcuts / Action Button → Emergency mode
- Lex Auto-File + global search across cases

## Code Architecture
- `/app/backend/server.py` — FastAPI (Auth, LLM, Vault, GDPR, Contracts, Engagements, Webhooks, **🆕 `/lex/taster` + `/lex/taster/status`**)
- `/app/backend/app_crypto.py` — Fernet AES utilities
- `/app/frontend/src/App.js` — ~6100 lines, Consumer UI (do NOT refactor pre-launch). Includes new `WelcomeTour` + `TasterLex` components inside `AuthScreen`.
- `/app/frontend/src/FirmPortal.js` — B2B lawyer dashboard
- `/app/frontend/src/icons.js` — PNG icon wrappers
- `/app/frontend/public/icons/` — 22 optimized transparent 256×256 PNGs (1.3 MB total)
- `/app/frontend/public/privacy.html`, `/terms.html` — public legal pages for App Store
- `/app/frontend/public/assets/splash-clean.mp4` (119 KB), `splash-midframe.jpg` (28 KB)

## Critical Notes for Next Agent
- **Free taster Lex**: rate-limited by `device_id` (localStorage `aa_device_id`) + IP, 7-day window. Uses claude-haiku-4-5. Records to `taster_usage` MongoDB collection.
- **Onboarding tour**: shows once per browser based on localStorage `aa_welcomed`. Auto-opens TasterLex after tour completes (high-conversion pattern).
- **Emergent badge stripped** from `index.html` — DO NOT restore.
- **i18n auto-translation**: only English keys added in Session 1 for new flows. Other 10 languages will fall back to English keys until translated (intentional — auto-translate is the project's pattern).
