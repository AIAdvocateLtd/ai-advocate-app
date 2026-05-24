# AI Advocate — App Store & Google Play Metadata

> All copy is **ship-ready** — copy directly into App Store Connect / Play Console.
> Character counts are right-sized for each store's limits.
> Last updated: 2026-02-23

---

## 🍎 Apple App Store Connect

### App Information

| Field | Value | Limit |
|---|---|---|
| **App name** | `AI Advocate` | 30 chars |
| **Subtitle** | `Your AI lawyer in pocket` | 30 chars |
| **Bundle ID** | `uk.co.aiadvocate.official` | n/a |
| **Primary category** | `Reference` | n/a |
| **Secondary category** | `Productivity` | n/a |
| **Age rating** | `17+` (Mature) | n/a |
| **Content rights** | "Does your app contain, show, or access third-party content?" → **Yes**, declare BAILII / legislation.gov.uk citation links (public domain UK law) |

> **Why Reference (not Lifestyle / Utilities):** App Store Reference category gets the lowest competition + best ranking-velocity for legal-info apps. DoNotPay, Rocket Lawyer all sit here.

### Keywords (100 chars max, comma-separated, NO spaces after commas)

```
legal,lawyer,solicitor,law,advice,rights,evidence,court,SOS,contract,GDPR,immigration,letter
```

> **Strategy:** Mix branded ("lawyer", "solicitor"), problem-aware ("rights", "evidence"), and high-intent ("contract", "court"). NEVER waste keyword space on words already in your name/subtitle — Apple indexes those automatically.

### Promotional Text (170 chars — editable any time without re-review)

```
NEW: Live citation pills tap straight to legislation.gov.uk + BAILII. Get
AI legal guidance, draft letters, capture evidence, and SOS in 11 languages.
```

### Description (4000 chars — pasted as-is, blank line = paragraph break)

```
AI Advocate is your pocket-sized AI legal companion — a multilingual assistant
that gives you instant guidance on UK law, drafts professional letters, reviews
contracts, captures evidence, and helps you stay safe in emergencies.

Built for everyone who can't afford £300/hour solicitor fees — but still wants
clear, sourced, accurate legal information when they need it most.

⚖ ASK LEX — Your AI legal brain
Lex understands UK statute, case law, and consumer rights. Every answer is
grounded in real sources from legislation.gov.uk and BAILII, with tappable
citation pills you can click to verify in seconds.

🎙 RECORD ANY LEGAL INTERACTION
Capture police stops, disciplinary meetings, immigration interviews, and
hearings with one tap. Auto-stamped with GPS, time, and SHA256 chain-of-custody.
Whisper transcribes; Lex analyses for rights breaches.

🏛 HEARING RECORDER (Pro)
Record formal tribunals, mediations, and depositions with a named case file,
or upload existing audio for AI transcription and analysis.

📷 EVIDENCE & DOCUMENT ANALYSIS
Photograph injuries, scenes, contracts, or letters. Lex extracts what matters,
spots red flags, and tells you what to do next.

✉️ LETTER GENERATOR
Draft grievance letters, deposit-claim demands, section 21 challenges,
landlord complaints, and 30+ other templates in seconds. PDF-ready,
court-acceptable.

📁 CASE FILES + TIMELINE
Group chats, evidence, deadlines, and recordings by matter. Visual timeline
lets you see your entire legal life at a glance. Court-ready PDF export with
full chain-of-custody.

🚨 EMERGENCY SOS + LIVE TRACKING
One tap sends your live location to chosen contacts for up to 24 hours.
Public family-track page works without app install. Saves lives.

🔒 LEX VAULT
End-to-end encrypted vault for your most sensitive documents. Biometric
unlock; we can never read what's inside.

🌍 11 LANGUAGES
English, Spanish, French, Arabic, Polish, German, Hindi, Urdu, Italian,
Portuguese, Mandarin — every screen, every chat, every PDF.

💼 FOR LAW FIRMS
Optional firm portal lists your practice to nearby AI Advocate users with
matching legal needs. Verified solicitors only (SRA / LSS / LSNI numbers
required).

———————————————————————

PRICING
• Free tier: 5 Lex chats/day, 1 evidence photo/month, emergency rights
  (always free).
• Plus £19.99/mo: Unlimited Lex with Claude Sonnet 4.5, voice mode,
  record legal interactions, practice mode.
• Pro £34.99/mo: Everything in Plus + Hearing Recorder, Deep Think
  (King's Counsel-grade reasoning, 30/mo), Outcome Predictor.
• Yearly Pro £319.99/yr: 25% off Pro for annual commitment.
• 7-day free trial on all paid tiers. Cancel anytime.

———————————————————————

⚠️ IMPORTANT — AI Advocate provides general legal information, not
regulated legal advice. It is not a substitute for a qualified solicitor.
In life-threatening emergencies, ALWAYS call 999 (UK) / 112 (EU) / 911
(US) first. See full Terms at aiadvocate.co.uk/terms.html.

———————————————————————

QUESTIONS?
support@aiadvocate.app
```

### "What's New in This Version" (release notes, 4000 chars)

For the **first submission**, use:

```
Welcome to AI Advocate v1.0. Your AI lawyer in pocket, now on iPhone.

• Ask Lex — sourced legal guidance with tappable citations
• Record any legal interaction with GPS + chain-of-custody
• Evidence photo analysis, contract review, letter drafting
• Case files + visual timeline for your matters
• Emergency SOS with up to 24h live tracking
• End-to-end encrypted Vault with Face ID unlock
• 11 languages, fully translated

Thank you for trying us — drop us a line at support@aiadvocate.app with any
feedback. We respond to every email personally.
```

### Promotional URLs

| Field | Value |
|---|---|
| **Marketing URL** | `https://aiadvocate.co.uk` |
| **Support URL** | `https://aiadvocate.co.uk/support` (or `mailto:support@aiadvocate.app`) |
| **Privacy Policy URL** | `https://aiadvocate.co.uk/privacy.html` |

> ⚠️ Privacy Policy URL is **mandatory** for App Review. The link must work and the page must load on mobile — confirm before submission.

### App Review Information

| Field | What to write |
|---|---|
| **Demo account** | `appstore.reviewer@aiadvocate.co.uk` / `Review2026!Lex` *(create this account before submission, mark as Pro tier comped indefinitely)* |
| **Sign-in note** | "Demo account is pre-loaded with Pro tier access for the duration of review. Try `Ask Lex → 'What are my rights if a landlord serves a section 21?'` to see the live citation pills." |
| **Contact email** | Your direct email — Apple Reviewer questions sometimes need 24h response |
| **Notes** | "AI Advocate provides general legal information (NOT regulated legal advice) under the Legal Services Act 2007. UPL disclaimers shown on first use + persistent on every chat. ICO registered. UK-based business." |

### App Privacy Nutrition Labels (App Store Connect → App Privacy)

The questionnaire asks "Does your app collect data?" — answer **Yes**. Then:

| Data type | Linked to user? | Used for tracking? | Purpose |
|---|---|---|---|
| **Contact Info** (Email, Name) | ✅ Linked | ❌ Not for tracking | App Functionality, Account Management |
| **Location** (Precise) | ✅ Linked | ❌ Not for tracking | App Functionality (SOS, evidence GPS, lawyer search) |
| **User Content** (Photos, Audio Recordings, Other) | ✅ Linked | ❌ Not for tracking | App Functionality (evidence, Vault) |
| **Identifiers** (User ID) | ✅ Linked | ❌ Not for tracking | App Functionality |
| **Usage Data** (Product Interaction, Crashes) | ✅ Linked | ❌ Not for tracking | Analytics (opt-in only via cookie banner) |
| **Diagnostics** (Crash, Performance) | ❌ Not linked | ❌ Not for tracking | Analytics |

> **DO NOT** tick "Used for tracking" on anything — we don't run a tracking SDK like AppLovin or Meta SDK. This affects whether you'd be required to show Apple's ATT prompt (which you don't need to).

### In-App Purchase Setup (App Store Connect → Features → In-App Purchases)

| Product Name | Product ID | Tier | Family | Price |
|---|---|---|---|---|
| AI Advocate Plus | `aa_plus_monthly` | Auto-Renewable Subscription | "AI Advocate Subscription" | £19.99/mo |
| AI Advocate Pro | `aa_pro_monthly` | Auto-Renewable Subscription | "AI Advocate Subscription" | £34.99/mo |
| AI Advocate Yearly Pro | `aa_pro_yearly` | Auto-Renewable Subscription | "AI Advocate Subscription" | £319.99/yr |

> All three live in the same **Subscription Group** — Apple requires this to enable Plus ↔ Pro upgrades/downgrades. Set "Yearly Pro" as the highest level.
> Configure **7-day free trial** on each tier under "Subscription Promotional Offers → Introductory Offer".

---

## 🤖 Google Play Console

### Store Listing

| Field | Value | Limit |
|---|---|---|
| **App name** | `AI Advocate: AI Legal Help` | 30 chars |
| **Short description** | `AI lawyer in your pocket. Sourced legal guidance, evidence, SOS, in 11 languages.` | 80 chars |
| **Full description** | _(use the Apple description above — Play accepts up to 4000 chars)_ | 4000 chars |
| **Category** | `Productivity` | n/a |
| **Tags** | `legal` `lawyer` `productivity` `tools` `reference` | up to 5 |

### Content Rating (Google Play questionnaire)

| Question | Answer |
|---|---|
| Violence | None |
| Sexual content | None |
| Profanity | None |
| Controlled substances | None |
| Gambling | None |
| User-generated content | Yes (Lex chats, user-shared evidence) |
| Personal data shared | Yes (location, content) |
| Result | **Mature 17+** |

### Data Safety form

Mirror the Apple Privacy nutrition labels (above). Key declarations:
- **Data collected:** Email, name, location, photos, audio recordings, app interactions, crash logs.
- **Data shared with third parties:** Stripe (payments), OpenAI/Anthropic via Emergent (LLM processing), Sentry (crash reporting, opt-in), PostHog (analytics, opt-in).
- **Encryption in transit:** ✅ Yes (TLS 1.3).
- **Data deletion:** ✅ Yes (in-app `Settings → Manage My Data`).

---

## 📸 Screenshot specs & shot list

### Required device sizes (Apple)

| Device | Size | Quantity | Priority |
|---|---|---|---|
| iPhone 6.7" (15/16 Pro Max) | 1290 × 2796 | 6 | **REQUIRED** |
| iPhone 6.5" (older Pro Max) | 1284 × 2778 | 0 (Apple auto-scales 6.7" → 6.5") | Optional |
| iPhone 5.5" (older Plus) | 1242 × 2208 | 6 if you have an older device — otherwise Apple lets you submit 6.7" only since iOS 18 | Optional |
| iPad 12.9" / 13" | 2064 × 2752 | 6 if you submit iPad build | Required if iPad |

### Required device sizes (Play)

| Device | Size | Quantity |
|---|---|---|
| Phone | 1080 × 1920 (min) | 2–8 |
| 7" tablet | 1024 × 600 (min) | optional |
| 10" tablet | 1280 × 800 (min) | optional |

### Recommended shot list (in order, max impact first)

> Rule: **80% of users see only the first 3 screenshots in the swipe carousel.** Front-load the killer features.

| # | Screen | Caption to overlay |
|---|---|---|
| 1 | **Lex chat with citation pills visible** (the [1] [2] gold pills + sources box) | "Sourced legal guidance — tap to verify" |
| 2 | **Case Timeline** (the visual map) | "Your whole legal life in one place" |
| 3 | **Emergency SOS with live tracking active** | "Real-time location sharing for your safety" |
| 4 | **Recording legal interaction with mic active + GPS chip** | "Capture evidence with full chain-of-custody" |
| 5 | **Contract analysis result with red-flag highlights** | "Spot red flags before you sign" |
| 6 | **Lex Vault unlock with Face ID** | "End-to-end encrypted Vault" |

### Screenshot capture workflow (when you have Xcode set up)

```bash
# 1. Open the iOS simulator
open -a Simulator
xcrun simctl boot "iPhone 16 Pro Max"

# 2. Launch the app
cd /app/frontend && yarn build && npx cap sync && npx cap open ios
# (Then ⌘+R in Xcode)

# 3. Sign in as the demo Pro account, navigate to each screen
# 4. Capture: ⌘+S in the Simulator → saves to Desktop at correct resolution
# 5. Run through Figma to add the caption overlay (gold text on dark bg)
```

For caption overlays, I recommend [Screenshot.rocks](https://screenshot.rocks) or [ScreenshotPro](https://screenshotpro.io) — both free, take a clean screenshot in and out comes a polished store screenshot with caption + device frame in <2 minutes.

### App Preview Video (optional but strongly recommended for ranking)

- **Length:** 15–30 seconds
- **Size:** Same as screenshots (1290 × 2796)
- **Format:** MOV (H.264), max 500MB
- **Show in order:** Lex answering → citation pill tap → Timeline pan → SOS fire → Recording → Vault unlock
- **Music:** None — Apple often rejects videos with music. Use only on-screen sound effects.

Apple's official guide: <https://developer.apple.com/app-store/app-previews/>

---

## 🎨 App icon

- **Source asset:** `/app/frontend/public/icons/app-icon-source.png` (must be **1024 × 1024**, no rounded corners, no alpha, no shadow — Apple adds those).
- **Generate all sizes:** `npx @capacitor/assets generate` (Capacitor 7 plugin we already installed). Run from `/app/frontend/`.
- **iOS variants** auto-generated: 60pt, 76pt, 83.5pt, 1024pt @ 1×/2×/3×.
- **Android adaptive icon:** foreground PNG + background colour `#0a0a0a`.

> Apple rejects icons with transparency or "AI-generated style" claims of being a real lawyer's signature. Your existing gold scales-of-justice mark is perfect — just make sure the 1024 source has zero alpha.

---

## 🧪 TestFlight Pre-Launch Checklist (DO ALL OF THESE BEFORE SUBMITTING)

- [ ] Bundle ID matches `capacitor.config.json` (`uk.co.aiadvocate.official`).
- [ ] Production `REACT_APP_BACKEND_URL` baked into the build (NOT preview URL).
- [ ] All privacy strings from `IOS_INFO_PLIST.md` pasted into `Info.plist`.
- [ ] Apple Sign-in capability enabled (you offer Google sign-in, so this is mandatory).
- [ ] Demo account `appstore.reviewer@aiadvocate.co.uk` created + Pro tier comped indefinitely.
- [ ] `aiadvocate.co.uk/privacy.html` returns 200 + renders on mobile.
- [ ] `aiadvocate.co.uk/terms.html` returns 200 + renders on mobile.
- [ ] Privacy Nutrition Label questionnaire filled in App Store Connect.
- [ ] At least 4 screenshots (one per killer feature) uploaded.
- [ ] In-App Purchases created, prices match (£19.99 / £34.99 / £319.99), free trial enabled.
- [ ] Subscription Terms agreement signed in App Store Connect → Agreements, Tax, and Banking.
- [ ] Banking details + Tax forms (W-8BEN-E for UK Ltd) completed.
- [ ] First TestFlight internal-testers build uploaded + tested on a real device.
- [ ] External tester invite list (you, a friend, a solicitor if possible) seeded.
- [ ] All Capacitor permissions actually triggered + accepted on a physical device.
- [ ] Submit for **App Review** — expect 24-48h turnaround.

---

## 🚀 Launch-day social posts (drop into Buffer / Hootsuite)

### Twitter / X
```
Most people can't afford a solicitor. So we built one.

AI Advocate: an AI lawyer in your pocket. Sourced legal guidance, evidence
capture, letter drafting, emergency SOS — in 11 languages.

iOS launching today: [link]
Android in 2 weeks.

#legaltech #LawTwitter
```

### LinkedIn
```
Today we launch AI Advocate on the App Store.

For 6 months we've been building what I wish existed when my [pick a personal
story — eviction, work dispute, etc.]. An AI that knows UK law, drafts the
letters, captures the evidence, and never bills you £300/hour for a question.

What's different:
• Every answer cites real statute (BAILII / legislation.gov.uk)
• Court-ready chain-of-custody on recordings
• 11 languages, fully translated
• End-to-end encrypted vault for sensitive docs
• 7-day free trial; £19.99/mo after

It's NOT a replacement for a solicitor. It IS the first 80% of legal work
that most people skip because they can't afford to do it.

If you've ever wished you could ask a lawyer "is this normal?" without a
£200 invoice — please try it and tell me what's broken.

[App Store link]
```

### Reddit (r/LegalAdviceUK)
> ⚠️ Reddit's self-promotion rules are strict. Best approach: comment-and-answer on existing threads where AI Advocate would have helped. Don't post a launch announcement — you'll get banned.

---

This document is the only reference you need for the next 30 days of app-store
work. Print it. Tick it off. Don't deviate.
