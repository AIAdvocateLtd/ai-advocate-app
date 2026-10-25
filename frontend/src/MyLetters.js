// "My letters" — every letter Lex has written, re-download or delete.
import React, { useEffect, useState } from "react";
import { ArrowLeft, Download, Trash2, FileText } from "lucide-react";
import { ShareActionsRow } from "@/ShareActions";
import { renderLexMarkdown, stripLexMarkdown } from "@/LexMarkdown";

const fmtDate = (iso) => iso ? new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "";

export function MyLetters({ api, toast, pdfInline }) {
  const [items, setItems] = useState(null);
  const [open, setOpen] = useState(null);

  const load = () => api.get("/letters/mine").then(r => setItems(r.data)).catch(() => setItems([]));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const download = (l) => pdfInline({ title: l.title, body: l.letter, filename: `${l.title.replace(/[^\w-]+/g, "_").slice(0, 60)}.pdf` });
  const remove = async (l) => {
    if (!window.confirm(`Delete "${l.title}"? You can restore it from the Recycle Bin for 30 days.`)) return;
    try {
      await api.delete(`/legal-files/${l.id}`);
      toast("Letter deleted — restorable from the Recycle Bin for 30 days");
      setOpen(null); load();
    } catch { toast("Couldn't delete the letter", "error"); }
  };

  if (items === null) return <div style={{ textAlign: "center", padding: 24 }}><span className="spinner" /></div>;

  if (open) return (
    <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }} data-testid="my-letter-view">
      <button className="btn-ghost" onClick={() => setOpen(null)} data-testid="my-letter-back" style={{ marginBottom: 10, padding: "6px 12px" }}>
        <ArrowLeft size={14} style={{ display: "inline", marginRight: 4 }} />My letters
      </button>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--gold)", marginBottom: 4 }}>{open.title}</div>
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 10 }}>{fmtDate(open.created_at)}</div>
      <div data-testid="my-letter-text" style={{ fontSize: 13.5, color: "var(--text-dim)", lineHeight: 1.6, background: "#0a0a0a", border: "1px solid var(--line)", borderRadius: 10, padding: 14 }}>{renderLexMarkdown(open.letter)}</div>
      <div className="flex gap-2" style={{ marginTop: 12 }}>
        <button className="btn-gold" onClick={() => download(open)} data-testid="my-letter-pdf" style={{ flex: 1 }}>
          <Download size={14} style={{ display: "inline", marginRight: 6 }} />Download PDF
        </button>
        <button className="btn-ghost" onClick={() => remove(open)} data-testid="my-letter-delete" style={{ flex: 1, color: "#fca5a5" }}>
          <Trash2 size={14} style={{ display: "inline", marginRight: 6 }} />Delete
        </button>
      </div>
      <ShareActionsRow text={stripLexMarkdown(open.letter)} title={open.title} api={api} toast={toast} showPdf={false} testIdPrefix="my-letter" />
    </div>
  );

  return (
    <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }} data-testid="my-letters-list">
      {items.length === 0 && (
        <div data-testid="my-letters-empty" style={{ color: "var(--text-dim)", fontSize: 13, textAlign: "center", padding: 24, lineHeight: 1.6 }}>
          No letters yet. Pick a template and Lex will write your first one. It'll be kept here.
        </div>
      )}
      {items.map(l => (
        <div key={l.id} data-testid={`my-letter-${l.id}`} style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 12px", marginBottom: 6, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10 }}>
          <button onClick={() => setOpen(l)} data-testid={`my-letter-open-${l.id}`} style={{ flex: 1, minWidth: 0, display: "flex", gap: 10, alignItems: "center", background: "transparent", border: "none", color: "var(--text)", cursor: "pointer", textAlign: "left", padding: 0 }}>
            <FileText size={16} color="var(--gold)" style={{ flexShrink: 0 }} />
            <span style={{ minWidth: 0 }}>
              <span style={{ display: "block", fontSize: 13.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{l.title}</span>
              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>{fmtDate(l.created_at)}</span>
            </span>
          </button>
          <button onClick={() => download(l)} aria-label="Download PDF" data-testid={`my-letter-pdf-${l.id}`} style={{ background: "transparent", border: "none", color: "var(--gold)", cursor: "pointer", padding: 6 }}><Download size={16} /></button>
          <button onClick={() => remove(l)} aria-label="Delete letter" data-testid={`my-letter-delete-${l.id}`} style={{ background: "transparent", border: "none", color: "#fca5a5", cursor: "pointer", padding: 6 }}><Trash2 size={16} /></button>
        </div>
      ))}
    </div>
  );
}
