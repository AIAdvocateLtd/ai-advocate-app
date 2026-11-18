# Lex 2.0 Phase 2E: final verification and targeted retest (preview only, not deployed)
Date: 18 November 2026.
- **Unchanged:** AI models, prices, financial safeguards, Stripe, customer accounts, Phase 2C settings and production.
- **Synthetic eval accounts:** deleted after the run (3 users, their conversations, usage records and uploads).
- **Scores:** every score below comes from an AI reviewer (Claude Sonnet 5.5) and is **not legal certification**.

## 1. Can Lex access the legal sources?
**Yes, on all three plans.** This was checked with simulated-model chat tests for Free (Haiku 5.5), Plus (GPT-5.2) and Pro (Sonnet 5.5), and by the 45 real answers.

**How it works:**
- **Built into the prompt:** `lex_guidance.block()` adds to the Lex system prompt:
  - the relevant official-source rules (up to 5 of the 11);
  - a topic-matched "SOURCED CASE LIST" (up to 6 of the 41 cases);
  - the answer-directness instruction, with one extra line for Plus.
- **Filtered by place:** each rule only goes to its UK nation, and nothing goes to customers outside the UK.
- **Real answers confirm it:**
  - All 3 plans explained section 173 for Wales (PRO-05).
  - All 3 sent the Northern Ireland customer to the LRA, not Acas (EMP-06).
  - All 3 gave 6 months for the 20 Oct 2026 dismissal (EMP-01).
  - All 3 cited ParkingEye v Beavis (PAR-01).
  - All 3 said a visitor refusal has no right of appeal (IMM-03).
  - All 3 gave the 20-week divorce wait (FAM-01).
- **Deadline failures no longer hide the rules:** a deadline-calculation error used to silently remove the rules from the prompt. The testing agent found this ("Last Week" in capitals); it is fixed and tested.

**Professional sign-off is not bypassed:**
- The 38 fact packs are still gated by `is_signed_off`; 0 of 38 are signed off in preview.
- `lex_guidance` never reads or writes the fact-pack store.
- The new rules are a separate channel, labelled in the prompt as *"checked against official pages — NOT yet reviewed by a qualified lawyer"*. Lex is told to say a regulated adviser should confirm.
- **Two different things:**
  - **Source verification (done by the app):** a page, Act, instrument or court decision exists and says this.
  - **Professional review (not done):** a lawyer confirms the interpretation and how it applies.
- **No blocker found.** If you prefer, the 11 rules can be held behind the same sign-off as the fact packs.

## 2. Date and deadline safety
- **Current date:** the app and the evaluation both use the real date, 18 November 2026. The scenarios now use the same date, and the reviewer was told the real date.
- **Tribunal calculator now uses the claim type:**

| Claim type | Rule applied |
|---|---|
| Unfair dismissal, wages, discrimination | 6 months less one day on or after 1 Oct 2026; 3 months before |
| Statutory redundancy pay | 6 months (ERA 1996 s.164) |
| Breach of contract in Scotland | 6 months only from 9 Nov 2026 |
| Equal pay | No date given (different trigger, s.129) |
| Unknown | General rule plus "CLAIM TYPE NOT CONFIRMED — ask" |

- **Northern Ireland:** 3 months, through the LRA.
- **Other safeguards:** series of deductions and conduct over a period are flagged. Deadlines are marked as passed, urgent or approximate, and high-risk dates carry an "independent check" line. The CPR rules are unchanged. Six months less one day is never treated as universal.

## 3. Testing agent (iteration_54, simulated and free services only)
- **Existing suites:** 418/418 passed; offline checks 117/117.
- **Its own edge-case probes:** 11 of 34 failed. All are now fixed, and the 34 probes pass when I re-run them; the testing agent has not re-run them.
  - **Most serious:** writing "Last Week" in capitals crashed the date reader, which dropped both the deadline section and the new rules from the prompt. Fixed, and the rules are now kept even if the deadline step fails.
  - **The tribunal calculator, when the UK nation was unknown,** skipped the claim-type warning and its explanatory notes. Fixed.
  - **Instrument detection picked up things that aren't instruments:**
    - two rule books joined into one name ("Immigration Rules 2024 and the Civil Procedure Rules 1998");
    - court orders such as "Child Arrangements Order";
    - Scottish SSI numbers.
  - **Case citations:**
    - "[2015] UKSC 6" was accepted as ParkingEye's citation ([2015] UKSC 67);
    - "Parkinson's" brought up parking cases;
    - "Arsenal v Chelsea" was treated as a case.
  - **Sources list:** an Act that couldn't be found stayed in it when Lex wrote "Under the …".
- **The two tests that failed before:**
  - **Glasgow/Cardiff** (`test_stage2_safety`): an outdated expectation, not a defect. Since Phase 2D, housing follows the property's location, so the expected result is now Welsh law; the test is updated with an explanation.
  - **`test_lex_routing`:** an environment limitation. It signs up real users and makes paid AI calls through the public URL, which no-paid test mode blocks. It was not run.
- **Three wrong "not found" results came from the real answers** and are now fixed:
  - "Divorce, Dissolution and Separation Act 2020": the comma broke the title.
  - "First-tier Tribunal (Immigration and Asylum Chamber) Rules 2014": Lex used the short name of the real Tribunal Procedure Rules (SI 2014/2604), with a non-standard hyphen.
  - "Explanatory Memorandum to the Assured Tenancies (Amendment) (England) Order 2010": the prefix was read as part of the title (the instrument is real, SI 2010/908).
  - These now match safely (an exact title, or the cited name forming the end of the official title), and a test covers them.
- **New-test totals:** `test_lex2_phase2e_corrections.py` 36/36 and `test_phase2e_probe_iter54.py` 34/34; existing suites still pass.

## 4. Real-answer retest: 15 scenarios × 3 plans = 45 answers, all answered
Run through the real `lex_chat` pipeline with one shared research call per scenario. Full answers and reviews: `backend/evals/results_live_retest.json`. Comparison script: `python -m evals.compare_retest`.

| Scenario | Free (before → after, /16) | Plus | Pro |
|---|---|---|---|
| EMP-01 | 7 critical → 14 | 4 major → 10 | 7 major → 15 |
| EMP-03 | 11 major → 11 | 8 major → **8 major** | 11 major → 12 |
| EMP-04 | 10 major → 10 | 6 major → **6 major** | 12 → 12 |
| EMP-05 | 7 major → 11 | 9 → 9 | 11 → 13 |
| EMP-06 | 8 major → 15 | 9 → 14 | 10 → 15 |
| IMM-02 | 7 major → 10 | 8 → 8 | 9 → 11 |
| IMM-03 | 5 major → 11 | 8 major → 12 | 13 → 12 |
| IMM-05 | 8 major → 12 | 9 major → **8 major** | 12 → 13 |
| FAM-01 | 11 major → 12 | 10 → 13 | 14 → 15 |
| PRO-02 | 14 → 13 | 10 major → 12 | 12 → 12 |
| PRO-05 | 8 major → 14 | 5 major → 11 | 9 major → 12 |
| PAR-01 | 9 → 9 | 7 → **8 major** | 11 → 9 |
| PAR-02 | 7 major → 14 | 7 major → 12 | 12 → 13 |
| CON-01 | 9 major → **8 major** | 6 major → 12 | 12 → 15 |
| MED-02 | 8 major → 10 | 8 → 14 | 15 → 15 |

(Unmarked = minor or no issues.)

**Scores by plan for the same 15 scenarios (average out of 16):**

| | Free | Plus | Pro |
|---|---|---|---|
| Phase 2E (before) | 8.6 | 7.6 | 11.3 |
| **Retest (after)** | **11.6** | **10.5** | **12.9** |
| Critical / major (before) | 1 / 12 | 0 / 9 | 0 / 3 |
| **Critical / major (after)** | **0 / 1** | **0 / 4** | **0 / 0** |
| Deadlines score (before → after, /2) | 0.80 → 1.40 | 0.33 → 1.13 | 1.00 → ≈1.4 |
| Citations score (before → after, /2) | 0.60 → 1.00 | 0.33 → 0.80 | 1.00 → ≈1.1 |

**Machine checks:**
- **Answers:** 45/45 answered and signposted help; research ran for all 15 scenarios.
- **Cases:** none removed and no citation fragments; real landmark cases were kept.

**Comparison caveats:**
- The reviewer is an AI and not deterministic.
- 8 reference standards were corrected. EMP-01 now expects 6 months, which accounts for part of its gain.
- The earlier run was dated 13 Nov, against the app's real date of 18 Nov.
- Plus is still the weakest plan.

## 5. Remaining critical and major failures (no critical; 5 major)
- **Plus, EMP-03 and EMP-04:** gave **no time limit at all**, and missed the continuing-acts and series-of-deductions rules. Neither question gives a calculable date, so the "no calculated date" instruction seems to win over the official-source rule.
  - Suggested fix (prompt only): "when no date can be calculated, still state the applicable rule".
  - EMP-04 Plus also said "Wales law applies" for a matter where employment law is the same across Great Britain.
- **Plus, IMM-05 (detention tonight):** used an irrelevant police-caution source and named no out-of-hours route.
- **Plus, PAR-01 (private parking):** no 28-day operator appeal, no POPLA/IAS, no keeper-liability explanation. These rules aren't in the new rules yet.
- **Free, CON-01:** suggested a later-arising fault weakens the 30-day right to reject, and gave no worked date.
- **Minor, all plans:** answers often repeat the internal "INDEPENDENT CHECK:" label word for word. It's harmless, but the wording could be smoother.

## 6. Costs (recorded by the app's own cost tracker)

| Item | Cost |
|---|---|
| Free | £0.284 (46 calls, 20 search credits) |
| Plus | £0.367 (36 calls, 10 search credits) |
| Pro | £0.331 (40 calls) |
| AI reviewer (estimate) | £0.237, plus £0.005 to re-grade one answer whose review failed to read |
| **Total** | **≈ £1.22 of the £3 approved** |
| Of which searches | 30 credits ≈ £0.19 (15 shared research calls) |

## 7. Still needs independent legal review
- All 11 official-source rules and the claim-type deadline logic. In particular:
  - redundancy pay and equal pay triggers;
  - the Scottish 9 November date (sourced only from Acas);
  - acts that straddle 1 Oct 2026.
- The 41-case list (only existence and citation were checked).
- The CPR calculator.
- The 40 reference standards, including the 8 corrected ones.
- The 38 fact packs waiting for sign-off.
- The 5 remaining major answers above.
