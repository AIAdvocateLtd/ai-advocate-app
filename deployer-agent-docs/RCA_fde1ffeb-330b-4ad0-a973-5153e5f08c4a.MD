# lex-learning weekly job — production inspection (READ-ONLY)

Deployment: ai-law-guide-1 (aiadvocate.co.uk) · DB: ai-law-guide-1-ai_advocate_db · active run fde1ffeb-330b-4ad0-a973-5153e5f08c4a
No writes/redeploys/endpoint calls made. Counts/dates only, no PII, no lesson text.

## 1. Cron registered/enabled in prod
- No scheduler-config tool exists, but execution proves it is wired in prod: `cron_runs` holds a `lex-learning:` doc fired **2026-11-09T07:01:42Z** — a Monday ~07:00 Europe/London, exactly matching schedule `0 7 * * 1`. `WEBHOOK_CRON_SECRET` secret is present.
- Only ONE scheduled execution recorded to date. No "next run" value is stored in the DB; next expected ≈ **Mon 2026-11-16 07:00 Europe/London**.

## 2. cron_runs (_id prefix "lex-learning:")
- Count: **1**. Only/most-recent `at`: **2026-11-09T07:01:42.711928Z**.
- No TEST/test in id.

## 3. lex_lessons by source
- source **law_watch**: count **3**, status breakdown pending=3, approved=0. Most recent created_at **2026-11-09T07:01:52.980018Z**.
- source **thumbs_down**: count **0** (no docs).
- (Context: lex_lessons total 46; other sources present = fact_pack, law_note. Statuses in collection: pending, approved.)

## 4. lex_feedback rating "down"
- Collection **`lex_feedback` does NOT exist** in prod → rating "down" total = **0**, unprocessed = **0**. The weekly job's phase (a) has never had input.
- Related note (not the code's lex_feedback): a separate `feedback` collection (surface "lex_chat") exists with rating=down count **2**; it has no processed flag and is NOT what `lex_lessons.weekly_job` reads. Consistent with 0 thumbs_down lessons and no phase-(a) Claude call.

## 5. Cost evidence
All lex-learning usage is logged in `llm_usage` (fields: feature, call_site, model, provider, cost_gbp, ts). **No separate `ai_usage` collection exists** — Tavily rows are stored in `llm_usage` with provider "tavily".

- feature **cron_lex-learning** (4 records, 2026-11-09):
  - 1× anthropic `claude-sonnet-5-5`, call_site "lessons", £0.015239
  - 3× tavily `search-basic`, call_site "legal_research", £0.0063 each = £0.0189
  - subtotal **£0.034139**
- feature **admin_lex-lessons_run-now** (4 records, 2026-11-07):
  - 1× anthropic `claude-sonnet-5-5`, call_site "lessons", £0.016451
  - 3× tavily `search-basic`, legal_research, £0.0063 each = £0.0189
  - subtotal **£0.035351**
- **Combined (last 90 days): £0.06949.** Per-run: one cron run (Nov 9) + one admin run (Nov 7).
- Tavily legal_research within ~10 min after the cron `at` (07:01:42): **3** records at 07:01:45.47, 07:01:48.20, 07:01:50.96 ✓ (matches "3 basic searches").
- `tavily_usage` monthly counts (app-wide, not lex-only), last 4 months: 2026-08 = 180, 2026-09 = 170, 2026-10 = 398, 2026-11 = 106 (as of 2026-11-12).

## 6. Backend logs ("lex learning" / "weekly lex learning job failed")
- **0 matching lines** in available retention. Current active run's pods started 2026-11-12 16:42Z; the Nov 9 cron and Nov 7 admin run predate this run, so their stdout is outside this run's Loki window (24h) — not observable. No failure evidence seen; success is inferred from the DB writes above (cron_runs doc + 3 law_watch drafts + usage rows all timestamped at the run).

## 7. Phase 2C collections & env
- `law_watch_records`, `law_watch_history`, `law_watch_runs`, `law_watch_seen`, `law_watch_fact_checks`: **ALL ABSENT** (confirmed via list_collections — 55 collections, none `law_watch_*`). Expected ✓
- env **`LAW_WATCH_WRITE_ENABLED`: NOT set** (absent from the deployment's secret/env key list). Expected ✓

## Summary
The weekly lex-learning job is live and has fired once in prod (2026-11-09, on schedule), producing 3 law_watch pending lessons, 1 Claude Sonnet 5.5 call + 3 Tavily basic searches (£0.0341). The thumbs_down path has produced nothing because `lex_feedback` does not exist. An admin run-now also fired 2026-11-07 (£0.0354). Phase 2C law_watch collections and LAW_WATCH_WRITE_ENABLED are absent as expected. No errors found; no action required.
