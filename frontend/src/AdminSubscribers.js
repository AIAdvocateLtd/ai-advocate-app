// Admin: paying subscribers list with billing controls.
import React, { useEffect, useState } from "react";
import { ExternalLink, RefreshCw } from "lucide-react";

const PLAN = { plus: "Plus", pro: "Pro", yearly: "Pro Yearly" };
const fmt = (iso) => iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "";
const btn = (color = "var(--text-dim)") => ({
  background: "transparent", border: `1px solid ${color}`, color, borderRadius: 7, padding: "5px 9px",
  fontSize: 11.5, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap",
});

function statusOf(s) {
  if (s.subscription_paused) return ["Paused", "#93c5fd"];
  if (s.cancel_at_period_end) return [`Cancels ${fmt(s.current_period_end)}`.trim(), "#fdba74"];
  if (s.subscription_status === "active") return ["Active", "#86efac"];
  return [s.subscription_status.replace("_", " "), "#fca5a5"];
}

const CONFIRM = {
  cancel_period_end: "Cancel at the end of their billing period? They keep access until then and won't be charged again.",
  undo_cancel: "Undo the scheduled cancellation? Their subscription will renew as normal.",
  cancel_refund: "Cancel NOW and refund their last payment in full? Paid features stop immediately. This can't be undone.",
  pause: "Pause billing? They won't be charged and drop to the free plan until you resume.",
  resume: "Resume billing? Their paid plan comes back immediately and billing restarts.",
};

function SubscriberRow({ s, act, busy }) {
  const [plan, setPlan] = useState("");
  const [label, color] = statusOf(s);
  const run = (action, extra) => {
    if (CONFIRM[action] && !window.confirm(`${s.email}\n\n${CONFIRM[action]}`)) return;
    if (action === "change_plan" && !window.confirm(`${s.email}\n\nChange their plan to ${PLAN[extra.plan]}? Stripe adjusts their next bill automatically.`)) return;
    act(s.id, action, extra);
  };
  return (
    <div data-testid={`subscriber-${s.id}`} style={{ borderTop: "1px solid var(--line)", padding: "12px 0", opacity: busy ? 0.5 : 1 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "baseline" }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13.5, color: "var(--text)", overflow: "hidden", textOverflow: "ellipsis" }}>{s.email}</div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>
            <strong style={{ color: "var(--gold)" }}>{PLAN[s.plan] || s.plan}</strong>{s.subscription_started_at ? ` · since ${fmt(s.subscription_started_at)}` : ""}
          </div>
        </div>
        <span data-testid={`subscriber-status-${s.id}`} style={{ fontSize: 11, color, border: `1px solid ${color}`, borderRadius: 999, padding: "2px 8px", whiteSpace: "nowrap" }}>{label}</span>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
        {s.cancel_at_period_end
          ? <button disabled={busy} style={btn()} onClick={() => run("undo_cancel")} data-testid={`sub-undo-cancel-${s.id}`}>Undo cancel</button>
          : <button disabled={busy} style={btn("#fdba74")} onClick={() => run("cancel_period_end")} data-testid={`sub-cancel-end-${s.id}`}>Cancel at period end</button>}
        <button disabled={busy} style={btn("#fca5a5")} onClick={() => run("cancel_refund")} data-testid={`sub-cancel-refund-${s.id}`}>Cancel now + refund</button>
        {s.subscription_paused
          ? <button disabled={busy} style={btn("#86efac")} onClick={() => run("resume")} data-testid={`sub-resume-${s.id}`}>Resume billing</button>
          : <button disabled={busy} style={btn("#93c5fd")} onClick={() => run("pause")} data-testid={`sub-pause-${s.id}`}>Pause billing</button>}
        <select value={plan} disabled={busy} data-testid={`sub-plan-select-${s.id}`}
          onChange={(e) => { const p = e.target.value; setPlan(""); if (p) run("change_plan", { plan: p }); }}
          style={{ ...btn(), background: "#0a0a0a" }}>
          <option value="">Change plan…</option>
          {Object.entries(PLAN).filter(([k]) => k !== s.plan).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <button disabled={busy} style={btn()} onClick={() => run("resync")} data-testid={`sub-resync-${s.id}`}><RefreshCw size={11} style={{ display: "inline", marginRight: 4 }} />Re-sync</button>
        {s.stripe_customer_id && (
          <a href={`https://dashboard.stripe.com/customers/${s.stripe_customer_id}`} target="_blank" rel="noopener noreferrer"
            style={{ ...btn(), textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }} data-testid={`sub-stripe-link-${s.id}`}>
            Stripe <ExternalLink size={11} />
          </a>
        )}
      </div>
    </div>
  );
}

export function AdminSubscribersCard({ api, toast }) {
  const [data, setData] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const load = () => api.get("/admin/subscribers").then(r => setData(r.data)).catch(() => setData({ items: [], count: 0, monthly_gbp: 0 }));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (id, action, extra = {}) => {
    setBusyId(id);
    try {
      await api.post(`/admin/subscribers/${id}/action`, { action, ...extra });
      toast(action === "resync" ? "Re-synced from Stripe" : "Done — the subscriber has been emailed");
      load();
    } catch (e) { toast(e?.response?.data?.detail || "Action failed", "error"); }
    finally { setBusyId(null); }
  };

  return (
    <div data-testid="admin-subscribers-card" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginTop: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
        <div style={{ fontWeight: 700, color: "var(--gold)" }}>Paying subscribers {data ? `(${data.count})` : ""}</div>
        {data && <div data-testid="admin-subscribers-mrr" style={{ fontSize: 12, color: "var(--text-dim)" }}>≈ £{data.monthly_gbp.toFixed(2)}/month</div>}
      </div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", margin: "4px 0 6px" }}>People paying through Stripe (free comps aren't shown). Every action emails the subscriber a short confirmation.</div>
      {!data && <div style={{ textAlign: "center", padding: 14 }}><span className="spinner" /></div>}
      {data && data.items.length === 0 && <div data-testid="admin-subscribers-empty" style={{ fontSize: 13, color: "var(--text-dim)", padding: "10px 0" }}>No paying subscribers yet.</div>}
      {data && data.items.map(s => <SubscriberRow key={s.id} s={s} act={act} busy={busyId === s.id} />)}
    </div>
  );
}
