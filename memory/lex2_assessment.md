# Lex 2.0 — Read-only assessment (2026-11-06). No code changed.

## Current pipeline (chat: /lex/chat + /lex/chat/stream)
jurisdiction (lex_safety.assess_jurisdiction: regex nations/places + profile + app country)
-> research (rag.py: 2 Tavily basic searches on the raw message: 3 official-domain + 2 open-web, 350-char snippets)
-> hard-coded deadlines (deadline_calc: Haiku 4.5 extracts dates, Python computes; bank holidays 2025-27)
-> model by tier (Free Haiku 5.5 / Plus GPT-5.2 / Pro Sonnet 5.5 / Deep Think Sonnet 5.5 + thinking)
-> finalize_answer (lexical citation check, URL allow-list, case refs flagged, confidence downgrade).
Not grounded: letters (Sonnet 4.5), contract review (Gemini Flash/Sonnet 4.5), outcome predictor, practice, evidence,
no-login taster (Haiku 4.5, no research, no deadlines, no finalize).

## Costs observed (estimated)
Tavily research ~£0.0126 per legal message (2 credits) — more than the Free model itself (~£0.009).
Deadline extractor ~£0.002 when triggered; Deep Think router ~£0.0001.

## Full report: see the chat summary of this date.
