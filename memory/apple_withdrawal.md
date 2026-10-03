# 🛑 App Store Withdrawal — AI Advocate (v1.0.x)

**Status:** DRAFT — ready to send via App Store Connect → Resolution Center.
**Decision date:** 2026-02-03
**Strategic rationale:** Pivot to Web/PWA-first distribution. The native shell adds no distinct value over the installed PWA (which already supports camera, biometric unlock, offline, home-screen install). Pursuing Guideline 3.1.1 IAP compliance would strip the Pro-tier billing economics; pursuing Guideline 4.2 "Minimum Functionality" would require native code we do not need to ship our core promise. We will revisit after we have 20k+ web MAU and clear native-only feature requests from paying customers.

---

## Reply to send in Resolution Center

Hello Apple Review Team,

Thank you for the detailed feedback on submissions 1.0.x in response to Guidelines 3.1.1 (In-App Purchase) and 4.2 (Minimum Functionality).

After reviewing your guidance, we have decided to **withdraw this submission** and remove the AI Advocate app from the App Store review queue at this time. We will focus on our web and installable Progressive Web App (PWA) experience, which delivers the same features our users rely on today — including on-device camera capture for evidence, biometric vault unlock via WebAuthn, home-screen installation, and offline access.

Please take no further action on this build. If and when we return to the App Store with a native build that fully reflects iOS-native capabilities and complies with 3.1.1 IAP for digital content, we will file a fresh submission.

Thank you for your time and for the clear guidance.

Kind regards,
Samuel
AI Advocate — Founder
support@aiadvocate.co.uk

---

## Operational checklist after withdrawal

- [ ] Send the message above in App Store Connect → App Review → Resolution Center.
- [ ] In App Store Connect → App Information → change availability to "Remove from Sale" if the build was ever approved on TestFlight external groups (internal TestFlight can stay for the dev team).
- [ ] Keep the Capacitor iOS source in `/ios` so we can revive it later.
- [ ] Keep `apple-app-site-association` on the domain (we may re-enable universal links later with no cost).
- [ ] Update marketing site: remove any "Download on the App Store" badges; keep "Add to Home Screen" and "Install app" CTAs instead.
- [ ] Keep the Google Play Closed Testing track live and work towards Production.

---

## What stays, what goes

| Area | Keep | Change |
|------|------|--------|
| iOS Capacitor source | ✅ in `/ios` | No new submissions |
| iOS Keyboard fix in App.js | ✅ (helps mobile Safari too) | — |
| Turnstile native bypass header | ✅ (works for Android Capacitor) | — |
| App Store badges on marketing | ❌ | Replace with "Install app" |
| Apple Sign-in button | ✅ | Keep — still a valid web sign-in method |
| In-App Purchase code | — | Not needed |

