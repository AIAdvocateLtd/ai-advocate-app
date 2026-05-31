# AI Advocate — Product Requirements Document

## Original Problem Statement
"AI Advocate" — a multilingual "lawyer in your pocket" application. Free, Plus (£14.99), and Pro (£34.99) tiers with tiered LLM access. Stripe live subscriptions for consumers + law firms. Vault encryption, evidence analysis, Lex chat, hearing recorder, contract hub, firm portal with case threads, courtroom practice, emergency rights. Native iOS/Android wrap via Capacitor.

## Target Users
- **Consumers** (UK/EU primarily, 11 languages supported) needing legal information
- **Law firms** (B2B Featured £49 / Premium £199 / Practice £399 tiers)
- **Lawyers** working B2B2C via Firm Portal

## Completed Implementation (rolling)

### 2026-02 (Iter 34 — Per-thread jurisdiction pill in Lex chat)
- ⚖️ **Inline jurisdiction pill** above the Lex chat input. Shows "Using **United Kingdom** law" by default, with a `ChevronDown` to expand a country picker (all 15 supported countries, with flags). Selecting a country sets `threadCountry` state which overrides the `country` field sent in `/lex/chat` + `/lex/chat/stream` requests — backend already reads `data.country` from the body, so the override is honored without backend changes. Verified via curl: same prompt with `country=FR` → French Labour Code; `country=GB` → Employment Rights Act 1996. The override is scoped to the current `LexChat` mount (resets to profile country when reopened). System prompt continues to handle natural-language overrides ("actually, this is about UK law") for free-form questions.



### 2026-02 (Iter 33 — Travel-aware jurisdiction banner)
- ✈️ **Friendly travel banner** for users abroad. Wired up the existing `/profile/auto-jurisdiction` flow now that the IP-geo fallback (Iter 32) actually works in production. When detected country ≠ profile country AND user hasn't pinned, a sticky banner appears at the top of the Dashboard with: country flag, full country names (mapped from `COUNTRIES`), reassuring note "*You can always ask Lex about UK law — just say so in your question*", and two CTAs: **Switch to France** / **Keep United Kingdom**. Decline persists server-side via `country_manually_set=true` so we never pester. Lex's system prompt already handles per-question jurisdiction overrides ("If they mention another country, switch and tell them you've done so" — `lex_system_prompt`).



### 2026-02 (Iter 32 — Demo deletion + Geo fallback + Location toggle fix)
- 🗑 **Demo mode fully removed (founder decision).** Deleted `/api/auth/demo` endpoint + 220-line sample-case seeder in `server.py`, the "Try a sample case" button on the auth screen, `DemoBanner` component, the demo-refresh 401 interceptor, and `is_demo` references throughout `App.js`. Defensive `is_demo: {"$ne": True}` filters in admin queries kept as harmless safety nets. App Store reviewers continue to use the dedicated `appstore.reviewer@aiadvocate.co.uk` account (separate from the deleted demo).
- 🔒 **Security fix — `/api/subscription/activate-test` lockdown.** This dev endpoint previously let ANY logged-in user grant themselves Pro for free by calling `POST /subscription/activate-test?plan=pro`. The frontend even exposed an "Activate PRO (demo / no payment)" button to everyone in the subscription modal. Both endpoint and UI now restricted: endpoint returns 403 unless email is in `ADMIN_EMAILS`, button removed. Verified with a regular test user → 403.
- 🌍 **Country detection fallback (was always empty in prod).** Emergent's Google ingress strips Cloudflare's `cf-ipcountry` header before it reaches the backend. Confirmed live — sending `cf-ipcountry: FR` to production returned `detected_country: ""`. Added a server-side IP→country lookup in `_ip_country` using `https://ipapi.co/<ip>/country/` (free, no API key, HTTPS, 2s timeout, 1-hour in-process cache). Verified: now returns `"US"` for the preview pod IP instead of empty.
- 📍 **Location toggle "stuck off" bug fix.** Previously, after turning off Location in Settings, users couldn't turn it back on if the browser permission was denied at the OS level — they'd see a vague `alert("Location blocked")` with no actionable path. Rewrote `toggleLocation` to: (a) probe `navigator.permissions.query` first and show a clear "Settings → Safari → Location → Allow" message when blocked, (b) fall back to low-accuracy retry on iOS Safari timeouts (err.code === 3), (c) replaced ALL `alert()` calls with `aaToast()` so the toggle never gets stuck due to a blocked dialog, (d) always reset `busy` state in every path.



### 2026-02 (Iter 31 — Firm logo: phone photo picker)
- 📷 **Firm portal — logo upload via phone photo library.** Replaced the text URL input in `BrandingModal` (`FirmPortal.js`) with a native file picker (`<input type="file" accept="image/*">`) + thumbnail preview + Remove button. On iOS/Android this opens the Photo Library directly. Backend (`PATCH /api/firm/branding`) now accepts either `https://` URLs (legacy) or base64 `data:image/...` URLs, with a 700KB cap. Validates `javascript:` / other schemes are still rejected. End-to-end curl + UI verified.



### 2026-02 (Iter 30 — Password reset, 2FA TOTP, Firm onboarding email, Pitch CTA)
- 🔑 **Forgot/Reset password — consumer + firm.** Both flows use a `/reset.html` self-contained page + Resend transactional email. Token: `secrets.token_urlsafe(32)`, 60 min TTL, single-use, MongoDB `password_reset_tokens` collection. Anti-enumeration: `/forgot-password` always returns 200. Rate limit: 3 requests per email per hour. Endpoints: `POST /api/auth/forgot-password`, `POST /api/auth/reset-password`, `POST /api/firm/forgot-password`, `POST /api/firm/reset-password`. UI: "Forgot password?" links on both consumer auth screen and FirmPortal auth screen.
- 🔐 **TOTP 2FA (pyotp + QR code) — opt-in for consumers.** Login state machine: if `totp_enabled`, `/auth/login` returns `{requires_2fa: true, tmp_token}` (5-min lifetime); frontend shows the 6-digit code challenge; `/auth/2fa/login` exchanges `tmp_token + code → full JWT`. Setup flow: `/auth/2fa/setup` → secret + QR data URL → user scans → `/auth/2fa/verify` (first code activates + returns 10 backup codes). Backup codes are bcrypt-hashed at rest, shown plain ONCE. Disable requires password + valid TOTP.
- 🏛 **Founding-firm onboarding email (Feature A)** — `admin_firms_comp` endpoint now auto-fires `send_firm_onboarding()` email when the founder comps a firm. Email contains tier/duration, portal URL, and a one-tap "Set password & sign in" reset link. Removes the friction of "what was my password?". Firm just clicks the link, sets a password, lands in portal. Endpoint returns `onboarding_email_sent: bool`.
- 🪪 **"Already a partner firm? Sign in →" button (Feature B)** added to the `/for-firms` pitch page CTA box, links to `/firm-portal`.
- New dependency: `pyotp==2.9.0` (added to `requirements.txt`). `qrcode` was already installed.
- 8 backend curl tests pass end-to-end (signup → forgot → reset → old-pw-rejected → new-pw-works → token-single-use → 2FA setup/verify → login-requires-2fa → tmp-token-exchange).

### 2026-02 (Iter 29 — Permanent Delete + Chinese mojibake fix + Translation gaps)
- 🗑 **Permanent Delete in Admin Comp Pro card** — new `POST /api/admin/users/delete` (soft-delete: `deleted: true`). Per-row red "Delete" button in Recent Users, Active Comps, and Founding 100 lists. Protected: `admin@`, `appstore.reviewer@`, `demo@` (server returns 400). Hides the user from every admin list permanently with one click.
- 🔄 **Revoke now auto-deletes** — `POST /api/admin/users/uncomp` defaults to `keep:false`, which both revokes Pro AND soft-deletes from the lists in one action. Pass `keep:true` to revoke without deleting (for legitimate users whose comp you want to end but still keep visible). Optimistic UI removes the row instantly.
- 🈯 **Chinese mojibake repair** — ~91 strings in `/app/frontend/src/i18n.js` (`zh-CN` ROUND12 block, lines 2700–2920) were UTF-8 bytes corrupted into Latin-1 (e.g., `ç¼ºå°æä¸ªæ³å¾é¢åï¼` → 缺少某个法律领域？). Repaired via deterministic `s.encode('latin-1').decode('utf-8')` with CJK-validation guard.
- 🌍 **Translation gap fix** — `Recycle Bin` + `Case Timeline` were hardcoded English on the dashboard tile and Case Timeline modal heading. Added `recycleBin` + `caseTimeline` keys to all 11 languages in ROUND12 block, wired via `t(lang, …)`.

### 2026-02 (Iter 28 — Founding-100 Admin Queue + Thank-You email)
- 🌟 **Founding 100 — Free Day Pass Queue** in Admin Comp Pro card. The landing-page promise ("first 100 signups get a free 24h Day Pass") is auto-honoured at signup (`launch_day_pass_until`), but the founder now has a visible queue to review each one.
  - `GET /api/admin/founding-100` — first-100 signups by `signup_position`, with day-pass status + dismiss flag + thanked flag. Filters out test/demo emails. Returns `slots_taken`/`slots_total`/`pending`.
  - `POST /api/admin/founding-100/dismiss` — manual "Skip" per row (optimistic UI shrink). Supports `undo:true` to bring back. Hard 400 if the user is not in the cohort (`signup_position > 100`).
  - `POST /api/admin/founding-100/thank` — primary "Approve & Thank" action. Fires a personal founder thank-you email (Resend) **and** auto-dismisses the row in one tap. Idempotent — returns `already_thanked` flag. Verified end-to-end with `sent: true` against the live Resend account.
  - New email template `send_founding_thank_you()` in `email_helper.py` — personal note from the founder, "founding member" framing, reply-to support@aiadvocate.co.uk.
  - Each row UI: position #, email, day-pass hours remaining, current comp status, **Approve & Thank** (gold) + **Skip** (ghost).
  - Cap behaviour: signup endpoint already stops awarding at 100 (`DAY_PASS_LIMIT`), so the queue naturally closes once full.
- ✅ Stripe Practice Tier Price ID confirmed live in `.env`: `price_1TcVaHFh8lRHrXPIGOKrL55T` (no code change needed — already pointing to env var).

### 2026-02 (Iter 27 — Auto-jurisdiction, Multi-seat firms, Custom branding, Founding Firm Agreement)
- 🌍 **Auto country/jurisdiction detection** — `GET /api/profile/auto-jurisdiction` reads CDN headers (cf-ipcountry, x-vercel-ip-country, x-country-code) and surfaces a one-tap banner if the user has travelled. **Never silently switches** — too important. `POST /api/profile/jurisdiction/accept` switches; `/decline` pins to stop asking. The existing `_check_geo_anomaly` was also upgraded to drive this prompt on login. `country_manually_set=True` is now stamped on every manual preference update so the auto-detector respects user choice.
- 👥 **Multi-user firm seats (firm_users collection)** — Premium/Practice/Practice tiers now support multiple fee-earners under one firm. New endpoints: `GET /api/firm/users`, `POST /api/firm/users/invite` (returns invite URL + token, 14-day expiry), `POST /api/firm/users/accept` (sets password + returns JWT), `POST /api/firm/users/login`, `DELETE /api/firm/users/{id}`. Seat limits enforced: free/featured = 1, premium = 3, practice = 5. Owner always counts as 1 seat. `get_firm` dependency now accepts firm-user JWTs (kind="firm_user") and resolves to the parent firm with `acting_user`/`acting_role` populated.
- 🎨 **Custom firm branding** — `GET/PATCH /api/firm/branding` for logo_url + brand_color + accent_color. Tier-gated to Premium/Practice (402 if Featured). Validates hex format and https-only URLs. Audit timestamp stored on update.
- 📄 **Founding Firm Agreement PDF** — `/app/backend/tools/generate_founding_firm_agreement.py` — one-page personalisable lifetime-£199 contract template. CLI args for firm_name/sra/address/contact/email. Exposed via `GET /api/admin/founding-firm-agreement.pdf` with same query params. Admin Solicitor Brief card now includes a 3rd download section with form fields.
- 🎯 **Founder Briefing PDF** — `/app/backend/tools/generate_founder_briefing.py` — 8-page internal briefing covering elevator pitch, all tiers, automation honesty table, tech stack, compliance Q&A, 30/60/90 roadmap, competitive landscape, tough-questions cheat sheet. Exposed at `GET /api/admin/founder-briefing.pdf`.
- 🧪 12 new pytest tests in `/app/backend/tests/test_firm_seats_branding_jurisdiction.py`, all passing.



### 2026-02 (Session 2k — Iter 26 · Admin Suggestions Inbox)
- 📬 **New backend endpoints** (admin-only):
  - `GET /api/admin/suggestions?status=open|resolved|all` — list with `open_count` badge
  - `PATCH /api/admin/suggestions/{id}` — mark resolved / reopen (with optional `admin_note`)
  - `DELETE /api/admin/suggestions/{id}` — permanent delete
- 🎨 **AdminSuggestionsCard** in Settings → owner-only. Collapsed shows "📬 Suggestions Inbox · N new" red badge. Expanded shows Open/Resolved/All filter pills + per-suggestion card with: user email, timestamp, message, "Mark resolved", "Reply" (mailto pre-filled), "Delete".
- 🔄 Suggestions are still also saved to the user's email app via mailto (best-effort backup), so the inbox is purely additive — no behavior change for end-users.
- 🧪 **5 pytest regression tests** in `/app/backend/tests/test_admin_suggestions.py`, all passing. Full suite: 32 passing.


- 🎭 **New endpoint `POST /api/auth/demo`** — one-tap login to a shared demo account with freshly-seeded sample data on every call. Returns a JWT and a user object with `is_demo: true`. No signup required.
- 🌱 **Seeded sample case**: "Sarah v. Acme Ltd — Unfair Dismissal" (employment, whistleblowing). Includes:
  - 3-turn Lex chat thread with realistic dialogue about whistleblowing protection under ERA 1996 s.103A
  - Lex-drafted formal grievance letter (encrypted in `legal_files`)
  - Witness statement note
  - Two reminders: ACAS Early Conciliation (in 7 days) + ET1 tribunal deadline (90 days from dismissal)
- 🪟 **"Try a sample case" button** on the auth screen (below the "Try Lex Free" taster) — gold-outlined CTA with subtitle "Explore a real Unfair Dismissal case — no signup needed."
- 🏷️ **Persistent demo banner** at top of app shell when `user.is_demo === true` — sticky, gold-tinted, with `DEMO` chip on the left and "Sign up" CTA on the right (logs user out, lands them on auth screen).
- 🔄 **Idempotent reset**: every call to `/auth/demo` wipes the demo user's data across 11 collections and reseeds — so every new demo session starts fresh (App Store reviewer #2 sees the same case as reviewer #1).
- 📊 **Analytics**: `track("demo_started")` fires on demo entry (PostHog).
- 🧪 **6 pytest regression tests** in `/app/backend/tests/test_demo_mode.py`, all passing.


- 🐛 **Files-vs-Cases explainer modal**: previously showed both sections regardless of where the user tapped the (?) icon, AND the explainer was hidden behind the underlying modal because of an inline `zIndex: 200` that overrode the `.modal-bg` z-index 9999. Fix: explainer now takes a `focus` prop (`"files"` or `"cases"`), renders only the section relevant to where the user tapped the (?), has a compact "vs."-style comparison line for the other concept, and an inner scroll container so the "Got it" button is always visible on any screen. z-index raised to 20000.
- ✉️ **"Missing a legal area?" suggestion modal** previously alerted "Could not send. Try again later." on any backend hiccup. Fix: now does best-effort backend POST + opens user's native email app (mailto:) pre-filled to `support@aiadvocate.co.uk` with subject "AI Advocate — Missing legal area suggestion". Success state explicitly tells the user to hit send in their email app.

### 2026-02 (Session 2k — Iter 23 · Per-case Timeline + Solicitor-handover PDF)
- 🆕 **New endpoint `GET /api/cases/{case_id}/timeline`** — merges 4 sources into one chronological feed: `case_opened` anchor, `case_items` (chats/photos/uploads/notes), every Lex chat `turn` from linked sessions (decrypted), and `deadlines`. Server-side sort, ready to render.
- 🎨 **In-app Timeline tab** — new tab switcher inside the case detail view ("📂 Files & uploads" vs "🕘 Timeline"). Timeline displays a vertical **gold thread** with icon nodes per event type, alternating layout, You:/Lex: formatting on turns, highlighted "case opened" anchor card.
- 📄 **Enhanced PDF export** at `GET /api/cases/{case_id}/export-pdf` — completely rewritten:
  - Cover header with "AI ADVOCATE · CASE FILE" eyebrow
  - Summary table (filed by, account, opened, total events, exported)
  - UPL disclaimer paragraph
  - Full chronological timeline (case opening + every Lex turn + uploads + deadlines)
  - SHA256 evidence hash per item
  - **Solicitor handover panel** on its own page — signature fields for client + solicitor + SRA number, designed to be torn off and handed over
  - Safe filename: `ai-advocate-{slug}-{caseid8}.pdf`
- 🧪 **Pytest regression** — 4 tests in `/app/backend/tests/test_case_timeline_feed.py`, all passing.
- ♻️ **Refactor**: extracted `_build_case_timeline()` helper so the JSON endpoint and PDF generator share one source of truth.

### 2026-02 (Session 2k — Iter 22 · Case Timeline ↔ Case Files wiring + landing page)
- 🐛 **Resume chat bug fixed** — tapping "open →" on a chat row in Case Timeline now re-hydrates the full conversation history and adopts the original session_id (was broken — opened a new empty thread before).
- 🪄 **Auto-promote chats → Case Files (Option A)**: When a session reaches 3+ turns and isn't already linked to a case, `_ensure_case_for_session()` auto-creates a Case File with a cleaned title ("I'm being bullied at work" → "Bullied at work"), inferred category, `source: "auto"` flag, and the chat thread attached as the first case item. Runs on every `GET /timeline` hit (cheap, idempotent).
- ✋ **Manual promote endpoint (Option B)**: `POST /api/cases/from-session` — one-tap "📂 Save as Case File" button on each chat row in the timeline. Accepts optional `name_override` and `category_override` so the user can rename on the spot. Idempotent: re-calling returns the existing case (no dup).
- 🏷️ **Timeline row now shows `linked_case_id`** — chats already filed under a case display "✓ Filed under Case Files" instead of the "Save as Case File" button.
- 📘 **"What's the difference?" explainer** — new `FilesVsCasesExplainer` modal accessible via a small "?" icon next to both "My Files" and "Case Files" titles. Cleanly distinguishes: My Legal Files = your stuff (filing cabinet); Case Files = the matters your stuff belongs to (folders).
- 🌐 **Pre-launch marketing landing** (`/welcome.html`) with waitlist form → backend `POST /api/waitlist/join` + admin CSV export at `/api/admin/waitlist.csv`. Root URL now redirects unauthenticated visitors to the landing page; authenticated users go straight into the app at `/`.
- 🎨 **Landing page UX fixes**: button text contrast fixed (gold→black not gold→dark-brown), reward copy changed from "first 500" → "first 100" sign-ups (scarcity converts better than generosity).
- 📦 **Instagram Content Pack delivered** (15 Nano Banana images + 8 Reels scripts + 5 Story sequences + bio rewrite + hashtag clusters), shipped at `/instagram-pack/`. **User feedback: visuals were too abstract — didn't show the actual app. Not used.** Pack archived in `/app/memory/INSTAGRAM_CONTENT_PACK.md` for reference, but the production strategy needs real iPhone screen-recordings to be useful.
- 🧪 **Pytest regression suite**: 6 tests for case-promote, 5 for waitlist — all passing.

### 2026-02 (Session 2k — Iter 21 · Abuse defenses + Winback Day Pass + SSE chat + Voice + UX fixes)
- 🐛 **CRITICAL Stripe webhook fix**: signed `checkout.session.completed` events were 500ing because `event["data"]` returned a `StripeObject` (no `.get()`). Now normalized via `json.loads(str(event))`. Resends from Stripe Dashboard will now succeed.
- 🐛 **Stripe redirect URL fix**: replaced fragile `request.headers["origin"]` with canonical `FRONTEND_URL` env var across all checkout flows (subs, top-ups, firm subs). Previously triggered 403 Forbidden when users had stale preview-domain tabs open.
- 🎙️ **Lex voice changed to Fable** (warm British male) across backend default and all frontend TTS calls. Voice sample comparison page kept at `/voice-samples/` for future reference.
- ⚡ **SSE streaming for Lex Chat** (`POST /api/lex/chat/stream`): emits `meta` event with citations + session_id INSTANTLY (~0.5s), then streams LiteLLM chunks, then `done` event with `connected_session_id` + full text. Frontend uses fetch + ReadableStream + smart client-side typewriter that handles either real token streaming OR proxy buffering (current Emergent proxy behaviour). Net UX: citations visible during "thinking", not just after the reply lands. Auto-fallback to `/lex/chat` if stream fails.
- 🛡️ **Anti-abuse defenses** (cheap, no-friction):
  - **Disposable email blocklist** (28 most-common throw-away domains rejected at signup with helpful error).
  - **Device-fingerprint signup cap**: max 2 signups per `device_id` per 24h → 429. Stable per-device UUID stored in `localStorage["aa_device_id"]`.
  - All other tightening (phone verify, account-age throttling, IP rate limiting) deliberately deferred — premature for pre-launch.
- 🎁 **Winback Day Pass** (lifetime once per account):
  - Fires when a free user has hit the daily chat cap (≥5) AND dismissed the upgrade modal ≥2 times.
  - `GET /api/winback/eligibility`, `POST /api/winback/dismiss-upgrade`, `POST /api/winback/claim`.
  - Claim activates a real Day Pass `topup_active` payload (24h Plus features) with `price_gbp:0` and `source:"winback"`. Marked `winback_gifted_at` so it can NEVER refire — even on reinstall.
  - `WinbackGiftBanner` UI on dashboard with gold gradient + 🎁 emoji + "Claim free Day Pass" CTA. Session-dismissible.
- 🐛 **Household size placeholder bug**: Legal Aid Finder no longer pre-fills `1` in the household-size input. Empty state → placeholder visible. Submit still defaults to 1 if blank.
- **Pytest regression suite** at `/app/backend/tests/test_winback_and_abuse.py` (6 tests, all passing).
- **All Phase A Stripe Top-up Price IDs configured** (Day £4.99, Letter £9.99, Weekend £14.99, Crisis £29.99). User completed one £14.99 purchase end-to-end before the webhook bug was found → manually activated their Day Pass in DB; webhook now fixed for all future purchases.

### 2026-02 (Session 2k — Consumer Top-up Packs · Phase A · Stripe Web)
- **One-off Stripe Checkout flow** for 4 consumer packs (no subscription, no auto-renew):
  - Day Pass — £4.99 · grants Plus features for 24h.
  - Letter Pack — £9.99 · 5 letters + 1 contract review · 30-day use-by.
  - Weekend Pass — £14.99 · full Plus features for 72h.
  - Crisis Pack — £29.99 · full Pro features for 24h (Hearing Recorder, Deep Think, RAG priority).
- **Backend endpoints** (`server.py` lines 2954-3125):
  - `GET /api/topups/packs` → catalogue + active top-up status + `configured` flag per pack.
  - `POST /api/topups/checkout` → returns Stripe Checkout URL for a one-time payment; 503 with helpful message if Stripe price ID not yet set in `.env`.
  - `POST /api/webhook/stripe` → on `checkout.session.completed` with `metadata.topup_pack`, calls `_activate_topup_for_user()` (idempotent — stores `topup_active` + `topup_history` on user row).
  - `user_to_public()` surfaces `topup_active` (kind, label, grants_tier, expires_at, hours_remaining) and applies the higher of (subscription tier, top-up tier) to gate features.
- **Frontend UI** (`App.js`):
  - `SubscribeModal` now has a tab switcher: "Subscriptions" / "One-time top-ups" (hidden on native iOS — Apple Reader-App compliance).
  - 4 pack cards with price, tagline, duration; Crisis Pack badged "PRO FEATURES". Disabled "Coming soon" state until Stripe Price IDs are populated.
  - `?topup=success&pack=<id>` URL handler shows a gold confetti-style toast and polls `/auth/me` 4× to refresh the new tier post-webhook. URL is cleaned via `history.replaceState`.
  - Active-top-up pill on the dashboard showing "ACTIVE TOP-UP · <label> · grants PRO · Xh left".
- **`.env` scaffolding** added: `STRIPE_PRICE_TOPUP_DAY_PASS`, `_LETTER_PACK`, `_WEEKEND_PASS`, `_CRISIS_PACK` (empty — user populates after creating one-time prices in Stripe Dashboard).
- **Tested**: 8/8 backend pytest PASS (`/app/test_reports/iteration_20.json`). Frontend manually verified — all 4 cards, tab switcher, gift banner, all data-testids present. Lint clean.
- **Phase B (deferred)**: Apple IAP receipt validation — wire after TestFlight build is live. Top-ups will use Apple StoreKit on iOS, Stripe on web.

### 2026-02 (Session 2j — Firm Free Trial + Founding Firms admin tool)
- **Auto 14-day Featured trial** on every new firm signup (no card required up-front — convert-to-paid is a separate Stripe checkout step).
- **`_firm_tier()`** now returns the trial tier (Featured / Premium / Practice) while `trial_until` is in the future; falls back to the paid tier or 'free' otherwise. Single source of truth for every firm-side paywall.
- **Owner admin endpoints**:
  - `POST /api/admin/firms/comp` — grant N days of a chosen tier (with stacking; if a trial is already active, days add on top).
  - `POST /api/admin/firms/uncomp` — instantly revoke an active trial.
  - `GET /api/admin/firms/comps/active` — list every firm currently on a trial with days remaining.
  - `GET /api/admin/firms/search?q=` — autocomplete search across email / firm name / city.
  - Full audit trail in `firm_comp_audit`.
- **`<CompFirmAdminCard />`** rendered in Settings (owner-only, next to the user comp card). Tier picker (Featured / Premium / Practice), days picker (14 / 30 / 60 / 90), reason field, autocomplete search, active-trials list with per-firm revoke.
- **🎁 Trial banner in Firm Portal** — gold-themed card at the top of the firm dashboard showing the active trial tier + days remaining + "Convert & lock in" upgrade CTA. Turns red below 7 days.
- **Backend tested end-to-end**: fresh signup → 14d Featured; owner grant → stacks +90d to Premium; `effective_tier` resolves correctly through `/firm/me`. JS lint clean.

### 2026-02 (Session 2i — App Store Metadata + Reviewer Demo Account)
- **`/app/memory/APP_STORE_METADATA.md`** — full ship-ready copy for both App Store Connect + Google Play Console: name, subtitle, keywords, 4000-char description, "What's New" v1.0 release notes, support/marketing/privacy URLs, App Privacy Nutrition Labels mapping, IAP product IDs, screenshot shot-list, App Preview video direction, TestFlight pre-launch checklist, launch-day social posts.
- **Apple App Store reviewer account live** — `appstore.reviewer@aiadvocate.co.uk` / `Review2026!Lex`, comped Pro until 2053-10-08 (effectively permanent). Created via `/api/auth/signup` + `/api/admin/users/comp` (9999 days). Recorded in `/app/memory/test_credentials.md`.
- **App Store icon generated** — `/app/frontend/public/icons/app-icon-1024.png`, 1024×1024 RGB (no alpha), dark `#0a0a0a` background, gold shield + wordmark centred with 11% margin. Apple-compliant. Verified visually.
- **`@capacitor/assets` installed** + staged `assets/icon-foreground.png`, `assets/icon-only.png`, `assets/splash.png` (2732×2732 with centred logo). Once user picks shield-only vs wordmark variant, single `npx capacitor-assets generate` produces every iOS + Android size in one step.
- **Plus pricing migration complete** — Stripe price ID swapped to `price_1TagTTFh8lRHrXPIerlsHVtC` (£19.99), backend `/api/subscriptions/plans` returns 19.99, all 11 i18n languages updated, terms.html + marketing-site copy updated. Old `price_1TX0CcFh8lRHrXPI3feMOlOx` archived in Stripe.
- **Recycle Bin moved to dashboard** (gold-matched custom Nano-Banana icon, hue-shifted from copper to amber-gold to match the other tiles).

### 2026-02 (Session 2h — Legal & Compliance hardening for App Store)
- **T&Cs v1.3** (`/app/frontend/public/terms.html`): Added Legal Services Act 2007 reference; explicit "Not a replacement for 999/112/911" in §4d Emergency SOS; 14-day cooling-off period under UK CCR 2013 in §6; two-party-consent foreign-recording warning in §4; sponsored-firms disclosure in §11; ICO registration reference + DPIA mention in §12.
- **18+ Age Gate**: Added confirmation checkbox to `TermsScreen` — accept button disabled until both T&C agreement AND "I am 18+" boxes are ticked. App Store 17+ rating evidence.
- **Persistent UPL footer in Lex Chat**: small "AI-generated legal *information*, not legal advice — always verify with a regulated solicitor" footer below the chat input on every Lex surface.
- **First-use UPL acknowledgment modal**: Shown the first time a user opens Lex. Lists what Lex is (information assistant) and isn't (a solicitor). Persisted per-device via `aa_lex_upl_ack`.
- **Cookie / PECR consent banner**: Persistent bottom banner on first visit with "Essential only" / "Accept all" choice; persists in localStorage. PostHog analytics is now gated — `ensureInit()` refuses to initialise until consent is granted, honouring `respect_dnt` browser flag.
- **999 / Emergency Services banner**: Prominent tappable red banner at top of Emergency modal — `tel:999` direct dial, with EU 112 and US/CA 911 reminders. Coroner-report risk mitigation.
- **DPIA template** at `/app/memory/DPIA.md` — full ICO-compliant DPIA scaffold covering lawful bases, processing description, retention, risk assessment, and sign-off section ready for your solicitor / DPO.
- **Pricing left as-is** for now (£14.99 / £34.99 / £319.99) — these touch live Stripe price IDs and need an explicit decision before changing.

### 2026-02 (Session 2g — Capacitor 7 wrap prep)
- **Installed Capacitor 7** (`@capacitor/core`, `@capacitor/cli`, `@capacitor/ios`, `@capacitor/android`) and all essential plugins: Geolocation, Filesystem, Share, Preferences (Keychain/EncryptedSharedPreferences), SplashScreen, StatusBar, App, Haptics, Network, Device, Clipboard, Keyboard, Browser.
- **`/app/frontend/capacitor.config.json`** polished — `uk.co.aiadvocate.official` app id, dark splash bg, status bar config, keyboard resize, iOS contentInset, no insecure mixed content.
- **`/app/frontend/src/nativeBridge.js`** — thin platform-detection layer (`isNative()`) with web fallbacks for every native API: `getPosition`, `share`, `secureGet/Set/Remove`, `openExternal`, `vibrate`, `getNetworkStatus`, `hideSplash`, `addAppListeners`. Lazy-imports each Capacitor plugin so the web bundle stays small.
- **Two surgical wires:** (1) `hideSplash()` called when auth resolves so the native launch image fades when React is ready; (2) citation pills route through Capacitor `Browser` (Safari View Controller / Chrome Custom Tab) on native — required for App Store approval (no Safari bounces).
- **Reference docs** for the user's local Xcode/Android Studio build:
  - `/app/frontend/BUILD_INSTRUCTIONS.md` — prerequisites, day-to-day workflow, iOS/Android release steps, Vault-key migration recipe.
  - `/app/frontend/IOS_INFO_PLIST.md` — every privacy usage description string verbatim (Location, Microphone, Camera, Photos, Speech, Face ID), background-mode notes, Apple Sign-in entitlement.
  - `/app/frontend/ANDROID_MANIFEST.md` — full `<uses-permission>` block, `<queries>` for SMS intent visibility, `allowBackup="false"`, Universal Link / App Link snippets, network-security config.
- **Tested**: lint clean. `yarn build` succeeds (16s). Web preview boots without errors. No regression — `isNative()` returns false on the web so every native code path is a no-op outside Capacitor.

### 2026-02 (Session 2f — Bug-fix + Citation Pills)
- **🛠 Replaced `window.confirm()` / `alert()` with in-app modal + toast** — root cause of "delete buttons don't work" reports was Brave/iOS suppressing native dialogs. New `<AAConfirmHost />` + `aaConfirm()` / `aaToast()` are gold-themed, always-visible, mounted at app root. Affected flows: legal-files delete + save-to-vault, case delete + case-item delete + case-item save-to-vault, recycle-bin restore + purge + empty-all, timeline save + clear, hearing/encounter save-to-vault.
- **🗑 Recycle Bin moved from Settings to dashboard** — new gold tile (between Reminders and Letter Library) using a custom-generated `recycle.png` icon (Nano Banana, transparent BG, hue-shifted to match the existing gold palette).
- **📜 Clickable Citation Pills** — `[1] [2]` markers in Lex responses are now tappable gold pills that open the actual BAILII / legislation.gov.uk source. Backend: `build_rag_context()` now returns `(prompt_block, citations[])`; `/api/lex/chat` exposes `citations: [{n, title, url, source}]`; conversations DB stores citations on the row so they survive reload; `/api/lex/sessions/{id}` re-hydrates them. Frontend: `renderWithCitationPills()` parses `[\d+]` markers + a Sources-Cited footer renders under each Lex bubble.
- **🚨 Emergency Contacts cleanup** — server-side filter drops contacts with name < 2 chars OR phone < 7 digits on both GET and POST, so stale "M / +447700111" entries from earlier sessions disappear.
- **Tested**: 10/10 backend pytest PASS — see `/app/test_reports/iteration_19.json` and `/app/backend/tests/test_iter19_citations.py`. JS lint clean.

### 2026-02 (Session 2e — Recycle Bin + Soft-delete + Merged Record tile + Timeline Save/Clear)
- **🗑 Recycle Bin (30-day soft-delete recovery)** — every delete in the app is now non-destructive. Affects: legal_files, cases, case_items, conversations, reminders, hearings. New collection-agnostic endpoints: `GET /api/recycle-bin`, `POST /api/recycle-bin/restore/{kind}/{id}`, `DELETE /api/recycle-bin/{kind}/{id}`, `DELETE /api/recycle-bin` (empty all). Background sweeper (every 6h) hard-purges items older than 30 days. New `RecycleBinCard` collapsible in Settings shows per-item days-left, Restore + Permanently-Delete + Empty-bin.
- **🎙 Merged Record tile** — the separate "Record Legal Interaction" and "Hearing Recorder" tiles are gone. One tile (using the Hearing/vintage-mic icon) opens a new `RecordHub` modal with two mode pills: 🚔 *Encounter* (Plus, default — panic-mic + auto-GPS) and 🏛 *Hearing* (Pro — title field + file-upload). Mode persists in localStorage.
- **🚨 Emergency Contacts auto-save on remove** — trash button on contact rows now POSTs immediately, so stale rows can't reappear after re-opening Settings.
- **📁 Case Files: per-item delete + upload + Save to Vault** — each case-item has its own trash button (soft-delete via `DELETE /api/case-items/{id}`) and a "🛡 Save to Vault" button. Cases now also expose `POST /api/cases/{id}/upload-file` (multipart, ≤50MB, SHA256-hashed, metadata-only) to attach arbitrary docs/photos/audio/video.
- **🗂 My Legal Files: Save to Vault** — detail view gained a new Save-to-Vault button alongside Download PDF / Delete. Hearing & Encounter result panes also gained the Save-to-Vault action.
- **📜 Case Timeline upgrades** — items are now clickable: `chat` opens the chat, `deadline` opens Reminders, `case` opens that case directly. New **Save timeline** button snapshots the current view to `legal_files` (`POST /api/timeline/snapshot`). New **Clear timeline** button (`DELETE /api/timeline`) soft-deletes chats + reminders; if unsaved, prompts to save first.
- **Backend**: soft-delete filter `{deleted_at: {$in: [None, '', False]}}` added to all list/get queries. Cascading restore for cases (items with `deleted_with_case: true` restore alongside the parent).
- **Tested**: backend 13/13 PASS — see `/app/test_reports/iteration_18.json` and `/app/backend/tests/test_iter18_recycle_bin.py`. JS lint clean.

### 2026-02 (Session 2d — Embassy quick-dial + Multi-contact SOS + Lawyer Standby + Covert Watch SOS)
- **🏛 Embassy / Consulate quick-dial** — built-in directory of 25 British FCDO consulates (Iraq, UAE, Turkey, Egypt, Thailand, India, Pakistan, US, China, Russia, France, Germany, Spain, Italy, Greece, Morocco, Saudi, Qatar, Japan, Australia, South Africa, Nigeria, Kenya, Brazil, Mexico). Unknown country falls back to the FCDO 24/7 emergency line (+44 20 7008 5000). New endpoints: `GET /api/embassy/lookup?country=XX`, `GET /api/embassy/all`. Tappable button in Emergency Modal.
- **📍 Geo-sorted lawyer finder** — "Nearest lawyers to you" section in Emergency Modal pulls top-3 firms within 50km via the existing `/api/lawfirms?latitude=&longitude=&max_km=` endpoint. One-tap call buttons.
- **🚨 Multi-contact SOS** — replaced the single `emergency_contact_phone` field with unlimited contacts (name, relationship, phone, `include_in_sos`, `is_lawyer` star flag). One contact can be marked "My Lawyer" — exclusivity enforced both client-side and on save. New endpoints: `GET/POST /api/emergency/contacts`, `GET /api/emergency/sos-history`. New Settings card `EmergencyContactsCard`.
- **⚖ Lawyer Standby fallback** (Pro tier) — if SOS fires with no contact ACK in 60s, pings TOP-3 nearest opted-in Premium/Practice firms simultaneously inside a configurable radius (5–100km). Stored in `db.firm_emergency_pings` for firm-side pickup with a 90s accept window.
- **⌚ Covert Watch SOS** — new `POST /api/emergency/watch-token` issues a private rotatable token; `GET /api/emergency/silent-sos?wt=<token>&lat=&lng=&src=watch` fires SOS with NO Authorization header — works from any smartwatch via a one-tap URL Shortcut (Apple Watch Shortcuts complication / Wear OS HTTP-Shortcuts tile). Always silent on the user's phone. Sets `duress=true`. Token can be rotated to invalidate. Setup guide built into the Settings card.
- **Tested:** backend 12/12 PASS (1 env-skipped) · frontend all key Settings flows + "My Lawyer" exclusivity verified by Playwright on mobile 390x844 (see `/app/test_reports/iteration_17.json`).

### 2026-02 (Session 2c — Whisper Mode + Translation Mode + T&Cs v1.1)
- **🌍 Translation Mode** (3rd tab in Courtroom Trainer). Bidirectional live interpreter for travellers stopped abroad. Powered by Whisper (STT) + Claude (translation) + OpenAI TTS (playback). 53-language picker (Whisper's full list — Arabic, Mandarin, Urdu, Hindi, Swahili, etc.). Other party's speech → translated + safety tip + suggested reply. User reply → translated → spoken aloud in their language. Pro tier only.
  - New backend endpoints: `POST /api/lex/translate`, `GET /api/lex/translate/languages`.
  - New frontend components: `TransReplyBar`, full Translation panel in `CourtroomModal` with consent gate.
  - RTL rendering for Arabic / Farsi / Hebrew / Urdu.
- **🔊 Whisper Mode** — TTS read-aloud on the Live Legal Assist SAY THIS card. Tap "Listen" to play Lex's suggested reply through AirPods. "Auto" toggle remembers preference in localStorage.
  - **Court-proximity guard** (uses existing `recordingLaw.detectNearCourt`) auto-disables audio output near courthouses, with one-tap user override stored in sessionStorage.
- **📜 T&Cs v1.1** — added sections 4a (Whisper Mode), 4b (Translation Mode), 4c (Cross-border data flow). Footer bumped to v1.1.
- Tested: backend 8/8 PASS · frontend 100%.

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
