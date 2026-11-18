# Lex 2.0 Phase 2E: targeted legal accuracy corrections (preview only, not deployed)
Date: 18 November 2026. No AI models, prices, subscriptions, financial safeguards, Stripe settings or customer data were changed. Phase 2C writing is still off. No paid AI evaluation was run.

## The date question
- The server clock and the app both use the real date, **18 November 2026** (`date` = Wed 18 Nov 2026 UTC). Lex's "today" line and the deadline calculator both use `datetime.now()`.
- "June 2026" came from a static note in my own working instructions. It was never in the app or the evaluation environment. No production setting was involved.
- The scenarios were dated **13 Nov 2026** (`D`). They now use **18 Nov 2026**, so they match the app's real date.

## 1. Key finding: why Free and Plus missed rules the app already had
- In preview, **0 of the 38 built-in fact packs are signed off** (`is_signed_off`). That includes the Wales section 173 pack, the Northern Ireland employment pack and the tribunal time-limit note. So none of them reached Lex during Phase 2E.
- That is why every plan missed Wales section 173 (PRO-05), and why Free sent a Northern Ireland customer to Acas (EMP-06).
- The new official-source rules (section 2B) cover these gaps now. The fact-pack sign-off queue in admin is unchanged and still needs a person to review it.
- **Production sign-off state was not checked.** I can check it read-only if you want.

## 2. Fixes implemented
**A. Employment tribunal time limits** (`deadline_calc._et`)
- **Date of the act decides the limit:**
  - Act or dismissal on or after 1 Oct 2026: 6 months less one day.
  - Before 1 Oct 2026: 3 months less one day.
  - Each result names ERA 2025 s.152 / Sch.12 and SI 2026/954.
- **Removed:** the unsupported line "transitional rules may give this claim longer".
- **Scotland breach of contract:** 6 months only for a breach on or after 9 Nov 2026; before that, 3 months less one day.
- **Series and continuing conduct:** a note that time usually runs from the last deduction in a series, or the end of conduct extending over a period.
- **Northern Ireland:** the Labour Relations Agency (LRA), with its phone number. States that the 6-month change does not apply to most Northern Ireland industrial tribunal claims.
- **Unchanged:** the Acas early-conciliation handling.

**B. Official-source rules** (new `lex_guidance.py`)
- Each rule is labelled for Lex as *"checked against the official pages on 18 November 2026; NOT yet reviewed by a qualified lawyer"*.
- Lex only gets the rules that match the customer's UK nation, and none at all for customers outside the UK. These are prompt text only; nothing is saved to the database.
- **Rules added:**
  - Tribunal limits by date of act.
  - Northern Ireland employment: LRA, industrial tribunal, one year's service.
  - Wales tenancies: Renting Homes (Wales) Act 2016, section 21 doesn't apply, section 173 notice period of 6 months, not in the first 6 months, a court order is still needed.
  - Scotland exceptions: parking keeper liability, simple procedure, prescription and limitation, divorce.
  - Immigration: no appeal against a visitor refusal, the 180-day rolling rule, removal emergencies.
  - Settlement agreements: s.203 independent adviser, the Acas 10-day guidance.
  - Divorce in England & Wales: 20 weeks plus 43 days.
  - Limitation for children and people who lack capacity (s.28 / s.11).
  - Deposit penalty of 1–3 times the deposit (s.214(4)).
  - Consumer law: 30-day right to reject (CRA s.22), Late Payment Act.
  - Council PCN discount and appeal periods.

**C. Plus answer quality** (prompt only; the model is unchanged)
- **What I found:** Plus doesn't use "not confirmed" more than Pro does (41 vs 46 times across 40 answers). Its real weakness is leaving out the rule itself: no 30-day period (CON-01), no Late Payment Act (CON-03), no s.214 penalty (PRO-02). Without signed-off facts it had nothing to anchor to.
- **Fix:** a new "ANSWER DIRECTNESS" instruction for all plans. It tells Lex to state sourced rules plainly with their status and to name the governing Act. "Not confirmed" is kept for points that are genuinely uncertain.
- **Plus only:** one extra line telling it not to answer with a list of "not confirmed" points.

**D. Case-law guard** (`lex_safety.guard_case_refs`, new `landmark_cases.py`)
- **Landmark list:** 41 cases, each with a BAILII URL. Every URL was fetched and its page title matched. For Bolam and Western Excavating, which BAILII doesn't host, the URL is a later judgment that quotes the case and citation.
- **How they show:** listed cases are kept and added to the sources list. The label reads "sourced (existence and citation checked) — not reviewed by a qualified lawyer; does not confirm how this answer applies it". Nothing is marked as professionally verified.
- **Citation parsing fixed:** it now handles:
  - Volume numbers (`[1957] 1 WLR 582`).
  - Paired citations (`[1997] UKHL 46; [1998] AC 232`).
  - More report series and court divisions.
  - Case-number formats (`[UKSC 2026/0095]`).
  - Names like `R (Cart)` and `City and Hackney Health Authority`.
  - Leftover fragments such as "[1957]" are removed.
- **Wrong citation for a listed case:** the name is kept and the wrong citation is removed.
- **Fake cases are still rejected.** A source now only supports a case if it names both parties together ("A … v … B"). This closes the loophole where the two names appeared separately.
- **Removed cases** are also dropped from the `[SOURCES: …]` line. The short "a court decision (reference removed …)" note and the source-check note are unchanged.
- The format example in the system prompt used a made-up case (`Smith v Jones [2019] EWCA Civ 123`). It now uses ParkingEye v Beavis.

**E. Legislation checks** (`legal_sources.py`, free legislation.gov.uk, results remembered for 3 days, down from 7)
- **Bug fixed:** Welsh and bilingual Acts (such as the Renting Homes (Wales) Act 2016) always came back "could not be found". The feed title for these is xhtml; it is now parsed correctly.
- **New: statutory instruments.** Titles ending in "… Regulations / Order / Rules YYYY" and "SI yyyy/nnn" references are checked for existence.
  - If found, the label says "existence checked only — not whether it is in force, amended or applies to your situation".
  - If not found, the reference is flagged inline, explained in a note and removed from the SOURCES line.
- An Act named inside an instrument's title is no longer checked as a separate Act.
- Acts that are not found are also removed from the SOURCES line.
- The existing section status check still separates "exists / in force" from "this interpretation is correct".

**F. Deadline reliability** (`deadline_calc`)
- **Already passed:** says how many days ago, with fitting next steps. For a tribunal deadline, Lex must never say the claim is definitely out of time.
- **Urgent:** flagged when 7 days or fewer remain.
- **Approximate dates:** the date extractor now flags dates it worked out from vague wording.
- **Relative dates:** phrases like "3 weeks ago" are turned into an approximate range for Lex, with a prompt to ask for the exact date.
- **Council PCN, service method unknown:** explains both timings and says when the windscreen discount has already passed. It gives no reminder date, so no precise deadline is invented.
- **High-risk dates:** court-claim and tribunal dates carry a line telling the customer to get them independently checked.
- **Unchanged:** the CPR safeguards.

## 3. Corrected reference standards (`evals/lex_eval_scenarios.py`)
- Every scenario is now labelled `reference_status`: AI-drafted, and none reviewed by a qualified UK lawyer.
- Corrected entries keep the old wording in a `corrected` field, with the sources used.

| Scenario | Correction |
|---|---|
| EMP-01 | 6 months applies (dismissal 20 Oct 2026, so the normal limit is 19 Apr 2027 if that is the EDT). New fail mode: giving 3 months for a dismissal on or after 1 Oct 2026, or giving 6 months as universal. |
| EMP-02 | Ask the date (3 or 6 months by date). Qualifying period is 2 years until EDTs from 1 Jan 2027 (SI 2026/559). |
| EMP-03 | Limit by date of each act; continuing conduct runs from the end of the period (EqA s.123(3)). |
| EMP-04 | Runs from the last deduction in the series (ERA 1996 s.23(3)); 3 or 6 months by that date. |
| EMP-06 | Northern Ireland: 3 months less one day, LRA, Great Britain change not applicable (same substance, now sourced). |
| PAR-02 | The 14-day windscreen discount ended 14 Nov 2026 (already passed); postal timing depends on service. |
| CON-01 | "3 weeks ago" ≈ 28 Oct 2026, so the 30-day right to reject ends about 27 Nov 2026 (urgent). |
| IMM-04 | Note: the instrument Free cited, "British Nationality Act 1981 (Immigration Rules Appendix EU) (Amendment) Regulations 2021", **exists** (SI 2021/743). The Phase 2E report was wrong to call it non-existent. |

- "Ferrara v Ferrara [UKSC 2026/0095]" (FAM-01) is **unverified, not proven fabricated**. Plus took it from a retrieved source. The new guard removes it unless a source names both parties together.

## 4. Official sources for the main corrections
- **ERA 2025 Schedule 12:** https://www.legislation.gov.uk/ukpga/2025/36/schedule/12 (amends ERA 1996, Equality Act 2010, the Working Time Regulations and others; a few UK-wide instruments extend to Northern Ireland).
- **SI 2026/954:** https://www.legislation.gov.uk/uksi/2026/954. Commences s.152 and Sch.12 on 1 Oct 2026. Its note says the amendments don't apply where the relevant date is before 1 Oct 2026.
- **Acas time limits:** https://www.acas.org.uk/employment-tribunal-time-limits
  - Before 1 Oct 2026: 3 months less one day (redundancy pay and equal pay: 6 months).
  - On or after 1 Oct 2026: 6 months less one day.
  - Scotland breach of contract: 3 months before 9 Nov 2026, 6 months from 9 Nov 2026.
- **Northern Ireland:** https://www.lra.org.uk/resources/early-conciliation and https://www.legislation.gov.uk/nisi/1996/1919/article/140 (one year's service).
- **Wales:** https://www.gov.wales/renting-homes-frequently-asked-questions-tenants (6 months' notice, not in the first 6 months, fixed-term rule, converted contracts) and https://www.legislation.gov.uk/anaw/2016/1/section/173
- **Limitation Act 1980 s.28:** https://www.legislation.gov.uk/ukpga/1980/58/section/28
- **Housing Act 2004 s.214(4):** https://www.legislation.gov.uk/ukpga/2004/34/section/214
- **ERA 1996 s.203:** https://www.legislation.gov.uk/ukpga/1996/18/section/203

## 5. Tests
- **New:** `tests/test_lex2_phase2e_corrections.py`, **33/33 passed**. It covers:
  - Tribunal limits.
  - Expired, urgent, approximate and high-risk flags.
  - Parking timings and relative dates.
  - The landmark, fragment, wrong-citation, fake-case and SOURCES-line case guards.
  - Welsh titles and SI existence checks.
  - Official-rule matching by nation and topic.
  - The chat prompt for all 3 plans, with models unchanged (mocked model, mocked legislation.gov.uk).
- **Existing suites, run per file with paid calls blocked: all passed.** Phase 2D 21, phase1 16, Acas deadlines 13, date guard 12, 2A-1 review 5, 2A-1 facts 8, phase1 wiring 4, customer test 12, Free fallback 5, law watch 43, 2B 34, 2A-3 45, 2A-2 91, financial safeguards 18, pass queue 12.
- **Offline evaluation:** 117/117.
- **Still failing, not caused by this work** (they fail on the previous commit too):
  - `test_stage2_safety` Glasgow/Cardiff: an old expectation. Since Phase 2D, a property in Cardiff applies Welsh law.
  - `test_lex_routing`: a live-HTTP test, blocked in no-paid mode.
- **Free live checks:** legislation.gov.uk (Welsh Act, two real SIs, one fake SI) and BAILII (41 URLs).
- The testing agent was not used; it was all checked offline.

## 6. Still needs independent legal review
1. ERA 2025 commencement: the "relevant date" for continuing acts or series that straddle 1 Oct 2026, and the Scotland breach-of-contract date (Acas is the only source used).
2. All 11 official-source rules, especially the Wales s.173 restrictions, Scotland divorce and prescription, the visitor-refusal routes, and the PCN periods.
3. The landmark-case list (only existence and citation were checked), plus the new CPR calculator.
4. All 40 reference standards, including the 8 corrected ones.
5. The 38 fact packs waiting for sign-off in admin.

## 7. Ready for a final real-answer evaluation?
Yes, for a **focused** rerun. I suggest the 15 scenarios that failed or were corrected (EMP-01/03/04/05/06, IMM-02/03/05, FAM-01, PRO-02/05, PAR-01/02, CON-01, MED-02/04) on all 3 plans. That is 45 answers, about £1.20. A full 120-answer rerun would cost about £3.10. Either needs your approval. Nothing was deployed.
