// Will Writer — guided questions → Lex drafts a will → PDF / email / share. Plus & Pro only.
import React, { useEffect, useState } from "react";
import { X, ScrollText, Plus, Trash2, AlertTriangle, Pencil } from "lucide-react";
import { ShareActionsRow } from "@/ShareActions";

const JURISDICTIONS = [
  { v: "ew", label: "England & Wales" }, { v: "scotland", label: "Scotland" },
  { v: "ni", label: "Northern Ireland" }, { v: "other", label: "Another country" },
];

const SECTIONS = [
  { title: "About you", fields: [
    { k: "full_name", label: "Your full legal name *" },
    { k: "address", label: "Your address", area: true },
    { k: "date_of_birth", label: "Date of birth", type: "date" },
    { k: "marital_status", label: "Relationship status", options: ["Single", "Married", "Civil partnership", "Living with a partner", "Separated", "Divorced", "Widowed"] },
    { k: "children", label: "Children (names and ages)", area: true, ph: "e.g. Amira (12), Yusuf (8)" },
  ] },
  { title: "Executors (people who carry out your will)", fields: [
    { k: "executors", label: "Executors — names and relationship to you *", area: true, ph: "e.g. My wife, Sara Malick, and my brother, Adam Malick" },
    { k: "backup_executors", label: "Backup executor if they can't act", area: true },
  ] },
  { title: "Children under 18", fields: [
    { k: "guardians", label: "Guardians for children under 18 (optional)", area: true },
  ] },
  { title: "Who gets what", fields: [
    { k: "specific_gifts", label: "Specific gifts (optional)", area: true, ph: "e.g. My watch to my son Yusuf; £1,000 to the British Heart Foundation" },
    { k: "residuary", label: "Who gets everything else (the rest of your estate) *", area: true, ph: "e.g. My wife Sara; if she dies before me, split equally between my children" },
    { k: "backup_beneficiary", label: "Backup beneficiary if they die before you", area: true },
  ] },
  { title: "Your wishes (optional)", fields: [
    { k: "funeral_wishes", label: "Funeral wishes", area: true },
    { k: "pets", label: "Care of pets", area: true },
    { k: "digital_assets", label: "Online accounts and digital items", area: true },
    { k: "other_wishes", label: "Anything else", area: true },
  ] },
];

const COMPLEXITY = [
  ["owns_business", "I own a business or shares in a private company"],
  ["property_abroad", "I own property or assets outside the UK"],
  ["trust_needed", "I want a trust (e.g. for children or a vulnerable beneficiary)"],
  ["estate_over_iht", "My estate may be over the inheritance tax threshold"],
  ["blended_family", "I have children from a previous relationship"],
  ["disinherit", "I want to leave out a spouse, partner or child"],
];

const label = { fontSize: 12, color: "var(--text-muted)", marginBottom: 4, display: "block" };

function WillForm({ will, onSaved, api, toast }) {
  const [jur, setJur] = useState(will?.jurisdiction || "ew");
  const [country, setCountry] = useState(will?.country || "");
  const [a, setA] = useState(will?.answers || { complexity: {} });
  const [busy, setBusy] = useState("");
  const set = (k, v) => setA(p => ({ ...p, [k]: v }));
  const setFlag = (k) => setA(p => ({ ...p, complexity: { ...(p.complexity || {}), [k]: !(p.complexity || {})[k] } }));

  const save = async (andGenerate) => {
    if (jur === "other" && !country.trim()) { toast("Tell us which country", "error"); return; }
    setBusy(andGenerate ? "gen" : "save");
    try {
      const { data } = await api.post("/wills", { id: will?.id, jurisdiction: jur, country, answers: a });
      if (!andGenerate) { toast(data.draft_stale ? "Saved — redraft to update your will" : "Draft saved", "success"); onSaved(data, false); return; }
      const g = await api.post(`/wills/${data.id}/generate`);
      toast("Your will has been drafted", "success");
      onSaved(g.data, true);
    } catch (e) { toast(e?.response?.data?.detail || "Something went wrong — try again", "error"); }
    finally { setBusy(""); }
  };

  return (
    <div data-testid="will-form">
      <span style={label}>Where do you live? (your will follows the law of this place)</span>
      <select className="input" data-testid="will-jurisdiction" value={jur} onChange={e => setJur(e.target.value)} style={{ marginBottom: 8 }}>
        {JURISDICTIONS.map(j => <option key={j.v} value={j.v}>{j.label}</option>)}
      </select>
      {jur === "other" && (
        <input className="input" data-testid="will-country" placeholder="Which country?" value={country} onChange={e => setCountry(e.target.value)} style={{ marginBottom: 8 }} />
      )}
      {jur === "other" && (
        <div data-testid="will-other-country-note" style={{ fontSize: 12, color: "#fcd34d", background: "rgba(252,211,77,0.08)", border: "1px solid rgba(252,211,77,0.3)", borderRadius: 8, padding: 10, marginBottom: 8 }}>
          Will rules differ between countries. Lex will prepare a draft, but it must be checked by a local lawyer or notary before you sign it.
        </div>
      )}
      {SECTIONS.map(s => (
        <div key={s.title} style={{ marginTop: 16 }}>
          <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>{s.title}</div>
          {s.fields.map(f => (
            <div key={f.k} style={{ marginBottom: 10 }}>
              <span style={label}>{f.label}</span>
              {f.options ? (
                <select className="input" data-testid={`will-${f.k}`} value={a[f.k] || ""} onChange={e => set(f.k, e.target.value)}>
                  <option value="">Choose…</option>{f.options.map(o => <option key={o}>{o}</option>)}
                </select>
              ) : f.area ? (
                <textarea className="input" data-testid={`will-${f.k}`} rows={2} placeholder={f.ph || ""} value={a[f.k] || ""} onChange={e => set(f.k, e.target.value)} />
              ) : (
                <input className="input" data-testid={`will-${f.k}`} type={f.type || "text"} placeholder={f.ph || ""} value={a[f.k] || ""} onChange={e => set(f.k, e.target.value)} />
              )}
            </div>
          ))}
        </div>
      ))}
      <div style={{ marginTop: 16, color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>Does any of this apply to you?</div>
      {COMPLEXITY.map(([k, txt]) => (
        <label key={k} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, color: "var(--text)", marginBottom: 8, cursor: "pointer" }}>
          <input type="checkbox" data-testid={`will-flag-${k}`} checked={!!(a.complexity || {})[k]} onChange={() => setFlag(k)} style={{ marginTop: 3 }} />
          {txt}
        </label>
      ))}
      <div className="flex gap-2" style={{ marginTop: 16 }}>
        <button className="btn-ghost" data-testid="will-save-btn" disabled={!!busy} onClick={() => save(false)} style={{ flex: 1 }}>{busy === "save" ? <span className="spinner" /> : "Save draft"}</button>
        <button className="btn-gold" data-testid="will-generate-btn" disabled={!!busy} onClick={() => save(true)} style={{ flex: 1.4 }}>
          {busy === "gen" ? <><span className="spinner" /> Lex is drafting…</> : "Draft my will with Lex"}
        </button>
      </div>
    </div>
  );
}

function WillResult({ will, api, toast, onEdit, onDelete }) {
  const downloadPdf = async () => {
    const r = await api.get(`/wills/${will.id}/pdf`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const el = document.createElement("a");
    el.href = url; el.download = `${(will.title || "Will").replace(/[^A-Za-z0-9]+/g, "_")}.pdf`;
    document.body.appendChild(el); el.click(); el.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  };
  return (
    <div data-testid="will-result">
      {will.draft_stale && (
        <div data-testid="will-stale-warning" style={{ background: "rgba(252,211,77,0.08)", border: "1px solid rgba(252,211,77,0.4)", borderRadius: 10, padding: 12, marginBottom: 12, fontSize: 12.5, color: "#fcd34d" }}>
          You've changed your answers since this will was drafted. Tap <strong>Edit answers</strong> then <strong>Draft my will with Lex</strong> to update it before printing.
        </div>
      )}
      {(will.complexity_warnings || []).length > 0 && (
        <div data-testid="will-complexity-warning" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.4)", borderRadius: 10, padding: 12, marginBottom: 12, fontSize: 12.5, color: "#fca5a5" }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", fontWeight: 700, marginBottom: 4 }}><AlertTriangle size={14} /> We strongly recommend a solicitor checks this will</div>
          {will.complexity_warnings.map(w => <div key={w}>• {w}</div>)}
        </div>
      )}
      <div data-testid="will-text" style={{ whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.6, color: "var(--text)", background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 14, maxHeight: "45vh", overflowY: "auto" }}>
        {will.full_text}
      </div>
      <div style={{ fontSize: 11.5, color: "#fcd34d", marginTop: 8 }}>
        This will is not valid until it is printed, signed and witnessed exactly as described at the end. Do not sign it electronically.
      </div>
      <ShareActionsRow text={will.full_text} title={will.title || "My will"} api={api} toast={toast} onPdf={downloadPdf} testIdPrefix="will" />
      <div className="flex gap-2" style={{ marginTop: 12 }}>
        <button className="btn-ghost" data-testid="will-edit-btn" onClick={onEdit} style={{ flex: 1, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6 }}><Pencil size={14} /> Edit answers</button>
        <button className="btn-ghost" data-testid="will-delete-btn" onClick={onDelete} style={{ flex: 0.6, color: "#fca5a5" }}><Trash2 size={14} /></button>
      </div>
      <div style={{ fontSize: 10.5, color: "var(--text-muted)", marginTop: 10 }}>General legal information, not legal advice. AI Advocate is not a law firm.</div>
    </div>
  );
}

export default function WillWriterModal({ api, toast, onUpsell, onClose }) {
  const [view, setView] = useState("list");
  const [wills, setWills] = useState([]);
  const [current, setCurrent] = useState(null);
  const [locked, setLocked] = useState(false);

  const load = () => api.get("/wills").then(r => setWills(r.data.wills || [])).catch(e => { if (e?.response?.status === 402) setLocked(true); });
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const open = async (w) => {
    try {
      const { data } = await api.get(`/wills/${w.id}`);
      setCurrent(data); setView(data.full_text ? "result" : "form");
    } catch { toast("Couldn't open that will", "error"); }
  };
  const remove = async () => {
    if (!window.confirm("Delete this will draft? This can't be undone.")) return;
    try { await api.delete(`/wills/${current.id}`); toast("Will deleted", "success"); setCurrent(null); setView("list"); load(); }
    catch { toast("Couldn't delete", "error"); }
  };

  return (
    <div className="modal-bg" data-testid="will-writer-modal">
      <div className="modal-card" style={{ padding: 0, display: "flex", flexDirection: "column", maxHeight: "92%", maxWidth: 720 }}>
        <div className="flex items-center justify-between" style={{ padding: "18px 20px 12px", borderBottom: "1px solid var(--line)" }}>
          <div>
            <h2 className="brand-font gold" style={{ fontSize: 20, margin: 0, display: "flex", alignItems: "center", gap: 8 }}><ScrollText size={20} /> Will Writer</h2>
            <div style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 2 }}>Answer a few questions · Lex drafts your will · print, sign &amp; witness</div>
          </div>
          <button onClick={onClose} data-testid="will-close" aria-label="Close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        <div style={{ padding: 20, overflowY: "auto", flex: 1 }}>
          {locked ? (
            <div data-testid="will-locked" style={{ textAlign: "center", padding: 20 }}>
              <p style={{ color: "var(--text)", marginBottom: 12 }}>Will Writer is available on Plus and Pro.</p>
              <button className="btn-gold" data-testid="will-upgrade-btn" onClick={onUpsell}>See plans</button>
            </div>
          ) : view === "list" ? (
            <div data-testid="will-list">
              <button className="btn-gold" data-testid="will-new-btn" onClick={() => { setCurrent(null); setView("form"); }} style={{ width: "100%", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6 }}><Plus size={16} /> Start a new will</button>
              {wills.length === 0 && <p style={{ fontSize: 12.5, color: "var(--text-muted)", marginTop: 14 }}>Your saved wills will appear here so you can update them any time.</p>}
              {wills.map(w => (
                <button key={w.id} data-testid={`will-item-${w.id}`} onClick={() => open(w)}
                        style={{ display: "block", width: "100%", textAlign: "left", marginTop: 10, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 12, color: "var(--text)", cursor: "pointer" }}>
                  <div style={{ fontWeight: 600 }}>{w.title}</div>
                  <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>{w.has_draft ? "Drafted" : "In progress"} · updated {new Date(w.updated_at).toLocaleDateString("en-GB")}</div>
                </button>
              ))}
            </div>
          ) : view === "form" ? (
            <>
              <button className="btn-ghost" data-testid="will-back-btn" onClick={() => { setView("list"); load(); }} style={{ fontSize: 12, marginBottom: 12 }}>← My wills</button>
              <WillForm will={current} api={api} toast={toast} onSaved={(w, drafted) => { setCurrent(w); if (drafted) setView("result"); }} />
            </>
          ) : (
            <>
              <button className="btn-ghost" data-testid="will-back-btn" onClick={() => { setView("list"); load(); }} style={{ fontSize: 12, marginBottom: 12 }}>← My wills</button>
              <WillResult will={current} api={api} toast={toast} onEdit={() => setView("form")} onDelete={remove} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
