# AI Advocate — Lex 2.0 Cost & Profitability Review (information only)

Sources: read-only production aggregates (no conversations read, no customer identified, no changes, no paid calls) + code review of preview (same code as production).
**RECORDED** = values in production `llm_usage` (token counts from the provider × our own rate table — not a provider invoice). **ESTIMATE** = calculated by me from stated assumptions.

## 1. Actual AI costs (RECORDED)
| | Last 7 days | Last 30 days |
|---|---|---|
| Total AI + search spend | £1.67 | £2.34 |
| AI calls logged | 245 | 301 |
| Lex questions (distinct requests) | – | 40 |
| Avg cost per AI call | £0.0068 | £0.0078 |
| Avg cost per Lex question (incl. searches, side calls) | – | £0.040 |

30-day split: Anthropic £1.61 · Tavily search £0.68 (108 credits) · Gemini £0.04 · OpenAI £0.00. Top model Claude Sonnet 5.5 (£0.98). Top feature streamed Lex chat (£1.56).

Per tier (30 days):
- **Pro**: 8 questions, £0.57 → **£0.072 per question**. Activity appears to be ~1 active Pro account.
- **Plus**: no recorded usage. OpenAI (the Plus model) cost £0.00, so there are no real figures for Plus.
- **Free / untiered**: 32 questions, £1.04 → **£0.032 per question**. The tier wasn't saved on cost records after about 6 Nov, so Free and paid usage after that date can't be separated.
- **Highest individual month**: one Pro account, £0.59 for the month.
- **Paid search share**: £0.68 of £2.34 = **29% of spend**. This is an ESTIMATE at £0.0063 per credit. If the Tavily account is on a free credit allowance, the real cash cost was £0.

Accounts (non-deleted): 329 in total (Free 39, Plus 15, Pro 50, no tier field 225). There are 52 active subscriptions. No spend alerts or per-customer flags have ever fired.
Confidence: **low**. Only 40 questions in 30 days, so the figures below rely on assumptions.

Data could not be retrieved:
- Actual Stripe fees and VAT on transactions (no Stripe read access from the tooling). Check the Stripe Dashboard → Balance.
- The values of AA_DAILY_LLM_BUDGET_GBP and TAVILY_MONTHLY_CAP. Both are set in production, but the values are hidden. The code defaults are £30/day and 900 searches/month.

## 2. Per-question cost assumptions (ESTIMATE)
- Pro: £0.072 (recorded). Plus: about £0.08. GPT-5.2's rate-table price is about 1.5× Sonnet 5.5's, plus 2 searches. Free: about £0.03–0.04 (recorded).
- Every legal question runs 2 basic Tavily searches (about £0.013 together), plus free legislation.gov.uk/ACAS lookups.
- Document or contract analysis: about £0.04–0.11 each (code estimates).
- Paid-subscriber mix: 25% Plus / 75% Pro (actual 15 vs 50).

Usage scenarios per subscriber per month:
- **Low**: 10 questions.
- **Typical**: 40 questions.
- **Heavy**: 200 questions plus 10 document analyses.
- **Extreme (abuse)**: Plus 100/day limit; Pro has no message limit today.

AI + search cost per subscriber-month:
| | Low | Typical | Heavy |
|---|---|---|---|
| Plus | £0.80 | £3.20 | £16.80 |
| Pro | £0.72 | £2.87 | £15.20 |

## 3. Revenue scenarios (alternatives — VAT status not assumed)
| | Plus | Pro |
|---|---|---|
| A. Not VAT-registered (full price) | £19.99 | £34.99 |
| B. VAT-registered (price incl. 20% VAT) | £16.66 | £29.16 |
| Stripe fees, UK standard 1.5%+20p+0.5% Billing (ESTIMATE) | £0.60 | £0.90 |
| Stripe fees, mixed cards ~2.5%+20p+0.5% Billing (ESTIMATE) | £0.80 | £1.25 |

## 4. Gross margin after AI + search costs only (ESTIMATE, 25/75 Plus/Pro mix)
Blended revenue per subscriber is £31.24 (A) or £26.04 (B). Blended AI cost is £0.74 low, £2.95 typical and £15.60 heavy.

| Subscribers | Revenue A / B | AI cost Low | AI cost Typical | AI cost Heavy |
|---|---|---|---|---|
| 10 | £312 / £260 | £7 | £30 | £156 |
| 50 | £1,562 / £1,302 | £37 | £148 | £780 |
| 100 | £3,124 / £2,604 | £74 | £295 | £1,560 |
| 500 | £15,620 / £13,018 | £370 | £1,475 | £7,800 |
| **Gross margin A** | | 97.6% | 90.6% | 50.1% |
| **Gross margin B** | | 97.2% | 88.7% | 40.1% |

Per plan, heavy usage:
- Plus: 84% margin (A) or −1% (B).
- Pro: 57% (A) or 48% (B).

Plus is the weaker plan: it costs more per question than Pro and earns less.

**Not included**:
- Stripe fees (table above, roughly £0.60–1.25 per subscriber).
- VAT (scenario B).
- Hosting/Emergent platform, Resend email, Cloudflare, domain, Sentry.
- Tavily subscription (if any), insurance, professional review, refunds and chargebacks.
- Corporation tax, and Apple/Google store fees if sold in-app (15–30%).

**Search cap at scale**: 900 searches/month covers about 450 questions. With 100 subscribers at typical usage (about 4,000 questions), the cap would run out within days. After that, answers use free official sources only. Costs then fall, but answers have less web research behind them. Raising the cap would cost about £0.013 per question, and that cost is already included above.

## 5. Existing spending protections (code + production settings)
| Protection | Current setting | Enforcement |
|---|---|---|
| Daily AI budget (AA_DAILY_LLM_BUDGET_GBP, set; default £30) | Hourly check; emails the owner once per 24h | **Alert only.** At 2× the budget, Free AI pauses until midnight UK time. Paid AI is never stopped. |
| Tavily monthly cap (TAVILY_MONTHLY_CAP, set; default 900 searches) | Checked before each search | **Hard stop** on paid search; free official lookups continue. No early-warning email. |
| Free | 2 lifetime actions + £0.10 lifetime cost cap + 10 sign-ups per network per 7 days | Enforced |
| Plus | 100 Lex messages/day (old limit); 15 analyses/month; 10 documents/day | Enforced |
| Pro | Unlimited messages; 30 Deep Think/month; unlimited documents | Only Deep Think is limited |
| Stage 3 paid allowances (Plus 300/month, Pro 600/month) | Built; start date not set | **Not in force** |
| Per-customer spend guard | Flag at £1.50 (Plus) / £3 (Pro) per day; cool-down at £4 / £8; monthly review at £12 / £25 | **Flag and email only.** Cool-down and pause only work once Stage 3 paid limits are switched on. |
| Abuse guards | 8 messages/minute, duplicate/retry block, one answer at a time | Enforced for all tiers |
| Expensive requests | Answer-length caps on every AI call (1,400 normal, 3,500 Deep Think, up to 6,000 for document tools); Deep Think router; document page limits | Enforced. No per-request £ ceiling. |

## 6. Gaps that could cause unexpected charges
1. **Pro has no message limit and no automatic stop.** A scripted or shared Pro account could run about 8 messages a minute all day (very roughly £100+/day). Today the only response is an email to the owner, who must act by hand.
2. **Plus**: 100 messages/day × about £0.08 is up to about £8/day, or £240/month, against £19.99 revenue.
3. **No hard daily limit for the whole site** for paid customers, and **no monthly total budget alert**.
4. **No warning as the Tavily cap approaches.** It becomes visible only in the admin dashboard.
5. **Tier stopped being saved on cost records after about 6 Nov.** Per-plan cost reporting is blind. The per-customer spend checks still work.
6. Costs come from our own rate table and have not been checked against the Emergent key invoice. The Tavily price per credit is an estimate.
7. If Universal Key auto top-up is on, there is no final spending ceiling outside the app.

## 7. Lex 2.0 / Phase 2D cost impact
All Phase 2D improvements recommended in `lex_eval_report.md` can be built with ordinary code and **no extra AI calls per question**.

| Improvement | Extra cost per question |
|---|---|
| Court citation verification ("unverified case reference" label; later the free National Archives lookup once the licence is approved) | £0 |
| Jurisdiction detection (rules + saved profile; one clarifying question when needed) | £0 |
| Legal deadline detection (extend the existing calculator) | £0 |
| Emergency and high-stakes safeguards (rule-based, existing high_stakes.py) | £0 |
| Improved legal source checking (free legislation.gov.uk / ACAS) | £0 for the AI itself; bigger source excerpts add roughly £0.002–0.004 of input per question |
| *Not recommended:* a second AI "checker" pass | +£0.01 (Haiku) to +£0.05 (Sonnet) per question |
| *Not recommended:* extra Tavily searches | +£0.006 each, and they use up the monthly cap |

## 8. Plain-English recommendation
- **Cost per question today**: about 4p on average. Pro is about 7p, Free about 3p, Plus an estimated 8p (not yet observed). Roughly 30% of that is web search.
- **Sustainability**: at realistic usage, Plus and Pro keep about 85–95% of revenue after AI costs. Heavy users are still profitable on Pro. Heavy Plus users would wipe out the Plus margin if VAT-registered.
- **Lex 2.0**: yes, it can improve with no meaningful rise in per-question cost, because every planned safeguard is ordinary code.
- **Adequate today**: the Free tier controls, the hard Tavily cap, the abuse and burst guards, answer-length caps, the Deep Think cap, and the daily spend alert.
- **Risks to address before or during Phase 2D**:
  1. Pro has no limit and no automatic cool-down. The fix is the planned Stage 3 activation (notice emails first).
  2. No hard site-wide daily stop or monthly budget alert.
  3. No warning before the Tavily cap runs out, and the cap will be too small beyond about 10–20 active subscribers.
  4. Tier is missing from cost records.
  5. Check actual Stripe fees, VAT status, the Tavily plan and the Emergent key invoice by hand to confirm the estimates.
