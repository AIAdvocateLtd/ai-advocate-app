// Passes bought while another is active — each starts when the previous one ends.
import React from "react";

const fmt = iso => new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export const QueuedPassesList = ({ queued }) => {
  if (!queued || !queued.length) return null;
  return (
    <div data-testid="topup-queued-list" style={{ border: "1px dashed var(--gold-deep)", borderRadius: 12, padding: "10px 12px" }}>
      <div style={{ fontSize: 11, color: "var(--gold)", fontWeight: 800, letterSpacing: "0.05em" }}>QUEUED PASSES</div>
      {queued.map((q, i) => (
        <div key={`${q.kind}-${q.starts_at}`} data-testid={`topup-queued-${i}`} style={{ fontSize: 12.5, color: "#fff", marginTop: 4 }}>
          {q.label} · starts <b>{fmt(q.starts_at)}</b> · ends {fmt(q.ends_at)}
        </div>
      ))}
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
        Starts automatically with its full time and allowance. Your current pass is not affected.
      </div>
    </div>
  );
};
