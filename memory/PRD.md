# AI Advocate — Product Requirements Document

## Original Problem Statement
"AI Advocate" — a multilingual "lawyer in your pocket" application. Free, Plus (£14.99), and Pro (£34.99) tiers with tiered LLM access. Stripe live subscriptions for consumers + law firms. Vault encryption, evidence analysis, Lex chat, hearing recorder, contract hub, firm portal with case threads, courtroom practice, emergency rights. Native iOS/Android wrap via Capacitor.

## Target Users
- **Consumers** (UK/EU primarily, 11 languages supported) needing legal information
- **Law firms** (B2B Featured £49 / Premium £199 / Practice £399 tiers)
- **Lawyers** working B2B2C via Firm Portal

## Completed Implementation (rolling)

### 2026-02 — current session
- **Splash black-box fix** — Crushed video vignette to pure #000 via contrast filter + radial mask. Logo floats free on black, no rectangular boundary.
- **Icon transparency + size optimization** — 22 dashboard icons reprocessed: 1024×1024 RGB (10.5 MB) → 256×256 RGBA (1.3 MB), 89% smaller. Originals backed up.
- **Tap-highlight removal** — Global CSS kill of iOS/Android tap rectangle, custom press feedback on tiles (scale + glow, no box).
- **Startup performance** — `<link rel="preload">` for splash MP4 + poster, instant CSS-only first-paint logo before React mounts.
- **Page title** — Fixed to "AI Advocate — AI Lawyer in your Pocket"

### Earlier sessions (recap from prior handoffs)
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
- Estimated final perceived response: web ~7s → iOS native ~3s

### P0 — Verification
- User confirms on iPhone: icons no longer show boxes, app loads fast, splash has no visible boundary

### P1 — Phase 2 (mobile launch)
- Capacitor iOS/Android wrap (capacitor.config.json already scaffolded)
- Swap Vault `localStorage` → native iOS Keychain / Android Keystore
- First-time onboarding tour (3-4 swipeable cards)
- First-run free 1-question Lex chat without signup
- "Hey Lex" discovery card in Settings

### P2 — Phase 3
- Lex Confidence Check toggle (sources + confidence score)
- 2FA / authenticator-app login
- Trustpilot reviews wall (once 5+ reviews exist)
- iOS Siri Shortcuts / Action Button → Emergency mode
- Lex Auto-File + global search across cases

## Code Architecture (unchanged)
- `/app/backend/server.py` — FastAPI (Auth, LLM, Vault, GDPR, Contracts, Engagements, Webhooks)
- `/app/backend/app_crypto.py` — Fernet AES utilities
- `/app/frontend/src/App.js` — ~5900 lines, Consumer UI (do NOT refactor pre-launch)
- `/app/frontend/src/FirmPortal.js` — B2B lawyer dashboard
- `/app/frontend/src/icons.js` — PNG icon wrappers (now using transparent PNGs)
- `/app/frontend/public/icons/` — 22 optimized transparent 256×256 PNGs (1.3 MB total)
- `/app/frontend/public/icons_originals_backup/` — Pristine 1024×1024 originals (~10.5 MB)

## Critical Notes for Next Agent
- **Icons are now RGBA** with transparent backgrounds. Never restore from `icons_originals_backup/` without re-processing — that would bring back the black boxes.
- **Splash CSS in two places**: React component `App.js:~5306` + first-paint poster in `index.html`. Keep mask/filter values in sync if tuning further.
- **iOS PWA hard-refresh**: Users must close Safari tab + reopen to clear cached CSS.
