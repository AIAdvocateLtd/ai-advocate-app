# AI Advocate — Product Requirements Document

## Original Problem Statement
"AI Advocate" — a multilingual "lawyer in your pocket" application. Free, Plus (£14.99), and Pro (£34.99) tiers with tiered LLM access. Stripe live subscriptions for consumers + law firms. Vault encryption, evidence analysis, Lex chat, hearing recorder, contract hub, firm portal with case threads, courtroom practice, emergency rights. Native iOS/Android wrap via Capacitor.

## Target Users
- **Consumers** (UK/EU primarily, 11 languages supported) needing legal information
- **Law firms** (B2B Featured £49 / Premium £199 / Practice £399 tiers)
- **Lawyers** working B2B2C via Firm Portal

## Completed Implementation (rolling)

### 2026-02 (Session 2a — Live legal RAG + Hybrid Claude/GPT-5 + customisable bottom nav)
- **📚 Legal RAG grounding.** New `/app/backend/rag.py` calls **Tavily** twice per qualifying question — once filtered to UK authority domains (`legislation.gov.uk`, `bailii.org`, `judiciary.uk`, `supremecourt.uk`, `gov.uk`, `caselaw.nationalarchives.gov.uk`) and once for broader web. Snippets are numbered and appended to Lex's system prompt with explicit citation instructions, so every claim is traceable to a real URL.
  - Gracefully no-ops when `TAVILY_API_KEY` is empty — Lex still answers, just without grounding.
  - Smalltalk filter (`_looks_like_legal_question`) avoids burning credits on "hi" / "thanks".
  - Jurisdiction-aware (UK / Scotland / NI).
- **🧠 Hybrid Claude + GPT-5 routing** in `lex_model_for_tier`:
  - Free → `claude-haiku-4-5-20251001`
  - Plus → `openai/gpt-5.2` (conversational primary)
  - Pro / Yearly / trial_pro → `claude-sonnet-4-5-20250929` (Deep Think doubles token budget)
  - Existing fallback to Sonnet 4.5 if primary model rejects.
- **📱 Customisable bottom nav.** First slot (left of Vault) is now user-pickable via Settings → "Customise quick nav" — 8 options (Reminders / Vault / Cases / Lawyers / Hearings / Letters / Contracts / Legal Aid). Live-updates without reload via `aa:nav-slot1` event.
- **🎤 Microphone access moved to Settings.** New "Microphone access" card explicitly requests permission via `getUserMedia`; uses `navigator.permissions.query` to surface current state.
- Confirmed: "LEX" caption beneath the centre Lex button was already removed.
- Verified: backend pytest 6/6 PASS, frontend live-update verified by testing agent on 390x844.

### 2026-02 (Session 1i — Evidence-grade timestamping + Bottom-nav icon polish)
- **⚖ Recording timestamps + GPS for evidentiary use.**
  - Frontend `RecordModal` now captures wall-clock `started_at` + `ended_at` + computed `duration_seconds` + IANA timezone. Best-effort GPS captured (silently, on permission) at recording start.
  - Backend `/api/record/analyze` accepts the new Form fields and stores them. Also stamps a tamper-evident `server_received_at` independent of the client clock.
  - PDF export (`/api/pdf/file/{id}`) now opens with a prominent **⚖ EVIDENCE METADATA** block listing recording start, end, duration, timezone, GPS (with ±metres accuracy), server timestamp, and a file reference.
  - In-app result view shows the same metadata in a gold-bordered "Evidence Metadata" card above the transcript.
  - Verified end-to-end: inserted a synthetic record → fetched the PDF (HTTP 200, 408 KB) → extracted text via pypdf → confirmed all six evidence fields rendered correctly.
- **🎨 Bottom-nav icons fully gold.** Previously inactive items were `var(--text-muted)` (grey); now muted gold (`var(--gold-deep)` at 55% fill) inactive and bright gold (95% fill) active. Heraldic consistency end-to-end.

### 2026-02 (Session 1h — Sponsor Admin)
- **🛠️ Standalone admin page** at `/admin-sponsor.html` (phone-friendly, no React build). Sign in with admin email → live preview pill → toggle sponsor on/off → save.
- **`GET /api/admin/sponsor`** + **`POST /api/admin/sponsor`** — protected by existing `require_admin` (checks `ADMIN_EMAILS` env, default `admin@aiadvocate.co.uk`). Upserts into MongoDB `sponsor` collection.
- Public `/api/sponsor` reflects changes instantly — `SponsorFooter` component in the app picks up the new firm name + logo on next page load.
- Verified end-to-end: GET (admin) → POST activate → public endpoint shows "Hamilton & Co. Solicitors" → POST deactivate → public returns `{active:false}` → non-admin user gets 403 "Admin only".
- Admin password set: `AdminLex2026!` for `admin@aiadvocate.co.uk` (stored in `/app/memory/test_credentials.md`).

### 2026-02 (Session 1g — Partner pack + Sponsor slot + Case Timeline + Progressive reveal)
- **📄 Partner Pitch Card** (`/pitch-card.html`) — single-page A4 leave-behind PDF for law-firm sales. Print-ready, fully branded gold-on-black, includes tiers, key stats, pilot offer.
- **📚 Partner Introduction Pack** (`/intro-pack.html`) — 8-page A4 PDF: product overview, lead funnel, tiers + Founding Partner, security & compliance, liability architecture, Firm Portal, exclusivity options + sponsorship reservation, next-steps onboarding.
- **🤝 Sponsor slot** — `/api/sponsor` endpoint + `SponsorFooter` component. Currently dormant (no sponsor configured). When MongoDB `sponsor` collection has an active doc, a discreet "In partnership with [Firm]" pill renders on the home screen above the bottom nav.
- **🗺️ Case Timeline** — `/api/timeline` aggregates all the user's chats, deadlines, cases, and vault count into a chronological feed. `CaseTimeline` modal renders a vertical timeline with category icons, time-rail dots, time-ago labels, and stats strip. Tappable chat items resume the conversation. Designed as the App Store screenshot hero feature.
- **⚡ Progressive client-side reveal** for Lex replies — the full answer arrives in one chunk (true SSE blocked by Emergent SDK not yet exposing streaming), then types out at 30 chars per 25ms client-side. Same perception win as real streaming.

### 2026-02 (Session 1f — Tappable Connected-to chip)
- **🔗 "Connected to" chip is now clickable** — tap it to jump straight into that prior conversation thread (loads all its messages, switches session_id, smooth context switch).
- Backend: cross-sessions indexed with `#N` numbering. Lex now outputs `[CONNECTED_TO: #1 short topic]`. Backend regex extracts `#1`, looks up session_id from the indexed list, returns it as `connected_session_id` in the chat response.
- Frontend: parser strips `#N` prefix from chip text. Click handler calls `GET /api/lex/sessions/{id}` (existing endpoint) → replaces messages → updates sessionId. Hover state on clickable chip + external-link icon.
- Strengthened cross-case prompt rule: "If the user's NEW question shares a SPECIFIC entity (same company/landlord/property/contract/date) with any case in the list above, you MUST output [CONNECTED_TO: #N]." Verified: Acme deposit (Session A) + Acme employer (Session B) → Lex correctly outputs `[CONNECTED_TO: #1 Acme deposit dispute]` → backend resolves to Session A's UUID → frontend chip becomes a clickable gold-bordered link.

### 2026-02 (Session 1e — Clickable source citations)
- **🔗 Source chips are now clickable.** Each `[SOURCES:]` citation Lex produces is auto-routed to its official database:
  - UK statute (any "Act YYYY" / "s.X" / "Schedule X") → **legislation.gov.uk** search
  - UK case (pattern "X v Y") → **BAILII** search
  - EU regulation/directive → **EUR-Lex** search
  - Anything else → Google scoped to those 3 legal domains
- Tested 10 representative citations (Housing Act 2004 s.213, Donoghue v Stevenson [1932], Regulation (EU) 2016/679, etc.) — 100% routed correctly.
- Chips show external-link icon, hover state (gold border), open in new tab with `rel="noopener noreferrer"`, click-stop-propagation so tapping doesn't trigger parent message actions.
- This is the **single biggest differentiator vs. ChatGPT for legal users**: every claim Lex makes can be verified on the official source in one tap.

### 2026-02 (Session 1d — Lex Confidence Check + Connected-to chip)
- **🛡️ Lex Confidence + Sources visible in chat.** Every Lex answer now ends with three structured markers `[CONFIDENCE: HIGH|MED|LOW]` `[SOURCES: ...]` `[CONNECTED_TO: ...]`. Backend system-prompt enforces the format; frontend parses + strips them from the bubble and renders as colored pills below (green=HIGH, gold=MED, red=LOW) + grey source chips.
- **✨ "Connected to: …" chip** appears above the bubble when Lex links the new question to a prior case. Powered by the cross-session memory we built in 1c.
- Line-based parser handles `[2019]`-style case-citation brackets inside source values without breaking.
- Verified end-to-end: Turn 1 → HIGH + 2 sources + no connection. Turn 2 (new session referencing Acme from turn 1) → HIGH + 4 sources + "Connected to: Landlord deposit refusal" AND Lex spontaneously wrote strategic advice: *"mention in any settlement talks that you also have an outstanding £1200 deposit claim against them — combined pressure = more likely they'll settle both."*

### 2026-02 (Session 1c — Cross-session memory)
- **🧠 Cross-session memory**: `/api/lex/chat` now injects a one-line summary of the user's **other** recent chat threads into the system prompt. Lex can spot connections like "you were fired without warning after 3 years at Acme Ltd (we discussed earlier) — now they're withholding your final pay…" — but **only when there's a genuine link**.
- Verified end-to-end: A=dismissal at Acme → B=property → C=noise (clean, no false cross-links) → D=Acme final pay = **correctly carried the Acme/employment context across sessions**.
- Implementation: MongoDB aggregation pulls last 4 distinct session_ids excluding the current one, decrypts the first turn of each, builds topic list "[category] first 90 chars…", and appends as `RECENT CASES THIS USER HAS DISCUSSED WITH YOU` block. Failsafe: aggregation wrapped in try/except — if anything fails, just uses base system prompt.

### 2026-02 (Session 1b — Lex conversation memory + speed)
- **🧠 Lex now remembers context across turns.** `/api/lex/chat` now loads the last 12 conversation turns (decrypted from MongoDB), seeds `LlmChat.initial_messages`, so follow-up questions like "and?" / "what if photos?" / "the time limit?" carry full context from the prior dialogue.
- Added `CONVERSATION MEMORY` directive in `lex_system_prompt` so model explicitly links follow-ups back to prior facts (parties, dates, jurisdiction).
- **Speed: ~53s → ~25s per answer** (-53%). Reduced Sonnet `max_tokens` 2048→1400 + added concision instruction (200-450 words, 100-250 for follow-ups). Quality unchanged, generation time halved.
- iMessage-style typing indicator (3 bouncing gold dots) replaces static spinner.
- Phase-aware label: "Lex is reading the conversation…" on follow-ups vs "Lex is thinking…" on first message.

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
