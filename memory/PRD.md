# AI Advocate — Product Requirements (v2)

## Product
A multilingual "lawyer in your pocket" web + iOS + Android app. Core: Lex AI chat (Claude 4.5), photo evidence (Gemini), voice in/out, multilingual PDF letters, law-firm directory, **4-tier Stripe subscription**.

## Brand & UX
- Pure-black (#000) background, gold accents (#f7c948), Cinzel serif for headings, Heraldic SVG icons, Lex avatar character (mix-blend-mode lighten).
- RTL support for Arabic & Urdu. 11 languages total.

## Auth
- Email/password (custom JWT)
- Apple Sign-In — ✅ WORKING (Services ID: `app.aiadvocate.signin`, domain `ai-law-guide-1.preview.emergentagent.com`, return URL with trailing `/`)
- Google Sign-In — ✅ WORKING (Client ID wired in env; button verified rendering on auth screen 2026-02-16)

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
