# Lex 2.0 Phase 2D — Legal Intelligence Fixes (PREVIEW ONLY, not deployed)

No paid AI or search calls were made. AI models, subscriptions, Stripe, financial safeguards, account deletion, customer data and the landing page are unchanged. Phase 2C is still inactive.

## Implemented (all deterministic code)
| Area | Change | Files |
|---|---|---|
| Fabricated court cases | Every case name ("X v Y") or neutral citation that no retrieved trusted source supports is checked. **Lex-introduced → removed** and replaced with "a court decision (reference removed — it could not be verified against a trusted source)". **Customer-quoted → kept but labelled** "(unverified case reference — not found in any trusted source)". The source-check note is added in either case. National Archives stays disabled. | lex_safety.py `guard_case_refs`, `verify_citations`, `finalize_answer`; server.py `_lex_finalize` passes customer text |
| UK jurisdiction | Separates where the customer lives from where the matter is governed. No saved nation + "I live / we live in Aberdeen, Cardiff, Belfast…" → applies that nation and says so in one line. A matter located somewhere ("hospital in Edinburgh", "car park in Leeds") → applies that nation. No saved nation and no clue → asks ONE short question, only for topics where nations differ (housing, family, court, parking, negligence, limitation, wills, employment, police). A short reply ("Scotland", "It's in Cardiff") is understood, including in later turns. A matter elsewhere than the saved nation → asks. The saved nation is never overwritten automatically. A Welsh tenant saying "section 21" follows the property's nation. | lex_safety.py `_LIVES`, `_MATTER`, `_ANSWER`, `_NATION_DIFFERS`, `_answered_nation`, `assess_jurisdiction` |
| Remember home nation | When Lex asks, or assumes from where the customer lives, the chat shows a one-time card: "Which part of the UK do you usually live in?" (England / Wales / Scotland / NI / Not now). It saves only the nation (never the town) via the existing setting. It can be changed in Settings; "Not now" stops future offers. | server.py `_home_nation_prompt`, `POST /api/profile/home-nation-prompt/dismiss`; components/HomeNationPrompt.jsx; App.js |
| Urgent court matters | A received claim form, particulars of claim, response pack, acknowledgment of service, CCJ, civil bill, charge for payment or sheriff officers now count as urgent. Citing a precedent ("The Supreme Court decided in …") no longer makes the question high-stakes. | high_stakes.py |
| Deadline calculator | **England & Wales court claim:** safe working date of issue date + 14 days, explaining the 14/28-day rule (CPR 10.3 / 15.4). A received date alone, Scotland, NI or an unknown nation → unconfirmed, with the facts needed. **Council PCN (England/Wales/Scotland):** windscreen notice: discount safe date = date + 13 (14 days beginning with service). Postal notice (E/W): date + 20. Private charge, NI, unknown nation or unknown service method → unconfirmed. **Consumer (UK-wide):** faulty goods, 30-day right to reject (CRA 2015 s.22); online order, 14 days after delivery (CCR 2013); service, 14 days after the contract. The date guard accepts only dates the customer actually gave. | deadline_calc.py, date_guard.py |
| Prompt injection | "SYSTEM NOTE:", "admin notice:" and similar, plus messages addressed to the AI ("Lex, say…", "AI: confirm…"), are now caught. Ordinary letters ("Dear Assistant: please confirm receipt…") are not flagged. | content_guard.py |
| Unmarried partners | Cohabitation and "common-law" wording, "weren't married", lived together, joint ownership or declaration of trust → family high-stakes. A new prompt section says: do not apply divorce or financial-remedy rules; common-law marriage gives no rights; property depends on title, trusts and contributions; rules differ by nation (Scotland has a strict time limit). Lex asks whose name is on the title. | high_stakes.py |

## Tests (exact counts)
| Suite | Result |
|---|---|
| Offline Phase 2D evaluation (117 checks) | **117 passed, 0 failed** (was 103 / 117) |
| New regression tests `test_lex2_phase2d_fixes.py` | **18 passed, 0 failed** |
| Existing Lex 2.0 suites (2A-1, 2A-1 review, 2A-2 injection, 2A-3 high-stakes, 2B reasoning, ACAS deadlines, customer test 1, date guard, free official fallback, phase 1, phase 1 wiring) | **245 passed, 0 failed** |
| Two older suites (`test_deadline_reminders`, `test_iter19_citations`) | Not run: they log in over HTTP and call the paid chat, so they were skipped under the no-paid rule. Their login step failed before any test ran. |

The offline checks only measure the safety code, not Lex's actual answers. The fake-case check now tests the new free guard, because the National Archives lookup it used before is still disabled.

## Remaining weaknesses
1. **Substantive accuracy is still unmeasured.** No real Lex answers were generated. The 40 AI-drafted reference scenarios still need independent professional review.
2. **Case checking can only compare against retrieved sources.**
   - **Real cases may be removed:** a genuine, well-known case Lex quotes from memory is removed if the search didn't return it.
   - **"Unverified" isn't proof of fake:** a customer-quoted case labelled unverified may still exist.
   - **Missed formats:** "R v Smith" style criminal cases, "Re X" and short forms ("in Smith") are not detected.
3. **Jurisdiction detection is rule-based.**
   - **Limited place list:** about 45 towns are recognised. Ambiguous names (Newport, Bangor, Perth, Newcastle) are ignored.
   - **Assumption from residence:** residence is assumed as the governing nation when nothing else is said. Lex states the assumption and invites correction.
   - **More questions for new customers:** customers with no saved nation will now be asked once on nation-dependent topics.
4. **Deadline calculator gaps.**
   - **Not calculated:** Scotland and NI court response times, private parking periods, NI PCNs and deemed-service maths.
   - **Calendar days only:** the new safe dates use calendar days. They are always earlier than or equal to the true deadline.
5. **Phase 2C:** the ERA 2025 and Renters' Rights Act provisions are still not tracked, and the tracker is still off.

## Source-verification limits (unresolved)
- **Legislation:** checked via legislation.gov.uk (existing).
- **Case law:** checked only against retrieved search or official text. The National Archives Find Case Law lookup stays off until the Open Justice Licence is approved.
- **Deadline rules:** coded from the statutes and rules named above. They need professional review before being relied on.

## Cost per question
- **No new AI calls or paid searches.** Prompts grow by about 100–250 tokens only when the jurisdiction or cohabitation sections apply (under £0.001).
- **Existing date-extraction step:** it now also runs for parking and consumer messages that include a date, at about £0.001–0.002 each, for those messages only.
- **Overall:** Lex still averages about 4p per question.

## Readiness for real-answer testing
Ready for the next stage once you approve:
1. The paid evaluation run (about £6–8 for 40 scenarios × 3 plans plus consistency repeats; about 360 searches, so run it in two batches against the 900 cap).
2. Professional review of the scenarios and deadline rules.

Nothing is deployed.
