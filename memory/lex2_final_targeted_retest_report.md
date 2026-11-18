# Lex 2.0: final targeted real-answer retest (preview only, not deployed)
Date: 18 November 2026.

| Item | Detail |
|---|---|
| Answers | 15 (5 scenarios × Free Haiku 5.5 / Plus GPT-5.2 / Pro Sonnet 5.5) |
| Pipeline | Real `lex_chat` path: research, deadline calculator, legislation, case and citation checks, safety layers |
| Accounts | 3 synthetic accounts, deleted afterwards |
| Optional AI citation check | OFF (setting absent in the database) |
| Unchanged | AI models, prices, safeguards, Stripe, customer data and Phase 2C |

**All scores come from an AI reviewer (Claude Sonnet 5.5). They are automated, not professional legal verification, and not legal certification.**

## 1. Results (out of 16: original Phase 2E → first retest → this retest)

| Scenario | Free | Plus | Pro |
|---|---|---|---|
| CON-01 faulty laptop | 9 → 8 **major** → **12 minor** | 6 → 12 → **14 minor** | 12 → 15 → **13 minor** |
| EMP-03 pregnancy, cut hours (Bristol) | 11 → 11 → **9 MAJOR** | 8 → 8 **major** → **10 minor** | 11 → 12 → **15 minor** |
| EMP-04 unpaid wages and holiday pay (Cardiff) | 10 → 10 → **9 minor** | 6 → 6 **major** → **7 MAJOR** | 12 → 12 → **14 minor** |
| PAR-01 private supermarket parking (Leeds) | 9 → 9 → **12 minor** | 7 → 8 **major** → **11 minor** | 11 → 9 → **11 minor** |
| IMM-05 detention, removal tomorrow | 8 → 12 → **11 minor** | 9 → 8 **major** → **8 minor** | 12 → 13 → **13 minor** |

**Average score by plan (same 5 scenarios):**

| Plan | Original | First retest | This retest |
|---|---|---|---|
| Free | 9.4 | 10.0 | **10.6** |
| Plus | 7.2 | 8.4 | **10.0** |
| Pro | 11.6 | 12.2 | **13.2** |

**Errors in this retest:** 0 critical, **2 major** (Free EMP-03, Plus EMP-04) and **13 minor**.

**The 5 previous majors:**
- **Resolved (4):** Free CON-01, Plus EMP-03, Plus PAR-01, Plus IMM-05 (all now minor).
- **Not resolved:** Plus EMP-04 (major again).
- **New major:** Free EMP-03, which was minor before.

## 2. Deadlines: correctness and completeness
- **CON-01:** all 3 plans now give the 30-day right to reject (deadlines 2/2 on every plan). The calculator now runs for this question.
- **PAR-01:** no plan gave an invented date. All mention appealing to the operator and an independent appeal; the reviewer scored deadlines 1/2, saying "28 days after rejection" is imprecise. **This needs legal review:** the reviewer said POPLA allows 33 days, and the app has not verified that.
- **IMM-05:** Plus and Pro scored 2/2; urgency and removal timing were handled.
- **EMP-03 and EMP-04, the remaining weakness:**
  - **Free EMP-03** gave "3 months less one day" without the continuing-conduct rule. That is correct for the August acts in isolation, but incomplete.
  - **Plus EMP-04** correctly gave 6 or 3 months by date of act, but left out that time runs from the last deduction in a series.
  - Both rules were in Lex's instructions; the models left them out.
  - **Fix made after the run, not yet tested on real answers:** a new free check (`ensure_et_points`) adds any missing date-of-act, series or continuing-conduct point to the answer, labelled as official-source rules not reviewed by a lawyer.
  - Replayed offline against the stored answers, it adds the missing points to exactly the two major answers (and one continuing-conduct note to Pro EMP-03), and to no other answers.

## 3. Do the citations support their claims?
- **Citation scores across the 15 answers:** 0/2 three times (Plus EMP-03, EMP-04, IMM-05), 2/2 twice (Pro CON-01), and 1/2 for the rest. No invented cases or legislation were reported.
- **Plus IMM-05 still cited a Brighton & Hove police-caution page.** It was cited for the statement "don't rely on police caution advice", so the free check correctly found that it supports *that sentence*. The real problem was that the emergency rule itself mentioned police-station guidance. **Fixed after the run:** the rule now says to cite only immigration-specific sources, and no longer mentions the police.
- **Also fixed in the detention rule:** only a solicitor (not an OISC adviser) can bring court proceedings, and the out-of-hours route is the High Court duty judge.
- The answers still contain some irrelevant boilerplate source notes (e.g. Acas Code text in a parking answer). Minor.

## 4. Testing-agent regression (simulated or free services only; no paid calls)
- **All 34 iteration-55 checks passed (34/34)**, rerun by the testing agent (iteration 56) and by me.
- **Scotland parking:** every service method gives one 14-day discount and the First-tier Tribunal for Scotland. No England & Wales 21-day, London Tribunals or Traffic Penalty Tribunal wording appears.
- **Citation warnings:** the agent found one remaining issue. In a sentence with two citations, the warning attached to the second claim, and a citation placed after the full stop was read as part of the next sentence. **Both are fixed:** each warning now sits at the end of its own claim, and citations after a full stop are moved before it. The agent's new 32 checks pass 32/32.
- Scottish private-parking wording now names the sheriff court.
- **Regression after all changes:** every suite passes (iteration-55 checks 34, iteration-56 checks 32, final refinements 23, plus all previous suites); offline evaluation 117/117.
- The 15 answers were generated **before** the post-run fixes (ET points, detention wording, citation placement). They reflect the code as it was at the start of this retest.

## 5. Recorded costs (from the app's own cost tracking)

| Item | Cost |
|---|---|
| Free | £0.079 (14 calls, 4 search credits £0.025) |
| Plus | £0.142 (16 calls, 6 search credits £0.038) |
| Pro | £0.107 (15 calls) |
| AI reviewer (estimate) | £0.081 |
| **Total** | **£0.41 of the £1 approved** (stop limit £0.95, not reached) |

## 6. Release readiness
**Engineering issues that would block a controlled release:** none known.
- **Caveat:** the post-run fixes for the two remaining majors have only been checked offline, against the stored answers and in unit tests. A 6-answer confirmation run (EMP-03 and EMP-04 on all plans, about £0.17) would confirm them; it needs your approval.
- Still to switch on in production, needing your separate approval: deployment of everything from Phase 2E onwards, plus the financial safeguards and Phase 2C (both off).
- The optional AI citation check stays off until separately tested and approved.

**Professional legal review (separate from engineering):**
- **Nothing has been reviewed by a qualified UK lawyer**, so Lex must not be described as legally certified or professionally approved.
- Sign-off needed for:
  - the 149 items in `lex2_legal_review_pack.docx`: 40 scenarios, 16 official-source rules, 41 cases, 38 fact packs (still held back from Lex), 6 tribunal transition questions and 8 deadline calculators;
  - in particular the tribunal 1 October 2026 transition and continuing acts, the Scotland 9 November breach-of-contract date, the POPLA/IAS appeal periods, and the detention court routes.
