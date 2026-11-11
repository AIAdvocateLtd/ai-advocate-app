// Admin: Lex's Brain — approve AI-drafted lessons that Lex follows on every answer.
import React, { useEffect, useState } from "react";

const SOURCE = { report: "Customer report", thumbs_down: "Thumbs-down", law_watch: "Law change check", manual: "Added by you", fact_pack: "Fact pack", law_note: "Law-change note" };
const btn = (bg, col) => ({ background: bg, color: col, border: "1px solid var(--gold-deep)", borderRadius: 8, padding: "5px 10px", fontSize: 12, fontWeight: 700, cursor: "pointer" });
const REC = { approve: "#86efac", correct: "#fcd34d", withhold: "#fca5a5" };

function ReviewInfo({ l }) {
  const m = l.review_meta;
  if (!m) return null;
  return (
    <div data-testid={`lesson-review-${l.id}`} style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6, lineHeight: 1.5 }}>
      <div><b style={{ color: REC[m.recommendation] }}>Suggested: {m.recommendation}</b> · {m.verification} · {m.jurisdiction}{m.effective ? ` · effective ${m.effective}` : ""} · checked {m.checked_at}{m.next_review ? ` · re-check by ${m.next_review}` : ""}</div>
      <div>{m.reason}</div>
      {m.unconfirmed_parts && <div style={{ color: "#fcd34d" }}>Not confirmed: {m.unconfirmed_parts}</div>}
      {m.source_url && <a href={m.source_url} target="_blank" rel="noreferrer" style={{ color: "var(--gold)" }}>Official source</a>}
      {l.proposed_text && <div data-testid={`lesson-proposed-${l.id}`} style={{ marginTop: 4, color: "var(--text)" }}>Proposed correction: {l.proposed_text}</div>}
      {l.reviewed_by && <div>Signed off by {l.reviewed_by} on {String(l.reviewed_at).slice(0, 10)}</div>}
    </div>
  );
}

function LessonRow({ l, onAct }) {
  return (
    <div data-testid={`lesson-${l.id}`} style={{ borderTop: "1px solid var(--line)", padding: "10px 0" }}>
      <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>{l.text}</div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
        {SOURCE[l.source] || l.source} · {l.category}{l.why ? ` · ${l.why.replace(/^Fact pack · /, "")}` : ""}
      </div>
      {l.status === "approved" && !l.used_by_lex && (
        <div data-testid={`lesson-needs-signoff-${l.id}`} style={{ fontSize: 11, color: "#fca5a5", marginTop: 4 }}>
          Not used by Lex until you sign it off{l.needs_review && l.review_reason ? ` · Review note: ${l.review_reason}` : ""}
        </div>
      )}
      <ReviewInfo l={l} />
      <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
        {l.status === "pending" && <button data-testid={`lesson-approve-${l.id}`} onClick={() => onAct(l, "approved")} style={btn("var(--gold)", "#0a0a0a")}>Approve</button>}
        {l.status === "approved" && !l.used_by_lex && <button data-testid={`lesson-signoff-${l.id}`} onClick={() => onAct(l, "signoff")} style={btn("var(--gold)", "#0a0a0a")}>Sign off</button>}
        {l.proposed_text && !l.used_by_lex && <button data-testid={`lesson-signoff-correction-${l.id}`} onClick={() => onAct(l, "signoff-correction")} style={btn("var(--gold)", "#0a0a0a")}>Use correction &amp; sign off</button>}
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
      } else if (action === "signoff" || action === "signoff-correction") {
        const fix = action === "signoff-correction";
        if (!(await confirm({ title: fix ? "Sign off the corrected wording?" : "Sign off this fact?", message: "Only sign off after checking it against the official source. Lex will then treat it as reviewed; the previous wording is kept in its history.", confirmLabel: "I've checked it — sign off" }))) return;
        await api.patch(`/admin/lex-lessons/${l.id}`, fix ? { status: "approved", text: l.proposed_text } : { status: "approved" });
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
  const live = (data?.lessons || []).filter(l => l.status === "approved" && l.used_by_lex);
  const awaiting = (data?.lessons || []).filter(l => l.status === "approved" && !l.used_by_lex);
  return (
    <div data-testid="admin-lex-lessons-card" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginTop: 14 }}>
      <div style={{ fontWeight: 700, color: "var(--gold)", marginBottom: 4 }}>Lex's Brain</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10 }}>
        Lessons Lex follows on every answer. Only lessons a person has approved or signed off are used; fact packs wait for your sign-off.
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
        <button data-testid="lesson-add-btn" onClick={add} style={btn("var(--gold)", "#0a0a0a")}>Add a lesson</button>
        <button data-testid="lesson-run-now-btn" onClick={runNow} style={btn("transparent", "var(--gold)")}>Check for new lessons now</button>
      </div>
      <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--text)", marginTop: 12 }}>Waiting for your approval ({pending.length})</div>
      {pending.length === 0 && <div style={{ fontSize: 12, color: "var(--text-muted)", padding: "6px 0" }}>Nothing to review.</div>}
      <div style={{ maxHeight: 420, overflowY: "auto" }}>{pending.map(l => <LessonRow key={l.id} l={l} onAct={act} />)}</div>
      <div data-testid="lesson-awaiting-signoff-count" style={{ fontSize: 12.5, fontWeight: 700, color: "var(--text)", marginTop: 14 }}>Awaiting your sign-off — not used by Lex ({awaiting.length})</div>
      <div style={{ maxHeight: 420, overflowY: "auto" }}>{awaiting.map(l => <LessonRow key={l.id} l={l} onAct={act} />)}</div>
      <div style={{ fontSize: 12.5, fontWeight: 700, color: "var(--text)", marginTop: 14 }}>Live lessons ({live.length})</div>
      <div style={{ maxHeight: 420, overflowY: "auto" }}>{live.map(l => <LessonRow key={l.id} l={l} onAct={act} />)}</div>
    </div>
  );
}
