// Admin: Lex's Brain — approve AI-drafted lessons that Lex follows on every answer.
import React, { useEffect, useState } from "react";

const SOURCE = { report: "Customer report", thumbs_down: "Thumbs-down", law_watch: "Law change check", manual: "Added by you" };
const btn = (bg, col) => ({ background: bg, color: col, border: "1px solid var(--gold-deep)", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" });

function LessonRow({ l, onAct }) {
  return (
    <div data-testid={`lesson-${l.id}`} style={{ borderTop: "1px solid var(--line)", padding: "10px 0" }}>
      <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>{l.text}</div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
        {SOURCE[l.source] || l.source} · {l.category}{l.why ? ` · ${l.why}` : ""}
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
        {l.status === "pending" && <button data-testid={`lesson-approve-${l.id}`} onClick={() => onAct(l, "approved")} style={btn("var(--gold)", "#0a0a0a")}>Approve</button>}
        <button data-testid={`lesson-edit-${l.id}`} onClick={() => onAct(l, "edit")} style={btn("transparent", "var(--gold)")}>Edit</button>
        <button data-testid={`lesson-reject-${l.id}`} onClick={() => onAct(l, l.status === "pending" ? "rejected" : "delete")} style={btn("transparent", "var(--text-muted)")}>
          {l.status === "pending" ? "Reject" : "Remove"}
        </button>
      </div>
    </div>
  );
}

export function AdminLexLessonsCard({ api, toast, prompt, confirm }) {
  const [data, setData] = useState(null);
  const load = () => api.get("/admin/lex-lessons").then(r => setData(r.data)).catch(() => toast("Couldn't load Lex lessons", "error"));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (l, action) => {
    try {
      if (action === "edit") {
        const text = await prompt({ title: "Edit lesson", defaultValue: l.text, confirmLabel: "Save" });
        if (!text || !text.trim()) return;
        await api.patch(`/admin/lex-lessons/${l.id}`, { text });
      } else if (action === "delete") {
        if (!(await confirm({ title: "Remove lesson?", message: "Lex will stop following this rule straight away.", danger: true, confirmLabel: "Remove" }))) return;
        await api.delete(`/admin/lex-lessons/${l.id}`);
      }
      else await api.patch(`/admin/lex-lessons/${l.id}`, { status: action });
      load();
    } catch { toast("Couldn't update lesson", "error"); }
  };
  const add = async () => {
    const text = await prompt({ title: "Teach Lex a rule", message: "Write one clear UK legal rule Lex must always follow.", placeholder: "e.g. Small claims limit in England & Wales is £10,000", confirmLabel: "Add lesson" });
    if (!text || !text.trim()) return;
    try { await api.post("/admin/lex-lessons", { text }); toast("Lesson added — Lex is using it now"); load(); }
    catch (e) { toast(e?.response?.data?.detail || "Couldn't add lesson", "error"); }
  };
  const runNow = async () => {
    try { await api.post("/admin/lex-lessons/run-now"); toast("Checking for new lessons — refresh in a minute"); }
    catch { toast("Couldn't start the check", "error"); }
  };

  const pending = (data?.lessons || []).filter(l => l.status === "pending");
  const live = (data?.lessons || []).filter(l => l.status === "approved");
  const s = data?.stats_30d || {};
  return (
    <div data-testid="admin-lex-lessons-card" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginTop: 14 }}>
      <div style={{ fontWeight: 700, color: "var(--gold)", marginBottom: 4 }}>Lex's Brain</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10 }}>
        Lessons Lex follows on every answer. Nothing goes live until you approve it.
      </div>
      <div data-testid="lex-feedback-stats" style={{ fontSize: 12, color: "var(--text)", marginBottom: 10 }}>
        Last 30 days: <b>{s.up || 0}</b> helpful · <b>{s.down || 0}</b> not helpful · <b>{s.wrong || 0}</b> reported wrong
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
        <button data-testid="lesson-add-btn" onClick={add} style={btn("var(--gold)", "#0a0a0a")}>Add a lesson</button>
        <button data-testid="lesson-run-now-btn" onClick={runNow} style={btn("transparent", "var(--gold)")}>Check for new lessons now</button>
      </div>
      <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--text)", marginTop: 12 }}>Waiting for your approval ({pending.length})</div>
      {pending.length === 0 && <div style={{ fontSize: 12, color: "var(--text-muted)", padding: "6px 0" }}>Nothing to review.</div>}
      <div style={{ maxHeight: 420, overflowY: "auto" }}>{pending.map(l => <LessonRow key={l.id} l={l} onAct={act} />)}</div>
      <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--text)", marginTop: 14 }}>Live lessons ({live.length})</div>
      <div style={{ maxHeight: 420, overflowY: "auto" }}>{live.map(l => <LessonRow key={l.id} l={l} onAct={act} />)}</div>
    </div>
  );
}
