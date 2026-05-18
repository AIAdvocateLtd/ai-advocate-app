# AI Advocate — Product Requirements (v2)

## Product
A multilingual "lawyer in your pocket" web + iOS + Android app. Core: Lex AI chat (Claude 4.5), photo evidence (Gemini), voice in/out, multilingual PDF letters, law-firm directory, **4-tier Stripe subscription**.

## Brand & UX
- Pure-black (#000) background, gold accents (#f7c948), Cinzel serif for headings, Heraldic SVG icons, Lex avatar character (mix-blend-mode lighten).
- RTL support for Arabic & Urdu. 11 languages total.

## Trial economics (UPDATED 2026-02-16)
- 14-day trial_pro tier protects LLM costs via tighter caps than paid Pro:
  - lex_chat: 50/day, evidence_analyze: 10/mo, doc_analyze: 10/mo, letters_generate: 5/mo
  - deep_think: 5/mo (vs Pro 30/mo), live_assist: 1 session/day, files_total: 20

## Firm Tiers (UPDATED 2026-02-16 — consolidated to 2)
| Tier | Price | What firm gets |
|---|---|---|
| Featured | £49 / mo | Top-of-list placement, Sponsored badge, gold border, direct enquiries |
| Premium Sponsor | £149 / mo | Hero card, Verified ✓ badge, logo slot, direct call CTA |

`STRIPE_PRICE_FIRM_VERIFIED` (£19) tier is REMOVED. `/api/firm/subscribe` rejects `verified` plan with 400.

## Round-1 New Features (2026-02-16)
- ✅ **Live Mode timestamped notes** — every utterance during police interview / disciplinary / tribunal is logged with millisecond UTC timestamps (`POST /api/live/notes`); list & PDF export endpoints added (`GET /api/live/sessions`, `GET /api/live/notes/{id}/export`). Frontend wires into existing CourtroomModal Live tab; Export PDF button appears after session.
- ✅ **Document/Letter Auto-Responder** — new tile "Letter Reader" on dashboard. User snaps any letter; Gemini vision returns category + summary + deadlines + drafted response + next_steps + severity in strict JSON. Auto-creates case_items entry AND auto-creates `doc_auto` reminders for every extracted deadline (status=pending, kind=deadline). Endpoint: `POST /api/document/analyze`.
- ✅ **Smart Deadline Tracker** — flows from doc analysis above; reminders appear in default `GET /api/reminders` listing.
- ✅ **Thumbs up/down feedback** — every Lex chat reply has `fb-up-{i}` / `fb-down-{i}` buttons; persists to `feedback` collection via `POST /api/feedback`.
- ✅ **Daily "Know Your Rights" tip** — `GET /api/tips/daily?language&country` cached per-day per-language. Renders as DailyTipCard at top of dashboard.

## Round-2 New Features (2026-02-16)
- ✅ **File deletion** — customer-facing trash icons on every legal file row and a Delete button in detail view (`DELETE /api/legal-files/{id}`).
- ✅ **Outcome Predictor** — % chance of success with similar past cases cited by name (e.g. Superstrike v Rodrigues). `POST /api/outcome/predict`. New tile.
- ✅ **Lawyer Cost Estimator** — likely solicitor fee range + court fees + hourly rate + no-win-no-fee flag + "AI Advocate covers this" upsell. `POST /api/cost/estimate`. New tile.
- ✅ **Hearing Recorder** — Whisper STT transcript + structured analysis (summary / favourable / unfavourable / next actions / deadlines). `POST /api/hearing/transcribe`. New tile.
- ✅ **Free Legal Aid Finder** — UK means-test (£2,657/mo income, £8,000 savings) + category-specific signposts (Citizens Advice / Law Centres / Shelter / ACAS / Right to Remain). `POST /api/legal-aid/check`. New tile.
- ✅ **Case Sharing read-only links** — 30-day public token for any case. `POST /api/cases/{id}/share`, `GET /api/share/{token}` (no auth), `DELETE /api/cases/{id}/share` revokes. Share button in CaseFilesModal.
- ✅ **Anonymous Stats Wall** — `GET /api/stats/public` (no auth, 5-min cache). Renders "AI Advocate by the numbers" card at bottom of dashboard.

## Auth
- Email/password (custom JWT)
- Apple Sign-In — ✅ WORKING (Services ID: `app.aiadvocate.signin`, domain `ai-law-guide-1.preview.emergentagent.com`, return URL with trailing `/`)
- Google Sign-In — ✅ WORKING (OAuth2 popup flow via `initTokenClient`, server-side userinfo verification 2026-02-16)

## Branding
- ✅ Splash screen (2026-02-16): 3D gold logo reveal video (`/assets/splash.mp4`, 1.3 MB, 560×560). Plays once per browser-tab session, 4-sec hard cap, 70vw centred, tap-to-skip. Fades into existing flow (lang/terms/auth).

## AI Stack (Emergent LLM Key)
- **Chat (Lex):** Claude Sonnet 4.5 with court-prep-grade system prompt + auto-detect-language
- **Vision:** Gemini 2.5 Flash
- **Voice:** OpenAI Whisper STT + OpenAI TTS
- **Wake word:** Web Speech API ("Hey Lex")

## Subscription Tiers (LIVE Stripe)
| Tier | Price | Stripe Price ID (env var) |
|---|---|---|
| Free | £0 | n/a |
| Plus | £14.99 / mo | `STRIPE_PRICE_PLUS` (currently `price_1TX0CcFh8lRHrXPI3feMOlOx`) |
| **Pro** | **£29.99 / mo** ⬆ (was £24.99) | `STRIPE_PRICE_PRO` — **NEEDS NEW STRIPE PRICE OBJECT** at £29.99 |
| **Yearly Pro** | **£299.99 / yr** ⬆ (was £239.99) | `STRIPE_PRICE_YEARLY_PRO` — **NEEDS NEW STRIPE PRICE OBJECT** at £299.99 |

### ⚠️ Critical: Stripe price IDs are immutable
The Pro + Yearly Pro UI now shows the new prices, but Stripe will still charge the old amounts until you create new Price objects:
1. Go to Stripe Dashboard → Products → Pro (and Yearly Pro)
2. Click "Add another price" → enter new amount (£29.99 / £299.99)
3. Copy the new `price_xxx` IDs
4. Update `/app/backend/.env`:
   - `STRIPE_PRICE_PRO="price_NEW..."` 
   - `STRIPE_PRICE_YEARLY_PRO="price_NEW..."`
5. Restart backend (`sudo supervisorctl restart backend`)
6. Existing subscribers stay on their old £24.99 / £239.99 prices until they cancel & re-subscribe (this is fair grandfathering — they're locked in at the price they signed up for).

New signups get 14-day **trial_pro** (full Pro features). After trial → drop to Free unless subscribed.

## Tier Access Matrix
- **Free:** 5 chats/day, 1 photo/mo, 1 letter/mo, 3 files, view templates only, no court categories, no Practice, no Live Assist, no voice. Emergency Rights + Lawyer Directory always free. **TTS Read-Aloud capped at 20/day.**
- **Plus £14.99:** Unlimited chats (100/day fair use), 15 photos/mo, unlimited letters, Court Prep modes, Voice in/out, Practice Mode, 50 files, Contract Review, Hey Lex wake-word. Claude **Sonnet 4.5** brain.
- **Pro £29.99:** Plus everything + Live Legal Assist (**3 sessions/day**), **Deep Think 30/mo** (Sonnet 4.5 + extended reasoning), Premium templates, priority queue, unlimited everything.
- **Yearly Pro £299.99:** Pro at ~17% discount + **Deep Think 50/mo** + **Live Assist 5 sessions/day** (premium perks for annual commitment).

## Legal
England & Wales + ICC arbitration + GDPR + CCPA. 22-section Terms + 10-section Privacy. Forced "I Agree" at signup.

## Domain
- Production: `aiadvocate.co.uk` (owned by user)
- Preview: `ai-law-guide-1.preview.emergentagent.com`

## Contact Emails (live in Settings)
- support@aiadvocate.co.uk (customer help)
- admin@aiadvocate.co.uk (business)
- press@aiadvocate.co.uk (media)
- info@aiadvocate.co.uk (general)
- Trustpilot: https://www.trustpilot.com/review/aiadvocate.co.uk

---

## Changelog

### Iter 9 — Full roadmap blitz: Cases · Video · Reminders · Firm Portal · Admin · Capacitor · Backup · Smart Review (Feb 2026)

**Backend testing: 21/21 PASS** · **Frontend Cases flow verified end-to-end**

**🗂️ Case Files**
- `POST/GET/PATCH/DELETE /api/cases` — full CRUD per user
- `POST /api/cases/{id}/items` — attach chats, photos, videos, letters, notes
- `POST /api/cases/{id}/auto-name` — **Lex auto-names cases** from first 5 items via Haiku 4.5 (with Sonnet fallback). Examples: "Deposit Recovery — Landlord", "Parking PCN Appeal"
- `GET /api/cases/{id}/export-pdf` — court-ready PDF with timestamps + locations + SHA-256 evidence hashes
- Frontend `CaseFilesModal` with create / rename / delete / detail view / Escape-to-close
- Each item shows item-type badge + preview + UTC timestamp + GPS pin if available

**🎥 Video Recording + Lex Analysis (Pro tier)**
- `POST /api/video/analyze` accepts audio extracted from video → Whisper STT → Lex Sonnet 4.5 in `record` category
- Lex flags rights violations, leading questions, drafts a complaint letter / defence statement
- Tier-gated: 402 for free, monthly evidence quota enforced
- Auto-attaches to a `case_id` if provided
- SHA-256 evidence hash stored

**⏰ Limitation-Period Reminders (the killer feature)**
- `POST /api/reminders/detect` — Lex extracts deadlines from any chat message (e.g. "you have 14 days to challenge"). Returns JSON list of `{title, due_at, kind}`
- Frontend integration in `LexChat`: after every user message, a fire-and-forget call surfaces a **⏰ Deadline detected** card with one-tap "Add to reminders"
- Full Reminder CRUD + datetime-local picker in `RemindersModal`
- Visual urgency: red border when ≤3 days out, with "Xd left" / "Xd overdue"

**🏛️ Law Firm Portal**
- `POST /api/firm/signup` + `/api/firm/login` (separate auth, JWT `kind=firm`)
- `GET /api/firm/me` — returns firm profile + recent leads (inquiries)
- `PATCH /api/firm/listing` — firms edit their own directory listing (gated until admin approves)
- `POST /api/firm/subscribe` — Stripe checkout for **£49/mo Featured** or **£19/mo Verified** (price IDs come from new env vars `STRIPE_PRICE_FIRM_FEATURED` + `STRIPE_PRICE_FIRM_VERIFIED`)

**👨‍💼 Admin Dashboard**
- `ADMIN_EMAILS` env var (default `admin@aiadvocate.co.uk`) gates `require_admin` dependency
- `GET /api/admin/stats` — users by tier, firms by status, daily chat / lead counts
- `GET /api/admin/firms` — list w/ status filter
- `POST /api/admin/firms/action` — `approve | reject | suspend | verify | unverify`; on approve auto-creates the public `lawfirms` row

**📱 Capacitor Wrap (Reader-App compliant)**
- `/app/frontend/capacitor.config.json` — appId `uk.co.aiadvocate.official`
- `/app/frontend/CAPACITOR_SETUP.md` — full step-by-step for Xcode + Android Studio: `npx cap add ios/android`, Info.plist + AndroidManifest permissions, App Store Connect submission checklist
- Frontend `IS_NATIVE` detection — hides all Subscribe / Upgrade buttons inside iOS native binary (passes Apple Guideline 3.1.3(a))
- Subscribe banners replaced with web-link "Manage on aiadvocate.co.uk" in native mode

**☁️ Cloud Backup**
- `GET /api/backup/export` — Plus+ feature; returns a JSON file with all cases + conversations + evidence + letters + reminders + recordings (GDPR data-portability compliant)
- Settings → Cloud Backup card → one-click download
- User can then save the JSON to iCloud Drive / Google Drive via their phone's Share sheet (no third-party OAuth required, no credentials handling)

**⭐ Smart Pre-Renewal Trustpilot Reminder (your spec, not pushy)**
- `GET /api/review/should-prompt` — returns `should_prompt: true` ONLY when:
  - Trial user with ≤2 days left (ceil-based — last 12h users get prompted), OR
  - Paid user with renewal ≤7 days away
- AND user hasn't already reviewed (`review_left: true`)
- `POST /api/review/recorded` — sets the flag when user clicks through to Trustpilot
- Frontend `ReviewPrompt` modal opens once per session if backend says so
- **No more chat-count nagging** — only fires at the moment a user is deciding whether to renew

**🐛 Bug fixes (caught by testing agent)**
- `review_should_prompt` read `trial_days_remaining` from raw DB doc (where it's never stored) — fixed to read from `user_to_public()` result. Plus ceil-based comparison so last-24h users still get prompted
- `CaseFilesModal` Escape now closes detail-view first, then whole modal
- TIER_QUOTAS key naming alignment (`live_assist_session_daily` matches `feature + _daily` convention)
- `STRIPE_SECRET_KEY` typo → `STRIPE_API_KEY`

### Iter 8 — Tier-Based Lex Brain + Auto-Detect Language + Evidence-grade UX (Feb 2026)
**Tier-Based Lex Brain**: Free → Haiku 4.5 · Plus → Sonnet 4.5 · Pro/Trial → Sonnet 4.5 + Deep Think. 14-day trial gets full Pro brain.
**Sharper system prompt**: IRAC method, banned hedge-phrases, confidence rating (High/Medium/Low).
**Auto-detect language**: 3-layer detector (Unicode script + word-boundary regex) — 11/11 tests pass.
**Native Contact Picker** + Read-aloud Emergency Rights (TTS) + 11-language i18n full coverage + chat timestamps.
**Bug fixes**: Send-btn z-index intercept fixed, French-vs-Spanish ` la ` overlap fixed.

---

## Roadmap

### P1 (next session — high impact)
- **Stripe Firm Pricing Setup** — user must create new Price objects in Stripe Dashboard for £49/mo Featured + £19/mo Verified, then add `STRIPE_PRICE_FIRM_FEATURED` + `STRIPE_PRICE_FIRM_VERIFIED` to `/app/backend/.env`. Backend will then unlock firm billing.
- **Pro Pricing Stripe Setup** — user must create new £29.99 + £299.99 Price objects in Stripe Dashboard, swap the env vars `STRIPE_PRICE_PRO` + `STRIPE_PRICE_YEARLY_PRO`.
- **Native iOS/Android build** — run `npx cap add ios/android` on a Mac with Xcode (see `CAPACITOR_SETUP.md`)
- **Admin Dashboard Frontend UI** — currently backend-only; build `/admin` route for one-click firm approval
- **Firm Portal Frontend UI** — currently backend-only; build `/firm-portal` route for firm self-service
- **In-app Video Recording UI** — current backend works via audio upload; build the camera+mic React component to actually record + extract audio + POST to `/api/video/analyze`
- **Refactor `/app/backend/server.py`** (~2737 lines) into routers: auth, lex, cases, reminders, firm, admin, subscription, voice, webhook

### Future / Backlog
- DNS cutover: aiadvocate.co.uk → backend (manual user task — DNS provider)
- Limitation-period reminder push notifications (web push + iOS native)
- iCloud-Drive direct write integration (currently manual JSON download)
- Cleanup script for TEST_iter*@advocate.app users from previous test runs
**Tier-Based Lex Brain (the "average lawyer → partner steps in" model)**
- Free → Claude Haiku 4.5 (paralegal-grade, fast)
- Plus → Claude Sonnet 4.5 (solicitor-grade)
- Pro / trial_pro → Claude Sonnet 4.5 + **Deep Think** toggle (King's Counsel-grade reasoning, 4096 tokens)
- 14-day trial gets full Pro brain as a taster — drives conversion
- Automatic Sonnet fallback if Haiku/Opus model id is unavailable (never blocks the user)

**Lex system prompt v3 — sharper reasoning**
- **IRAC** method enforced (Issue → Rule → Application → Counter → Action → Flag)
- **Banned hedge-phrases** (no more "I'm not a lawyer" mid-answer)
- **Confidence rating** appended (High/Medium/Low) so users know when to double-check
- Strict citation discipline — never invent statutes; say "I don't recall the exact section" if unsure
- **STRICT language lock** — Lex replies in user's chosen language only, no English fallback unless user types English

**Auto-detect language (3-layer)**
- Score-based detector for all 11 languages (Unicode-script majority + word-boundary regex)
- Auto-detect toggle in Settings (default ON)
- Returns `reply_language` and `model` in chat response for transparency
- 22/22 pytest including overlap-regression cases (es-vs-fr `la`, fr-vs-de, etc.)

**Native Contact Picker for Emergency Contact**
- Web `navigator.contacts.select()` API (Chrome Android, some iOS)
- Graceful fallback to manual name + phone inputs if API unavailable

**Read-Aloud Emergency Rights (TTS)**
- Tap a button on the Emergency Modal — Lex reads the user's rights aloud
- Critical for distress moments (arrested, can't read on phone)
- TTS now allows short text (<1500 chars) for all tiers (safety carve-out); long-form voice stays Plus+

**Evidence-grade timestamps**
- Every chat message bubble shows a locale-formatted timestamp underneath (court-ready)
- Each message dict stores `at: ISO-8601 UTC` server-side

**Global i18n completeness — 11 languages × ~70 new keys**
- Emergency modal, SMS buttons, Multi-photo, Voice Mode, Settings, Letter Library, Practice Mode, Live Assist all fully translated (Spanish, French, Arabic, Polish, German, Hindi, Urdu, Italian, Portuguese, Chinese)
- 4 new Settings toggles (Hey Lex, Auto-detect language, Location stamp on evidence, Native Contact Picker)

**Frontend chat modal — fixed send-btn click intercept**
- Z-index of `.modal-bg` bumped to 9999, `.modal-card` to 10000
- 56px bottom-padding on chat input row so preview-badge no longer overlays send-btn

### Iter 6 — 4-tier subscription system
- Backend: `TIER_QUOTAS`, `tier_has_access()`, `check_quota_and_increment()`, `get_user_usage_summary()`
- Stripe webhook: `PRICE_TO_TIER` mapping → user.tier auto-set on checkout/update/cancel
- New endpoints: `/api/subscription/tiers`, `/api/subscription/portal`, `/api/subscription/usage`
- Endpoint gates: Plus-only for Practice/Voice/Contracts/Court categories; Pro-only for Live Assist + premium templates
- Quota gates: Free user 5 chats/day, 1 letter/mo, 1 photo/mo
- Frontend: 4-card SubscribeModal with BEST VALUE + YOUR PLAN badges; tile lock badges (🔒 PLUS/PRO); tier-aware banners
- Settings: Subscription card + Contact emails + Trustpilot link
- Bug fixes: CheckoutRequest Literal widened, TIER_QUOTAS keys aligned, unknown plan → 400, Free card shows £0/forever

### Iter 5 — Courtroom Trainer + Letter Library + Emergency
- Emergency Rights screen ("I've Been Arrested" red button) — works for ALL tiers including free
- Courtroom Trainer modal with Practice Mode (Lex role-plays 8 hostile roles) + Live Legal Assist (≤35-word advice per chunk, consent screen)
- Letter Library: 31 templates, 5 marked premium (Pro-only)

### Iter 4 — Apple Sign-In fix + Lex brain v2 + bulletproof T&C
- Apple Sign-In fully working (domain config + trailing slash)
- Lex brain auto-detects user language; "Hey Lex" wake-word (Plus+ only)
- Pure-black UI; mix-blend-mode for logo & avatars
- 22-section bulletproof Terms & Privacy

### Earlier
- Core MVP: Lex chat, photo evidence, multilingual PDF, law-firm directory, Stripe.

---

## Roadmap

### P1 (next session — high impact)
- **Video recording with Lex analysis** — record police/public encounter in-app, Whisper transcript + Gemini frame sample → Lex flags rights violations / drafts complaint letter (Pro tier)
- **Case Files** — group chats / photos / videos / letters per case; Lex auto-names case (renameable)
- **Law Firm Portal** — separate auth, self-register w/ SRA verification, Stripe £49/mo Featured + £19/mo Verified, lead-tracking PPC
- **Admin Dashboard** — approve/reject firm applications, manage Verified badge
- **Capacitor iOS/Android wrap** — Reader-app compliance (hide Stripe inside native iOS to pass Apple Review)
- **iCloud + Google Drive Backup** — Plus+ tier
- **Trustpilot prompt** — after 3 helpful chats, prompt user for review
- **Per-day TTS quota for free tier** (20 calls/day) — protect OpenAI billing
- **Sonnet fallback monkeypatched unit test** — covers Haiku failure path
- **Tagline translation** — currently baked into logo image; designer task to make it text-based

### P2 (later)
- Limitation-period reminders — Lex detects deadlines from chat ("you have 6 months to file") and offers to add calendar reminder
- Multi-image evidence (already gated in Pro matrix)
- One-click email PDF send
- DNS cutover: aiadvocate.co.uk → preview backend
- Live Stripe webhook: replay test via Stripe CLI before launch
- Split `/app/backend/server.py` (~2137 lines) into routers (auth/lex/letters/subscription/voice/webhook)


## Contract Tools merge (2026-02-17)
- ✅ Merged separate **Contract Reader** and **Contract Drafter** tiles into a single `Contract Tools` tile (id: `contracts`, free access).
- ✅ New `ContractsHubModal` with tabbed UI (`Read` | `Draft`). Draft tab is Plus-gated; tap by Free users triggers Plus upsell.
- ✅ Read tab now exposes **two distinct CTAs**: `Take photo` (capture=environment opens device camera) and `Upload file` (no capture, opens gallery/file picker; accepts images, PDFs, docx/txt).
- ✅ Selected file preview chip + image thumbnail before analysis.
- ✅ Fixed previous wiring bug — `contract_read`/`contract_draft` tiles had no router entry and fell through to chat (modal renderers never fired). New `contracts` route wired up correctly.
- ✅ Verified `POST /api/contract/draft` returns valid contract text (NDA test passed via curl — LLM budget healthy).
- New i18n keys (en-GB): `contractTools`, `contractTabRead`, `contractTabDraft`, `contractTakePhoto`, `contractUploadFile`. Other languages fall back to English via existing `t()` helper.
- Files touched: `/app/frontend/src/App.js`, `/app/frontend/src/i18n.js`.


## Contract Negotiate (Pro flagship) + tier re-map (2026-02-17)
- ✅ **New `Negotiate` tab** inside Contract Tools — Pro-only flagship feature.
- ✅ Backend: `POST /api/contract/negotiate` returns worst_clauses[] with verbatim quotes + suggested_redline + fallback_position + priority, plus missing_protections, do_not_compromise_on, walk_away_signals, negotiation_strategy, ready_to_send_email (full professional email), estimated_negotiation_difficulty.
- ✅ Frontend `ContractNegotiateBody` — dual Camera/Upload buttons, user-role selector (recipient/offerer), priorities textarea, rich result UI with priority-coloured clause cards + copyable email.
- ✅ **Tier re-map (Plus → Pro):** Outcome Predictor, Hearing Recorder, Contract Drafter, Contract Negotiate now all require Pro tier. Backend `FEATURE_MIN_TIER` enforces; frontend tiles display PRO lock badges for Plus/Free users; Contract Tools hub Read tab stays free, Draft + Negotiate tabs show inline PRO badge and trigger Pro upsell on tap.
- ✅ **Bug fix:** `/contract/analyze` (Read tab) was silently broken — Claude doesn't accept file attachments via emergentintegrations. Refactored to 2-stage pipeline: Gemini Flash extracts verbatim text → Claude Sonnet does the legal analysis. Same pipeline applied to `/contract/negotiate`.
- ✅ **Latency tuning:** Reduced max_tokens (extract 8000→4000, analyze 4000→2800, negotiate 4500→3000) so external-ingress round-trip fits comfortably under the 60s nginx proxy_read_timeout. Verified ~57s end-to-end via public URL.
- New i18n keys (en-GB): `contractTabNegotiate`, `neg*` (15 keys).
- Tests: `/app/backend/tests/test_iter12_contracts.py` — 9/9 passing.
- Files touched: `/app/backend/server.py`, `/app/frontend/src/App.js`, `/app/frontend/src/i18n.js`.

### Pricing ladder (current)
- **Free** — Triage: Snap Evidence, Letter Reader, Contract Read, Find Lawyer, Legal Aid, Cost Estimator, Files/Cases/Reminders, Letter Library, Emergency Mode.
- **Plus £14.99** — Daily AI lawyer: Ask Lex, all category chats (immigration/employment/property/medical), Courtroom Trainer, Record Legal Interaction.
- **Pro £29.99** — Pro outcomes: Outcome Predictor (Opus), Contract Drafter, **Contract Negotiate**, Hearing Recorder, Opus Deep Think, "Hey Lex" wake-word.


## Email-this-draft + Pro upsell hooks (2026-02-17)
- ✅ **"Email this draft" button** added to Contract Negotiate result. Parses the `Subject:` first line of Lex's email automatically, then opens a `mailto:` link with subject + body pre-filled. Optional recipient field; works on iOS Safari and Capacitor wrapper.
- ✅ **Read → Negotiate upsell card** appears at the bottom of Contract Read result whenever red_flags or amber_flags are present. One-tap card with PRO badge that switches to Negotiate tab (and triggers Pro paywall for non-Pro users). Highest-converting moment in the contract flow.
- New i18n keys: `negSendEmail`, `negSendEmailHint`, `negRecipientEmail`, `negRecipientPlaceholder`, `readUpsellTitle`, `readUpsellSub`.

## Tier-locking strategy (decided 2026-02-17)
After review: deliberately NOT locking more features behind Pro. Current ladder is the right balance:
- Locking safety/triage tools (Snap Evidence, Letter Reader, Legal Aid, Find Lawyer) would risk App Store rejection in regulated category AND kill the conversion funnel.
- Instead, monetisation moves to **inline upsell hooks at aha moments** — Contract Read → Negotiate (Pro) is the first. Follow-ups planned: Letter Read → "Draft a reply with Lex" (Plus), Snap Evidence → "Predict your outcome" (Pro).


## Pricing v3 + Mic permission fix (2026-02-17)
### Pricing changes
- Pro tier price: £29.99 → **£34.99** (justified by exclusive flagship Pro features: Outcome Predictor, Contract Drafter + Negotiate, Hearing Recorder, Opus Deep Think).
- Yearly Pro: £299.99 → **£319.99** (24% off vs monthly Pro — saves user £100/year).
- Free trial: 14 days → **7 days** (across all 3 signup paths: email, Google, Apple). LLM cost per trial user drops from ~£1.70 to ~£0.85 average.
- ToS text updated: "14-day free trial" → "7-day free trial".
- `subscription/tiers` API response updated with new prices + new highlights (Pro now mentions Outcome Predictor, Contract Drafter + Negotiate, Hearing Recorder).
- ⚠️ **MANUAL STEP REQUIRED:** The actual amounts charged are controlled by Stripe Price IDs in `.env` (`STRIPE_PRICE_PLUS`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_YEARLY_PRO`). User must create new prices in Stripe Dashboard at £14.99/£34.99/£319.99 and update `.env` before launch.

### Mic-permission popup bug fix
- **Root cause:** On cold-open with a stored auth token, the Dashboard mounted while the splash video was still playing → `useHeyLex` started SpeechRecognition → iOS Safari showed the mic permission prompt over the splash. Made worse by Hey Lex defaulting to ON.
- **Fix 1:** Dashboard now only renders after `showSplash === false` (App.js line 4500). Eliminates the race condition.
- **Fix 2:** `wakeOn` (Hey Lex wake-word) default changed from ON → **OFF** (opt-in via Settings). No mic prompt fires automatically — only when user explicitly enables the toggle.
- iOS Safari security note: when the prompt does fire, iOS forces it to display the domain ("ai-law-guide-1.preview...") as a security feature — we cannot suppress that in a webapp context. Will be replaced with "AI Advocate" once we ship the Capacitor wrapper, or `aiadvocate.co.uk` once you swap to your real domain.

### Tier-locking decision (final)
After review: NOT locking more tabs. Free → Plus → Pro ladder stays. Auto-trial gives every new user 7 days of full Pro access; tier locks only apply after trial ends without subscription. App Store compliance + funnel velocity preserved.

## Security overhaul + Lex Vault + Smart routing + Feature suggest (2026-02-18)

### 🔐 Field-level encryption at rest
- New module `/app/backend/app_crypto.py` — Fernet (AES-128-CBC + HMAC-SHA256) helper.
- `AA_DATA_KEY` added to `/app/backend/.env` (32-byte base64 key). Encryption auto-disables if missing (dev-safe).
- Encrypted fields in MongoDB at rest (transparent encrypt-on-write, decrypt-on-read):
  - `conversations.user_message` and `conversations.assistant_response` (Lex chat history)
  - `cases.summary`, `case_items.description`
  - `vault_items.file_b64` and `vault_items.notes_enc` (defence-in-depth on top of client encryption)
- Verified: DB rows now start with `enc:v1:gAAA...` prefix, plain `find_one()` returns ciphertext.
- Existing plaintext rows are gracefully handled (no migration required — read path passes plaintext through unchanged).

### 🔒 Lex Vault — zero-knowledge encrypted storage
**Triple-layer security:** Client AES-GCM-256 (PIN-derived via PBKDF2 250k iterations) → Server Fernet (AA_DATA_KEY) → TLS in transit.
- New tile **"Lex Vault"** (free for all users; categorised storage cap by tier: free=5, plus=25, pro=200 items).
- 12MB per-item limit.
- Endpoints: `GET /api/vault/status`, `POST /api/vault/setup`, `POST /api/vault/unlock`, `GET /api/vault/items`, `GET /api/vault/items/{id}`, `POST /api/vault/items`, `DELETE /api/vault/items/{id}`, `POST /api/vault/wipe`, `POST /api/vault/share` (7-day expiring share links).
- New client helper `/app/frontend/src/vaultCrypto.js` — WebCrypto wrappers for PBKDF2, AES-GCM, base64.
- New `VaultModal` with PIN setup → lock/unlock → categorised list (Evidence/Contracts/Letters/ID/Witness/Court/Other) → upload with encrypted notes → encrypted download → panic-wipe with confirmation.
- Server NEVER sees the PIN. Only stores SHA-256(PIN || salt) verifier + the salt. If the user forgets their PIN, items are unrecoverable.
- Two new heraldic SVG icons: `VaultIcon` (shield + keyhole) and `SuggestIcon` (lightbulb).

### 🧠 Smart category routing
- New endpoint `POST /api/lex/classify` — uses Haiku to classify a free-text question into one of {employment, property, immigration, criminal, family, medical, consumer, debt, tax, general}.
- Frontend: after the first user message in general "Ask Lex" chat, the result is shown as a banner: *"Looks like Employment Law. Switch to the dedicated chat?"* — one-tap switches modal to that category (triggers Plus paywall for free users).
- Banner is dismissable + only fires once per session.

### 💡 Suggest-a-feature
- New endpoint `POST /api/feedback/suggest` — stores in `feature_requests` collection with user email + free text. Lightweight, no LLM.
- Dashboard footer: "Missing a legal area?" dashed-gold pill that opens `SuggestFeatureModal`. Confirmation screen on submit.
- Use this data to drive product roadmap post-launch (top 5 most-requested categories become tile candidates).

### Lex chat history history endpoint also now transparently decrypts.

Files touched: `/app/backend/server.py`, `/app/backend/app_crypto.py` (new), `/app/backend/.env`, `/app/frontend/src/App.js`, `/app/frontend/src/icons.js`, `/app/frontend/src/i18n.js`, `/app/frontend/src/vaultCrypto.js` (new).



## Biometric Vault unlock (2026-02-18)
- ✅ New helper `/app/frontend/src/vaultBiometric.js` — WebAuthn platform-authenticator integration.
- ✅ Detects support via `PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()`.
- ✅ After PIN unlock, user can opt-in via gold pill: "Biometric unlock — Use Face ID / Touch ID to unlock faster" + "Turn on" button.
- ✅ Setup flow: `navigator.credentials.create()` with `authenticatorAttachment: "platform"`, `userVerification: "required"` → registers a platform passkey (Face ID / Touch ID / Windows Hello / Android biometric).
- ✅ PIN encrypted with AES-GCM (key derived from credential `rawId` via SHA-256), stored in localStorage.
- ✅ Locked screen shows gold "Unlock with Face ID / Touch ID" button when bio enabled — triggers `navigator.credentials.get()` → decrypts PIN → verifies with server → unlocks silently.
- ✅ Bio record auto-cleared if server-side PIN mismatches (e.g. after vault wipe). UX self-heals.
- ✅ Wipe vault also clears local biometric record.
- New i18n keys: `vaultBioTitle`, `vaultBioOn`, `vaultBioOff`, `vaultBioTurnOn`, `vaultBioTurnOff`, `vaultBioUnlock`.
- **Production note:** When we wrap with Capacitor (P1), swap localStorage backing for iOS Keychain / Android Keystore for true device-level encryption.
