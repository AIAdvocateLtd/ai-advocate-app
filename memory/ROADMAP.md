# AI Advocate — Roadmap (post Session 2a)

## 🔔 Owner Reminders (also live inside the app — log in as admin@aiadvocate.co.uk and check Reminders)

### Reminder 1 — 2026-03-15 — Review Tavily usage
- Check `GET /api/admin/rag-usage` (admin-only).
- If trending above **600 calls / month**, upgrade Tavily plan.
- Tavily "Researcher" paid plan: ~£25/mo → 4,000 credits. Step up well *before* you hit the 900 hard-cap.

### Reminder 2 — 2026-04-01 — Add vLex (paid UK case-law API)
- **Trigger:** ≥ £500/mo MRR OR ≥ 100 active Plus/Pro users — whichever first.
- Sign up: **https://vlex.com/api** (request a partner/API quote; typically £150-300/mo at low volume).
- Why: deeper UK case law beyond BAILII's free corpus, including unreported judgments + commentary. Big credibility boost for paying tier.
- Implementation: drop into `/app/backend/rag.py` as a third source alongside Tavily — append vLex hits with their own `[v1]` `[v2]` citation prefix.

### Reminder 3 — 2026-05-01 — Build Clio Firm Portal sync
- **Trigger:** first UK firm asks to sync their Clio cases.
- Apply for Clio Developer Account at **https://developers.clio.com**.
- Build OAuth flow + case-thread sync (Clio Manage API → AI Advocate `engagements` collection).
- Apply for **Clio App Marketplace** listing → free distribution to 150,000+ firms.

---

## P0 — Pre-launch (still pending)
- Capacitor iOS/Android wrap (`capacitor.config.json` scaffolded).
- Case Timeline View polish for App Store screenshots.
- Native iOS Keychain replacement for Vault PIN (Web Crypto → SecKey).

## P1 — Post-launch v1.0
- SSE streaming for Lex chat (perception speed).
- SiriKit Shortcuts / iPhone Action Button mapping ("Hey Siri, ask AI Advocate…").
- Native Speech/TTS via AVSpeechSynthesizer to cut latency.
- TestFlight beta + App Store metadata.
- 2FA login.
- Push notifications for deadlines.

## P2 — v1.1+
- **Clio Firm Portal sync** (see Reminder 3 above).
- Solicitor Marketplace.
- Trustpilot wall on dashboard.
- Lex Auto-File global search.
- Render inline citation pills `[1]` `[2]` as clickable in chat (opens BAILII / legislation.gov.uk in new tab).

## P3 — v1.2+
- Backend refactor: split `server.py` (~5000 lines) into `routers/auth.py`, `routers/lex.py`, `routers/stripe.py`, `routers/vault.py`, `routers/firms.py`, `routers/pdf.py`. Do this AFTER App Store launch when the codebase is stable.

---

## Live Integration Status

| Source | Status | Tier |
|---|---|---|
| Claude Sonnet 4.5 | ✅ Live | Pro / Yearly / trial_pro |
| OpenAI GPT-5.2 | ✅ Live | Plus |
| Claude Haiku 4.5 | ✅ Live | Free |
| Tavily Web Search | ✅ Live | All tiers (free 1,000/mo, capped at 900 in code) |
| legislation.gov.uk | ✅ Live (via Tavily filter) | All tiers |
| BAILII | ✅ Live (via Tavily filter) | All tiers |
| judiciary.uk / gov.uk | ✅ Live (via Tavily filter) | All tiers |
| Stripe (live mode) | ✅ Live | Plus / Pro / Yearly / Firm |
| Google Sign-in | ✅ Live | All |
| Apple Sign-in | ✅ Live | All |
| Sentry error tracking | ✅ Live | — |
| PostHog analytics | ✅ Live | — |
| vLex (paid case-law) | ⏳ Planned | Pro / Yearly (Reminder 2) |
| Clio Firm Portal | ⏳ Planned | B2B (Reminder 3) |
