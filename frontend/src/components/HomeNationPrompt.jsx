// One-time offer to save the customer's usual UK nation. Saved only when they tap; changeable in Settings.
import React, { useState } from "react";

const NATIONS = [["england", "England"], ["wales", "Wales"], ["scotland", "Scotland"], ["northern_ireland", "Northern Ireland"]];
const chip = active => ({
  background: active ? "var(--gold)" : "transparent", color: active ? "#1a1300" : "var(--text)", border: "1px solid var(--gold-deep)",
  borderRadius: 999, padding: "5px 12px", fontSize: 12, fontWeight: 600, cursor: "pointer",
});

export const HomeNationPrompt = ({ api, suggest, idx }) => {
  const [state, setState] = useState(null);
  const save = async j => {
    try { await api.post("/profile/uk-jurisdiction", { jurisdiction: j }); setState(j); } catch { setState("error"); }
  };
  const dismiss = async () => { try { await api.post("/profile/home-nation-prompt/dismiss"); } catch { /* ignore */ } setState("dismissed"); };
  if (state === "dismissed") return null;
  const label = NATIONS.find(([k]) => k === state)?.[1];
  return (
    <div data-testid={`home-nation-prompt-${idx}`} style={{ border: "1px dashed var(--gold-deep)", borderRadius: 12, padding: 12, width: "100%", marginTop: 4 }}>
      {label ? (
        <div data-testid="home-nation-saved" style={{ fontSize: 12.5, color: "var(--text)" }}>
          Saved: you usually live in {label}. Lex will still check if a matter is governed somewhere else. Change it any time in Settings.
        </div>
      ) : (<>
        <div style={{ fontSize: 12.5, color: "var(--text)", marginBottom: 8 }}>
          Which part of the UK do you usually live in? Saving it means Lex won't need to ask again.
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {NATIONS.map(([k, l]) => (
            <button key={k} data-testid={`home-nation-${k}`} onClick={() => save(k)} style={chip(k === suggest)}>{l}</button>
          ))}
          <button data-testid="home-nation-dismiss" onClick={dismiss} style={{ ...chip(false), border: 0, color: "var(--text-muted)" }}>Not now</button>
        </div>
        {state === "error" && <div data-testid="home-nation-error" style={{ color: "var(--danger)", fontSize: 11.5, marginTop: 6 }}>Could not save — try again in Settings.</div>}
        <div style={{ fontSize: 10.5, color: "var(--text-muted)", marginTop: 6 }}>Only the nation is saved — never your town or address.</div>
      </>)}
    </div>
  );
};
