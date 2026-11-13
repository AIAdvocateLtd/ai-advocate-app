// Fair-use notice above the Lex chat input: shows usage warnings (80%+) and free-question count.
import React, { useEffect, useState } from "react";

export function FairUseNotice({ api, refreshKey }) {
  const [fu, setFu] = useState(null);
  useEffect(() => {
    if (refreshKey) return;
    api.get("/subscription/usage").then(r => setFu(r.data?.fair_use || null)).catch(() => {});
  }, [api, refreshKey]);
  const free = fu?.items?.free_actions;
  const warnings = fu?.warnings || [];
  if (!free && !warnings.length) return null;
  const text = warnings.length ? warnings.join(" ")
    : `${Math.max(0, free.limit - free.used)} of ${free.limit} free Lex questions left.`;
  return (
    <div data-testid="fair-use-notice" style={{ margin: "0 12px 8px", padding: "7px 10px", borderRadius: 10,
      border: "1px solid var(--gold-deep)", color: "var(--gold-soft)", fontSize: 11.5, lineHeight: 1.4 }}>
      {text}
    </div>
  );
}
