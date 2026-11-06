# Urgent Lex Repair — Stage 3 Plan v4 (AWAITING FINAL APPROVAL — no code written)
Preview only. Stripe settings, prices, keys, design, admin features untouched. Carry-over: live SENTRY_ENV still "preview".

## Unit cost assumptions (estimated, incl. web research; preview llm_usage + provider list prices)
Msg: Free £0.016, Plus £0.022, Pro £0.027 | Deep Think £0.06 | Letter £0.02 | Doc analysis Plus £0.08 (25pp), Pro £0.15 (100pp)
Read-aloud reply £0.024 | Voice input £0.0023/msg | Live Assist turn £0.01 | Translation turn £0.005 | Hearing transcription £0.0045/min
Background (titles, deadline detection, classifier) £0.001/msg | Fallback allowance: 10% of msgs re-run once

## Allowances + worst-case monthly AI cost (every feature maxed)
Plus £19.99: 300 msgs (40/day), 20 letters, 15 analyses, 100 read-alouds -> £12.24
Pro £34.99: 600 msgs (80/day), 30 DT, 50 letters, 25 analyses, 150 read-alouds, Live Assist 6 sessions/mo (max 3/day, 60 turns each),
  150 translations, 5 h hearing recorder -> £34.96
Yearly £319.99 (£26.67/mo): as Pro + DT 50 -> £36.16
Free: 2 lifetime actions -> £0.10 max (hard stop)

## Retries: exactly 1 automatic fallback. Exception: zero-cost "provider busy" rejection before any output -> 1 retry after 2s.
User-pressed retry: max 3 per message per 10 min. Failed/blank/cut-off -> allowance refunded; cost still counts toward spend safeguards.

## Spend safeguards
Daily flag / 1-hour cool-down: Plus £1.50/£4, Pro £3/£8, Yearly £3/£8. Second cool-down same day -> paused until midnight UK + urgent owner email.
Monthly review ceiling (flag + admin review, no auto-cut): Plus £12, Pro £25, Yearly £20. All editable + override in admin.

## Passes
Day £4.99 24h Plus: 50 msgs, 2 letters, 5 evidence photos, 10 read-alouds -> £1.80
Weekend £14.99 72h Plus: 120 msgs, 5 letters, 5 analyses, 30 read-alouds -> £3.90
Crisis £29.99 24h Pro: 80 msgs (incl 5 DT), 5 letters, 5 analyses, 1 Live Assist session, 1 h hearing, 30 read-alouds -> £4.80
Letter Pack £9.99 30d: 5 letters + 1 contract review (DECISION: currently also grants Plus chat for 30 days)
Doc Pack £4.99: 5 analyses, never expires (unchanged) -> £0.75
Pass allowances used first, stack on subscription, expire with pass, no rollover, refunded on failure.

## Free abuse controls
One allowance per verified email (Gmail dot/+alias normalised) AND per device; max 3 free accounts per network per 7 days;
existing Turnstile, disposable-email block, email verification, 2 signups/device/24h kept. Each message = 1 action; cut-off -> refunded.

## Customer fairness
Active trials honoured. Monthly paid: 30-day notice, free cancellation. Yearly: keep current terms until renewal (recommended).
Notice email + Terms §6 + pricing/paywall/banner/limit-message/store wording drafted for approval. Recommend solicitor review.

## Stages 3A–3G as v3. Rollback: admin switches + checkpoint rollback.
