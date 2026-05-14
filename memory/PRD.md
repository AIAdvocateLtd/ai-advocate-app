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

### Iter 6 — 4-tier subscription system
- Backend: `TIER_QUOTAS`, `tier_has_access()`, `check_quota_and_increment()`, `get_user_usage_summary()`
- Stripe webhook: `PRICE_TO_TIER` mapping → user.tier auto-set on checkout/update/cancel
- New endpoints: `/api/subscription/tiers`, `/api/subscription/portal`, `/api/subscription/usage`
- Endpoint gates: Plus-only for Practice/Voice/Contracts/Court categories; Pro-only for Live Assist + premium templates
- Quota gates: Free user 5 chats/day, 1 letter/mo, 1 photo/mo
- Frontend: 4-card SubscribeModal with BEST VALUE + YOUR PLAN badges; tile lock badges (🔒 PLUS/PRO); tier-aware banners
- Settings: Subscription card + Contact emails + Trustpilot link
- Bug fixes (caught by testing agent): CheckoutRequest Literal widened, TIER_QUOTAS keys aligned to feature names, unknown plan → clean 400, Free card shows £0/forever

### Iter 5 — Courtroom Trainer + Letter Library + Emergency
- Emergency Rights screen ("I've Been Arrested" red button) — works for ALL tiers including free
- Courtroom Trainer modal with 2 tabs: Practice Mode (Lex role-plays 8 hostile roles) + Live Legal Assist (continuous mic, ≤35-word advice per chunk, consent screen)
- Letter Library: 31 templates, 5 marked premium (Pro-only)

### Iter 4 — Apple Sign-In fix + Lex brain v2 + bulletproof T&C
- Apple Sign-In fully working (domain config + trailing slash + cleared stuck record)
- Lex brain auto-detects user language; smarter system prompt; ban on hallucinated citations
- "Hey Lex" wake-word (Plus+ only)
- Pure-black UI; mix-blend-mode for logo & avatars
- 22-section bulletproof Terms & Privacy

### Earlier
- Core MVP: Lex chat, photo evidence, multilingual PDF, law-firm directory, Stripe.

---

## Roadmap

### P1 (next)
- Capacitor iOS wrap (with Apple Reader-app compliance — hide Subscribe inside app, link to web)
- Capacitor Android wrap
- DNS cutover: aiadvocate.co.uk → preview backend
- Live Stripe webhook: replay test via Stripe CLI before launch
- Cloud backup (iCloud + Google Drive) — Plus+ tier
- Hey Lex toggle in Settings (currently always-on for Plus+)

### P2
- Case Files (group chats + uploads + letters by case timeline)
- Multi-image evidence (Pro only — already gated in matrix)
- One-click email PDF send
- Admin dashboard for law firm verification + sponsored toggle
- Trustpilot widget on website footer
- "Read aloud" emergency rights (TTS for arrest scenario)
