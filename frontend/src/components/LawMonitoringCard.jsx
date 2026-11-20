import { useCallback, useEffect, useState } from "react";
import { LawUpdateReview } from "./LawUpdateReview";
import { LawWatchAdminCard } from "./LawWatchAdminCard";

const card = { background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 };
const row = { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: "1px solid var(--line)", fontSize: 13 };
const dim = { color: "var(--text-dim)", fontSize: 12 };
const fmt = (iso) => (iso ? new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "never");
const errMsg = (e) => e?.response?.data?.detail || "Something went wrong.";

const Switch = ({ on, onClick, disabled, testid }) => (
  <button data-testid={testid} onClick={onClick} disabled={disabled} role="switch" aria-checked={on}
          style={{ width: 46, height: 26, borderRadius: 999, border: "none", cursor: disabled ? "not-allowed" : "pointer", position: "relative",
                   background: on ? "#22c55e" : "rgba(255,255,255,0.18)", transition: "background-color .2s", opacity: disabled ? 0.5 : 1 }}>
    <span style={{ position: "absolute", top: 3, left: on ? 23 : 3, width: 20, height: 20, borderRadius: "50%", background: "#fff", transition: "left .2s" }} />
  </button>
);

const Status = ({ ov }) => (
  <div data-testid="law-monitoring-status">
    <div style={row}><span>Last successful check</span><span data-testid="law-monitoring-last-success">{fmt(ov.last_successful_check)}</span></div>
    <div style={row}><span>Last run</span>
      <span data-testid="law-monitoring-last-run">{ov.last_run ? `${ov.last_run.day} · ${ov.last_run.result.replace(/_/g, " ")}` : "no runs yet"}</span></div>
    <div style={row}><span>Failed checks last run</span><span data-testid="law-monitoring-failures" style={{ color: ov.last_failures ? "#fca5a5" : undefined }}>{ov.last_failures || 0}</span></div>
    <div style={row}><span>Changes awaiting professional review</span><span data-testid="law-monitoring-awaiting">{ov.awaiting_review}</span></div>
    <div style={row}><span>Provisions with amendments not yet in the text</span><span data-testid="law-monitoring-pending">{ov.pending_amendments}</span></div>
    <div style={{ ...row, borderBottom: "none" }}><span>Email alerts to</span><span data-testid="law-monitoring-alerts" style={dim}>{(ov.alerts_to || []).join(", ")}</span></div>
  </div>
);

export const LawMonitoringCard = ({ api }) => {
  const [ov, setOv] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [maint, setMaint] = useState(false);
  const load = useCallback(() => api.get("/admin/law-watch/overview").then((r) => setOv(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);

  const call = async (path, body) => {
    setBusy(true); setMsg("");
    try { await api.post(path, body); } catch (e) { setMsg(errMsg(e)); } finally { setBusy(false); load(); }
  };
  const toggle = () => {
    if (ov.monitoring_on) return call("/admin/law-watch/monitoring", { enabled: false });
    const password = window.prompt("Turn on automatic daily monitoring (06:00 UK) of the 17 provisions? Changes go to the review queue and are never approved automatically.\n\nEnter your password to confirm:");
    if (password) call("/admin/law-watch/monitoring", { enabled: true, password });
  };
  const stop = () => {
    if (!ov.emergency_stop) {
      if (window.confirm("Emergency stop: immediately stop all monitoring and tracker writes?")) call("/admin/law-watch/emergency-stop", { enabled: true });
      return;
    }
    const password = window.prompt("Release the emergency stop? Enter your password:");
    if (password) call("/admin/law-watch/emergency-stop", { enabled: false, password });
  };
  if (!ov) return null;
  return (
    <div data-testid="law-monitoring-card" style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontWeight: 700, color: "var(--gold)" }}>Automatic law monitoring</div>
          <div style={dim} data-testid="law-monitoring-state">
            {ov.emergency_stop ? "Emergency stop is ON" : ov.monitoring_on ? `ON · daily at ${ov.time}` : "OFF"} · {ov.records} of 17 provisions recorded
          </div>
        </div>
        <Switch testid="law-monitoring-switch" on={ov.monitoring_on} onClick={toggle} disabled={busy || ov.emergency_stop || !ov.baseline_complete} />
      </div>
      {!ov.baseline_complete && <div style={{ ...dim, marginTop: 6 }}>The 17-law starting record is incomplete — use Maintenance tools below.</div>}
      {msg && <div data-testid="law-monitoring-error" style={{ color: "#fca5a5", fontSize: 12, marginTop: 8 }}>{msg}</div>}
      <Status ov={ov} />
      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        <button data-testid="law-monitoring-emergency-btn" onClick={stop} disabled={busy}
                style={{ background: ov.emergency_stop ? "rgba(255,255,255,0.12)" : "#ef4444", color: "#fff", border: "none", borderRadius: 8, padding: "8px 14px", fontWeight: 700, fontSize: 12.5, cursor: "pointer" }}>
          {ov.emergency_stop ? "Release emergency stop" : "Emergency stop"}
        </button>
        <button data-testid="law-monitoring-maintenance-btn" onClick={() => setMaint((m) => !m)} className="btn-ghost" style={{ fontSize: 12 }}>
          {maint ? "Hide maintenance tools" : "Maintenance tools (advanced)"}
        </button>
      </div>
      <div style={{ ...dim, marginTop: 8 }}>Detecting a change is an official-record fact; its legal meaning still needs professional review. 17 provisions do not cover all UK law.</div>
      <LawUpdateReview api={api} />
      {maint && <div style={{ marginTop: 12 }}><LawWatchAdminCard key={`${ov.monitoring_on}-${ov.emergency_stop}`} api={api} onChange={load} /></div>}
    </div>
  );
};
