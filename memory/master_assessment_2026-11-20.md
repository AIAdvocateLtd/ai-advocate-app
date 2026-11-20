# AI Advocate — Lex 2.0 & security master assessment (2026-11-20). Read-only; nothing deployed/changed in production.

## A. Lex 2.0 current status
LIVE: Tavily web search restricted to official domains (legislation.gov.uk, bailii, judiciary.uk, supremecourt.uk, gov.uk, acas, caselaw.nationalarchives) + 2 general hits, 900/month internal cap; legislation.gov.uk direct: real section text/status/extent for Acts the customer names (grounding_sources, max 2) and post-answer check of every Act/SI Lex cites (check_answer: not found / repealed / not in force / wrong nation fixed or flagged); Acas guidance pages fetched directly (24h cache); jurisdiction detection + home-nation prompt + Wales/NI/Scotland rules (lex_guidance); date_guard + deadline_calc (deterministic deadlines incl. 1 Oct 2026 ET change); high_stakes classifier + safeguards; landmark_cases allowlist (41) + removal of unsupported case citations; legacy fact packs (38, unreviewed, labelled) + approved lessons; law_watch.annotate caution notes.
BUILT BUT OFF: source_ai_check (AI claim-support check), CASELAW_VERIFY_ENABLED (Find Case Law existence check), daily law-watch schedule.
NOT IMPLEMENTED: topic-based legislation discovery when no Act is named; judgment search/reading; EU law; official sources for the other 14 supported countries (US ES FR IQ PL DE IN PK IT PT CN AE AU CA) — web search only.
PRODUCTION ISSUE: Tavily returning HTTP 432 "exceeds plan usage limit" (x8) → web research currently failing; Lex answers without it (fallback). legislation.gov.uk calls healthy.

## B. Official sources (probed free)
legislation.gov.uk: data.xml per provision, /changes, /new feed — works, OGL v3, free; fair-use rate limits.
Find Case Law (TNA): atom search + judgment XML work. Open Justice Licence does NOT permit computational analysis (programmatic bulk searching); separate free licence application required (29 questions). Single-citation existence check lower risk but keep OFF until licence decision.
EUR-Lex/Cellar: SPARQL + HTML by CELEX work, free (EU reuse policy). Retained EU law in UK differs → use legislation.gov.uk "eur" versions for UK.
Other countries: official portals exist (e.g. US govinfo/eCFR, FR Légifrance API (free, registration), DE gesetze-im-internet, ES BOE API, AU legislation.gov.au, CA Justice Laws, IN India Code) — each needs separate work/terms; do not claim coverage.

## E. Social sign-in (prod)
334 accounts; 16 genuine Google (1 with password, 15 Google-only), 0 Apple, 0 paid social accounts; 4 QA fake-google accounts still present; 2 new social signups since 19 Nov.

## F. 2FA
Preview complete (iteration_58 100%, tests/test_auth_2fa_sessions.py 11/11). Prod: TOTP_ENC_KEY missing; 0 users with TOTP.

## D. Tracker (prod)
17 records + 17 history saved 2026-11-19 21:24Z (1 manual run, 0 changes); schedule never enabled (2× 409 on enable — preview reproduction shows the refusal occurs when "Turn on" is pressed before the baseline is saved / writes off; full sequence succeeds in preview); no proposals; 5 records with pending effects; kill switch not set.
