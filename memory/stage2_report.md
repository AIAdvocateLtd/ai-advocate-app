# Stage 2 — Legal research & reliability repairs (preview only, NOT deployed) — 2026-11-05

## Files
Created: backend/lex_safety.py, backend/scripts/flag_fact_review.py, backend/tests/test_stage2_safety.py (unit, no AI),
backend/tests/stage2_live_check.py (live, fictional), backend/tests/token_calibration.py, memory/token_calibration_results.json,
memory/lex2_memory_proposal.md. Testing agent added backend/tests/test_iter45_stage2_live.py + test_iter45_stage2_quota_stream.py.
Modified: backend/rag.py, backend/deadline_calc.py, backend/ai_usage.py, backend/server.py (lex chat + stream + llm-spend only),
frontend/src/App.js (1 line: streamed bubble now shows the server's checked final text; no layout change).

## Cross-conversation memory
- Cause: both chat endpoints injected the first message of the customer's 4 most recent OTHER conversations with a rule
  telling Lex it "MUST acknowledge" shared entities -> facts from unrelated matters appeared.
- Fix: code kept in lex_safety.build_cross_memory, gated by env LEX_CROSS_MEMORY_ENABLED=1 AND user.memory_consent.cross_chat=true.
  Neither exists -> OFF for everyone. When enabled later, prompt says the chats are separate matters, never import facts,
  label "In a separate conversation…", and confirm before relying.
- Customer isolation: every query filters by user_id (history, case files, attached docs, cross memory). Tested live + unit.

## Token / cost estimates
- Cause of under-estimate: chars/4. Measured (5 Nov 2026) vs chars/4: Claude 5.5 -36% to -66% (tokenizer ~1.3–2.3x o200k),
  GPT-5.2 -1% to -31%.
- Fix 1: LlmChat._execute_completion patched to capture provider usage -> nearly all calls are now MEASURED (live run: 19/19 LLM rows measured).
- Fix 2: estimates (errors / missing usage) use tiktoken o200k x provider factor (Claude 1.7, non-Latin 2.4; GPT 1.05) + 8/msg.
  Validated error: -9% (Welsh) to +32% (JSON); old -20% to -66%.
- Rows: measured true/false, tokens_source provider | estimated_tokenizer_v2 | not_applicable; cost_source measured_/estimated_tokens_x_rate_table.
- /admin/llm-spend adds cost_basis {measured, estimated, flat_rate} + note. All £ = our rate table, not the provider invoice.
- Finding (not changed — model routing frozen): Claude Haiku 5.5 bills hidden reasoning tokens (680 tokens for 249 visible; a Welsh
  test hit the 700 cap with an EMPTY reply). Free tier max_tokens 1200 could truncate answers. Recommend review in Stage 3/4.

## Research failures
rag.research() returns status ok | not_needed | not_configured | quota_exhausted (local cap or Tavily 402/429/432/433) |
unavailable (errors/timeouts/401) | no_results. Credits only counted for successful calls.
On failure: prompt forbids claiming verification, requires a plain sentence about not checking sources, no [n], no deep URLs;
high-risk adds no definitive conclusions + confidence LOW/MEDIUM + official next steps by topic.
Server backstop (lex_safety.finalize_answer): high-risk failure -> localised note (11 languages) inserted before disclaimer,
[CONFIDENCE: HIGH] -> MEDIUM; any "I've checked/verified" claim -> note. research_status returned + stored.

## Citations
verify_citations: drops [n] not in retrieved list; drops [n] where the sentence names an Act/section the source text doesn't contain;
retrieved URLs kept; official homepages/1-level pages kept; deeper official URLs -> site root; non-official URLs removed;
unverified case citations listed -> "Source check" note. Per-citation claim_check stored (supported/not_confirmed/unchecked/not_cited).
Limitation: claim support is keyword-level (Act name+year / section number), not semantic; no independent case-law database check yet (Lex 2.0).

## Jurisdiction
assess_jurisdiction separates customer location ("I live in…") from matter location ("flat/job/court in…") and legal-system markers
(section 173, notice to leave, LRA, sheriff court…). City names alone never decide; ambiguous towns (Bangor, Newcastle, Newport,
Perth, Richmond) ignored. Topic-aware (immigration UK-wide; employment differs only for NI). Conflict -> one short question, then
caveated general info, deadline calc gets "unknown". Explicit "under Scots law" honoured for that answer. Saved profile never changed.

## Deadlines
Added: GOV.UK bank holidays 2025–2027 per nation (Scotland working days), weekend/bank-holiday warnings (no assumed roll-forward),
month-end caution, unknown nation -> all-nation rules or safe earliest date (ET: NI 3-month date; contract debt: Scotland 5 yrs),
late ACAS warning, ACAS-without-certificate (no ET1 date), divorce not calculated for Scotland/NI, court/claim-form wording triggers
NO_CALC guidance (no precise date unless app-calculated). Extraction no longer defaults to England.
Unit-tested: ET old/new rule, month end, leap years, ACAS extension/late/pending, unknown nation, weekend, Scottish deposit with
St Andrew's/Christmas/New Year, tenancy unknown nation, divorce outside E&W, limitation, visa on bank holiday, missing date.
Open legal question for review: whether events before 1 Oct 2026 whose 3-month limit had not expired get 6 months (calculator
uses 3 months = earlier, safer date).

## Fact-pack review (preview DB flags only — text/status unchanged)
25 lex_lessons rows flagged needs_review (+review_priority, review_reason, review_flagged_at, review_flagged_by=stage2_audit):
HIGH: Two-child limit abolition; earned settlement (ILR); Scotland breach-of-contract 9 Nov 2026; pending AI drafts on Crime and
Policing Act 2026, HC 584, earned settlement, ET 6-month change. MEDIUM: SSP, SMP, ACAS 12 weeks, England deposits/assured
tenancies, UC rates, benefit cap, B2 English, ILR fee, citizenship fee, Graduate 18 months, other pending drafts.
LOW: NLW (annual), RRA Shelter source, spouse English levels. Code-level LEX_LAW_UPDATES reviewed: consistent; ET transitional rule unverified.
Re-run: python backend/scripts/flag_fact_review.py [--dry-run]. Production DB untouched.

## Tests
Unit 44/44 + Stage 1 suite pass. Live script 26/26 pass. Testing agent iteration_45: 9/10 -> the lock-out risk gap fixed and
re-verified live (quota_exhausted, note shown in UI, confidence not HIGH). Pre-existing unrelated failures: test_lex_routing.py
(signup now needs email verification), test_iter41 duplicate-reminder test (expects old dedupe response shape).
AI testing cost (rate-table estimate): ~£1.16 metered + ~£0.05 calibration ≈ £1.21.
Remaining limitations: high-risk "no definitive conclusions" is prompt-enforced (backstop note + confidence downgrade are deterministic);
[SOURCES:] tail may list law Lex cited from knowledge; non-English "verified" claim detection is English-only.
