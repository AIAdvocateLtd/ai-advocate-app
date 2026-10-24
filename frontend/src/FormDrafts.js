// Persist half-filled forms on this device so closing a window doesn't lose them.
import { useEffect, useState } from "react";

const PREFIX = "aa_draft_";

export function useFormDraft(name, initial) {
  const key = PREFIX + name;
  const [form, setForm] = useState(() => {
    try { return { ...initial, ...(JSON.parse(localStorage.getItem(key)) || {}) }; }
    catch { return initial; }
  });
  const [restored] = useState(() => !!localStorage.getItem(key));
  const dirty = Object.keys(initial).some(k => JSON.stringify(form[k]) !== JSON.stringify(initial[k]));

  useEffect(() => {
    const id = setTimeout(() => {
      if (dirty) localStorage.setItem(key, JSON.stringify(form));
      else localStorage.removeItem(key);
    }, 400);
    return () => clearTimeout(id);
  }, [form, dirty, key]);

  const clear = () => { localStorage.removeItem(key); setForm(initial); };
  return [form, setForm, { restored, dirty, clear, discard: () => localStorage.removeItem(key) }];
}

export function clearAllFormDrafts() {
  Object.keys(localStorage).filter(k => k.startsWith(PREFIX)).forEach(k => localStorage.removeItem(k));
}

export function DraftNotice({ draft, testid }) {
  if (!draft.dirty) return null;
  return (
    <div data-testid={testid} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, fontSize: 11.5, color: "var(--text-muted)", margin: "0 0 12px" }}>
      <span>{draft.restored ? "Your saved answers have been restored." : "Your answers are saved on this device as you type."}</span>
      <button onClick={() => { if (window.confirm("Clear everything you've typed in this form?")) draft.clear(); }}
        data-testid={`${testid}-clear`}
        style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--text-dim)", borderRadius: 6, padding: "3px 10px", fontSize: 11, cursor: "pointer" }}>
        Clear form
      </button>
    </div>
  );
}
