// Copy / Email / PDF / Share actions for Lex replies, letters, contracts and wills.
import React, { useState } from "react";
import { Copy, Mail, FileDown, Share2 } from "lucide-react";
import { stripLexMarkdown } from "@/LexMarkdown";

const MAILTO_SAFE_LEN = 1800;

const btn = {
  background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)",
  borderRadius: 8, padding: "2px 10px", fontSize: 11, cursor: "pointer", fontWeight: 600,
  display: "inline-flex", alignItems: "center", gap: 4, minHeight: 26,
};

const copyToClipboard = async (text) => {
  try { await navigator.clipboard.writeText(text); return true; }
  catch {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove(); return ok;
  }
};

export function ShareActions({ text, title = "AI Advocate", api, toast, onPdf, showPdf = true, testIdPrefix = "share" }) {
  const [pdfBusy, setPdfBusy] = useState(false);
  const clean = () => stripLexMarkdown(text || "");

  const copy = async () => {
    toast(await copyToClipboard(clean()) ? "Copied — ready to paste" : "Couldn't copy", "success");
  };

  const email = async () => {
    const body = clean();
    let mailBody = body;
    if (body.length > MAILTO_SAFE_LEN) {
      await copyToClipboard(body);
      mailBody = `${body.slice(0, MAILTO_SAFE_LEN)}…\n\n[The full text has been copied — paste it here if it's cut short.]`;
      toast("Full text copied too, in case your email app shortens it", "success");
    }
    window.location.href = `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(mailBody)}`;
  };

  const pdf = async () => {
    setPdfBusy(true);
    try {
      if (onPdf) { await onPdf(); }
      else {
        const filename = `${title.replace(/[^A-Za-z0-9]+/g, "_").slice(0, 60) || "AI_Advocate"}.pdf`;
        const r = await api.post("/pdf/inline", { title, body: clean(), filename }, { responseType: "blob" });
        const url = URL.createObjectURL(r.data);
        const a = document.createElement("a");
        a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
      }
    } catch (e) { toast("Couldn't create the PDF — try again", "error"); }
    finally { setPdfBusy(false); }
  };

  const share = async () => {
    try { await navigator.share({ title, text: clean() }); }
    catch (e) { if (e?.name !== "AbortError") copy(); }
  };

  return (
    <>
      <button data-testid={`${testIdPrefix}-copy`} onClick={copy} style={btn} title="Copy clean text"><Copy size={12} /> Copy</button>
      <button data-testid={`${testIdPrefix}-email`} onClick={email} style={btn} title="Open in your email app"><Mail size={12} /> Email</button>
      {showPdf && (
        <button data-testid={`${testIdPrefix}-pdf`} onClick={pdf} disabled={pdfBusy} style={btn} title="Save as PDF">
          {pdfBusy ? <span className="spinner" /> : <FileDown size={12} />} PDF
        </button>
      )}
      {typeof navigator !== "undefined" && navigator.share && (
        <button data-testid={`${testIdPrefix}-share`} onClick={share} style={btn} title="Share"><Share2 size={12} /> Share</button>
      )}
    </>
  );
}

export function ShareActionsRow(props) {
  return <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}><ShareActions {...props} /></div>;
}
