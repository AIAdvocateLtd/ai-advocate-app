# Read-Only Post-Redeploy Verification — ai-law-guide-1

**Run:** 9a435b6a-12fa-4c3b-8cdc-25eb3f227d1d (type: redeploy, trigger: agentic)
**Image:** customers-app-5@sha256:55e9a5b4a101ee8f9482ef092e918771714f63ea48bae834b8fdff17c2dc3131
**Mode:** READ-ONLY. No data/config/secrets changed, no redeploy, no customer message contents read.

## 1. Latest production deployment status & activation
- Status: **SUCCESS** — latest run and currently ACTIVE (serving traffic).
- Run id: `9a435b6a-12fa-4c3b-8cdc-25eb3f227d1d`
- All steps green: wakeup_environment, build, mongodb_migrate, manage_secrets, deploy, health_check.
- Activation / go-live timestamp: **2026-11-06T05:44:12Z (GMT)** (run completed_at; health_check completed 05:44:11Z; deployment_updated_at 05:44:12Z).

## 2. Backend health
- `GET /api/` on live URL (https://ai-law-guide-1.emergent.host) → **200 OK**, body `{"app":"AI Advocate","status":"ok"}`, 513ms.
- Startup logs clean: "Application startup complete", "Uvicorn running on http://0.0.0.0:8001". No import/startup errors, no tracebacks.

## 3. Deployed source verification (eph sandbox, run source at /app/scratch)
- `backend/server.py`: the fallback repair string `initial_messages=list(initial_messages) if len(initial_messages) > 1 else None` is present **exactly twice** (lines 2063 and 2081), both inside the `/lex/chat` handler (route declared at line 1940; streaming `/lex/chat/stream` begins at 2152, so both constructions are within the non-streaming /lex/chat handler). grep -c = 2. CONFIRMED.
- `backend/tests/conftest.py`: **exists** (125 bytes). CONFIRMED.

## 4. Production SENTRY_ENV
- **DISCREPANCY.** Stored SENTRY_ENV is non-empty and does **NOT** equal "production"; it matches_expected=TRUE for the value **"preview"**.
- Expected per request: "production" or unset (code defaults to "production"). Actual production value = **"preview"**.
- Impact: production Sentry alerts are tagged env="preview", so they are NOT separated from preview alerts. (Secret value itself never revealed — confirmed via list_secrets equals-comparison only.)
- SENTRY_DSN and REACT_APP_SENTRY_DSN are both present/non-empty.

## 5. Error/5xx scan since activation (loki, last 1440 min)
- Summary: total 170 lines, status_counts {200:3, 404:155}. No 5xx.
- 404s: all are internal k8s probes hitting `GET /health HTTP/1.0` (app exposes `/api/...`, so bare `/health` 404s) — probe noise, not app errors.
- 2 "error" lines: nginx `connect() failed (111: Connection refused)` to upstream 127.0.0.1:8001 `/health` at 2026-11-06 05:43:46 — during the ~1s window before uvicorn finished booting (startup race), self-resolved once backend came up. Transient, not ongoing.
- Targeted filter for `traceback|blankreply|blank streamed|couldn't finish|fallback|error|warn|500|502|503` (excluding /health probe noise): **0 matches**.
- No BlankReply / "Lex couldn't finish" / "Blank streamed reply" / fallback warnings since activation.

## Verdict
Deployment is healthy and live. The fallback-repair code and conftest.py are confirmed in the deployed image. One config discrepancy: production SENTRY_ENV="preview" instead of "production"/unset — user action required in Secrets tab.
