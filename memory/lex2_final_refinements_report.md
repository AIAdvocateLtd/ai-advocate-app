# Lex 2.0: final legal accuracy refinements (preview only, not deployed)
Date: 18 November 2026.
- **No new paid evaluation was run.** This stage made no AI calls; the only external lookups were free authoritative pages.
- **Unchanged:** AI models, prices, financial safeguards, Stripe, customer data and Phase 2C.

## 1. Phase 2E scores by plan (AI-reviewer scores out of 16; not legal certification)

| Plan | Phase 2E original (same 15 scenarios) | Phase 2E retest (45 answers) | After this stage |
|---|---|---|---|
| Free | 8.6 | **11.6** | not re-scored (no paid run approved) |
| Plus | 7.6 | **10.5** | not re-scored |
| Pro | 11.3 | **12.9** | not re-scored |

- **Full 120-answer Phase 2E run (40 scenarios):** Free, Plus and Pro scores are in `lex2_phase2e_evaluation_report.md`. They were not re-run.
- **Remaining failures in the latest real answers (the 45-answer retest):** **0 critical, 5 major, 40 minor or none.**
  - Major: Plus EMP-03, EMP-04, IMM-05, PAR-01; Free CON-01.
- **Each of those 5 majors now has a targeted fix** (section 2). They are confirmed only by free and simulated tests. They need a real-answer rerun before they can be counted as resolved.

## 2. Failures corrected

| Retest failure | Root cause found | Fix |
|---|---|---|
| Free CON-01: no worked 30-day date ("3 weeks ago" laptop) | The deadline trigger list did not contain "bought / crashing / repair", so **no deadline calculation ran** | Trigger list widened (consumer, pregnancy/hours, wages, detention). The calculator now runs, and relative dates are flagged as approximate. |
| Plus EMP-03 / EMP-04: no time limit at all | EMP-03 was not detected (pregnancy and hours weren't trigger words). EMP-04 has no exact date, and the "no calculated date" instruction overrode the rule | Trigger list widened. The "no calculated date" instruction now says Lex **must still state the time-limit rule** (period, start point, claim type, nation, continuing conduct, series of deductions); leaving it out is an error. Both are now classed as high-stakes employment questions. |
| Dropped or replaced app dates (all scenarios) | Nothing checked that the final answer kept the calculated date | New `ensure_dates`: any app-calculated date missing from the answer is restored in a section labelled **"not legally confirmed"**. A date that has already passed is flagged if the answer doesn't mention it. It never adds a date the app did not calculate. Dates for hypothetical questions are excluded. |
| Plus PAR-01: no 28-day appeal, POPLA/IAS or keeper liability | There was no private-parking rule | New sourced rules for private parking and for council tickets in each nation (below). The calculator gives no private-parking date; the customer uses the dates on the notice. |
| Plus IMM-05: irrelevant police-caution source; no out-of-hours route | The source wasn't checked against the claim's subject, and the emergency signposting had no detention route | Layer-1 source check (section 3) drops citations that don't cover the subject. A new detention emergency rule covers the Detention Duty Advice Scheme, urgent out-of-hours judicial review or injunction, Bail for Immigration Detainees, and "do not use police-station guidance". The urgent help line now covers this too, and detection now catches "will be removed" when detention, the Home Office or a flight is mentioned. |

**Parking timings now applied, by nation:**

| Nation | Council PCN | Private parking charge |
|---|---|---|
| England & Wales | 14-day discount (21 days if posted); 28 days for representations; London Tribunals or Traffic Penalty Tribunal within 28 days of rejection | Appeal to the operator; POPLA or IAS; keeper liability only if the PoFA Sch.4 para 9(5) 14-day notice rule was met |
| Scotland | One 14-day discount whatever the service method; First-tier Tribunal (General Regulatory Chamber) within 28 days of the Notice of Rejection | No keeper liability |
| Northern Ireland | £90 reduced to £45 within 14 days (nidirect); NI Traffic Penalty Tribunal | No keeper liability |

**Sources:**
- PoFA 2012 Sch.4 para 9: legislation.gov.uk
- POPLA: popla.co.uk
- Scotland: generalregulatorychamber.scot
- Northern Ireland: nidirect

**Housing emergencies:** a new rule covers illegal eviction (Protection from Eviction Act 1977 s.1), the council's out-of-hours homelessness duty and Shelter (England, 0808 800 4444).

**Detection:** the existing urgent-matter detection is unchanged. All 45 existing tests pass, police detention still counts as a criminal matter, and no extra paid calls are made.

## 3. Legal source quality: layered checks
**Layer 1: free, always on** (`lex_safety.verify_citations`). For every [n] citation:
- **Statute or section:** if the sentence names an Act or section, it must appear in that source (as before).
- **Subject:** otherwise the sentence must share meaningful terms with the source. If not, the citation is removed and the claim is recorded as unsupported. A sentence with no terms to compare is left "unchecked", never "supported".
- **Jurisdiction:** an official source tied to one nation (gov.wales, gov.scot, nidirect, LRA and others) is rejected for a different nation's matter.
- **Time periods:** the period in the clause before each citation must appear in that source, as digits or as a whole word. If it doesn't, the claim is marked uncertain and the customer sees a "Source check" note.
- **Record:** every claim is recorded as source_supported, uncertain, unsupported or unchecked, and the totals are stored with each answer.

**Layer 2: unchanged.** The claim-by-claim checks still run: the legislation status check (in force, pending changes) and the "Current law (quoted wording checked / in force — interpretation not verified / not confirmed)" labels.

**Layer 3: optional AI check** (`source_ai_check.py`). **OFF by default**; the setting is absent in preview, which the testing agent confirmed read-only.
- **When it runs:** only for "uncertain" claims in high-stakes or deadline answers, at most 3 per answer, using the model the app already uses for deadline extraction (Haiku 4.5).
- **Reuse:** it reuses the passage already retrieved (no new search) and remembers results for 7 days. Failed calls are not remembered and not counted as cost.
- **Result:** it adds *"the cited source does not clearly support this — treat it as unconfirmed"* to the claim's own sentence. It never invents a replacement citation and is never described as professional verification.
- **Estimated extra cost:**

| Case | Cost per customer question |
|---|---|
| Per claim checked | ≈ £0.0011 (~1,100 input + 60 output tokens) |
| Worst case (3 claims) | **≈ £0.0033** |
| Expected | **under £0.001** (most answers have no uncertain claims; only high-stakes or deadline answers qualify) |
| Repeated claims | £0 (remembered) |

  - Its accuracy can't be measured without real calls. **Activation needs a separate approved test**, for example 30 recorded uncertain claims, about £0.05.
- **Small increase in existing paid calls:** the wider deadline trigger list sends more questions to the existing Haiku date-extraction call, at about £0.0005 each.

**Four layers kept separate throughout:**

| Layer | What it means |
|---|---|
| Source exists | legislation.gov.uk existence check, or landmark list "existence and citation checked" |
| Provision in force | legislation status check |
| Interpretation supported | layer 1/2 claim status; layer 3 if switched on |
| Professional verification | **none has taken place** |

## 4. Legal review pack
Files: `/app/memory/lex2_legal_review_pack.docx` (Word, a decision box for every item) and `/app/memory/lex2_legal_review_pack.md`. Rebuild with `python -m evals.build_review_pack`.

| Section | Contents | Items |
|---|---|---|
| A | Reference scenarios, with the 8 corrections and their sources | 40 |
| B | Official-source rules now given to Lex (the 11 from before plus 5 new: private parking, council parking in Scotland and NI, detention emergency, housing emergency) | 16 |
| C | Landmark cases | 41 |
| D | Legacy fact packs (read from the preview database; all awaiting sign-off) | 38 |
| E | Employment tribunal commencement and transitional issues | 6 |
| F | High-risk deadline calculators | 8 |
| **Total** | | **149** |

The pack's introduction states that nothing in it has been professionally reviewed, and that AI scores are not legal certification.

## 5. Tests (all free or simulated)
- **New:** `test_lex2_final_refinements.py` 21/21.
- **Testing agent (iteration 55):** passed all 19 suites and the offline checks. It found 12 defects through 34 probes; all are now fixed and its probe file passes 34/34. The main ones:
  - The AI check put its warning on the wrong sentence, or none at all.
  - The period check looked at the whole sentence instead of each citation.
  - Number words matched inside other words (e.g. "two" inside "network").
  - "removed", "removal" and "pregnant" caused immigration and employment false positives.
  - The England & Wales 21-day postal rule was applied in Scotland.
  - The passed-date flag was suppressed by words like "ago".
  - Dates written as "5th January 2027" or "January 5, 2027" weren't recognised.
  - Failed AI calls were remembered and counted as cost.
  - Hypothetical questions got "from the dates you gave" dates.
- **Regression: all passed (508 tests in 21 suites)**, plus the offline evaluation at 117/117.
  - Stage 2 safety 44, Phase 2D 21, phase 1 16, wiring 4, 2B 34, 2A-2 91, 2A-3 45, customer 12, Acas deadlines 13, date guard 12, 2A-1 5 + 8, Free fallback 5, law watch 43, financial 18, pass queue 12, Phase 2E corrections 36, iteration-54 probes 34, iteration-55 probes 34, final refinements 21.
- **Not run:** `test_lex_routing` (live paid HTTP; an environment limitation, not a defect).

## 6. Remaining release blockers
1. **No professional legal review yet.** All 149 items in the review pack need a qualified UK lawyer's decision, especially ET-1 (claims straddling 1 Oct 2026) and ET-2 (the Scotland 9 Nov date, sourced from Acas only).
2. **The 38 fact packs are still held back until someone signs them off.** Lex currently relies on the 16 labelled official-source rules instead.
3. **The fixes for the 5 remaining majors have not been confirmed with real answers.** A focused paid rerun needs your approval: those 5 scenarios on all 3 plans, 15 answers, about £0.45.
4. **The optional AI source check is untested with real calls and is OFF.** It needs separate approval to test and to switch on.
5. Already known, not changed here: the financial safeguards and Phase 2C are off in production. Nothing from Phase 2E onwards has been deployed.

## 7. Ready for professional legal review?
**Yes.** The preview build and the review pack are ready for a qualified UK legal professional. Lex should not be described as legally reviewed until that sign-off is complete and the targeted real-answer rerun has passed.
