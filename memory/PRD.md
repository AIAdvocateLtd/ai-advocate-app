# AI Advocate — Product Requirements Document

## Original Problem Statement
"AI Advocate" — a multilingual "lawyer in your pocket" application. Free, Plus (£19.99), and Pro (£34.99) tiers with tiered LLM access. Stripe live subscriptions for consumers + law firms. Vault encryption, evidence analysis, Lex chat, hearing recorder, contract hub, firm portal with case threads, courtroom practice, emergency rights. Native iOS/Android wrap via Capacitor.

## Target Users
- **Consumers** (UK/EU primarily, 11 languages supported) needing legal information
- **Law firms** (B2B Featured £49 / Premium £199 / Practice £499 tiers)
- **Lawyers** working B2B2C via Firm Portal


### 2026-02 (Iter 59 — GDPR export human-readable HTML companion)
- User feedback: the JSON export "looks messy and difficult to read" (correct — JSON is machine-readable by design, not human-readable).
- Added `_render_user_export_html()` in `server.py` — renders the export payload into a fully-styled standalone HTML page with:
  - Gold-accented headings matching AI Advocate brand + light/dark mode CSS variables
  - User profile section as a clean table (email, country, subscription, last login, etc.)
  - Ask Lex conversations rendered as Q&A cards (question in gold box, reply properly markdown-parsed — headings, bold, italic, links, blockquotes, lists, horizontal rules all converted correctly)
  - Case files with timeline entries as blockquotes
  - Uploaded documents, reminders, Vault metadata as tables
  - Source citations as bulleted links per Lex response
  - Mini-markdown parser (`md_to_html`) handles `#`/`##`/`###` headings, `**bold**`, `*italic*`, `[text](url)` links, `- lists`, `> blockquotes`, `---` HR, and paragraph splitting on double newlines. Not a full CommonMark parser — just Lex's output patterns.
- Updated `POST /users/me/export-email`: now attaches BOTH `ai-advocate-export-YYYY-MM-DD.html` (11 KB, human-friendly) AND `ai-advocate-export-YYYY-MM-DD.json` (18 KB, GDPR-required machine-readable). Email body explains which to open for reading vs importing.
- curl-verified: HTTP 200, 30 KB combined attachment size sent to `appstore.reviewer@aiadvocate.co.uk`.
- Playwright preview verified visually — Q&A cards render cleanly, gold gradient headers, proper spacing, mobile-responsive.



### 2026-02 (Iter 58 — CRITICAL: Password hash leak in GDPR export fixed)
- 🚨 **Bug**: `_build_user_export()` projection used `hashed_password: 0` but the actual DB field is `password_hash` (single word, singular). Projection was a no-op → **bcrypt password hashes were included in every /users/me/export response and email attachment**. User discovered on TestFlight Build 15 when previewing the emailed JSON — saw `"password_hash": "$2b$12$..."` in plain view.
- ✅ **Fix**: Removed field-name projection (typo-fragile). Replaced with post-fetch `pop()` of an explicit deny-list: `password_hash`, `hashed_password`, `totp_secret`, `totp_backup_codes`, `email_verify_token_hash`, `password_reset_token_hash`, `apple_id`, `google_id`, `webauthn_credentials`. Belt-and-braces so a future typo can't re-leak.
- ✅ **Verified**: curl against `appstore.reviewer@aiadvocate.co.uk` — sensitive fields = NONE. User dict now contains only: auth_provider, comp_pro_*, country, created_at, email, email_verified*, full_name, id, language, last_login_*, stripe_customer_id, stripe_subscription_id, subscription_status, terms_accepted, trial_*_date. All legitimate GDPR export fields.
- 📊 **Risk**: LOW in practice — app is not publicly launched, only founder has used export, bcrypt cost 12 = infeasible offline crack, no known real user hashes exposed.
- 🚀 **Deploy required**: This is a backend-only fix. No new TestFlight build needed — user's iPhone will get the clean export as soon as production is redeployed.



### 2026-02 (Iter 57 — Apple Guideline 2.1 Rejection Fixes)
- ⚖️ **iOS keyboard fix (Ask Lex chat input)**: Root cause was Capacitor `Keyboard.resize: "body"` mode which pads only `<body>`, leaving `position: fixed` modals anchored to full viewport (behind keyboard). Switched to `resize: "native"` (WebView shrinks with keyboard). Added `@capacitor/keyboard` event listeners (`keyboardWillShow/Hide`) that publish `--kb-height` CSS var. `.modal-bg` height now `calc(var(--vvh, 100dvh) - var(--kb-height, 0px))`. Input rises above keyboard exactly like Safari web behaviour. Files: `capacitor.config.json`, `nativeBridge.js:attachKeyboardListeners`, `App.js` global useEffect, `index.css:.modal-bg`.
- 📱 **iOS viewport hardening**: Added `maximum-scale=1, user-scalable=no` to viewport meta (blocks pinch-zoom + iOS auto-zoom into inputs under 16px). Set `overflow-x: hidden` and `max-width: 100vw` on html/body/#root to kill horizontal panning. Added `overscroll-behavior-y: none` to prevent iOS rubber-band bounce. Bumped `.input` font-size 15px→16px. Global rule sets all `input, textarea, select` to 16px minimum.
- 📧 **GDPR export switched to email delivery**: iOS Capacitor Filesystem + Share pipeline hangs silently at unknown step (verified via 5-alert diagnostic Build 14 — user got past ①②③④ into `native.exportFile` but never returned). Rather than continue chasing native SDK bug, switched to industry-standard email-based export (GitHub, Google Takeout, LinkedIn all use this pattern). New endpoint `POST /api/users/me/export-email` calls shared `_build_user_export()` helper, base64-encodes JSON, sends via Resend as attachment. Frontend button label: "Email me my data" (Mail icon). curl-verified: HTTP 200, 19 KB attachment sent to `appstore.reviewer@aiadvocate.co.uk`. Works identically on iOS, Android, and Web — zero native plugin dependencies.
- 🏛 **Apple App Review reply drafted** (`/app/memory/apple_response_v1.md`): 3,969 characters (under Apple's 4,000-char Resolution Center limit), covers all 6 Guideline 2.1 information-needed points including regulated-industry disclosure quoting SRA guidance on unregulated legal-information providers.
- Rationale: Apple reviewer rejected on Guideline 2.1 (information needed) + iOS keyboard bug in Ask Lex. Both blockers now resolved. Pending: user rebuilds Xcode Build 15+ with all fixes, records fresh TestFlight screen recording, replies in Resolution Center + attaches recording.



### 2026-02 (Iter 56 — SRA Compliance Pack while Apple reviews)
- ⚖️ **Enhanced UPL footer** under every Lex chat surface (`data-testid="lex-upl-footer"`). Old: "AI-generated legal information, not legal advice. Always verify with a regulated solicitor before acting." **New**: "AI Advocate is **not a law firm** and is not SRA regulated. AI-generated legal information, not legal advice — always verify with a regulated solicitor." Meets SRA public-facing disclosure requirement + is visible on every chat exchange (not just once per session).
- 📌 **Per-response "not legal advice" tag** rendered below every Lex assistant bubble (`data-testid="lex-not-advice-{i}"`). Small muted italic line: "This is legal information, not legal advice." Auto-appended after every reply — no user dismissal, no session flag, always visible. Belt-and-braces on top of the persistent chat footer.
- 🤝 **Referral programme transparency card** added to Settings (`data-testid="settings-referral-transparency"`). Explains that partner organisations, Citizens Advice branches, and law firms may receive a fee (typically 20–30% of first subscription payment) when a user signs up with their partner code. States clearly: "the referral fee is paid by AI Advocate out of our margin — you never pay extra." Shows the linked partner code if present (`settings-referral-partner-code`) or "No partner referral is linked" (`settings-referral-none`). Meets SRA / CMA transparency-of-financial-incentives rules.
- ✅ **GDPR data export verified live** — curl'd `GET /api/users/me/export` against `appstore.reviewer@aiadvocate.co.uk` and got HTTP 200 · 17.5 KB structured JSON with 11 top-level keys (user, conversations, cases, case_items, legal_files, reminders, feature_requests, vault_items_metadata, export_generated_at, format_version, notes). Frontend button `data-testid="export-data-btn"` in Settings → Manage My Data was already wired to this endpoint. Confirmed working end-to-end — no user action needed.
- Rationale: Bulletproofs the app against UK legal-services compliance risks BEFORE public App Store launch. No code refactor, purely additive UI changes — safe to ship while Apple is reviewing.



### 2026-06 (Iter 55 — CFC Insurance Proposal PDF v4 final)
- 📄 **`CFC_Tech_Proposal_Form_AI_Advocate_v4_FINAL.pdf`** generated at `/app/frontend/public/`. Rebuild from clean DRAFT via `/tmp/patch_v4.py`.
- ✅ **MFA section corrected**: ticked **No** (was incorrectly Yes in v3). Truthful explanation written into `Why_MFA_is_not_enabled` — clarifies the founder uses SSH-key auth + Google MFA, no PCI data is stored (Stripe holds it), end-user OAuth (Google/Apple) inherits provider MFA, native user-side MFA is on the Q2 2026 roadmap.
- ✅ **£ duplication fixed**: revenue fields now contain plain numbers (form has pre-printed £ glyph next to each cell).
- ✅ **Registered Address fixed**: was duplicating company name; now reads "20-22 Wenlock Road, London, N1 7GU, United Kingdom" + ICO/Co. number on the continuation line.
- ✅ **Font consistency**: every text widget forced to Helvetica with content-aware size tier (10 → 9 → 8 → 7 pt) so long paragraphs no longer shrink to micro-print while short fields stay readable.
- ✅ **Flattened** via `doc.bake()` so all X-marks and field values bake into permanent ink (renders identically in Adobe, Preview, Chrome, Firefox).
- 🔍 Verified by `analyze_file_tool` on pages 1 (address + revenue table), 5 (MFA), and 7 (Additional info block).


### 2026-06 (Iter 54 — Email Verification Hard Gate + Turnstile Runtime Fix)
- 🔐 **Email verification (Hard Gate)** for email/password signups. New accounts get `email_verified=false`, receive a Resend-powered email with a one-click link, and **cannot use any protected endpoint** until they click it. Google/Apple sign-ins are auto-verified (provider already confirmed the email). Existing users are grandfathered on startup via a one-time `email_verified=true` backfill — no one currently using the app gets locked out.
- 🆕 Endpoints: `POST /auth/verify-email` (token exchange → fresh JWT), `POST /auth/resend-verification` (rate-limited 3/hour/email, 5/hour/IP), `GET /auth/verify-status` (frontend polls so other-tab clicks auto-progress).
- 🆕 Frontend: `EmailVerifyScreen` component with **email shown**, **Resend** button (30s UI cooldown), **Wrong email — sign out** escape hatch, and **4-second polling** that auto-progresses when the user verifies elsewhere. Global axios interceptor catches 403 + `code: "email_not_verified"` and routes any unverified user back to the verify screen. `/verify-email?token=xxx` URL handler exchanges token for JWT and auto-logs the user in.
- 🛡 **Turnstile runtime fix (root cause of last 5 hours of debugging)**: Site key now fetched from `/api/auth/providers` at runtime instead of being baked into the JS bundle at build time. Fixes the recurring issue where setting `REACT_APP_TURNSTILE_SITE_KEY` in Emergent secrets didn't propagate without a frontend rebuild (which Emergent's "Re-deploy changes" wasn't triggering when only env vars changed, no code changed). Now keys can be set or rotated in production secrets and propagate on the next backend reload — no rebuild needed.
- 🛠 Founder email (`samuel.malick@aiadvocate.co.uk`) auto-verified at signup to prevent founder lockout. Already-existing accounts grandfathered as verified.



### 2026-06 (Iter 53 — PWA → Google Play Store ready)
- 📲 **Manifest upgraded to TWA-grade.** `/app/frontend/public/manifest.json` now has `id`, `scope`, `display_override`, `categories`, `lang`, 4 icons (192/512 in `any` + dedicated 192/512 `maskable` with 20% safe-zone padding), and 4 launcher shortcuts (Ask Lex, Cases, Vault, Find Legal Aid). `start_url` is `/?source=pwa` for install attribution.
- 🛠 **Service worker added** at `/app/frontend/public/sw.js`. Network-first for HTML navs, cache-first for static, never caches `/api/*` (legal data must always be live). Registered from both `index.html` (React app) and `welcome.html` (static marketing splash). Confirmed `activated` in the live preview.
- 🎯 **Fixed PWA-killer bug**: `/welcome.html` is where most first-time visitors land, but it had no `<link rel="manifest">`, so Chrome wouldn't fire the install prompt. Added manifest link, apple-touch-icon meta, and SW registration to welcome.html. Verified Chrome now sees a valid manifest from every entrypoint.
- 🚦 **PWA-launch detection in App.js**: when launched from the installed app (`?source=pwa` query, `display-mode: standalone`, or iOS `navigator.standalone`), the React app now sets `aa_skip_marketing` and skips the redirect to welcome.html. Installed users land straight in the language picker / auth flow, not the marketing splash.
- 📄 **`/app/memory/google_play_listing.md`** — complete Play Console copy: app title (30 char), short description (80 char), full description (4000 char), Data Safety form answers per data type (Stripe / Anthropic / OpenAI / Google / Resend / PostHog / Tavily disclosures), IARC content rating answers, financial-services declaration, IAP / subscription SKU table.
- 📄 **`/app/memory/pwabuilder_steps.md`** — step-by-step from `aiadvocate.co.uk` → PWABuilder.com → `.aab` → Play Console internal testing → production. Covers `assetlinks.json` upload to `/.well-known/`, keystore backup, common review rejections + fixes.
- 🟡 **Pending (user action)**: confirm package id `uk.co.aiadvocate.aiadvocate` in PWABuilder, capture 2–8 phone screenshots (1080×1920), create 1024×500 feature graphic, host `assetlinks.json` once PWABuilder emits it.



### 2026-06 (Iter 52 — Multi-page upload everywhere + UI polish)
- 📎 **Multi-page upload for Letter Reader + Contract Tools.** Both modals now accept multiple photos/PDFs in one go. Frontend chains: pick N files → first one shown as main preview, rest as `extraFiles` pills → on "Analyse", each file is uploaded via `/lex/upload`, then `/document/analyze` (or `/contract/analyze`) is called with `doc_ids=<comma-separated>`. The server stitches the per-page extracted text together (in submission order) and runs one combined analysis. Lex chat's `📎` already supported multi-select.
- 🎯 **New backend modes**: `POST /api/document/analyze` and `POST /api/contract/analyze` now accept an optional `doc_ids` form param (comma-separated /lex/upload IDs) on top of the existing `file` upload path. Single-file legacy path still works. Verified end-to-end via curl with a 2-page letter (returns `category=debt_collection, severity=high`).
- 🧹 **"AI Advocate" subheading + "TRY ASKING LEX:" + sample-chip cluster removed** from inside every Lex chat modal so it looks like a single calm prompt box (per user feedback — "more intelligent without it").
- 🪜 **Renamed `Show ladder` → `Counter letter`** on the Letter Reader result panel (data-testid `letter-ladder-btn` retained). Matches the underlying `CounterLadderPanel` feature.
- 🛠 **Test reviewer account re-comped to Pro until 2053-10-08** — the original trial had expired on 2026-05-31 and was failing /lex/upload with "(1/day on Free)". Updated `/app/memory/test_credentials.md` accordingly.


### 2026-02 (Iter 51 — Outcome Ladder decryption fix + smart-route preload)
- 🪄 **Smart-route now actually opens the tool with the doc preloaded.** Previously, clicking "Open Letter Reader" in the Lex chat smart-route banner only closed the chat. Now it closes the chat AND opens the Letter Reader modal with the already-uploaded doc, which auto-analyses via `/document/analyze?doc_id=<id>` (no re-upload needed). New `onSwitchTool` prop on `LexChat` + `initialDoc` prop on `LetterReaderModal` + new `doc_id` form-param mode on `POST /api/document/analyze`.
- 🐛 **Outcome Ladder + Devil's Advocate fixed** — `_last_lex_exchange()` was returning encrypted ciphertext to the strategist LLMs, which made them fail JSON validation and return "Lex couldn't structure the outcome ladder". Now decrypts `user_message` + `assistant_response` before returning. Verified end-to-end with curl using a real Lex conversation.
- 🧹 **Subtitle removed** — removed the small "AI Advocate" subheading under the `LEX` header inside every chat modal, per user feedback ("looks more intelligent without it").


### 2026-02 (Iter 46 — Founder story + For-Firms PDF downloads + Tip-of-Day verified)
- 📘 **For-Firms PDF download section** added to `/founding-firm-pitch.html` (route `/for-firms`). Two CTAs: Partner Introduction Pack (`/intro-pack.html`, 8pp A4) + One-page Pitch Card (`/pitch-card.html`). Plus a "copy share link" button. Lives above the trial-length pill grid. Test-ids: `firm-download-intro-pack`, `firm-download-pitch-card`, `firm-share-intro-pack`. Verified both PDFs load 200 in preview.
- 🌟 **Day 1 Instagram launch post REWRITTEN** with the real founder story (wife's French travel document, embassies refusing her, Eurostar workaround). Professional tone. Replaces the generic ET1-helping-a-friend draft. Updated in `/app/frontend/public/instagram-pack/30-day-content-calendar.md`.
- 💼 **New file `/app/memory/LINKEDIN_OUTREACH.md`** — pinned founder-story post (professional version), solicitor 1:1 DM template, weekly LinkedIn status template, posting cadence, and a price reference table (Plus = £19.99, NOT £14.99 — the old number was the Weekend Pass top-up, NOT the subscription).
- 🧹 **Stale £14.99 references fixed** in `/app/memory/PRD.md` (was internal-only, never user-facing). Backend Stripe prices were always correct at £19.99.
- ✅ **Tip-of-the-Day curated pool** verified live: 120 hand-written UK tips across 9 categories, deterministic rotation by day-of-year + per-user offset. Non-UK locales still get cached LLM translation. `source: "curated_pool"` for GB+en, `source: "llm"` elsewhere. Confirmed end-to-end via curl.
- ✅ **Pricing inconsistency resolved**: aligned Practice tier text everywhere to **£499/mo** (matches `/founding-firm-pitch.html`). Fixed in `backend/server.py` lines 7798 + 7887 and `memory/PRD.md` target-users line. **CRITICAL TODO for founder**: update the live Stripe Price ID `STRIPE_PRICE_FIRM_PRACTICE` in `.env` (currently `price_1TcVaHFh8lRHrXPIGOKrL55T`) to a £499/mo price object in the Stripe Dashboard, otherwise the checkout will still charge the old amount. UI text is now consistent; Stripe Dashboard is the only remaining step.

## Completed Implementation (rolling)

### 2026-02 (Iter 50 — Doc Pack live + weekly Stripe audit cron)
- 💷 **£4.99 Doc Pack top-up fully wired** — Stripe product "AI Advocate — Doc Pack" created at price ID `price_1TfQqYFh8lRHrXPIT1eRk3ie`. Count-based (5 docs, 100 pages each, never expires) — stacks on top of any tier's daily quota. New TOPUP_PACKS["doc_pack"] entry with `doc_grants=5`, `doc_page_cap=100`. `_activate_topup_for_user` extended with a doc_pack branch that `$inc`s `doc_pack_remaining` on the user record (instead of setting `topup_active` like time-windowed packs). Audit summary now **12/12 OK**. Webhook already wired — same path as Day Pass etc.
- 📎 **Polite paywall in chat** — when a Free user hits their 1-doc-per-day cap, `handleFileAttach` detects the 402 and surfaces an inline `data-testid="lex-doc-paywall"` card with two CTAs: **Buy Doc Pack £4.99** (calls `/api/topups/checkout` → redirects to Stripe Checkout) and **Upgrade to Plus £19.99/mo** (calls `/api/subscription/checkout`). Dismissable via `×`. Tested live — POST to checkout returned a real `cs_live_…` Stripe session.
- ⏰ **Weekly Stripe price audit cron** — runs every **Monday at 09:00 UTC** (verified via new `/api/admin/scheduler-status` endpoint: `next_run_utc=2026-06-08T09:00:00Z`). If any price mismatch / error is found, emails `admin@aiadvocate.co.uk` (and any addresses in `ADMIN_EMAILS`) with a detailed HTML table. Email only fires when something is off — quiet by default.
- 🛠 **New admin endpoints**: `GET /api/admin/scheduler-status` (lists all cron jobs + next-run timestamps); `POST /api/admin/trigger-stripe-audit-email` (manual test run — useful before waiting until Monday).
- 🛠 **Refactor**: `_run_stripe_price_audit()` helper extracted so the manual endpoint + weekly cron + manual-trigger endpoint all share one code path.



### 2026-02 (Iter 49 — Document upload in Lex chat)
- 📎 **Major new feature: attach documents to any Lex chat.** Paperclip button in the chat input accepts **PDF, .docx, .doc, .txt, .md, .rtf, .csv, .xlsx, .odt, .pages, and all image formats** (.jpg/.png/.heic/.webp/.gif/.bmp/.tif). Server extracts text via pypdf / docx2txt / striprtf / openpyxl / Gemini Nano Banana OCR for images. Each attached doc gets a `doc_id` and is injected as a system-context block on EVERY chat turn in that session — true ChatGPT-style whole-session memory. Up to 5 docs concurrently per session.
- 💰 **Tier limits (server-enforced)**:
  - Free: **5 pages / 1 doc per day**
  - Plus: **25 pages / 10 per day**
  - Pro: **100 pages / unlimited**
  - One-off "Doc Pack £4.99" top-up adds 5 × 100-page docs (backend ready, Stripe top-up wiring left for follow-up)
- 🪄 **Auto-routing to specialist tools**: when the uploaded doc is classified as a contract (`tenancy`, `lease`, `employment`, etc.) or a solicitor letter (`without prejudice`, `notice to quit`, `letter before action`…), a green banner suggests Contract Tools or Letter Reader as a one-tap alternative. User can still just chat about it.
- 🆕 Endpoints: `POST /api/lex/upload`, `GET /api/lex/upload/{doc_id}`.
- 🆕 ChatMessage payload: new optional `doc_ids: List[str]`.
- 🆕 Testids: `lex-attach-doc-btn`, `lex-doc-file-input`, `lex-attached-docs`, `lex-attached-doc-{id}`, `lex-remove-doc-{id}`, `lex-doc-routing-banner`, `lex-doc-route-open-tool`, `lex-doc-route-dismiss`.
- 🛡 **Defence-in-depth**: PDF page-count probed BEFORE text extraction (1ms metadata read) so oversized files are rejected without burning CPU. 20 MB hard cap. Cross-user GET → 404.
- ✅ **Testing**: 6/6 backend pytest pass + 8/8 frontend testid flows verified end-to-end. Verified live with a 1-page tenancy PDF → "How much rent?" returned "According to the attached tenancy agreement, you must pay £950 per month rent" — proving whole-session injection works.
- 🔧 **Code-review fixes applied**: classifier now recognises `lease`, `landlord`, `tenant`, `monthly rent`, `fixed term`, etc., and uses filename as a strong prior; PDF page-count probe added BEFORE text extraction.



### 2026-02 (Iter 48 — Emergency lawyers card fix + Stripe charges audit)
- 🚨 **Bug fix: Emergency → "Nearest lawyers to you" no longer disappears.** Previously the box only rendered while `lawyersBusy` was true OR results existed — so when the search completed with zero nearby firms (common abroad), the entire box silently vanished mid-flow, making the user think the feature was broken. Now the box renders whenever GPS is known, with three explicit states: "Searching…", lawyer rows, or a friendly "No partner firms within 50 km — close to browse the full Lawyers directory" empty-state. New testids: `emergency-lawyers-loading`, `emergency-lawyers-empty`, `emergency-open-directory`. Verified with curl that `/api/lawfirms` returns `[]` in <100ms for remote coords.
- 💳 **New admin endpoint `GET /api/admin/stripe-recent-charges`** — lists the N most recent Stripe charges + refund status (live or test mode). Use to verify customer payments / self-refunds without leaving the app. Used live to confirm both £14.99 (16 May) and £4.99 (25 May) charges on Mastercard ****3367 were succeeded + fully refunded.



### 2026-02 (Iter 47 — Smart-scroll fix + GDPR analytics delete + Stripe price audit)
- 🪄 **Smart chat-scroll fix (LexChat + Courtroom Practice)** — previously every streaming chunk re-scrolled the chat to the bottom, so the TOP of Lex's answer constantly fled off-screen. Now the `useEffect` depends only on `messages.length` (fires once per new message, not per chunk). When a new lex bubble appears, its TOP is scrolled to near the top of the chat container; while content streams in below, no auto-scroll fights the user. User-sent messages still scroll to bottom (so the user sees their own send). `data-msg-index` and `data-pmsg-index` added to bubble divs so the anchor finds the right node.
- 🗑 **GDPR "Delete my analytics data" button** (Settings → Privacy & analytics). New endpoint `POST /api/privacy/delete-analytics-data` — wipes the user's PostHog person + events server-side via Persons API (requires `POSTHOG_PERSONAL_API_KEY` env var; gracefully returns `status: skipped` if absent). Always resets PostHog client-side identity and switches off both analytics + crash toggles locally. Audit row written to `privacy_analytics_deletions` collection. New testids: `privacy-delete-analytics-row/btn/confirm/cancel/done`. Backend pytest 6/6 PASS.
- 💰 **Admin "Stripe price audit" card** (Settings → owner-only). New endpoint `GET /api/admin/stripe-price-audit` — resolves all 11 STRIPE_PRICE_* env vars to live Stripe Price objects and compares amount + currency + interval against expected. Returns 11-row table + summary {ok, mismatch, missing, error}. Used to verify after price-ID swaps. Current state: 11/11 OK, 0 mismatch.
- 🛡 **AdminSafeBoundary** — class component wrapping all 7 owner-only admin cards in Settings. If any single admin card crashes at runtime (e.g. a 500 from a deprecated admin endpoint), the founder still sees the rest of the Settings menu — not a blank dialog. Includes "Retry" button + dev-console error logging.
- ⚖ **Stripe Price ID alignment**: Practice tier verified £499/mo (`price_1TcVaHFh8lRHrXPIGOKrL55T`). Featured tier corrected £49.99 → £49.00 (`price_1TehZ2Fh8lRHrXPIHinV9eEU`). All marketing + backend strings consistent.
- ✅ **Testing**: backend 6/6 new + 40/40 prior regression = 46/46. Frontend regular-user GDPR flow 100% verified. Admin Stripe audit endpoint 100% verified via curl; UI card code-reviewed (Playwright couldn't dismiss the lang modal for admin login — known automation flake, not a real-app bug).



### 2026-02 (Iter 45 — Evidence-collection link + Auto-witness from chat)
- 📎 **Shareable evidence-collection magic-link** — Owner taps "+ Request files" inside any case → enters a label + instructions → gets a tokenised public link they can share with HR, ex-employers, friends, etc. Uploader visits the link (no signup), drops a file (max 12MB, max 8 per invite), Lex stores it encrypted (AES via `app_crypto.encrypt_text` → base64 in `evidence_files` collection), auto-creates a `case_item` so it lands in the case + timeline, and emails the owner with SHA-256 chain-of-custody. Owner can close the invite at any time. Backend: 6 new endpoints (create / public fetch / public upload / list / download / close). Frontend: `EvidencePublicPage` (public route `/evidence/<token>`) + `EvidenceCollectionPanel` inside the "People & files" case tab (renamed from "Witnesses").
- 👥 **Auto-Witness from Lex chat** — When a Lex chat is linked to a case, every Lex reply bubble gets a "👥 Invite witness" button. Clicking opens an inline panel with the witness context pre-filled from the previous user question + Lex's reply ("What I discussed with Lex: …\n\nLex's analysis: …\n\nPlease write what you witnessed…"). Owner edits, hits Send, magic-link is created via the existing `/api/cases/{id}/witness/invite` endpoint. Privacy: only Lex's reply + the user's last question (which the user themselves wrote) are passed forward — never the full chat history.
- 🛡 Privacy preserved: encrypted-at-rest file storage, SHA-256 logged, single-token-per-invite, expires in 30 days, max 8 uploads per invite, owner can close anytime.
- ✅ **Testing**: 15/15 new pytest + 25/25 regression = 40/40 PASS. Full frontend E2E green (testing_agent_v3_fork iter_24).

### 2026-02 (Iter 44 — Witness Statement Auto-Draft)
- ✨ **Lex auto-draft for witness statements** — public route `/witness/<token>` now has a "✨ Help me write this — Lex can draft a first version" CTA above the freestyle textarea. The witness jots bullets (dates, names, what they saw), clicks Generate, and Lex returns a numbered CPR Part 32-compliant statement ready to review/edit.
- 🔒 **Privacy by design** — `POST /api/witness/{token}/auto-draft` (public, no auth) only sends the witness's bullets + the invite's `context_for_witness` + guiding questions to Claude. The case owner's chat history, evidence, and other case items are NEVER passed to the LLM nor visible to the witness. Tested + documented in the public privacy note shown to the witness.
- 🛡 Auth invariants preserved: 404 for invalid tokens, 409 for already-submitted, 410 for expired, 400 if both bullets and invite context are empty.

### 2026-02 (Iter 43 — Phase 4b: 6-feature batch + 2 upgrades)
- 📸 **OCR Form Scanner** — Gemini 2.5 Flash vision detects UK gov forms (ET1/ET3/N1/N9/N244/MC100/D8) + extracts visible field values + signposts the right modal. New endpoint `POST /api/forms/ocr/detect`. ET1 modal now has "📸 Scan form" button that auto-fills claimant/employer/employment fields from a photo.
- 🪜 **Letter Counter-Ladder** — `POST /api/letters/counter-ladder` returns 4 escalating drafts (Polite → Firm → Pre-action → Court) with statute citations. Uses delimiter parsing (`===POLITE===` fences) instead of JSON to avoid escaping issues with long letter bodies. Frontend: "Show ladder" button in Letter Reader → `CounterLadderPanel` with 4 tone tabs.
- 🌡 **Letter Threat Meter** — visual 1-5 escalation bar in Letter Reader (low → urgent → crisis).
- 🤖 **Case Timeline Lex Auto-Summary** — `POST /api/cases/{id}/timeline/summarise` turns raw events into solicitor-handover JSON {headline, narrative, key_dates, open_questions, next_legal_steps}. Cached in `case_timeline_summaries` collection. Frontend: "Generate Lex solicitor handover" button on Timeline tab + horizontal `TimelineRibbon` (month-by-month visual scrubber).
- 👥 **Witness Statement Builder + Magic-Link Invite** — owner invites via `POST /api/cases/{id}/witness/invite` (sends email if address provided, otherwise copy-able link). Public no-auth route `/witness/<token>` → 30-day single-use token → witness fills CPR 32 form + signs Statement of Truth → owner sees in new "Witnesses" tab + downloads `application/pdf` (CPR Part 32 compliant template). Email notifies owner on submit. New collections: `witness_invites`, `witness_statements`.
- ✉️ **Letter Writing Tone Slider** (UPGRADE) — `/api/legal-letter` now accepts `tone ∈ {polite, firm, pre_action, court}`. Frontend: visual tone pills + color-coded ladder bar + dynamic hint text.
- 💷 **Lawyer Cost — postcode multiplier + 3-way compare** (UPGRADE) — `/api/cost/estimate` accepts UK postcode → regional uplift (EC1A=1.55× Central London, NE=0.90× North East, etc., 60+ outward codes). Returns `comparison: {diy, ai_advocate, solicitor}` with total cost + pros/cons/downside. AA Pro saving vs solicitor mid-point shown as banner. Frontend: 2-tab modal (Summary / Compare options) + postcode input + region badge.
- ✅ **Testing**: 14/14 new backend pytest + 11/11 ET1 regression = 25/25 PASS (`/app/backend/tests/test_iter23_phase4b.py` + `test_et1_autofill.py`). Frontend 85% live-verified; all testids confirmed in source.

### 2026-02 (Iter 42 — Phase 4a: ET1 Employment Tribunal Auto-Fill)
- 📋 **New tile "ET1 Auto-Fill"** (free tier, isNew badge) on the dashboard. Tap → `ET1AutoFillModal` (2-step: input form → structured result).
- 🧠 **Lex generates a full UK Employment Tribunal ET1 claim** from a plain-English narrative + optional personal/employer/employment fields. Claude Sonnet 4.5 extracts the right claim types (`unfair_dismissal`, `discrimination`, `redundancy_pay`, `unauthorised_deductions`, `breach_of_contract`, `equal_pay`, `harassment`, `victimisation`, `whistleblowing`, `automatic_unfair_dismissal`, `constructive_dismissal`), picks the right protected characteristics for discrimination (Equality Act 2010), drafts first-person narrative citing UK statutes (ERA 1996 s.94/s.139, Equality Act 2010, PIDA 1998), builds a sorted chronology of key dates, lists supporting evidence, and warns about the 3-months-less-1-day deadline + mandatory ACAS Early Conciliation.
- ⚙️ **Backend endpoints**:
  - `POST /api/forms/et1/draft` — generate + persist. `extra_context` now has `Field(min_length=40)` defence-in-depth so direct API callers get 422 instead of wasting tokens.
  - `GET /api/forms/et1/{draft_id}` — fetch saved draft (owner-scoped; cross-user returns 404).
  - `PUT /api/forms/et1/{draft_id}` — update structured data.
  - `GET /api/forms/et1/{draft_id}/pdf` — server-side reportlab PDF (~8KB, %PDF magic verified) mirroring the gov.uk ET1 format as a fill-in companion.
- 🎨 **Frontend (App.js)**: `ET1AutoFillModal` + `ET1Result` + `ET1Section` components. Result view shows claim type chips, protected-characteristic chips (red for discrimination), narrative, legal basis, key dates timeline, remedy block, evidence list, warnings block, + buttons to download PDF / open gov.uk online filing / open ACAS portal.
- ✅ **Testing**: 11/11 backend pytest tests (`/app/backend/tests/test_et1_autofill.py`) + full frontend E2E (testing_agent_v3_fork iter_22) — all green. Cross-user 404 isolation verified. PDF download verified (content-type `application/pdf`, 7826 bytes, valid magic bytes).

### 2026-02 (Iter 41 — Phase 3: Solicitor Sanity Check hybrid AI+human flow)
- 🎖 **Consumer-side**: new "🎖 Solicitor check · £49" button on every Lex answer (next to 👍 👎 🪜 😈). Tap → confirms with user → creates Stripe one-off checkout → user pays → webhook auto-routes to a verified UK law firm with capacity → solicitor reviews within 24h → user gets the verdict by email + visible in app.
- ⚙️ **Backend (new collection `sanity_checks`)**:
  - `POST /api/sanity-checks/create-and-checkout` — creates pending_payment row + Stripe Checkout session using `price_data` (no pre-created Stripe Price needed). Auto-pulls the latest Lex exchange from the session if question/answer not provided.
  - Webhook handler in `/api/stripe/webhook` recognises `metadata.kind=sanity_check` → activates → routes.
  - `_route_sanity_check()` selects the eligible firm with fewest open Sanity Checks (round-robin fairness, max 5 concurrent per firm). Only premium/practice/founding tier firms are eligible. Respects `declined_by` array so a declining firm doesn't get the same SC routed back.
  - `GET /api/sanity-checks` (user history) · `GET /api/sanity-checks/{id}` · `GET /api/firm/sanity-checks` · `POST /api/firm/sanity-checks/{id}/submit` (min 60 chars) · `POST /api/firm/sanity-checks/{id}/decline` · `GET /api/admin/sanity-checks` (admin oversight + by-status counts).
- 💷 **Auto-commission integration**: when a firm submits, a `firm_engagements` row is auto-inserted with `commission_owed_gbp = -30` (negative = AA owes the firm). This credits the firm on their next monthly invoice — clean reconciliation with the existing hybrid auto-billing pipeline (Iter 38).
- 📧 **Email orchestration** (Resend):
  - Firm assigned → "New Sanity Check assigned — £30 on completion"
  - Client when assigned → "Your Sanity Check is on its way — solicitor will respond within 24h"
  - Client when complete → "Your Sanity Check is back — ✓ Confirmed" or "⚠ A solicitor found concerns" with the solicitor's verbatim response
- 🔒 **Privacy**: the firm sees the matter type, the question text, and Lex's answer — but NOT the consumer's email/name. "AI Advocate doesn't share your contact details unless you ask us to" — clearly stated in the client email.
- 🎨 **Firm Portal UI**: new `FirmSanityCheckQueue` card with open/completed split, expandable review pane, anti-typo 60-char minimum, "Decline & re-route" fallback, capacity badge.
- 🛠 **Same `get_firm`/`_check_admin_user` lateness gotcha hit again** — fixed by moving firm + admin endpoints below their dependencies (consistent with the Iter 37 commissions fix).
- Verified full lifecycle end-to-end via curl: pending_payment → pending_assignment → assigned → completed, with commission auto-logged.

### 2026-02 (Iter 40 — Phase 2: Legal Aid done right + Courtroom scroll fix)
- 🏛 **Legal Aid modal** rebuilt as a 3-tab flow (Eligibility · Draft application · Find an adviser).
- ✍️ **Draft Statement in Support generator** — new `POST /api/legal-aid/draft-application` returns a markdown statement structured per LAA expectations (Applicant details, Nature of problem, Why representation needed, Means test, Merits test, What I'm applying for, Supporting documents, Declaration). Claude Sonnet 4.5 cites the right UK statutes (Housing Act 1988, Equality Act 2010, Children Act 1989 etc.) and leaves `[SQUARE BRACKET]` placeholders for missing facts. Companion `POST /api/legal-aid/draft-application/pdf` renders to a downloadable PDF via reportlab. Verified on a real eviction scenario — Claude correctly identified the retaliatory-eviction angle and cited Section 21 Housing Act 1988.
- 📍 **Find a Legal Adviser** — new `POST /api/legal-aid/find-advisers` LIVE-scrapes the gov.uk Legal Aid Agency directory (`find-legal-advice.justice.gov.uk`) which has no public JSON API. Returns up to 12 nearest legal aid advisers with: name, telephone, address, distance, map link, and matter categories. Tested with E15 postcode + housing category → 404 real matching advisers returned.
- 🆕 Mapping of 17 LAA category codes (housing, family, immigration, debt, welfare, employment, crime, mental health, community care, discrimination, education, public law, actions-against-police, clinical-negligence, personal-injury) and tolerant fallbacks.
- 🛡 New dependency: `beautifulsoup4==4.14.3` (already added to requirements.txt via pip freeze).
- 🛠 **Courtroom Trainer fixes**:
  - **Scroll bug**: capped both pinned "SAY THIS" + "latest translation" cards at `maxHeight: 38vh` with internal overflow, added the classic flexbox `minHeight: 0` to history scroll containers so they actually shrink and scroll.
  - **Past sessions browser**: new `PastSessionsBrowser` component shown in both Live Assist and Translation tabs (when not actively recording) — lists every saved session with date/time/turn-count and a one-click PDF re-download. Backend `/api/live/sessions` and `/api/live/notes/{id}/export` were already there but had no UI.

### 2026-02 (Iter 39 — Phase 1: Lex becomes a strategist)
- 🪜 **Outcome Ladder** — new `POST /api/lex/outcome-ladder` endpoint takes the user's most recent Lex exchange in a session and returns a structured worst-case / likely-case / best-case JSON with probabilities, "next step" guidance, and a warm calm-note. Free for all tiers. Powered by Claude Sonnet 4.5 via Emergent LLM key.
- 😈 **Devil's Advocate** — new `POST /api/lex/devil-advocate` returns the opposing party's strongest 3 arguments, evidence they'll use, loaded questions to expect, user's honest weakest point + strongest counter, and a prep checklist. Reframed as "case preparation" (not adversarial language) so Claude doesn't refuse. Verified output cites named UK statutes appropriately (Protection from Eviction Act 1977, Tenancy Deposit Scheme, etc.).
- 🎨 **UI**: two new buttons added to every Lex answer footer ("🪜 Outcome ladder" + "😈 Other side"). When tapped, an inline panel renders below with branded gold/red theming, prob badges, and clean typography. Toggle to hide/show without re-querying.
- 🛠 **Critical bug fix**: `json` module was never imported at the top of `server.py` (`NameError("name 'json' is not defined")` — silently swallowed by `except Exception: pass`). Fixed by adding `json` to the top-level imports.
- 🛠 **Tolerant JSON parser**: new `_extract_json_object()` + `_normalize_json_string_newlines()` helpers handle Claude's markdown-fenced output AND multi-line strings (which are invalid JSON per spec). Reusable for future structured-output features (forms auto-fill, witness statement builder, etc.).
- Verified end-to-end via curl on real cases (eviction with deposit dispute, adverse-possession claim) — both endpoints return well-structured, accurate UK-jurisdiction outputs in ~3-6 seconds.

### 2026-02 (Iter 38 — Hybrid auto-billing scheduler)
- 🤖 **APScheduler cron** for hands-off commission billing. Three jobs (all 09:00 UTC):
  - **22nd of month** → `_send_headsup_emails` — sends a 7-day-ahead heads-up to every firm with unpaid commission, showing estimated total. Skips firms <30 days old.
  - **1st of month** → `_create_monthly_drafts` — generates DRAFT Stripe invoices (auto_advance=False) for the previous calendar month, stores per-firm records in `commission_drafts` with anomaly flags + admin summary email.
  - **3rd of month** → `_job_autosend` — auto-finalises + sends every still-draft non-flagged invoice (48-hour review window for the founder). Flagged drafts stay held; admin gets a heads-up email if any are held.
- 🛡 **Anomaly guardrails** (`_compute_anomaly_flags`):
  - `large_amount` — current draft > £1,000 (catches typos like £15k instead of £1.5k)
  - `high_vs_avg` — current draft > 5× the rolling 3-month average
  - `<30 day skip` — brand-new firms get a free first month before auto-billing kicks in
- 🆕 **Admin endpoints**: `POST /api/admin/commissions/run-monthly-drafts`, `GET /api/admin/commissions/drafts`, `POST /api/admin/commissions/drafts/{id}/{approve|void}`, `POST /api/admin/commissions/drafts/approve-all` (skips flagged unless `?include_flagged=true`), `POST /api/admin/commissions/send-headsup`, `GET /api/admin/commissions/schedule`.
- 🆕 **New collection**: `commission_drafts` (stripe_invoice_id, firm_id, month, total_gbp, engagement_ids, anomaly_flags, rolling_avg_gbp, requires_review, status: draft|sent|voided, source: manual|cron, timestamps).
- 🆕 **Engagement statuses**: added `pending_invoice` between `unpaid` and `invoiced` (the 48-hour window). Voiding a draft reverts engagements to `unpaid`.
- 🎨 **Admin UI rebuild**: `AdminCommissionsCard` now shows a schedule banner (next 3 cron runs), a "Pending drafts" review section with per-row Approve/Void buttons + anomaly flags + 3-month rolling-avg comparison + bulk "Approve all non-flagged" button, and demotes the old "Issue all immediately" CTA to a secondary "skip review" path.
- Added `apscheduler==3.11.2` to `requirements.txt`.
- Verified end-to-end: log commissions → create drafts (£6,600 single firm → `large_amount` flag fires + `requires_review=true`) → void draft (Stripe `in_xxx` voided, engagement returns to `unpaid`) → schedule endpoint returns correct next-run timestamps.

### 2026-02 (Iter 37 — Commission ledger + manual auto-invoicing + default founder signature)
- 💷 **Firm referral-commission ledger.** New `POST/GET/DELETE /api/firm/commissions` endpoints (renamed from `/firm/engagements` which collided with the client-thread engagement system — discovered + fixed in this iteration). Firm portal now shows a "REFERRAL COMMISSIONS" card under their engagements list with 3 totals tiles (Lifetime fees / Commission / Unpaid) + a "Log closed engagement" modal that captures matter, client, fee_gbp, closed_at. Backend auto-calculates the 30% commission per the Founding Firm Agreement.
- 📧 **Stripe auto-invoicing for commissions.** New admin endpoints: `POST /api/admin/commissions/issue-invoice` (single firm/month) and `POST /api/admin/commissions/issue-all` (bulk run for whole month — defaults to *previous* month). Generates one Stripe Invoice per firm with one InvoiceItem per closed engagement (clear line items for reconciliation), auto-finalises, sends via Stripe + a branded heads-up email. Marks engagements as `invoiced` with the Stripe invoice ID.
- ✍️ **Default founder signature admin card.** New `AdminFounderSignatureCard` in the consumer Settings (owner-only). Draws once → persisted via `POST /api/admin/founder-signature` → auto-fire enabled. Now every new firm signup (in the first-20 cohort) automatically gets a personalised Founding Firm Agreement emailed without any manual action. Status badge ("AUTO-FIRE ON") + preview of saved signature + Clear button.
- 🛠 **Critical bug fix — route collision.** Both the commission system and the B2B2C client-thread system were registering on `/firm/engagements`. FastAPI was using whichever was registered first, silently breaking the other. Renamed commission endpoints to `/firm/commissions/*` and renamed `EngagementCreate` (commission model) to `CommissionEntryCreate` to also unblock the Pydantic class collision.
- 💵 **New admin commissions panel** (`AdminCommissionsCard`): month picker, by-firm summary with engagement count + fees + commission + unpaid, "Invoice" button per row, big "Issue invoices to all firms for [month]" CTA.
- Verified end-to-end via curl: login → POST `/firm/commissions` (£1,500 fee → £450 commission stored) → GET `/firm/commissions` → DELETE works; firm portal engagement listing still 200s (no regression on client threads).

### 2026-02 (Iter 35 — Founding Firm e-signing flow)
- ✍️ **In-app e-signature for the Founding Firm Agreement.** Admin signs once (canvas pad in the admin panel), then "Send for e-signature" emails the firm a unique signing URL (`/firm-sign/<token>`). Firm opens it, sees the agreement on screen, types name + draws signature on canvas + ticks acceptance, and clicks Sign. Backend captures IP + user-agent + timestamp, regenerates the PDF with BOTH signatures embedded, and emails signed copies to both parties. Legally binding under UK Electronic Communications Act 2000 + eIDAS as a "simple electronic signature."
- New endpoints: `POST /api/admin/firm-agreements/send`, `GET /api/firm-agreements/{token}`, `POST /api/firm-agreements/{token}/sign`, `GET /api/firm-agreements/{token}/pdf`, `GET /api/admin/firm-agreements`.
- New collection: `firm_agreements` (token, firm details, both signatures as data URLs, status, timestamps, signer IP/UA, terms_snapshot_version).
- New frontend route: `/firm-sign/<token>` → `FirmSign.jsx` (standalone, no auth, with built-in 50-line canvas signature pad — no library dependency added).
- PDF generator (`generate_founding_firm_agreement.py`) extended to accept signature data URLs and embed them as PNGs above the printed names.
- Email helper (`email_helper.py`) extended with a generic `send_email(to, subject, body_html, attachments)` function — fixes a long-standing bug where `from email_helper import send_email` was failing silently because that function never existed (gift packs, firm onboarding emails were quietly dropping for weeks).
- Admin panel: replaces the lone "Download agreement" button with: signature canvas + "📧 Send for e-signature" + "⬇️ Or download unsigned" + a status list of all agreements sent (SIGNED/PENDING badges, linkable to the signing page).
- Verified end-to-end via curl: send → fetch → sign → list → download signed PDF (8.3 KB) with both signatures, 70% wording present, old 50% absent.



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
- **Pricing left as-is** for now (£19.99 / £34.99 / £319.99) — these touch live Stripe price IDs and need an explicit decision before changing.

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

## 🆕 2026-02 — Find a Lawyer: Google Places integration (P0 SHIPPED)
- Replaced the 12-firm seed-only directory with real-time Google Places API (New v1).
- New backend endpoint: `GET /api/lawfirms/nearby?lat&lng&radius_km` (or `?postcode=...`).
  - Calls `places:searchNearby` (includedTypes=lawyer) with 20km default radius, top 20 results.
  - Sponsored / claimed firms from `db.law_firms` are merged at the top (dedupe by normalised name).
  - 24h in-process cache keyed on a ~1.1km lat/lng grid + radius bucket.
  - Postcode fallback uses `places:searchText` (Geocoding API is not enabled on the user's GCP project).
- Frontend (`LawyersModal` in `App.js`):
  - On the Nearby tab the modal requests browser geolocation; if denied/unsupported, a postcode input appears.
  - Each card shows distance + Google star rating (count) + an "Open now" pill if available.
  - Google Places firms show a "via Google" badge and an "Open in Maps" CTA (no inquiry form — disclaimer instead).
  - Sponsored firms keep the inquiry form (firm leads continue to flow into the existing pipeline).
  - Radius selector (5 / 10 / 20 / 50 km) re-fetches results.
- Tested 2026-02 — `testing_agent_v3_fork iteration_27`: backend 6/6 pytest passed (sponsored-first ordering, postcode geocoding, 400 on missing params, dedupe, fast cache repeat, /api/lawfirms regression). Frontend playwright verified postcode fallback, sponsored-first card, "via Google" badges, Open-in-Maps link, inquiry form gated correctly.
- Env: `GOOGLE_PLACES_API_KEY` is live in `/app/backend/.env`.

## P1 / P2 Backlog (rolled forward)
- P1 — Personalised success toasts using user's first name ("Nice work, Samuel — case saved").
- P2 — "Why I built this" founder story page in Settings → About.
- P2 — Live e-signature on drafted letters (browser canvas).
- P2 — Push notifications for legal deadlines (blocked on APNs/FCM keys).
- P3 — Native iOS/Android Capacitor builds + store submissions.
- P4 — Refactor App.js / server.py (DEFERRED — launch first).

## 🆕 2026-02 — Cost-Spike Protection (3-feature shield, SHIPPED)
1. **Cloudflare Turnstile bot-shield on signup** — `/auth/signup` now calls `verify_turnstile(token, request)` against Cloudflare's `siteverify` endpoint. Frontend `AuthScreen` injects the explicit-render Turnstile widget when `REACT_APP_TURNSTILE_SITE_KEY` is set. Both backend and frontend skip gracefully when keys aren't configured (dev/preview still works). Submit button is disabled until token is captured. ENV VARS NEEDED FROM USER: `TURNSTILE_SITE_KEY` + `TURNSTILE_SECRET_KEY` (Cloudflare → Turnstile → "Add site").
2. **Daily free-tier message cap** — already enforced at 5/day via existing `check_quota_and_increment("lex_chat", "daily")` (line 684 of server.py). Taster endpoint already locked at 1 free question per IP+device per 7 days. ✅ verified live.
3. **LLM spend watchdog** — new `_record_llm_call()` helper writes every chat/taster turn to `db.llm_usage` with estimated £ cost (uses `LLM_RATES_GBP_PER_1M` rate table). New scheduled job `_job_llm_spend_alert` runs hourly: if last-24h spend exceeds `AA_DAILY_LLM_BUDGET_GBP` (default £30), founder gets an email with top spenders. Alert is rate-limited to once per 24h via `db.system_alerts`. New admin endpoint `GET /api/admin/llm-spend?hours=24` returns live breakdown for the dashboard.

ENV VARS ADDED:
- backend/.env: `TURNSTILE_SITE_KEY=""`, `TURNSTILE_SECRET_KEY=""`, `AA_DAILY_LLM_BUDGET_GBP="30"`
- frontend/.env: `REACT_APP_TURNSTILE_SITE_KEY=""`

Tested 2026-02:
- ✅ Backend boots clean after restart
- ✅ `/auth/signup` still accepts requests with no Turnstile token when keys are empty (graceful skip)
- ✅ `db.llm_usage` aggregation pipeline works (verified with synthetic data)
- ✅ `GET /api/admin/llm-spend` returns correct totals + top spenders
- ✅ `yarn build` passes — no syntax errors

## 🆕 2026-02 — E-Signature + UK Devolved Jurisdictions (SHIPPED)
### Canvas e-signature
- New `SignaturePad` React component (`/app/frontend/src/App.js`) — HTML5 canvas, Retina-aware, finger or mouse drawing, base64 PNG output.
- Wired into `LetterLibraryModal`: signature card appears under generated letter; user toggles "Sign letter" → canvas reveals → draws → PDF download button now sends `signature_data_url`, `signer_name`, `signer_date` to backend.
- Backend: `build_pdf()` extended to embed signature PNG + printed name + date + ECA 2000 audit footnote.
- Security: 200KB cap on `signature_data_url` returns HTTP 413.
- Cost: £0 — no third-party SaaS. Legally valid for most non-deed letters under Electronic Communications Act 2000 (England, Wales, Scotland, NI).

### UK-internal jurisdiction
- New `jurisdiction` field on user docs (`england` | `wales` | `scotland` | `northern_ireland`).
- New endpoint: `POST /api/profile/uk-jurisdiction` (validation + normalisation of "ni" → "northern_ireland").
- `lex_system_prompt()` now injects a `juris_block` with jurisdiction-specific statute + court overlay (Renting Homes (Wales) Act 2016, Private Housing (Tenancies) (Scotland) Act 2016, Sheriff Court, Procurator Fiscal, PRT, sheriff appeals, etc.).
- `PATCH /api/auth/preferences` now accepts `jurisdiction` (including null to clear).
- Frontend `SettingsModal`: new "UK legal system" dropdown shown only when country=GB. Auto-clears when country changes away from GB.

### Tests
- iter28: 8/8 PASSED (initial impl)
- iter29: 13/13 PASSED (regression + size cap + preferences-jurisdiction integration)
- pytest files: `/app/backend/tests/test_iter28_signature_uk_juris.py`, `/app/backend/tests/test_iter29_sig_cap_and_pref_jurisdiction.py`

### Known cleanup
- `LegalLetterModal` (App.js:4739) is now dead code (no callers). Acceptable for now; cleanup PR can delete it + the duplicate `letter-pdf-btn` testid.
- App.js still ~16,300 lines — deferred refactor.

## 🆕 2026-02 — Partner Programme + Founder Single Pane of Glass (SHIPPED)

### Partner Programme (B2B referral attribution + commission ledger)
- New module: `/app/backend/partner_module.py` — fully encapsulated.
- New collection `partners` (directory) + `partner_commissions` (ledger) with unique index `(partner_id, user_id, period_key)` for idempotency.
- Commission model: **10% of monthly subscription revenue · capped at £40 per user lifetime · 12-month attribution window from signup**.
- Monthly accrual job (cron: 1st of month at 02:00 UTC) walks every paying user with `partner_code` and credits the partner. Idempotent — safe to re-run.
- New endpoints (all owner-only via `_check_admin_user`):
  - `GET /api/admin/partners` — list partners with lifetime owed/paid
  - `POST /api/admin/partners` — create partner
  - `PATCH /api/admin/partners/{id}` — edit (status, bank details, etc.)
  - `GET /api/admin/partners/{id}/ledger` — full ledger
  - `POST /api/admin/partners/{id}/mark-paid` — bulk-mark periods as paid
  - `GET /api/admin/partners/{id}/statement.csv` — BACS-ready CSV export
  - `GET /api/admin/partners/_summary` — dashboard summary
  - `POST /api/admin/partners/_accrue-now` — manual trigger (testing)
- Frontend: signup endpoint accepts `partner_code` (auto-captured from `?ref=CODE` URL param and persisted in localStorage until first signup).
- Tested manually: idempotency confirmed (duplicate detection works), cap enforcement confirmed (skipped_capped after £40 reached).

### Founder Single Pane of Glass (`/founder`)
- New backend endpoint `GET /api/founder/overview` — gated to `FOUNDER_EMAIL` env (default `samuel.malick@aiadvocate.co.uk`). 403 for any other admin.
- Returns: money KPIs (paying users, total users, new 24h, LLM cost 24h, partner $ owed, active partners), business relationships, critical deadlines, vault docs, owner's diary, runbook.
- New collections: `business_relationships`, `founder_deadlines`, `founder_diary`.
- Seeded: 14 business relationships (Stripe, Emergent, Cloudflare, Resend, Tavily, PostHog, Sentry, Anthropic/OpenAI/Google, Google Places, Apple Dev, Google Play, Companies House, ICO, JMG Insurance) + 6 critical deadlines (CH confirmation statement, accounts due, ICO renewal, Apple Dev renewal, CFC insurance review, Stripe price audit).
- Endpoints to manage all three: POST/DELETE for relationships, POST/POST-done/DELETE for deadlines, POST for diary entries.
- Frontend: `FounderPage` component (~250 lines) rendered when sessionStorage `aa_view === 'founder'`. Triggered by visiting `/founder`. Includes all 7 sections (Money, Deadlines, Relationships, Vault, Diary, Runbook).

### B2B Landing Page (`/partners`)
- New static page: `/app/frontend/public/for-organisations.html`.
- Routes: `/partners`, `/for-organisations`, `/for-councils`, `/for-charities` all redirect to it.
- Content: hero, key stats (£42 CAB referral cost, ~40% reduction, 11 languages), feature grid, 3-tier pricing (Pilot £99 / Council £499 / Enterprise £1,500+), partner revenue-share callout, target audience list, CTA strip linking to mailto.
- Linked from `welcome.html` nav and footer.

### Cold-outreach emails (drafts in markdown)
- `/app/memory/partner_outreach_emails.md` — 4 polished cold emails (councils, CABs, housing assocs, debt charities) with updated capped 10% terms. Ready for Samuel to copy-paste into Gmail and personalise.

### Critical operational rule
Before sending anything that creates a financial commitment, paste it for review.

## 🆕 2026-02 — Founder Dashboard v2 (5 new features SHIPPED)

### Bug fix: Money KPIs now show REAL paying users
- `paying_users` now requires `stripe_subscription_id != null` AND status in (active/trialing/past_due) — dev/seed users no longer counted.
- `total_users` excludes admin/test emails (`admin@aiadvocate.co.uk`, `test@advocate.app`, founder).
- Added **MRR** + **ARR (projected)** KPI cards — calculated from active Stripe subs × tier price.

### #1 — Quick user lookup
- `GET /api/founder/user-lookup?q=email-substring` — case-insensitive, returns up to 20 matches with conversation_count + case_count enriched.
- UI: search box at top of dashboard, instant results.

### #2 — At-risk subscriptions
- `GET /api/founder/at-risk` — captures: past_due, trial ending in ≤3d, cancel_at_period_end, renewing in ≤7d.
- UI: 4 KPI cards + collapsible lists of failing payments + cancellations.

### #3 — Recent activity feed
- `GET /api/founder/activity` — last 15 signups, 10 active-paying, 10 cancellations (excludes test emails).
- UI: two-column "Recent signups" + "Active paying" grid.

### #4 — VAT threshold tracker
- `GET /api/founder/vat-tracker` — rolling-12m revenue estimate (active subs × tier × months-since-signup) vs £90k UK VAT threshold.
- UI: prominent progress bar + colour-coded advice block (green <80%, gold 80-100%, red ≥100%).
- Cron job will fire alert when crossing 80% (TODO).

### #6 — Weekly CEO Monday Briefing email
- New scheduler job `aa_founder_weekly` — fires every Monday at 09:00 UTC.
- Sends single HTML email to `FOUNDER_EMAIL` (default samuel.malick@aiadvocate.co.uk) via Resend.
- Includes: MRR, paying users, new signups (7d), new paying (7d), LLM spend (7d), partner commissions owed, past_due count, cancelling count, deadlines next 14 days.

### Tests
- Backend smoke tests confirm all 5 endpoints return valid data (preview env: 15 signups, 10 paying, £1,829 rolling-12 VAT, 0 at-risk).
- Cron jobs registered: `aa_founder_weekly` + `aa_partner_commissions` + `aa_llm_spend` + existing tips/headsup/drafts/autosend/stripe_audit.

### Deployment note
Production redeploy required to push all of these to aiadvocate.co.uk. ENV vars unchanged.

## 🆕 2026-02 — Founder Dashboard v3 (FINAL — 4-feature bundle SHIPPED)

### #5 — Top Lex topics this week
- `GET /api/founder/top-topics?days=7` — Mongo aggregation on `db.conversations` grouped by category, returns count + unique users + % share.
- UI: bar-chart style list in the founder dashboard.

### #7 — Cash flow forecast (next 30 days)
- `GET /api/founder/cash-flow` — projected income from active subs renewing + recurring costs from `business_relationships` + partner payouts (1/3 of unpaid commissions) + deadline-driven outgoings.
- UI: 5 KPI cards (income, recurring costs, partner payouts, deadlines, net).
- Verified: preview env shows £1,584 income / £95 costs / £1,489 net.

### #8 — Quick actions
- `POST /api/founder/refund-user` — refunds most recent Stripe charge for a user. Audit log to `db.founder_actions`.
- `POST /api/founder/lock-user` — sets `account_locked=true` on user doc. Login enforcement TBD (separate task).
- `POST /api/founder/broadcast` — sends bulk email via Resend. Audience: all | paying | free | partner. Rate-limited 1/hr via `db.founder_actions`.
- UI: broadcast composer collapsible section (audience selector, subject, HTML body, send button with confirm dialog).

### 🚨 Anomaly watchdog (hourly cron)
- New scheduler job `aa_anomaly` — runs every hour at :15 minutes.
- Detects: signup spike (≥10x 24h avg AND ≥10 in last hour), churn spike (≥3 cancels in last hour). Refund detection requires Stripe webhook integration (deferred).
- Rate-limited: max 1 alert per 4h.
- Email to FOUNDER_EMAIL via Resend.

### Cron jobs now active
`aa_llm_spend`, `aa_anomaly`, `aa_founder_weekly`, `aa_headsup`, `aa_stripe_audit`, `aa_partner_commissions`, `aa_drafts`, `aa_autosend`.

### Tests
All 4 endpoints validated:
- `top-topics`: ✅ aggregation returns valid structure
- `cash-flow`: ✅ £1,584/£95/£1,489 sensible figures
- `broadcast` (partner audience filter): ✅ correct "no users matched"
- `aa_anomaly` cron: ✅ registered

### Deployment
Production redeploy required. All env vars unchanged.
