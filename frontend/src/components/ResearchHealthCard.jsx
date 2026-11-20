import { useCallback, useEffect, useState } from "react";

const card = { background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 };
const row = { display: "flex", justifyContent: "space-between", gap: 12, padding: "6px 0", borderBottom: "1px solid var(--line)", fontSize: 13 };
const dim = { color: "var(--text-dim)", fontSize: 12 };
const btn = { fontSize: 12, padding: "4px 10px", borderRadius: 999, border: "1px solid var(--line)", background: "transparent", color: "inherit", cursor: "pointer" };
const COV = { verified: "Official source connected", official_site_search: "Official-site search only", general_only: "General information only" };
const pct = (x) => `${Math.round((x || 0) * 100)}%`;

const Coverage = ({ rows }) => (
  <div data-testid="research-coverage-list">
    {rows.map((j) => (
      <div key={j.code} style={row} data-testid={`research-coverage-${j.code}`}>
        <span>{j.name}</span>
        <span style={{ ...dim, textAlign: "right", color: j.coverage === "verified" ? "#86efac" : undefined }}>{COV[j.coverage]}</span>
      </div>
    ))}
  </div>
);

const Health = ({ h }) => (
  <div data-testid="research-health-table">
    {Object.entries(h.by_jurisdiction).map(([j, b]) => (
      <div key={j} style={row} data-testid={`research-health-${j}`}>
        <span>{j} · {b.questions} questions</span>
        <span style={dim}>official {pct(b.official_source_rate)} · AI step {pct(b.ai_discovery_rate)} · {b.tavily_calls} searches · {b.avg_research_ms} ms</span>
      </div>
    ))}
    {Object.entries(h.ai_cost_per_answer_by_tier).map(([t, c]) => (
      <div key={t} style={row} data-testid={`research-cost-${t}`}><span>AI cost per answer · {t}</span><span style={dim}>£{c.avg_cost_gbp_per_answer} ({c.answers} answers)</span></div>
    ))}
    <div style={row}><span>AI research step</span><span style={dim} data-testid="research-ai-discovery-cost">{h.ai_discovery.calls} calls · £{h.ai_discovery.cost_gbp}</span></div>
  </div>
);

export const ResearchHealthCard = ({ api }) => {
  const [h, setH] = useState(null);
  const [cov, setCov] = useState([]);
  const [changes, setChanges] = useState([]);
  const [open, setOpen] = useState(false);
  const load = useCallback(() => {
    api.get("/admin/lex-research/health").then((r) => setH(r.data)).catch(() => {});
    api.get("/admin/lex-research/coverage").then((r) => setCov(r.data.jurisdictions)).catch(() => {});
    api.get("/admin/lex-research/source-changes").then((r) => setChanges(r.data.items)).catch(() => {});
  }, [api]);
  useEffect(() => { load(); }, [load]);
  const review = (id, outcome) => api.post(`/admin/lex-research/source-changes/${id}/review`, { outcome }).finally(load);
  const toggleAi = () => api.post("/admin/lex-research/ai-discovery", { enabled: !h.ai_discovery_enabled }).finally(load);
  if (!h) return null;
  return (
    <div data-testid="research-health-card" style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontWeight: 600 }}>Lex legal research</div>
          <div style={dim}>Last 30 days · {h.source_changes_awaiting_review} source change(s) awaiting review</div>
        </div>
        <button style={btn} data-testid="research-health-toggle" onClick={() => setOpen(!open)}>{open ? "Hide" : "Details"}</button>
      </div>
      {open && (
        <div style={{ marginTop: 10 }}>
          <Health h={h} />
          <div style={{ ...row, borderBottom: "none" }}>
            <span>AI research step (only when simple checks find nothing)</span>
            <button style={btn} data-testid="research-ai-discovery-switch" onClick={toggleAi}>{h.ai_discovery_enabled ? "On — turn off" : "Off — turn on"}</button>
          </div>
          <div style={{ fontWeight: 600, margin: "12px 0 4px" }}>Coverage by country</div>
          <Coverage rows={cov} />
          <div style={{ fontWeight: 600, margin: "12px 0 4px" }}>Official wording changes</div>
          {changes.length === 0 && <div style={dim} data-testid="research-changes-empty">No changes waiting.</div>}
          {changes.map((c) => (
            <div key={c.id} style={row} data-testid={`research-change-${c.id}`}>
              <a href={c.url} target="_blank" rel="noreferrer" style={{ color: "inherit" }}>{c.label}</a>
              <span style={{ display: "flex", gap: 6 }}>
                <button style={btn} data-testid={`research-change-noimpact-${c.id}`} onClick={() => review(c.id, "no_guidance_affected")}>No guidance affected</button>
                <button style={btn} data-testid={`research-change-flag-${c.id}`} onClick={() => review(c.id, "guidance_flagged_for_lawyer")}>Flag for lawyer</button>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
