// Case-file countdown card (key dates + Lex-written preparation checklist)
// and the Settings toggle for deadline reminder emails.
import React, { useEffect, useState } from "react";
import { CalendarClock, CheckSquare, Square, Plus, Sparkles, X } from "lucide-react";

const card = { background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 16, marginBottom: 14 };

const ukDate = (iso) => new Date(iso).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "long", year: "numeric", timeZone: "Europe/London" });

export const daysUntil = (iso) => {
  const toUk = (d) => new Date(d.toLocaleDateString("en-CA", { timeZone: "Europe/London" }));
  return Math.round((toUk(new Date(iso)) - toUk(new Date())) / 86400000);
};

const countdownLabel = (n) => (n < 0 ? `${Math.abs(n)} day${n === -1 ? "" : "s"} ago` : n === 0 ? "Today" : n === 1 ? "Tomorrow" : `${n} days to go`);

function Checklist({ date, api, toast, onChange }) {
  const [busy, setBusy] = useState(false);
  const items = date.checklist || [];
  const generate = async () => {
    setBusy(true);
    try { const { data } = await api.post(`/reminders/${date.id}/checklist`); onChange(data); }
    catch (e) { toast(e?.response?.data?.detail || "Couldn't create the checklist", "error"); }
    finally { setBusy(false); }
  };
  const toggle = async (it) => {
    onChange({ ...date, checklist: items.map(x => x.id === it.id ? { ...x, done: !x.done } : x) });
    try { await api.patch(`/reminders/${date.id}/checklist/${it.id}`, { done: !it.done }); }
    catch (e) { onChange(date); toast("Couldn't save — try again", "error"); }
  };
  if (!items.length) {
    return (
      <button data-testid="generate-checklist-btn" onClick={generate} disabled={busy} className="btn-ghost"
              style={{ width: "100%", marginTop: 12, fontSize: 13, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6, color: "var(--gold)", border: "1px solid var(--gold-deep)" }}>
        {busy ? <><span className="spinner" /> Lex is writing your checklist…</> : <><Sparkles size={14} /> Create a document checklist with Lex</>}
      </button>
    );
  }
  const done = items.filter(x => x.done).length;
  return (
    <div data-testid="key-date-checklist" style={{ marginTop: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>
        <span>Preparation checklist</span>
        <span data-testid="checklist-progress" style={{ color: "var(--gold)", fontWeight: 700 }}>{done}/{items.length} ready</span>
      </div>
      <div style={{ height: 4, background: "var(--line)", borderRadius: 2, marginBottom: 8 }}>
        <div style={{ width: `${(done / items.length) * 100}%`, height: 4, background: "var(--gold)", borderRadius: 2, transition: "width 250ms ease" }} />
      </div>
      {items.map(it => (
        <button key={it.id} data-testid={`checklist-item-${it.id}`} onClick={() => toggle(it)}
                style={{ display: "flex", gap: 8, alignItems: "flex-start", width: "100%", textAlign: "left", background: "transparent", border: "none", color: it.done ? "var(--text-muted)" : "var(--text)", padding: "6px 0", cursor: "pointer", fontSize: 13, textDecoration: it.done ? "line-through" : "none" }}>
          {it.done ? <CheckSquare size={16} color="var(--gold)" style={{ flexShrink: 0, marginTop: 1 }} /> : <Square size={16} style={{ flexShrink: 0, marginTop: 1 }} />}
          <span>{it.text}</span>
        </button>
      ))}
      <div style={{ fontSize: 10.5, color: "var(--text-muted)", marginTop: 6 }}>General legal information, not legal advice. Check official guidance for your exact requirements.</div>
    </div>
  );
}

function AddKeyDateForm({ caseId, api, toast, onSaved, onCancel }) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!title.trim() || !date) { toast("Add a name and a date", "error"); return; }
    setBusy(true);
    try {
      await api.post("/reminders", { case_id: caseId, title: title.trim(), due_at: new Date(`${date}T09:00:00`).toISOString(), kind: "deadline" });
      toast("Key date added — we'll email you 7, 3 and 1 day before", "success");
      onSaved();
    } catch (e) { toast(e?.response?.data?.detail || "Couldn't save the date", "error"); }
    finally { setBusy(false); }
  };
  return (
    <div data-testid="add-key-date-form" style={{ marginTop: 10 }}>
      <input className="input" data-testid="key-date-title-input" placeholder="e.g. ILR appointment" value={title} onChange={e => setTitle(e.target.value)} style={{ marginBottom: 8 }} />
      <input className="input" type="date" data-testid="key-date-date-input" value={date} onChange={e => setDate(e.target.value)} style={{ marginBottom: 8 }} />
      <div className="flex gap-2">
        <button className="btn-gold" data-testid="key-date-save-btn" disabled={busy} onClick={save} style={{ flex: 1 }}>{busy ? <span className="spinner" /> : "Save date"}</button>
        <button className="btn-ghost" data-testid="key-date-cancel-btn" onClick={onCancel} style={{ flex: 1 }}>Cancel</button>
      </div>
    </div>
  );
}

export function CaseKeyDates({ caseId, api, toast }) {
  const [dates, setDates] = useState([]);
  const [adding, setAdding] = useState(false);
  const load = () => api.get(`/cases/${caseId}/key-dates`).then(r => setDates(r.data.key_dates || [])).catch(() => {});
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [caseId]);

  const upcoming = dates.filter(d => daysUntil(d.due_at) >= 0);
  const main = upcoming[0] || dates[dates.length - 1];
  const others = dates.filter(d => d !== main);
  const replace = (nd) => setDates(ds => ds.map(d => d.id === nd.id ? nd : d));
  const dismiss = async (d) => {
    try { await api.patch(`/reminders/${d.id}?status=done`); setDates(ds => ds.filter(x => x.id !== d.id)); toast("Marked as done", "success"); }
    catch (e) { toast("Couldn't update", "error"); }
  };

  return (
    <div data-testid="case-key-dates" style={card}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--gold)", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase" }}>
          <CalendarClock size={14} /> Key dates
        </div>
        {!adding && (
          <button data-testid="add-key-date-btn" onClick={() => setAdding(true)} className="btn-ghost"
                  style={{ fontSize: 12, padding: "4px 10px", display: "inline-flex", alignItems: "center", gap: 4 }}>
            <Plus size={13} /> Add key date
          </button>
        )}
      </div>
      {adding && <AddKeyDateForm caseId={caseId} api={api} toast={toast} onSaved={() => { setAdding(false); load(); }} onCancel={() => setAdding(false)} />}
      {!main && !adding && (
        <p data-testid="key-dates-empty" style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 8 }}>
          No dates yet. Add an appointment, hearing or deadline and we'll count down to it and email you before it's due.
        </p>
      )}
      {main && (
        <div data-testid="countdown-card" style={{ marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
            <div>
              <div data-testid="countdown-days" className="brand-font" style={{ fontSize: 30, fontWeight: 700, color: daysUntil(main.due_at) <= 3 ? "#fca5a5" : "var(--gold)", lineHeight: 1.1 }}>
                {countdownLabel(daysUntil(main.due_at))}
              </div>
              <div data-testid="countdown-title" style={{ fontSize: 15, fontWeight: 600, color: "var(--text)", marginTop: 4 }}>{main.title}</div>
              <div data-testid="countdown-date" style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>{ukDate(main.due_at)}</div>
            </div>
            <button data-testid="countdown-done-btn" onClick={() => dismiss(main)} title="Mark as done" aria-label="Mark as done"
                    style={{ background: "transparent", border: "1px solid var(--line)", borderRadius: 8, color: "var(--text-muted)", padding: 6, cursor: "pointer" }}>
              <X size={14} />
            </button>
          </div>
          <Checklist date={main} api={api} toast={toast} onChange={replace} />
        </div>
      )}
      {others.length > 0 && (
        <div data-testid="other-key-dates" style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 10 }}>
          {others.map(d => (
            <div key={d.id} data-testid={`key-date-${d.id}`} style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, padding: "4px 0", color: "var(--text)" }}>
              <span>{d.title}</span>
              <span style={{ color: "var(--text-muted)" }}>{countdownLabel(daysUntil(d.due_at))}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function DeadlineEmailsRow({ user, api, toast, onUpdate }) {
  const [on, setOn] = useState(user?.deadline_emails_enabled !== false);
  const toggle = async () => {
    const next = !on;
    setOn(next);
    try {
      const { data } = await api.patch("/auth/preferences", { deadline_emails_enabled: next });
      onUpdate && onUpdate(data);
      toast(next ? "Deadline reminder emails on" : "Deadline reminder emails off", "success");
    } catch (e) { setOn(!next); toast("Couldn't save — try again", "error"); }
  };
  return (
    <div data-testid="deadline-emails-row" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, padding: 14, marginBottom: 12, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <div style={{ flex: 1, paddingRight: 10 }}>
        <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 600 }}>Deadline reminder emails</div>
        <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 3, lineHeight: 1.45 }}>
          We'll email you 7, 3 and 1 day before any saved deadline or key date.
        </div>
      </div>
      <button onClick={toggle} data-testid="deadline-emails-toggle" aria-pressed={on}
              style={{ width: 44, height: 24, borderRadius: 12, background: on ? "var(--gold)" : "var(--line)", border: "none", cursor: "pointer", position: "relative", flexShrink: 0 }}>
        <span style={{ position: "absolute", top: 2, left: on ? 22 : 2, width: 20, height: 20, borderRadius: 10, background: "#fff", transition: "left 0.18s ease" }} />
      </button>
    </div>
  );
}
