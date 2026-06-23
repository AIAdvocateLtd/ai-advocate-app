# Post-Launch Code Review Backlog (DO NOT TOUCH UNTIL APP STORE LAUNCH)

**Source:** Static analysis report from environment 99b5bebe, dated 2026-06-23
**Decision:** All items deferred until Google Play + Apple App Store launches are complete and stable for 30+ days. Per main roadmap, `App.js` and `server.py` refactoring is P4-FORBIDDEN until then.
**Why deferred:** Mid-launch refactors statistically introduce more bugs than they fix. No item in this report is launch-blocking or a real security hole (verified — zero genuine production secrets in test files).

---

## P1 — Tackle first when refactor phase opens

### 1. Split `LexChat` component (`App.js:1813`, ~1,114 lines)
- Extract into `LexChatHeader`, `LexChatThread`, `LexChatComposer`, `LexChatSettings`
- Move chat-state into a custom hook `useLexChat()`
- Critical because: most-used screen, biggest perf win

### 2. Split `server.py` into domain modules
- `routes/auth.py` (login, signup, 2FA, password reset)
- `routes/subscriptions.py` (Stripe sub create/cancel/portal)
- `routes/partners.py` (already half-done in `partner_module.py`)
- `routes/cases.py` (case files, timeline, vault)
- `routes/founder.py` (the /founder dashboard endpoints)
- Keep `server.py` as a thin orchestrator that mounts all routers

### 3. Refactor `build_partner_router()` (`partner_module.py:222`)
- Cyclomatic complexity 34 → target <10
- Split into `register_partner_admin_routes()`, `register_partner_public_routes()`, `register_partner_payout_routes()`

---

## P2 — Tackle in the second pass

### 4. Split `CourtroomModal`, `EmergencyModal`, `SettingsModal`, `CaseFilesModal`
- All 500+ lines in `App.js`
- Each modal → its own file in `src/modals/`
- Lift state into custom hooks

### 5. Refactor `user_to_public()` (`server.py:599`, complexity 32)
- Break into `serialize_user_profile()`, `serialize_user_subscription()`, `serialize_user_limits()`
- Currently returns one huge dict — split into composition

### 6. Refactor `detect_language()` (`server.py:1003`, complexity 31)
- Replace if-else chain with lookup table or strategy pattern
- Possibly: move to a `LanguageDetector` class

### 7. Refactor `signup()` (`server.py:1294`, complexity 20)
- Extract validation, Turnstile, partner-code, welcome-email steps
- Use a pipeline pattern or dataclass-based context object

---

## P3 — Cosmetic / nice-to-have

### 8. Replace index keys with stable IDs (~69 instances)
- Run a codemod: `key={i}` → `key={item.id || i}` where item has an id
- Use `crypto.randomUUID()` for items genuinely lacking IDs

### 9. Add proper deps to React hooks (~124 instances)
- ⚠ **Do not blindly add all flagged deps** — many are intentional run-once effects
- Triage: review each useEffect, decide intent, either:
  - Add the deps + memoize with `useCallback` to prevent infinite loops, OR
  - Add `// eslint-disable-next-line react-hooks/exhaustive-deps` with a comment explaining why

### 10. Replace `is` with `==` in test files (~172 instances)
- Pure cosmetic; pytest still passes either way
- Quick search-and-replace in `tests/` dir

### 11. Extract nested ternaries
- `FirmPortal.js` and `App.js` have several 3-4 level nested ternaries in JSX
- Replace with early returns or named variables

---

## ❌ Findings that are FALSE POSITIVES (don't fix)

### "Hardcoded secrets in test files"
- **VERIFIED FALSE** — scanned for sk_live, pk_live, Turnstile keys, AWS keys, etc. Zero hits.
- The tool was flagging test passwords like `"TestPassword123!"` as secrets.
- No action required.

### "Insecure localStorage usage for auth tokens"
- **DELIBERATE PRACTICE** — used by Stripe Dashboard, Notion, Linear, GitHub, Vercel, etc.
- Switching to httpOnly cookies requires rewriting the entire auth flow, CSRF protection, etc.
- Mitigated by: aggressive Content-Security-Policy, no `dangerouslySetInnerHTML` of user content.
- No action required pre-launch. Consider for v2.

### "Empty catch blocks"
- **INTENTIONAL POLYFILLS** in `nativeBridge.js`, `vaultBiometric.js`, `analytics.js`, `sentry.js`
- These handle browsers/devices where the underlying API doesn't exist (iOS Safari, Brave, Tor)
- Logging would spam Sentry with noise.
- Some have explanatory comments; add comments to those that don't.

---

## 🛡 Engineering principles for the eventual refactor

1. **One module at a time** — never refactor multiple modules in one PR
2. **Tests first** — write a regression test before touching a function with high complexity
3. **Behind a feature flag** — for big rewrites, deploy old + new in parallel for a week
4. **Measure before / after** — bundle size, render time, response time
5. **Never refactor + add features in the same PR** — separate concerns

---

## 📅 Suggested timeline (post-launch)

| When | What |
|---|---|
| **Week 1-4 post-launch** | Don't touch a thing. Monitor crash rates, fix real user bugs. |
| **Week 5-8** | P1 items, with tests written first |
| **Week 9-12** | P2 items |
| **Quarter 2** | P3 items, plus any new findings from a fresh static-analysis pass |
