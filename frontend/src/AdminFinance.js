// Admin: Money — Stripe income by month, UK tax-year totals, VAT threshold, accountant CSV.
import React, { useEffect, useState } from "react";
import { Download } from "lucide-react";

const gbp = (n) => `${(n || 0) < 0 ? "−" : ""}£${Math.abs(n || 0).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const monthLabel = (ym) => new Date(`${ym}-01T00:00:00Z`).toLocaleDateString("en-GB", { month: "short", year: "numeric" });
const today = () => new Date().toISOString().slice(0, 10);
const cell = { padding: "6px 4px", textAlign: "right", fontVariantNumeric: "tabular-nums" };
const dateInput = { background: "rgba(0,0,0,0.35)", border: "1px solid var(--line)", borderRadius: 8, padding: "6px 8px", color: "var(--text)", fontSize: 12.5, colorScheme: "dark" };

export function AdminFinanceCard({ api, toast }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState(today());
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/admin/finance/summary")
      .then(r => { setData(r.data); setFrom(r.data.tax_year.from); })
      .catch(e => setErr(e?.response?.data?.detail || "Couldn't load figures from Stripe"));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const download = async () => {
    setBusy(true);
    try {
      const r = await api.get("/admin/finance/export", { params: { start: from, end: to }, responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `ai-advocate-stripe-${from}-to-${to}.csv`; a.click();
      URL.revokeObjectURL(url);
    } catch { toast("Couldn't create the spreadsheet", "error"); }
    finally { setBusy(false); }
  };

  const ty = data?.tax_year, vat = data?.vat;
  return (
    <div data-testid="admin-finance-card" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginTop: 14 }}>
      <div style={{ fontWeight: 700, color: "var(--gold)", marginBottom: 4 }}>Money</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>Live from Stripe. A summary for you and your accountant, not a tax return.</div>
      {err && <div data-testid="admin-finance-error" style={{ fontSize: 13, color: "#fca5a5" }}>{err}</div>}
      {!data && !err && <div style={{ textAlign: "center", padding: 14 }}><span className="spinner" /></div>}
      {data && (
        <>
          <div data-testid="admin-finance-taxyear" style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8, marginBottom: 14 }}>
            {[["Sales", ty.sales], ["Refunds", ty.refunds], ["Stripe fees", ty.fees], ["Net", ty.net]].map(([k, v]) => (
              <div key={k} style={{ background: "#0a0a0a", border: "1px solid var(--line)", borderRadius: 10, padding: "8px 10px" }}>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{k} · tax year {ty.label}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: k === "Net" ? "var(--gold)" : "var(--text)" }}>{gbp(v)}</div>
              </div>
            ))}
          </div>

          <div data-testid="admin-finance-vat" style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--text-dim)", marginBottom: 4 }}>
              <span>VAT threshold · last 12 months</span><span>{gbp(vat.rolling_12m_sales)} of {gbp(vat.threshold)}</span>
            </div>
            <div style={{ height: 6, background: "#1a1a1a", borderRadius: 99, overflow: "hidden" }}>
              <div style={{ width: `${Math.max(vat.pct, 0.5)}%`, height: "100%", background: vat.warning ? "#fca5a5" : "var(--gold)" }} />
            </div>
            {vat.warning && <div style={{ fontSize: 12, color: "#fca5a5", marginTop: 6 }}>You're close to the £90,000 VAT threshold. Speak to your accountant about registering.</div>}
          </div>

          <table data-testid="admin-finance-months" style={{ width: "100%", fontSize: 12, borderCollapse: "collapse", marginBottom: 14 }}>
            <thead><tr style={{ color: "var(--text-muted)" }}>
              <th style={{ ...cell, textAlign: "left" }}>Month</th><th style={cell}>Sales</th><th style={cell}>Refunds</th><th style={cell}>Fees</th><th style={cell}>Net</th>
            </tr></thead>
            <tbody>
              {data.months.length === 0 && <tr><td colSpan={5} style={{ ...cell, textAlign: "center", color: "var(--text-dim)" }}>No sales yet</td></tr>}
              {data.months.map(m => (
                <tr key={m.month} style={{ borderTop: "1px solid var(--line)", color: "var(--text-dim)" }}>
                  <td style={{ ...cell, textAlign: "left" }}>{monthLabel(m.month)}</td><td style={cell}>{gbp(m.sales)}</td>
                  <td style={cell}>{gbp(m.refunds)}</td><td style={cell}>{gbp(m.fees)}</td>
                  <td style={{ ...cell, color: "var(--text)" }}>{gbp(m.net)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 6 }}>Spreadsheet for your accountant</div>
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <input type="date" value={from} onChange={e => setFrom(e.target.value)} style={dateInput} data-testid="admin-finance-from" />
            <span style={{ color: "var(--text-muted)", fontSize: 12 }}>to</span>
            <input type="date" value={to} onChange={e => setTo(e.target.value)} style={dateInput} data-testid="admin-finance-to" />
            <button onClick={download} disabled={busy || !from || !to} data-testid="admin-finance-export-btn"
              style={{ background: "var(--gold)", color: "#1a1300", border: "none", borderRadius: 8, padding: "7px 12px", fontWeight: 700, fontSize: 12.5, cursor: "pointer", opacity: busy ? 0.6 : 1, display: "flex", alignItems: "center", gap: 5 }}>
              <Download size={13} />{busy ? "Preparing…" : "Download"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
