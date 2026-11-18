# Lex 2.0: automatic law-update integration (Phase 2C completion, preview only)
Date: 18 November 2026.
- **Tracker writes:** OFF throughout (switch `enabled: false`; nothing saved to the tracker records in preview).
- **Not done:** no deployment, no scheduled monitoring, no paid calls.
- **Unchanged:** AI models, prices, budgets, search allowances, Stripe and customer data.

## 1. Already built and reused (Phase 2C)
- **Tracker** (`law_watch.py`): the 9 approved provisions, read from free legislation.gov.uk data only.
- **Detected change types:** first recorded, wording amended, repealed / partly repealed, commenced, status or territorial-extent changed, amendment pending, pending changes applied, provision no longer found.
- **Commencement:** taken only from the official record. A publication date or version date is never treated as the commencement date.
- **Four separate verification statuses:**

| Status | Meaning |
|---|---|
| A | Official metadata verified |
| B | Wording verified |
| C | Interpretation — always unverified |
| D | Professional review — only with a recorded regulated reviewer |

- **Safety:** dry run by default; admin write switch (expires after 30 minutes); a single-use, time-limited signed approval code, which needs a fresh fetch that matches the dry run; an emergency stop (`LAW_WATCH_KILL_SWITCH`); an audit log; version history.
- **Incomplete or inconsistent official records** are held back ("held_unverified") and never written.
- **Lex already had:** customer-facing notes for cited provisions, plus live legislation.gov.uk lookups of the current text and in-force status whenever Lex cites an Act or section (`legal_sources.check_answer`). Lex therefore checks current official legislation instead of relying only on what the model remembers.

## 2. Integration gaps corrected

| Gap | Fix |
|---|---|
| Detected changes didn't reach Lex's knowledge or a reviewer | Each real change saved in an authorised run now creates one `law_update_proposals` entry: "awaiting review", interpretation "not assessed", with the change types, commencement, affecting instruments and linked Lex knowledge. Its ID is the version ID, so the same change is never recorded twice. First records and unchanged checks create none. |
| Signed-off facts kept being used after their source changed | When a watched provision changes, linked `lex_lessons` facts are marked `needs_review`, which the existing sign-off gate already withholds from Lex. They stay withheld until re-signed in the existing flow. **Nothing is automatically approved**; the 38 legacy packs and the 149 review items are untouched. |
| Customers weren't told about unreviewed changes | As you chose, a short caution note: *"The official record shows a recent change to [provision] that hasn't been reviewed yet — check the current official text before relying on it: [link]"*, plus the existing "source fact only" line. UK customers only. |
| Related statutory instruments weren't singled out | New change types: `new_affecting_instrument` (e.g. a commencement or amending SI) and `commencement_date_recorded`. Affecting instruments are listed on the record and on the proposal. |
| Welsh Acts couldn't be tracked | Added the `anaw` type (Acts of the Senedd, e.g. the Renting Homes (Wales) Act 2016). |
| No reviewer workflow | **Existing admin Law tracker card** now has a "Detected law changes awaiting professional review" table (`LawUpdateReview.jsx`) with Approve, Request amendment and Reject. |
| Dry run didn't show the knowledge impact | The dry run now previews `proposed_updates` (linked rules and number of facts affected) without writing anything. |
| Only the 9 provisions were watchable | Added an optional scope, **"official_rules_provisions" (8 provisions behind Lex's new rules)**, marked PROPOSED. It needs your approval and the same switch-plus-code process before anything is saved. The 9-provision scope is unchanged. |

**Review workflow rules:**
- **Approve** requires the reviewer's name, a listed regulator (e.g. SRA, BSB, CILEX) and a registration number. Approval records the review on the source record (status D) as covering *the effect of this change* only; status C stays unverified.
- **Amend** requires notes. **Reject** requires a name.
- A decided update can't be decided again. Two decisions at the same moment can't both apply (fixed after the testing agent's report).
- Every decision is logged in the audit history.

## 3. Tests (official-source samples and simulated changes; no paid calls)
- **New:** `test_lex2_law_update_integration.py` **14/14**. It covers:
  - baseline vs real change;
  - one proposal per change, with no duplicates on re-runs;
  - amendment and commencement by SI;
  - repeal;
  - inconsistent records never promoted;
  - dry run writes nothing;
  - sign-off needing a qualified reviewer, and linked facts not re-approved;
  - reject and amend rules;
  - the conservative customer caution;
  - links to the official-source rules;
  - scopes and free sources;
  - writes still needing the switch and code.
- **Testing agent (iteration 57):** backend and front-end tested.
  - Its edge-case checks (`test_lex2_law_update_edges.py`) found 2 real defects: two decisions at the same moment could both apply, and an Act number could wrongly link to longer numbers (Act 18 matching Act 180). Both are fixed, and the checks now pass **13/13**.
  - Its live API checks `test_lex2_law_updates_api.py` pass **9/9**.
  - Admin screen flow: **100%**. Approval without details showed an error; a requested amendment changed the status. The synthetic test item was removed afterwards, and writes stayed OFF.
  - **Also fixed:** regulator text is now trimmed and upper-cased; approval now updates status D; field lengths are capped; the table scrolls on small screens; the last decision is shown.
- **Regression:** all 23 Lex suites pass and the offline evaluation is 117/117. One existing test now also expects the new `new_affecting_instrument` change type.

## 4. Expected ongoing costs
- **Tracker:** £0. It uses free legislation.gov.uk data under the Open Government Licence: about 9 requests per run for the approved scope, or 17 with the proposed scope. No AI calls and no paid search.
- **Lex answers:** the legislation lookups when a law is cited, and the caution notes, are also free. The existing paid-search allowances are unchanged.

## 5. Steps remaining before controlled activation (each needs your approval)
1. **Deploy** this preview code to production. It isn't deployed yet; everything since the Phase 2E corrections is preview-only.
2. **First write run:** in production, turn writes on (30 minutes), run a dry run, review it, and apply with the code. This saves the baseline records only; first records create no review items.
3. **Optional:** approve the proposed 8-provision scope.
4. **Decide on scheduled monitoring.** It is still off; every run is manual. If you want automatic checks, a separate approval is needed for a schedule. Each scheduled run would still need the write switch and code, unless you approve a different rule.
5. **Appoint a qualified reviewer** to handle the review queue, plus the 149-item review pack and the 38 legacy fact packs.

## 6. Does existing code need deploying?
**Yes**, if you want these features live. Production currently runs the Phase 2C tracker without the proposal, linking or review-screen pieces, and without the later Phase 2E fixes. No deployment has been made.
