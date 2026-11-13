// Admin: Stage 3 fair use & spending — thresholds, Free safety brake, flagged accounts, exemptions.
import React, { useEffect, useState } from "react";

const card = { background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginTop: 14 };
const btn = (bg, col) => ({ background: bg, color: col, border: "1px solid var(--gold-deep)", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" });
const muted = { fontSize: 12, color: "var(--text-muted)" };
const gbp = n => `£${Number(n || 0).toFixed(2)}`;
const SWITCHES = [
  ["login_limits_enabled", "Login protection"], ["abuse_guards_enabled", "Repeat / burst protection"],
  ["free_lifetime_enabled", "Free: 2 lifetime questions"], ["pass_limits_enabled", "Pass allowances"],
  ["spend_guard_enabled", "Paid spending safeguards"], ["site_brake_enabled", "Free site-wide brake"],
];

function BrakeRow({ b, onBrake }) {
  return (
    <div data-testid="fair-use-brake" style={{ ...muted, margin: "8px 0" }}>
      Free brake: <b style={{ color: b.paused ? "var(--danger)" : "var(--gold)" }}>{b.paused ? "PAUSED" : "running"}</b>
      {" "}· estimated today {gbp(b.spent_today_gbp)} · alert {gbp(b.alert_at_gbp)} · brake {gbp(b.brake_at_gbp)}
      <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
        <button data-testid="fair-use-brake-pause" style={btn("transparent", "var(--gold)")} onClick={() => onBrake("pause")}>Pause Free now</button>
        <button data-testid="fair-use-brake-resume" style={btn("transparent", "var(--gold)")} onClick={() => onBrake("resume")}>Resume</button>
        <button data-testid="fair-use-brake-override" style={btn("transparent", "var(--gold)")} onClick={() => onBrake("override")}>Override for today</button>
      </div>
    </div>
  );
}

function ThresholdRow({ tier, th, onEdit }) {
  return (
    <div data-testid={`fair-use-threshold-${tier}`} style={{ ...muted, display: "flex", justifyContent: "space-between", padding: "4px 0" }}>
      <span><span style={{ textTransform: "capitalize" }}>{tier}</span>: flag {gbp(th.flag)} · cool-down {gbp(th.cooldown)} / day · monthly review {gbp(th.monthly_review)}</span>
      <button data-testid={`fair-use-edit-${tier}`} style={btn("transparent", "var(--gold)")} onClick={() => onEdit(tier, th)}>Edit</button>
    </div>
  );
}

function FlagRow({ f, onLift }) {
  const active = ["cooldown", "paused"].includes(f.level) && !f.lifted && (f.until || "") > new Date().toISOString();
  return (
    <div data-testid="fair-use-flag-row" style={{ ...muted, borderTop: "1px solid var(--line)", padding: "6px 0", display: "flex", justifyContent: "space-between", gap: 8 }}>
      <span>{f.email} ({f.tier}) · {f.level.replace("_", " ")} · {gbp(f.spent_gbp)} · {f.day}{f.lifted ? " · lifted" : ""}</span>
      {active && <button data-testid={`fair-use-lift-${f.user_id}`} style={btn("var(--gold)", "#0a0a0a")} onClick={() => onLift(f.user_id)}>Lift</button>}
    </div>
  );
}

export function AdminFairUseCard({ api, toast, prompt, confirm }) {
  const [d, setD] = useState(null);
  const load = () => api.get("/admin/fair-use").then(r => setD(r.data)).catch(() => toast("Couldn't load fair-use settings", "error"));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const run = async (fn, ok) => { try { await fn(); toast(ok); load(); } catch (e) { toast(e?.response?.data?.detail || "Couldn't save", "error"); } };
  const save = patch => run(() => api.put("/admin/fair-use/settings", patch), "Saved");
  const editTier = async (tier, th) => {
    const v = await prompt({ title: `${tier} thresholds (£)`, message: "flag, cool-down, monthly review", defaultValue: `${th.flag}, ${th.cooldown}, ${th.monthly_review}`, confirmLabel: "Save" });
    const n = (v || "").split(",").map(x => parseFloat(x));
    if (n.length !== 3 || n.some(isNaN)) return;
    save({ thresholds: { [tier]: { flag: n[0], cooldown: n[1], monthly_review: n[2] } } });
  };
  const setEffective = async () => {
    const v = await prompt({ title: "Paid limits start date", message: "Only set this after the 30-day notice email has been sent. Limits start at midnight UK time. Format YYYY-MM-DD. Leave blank to keep paid limits off.", defaultValue: (d.settings.paid_limits_effective_at || "").slice(0, 10), confirmLabel: "Save" });
    if (v === null || v === undefined) return;
    const day = v.trim();
    const parsed = new Date(`${day}T00:00:00Z`);
    if (day && (!/^\d{4}-\d{2}-\d{2}$/.test(day) || isNaN(parsed) || parsed.toISOString().slice(0, 10) !== day)) {
      toast("Please enter a real date as YYYY-MM-DD", "error"); return;
    }
    if (day && day <= new Date().toISOString().slice(0, 10) &&
        !(await confirm({ title: "Start paid limits now?", message: "This date is today or in the past, so paid allowances switch on immediately.", danger: true, confirmLabel: "Start now" }))) return;
    save({ paid_limits_effective_at: day || null });
  };
  const exempt = async () => {
    const email = await prompt({ title: "Exempt a customer", message: "Their account skips fair-use limits and safeguards.", placeholder: "name@example.com", confirmLabel: "Exempt" });
    if (email) run(() => api.post("/admin/fair-use/exempt", { email, exempt: true }), "Customer exempted");
  };
  if (!d) return null;
  const s = d.settings;
  return (
    <div data-testid="admin-fair-use-card" style={card}>
      <div style={{ fontWeight: 700, color: "var(--gold)", marginBottom: 4 }}>Fair use &amp; spending</div>
      <div style={{ ...muted, marginBottom: 8 }}>{d.estimate_note} Estimated this month: <b data-testid="fair-use-month">{gbp(d.estimated_month_gbp)}</b></div>
      <BrakeRow b={d.brake} onBrake={a => run(() => api.post("/admin/fair-use/brake", { action: a }), "Brake updated")} />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "8px 0" }}>
        {SWITCHES.map(([k, label]) => (
          <button key={k} data-testid={`fair-use-switch-${k}`} style={btn(s[k] ? "var(--gold)" : "transparent", s[k] ? "#0a0a0a" : "var(--text-muted)")}
                  onClick={() => save({ [k]: !s[k] })}>{label}: {s[k] ? "On" : "Off"}</button>
        ))}
      </div>
      <div style={{ ...muted, margin: "6px 0" }}>
        Paid allowances start: <b data-testid="fair-use-effective">{s.paid_limits_effective_at ? s.paid_limits_effective_at.slice(0, 10) : "not set (current terms apply)"}</b>{" "}
        <button data-testid="fair-use-set-effective" style={btn("transparent", "var(--gold)")} onClick={setEffective}>Set date</button>
      </div>
      {Object.entries(s.thresholds).map(([t, th]) => <ThresholdRow key={t} tier={t} th={th} onEdit={editTier} />)}
      <div style={{ fontWeight: 700, color: "var(--text)", fontSize: 13, marginTop: 10 }}>Flagged accounts (7 days)</div>
      {d.flags.length ? d.flags.map((f, i) => <FlagRow key={i} f={f} onLift={uid => run(() => api.post("/admin/fair-use/lift", { user_id: uid }), "Cool-down lifted")} />)
        : <div style={muted}>None — no unusual spending.</div>}
      <div style={{ ...muted, marginTop: 10 }}>
        Exempt: {d.exempt_users.length ? d.exempt_users.map(u => (
          <span key={u.id} style={{ marginRight: 8 }}>{u.email}{" "}
            <button data-testid={`fair-use-unexempt-${u.id}`} style={btn("transparent", "var(--text-muted)")}
                    onClick={() => run(() => api.post("/admin/fair-use/exempt", { user_id: u.id, exempt: false }), "Exemption removed")}>Remove</button>
          </span>)) : "none"}{" "}
        <button data-testid="fair-use-exempt-btn" style={btn("transparent", "var(--gold)")} onClick={exempt}>Exempt a customer</button>
      </div>
    </div>
  );
}
