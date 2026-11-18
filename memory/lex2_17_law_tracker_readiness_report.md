# Lex 2.0 — 17-law tracker activation-readiness report (2026-11-18, PREVIEW, not deployed)

## Watchlist (all specific provisions — no whole-Act entries)
| # | legislation.gov.uk id | Provision | Jurisdiction (tracker) | Official extent | Status (dry run) |
|---|---|---|---|---|---|
| 1 | ukpga/1996/18 ERA 1996 | s.94 | England & Wales | E+W+S | in force |
| 2 | ukpga/1996/18 | s.108 | England & Wales | E+W+S | in force, 11 unapplied effects |
| 3 | ukpga/1996/18 | s.111 | England & Wales | E+W+S | in force (version from 2026-10-01) |
| 4 | ukpga/2010/15 Equality Act 2010 | s.13 | England & Wales | E+W+S | in force |
| 5 | ukpga/1988/50 Housing Act 1988 | s.21 | England & Wales | E+W | partly repealed (version from 2026-05-01) |
| 6 | ukpga/2004/34 Housing Act 2004 | s.213 | England & Wales | E+W | partly repealed |
| 7 | ukpga/1989/41 Children Act 1989 | s.1 | England & Wales | E+W | in force, 1 unapplied effect (ukpga/2026/21) |
| 8 | asp/2016/19 Private Housing (Tenancies) (Scotland) Act 2016 | s.51 | Scotland | S | in force |
| 9 | nisi/1996/1919 Employment Rights (NI) Order 1996 | art.126 | Northern Ireland | N.I. | in force, 1 unapplied effect |
| 10 | ukpga/1996/18 | s.23 | England & Wales | E+W+S | in force (version from 2026-10-01) |
| 11 | ukpga/1996/18 | s.203 | England & Wales | E+W+S | in force, 2 unapplied effects |
| 12 | ukpga/2010/15 | s.123 | England & Wales | E+W+S | in force (version from 2026-10-01) |
| 13 | ukpga/2004/34 | s.214 | England & Wales | E+W | partly repealed |
| 14 | anaw/2016/1 Renting Homes (Wales) Act 2016 | s.173 | England & Wales (Wales) | E+W | in force |
| 15 | ukpga/2015/15 Consumer Rights Act 2015 | s.22 | England & Wales | E+W+S+N.I. | in force |
| 16 | ukpga/1980/58 Limitation Act 1980 | s.28 | England & Wales | E+W | in force |
| 17 | nisi/1996/1919 | art.140 | Northern Ireland | N.I. | in force, 2 unapplied effects |

Items 1–9 = original nine (`WATCHLIST`); 10–17 = the eight from `PROPOSED_WATCHLIST` in law_watch.py (unchanged, not substituted).
Duplicates: none. Overlaps (same instrument, different provisions): ERA 1996 ×5, Equality Act ×2, Housing Act 2004 ×2, ERO (NI) ×2.

## Read-only dry run (live legislation.gov.uk, 17 requests, 2.1 s, £0)
17/17 resolved, A (official metadata) verified 17/17, B (wording retrieved) 17/17, 0 unavailable / not found / held / invalid.
C (interpretation) unverified for all; D (professional review) none. DB counts unchanged before/after (0 records written).

## Code changes (preview)
- law_watch.py: scope `all_17`; `schedule_state`, `set_schedule`, `baseline_missing`, `scheduled_run`, `alert_email`; `run_check(scheduled=True)`.
- server.py: `POST /api/admin/law-watch/schedule` (admin), `POST /api/cron/law-watch` (cron secret; no-op + no DB writes while OFF); law-updates list id serialisation.
- .emergent/crons.yml: `law-watch` 06:00 Europe/London daily (other 3 jobs unchanged).
- LawWatchAdminCard.jsx: 17-law dry run, daily-monitoring control + last run.

## Tests
New tests/test_lex2_17_law_tracker.py 13/13. All Lex/2C/2E/safety suites pass (no-paid mode), law_updates_api 9/9, offline eval 117/117.
