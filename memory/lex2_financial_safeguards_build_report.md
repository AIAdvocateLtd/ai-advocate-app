# Lex 2.0 — Financial Safeguards, Passes & Extra Lex Credits (PREVIEW BUILD, ALL SWITCHED OFF)

Nothing deployed. No live Stripe products, no charges, no paid AI or search calls.
Production prices, models, subscriptions, accounts, legal safeguards, Phase 2C settings and the £30 / 900 limits are unchanged.
Every new behaviour sits behind an admin switch (Admin → Fair use & spending), and every switch defaults to Off.

## 1. Current temporary products (from code; production pass limits already apply)
All passes are one-off Stripe payments (price IDs in `STRIPE_PRICE_TOPUP_*`; promotion codes allowed; gifting supported).
| Product | Price | Duration | Model | Allowance (live since 6 Nov via Stage 3 `pass_limits_enabled`) |
|---|---|---|---|---|
| Day Pass | £4.99 | 24h | Plus (GPT-5.2) | 50 msgs, 2 letters, 5 analyses, 10 read-alouds |
| Weekend Pass | £14.99 | 72h | Plus | 120 msgs, 5 letters, 5 analyses, 30 read-alouds |
| Crisis Pack | £29.99 | 24h | Pro (Sonnet 5.5) | 80 msgs incl. 5 Deep Think, 5 letters, 5 analyses, 1 Live Assist, 60 hearing min, 30 read-alouds, 30 translations |
| Letter Pack | £9.99 | 30 days | Plus | 5 letters, 1 contract review, 100 msgs |
| Doc Pack | £4.99 | never expires | no tier change | 5 document analyses (up to 100 pages each) |

None of these is unlimited, and the website taglines already state the allowances.

**Findings (not changed):**
- **Second pass replaces the first:** buying a pass while one is active replaces it, and the remaining time and allowance are lost.
- **Webhook redelivery:** a repeated Stripe webhook re-activates the pass with a fresh allowance. This needs idempotency on the session id.
- **Promotion codes:** these can push a pass below cost.

## 2. Built in preview (switched off)
| Switch | What it does |
|---|---|
| `allowances_v2_enabled` | Plus 150 msgs/month (20/day); Pro & Yearly 350 (50/day). Pricing-page copy follows automatically. Yearly stays grandfathered until renewal (existing). |
| `cost_cap_enabled` | Monthly AI + search backstop per account: Plus £10, Pro £18 (editable). Covers every chargeable feature that goes through Stage 3: chat, Deep Think, letters, document analysis, translation, hearing recorder, emergency answers (search cost is included in the per-request cost). Includes a £0.25 reserve, and recomputes spend live (no 10-minute cache) once usage passes 80% of the cap. Active pass adds headroom: Day £3, Weekend £8.50, Crisis £15, Letter £3.50. |
| `emergency_allowance_enabled` | After a limit is reached, messages the existing rule-based high-stakes check classes as *emergency/urgent* get Free 1/day (3/month) and Plus/Pro/Yearly 3/day (10/month). Pass holders use the tier their pass grants. Chat messages only (no documents, no Deep Think). Duplicate, burst, retry and lock guards still apply. Never bypasses cool-downs/pauses or the Free site brake. Pause messages add free helplines (999, Civil Legal Advice 0345 345 4345, Citizens Advice 0800 144 8848). |
| `emergency_rights_limits_enabled` | Emergency Rights button: max 5 newly generated scripts per account per day. Identical requests (same country + language, no note or location) reuse the last script for 24h (versioned, so a prompt change invalidates it). Over the limit, or if the AI fails, it shows fixed UK guidance and helplines at £0. Generation counts toward account spend. |
| `credits_enabled` | Extra Lex Credits (see §4). |
| `passes_v2_enabled` | New pass allowances for **purchases made after the switch-on time only**; earlier passes keep what they bought. |
| `usage_warnings_v2_enabled` | Friendly 80% warnings (see §5). |

**Monitoring fixes** (active in preview, no customer impact):
- Plan saved on cost records again (effective tier).
- New "access" label on each AI call (`plan`/`free`/`pass:<kind>`/`credits`/`emergency`) and a per-tier/per-access cost breakdown in `/api/admin/llm-spend`.
- App info logs no longer swallowed (`logging.basicConfig(force=True)`), so the hourly spend watchdog becomes visible in production logs.

## 3. Do the £10 / £18 caps block advertised allowances?
| | Allowance | Est. cost per msg | Cost at full allowance | Cap blocks at about |
|---|---|---|---|---|
| Plus | 150 msgs | 8p (ESTIMATE, Plus not yet used) | about £12 + letters/analyses | **about 115–125 msgs** |
| Pro | 350 msgs | 7.2p (recorded, 8 questions) | about £25 | **about 240 msgs** |

**Yes, at measured costs the provisional caps would stop some genuine customers before their advertised allowance.**

Recommendation:
- Enforce at **Plus £14 / Pro £28**.
- Keep £10 / £18 as owner "review" emails (the existing monthly-review flag).
- Re-measure cost per message from 30 days of real Plus/Pro data before activation.

Worst-case margin at £14 / £28 (VAT-registered):
- **Plus**: £16.66 − £14 − £0.60 Stripe = **+£2.06**.
- **Pro**: £29.16 − £28 − £0.90 = **+£0.26**.
- Not VAT-registered: Plus +£5.39, Pro +£5.09.

**Overshoot:** chat is limited to one answer at a time per account, and spend is recorded within milliseconds of each call. Expected overshoot is under the £0.25 reserve. The theoretical worst case is about £1 if several document analyses run at once.

## 4. Extra Lex Credits
**How credits are counted and used:**
- **Unit:** 1 credit = 1 Lex message; letter = 2; document analysis = 4. Credits never buy Deep Think and never upgrade the AI model — the customer gets the model of their current plan or pass.
- **Order:** pass allowance → plan allowance → credits (soonest-expiring first) → emergency allowance. Each deduction is atomic and recorded once. Failed, blank or cut-off answers refund the credit automatically.
- **Who can buy:** anyone, including Free customers and pass holders.
- **Limits:** credits are prepaid, so they continue past the monthly cost backstop and past the Free site brake. They are capped at 60 credits a day per account (abuse guard).
- **Validity:** 12 months from purchase.

**Payments and refunds:**
- One-off Stripe payment only — no auto top-up, no subscription.
- The customer must tick a box to consent to immediate supply (Consumer Contracts Regulations 2013).
- Credits are granted only for paid sessions, once per checkout session (duplicate webhooks ignored).
- Stripe refund → the refunded share of unused credits is removed. Chargeback → the remaining credits are frozen.
- A duplicate charge is two separate purchases; refund one in Stripe and its credits are revoked automatically.

**Pricing (proposed — not final).** Max cost assumes 8p a credit; typical assumes 4p. Stripe one-off fees are 1.5% + 20p (Billing 0.5% does not apply to one-off payments).
| Pack | Price | Per credit | Max AI cost | Margin A (no VAT) worst / typical | Margin B (VAT incl.) worst / typical |
|---|---|---|---|---|---|
| 25 | £4.99 | 20p | £2.00 | £2.72 (58%) / £3.72 | £1.89 (49%) / £2.89 (74%) |
| 60 | £9.99 | 16.7p | £4.80 | £4.84 (50%) / £7.24 | £3.18 (40%) / £5.58 (70%) |
| 120 | £17.99 | 15p | £9.60 | £7.92 (45%) / £12.72 | £4.92 (34%) / £9.72 (67%) |

Mixed UK/international cards (about 2.5% + 20p) reduce each margin by £0.05–0.18. A subscription stays the better deal (Plus about 13p a message), which protects recurring revenue.

**Consumer law (solicitor review recommended):**
- **Pre-contract information:** state clearly what a credit buys, the 12-month expiry, and the cancellation terms.
- **Cancellation:** the 14-day right is lost only with express consent plus acknowledgement. Recommended policy, already used in the UI wording: refund unused credits on request within 14 days.
- **Expiry:** clearly disclosed expiry is generally acceptable (CMA). Consider honouring reasonable requests after expiry.
- **Out of scope:** the DMCC Act 2024 subscription rules don't apply, because there is no renewal.

## 5. Customer experience (built, switched off)
**The 80% notice (existing chat banner, now more detailed):**
- Used / limit / remaining.
- The reset time: midnight UK for daily limits, "1 <Month>" for monthly ones.
- That Lex pauses at the limit and the customer is never charged automatically.
- Whether credits are available, and how many emergency answers are left today.

**At a limit:** a friendly 429 pause message (not an error) that says when access returns and which options apply (credits, helplines).

**Unchanged:** no model switching and no automatic charges. Pounds are never shown to customers.

## 6. Proposed pass allowances (`passes_v2_enabled`, new purchases only)
Max AI cost assumes the full allowance is used at 8p a message (Plus), 7.2p (Pro), and about 8–15p per analysis. Margins are after Stripe fees.
| Pass | v1 max cost | v1 margin A / B | v2 allowance | v2 max cost | v2 margin A / B |
|---|---|---|---|---|---|
| Day £4.99 | £4.68 | +£0.04 / **−£0.79** | 30 msgs, 2 letters, 3 analyses, 10 RA | £2.92 | +£1.80 / +£0.97 |
| Weekend £14.99 | £10.82 | +£3.75 / +£1.25 | 90 msgs, 5 letters, 5 analyses, 30 RA | £8.42 | +£6.15 / +£3.65 |
| Letter Pack £9.99 | £8.29 | +£1.35 / **−£0.31** | 5 letters, 1 contract, 40 msgs | £3.49 | +£6.15 / +£4.49 |
| Crisis £29.99 | about £9.10 | +£20.24 / +£15.24 | unchanged | — | — |
| Doc Pack £4.99 | about £2.00 | +£2.72 / +£1.89 | unchanged | — | — |

Typical pass use (about 10–20 messages) costs £0.80–1.60. Pass usage is still subject to burst and spend guards, cool-downs and the cost backstop.

## 7. Site-wide (Part 8 — recommendations only, nothing changed)
**Current state:**
- The £30 daily budget and 900-search cap are confirmed and unchanged; 122 of 900 searches have been used in November.
- Each legal question, including short follow-ups, triggers 2 paid searches.
- There is no caching of searches, and the free legislation.gov.uk and ACAS lookups always run as well.

**Recommended next (no loss of source checking):**
- Skip the general-web search when official sources already return 2 or more results.
- Reuse an identical search for 24h.
- Reuse a conversation's sources for short same-topic follow-ups.
- Send an owner email at 80% of the search cap.
- Expected saving: 40–60% of searches.

## 8. Notice requirements before activation
- **Existing subscribers:** Plus and Pro pricing currently advertises **300 / 600 messages**. Moving to 150 / 350 or enabling the cost backstop is a material change: send at least 30 days' notice with free cancellation, then set "Paid allowances start". Yearly subscribers keep their terms until renewal (automatic snapshot).
- **Wording still hard-coded:**
  - The paywall line "300 messages/month" in App.js.
  - The Free limit message "Upgrade to Plus for 300 messages a month" in server.py.
  - Terms §6, the store listings and the notice email (`stage3_wording_drafts.md`).
  - These need updating, plus new sentences for credits, the backstop and the emergency allowance.
- **Pass purchasers:** existing passes keep their entitlement. New allowances show at checkout as soon as `passes_v2_enabled` is on, so no notice is needed.
- **Credits:** terms page plus checkout consent before `credits_enabled`. Live Stripe prices are needed: `STRIPE_PRICE_CREDITS_SMALL/MEDIUM/LARGE`.

## 9. Tests
| Suite | Result |
|---|---|
| `tests/test_lex2_financial_safeguards.py` | 18/18 — defaults off, pricing copy, v2 daily/monthly limits, cost backstop and fresh recompute, credit idempotency/12-month expiry/weights/refund/expiry/daily max/Free use, refund and chargeback revocation, emergency allowance (eligible vs ordinary, documents excluded, Free respects site brake), passes v2 only for new purchases, 80% warnings, Emergency Rights reuse and limit without AI, settings merge |
| `test_stage3_limits.py` | 16/16 |
| `test_stage3_release.py` | 33/33 |
| `test_iter47` / `test_iter49` | pass |
| `test_iter48` | one known flaky login-IP test that passes when run alone |
| Testing agent iteration_52 | backend 43/43, frontend 100% (credits card hidden when off, consent gating, admin switches); all switches restored Off |

## 10. Decisions needing your approval
1. Message allowances: Plus 150/20, Pro 350/50 (or keep 300/600), and the date for the 30-day notice.
2. Cost backstop: enforce at **£14 / £28** (recommended) or the provisional £10 / £18; and whether £10 / £18 become review-email levels.
3. Emergency allowance: Free 1/day (3/month), paid 3/day (10/month).
4. Emergency Rights limits: 5 a day plus 24h reuse.
5. Pass v2 allowances (Day 30, Weekend 90, Letter Pack 40 messages).
6. Credit packs and prices (£4.99 / £9.99 / £17.99), the 14-day refund-of-unused policy, and creation of live Stripe prices.
7. Fix pass re-activation on repeated webhooks and the "second pass replaces the first" behaviour.
8. The Tavily search reductions in §7.
9. Solicitor review of the Terms, notice and credit wording; then a deployment (preview only so far).
