"""Summarise evals/results_live.json (no AI calls). Run: cd /app/backend && python -m evals.report_live_eval"""
import json
import os
from collections import defaultdict

from evals.lex_eval_scenarios import SCENARIOS

D = json.load(open(os.path.join(os.path.dirname(__file__), "results_live.json")))
DIMS = ["accuracy", "jurisdiction", "deadlines", "citations", "missing_facts", "reasoning", "uncertainty_escalation", "trap_resistance"]
SEV = ["none", "minor", "major", "critical"]


def main():
    R = D["results"]
    tiers = ["free", "plus", "pro"]
    by_tier = {t: defaultdict(list) for t in tiers}
    sev = {t: defaultdict(int) for t in tiers}
    rows, crit = [], []
    area = defaultdict(lambda: defaultdict(list))
    mc = {t: defaultdict(int) for t in tiers}
    for s in SCENARIOS:
        r = R.get(s["id"])
        if not r:
            rows.append((s["id"], "NOT RUN"))
            continue
        cells = []
        for t in tiers:
            a = r.get(t, {})
            if not a.get("ok"):
                cells.append(f"{t}:ERROR")
                sev[t]["error"] += 1
                continue
            g, c = a.get("ai_review") or {}, a.get("checks") or {}
            for k, v in c.items():
                if v is True:
                    mc[t][k] += 1
            mc[t]["answered"] += 0
            if "parse_error" in g or not g:
                cells.append(f"{t}:unreviewed")
                sev[t]["unreviewed"] += 1
                continue
            tot = sum(int(g.get(d, 0) or 0) for d in DIMS)
            for d in DIMS:
                by_tier[t][d].append(int(g.get(d, 0) or 0))
            by_tier[t]["total"].append(tot)
            area[s["area"]][t].append(tot)
            sv = g.get("severity", "none")
            sev[t][sv] += 1
            if sv in ("major", "critical"):
                crit.append((sv, s["id"], t, (g.get("wrong_or_risky_statements") or [])[:2], g.get("fail_modes_hit") or []))
            cells.append(f"{t}:{tot}/16 {sv}")
        rows.append((s["id"], " | ".join(cells)))
    out = {"per_scenario": rows, "severity": {t: dict(sev[t]) for t in tiers},
           "avg_by_dim": {t: {d: round(sum(v) / len(v), 2) for d, v in by_tier[t].items() if v} for t in tiers},
           "avg_total_by_area": {a: {t: round(sum(v) / len(v), 1) for t, v in d.items() if v} for a, d in area.items()},
           "machine_true_counts": {t: dict(mc[t]) for t in tiers},
           "major_critical": sorted(crit, key=lambda x: SEV.index(x[0]), reverse=True), "runs": D["runs"], "spent_gbp": D.get("spent_gbp")}
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
