// Admin: re-sync a user's app plan from their live Stripe subscription.
import React, { useState } from "react";
import { RefreshCw } from "lucide-react";

export function AdminStripeResyncCard({ api, toast }) {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const run = async () => {
    setBusy(true); setResult(null);
    try {
      const { data } = await api.post("/admin/users/resync-stripe", { email });
      setResult(data);
      toast(`${data.email} is now on ${data.tier.toUpperCase()}`);
    } catch (e) { toast(e?.response?.data?.detail || "Re-sync failed", "error"); }
    finally { setBusy(false); }
  };

  return (
    <div data-testid="admin-stripe-resync-card" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginTop: 14 }}>
      <div style={{ fontWeight: 700, color: "var(--gold)", marginBottom: 4 }}>Re-sync plan from Stripe</div>
      <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10 }}>If a subscriber's plan in the app doesn't match what they paid for, enter their email to fix it from Stripe.</div>
      <div style={{ display: "flex", gap: 8 }}>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="customer@email.com" data-testid="admin-resync-email"
          style={{ flex: 1, background: "rgba(0,0,0,0.35)", border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px", color: "var(--text)", fontSize: 13 }} />
        <button onClick={run} disabled={busy || !email.includes("@")} data-testid="admin-resync-btn"
          style={{ background: "var(--gold)", color: "#1a1300", border: "none", borderRadius: 8, padding: "8px 14px", fontWeight: 700, cursor: "pointer", opacity: busy || !email.includes("@") ? 0.5 : 1, display: "flex", alignItems: "center", gap: 6 }}>
          <RefreshCw size={14} className={busy ? "spin" : ""} />Re-sync
        </button>
      </div>
      {result && (
        <div data-testid="admin-resync-result" style={{ fontSize: 12.5, color: "var(--text-dim)", marginTop: 10 }}>
          {result.email}: {String(result.previous_tier || "free").toUpperCase()} → <strong style={{ color: "var(--gold)" }}>{result.tier.toUpperCase()}</strong> ({result.status})
        </div>
      )}
    </div>
  );
}
