# Stage 3 Release Report — PREVIEW ONLY (not deployed)

## Built
- 3A Login security (login_guard.py): 5 fails/15 min per account+network, 15 per account from any network, 20 per network;
  2FA 5 wrong codes -> sign in again; reset-link guessing 10/15 min per network; customer, firm, firm-staff logins.
  Real client IP now read safely (spoofed X-Forwarded-For ignored) — also fixes resend-verification, Turnstile, signup IP.
- 3B Foundations (stage3.py): admin settings store (app_settings/_id stage3) with on/off switches, monthly/daily counters,
  automatic refund of any allowance when a request fails (middleware) or a reply is blank/cut-off.
- 3C Allowances: Free 2 lifetime actions (email + device + Gmail-alias shared, 3 free signups per network / 7 days);
  Plus/Pro/Yearly monthly+daily allowances, passes; paid limits OFF until "Paid allowances start" date is set;
  Yearly snapshot grandfathering until renewal. Trial: already not granted to new signups (admin-only); active trials untouched.
- 3D Paid safeguards: daily flag -> owner email; 1-hour cool-down; second cool-down -> pause to midnight; monthly review flag.
  Cool-downs only enforced after the paid start date. Never a model change.
- 3E Free site brake: 2x daily budget pauses Free AI (incl. taster) until midnight UK; Pause/Resume/Override; trigger + reset emails.
- Abuse guards: 8 msgs/min, same message within 30s, >3 retries in 10 min, one answer at a time.
- Admin card "Fair use & spending"; chat notice "N of 2 free Lex questions left" / 80% warnings.
- 3F Wording + notice email drafts: /app/memory/stage3_wording_drafts.md (NOT applied).

## Unchanged
AI models for every tier, Stripe, prices, keys, existing design/admin features. One automatic fallback (unchanged);
the only extra retry is the existing zero-cost "provider busy" retry in reminder detection.

## Tests
tests/test_stage3_limits.py 14/14; testing agent iteration_47 (15/15) + iteration_48 (20/20) — all fixes verified.
Stage 1/2 regressions (blank reply, stage1 smoke, stage2 quota/stream, deep-think router) pass.

## Before production (owner decisions)
1. Approve wording drafts — Free "5 Lex chats / day" copy must change in the same release as the 2-lifetime rule.
2. Live SENTRY_ENV still "preview".
3. After deploy: send notice email, then set "Paid allowances start" = send date + 30 days.
## Rollback
Admin switches (instant) or platform checkpoint rollback. New collections only: login_attempts, s3_events, s3_flags, s3_consumptions.
