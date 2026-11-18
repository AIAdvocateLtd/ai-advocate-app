import { useCallback, useEffect, useState } from "react";

const cell = { padding: "6px 8px", borderBottom: "1px solid var(--line)", textAlign: "left", verticalAlign: "top" };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid var(--line)", color: "var(--text)", borderRadius: 6,
  padding: "5px 8px", fontSize: 12, marginRight: 6, marginBottom: 6 };
const btn = (bg, fg = "#1a1300") => ({ background: bg, border: "none", color: fg, padding: "6px 10px", borderRadius: 7,
  fontSize: 12, fontWeight: 700, cursor: "pointer", marginRight: 6 });
const errMsg = (e, d) => e?.response?.data?.detail || d;

const Decide = ({ p, api, done }) => {
  const [f, setF] = useState({ reviewer_name: "", regulator: "", registration_number: "", notes: "" });
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const send = async (decision) => {
    setErr("");
    try { await api.post(`/admin/law-updates/${p._id}/decision`, { decision, ...f }); done(); }
    catch (e) { setErr(errMsg(e, "Decision not saved.")); }
  };
  return (
    <div data-testid={`law-update-decide-${p._id}`} style={{ marginTop: 6 }}>
      <input data-testid="law-update-reviewer-name" placeholder="Reviewer name" value={f.reviewer_name} onChange={set("reviewer_name")} style={inp} />
      <input data-testid="law-update-regulator" placeholder="Regulator (e.g. SRA)" value={f.regulator} onChange={set("regulator")} style={inp} />
      <input data-testid="law-update-registration" placeholder="Registration no." value={f.registration_number} onChange={set("registration_number")} style={inp} />
      <input data-testid="law-update-notes" placeholder="Notes / amendments needed" value={f.notes} onChange={set("notes")} style={{ ...inp, width: 260 }} />
      <div>
        <button data-testid="law-update-approve-btn" onClick={() => send("approve")} style={btn("#22c55e")}>Approve</button>
        <button data-testid="law-update-amend-btn" onClick={() => send("amend")} style={btn("var(--gold)")}>Request amendment</button>
        <button data-testid="law-update-reject-btn" onClick={() => send("reject")} style={btn("#ef4444", "#fff")}>Reject</button>
      </div>
      {err && <div data-testid="law-update-error" style={{ color: "#fca5a5" }}>{err}</div>}
    </div>
  );
};

export const LawUpdateReview = ({ api }) => {
  const [rows, setRows] = useState(null);
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    try { setRows((await api.get("/admin/law-updates")).data); } catch (e) { setErr(errMsg(e, "Couldn't load law updates.")); }
  }, [api]);
  useEffect(() => { load(); }, [load]);
  return (
    <div data-testid="law-update-review" style={{ marginTop: 14, fontSize: 12 }}>
      <b>Detected law changes awaiting professional review</b>
      <div style={{ color: "var(--text-dim)", margin: "4px 0 8px" }}>
        Source facts from legislation.gov.uk only. Approval records a qualified reviewer's view of the change's effect; linked Lex facts stay withheld until re-signed.
      </div>
      {err && <div style={{ color: "#fca5a5" }}>{err}</div>}
      {rows && rows.length === 0 && <div data-testid="law-update-empty" style={{ color: "var(--text-dim)" }}>No detected changes.</div>}
      {rows && rows.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>{["Provision", "Change", "Linked Lex knowledge", "Status"].map(h => <th key={h} style={cell}>{h}</th>)}</tr></thead>
          <tbody>{rows.map(p => (
            <tr key={p._id} data-testid={`law-update-row-${p._id}`}>
              <td style={cell}><a href={p.url} target="_blank" rel="noreferrer" style={{ color: "var(--gold)" }}>{p.title || p.key}</a>
                <div style={{ color: "var(--text-dim)" }}>{p.provision} · {p.jurisdiction}</div></td>
              <td style={cell}>{(p.change_types || []).join(", ").replace(/_/g, " ")}
                {p.commencement?.date && <div>commencement {p.commencement.date}</div>}
                {p.affecting_instruments?.length > 0 && <div>by {p.affecting_instruments.join(", ")}</div>}
                <div style={{ color: "var(--text-dim)" }}>interpretation: {p.interpretation}</div></td>
              <td style={cell}>{(p.linked_rules || []).join(", ") || "—"} · {(p.linked_lessons || []).length} fact(s) withheld</td>
              <td style={cell}><span data-testid={`law-update-status-${p._id}`}>{p.status.replace(/_/g, " ")}</span>
                {["awaiting_review", "amend_requested"].includes(p.status) && <Decide p={p} api={api} done={load} />}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </div>
  );
};
