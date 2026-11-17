// Message allowances + fair-use wording from the backend (follows the active allowance version).
import { useEffect, useState } from "react";
import axios from "axios";

const DEFAULT = { version: "v1", plus: { monthly: 300, daily: 40 }, pro: { monthly: 600, daily: 80 }, cost_cap: false, fair_use_note: "" };
let cached = null;
let pending = null;

export function useAllowances() {
  const [a, setA] = useState(cached || DEFAULT);
  useEffect(() => {
    if (cached) return;
    pending = pending || axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/plans/allowances`).then(r => (cached = r.data)).catch(() => DEFAULT);
    pending.then(d => setA(d || DEFAULT));
  }, []);
  return a;
}

export const AllowanceText = ({ plan, suffix = " messages/month" }) => {
  const a = useAllowances();
  return <>{a[plan].monthly}{suffix}</>;
};

export const FairUseFootnote = ({ testid = "fair-use-footnote", style }) => {
  const a = useAllowances();
  if (!a.fair_use_note) return null;
  return <div data-testid={testid} style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.45, ...style }}>{a.fair_use_note}</div>;
};
