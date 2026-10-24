// Trustpilot review prompt (in Lex chat) + admin testimonials manager.
import React, { useEffect, useRef, useState } from "react";
import { Star, X, Trash2 } from "lucide-react";

export const TRUSTPILOT_URL = "https://www.trustpilot.com/review/aiadvocate.co.uk";
const PROMPT_KEY = "aa_tp_prompt_done";
const MIN_REPLIES = 3;

export function TrustpilotPrompt({ lexReplies }) {
  const [done, setDone] = useState(() => localStorage.getItem(PROMPT_KEY) === "1");
  const ref = useRef(null);
  const show = !done && lexReplies >= MIN_REPLIES;
  useEffect(() => { if (show) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [show]);
  if (!show) return null;
  const close = () => { localStorage.setItem(PROMPT_KEY, "1"); setDone(true); };
  return (
    <div ref={ref} data-testid="trustpilot-prompt" style={{
      margin: "12px 0", padding: "12px 14px", borderRadius: 12, border: "1px solid var(--gold-deep)",
      background: "rgba(247,201,72,0.06)", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
    }}>
      <Star size={16} color="var(--gold)" fill="var(--gold)" />
      <span style={{ flex: 1, minWidth: 180, fontSize: 13, color: "var(--text)" }}>
        Is Lex helping? A quick review on Trustpilot helps other people find free legal help.
      </span>
      <a href={TRUSTPILOT_URL} target="_blank" rel="noopener noreferrer" onClick={close}
        data-testid="trustpilot-prompt-review-btn"
        style={{ background: "var(--gold)", color: "#1a1300", borderRadius: 8, padding: "6px 12px", fontSize: 12, fontWeight: 700, textDecoration: "none" }}>
        Leave a review
      </a>
      <button onClick={close} data-testid="trustpilot-prompt-dismiss" aria-label="Dismiss"
        style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: 4 }}>
        <X size={14} />
      </button>
    </div>
  );
}

const input = {
  width: "100%", boxSizing: "border-box", background: "rgba(0,0,0,0.35)", border: "1px solid var(--line)",
  borderRadius: 8, padding: "8px 10px", color: "var(--text)", fontSize: 13, marginBottom: 8, fontFamily: "inherit",
};
const EMPTY = { name: "", stars: 5, quote: "", review_date: "", link: "" };

export function AdminTestimonialsCard({ api, toast }) {
  const [items, setItems] = useState([]);
  const [minShown, setMinShown] = useState(3);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/admin/testimonials").then(r => { setItems(r.data.items); setMinShown(r.data.min_shown); }).catch(() => {});
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const add = async () => {
    setBusy(true);
    try {
      await api.post("/admin/testimonials", { ...form, stars: Number(form.stars) });
      setForm(EMPTY); toast("Review added"); load();
    } catch (e) { toast(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Couldn't add review", "error"); }
    finally { setBusy(false); }
  };
  const remove = async (id) => {
    if (!window.confirm("Remove this review from the landing page?")) return;
    try { await api.delete(`/admin/testimonials/${id}`); toast("Review removed"); }
    catch { toast("Couldn't remove review", "error"); }
    load();
  };
  const canAdd = !busy && form.name.trim() && form.quote.trim().length >= 5;
  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }));

  return (
    <div data-testid="admin-testimonials-card" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginTop: 14 }}>
      <div style={{ fontWeight: 700, color: "var(--gold)", marginBottom: 4 }}>Landing page reviews (Trustpilot)</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
        Paste real reviews from <a href={TRUSTPILOT_URL} target="_blank" rel="noopener noreferrer" style={{ color: "var(--gold)" }}>your Trustpilot page</a>.
        The strip shows on the landing page once there are {minShown}+ ({items.length} added).
      </div>
      <input style={input} placeholder="Reviewer name (as shown on Trustpilot)" value={form.name} onChange={set("name")} data-testid="admin-testimonial-name" />
      <select style={input} value={form.stars} onChange={set("stars")} data-testid="admin-testimonial-stars">
        {[5, 4, 3, 2, 1].map(n => <option key={n} value={n}>{n} stars</option>)}
      </select>
      <textarea style={{ ...input, minHeight: 70 }} placeholder="Review text (copy exactly)" maxLength={400} value={form.quote} onChange={set("quote")} data-testid="admin-testimonial-quote" />
      <input style={input} placeholder="Date, e.g. October 2026 (optional)" value={form.review_date} onChange={set("review_date")} data-testid="admin-testimonial-date" />
      <input style={input} placeholder="Link to this review on Trustpilot (optional)" value={form.link} onChange={set("link")} data-testid="admin-testimonial-link" />
      <button onClick={add} disabled={!canAdd} data-testid="admin-testimonial-add"
        style={{ background: "var(--gold)", color: "#1a1300", border: "none", borderRadius: 8, padding: "8px 14px", fontWeight: 700, cursor: canAdd ? "pointer" : "not-allowed", opacity: canAdd ? 1 : 0.5 }}>
        Add review
      </button>
      <div style={{ marginTop: 14 }}>
        {items.map(it => (
          <div key={it.id} data-testid={`admin-testimonial-${it.id}`} style={{ display: "flex", gap: 10, alignItems: "flex-start", borderTop: "1px solid var(--line)", padding: "10px 0" }}>
            <div style={{ flex: 1, fontSize: 13 }}>
              <div style={{ color: "var(--gold)" }}>{"★".repeat(it.stars)}<span style={{ color: "var(--text-muted)" }}> · {it.name}{it.review_date ? ` · ${it.review_date}` : ""}</span></div>
              <div style={{ color: "var(--text-dim)", marginTop: 4 }}>{it.quote}</div>
            </div>
            <button onClick={() => remove(it.id)} data-testid={`admin-testimonial-delete-${it.id}`} aria-label="Delete"
              style={{ background: "transparent", border: "none", color: "#fca5a5", cursor: "pointer" }}><Trash2 size={14} /></button>
          </div>
        ))}
      </div>
    </div>
  );
}
