import { useCallback, useEffect, useState } from "react";

const card = { background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 };
const btn = (bg, fg = "#1a1300") => ({ background: bg, border: "none", color: fg, padding: "8px 14px", borderRadius: 8,
  fontSize: 12.5, fontWeight: 700, cursor: "pointer", marginRight: 8 });
const pill = (ok) => ({ fontSize: 11, padding: "2px 8px", borderRadius: 999, fontWeight: 700,
  background: ok ? "rgba(34,197,94,0.18)" : "rgba(239,68,68,0.18)", color: ok ? "#86efac" : "#fca5a5" });
const cell = { padding: "6px 8px", borderBottom: "1px solid var(--line)", textAlign: "left", verticalAlign: "top" };
const errMsg = (e, d) => e?.response?.data?.detail || d;

const ItemRow = ({ it }) => {
  const v = it.verification || {};
  const ok = it.result === "checked";
  return (
    <tr data-testid={`law-watch-item-${it.key}`}>
      <td style={cell}>{it.title || it.key}<div style={{ color: "var(--text-dim)", fontSize: 11 }}>{it.key}</div></td>
      <td style={cell}><span style={pill(ok)}>{ok ? "verified" : it.result.replace(/_/g, " ")}</span></td>
      <td style={cell}>{it.status || "—"}{it.extent ? ` · ${it.extent}` : ""}</td>
      <td style={cell}>{it.commencement ? `${it.commencement.state}${it.commencement.date ? ` (${it.commencement.date})` : " · date unknown"}` : "—"}</td>
      <td style={cell}>{v.A_metadata?.verified ? "A ✓" : "A ✗"} · {v.B_wording?.verified ? "B ✓" : "B ✗"} · C unverified · D none</td>
      <td style={cell}>{it.write === "new_version" ? "will save" : it.write === "unchanged" ? "unchanged" : "not saved"}</td>
    </tr>
  );
};

const Proposal = ({ dry }) => (
  <div style={{ marginTop: 12, overflowX: "auto" }} data-testid="law-watch-proposal">
    <div style={{ fontSize: 12, marginBottom: 6 }}>
      Proposal code <b data-testid="law-watch-proposal-code">{dry.proposal_code}</b> · {dry.summary.to_write} to save ·{" "}
      {dry.summary.held_unverified} held back · {dry.summary.unavailable} unavailable · expires {dry.expires_at?.slice(11, 16)} UTC
    </div>
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
      <thead><tr>{["Provision", "Check", "Status · extent", "Commencement", "Statuses", "Action"].map(h => <th key={h} style={cell}>{h}</th>)}</tr></thead>
      <tbody>{dry.items.map(it => <ItemRow key={it.key} it={it} />)}</tbody>
    </table>
    <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 6 }}>
      Official source facts only (legislation.gov.uk). Interpretation stays unverified; no professional review is recorded.
    </div>
  </div>
);

const Audit = ({ audit }) => (
  <div style={{ marginTop: 12, fontSize: 12 }} data-testid="law-watch-audit">
    <b>Audit history</b>
    {audit.length === 0 && <div style={{ color: "var(--text-dim)" }}>No tracker actions yet.</div>}
    {audit.map((a, i) => (
      <div key={i} style={{ color: "var(--text-dim)" }}>
        {a.at?.slice(0, 16).replace("T", " ")} · {a.actor} · {a.action.replace(/_/g, " ")}
        {a.result ? ` · ${a.result}` : ""}{a.saved_keys ? ` · ${a.saved_keys.length} saved` : ""}
      </div>
    ))}
  </div>
);

export const LawWatchAdminCard = ({ api }) => {
  const [open, setOpen] = useState(false);
  const [st, setSt] = useState(null);
  const [dry, setDry] = useState(null);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    try { setSt((await api.get("/admin/law-watch/status")).data); } catch (e) { setErr(errMsg(e, "Couldn't load tracker status.")); }
  }, [api]);
  useEffect(() => { if (open) load(); }, [open, load]);

  const act = async (name, fn) => {
    setBusy(name); setErr("");
    try { await fn(); } catch (e) { setErr(errMsg(e, "Action failed.")); } finally { setBusy(""); load(); }
  };
  const runDry = () => act("dry", async () => { setRes(null); setDry((await api.post("/admin/law-watch/dry-run", { scope: "nine_provisions" })).data); });
  const toggle = (enabled) => act("switch", async () => { await api.post("/admin/law-watch/switch", { enabled }); });
  const apply = () => {
    if (!window.confirm(`Save ${dry.summary.to_write} verified provision record(s) with proposal ${dry.proposal_code}?`)) return;
    act("apply", async () => { setRes((await api.post("/admin/law-watch/apply", { token: dry.token })).data); setDry(null); });
  };
  const on = st?.enabled;

  return (
    <div data-testid="admin-law-watch-card" style={card}>
      <button onClick={() => setOpen(o => !o)} data-testid="admin-law-watch-toggle"
              style={{ display: "flex", justifyContent: "space-between", width: "100%", background: "transparent", border: "none", padding: 0, cursor: "pointer", color: "var(--gold)" }}>
        <span style={{ fontWeight: 700, fontSize: 14 }}>
          ⚖ Law tracker {st && <span data-testid="law-watch-write-state" style={{ ...pill(!on), marginLeft: 8 }}>{on ? `writes ON until ${st.until.slice(11, 16)} UTC` : "writes OFF"}</span>}
        </span>
        <span style={{ color: "var(--text-dim)" }}>{open ? "▾" : "▸"}</span>
      </button>
      {open && st && (
        <div style={{ marginTop: 12, fontSize: 12 }}>
          <div style={{ color: "var(--text-dim)", marginBottom: 10 }} data-testid="law-watch-status">
            {st.records} provision records · {st.history_versions} versions · emergency stop {st.kill_switch ? "ON" : "off"} ·
            scheduled monitoring off · customer notifications off
          </div>
          <button data-testid="law-watch-dry-run-btn" onClick={runDry} disabled={!!busy} style={btn("var(--gold)")}>
            {busy === "dry" ? "Checking legislation.gov.uk…" : "Run dry run (nine provisions)"}
          </button>
          {on
            ? <button data-testid="law-watch-writes-off-btn" onClick={() => toggle(false)} disabled={!!busy} style={btn("#ef4444", "#fff")}>Turn writes off now</button>
            : <button data-testid="law-watch-writes-on-btn" onClick={() => toggle(true)} disabled={!!busy || st.kill_switch} style={btn("rgba(255,255,255,0.12)", "var(--text)")}>Turn writes on (30 min)</button>}
          {dry && <button data-testid="law-watch-apply-btn" onClick={apply} disabled={!!busy || !on || !dry.summary.to_write} style={btn("#22c55e")}>
            {busy === "apply" ? "Saving…" : `Save ${dry.summary.to_write} verified records`}
          </button>}
          {err && <div data-testid="law-watch-error" style={{ color: "#fca5a5", marginTop: 8 }}>{err}</div>}
          {res && <div data-testid="law-watch-result" style={{ color: "#86efac", marginTop: 8 }}>
            Saved {res.saved_keys.length} record(s) · run {res.id.slice(0, 8)} · {res.summary.unchanged} unchanged · {res.summary.unavailable} unavailable
          </div>}
          {dry && <Proposal dry={dry} />}
          <Audit audit={st.audit} />
        </div>
      )}
    </div>
  );
};
