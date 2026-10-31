// Conveyancing Companion: buying/selling stage tracker + help with the seller's property forms.
import React, { useEffect, useState } from "react";
import { X, Home, ArrowLeft, Check, ChevronDown, Sparkles, Trash2, Download, AlertTriangle } from "lucide-react";
import { SELL_STAGES, BUY_STAGES, FORMS, DISCLAIMER } from "@/ConveyancingData";
import { renderLexMarkdown } from "@/LexMarkdown";

const card = { background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, padding: 12, marginBottom: 8 };
const area = { width: "100%", boxSizing: "border-box", background: "rgba(0,0,0,0.35)", border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px", color: "var(--text)", fontSize: 13, fontFamily: "inherit", minHeight: 70, resize: "vertical" };

function Disclaimer() {
  return (
    <div data-testid="conv-disclaimer" style={{ display: "flex", gap: 8, fontSize: 11.5, color: "var(--text-dim)", lineHeight: 1.5, background: "rgba(247,201,72,0.06)", border: "1px solid var(--gold-deep)", borderRadius: 10, padding: "8px 10px", marginBottom: 12 }}>
      <AlertTriangle size={14} color="var(--gold)" style={{ flexShrink: 0, marginTop: 2 }} /><span>{DISCLAIMER}</span>
    </div>
  );
}

function StageItem({ s, i, done, note, onToggle, onNote }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ ...card, borderColor: done ? "var(--gold-deep)" : "var(--line)" }} data-testid={`conv-stage-${s.key}`}>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <button onClick={onToggle} aria-label={done ? "Mark not done" : "Mark done"} data-testid={`conv-stage-toggle-${s.key}`}
          style={{ width: 24, height: 24, borderRadius: 99, flexShrink: 0, cursor: "pointer", border: `1.5px solid ${done ? "var(--gold)" : "var(--line)"}`, background: done ? "var(--gold)" : "transparent", display: "grid", placeItems: "center" }}>
          {done ? <Check size={14} color="#1a1300" /> : <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{i + 1}</span>}
        </button>
        <button onClick={() => setOpen(o => !o)} data-testid={`conv-stage-open-${s.key}`} style={{ flex: 1, textAlign: "left", background: "transparent", border: "none", color: done ? "var(--text-dim)" : "var(--text)", fontSize: 13.5, fontWeight: 600, cursor: "pointer", padding: 0, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
          <span style={{ textDecoration: done ? "line-through" : "none" }}>{s.title}</span>
          <ChevronDown size={15} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s", flexShrink: 0 }} />
        </button>
      </div>
      {open && (
        <div style={{ marginTop: 10, fontSize: 13, color: "var(--text-dim)", lineHeight: 1.55 }}>
          <p style={{ margin: "0 0 8px" }}>{s.what}</p>
          <ul style={{ margin: "0 0 10px", paddingLeft: 18 }}>{s.todo.map(t => <li key={t}>{t}</li>)}</ul>
          <textarea style={area} defaultValue={note || ""} placeholder="Your notes for this stage (dates, who you spoke to…)" maxLength={2000}
            onBlur={(e) => e.target.value !== (note || "") && onNote(e.target.value)} data-testid={`conv-stage-note-${s.key}`} />
        </div>
      )}
    </div>
  );
}

function FormSection({ form, sec, saved, onSave, suggest }) {
  const [open, setOpen] = useState(false);
  const [facts, setFacts] = useState(saved?.facts || "");
  const [answer, setAnswer] = useState(saved?.answer || "");
  const [sugg, setSugg] = useState("");
  const [busy, setBusy] = useState(false);
  const id = `${form}-${sec.key}`;
  const save = (patch) => onSave({ facts, answer, ...patch });
  const ask = async () => {
    setBusy(true);
    const s = await suggest(form, sec, facts);
    if (s) setSugg(s);
    setBusy(false);
  };
  const useIt = () => {
    const m = sugg.match(/\*\*Suggested wording\*\*\s*([\s\S]*?)(\n\s*\*\*Check before|$)/);
    const text = (m ? m[1] : sugg).trim();
    setAnswer(text); save({ answer: text });
  };
  return (
    <div style={card} data-testid={`conv-form-${id}`}>
      <button onClick={() => setOpen(o => !o)} data-testid={`conv-form-open-${id}`} style={{ width: "100%", textAlign: "left", background: "transparent", border: "none", color: "var(--text)", fontSize: 13.5, fontWeight: 600, cursor: "pointer", padding: 0, display: "flex", justifyContent: "space-between", gap: 6 }}>
        <span>{sec.title}{saved?.answer ? <Check size={13} color="var(--gold)" style={{ display: "inline", marginLeft: 6 }} /> : null}</span>
        <ChevronDown size={15} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform 0.2s" }} />
      </button>
      {open && (
        <div style={{ marginTop: 10, fontSize: 13, color: "var(--text-dim)", lineHeight: 1.55 }}>
          <p style={{ margin: "0 0 4px", color: "var(--text)" }}>{sec.q}</p>
          <p style={{ margin: "0 0 10px", fontSize: 12 }}>{sec.tip}</p>
          <textarea style={area} value={facts} onChange={e => setFacts(e.target.value)} onBlur={() => save({})} maxLength={2500}
            placeholder="In your own words, what's true? e.g. 'Rear extension built 2019, building control sign-off received.'" data-testid={`conv-facts-${id}`} />
          <button onClick={ask} disabled={busy || facts.trim().length < 3} data-testid={`conv-suggest-${id}`} className="btn-gold"
            style={{ marginTop: 8, padding: "7px 12px", fontSize: 12.5, opacity: busy || facts.trim().length < 3 ? 0.6 : 1 }}>
            <Sparkles size={13} style={{ display: "inline", marginRight: 5 }} />{busy ? "Lex is writing…" : "Suggest wording"}
          </button>
          {sugg && (
            <div data-testid={`conv-suggestion-${id}`} style={{ marginTop: 10, background: "#0a0a0a", border: "1px solid var(--line)", borderRadius: 10, padding: 12 }}>
              {renderLexMarkdown(sugg)}
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>Not legal advice. Check this with your solicitor or conveyancer before using it.</div>
              <button onClick={useIt} className="btn-ghost" data-testid={`conv-use-${id}`} style={{ marginTop: 8, padding: "6px 12px", fontSize: 12 }}>Use as my answer</button>
            </div>
          )}
          <div style={{ fontSize: 12, color: "var(--text-muted)", margin: "12px 0 4px" }}>My answer for the form</div>
          <textarea style={area} value={answer} onChange={e => setAnswer(e.target.value)} onBlur={() => save({})} maxLength={3000}
            placeholder="Your final wording" data-testid={`conv-answer-${id}`} />
        </div>
      )}
    </div>
  );
}

function SellerForms({ move, update, suggest, pdfInline }) {
  const [form, setForm] = useState("TA6");
  const answers = move.form_answers || {};
  const onSave = (key) => (val) => update({ form_answers: { ...answers, [key]: val } });
  const download = () => {
    const f = FORMS[form];
    const body = f.sections.map(s => `## ${s.title}\n${s.q}\n\n${answers[`${form}-${s.key}`]?.answer || "(not answered yet)"}`).join("\n\n");
    pdfInline({ title: `${f.name} — my draft answers`, subtitle: move.address || undefined,
      body: `${body}\n\n---\n${DISCLAIMER}`, filename: `${form}-draft-answers.pdf` });
  };
  return (
    <div>
      <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {Object.keys(FORMS).map(k => (
          <button key={k} onClick={() => setForm(k)} className={form === k ? "btn-gold" : "btn-ghost"} data-testid={`conv-formtab-${k}`} style={{ flex: 1, padding: "7px 8px", fontSize: 12.5 }}>{k}</button>
        ))}
      </div>
      <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 10 }}>{FORMS[form].name}. Copy your final answers onto the official form your conveyancer sends you.</div>
      {FORMS[form].sections.map(s => <FormSection key={`${form}-${s.key}`} form={form} sec={s} saved={answers[`${form}-${s.key}`]} onSave={onSave(`${form}-${s.key}`)} suggest={suggest} />)}
      <button onClick={download} className="btn-ghost" data-testid="conv-forms-pdf" style={{ width: "100%", marginTop: 6 }}>
        <Download size={14} style={{ display: "inline", marginRight: 6 }} />Download my {form} answers (PDF)
      </button>
    </div>
  );
}

function MoveView({ move, update, remove, back, suggest, pdfInline }) {
  const [tab, setTab] = useState("stages");
  const stages = move.journey === "sell" ? SELL_STAGES : BUY_STAGES;
  const done = new Set(move.stages_done || []);
  const toggle = (k) => update({ stages_done: done.has(k) ? [...done].filter(x => x !== k) : [...done, k] });
  return (
    <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }} data-testid="conv-move-view">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <button className="btn-ghost" onClick={back} data-testid="conv-back" style={{ padding: "6px 12px" }}><ArrowLeft size={14} style={{ display: "inline", marginRight: 4 }} />My moves</button>
        <button onClick={() => window.confirm("Delete this move and all its notes?") && remove()} data-testid="conv-delete" aria-label="Delete move" style={{ background: "transparent", border: "none", color: "#fca5a5", cursor: "pointer" }}><Trash2 size={16} /></button>
      </div>
      <input defaultValue={move.address} placeholder="Property address (optional)" maxLength={200} data-testid="conv-address"
        onBlur={(e) => e.target.value !== move.address && update({ address: e.target.value })}
        style={{ ...area, minHeight: 0, marginBottom: 8, fontWeight: 600 }} />
      <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 10 }}>{move.journey === "sell" ? "Selling" : "Buying"} · {done.size} of {stages.length} stages done</div>
      <div style={{ height: 5, background: "#1a1a1a", borderRadius: 99, marginBottom: 12, overflow: "hidden" }}>
        <div style={{ width: `${(done.size / stages.length) * 100}%`, height: "100%", background: "var(--gold)", transition: "width 0.3s" }} />
      </div>
      {move.journey === "sell" && (
        <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
          {[["stages", "Stages"], ["forms", "Seller's forms"]].map(([k, l]) => (
            <button key={k} onClick={() => setTab(k)} className={tab === k ? "btn-gold" : "btn-ghost"} data-testid={`conv-tab-${k}`} style={{ flex: 1, padding: "8px 10px", fontSize: 13 }}>{l}</button>
          ))}
        </div>
      )}
      {tab === "stages"
        ? stages.map((s, i) => <StageItem key={s.key} s={s} i={i} done={done.has(s.key)} note={(move.notes || {})[s.key]}
            onToggle={() => toggle(s.key)} onNote={(v) => update({ notes: { ...(move.notes || {}), [s.key]: v } })} />)
        : <SellerForms move={move} update={update} suggest={suggest} pdfInline={pdfInline} />}
    </div>
  );
}

export default function ConveyancingModal({ api, toast, pdfInline, onUpsell, onClose }) {
  const [moves, setMoves] = useState(null);
  const [left, setLeft] = useState(null);
  const [openId, setOpenId] = useState(null);
  const load = () => api.get("/conveyancing").then(r => { setMoves(r.data.items); setLeft(r.data.suggestions_left); }).catch(() => setMoves([]));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const move = moves?.find(m => m.id === openId);

  const create = async (journey) => {
    try { const { data } = await api.post("/conveyancing", { journey }); setMoves(ms => [data, ...ms]); setOpenId(data.id); }
    catch (e) { toast(e?.response?.data?.detail || "Couldn't start", "error"); }
  };
  const update = async (patch) => {
    setMoves(ms => ms.map(m => m.id === openId ? { ...m, ...patch } : m));
    try { await api.patch(`/conveyancing/${openId}`, patch); } catch { toast("Couldn't save — check your connection", "error"); }
  };
  const remove = async () => { await api.delete(`/conveyancing/${openId}`).catch(() => {}); setOpenId(null); load(); };
  const suggest = async (form, sec, facts) => {
    try {
      const { data } = await api.post("/conveyancing/suggest", { form, section: sec.title, question: sec.q, facts });
      setLeft(data.suggestions_left);
      return data.suggestion;
    } catch (e) {
      if (e?.response?.status === 402) { toast(e.response.data.detail, "error"); onUpsell(); }
      else toast(e?.response?.data?.detail || "Lex couldn't suggest wording right now", "error");
      return null;
    }
  };

  return (
    <div className="modal-bg" data-testid="conveyancing-modal" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()} style={{ display: "flex", flexDirection: "column", maxHeight: "92%", padding: "18px 18px calc(18px + env(safe-area-inset-bottom))" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexShrink: 0 }}>
          <h3 className="font-display" style={{ margin: 0, color: "var(--gold)", display: "flex", alignItems: "center", gap: 8 }}><Home size={18} />Conveyancing Companion</h3>
          <button onClick={onClose} data-testid="conveyancing-close" aria-label="Close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={20} /></button>
        </div>
        {move ? <MoveView move={move} update={update} remove={remove} back={() => setOpenId(null)} suggest={suggest} pdfInline={pdfInline} /> : (
          <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
            <Disclaimer />
            <p style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.55, marginTop: 0 }}>Follow every stage of your sale or purchase in plain English, keep notes, and get help wording your seller's property forms. For England and Wales.</p>
            {left !== null && <div data-testid="conv-free-left" style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10 }}>Free plan: {left} of 3 Lex form suggestions left. Plus and Pro get unlimited.</div>}
            <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
              <button className="btn-gold" onClick={() => create("sell")} data-testid="conv-new-sell" style={{ flex: 1 }}>I'm selling</button>
              <button className="btn-gold" onClick={() => create("buy")} data-testid="conv-new-buy" style={{ flex: 1 }}>I'm buying</button>
            </div>
            {moves === null && <div style={{ textAlign: "center", padding: 14 }}><span className="spinner" /></div>}
            {moves?.map(m => {
              const total = (m.journey === "sell" ? SELL_STAGES : BUY_STAGES).length;
              return (
                <button key={m.id} onClick={() => setOpenId(m.id)} data-testid={`conv-move-${m.id}`} style={{ ...card, width: "100%", textAlign: "left", cursor: "pointer", color: "var(--text)" }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600 }}>{m.address || (m.journey === "sell" ? "My sale" : "My purchase")}</div>
                  <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>{m.journey === "sell" ? "Selling" : "Buying"} · {(m.stages_done || []).length} of {total} stages done</div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
