# Lex 2.0 Financial Safeguards — Readiness Report (PREVIEW, all switches OFF, not deployed)

## Approved configuration (in preview code)
| | Plus £19.99 (GPT-5.2) | Pro / Yearly £34.99 / £319.99 (Sonnet 5.5) |
|---|---|---|
| Messages | 150 a month, 20 a day | 350 a month, 50 a day |
| Internal review email | £10 a month | £18 a month |
| Enforced monthly AI cost limit | £14 | £28 |

**Switches and wording:**
- **Allowances and review levels:** the new allowances and the £10 / £18 review levels apply only when `allowances_v2_enabled` is on. Until then the current £12 / £25 review levels and 300 / 600 allowances apply.
- **Cost limit:** the £14 / £28 limit applies only when `cost_cap_enabled` is on.
- **Visible in admin:** the Admin "Fair use & spending" card now shows both sets of figures.

**Other features (built, switched off):**
- Emergency allowance and Emergency Rights limits.
- Extra Lex Credits: 25 / 60 / 120 credits at £4.99 / £9.99 / £17.99. **Payments are MOCKED**: no Stripe products exist.

## Done this round
1. **Customer wording follows the switch**, through a new public endpoint `/api/plans/allowances`. It covers:
   - welcome.html pricing cards, FAQ, fine print and FAQ structured data.
   - terms.html §6c (adds the fair-use cost-limit paragraph).
   - The subscribe modal (plan highlights plus a fair-use note) and the in-chat Plus upsell.
   - The Free daily-limit message and the welcome email.

   With switches off, the live wording is unchanged (300 / 600, 40 / 80). With them on, it shows 150 / 350 and 20 / 50. It also explains that unusually heavy use can reach a monthly cost limit *before* the message allowance, with an 80% warning, a pause rather than a charge, and the emergency allowance.
2. **Pass queueing.** Buying a pass while one is active now queues it.
   - The current pass keeps its expiry and allowance.
   - The queued pass starts exactly when the current one ends, with its full duration and its own separate allowance.
   - Several passes chain in order, and different pass types are never mixed.
   - The Doc Pack still adds documents straight away.
   - The Top-ups tab shows the active pass plus "Queued passes" with start and end times.
   - The pass allowance version (v1 or v2) is taken from the purchase time, so a queued pass keeps the terms it was bought under.
3. **Duplicate Stripe webhooks.**
   - Each checkout session can grant a pass or gift only once (`topup_grants`). Repeats return "duplicate" and never restart or duplicate a pass.
   - If granting fails, the claim is released so Stripe's retry succeeds.
   - Gift notes attach to the right (possibly queued) pass.
4. **Tests.**
   - test_lex2_pass_queue 12/12
   - test_lex2_financial_safeguards 18/18
   - test_stage3_limits 16/16
   - iter49 wording 9/9
   - iter52 / iter53 API 10/10 and 4/4
   - Testing agent iteration_53: backend 100%, all reachable frontend pages pass. All switches were restored Off.

## What remains before deploying
1. **Approve a deployment.** All switches default Off, so deploying changes nothing a customer sees, apart from:
   - Pass queueing and duplicate-webhook protection, which go live immediately; they protect customers.
   - The plan being recorded on cost records.
   - The log fix.
2. **Pass queueing is live behaviour once deployed.** Today a second pass replaces the first. Consider a short note on the Top-ups page, which is already built (it appears when a pass is active).
3. **Live check after deploying (read-only):** all new switches Off, `/api/plans/allowances` returns v1, and the webhook endpoint is healthy.

## What remains before activating the new limits
1. **Notice to existing subscribers.** Moving 300/600 to 150/350 and adding a cost limit is a material change.
   - Email every active Plus and Pro subscriber at least 30 days before the "Paid allowances start" date, explaining the change and their right to cancel free of charge. The draft is in `stage3_wording_drafts.md`; it still needs the new figures, cost-limit and emergency wording.
   - Yearly subscribers keep their current terms until renewal (existing grandfathering).
   - No notice email has been sent yet (production record: 0).
2. **Solicitor review** of the Terms §6c / fair-use wording, the subscriber notice, and the credit terms (14-day cancellation and immediate-supply consent, 12-month expiry, refunds).
3. **On the activation date** (admin card), in this order:
   - Set "Paid allowances start".
   - Switch on `allowances_v2_enabled` (copy changes immediately), then `cost_cap_enabled`, `emergency_allowance_enabled`, `emergency_rights_limits_enabled` and `usage_warnings_v2_enabled`.
   - `passes_v2_enabled` applies to new pass purchases only, so it can be switched on at any time, and no notice is needed.
4. **Recalibrate cost per message** from 30 days of real Plus/Pro data. Plus has no recorded usage yet, so £14 / £28 rests on estimates. The plan field on cost records (fixed in this build) makes this possible after deployment.
5. **Store listings** (App Store / Play) and any marketing outside this codebase must be updated by hand.

## Extra Lex Credits (stay in preview)
Before activation you will need:
- Three live Stripe one-off prices, set as `STRIPE_PRICE_CREDITS_SMALL/MEDIUM/LARGE`.
- Solicitor-approved terms.
- The `credits_enabled` switch turned on.

Refund, chargeback and duplicate handling are built and tested.

## Known items not changed
- **Unreachable React pages:** the React /pricing and /terms pages in MarketingSite.jsx are not routed anywhere, so customers never see them. The live pricing and terms are welcome.html and terms.html (both updated). The React versions were updated too, for consistency.
- **Pass-only customers:** a customer with only a pass sees "You're on PLUS" and a "Manage subscription" button in the subscribe modal. This was already the case.
- **Promotion codes:** these are still allowed on pass checkouts and can push a pass below cost.
- **Search reductions:** the Tavily search reductions from the previous review have not been built.
