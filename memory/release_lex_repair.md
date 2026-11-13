# Release: Urgent Lex Repair (Stage 1 + Stage 2 + blank-reply fix) — preview verified 2026-11-05, NOT deployed

## Files changed vs production
Backend new: ai_usage.py, chat_memory.py, lex_safety.py, lex_output.py, scripts/flag_fact_review.py, tests/* (test_stage1_memory_usage, test_stage2_safety,
test_blank_reply_fix, stage2_live_check, blank_reply_live_check, token_calibration, free_tier_output_check, test_iter44-46_*).
Backend modified: server.py, rag.py, deadline_calc.py, lex_lessons.py. Frontend modified: src/App.js (stream handler only: use server full_text; show
'lex_incomplete' notice without re-sending). No model routing, price, quota, Stripe or layout changes.

## Blank-reply fix
lex_output.gen_params: Haiku 5.5 thinking disabled (cap 1200 unchanged); Sonnet 5.5 thinking budget 1024 / cap 2600; Deep Think budget 1500 / cap 4000;
GPT-5.2 unchanged. Blank primary -> existing Sonnet 4.5 fallback; blank again -> 503 / SSE error code lex_incomplete, quota refunded, nothing saved.
finish_reason=length -> localised "cut short — reply continue" note. llm_usage: finish_reason, reasoning_tokens; admin llm-spend lex_reply_health.

## Deploy procedure
1. Founder approval. 2. Emergent Deploy (same pipeline). No new env vars required; do NOT set LEX_CROSS_MEMORY_ENABLED (keeps cross-chat memory off).
3. requirements.txt already contains tiktoken 0.12.0 / litellm 1.80.0. 4. Post-deploy smoke (fictional): Free, Plus, Pro and Deep Think one question
each (stream) -> non-blank; GET /api/admin/llm-spend shows lex_reply_health with blank 0. 5. Watch lex_reply_health + backend logs for
"Blank streamed reply" for 24h.
Optional (preview-only now): run scripts/flag_fact_review.py against production ONLY if founder wants the 25 needs_review flags there (adds flags, no text change).

## Rollback
Use Emergent's Rollback to the last production checkpoint (deploy run 2f1ec1d6, live since 2026-11-04 01:10 UTC) — no data migration to undo:
new llm_usage fields are additive; conversations.safety_checks / research_status are additive; no schema removals.
Note: rolling back restores the blank-reply bug (production currently has it).

## Production config differences to check at release
- Production has no ai_usage/lex_safety/lex_output code yet; its llm_usage has only 41 legacy rows (no stream logging) — spend history starts at deploy.
- TAVILY_API_KEY / TAVILY_MONTHLY_CAP must exist in production secrets (preview: cap 900); missing key -> research_status not_configured (handled).
- Fact-pack needs_review flags exist in preview DB only.
- Stripe/Resend/Turnstile live keys unchanged.

## Final checks round (2026-11-05)
- Free conciseness: lex_output.CONCISE_SUFFIX appended to the model-only user turn for claude-haiku-5-5 (not saved). Experiment
  (tests/free_tier_concise_experiment.py): 1200 baseline 3/6 complete; concise@1200 6/6; avg out 1066 -> 946 tokens.
  Live (tests/free_tier_live_validation.py + blank_reply_live_check): English 6/6 complete; ar/pl/zh 3/3; Welsh 2/3; Urdu 0/3; Hindi 0/1
  (cut-off note shown). Hindi/Urdu need ~1,770-1,900 tokens even concise (2000 cap -> complete). PROPOSED (not applied): Free cap 2000.
- Legal text: LEX_LAW_UPDATES no longer states pre-Oct-2026 ET matters definitely keep 3 months (transitional caveat, never say out of
  time); Wages Act 1986 marked repealed -> ERA 1996 Part II. deadline_calc ET transitional caveat; weekend note wording.
- Security: login no rate limit/lockout (Medium, pre-existing, credential stuffing feasible); JWT in localStorage 30 days (Low, no XSS sinks
  found: no dangerouslySetInnerHTML, AI text rendered as React text, links from retrieved/constructed URLs); CORS * + credentials (Low,
  bearer-header auth, no cookies -> not exploitable cross-site).
- Round AI cost ≈ £0.79.

## Founder-approved deploy (2026-11-06)
- Free cap 1200 -> 2000 (lex_output.FREE_MAX), concise instruction kept. Pre-deploy live: 11/11 Free complete (finish=stop) incl. Welsh x3,
  Urdu x3, Hindi x3; texts checked: deadlines, ACAS, adviser referral, disclaimer, CONFIDENCE MEDIUM present. Cost £0.26. Unit 54/54.
- Deploy dispatched to deployer (job c12aebe9…). POST-DEPLOY TODO: live smoke Free/Plus/Pro/Deep Think (regular + stream), research
  warnings/citations/memory, admin llm-spend lex_reply_health, Stripe/pricing unchanged, design/admin intact, 24h monitoring.
  Rollback: Emergent Rollback to run 2f1ec1d6.

## Incident 6 Nov 05:19:31 GMT (Sentry alert BlankReply + 503 in server.lex_chat)
- Origin: PREVIEW, not production. Production served run 2f1ec1d6 until the new release (run a00761ab) went live 05:25:05 GMT;
  prod had 0 llm_usage/conversation/usage rows on 6 Nov and no matching logs. Preview Sentry env = "preview"; the alert matches the
  mocked failure test (test_regular_both_blank_refunds...) run just before deploy dispatch — pytest imported server.py with Sentry on.
- Fix: tests/conftest.py blanks SENTRY_DSN during pytest. Real bug found while investigating (preview repro): regular-chat fallback reused
  the history list mutated by the failed primary (blank assistant turn + question twice). Fixed with list(initial_messages) copies;
  regression test test_followup_fallback_gets_clean_history (fails without fix). 55/55 unit; live follow-ups Free+Pro OK (£0.11).
- Redeploy dispatched 2026-11-06 ~05:40 GMT.
