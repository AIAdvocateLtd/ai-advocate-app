# Stage 3 — Final Release-Readiness Report (PREVIEW, not deployed)

## Complete (verified)
- Free = exactly 2 lifetime AI actions shared by chat, letters, document/evidence analysis and the Lex helper tools
  (Outcome Ladder, Devil's Advocate, Do-Nothing). Enforced server-side in check_quota_and_increment/stage3.consume.
- Fresh start: counters are new (lifetime bucket + cost cap counted from go-live), so every existing Free customer gets 2.
- Paid allowances, passes, Letter Pack (Plus chat capped 100 + 5 letters + 1 contract), Yearly grandfathering, spend
  safeguards and the delayed start date match the approved decisions. Paid limits stay OFF until the admin start date.
- No changes to AI models (routing test passes), Stripe prices/IDs, API keys, or existing admin features.
- Refunds: any failed request (HTTP >= 400 or crash) returns the allowance; blank/cut-off streamed replies refunded.
- Duplicate/burst/one-at-a-time guards, admin override (lift, exempt/un-exempt, brake pause/resume/override).
- Wording applied in preview: plan chooser, top-up packs, landing page /welcome.html (pricing, FAQ, structured data,
  taster text), limit messages, welcome email, Terms (in-app 6a, terms.html 6c, acceptance Terms 6a).
- Tests: test_stage3_limits 16/16, iteration 47 15/15, 48 19/20 (1 test is environment-flaky: preview egress IP rotates),
  49 wording 9/9. No new paid AI calls in this review.

## Changes since last report
- Shared networks: free signups per network raised 3 -> 10 / 7 days; per-network login failures 20 -> 50 / 15 min.
- Privacy: email allowance key is now a SHA-256 hash (no plain email in usage counters).
- /subscription/usage no longer reports the old "5 per day" Free limit.

## Unresolved / risks
- Live SENTRY_ENV label is "preview" (owner edits ONE value, no key rotation) — or optional 1-line code fallback.
- MarketingSite.jsx is not routed (unused file) — updated anyway; live pricing is /welcome.html.
- Translated languages show the new English strings until auto-translation refreshes.
- Doc Pack card says "Valid for 0h" (pre-existing display bug, not changed).
- Free user bottom-nav LEX button shows paywall (pre-existing) while Ask Lex tile allows the 2 questions.
- CGNAT / mobile networks: many people share one IP; limits raised but a large office/university could still hit
  10 new free accounts per week. Adjustable via API.
- signup_network_ip is stored on the user record indefinitely (recommend 30-day purge later).
- Notice email and Terms should be reviewed by your solicitor.
