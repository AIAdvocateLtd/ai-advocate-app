# Lex 2.0: final employment deadline validation (preview only, not deployed)
Date: 18 November 2026.

| Item | Detail |
|---|---|
| Answers | 6: EMP-03 (pregnancy) and EMP-04 (unpaid wages) × Free / Plus / Pro |
| Pipeline | Real `lex_chat` path with research, deadline calculator, new time-limit safeguard (`ensure_et_points`) and citation checks |
| Accounts | Synthetic, deleted afterwards |
| Optional AI citation check | OFF |
| Unchanged | Models, prices, safeguards, Stripe, customer data and Phase 2C |

**Scores are from an AI reviewer (Claude Sonnet 5.5). They are not professional legal verification.**

## Results (out of 16: original → retest 1 → retest 2 → now)

| Answer | Score history | Now | Deadlines | Citations | Safeguard added text? |
|---|---|---|---|---|---|
| EMP-03 Free | 11 → 11 → 9 (major) → **12** | minor | 1/2 | 1/2 | Yes (date-of-act, continuing conduct) |
| EMP-03 Plus | 8 → 8 → 10 → **8** | minor | 1/2 | 0/2 | Yes (date-of-act, continuing conduct) |
| EMP-03 Pro | 11 → 12 → 15 → **14** | minor | 2/2 | 1/2 | Not needed; already complete |
| EMP-04 Free | 10 → 10 → 9 → **11** | minor | 1/2 | 1/2 | Yes (series of deductions) |
| EMP-04 Plus | 6 → 6 → 7 (major) → **11** | minor | 2/2 | 1/2 | Not needed; the answer now states the last-deduction rule itself |
| EMP-04 Pro | 12 → 12 → 14 → **15** | minor | 2/2 | 1/2 | Not needed; already complete |

**Averages (EMP-03 and EMP-04):**

| Plan | Original | Retest 1 | Retest 2 | Now |
|---|---|---|---|---|
| Free | 10.5 | 10.5 | 9.0 | **11.5** |
| Plus | 7.0 | 7.0 | 8.5 | **9.5** |
| Pro | 11.5 | 12.0 | 14.5 | **14.5** |

**Errors:** 0 critical, **0 major**, 6 minor. **Both previous majors are resolved** (Free EMP-03 and Plus EMP-04).

## Checks
- **All 6 final answers state:**
  - the 6-month limit for acts on or after 1 October 2026 and the 3-month limit before it;
  - Acas early conciliation;
  - for wages, that time runs from the last deduction;
  - for pregnancy, that ongoing treatment runs from the end of the period.
- **Correct law used:** each answer handles claim type, jurisdiction (Great Britain-wide employment law for Bristol and Cardiff), the date of the act and commencement.
- **No invented deadlines:** no precise calendar deadline was given in any answer. The only date stated is the 1 October 2026 commencement. Every answer explains the rule and asks for the missing dates.
- **No made-up citations:** the reviewer found no invented legislation or cases, and one unsupported case reference was removed (EMP-03 Pro).

## Remaining minor issues
These are not blockers, and per your instruction I made no further correction cycle.
1. **Safeguard placement:** in Free and Plus, the 6-month rule appears in the appended "Time-limit points to check" box rather than the main text, which the reviewer called inconsistent. **Cause:** the safeguard adds missing points at the end and does not rewrite the model's own wording.
2. **Loosely relevant citations:**
   - EMP-03 Free and Plus cite Acas's capability/conduct dismissal page; Plus scored 0/2 on citations and didn't name Equality Act s.18. **Cause:** that page came back as the top search result and does cover the general topic, so the free relevance check accepts it.
   - EMP-04 Pro lists Western Excavating, a constructive-dismissal case, in its sources for an unpaid-wages answer. **Cause:** the sourced case list offers employment-area cases by broad topic.
3. **Small wording issues:**
   - "Acas pauses the clock" without explaining that it only helps if started in time.
   - [CONFIDENCE: HIGH] given alongside unreviewed rules (Plus EMP-04).

## Recorded cost (from the app's cost tracking)

| Item | Cost |
|---|---|
| Free | £0.036 (incl. 2 search credits) |
| Plus | £0.062 (incl. 2 search credits) |
| Pro | £0.049 |
| AI reviewer (estimate) | £0.034 |
| **Total** | **£0.18 of the £0.50 approved** (stop limit £0.45, not reached) |

## Release readiness
- **Engineering blockers before preparing a controlled release:** none known. All test suites pass, and the offline checks pass 117/117.
- **Before going live, you still need to approve:** deployment of everything from Phase 2E onwards, and switching on the financial safeguards and Phase 2C in production.
- **Professional legal verification (separate):** not done. All 149 items in `lex2_legal_review_pack.docx` need sign-off by a qualified UK lawyer, including the employment tribunal transition rules (ET-1 to ET-6). Lex must not be described as legally certified or approved.
