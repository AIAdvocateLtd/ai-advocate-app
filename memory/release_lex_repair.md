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
