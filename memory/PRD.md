# AI Advocate — Product Requirements (v2)

## Product
A multilingual "lawyer in your pocket" web + iOS + Android app. Core: Lex AI chat (Claude 4.5), photo evidence (Gemini), voice in/out, multilingual PDF letters, law-firm directory, **4-tier Stripe subscription**.

## Brand & UX
- Pure-black (#000) background, gold accents (#f7c948), Cinzel serif for headings, Heraldic SVG icons, Lex avatar character (mix-blend-mode lighten).
- RTL support for Arabic & Urdu. 11 languages total.

## Auth
- Email/password (custom JWT)
- Apple Sign-In — ✅ WORKING (Services ID: `app.aiadvocate.signin`, domain `ai-law-guide-1.preview.emergentagent.com`, return URL with trailing `/`)
- Google Sign-In — code ready, env var set, awaiting verify by user

## AI Stack (Emergent LLM Key)
- **Chat (Lex):** Claude Sonnet 4.5 with court-prep-grade system prompt + auto-detect-language
- **Vision:** Gemini 2.5 Flash
- **Voice:** OpenAI Whisper STT + OpenAI TTS
- **Wake word:** Web Speech API ("Hey Lex")

## Subscription Tiers (LIVE Stripe)
| Tier | Price | Stripe Price ID |
|---|---|---|
| Free | £0 | n/a |
| Plus | £14.99 / mo | `price_1TX0CcFh8lRHrXPI3feMOlOx` |
| Pro | £24.99 / mo | `price_1TX0EKFh8lRHrXPIPLZzGSoT` |
| Yearly Pro | £239.99 / yr | `price_1TX0IgFh8lRHrXPInG4THCC1` |

New signups get 14-day **trial_pro** (full Pro features). After trial → drop to Free unless subscribed.

## Tier Access Matrix
- **Free:** 5 chats/day, 1 photo/mo, 1 letter/mo, 3 files, view templates only, no court categories, no Practice, no Live Assist, no voice. Emergency Rights + Lawyer Directory always free.
- **Plus £14.99:** Unlimited chats (100/day fair use), 15 photos/mo, unlimited letters, Court Prep modes, Voice in/out, Practice Mode, 50 files, Contract Review, Hey Lex wake-word.
- **Pro £24.99:** Plus everything + Live Legal Assist, Premium templates (witness statement, mitigation, defence statement, immigration, asylum), priority queue, unlimited everything.
- **Yearly £239.99:** Pro at 20% discount.

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

### Iter 8 — Intelligence + Language + Evidence-grade UX
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
