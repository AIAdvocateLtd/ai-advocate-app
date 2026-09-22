# Apple Resolution Center Reply v2 — After 22 Sep 2026 Rejection

Paste into Resolution Center. ~2,900 characters — well under Apple's 4,000-char limit.

---

Hello App Review Team,

Thank you for the detailed feedback on Submission 6c40a7db. All three issues have been fully resolved in **Build 16** (uploaded today). Details below.

**Guideline 2.1.0 — App Completeness (registration error)**
Root cause: our Cloudflare Turnstile bot-shield widget failed to render inside the iOS WKWebView (an issue Cloudflare acknowledges with Turnstile in WebViews), which then blocked the sign-up form. Fixed in Build 16 by disabling Turnstile entirely for the native iOS build — bot-shielding is only needed on the open web, not for users who already passed the App Store install gate. The native app now sends an X-Client-Platform: ios-native header and the backend skips Turnstile verification for those requests. Sign-up now works on iPad Air 11-inch (M3) running iPadOS 27.0 as verified in TestFlight.

**Guideline 2.3.10 — Accurate Metadata (Google Play references)**
Removed all Google Play references:
1. Marketing website (aiadvocate.co.uk): "Get it on Google Play" download button and "COMING SOON ON Google Play" badge have been removed. Hero pill updated from "LAUNCHING SOON · iOS · ANDROID · WEB" → "LIVE ON WEB · iOS COMING SOON".
2. In-app: removed "Available on web, iOS & Android" copy on the marketing page. Removed "install HTTP Shortcuts from the Play Store" instruction in the Emergency SOS setup flow.
3. Only remaining Google Play mentions are inside our Terms of Service and Privacy Policy, where they are required by law to disclose subscription-cancellation channels for users who signed up via other stores. These are legal-compliance documents, not marketing.

**Guideline 5.1.2(i) — Legal: Privacy — Data Use and Sharing (cookie prompt / ATT)**
Confirmed: AI Advocate does not track users under Apple's definition. Specifically we do not:
- link app data with third-party data for advertising purposes
- share data with any data broker
- run any advertising SDKs

Per Apple's guidance ("If you do not collect cookies for tracking purposes on Apple devices, remove the cookie prompts or revise them to clarify you do not track users"), the cookie-consent banner has been fully removed from the native iOS/Android builds. The banner remains on the web version because UK-GDPR / PECR cookie law applies to websites — but is not shown inside the installed app.

PostHog product-analytics is now disabled by default on native and can only be enabled by the user via Settings → Privacy → Anonymous Analytics (opt-in, not opt-out). Sentry crash reporting operates on a fully anonymised basis — no personal identifiers are captured — and is disclosed in our App Privacy answers as "Diagnostics → Crash Data · Not Linked to User".

App Privacy questionnaire in App Store Connect already declares that we do not use data for tracking. No ATT prompt is required because no tracking (as defined by Apple) takes place.

Build 16 is ready in TestFlight and attached to this submission. Any further questions: samuel.malick@aiadvocate.co.uk.

Kind regards,
Samuel Malick
Founder, AI Advocate
