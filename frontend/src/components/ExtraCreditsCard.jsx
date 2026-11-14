// Extra Lex Credits — one-off packs (no auto top-up). Hidden unless the owner switches credits on.
import React, { useEffect, useState } from "react";

const box = { border: "1px solid var(--gold-deep)", borderRadius: 12, padding: "10px 12px" };
const fmt = iso => new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

function PackRow({ p, consent, onBuy, busy }) {
  return (
    <div data-testid={`credit-pack-${p.id}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0" }}>
      <span style={{ fontSize: 13, color: "#fff" }}>{p.label} · <b style={{ color: "var(--gold)" }}>£{p.price_gbp.toFixed(2)}</b></span>
      <button data-testid={`credit-buy-${p.id}`} disabled={!consent || busy} onClick={() => onBuy(p)}
        style={{ background: "var(--gold)", color: "#1a1300", border: 0, borderRadius: 8, padding: "5px 12px", fontWeight: 700,
                 fontSize: 12, opacity: consent && !busy ? 1 : 0.5, cursor: consent ? "pointer" : "not-allowed" }}>Buy</button>
    </div>
  );
}

export const ExtraCreditsCard = ({ api }) => {
  const [d, setD] = useState(null);
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => { api.get("/credits").then(r => setD(r.data)).catch(() => setD(null)); }, [api]);
  if (!d || (!d.enabled && !d.balance)) return null;
  const buy = async (p) => {
    setBusy(true); setErr("");
    try {
      const { data } = await api.post("/credits/checkout", { pack_id: p.id, consent_immediate_supply: consent });
      window.location.href = data.checkout_url;
    } catch (e) { setErr(e?.response?.data?.detail || "Could not start checkout."); setBusy(false); }
  };
  const next = d.lots?.[0];
  return (
    <div data-testid="extra-credits-card" style={box}>
      <div style={{ fontSize: 11, color: "var(--gold)", fontWeight: 800, letterSpacing: "0.05em" }}>EXTRA LEX CREDITS</div>
      <div data-testid="credit-balance" style={{ fontSize: 13, color: "#fff", margin: "4px 0" }}>
        Balance: <b>{d.balance}</b> credits{next ? ` · next ${next.remaining} expire ${fmt(next.expires_at)}` : ""}
      </div>
      <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.45 }}>
        Used only after your plan or pass allowance runs out. 1 credit = 1 Lex message · letter = 2 · document analysis = 4.
        Valid {Math.round(d.valid_days / 30.4)} months. Same AI as your current plan. One-off payment — never automatic.
      </div>
      {d.enabled && (<>
        {d.packs.map(p => <PackRow key={p.id} p={p} consent={consent} onBuy={buy} busy={busy} />)}
        <label data-testid="credit-consent" style={{ display: "flex", gap: 6, fontSize: 11.5, color: "var(--text-muted)", marginTop: 4 }}>
          <input data-testid="credit-consent-checkbox" type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
          I want my credits available straight away. I understand I can cancel within 14 days for a refund of unused credits.
        </label>
      </>)}
      {err && <div data-testid="credit-error" style={{ color: "var(--danger)", fontSize: 12, marginTop: 4 }}>{err}</div>}
    </div>
  );
};
