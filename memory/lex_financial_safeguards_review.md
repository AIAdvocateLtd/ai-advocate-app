# Lex 2.0 — Financial Safeguards Review (REVIEW ONLY, nothing implemented or deployed)

## 1. Confirmed production values (read-only)
- **Daily AI budget**: £30. Confirmed from secret metadata; the code default is also £30.
- **Tavily search cap**: 900 a month. Confirmed the same way. November so far: 122 of 900 used.
- **Stage 3 settings record**: holds only `launched_at = 2026-11-06`. Every other Stage 3 setting is using its code default. Paid allowances have **no start date**, so they are not in force.
- **Notice emails**: never sent. No user carries a notice marker, and no code tracks one.
- **Hourly spend watchdog**: scheduled, but its log lines never reach production logs. The app's info-level logging isn't shipped (the likely cause is `logging.basicConfig` in server.py). Its alert emails are unaffected.

## 2. Reconciling "4p per question" with £2.34 and 40 questions (last 30 days)
| Item | £ | Basis |
|---|---|---|
| All AI and search activity | 2.34 | RECORDED (301 calls) |
| — Lex questions: 40 requests, all calls inside each request (answer model, Deep Think router, fallback, 2 searches each) | 1.61 → **4.0p per question** | RECORDED |
| — Other actions: letters, document/letter analysis, titles, translation, emergency rights, background jobs | 0.73 | RECORDED |
| Within the total: Anthropic | 1.61 | measured tokens × our rate table |
| Within the total: Tavily (108 credits) | 0.68 | ESTIMATE at £0.0063 per credit; £0 cash if the account is on a free allowance |
| Within the total: Gemini | 0.04 | measured tokens × rate table |
| Within the total: OpenAI (the Plus model) | 0.00 | no Plus usage recorded |

Per question:
- **Pro**: 7.2p (8 questions; some likely used Deep Think).
- **Free / untiered**: 3.2p.
- **Plus**: about 8p, an ESTIMATE because Plus hasn't been used.

Each legal question runs up to 2 paid searches (about 1.3p). Every £ figure comes from our rate table, not a provider invoice.

## 3. What protects spending today
| Protection | Status |
|---|---|
| Free plan | Protected: 2 lifetime actions, a 10p lifetime cost cap, and sign-up limits per network. |
| Abuse guards (all plans) | Protected: 8 messages a minute, duplicate and retry blocks, one answer at a time. |
| Answer length / Deep Think | Protected: every AI call has a length cap; Pro gets 30 Deep Think answers a month. |
| Tavily | Hard stop at 900 searches; free legislation.gov.uk and ACAS lookups continue. No early warning. |
| £30 daily budget | Email alert only. At £60 Free AI pauses. **Paid AI is never stopped.** |
| Plus | Old limit of 100 messages a day: **up to about £240 a month** at 8p, against £19.99. |
| Pro | **No message limit.** The spend guard only emails you; cool-downs need the paid start date. |
| Emergency rights button | **No limit on any plan, Free included.** Each press is a fresh Sonnet 4.5 call (about 2p). |
| Monthly review (Plus £12, Pro £25) | Email flag only. |

## 4. Stage 3 as drafted vs. current measured costs
The Stage 3 plan assumed 2.2–2.7p per message. Measured costs are now 4–8p, because they include searches, Deep Think and side calls. At those costs, a maxed-out account would cost:
- **Plus** (300 messages + extras): about £27 a month, against £16.66–19.99 revenue. **Loss-making.**
- **Pro** (600 messages + extras): about £50 a month, against £29.16–34.99. **Loss-making.**

The notice emails haven't been sent, so the allowance numbers can still be changed at no cost to customers.

## 5. Proposed minimum improvements
All of these are preview-only and inactive until you approve them and set a paid start date at least 30 days after the notice.

**A. Message allowances** (recommended change to the Stage 3 drafts)
- **Plus**: 150 a month, 20 a day.
- **Pro**: 350 a month, 50 a day.
- **Yearly**: keeps its current terms until renewal (unchanged).
- Letters, analyses and Deep Think stay as drafted.
- The busiest real account used about 8 questions in its busiest month, so these allowances are about 19× real usage.

**B. Monthly cost ceiling**
- This turns the existing "monthly review" flag into an enforced backstop: **Plus £15, Pro £28, Yearly £28** (Yearly only after renewal).
- It only bites on unusually costly use, such as very long documents. A typical customer runs out of messages long before they reach it.

**C. Warnings and what happens at a limit**
- **At 80%** of any allowance or the ceiling: an in-chat banner, e.g. "You've used 120 of your 150 Lex messages this month. Your allowance resets on 1 [Month]." The existing 80% warning logic is reused. Pounds are never shown to customers.
- **At 100%**: a clear message saying what's paused, when it returns (midnight UK time for daily limits, the 1st for monthly limits or the ceiling), and the options: a Day Pass or upgrade, or contact support.
- **Unchanged**: no model downgrade and no data loss. Failed, blank or cut-off answers are refunded. The 1-hour cool-down and pause-until-midnight already in Stage 3 stay as they are.

**D. Emergency and urgent-deadline allowance**
- **How it's detected**: the existing rule-based high-stakes check (no AI, £0). It would run before the limit check, not after.
- **Allowance**: once a limit is reached, emergency or urgent matters (arrest, eviction or bailiffs, a hearing today or tomorrow, domestic abuse, dismissal or tribunal deadlines, visa expiry) get **3 extra answers a day and 10 a month**. They use the normal model, without Deep Think.
- **Guards still apply**: burst, duplicate and site-wide guards. The answers count toward spending.
- **Always free, and £0**: fixed helplines such as 999, the duty solicitor (0800 026 0200 via police), Shelter, Refuge, ACAS, Citizens Advice and the court enquiry service.
- **Most extra this can cost**: about 80p per account per month.

**E. Emergency rights button**
- Limit to 5 presses a day per account.
- Reuse the same script for 24 hours per country and language.
- Cost drops to near £0, and the feature stays available on every plan.

**F. Site-wide** (£30 value unchanged)
- An extra email at 80% (£24).
- A monthly total alert (suggested £300).
- A "protect mode" at 3× the budget (£90 a day): only paid accounts already above their daily flag level get the 1-hour cool-down. Everyone else is unaffected.
- Review the £30 once you pass about 100 subscribers. At 500 subscribers, typical spend would be about £50 a day.

**G. Tavily: fewer paid searches without losing accuracy**
- Run the general-web search only when the authority-site search and the free legislation/ACAS lookups return fewer than 2 sources.
- Reuse identical searches for 24 hours.
- On short follow-ups in the same conversation and topic, reuse that conversation's sources.
- Email a warning at 80% of the cap (720).
- Estimated saving: 40–60% of searches. The free official lookups and claim-by-claim source checks are unchanged.
- 900 a month is enough today. Plan for roughly 1–2 searches per question as subscribers grow.

**H. Monitoring** (no customer impact)
- Restore saving the plan on cost records.
- Ship app info logs so the hourly watchdog is visible in production.

## 6. Estimated financial protection (worst case per account per month)
| | Today | Stage 3 as drafted | Proposed |
|---|---|---|---|
| Plus | about £240 | about £27 | **about £15.80** (ceiling + emergency allowance) |
| Pro | unbounded (£100s a day possible) | about £50 | **about £28.70** |

Worst-case margin under the proposal:
- **Not VAT-registered**: Plus +£3.60, Pro +£5.40.
- **VAT-registered**: Plus +£0.30, Pro −£0.40. At the absolute worst this is roughly break-even, and typical margins stay at about 85–95%.

## 7. Compatibility with existing Stage 3 work
- Everything reuses `stage3.py` (allowances, thresholds, refunds, 80% warnings, admin switches).
- Changes are new settings with defaults that don't alter behaviour, plus new allowance numbers.
- Nothing takes effect until the paid start date is set. Rollback is via the admin switches.
- No change to prices, models, Stripe, accounts, legal safeguards or Phase 2C.
- The wording drafts (pricing, Terms §6, notice email) need the new numbers, the ceiling sentence and the emergency allowance sentence.

## 8. Decisions needing your approval
1. Allowances: 150/350 (recommended) or keep the drafted 300/600.
2. Enforced monthly cost ceiling: Plus £15, Pro £28.
3. Emergency allowance: 3 a day, 10 a month, plus helplines always free.
4. Emergency rights button: 5 a day plus 24-hour reuse.
5. Site-wide 80% alert, £300 monthly alert, and protect mode at £90 a day.
6. Tavily search reductions plus the 80% warning.
7. Monitoring fixes (plan on cost records, log shipping).
8. Updated customer wording plus solicitor review; then the notice send date, with the paid start date at least 30 days later (Yearly unchanged until renewal).
