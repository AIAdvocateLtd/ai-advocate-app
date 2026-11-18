"""Compare the Phase 2E targeted retest with the original Phase 2E answers for the same scenarios (AI-assisted review only).
Run: cd /app/backend && python -m evals.compare_retest"""
import json
import os

D = os.path.dirname(__file__)
DIMS = ["accuracy", "jurisdiction", "deadlines", "citations", "missing_facts", "reasoning", "uncertainty_escalation", "trap_resistance"]
TIERS = ["free", "plus", "pro"]


def _total(g):
    return sum(int(g.get(k) or 0) for k in DIMS) if g and "parse_error" not in g else None


def main():
    new = json.load(open(os.path.join(D, "results_live_retest.json")))
    old = json.load(open(os.path.join(D, "results_live.json")))["results"]
    ids = list(new["results"])
    print("Scenario | " + " | ".join(f"{t} old→new" for t in TIERS))
    agg = {t: {"old": [], "new": [], "dims_old": {k: [] for k in DIMS}, "dims_new": {k: [] for k in DIMS},
               "sev_old": {}, "sev_new": {}} for t in TIERS}
    for sid in ids:
        row = []
        for t in TIERS:
            go = (old.get(sid, {}).get(t) or {}).get("ai_review") or {}
            gn = (new["results"][sid].get(t) or {}).get("ai_review") or {}
            a, b = _total(go), _total(gn)
            so, sn = go.get("severity", "?"), gn.get("severity", "?")
            row.append(f"{a} {so} → {b} {sn}")
            for k, g, tag in (("old", go, "dims_old"), ("new", gn, "dims_new")):
                if _total(g) is not None:
                    agg[t][k].append(_total(g))
                    for d in DIMS:
                        agg[t][tag][d].append(int(g.get(d) or 0))
            agg[t]["sev_old"][so] = agg[t]["sev_old"].get(so, 0) + 1
            agg[t]["sev_new"][sn] = agg[t]["sev_new"].get(sn, 0) + 1
        print(f"{sid} | " + " | ".join(row))
    print()
    for t in TIERS:
        a = agg[t]
        avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None  # noqa: E731
        print(t, "total/16 old", avg(a["old"]), "new", avg(a["new"]), "| severity old", a["sev_old"], "new", a["sev_new"])
        print("   dims new:", {d: avg(a["dims_new"][d]) for d in DIMS})
        print("   dims old:", {d: avg(a["dims_old"][d]) for d in DIMS})
    print()
    for sid in ids:
        for t in TIERS:
            g = (new["results"][sid].get(t) or {}).get("ai_review") or {}
            if g.get("severity") in ("major", "critical"):
                print(f"{sid} {t} {g['severity']}: fails={g.get('fail_modes_hit')} | {g.get('wrong_or_risky_statements')}")
    print()
    for sid in ids:
        for t in TIERS:
            c = (new["results"][sid].get(t) or {}).get("checks") or {}
            print(sid, t, {k: c.get(k) for k in ("research_status", "sources_cited", "law_named", "case_refs_removed",
                                                 "escalation_signposted", "jurisdiction_check_asked")})
    print("\nruns:", json.dumps(new["runs"], default=str))


if __name__ == "__main__":
    main()
