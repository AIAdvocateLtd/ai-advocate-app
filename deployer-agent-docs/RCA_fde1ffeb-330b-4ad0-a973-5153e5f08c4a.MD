# Production Verification — aiadvocate.co.uk (Lex 2.0 Phase 2B)

**Mode:** STRICTLY READ-ONLY. No redeploy, no code/data/secret changes, no paid LLM/Tavily/email/Stripe calls were made.
**Deployment:** ai-law-guide-1 (id 10af96b9-36d8-4336-b814-7da19ae5225b)
**Active run:** fde1ffeb-330b-4ad0-a973-5153e5f08c4a (type=redeploy)
**Image:** customers-app-3@sha256:297c8b93e9c65e065ff688735600bddc10d7ce16e0d8ad75891f03de69cfef5e
**DB:** ai-law-guide-1-ai_advocate_db
**Frontend:** Cloudflare (R2)

---

## 1. Deployment identity & image contents — PASS
- Latest deploy run: `fde1ffeb-330b-4ad0-a973-5153e5f08c4a`, status **success / LIVE**.
- Completed: **2026-11-12T16:48:02Z** (UTC). Started 16:42:28Z.
- Running image contains the new/updated backend files (verified from the run's pulled source that built this image, extracted in an isolated sandbox at /app/scratch):
  - `backend/legal_reasoning.py` present (13,822 bytes).
  - `backend/legal_sources.py` present (20,527 bytes).
  (Note: verified via the exact source archive that produced active image sha 297c8b93; the prod pod itself was not exec'd — tool policy.)

## 2. Backend/pod health — PASS
- `GET /` (frontend via Cloudflare) → **200**, real AI Advocate HTML (not nginx default).
- `GET /api` → **200** `{"app":"AI Advocate","status":"ok"}`.
- `GET /api/health` → **404** `{"detail":"Not Found"}` — this route is not defined; the app's health root is `/api` (200). Not a regression.
- Live `/api/*` traffic in logs returning 200: `/api/auth/me`, `/api/tips/daily`, `/api/profile/auto-jurisdiction`, `/api/security/events`, `/api/sponsor`, `/api/reminders/badge`.
- No import errors / tracebacks / exceptions in logs since deploy (filtered search returned 0 matches).
- Cosmetic note: repeated internal `GET /health` → 404 are the k8s/entrypoint probe hitting an undefined `/health`; backend is up and serving — not an error.

## 3. Legal reasoning module — PASS
- `legal_reasoning.py` module docstring: "Lex 2.0 Phase 2B: proportionate legal reasoning, evidence analysis and claim-by-claim label verification."
- AST parse OK (syntactically importable). No log lines referencing legal_reasoning errors.

## 4. Source verification logic (legal_sources.py) — PASS
- Claim-by-claim verification confirmed in code:
  - "in-force sections become 'status checked' citations. **Never marks the *claim* as verified**."
  - Citations tagged `"claim_check": "status_checked"` with label "status checked only: exists and in force … it does not confirm this answer's interpretation".
  - Unverified handling: "could not be found on legislation.gov.uk — treat this reference as **unverified**", caselaw "[⚠ unverified]".
- Matches the requirement: an Act merely mentioned does NOT mark an interpretation as "checked"; only exact provision status is confirmed. AST parse OK. No errors in logs.

## 5. Evidence analysis / timeline — PASS
- `legal_reasoning.py` contains evidence+timeline logic: `_EVIDENCE` analysis block ("a short chronological timeline", "evidence vs hearsay vs allegation"), and a deterministic date-timeline helper ("Lines of an attached document that contain a date — a timeline aid, quoted verbatim, never interpreted"). `depth()` / `prompt_block()` gate on `has_evidence`. No errors.

## 6. Security safeguards preserved — PASS
- `content_guard.py` (16,909 B) and `high_stakes.py` (25,029 B) present in image source.
- `attack_detections` collection exists; TTL index present: `expires_at_1` with `expireAfterSeconds: 0` (code sets `expires_at = now + 90 days`, RETENTION_DAYS=90 — effective 90-day TTL). NOTE: implemented as per-doc `expires_at`+`expireAfterSeconds:0`, NOT a fixed `expireAfterSeconds:7776000` on `at`; functionally equivalent 90-day retention.
- `security_events` is a separate collection (6 docs) — distinct from `attack_detections`.
- Doc counts: attack_detections = 0 (empty, TTL-indexed, no injection attempts logged yet), security_events = 6.

## 7. Customer data intact (counts only) — PASS (no drop/wipe)
- users total: **328** → free 39, plus 15, pro 50, no `tier` field 224 (39+15+50+224=328, reconciles; untiered = default/unconverted signups).
- cases: **88**
- lex_lessons: **46** (Phase 2A-1 admin fact review data intact)
- llm_usage: **267**
- conversations (chat sessions): **712**
- Note: no standalone `fact_pack`/`fact_packs` collection exists; `fact_packs.py` builds packs from case data at runtime. Case-related data present via `cases` (88), plus `case_items`, `contract_analyses`, `lex_uploads` collections.
- All values non-zero and consistent with an established app — no evidence of data loss.

## 8. AI model routing & key — PASS
- Model routing config present and unchanged in code (names only): providers anthropic/openai/gemini in `ai_usage.py` (TOKEN_FACTORS), model ids `claude-haiku-5-5`, `claude-sonnet-5-5`, GPT-5.2 referenced; `lex_output.py` comment "Model choice is unchanged."
- `EMERGENT_LLM_KEY` present and non-empty in active run env.

## 9. Subscriptions / Stripe — PASS
- Stripe secrets present (existence only, values never read): STRIPE_API_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET, plus price IDs STRIPE_PRICE_PLUS, STRIPE_PRICE_PRO, STRIPE_PRICE_YEARLY_PRO, firm & top-up prices — all non-empty.
- app_settings collection intact (2 settings docs, incl. "stage3").
- users with `stripe_customer_id`: **3**; users with `subscription_status="active"`: **52** (gap expected — most paid/active tiers are comped via firm-comp grants, not Stripe-billed; pre-existing characteristic, not a regression).
- OBSERVATION (pre-existing, not caused by this deploy): `STRIPE_PRICE_MONTHLY` and `STRIPE_PRICE_YEARLY` are empty; `TURNSTILE_SITE_KEY` is empty. Flagging for awareness only — the active price IDs used by current tiers are populated.

## 10. Spending limits & Tavily — PASS
- Spending-limit settings present in env: `AA_DAILY_LLM_BUDGET_GBP` (non-empty), `TAVILY_MONTHLY_CAP` (non-empty); per-call cost/token accounting in `ai_usage.py` unchanged.
- `TAVILY_API_KEY` present and non-empty.

---

## Overall: ALL 10 ITEMS PASS
The Lex 2.0 Phase 2B deploy is LIVE and healthy; new reasoning/source-verification code is in the running image; all Phase 2A safeguards (content_guard, high_stakes, lex_lessons, attack_detections TTL, separate security_events) are preserved; customer data is intact; required keys and spending limits are present.

Minor, non-blocking observations (pre-existing, user awareness only): `/api/health` is 404 (health root is `/api`); empty Stripe price secrets STRIPE_PRICE_MONTHLY / STRIPE_PRICE_YEARLY and empty TURNSTILE_SITE_KEY; attack_detections TTL uses expires_at+expireAfterSeconds:0 rather than a literal 7776000.
