// Lightweight renderer for Lex replies: turns the AI's markdown (#, **, -, ---, tables)
// into clean, professional formatting without exposing raw symbols.
import React from "react";

const INLINE_RE = /(\*\*[^*\n]+?\*\*|__[^_\n]+?__|\*[^*\s][^*\n]*?\*|`[^`\n]+?`)/g;

function renderInline(text, renderText, key) {
  const parts = text.split(INLINE_RE).filter(p => p !== "");
  return parts.map((p, i) => {
    const k = `${key}-${i}`;
    if ((p.startsWith("**") && p.endsWith("**")) || (p.startsWith("__") && p.endsWith("__")))
      return <strong key={k} style={{ color: "var(--text)", fontWeight: 700 }}>{renderText(p.slice(2, -2), k)}</strong>;
    if (p.startsWith("`") && p.endsWith("`")) return <span key={k}>{renderText(p.slice(1, -1), k)}</span>;
    if (p.length > 2 && p.startsWith("*") && p.endsWith("*")) return <em key={k}>{renderText(p.slice(1, -1), k)}</em>;
    return <React.Fragment key={k}>{renderText(p, k)}</React.Fragment>;
  });
}

const stripBold = (s) => s.replace(/\*\*|__/g, "").trim();
const isTableSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);

export function renderLexMarkdown(body, renderText = (t) => t) {
  if (typeof body !== "string" || !body) return body;
  const lines = body.replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let para = [];
  const flush = () => {
    if (!para.length) return;
    const k = `p${blocks.length}`;
    blocks.push(
      <p key={k} style={{ margin: "0 0 10px 0" }}>
        {para.map((l, i) => <React.Fragment key={i}>{i > 0 && <br />}{renderInline(l, renderText, `${k}-${i}`)}</React.Fragment>)}
      </p>
    );
    para = [];
  };
  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const k = `b${idx}`;
    let m;
    if (!line.trim()) { flush(); return; }
    if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      flush();
      blocks.push(<hr key={k} style={{ border: "none", borderTop: "1px solid var(--line)", margin: "12px 0" }} />);
    } else if ((m = /^\s*(#{1,6})\s+(.*)$/.exec(line))) {
      flush();
      const level = m[1].length;
      blocks.push(
        <div key={k} style={{ fontWeight: 700, color: "var(--gold)", fontSize: level <= 2 ? 15.5 : 14.5, margin: "14px 0 6px 0", lineHeight: 1.35 }}>
          {renderInline(stripBold(m[2]), renderText, k)}
        </div>
      );
    } else if ((m = /^(\s*)[-*•]\s+(.*)$/.exec(line))) {
      flush();
      const indent = Math.min(m[1].length, 6) * 4;
      blocks.push(
        <div key={k} style={{ display: "flex", gap: 8, margin: "0 0 6px 0", paddingLeft: indent }}>
          <span style={{ color: "var(--gold)", flexShrink: 0 }}>•</span>
          <span>{renderInline(m[2], renderText, k)}</span>
        </div>
      );
    } else if ((m = /^(\s*)(\d+)[.)]\s+(.*)$/.exec(line))) {
      flush();
      blocks.push(
        <div key={k} style={{ display: "flex", gap: 8, margin: "0 0 6px 0", paddingLeft: Math.min(m[1].length, 6) * 4 }}>
          <span style={{ color: "var(--gold)", fontWeight: 700, flexShrink: 0, minWidth: 18 }}>{m[2]}.</span>
          <span>{renderInline(m[3], renderText, k)}</span>
        </div>
      );
    } else if ((m = /^\s*>\s?(.*)$/.exec(line))) {
      flush();
      blocks.push(
        <div key={k} style={{ borderLeft: "3px solid var(--gold-deep)", paddingLeft: 10, margin: "0 0 8px 0", color: "var(--text-muted)" }}>
          {renderInline(m[1], renderText, k)}
        </div>
      );
    } else if (line.trim().startsWith("|")) {
      flush();
      if (isTableSep(line)) return;
      const cells = line.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim()).filter(Boolean);
      blocks.push(
        <div key={k} style={{ display: "flex", flexWrap: "wrap", gap: "2px 14px", padding: "5px 0", borderBottom: "1px solid var(--line)", fontSize: 13 }}>
          {cells.map((c, ci) => <span key={ci} style={ci === 0 ? { fontWeight: 600 } : undefined}>{renderInline(c, renderText, `${k}-${ci}`)}</span>)}
        </div>
      );
    } else {
      para.push(line);
    }
  });
  flush();
  return <div data-no-translate="">{blocks}</div>;
}

// Plain-text version for read-aloud / copying — no markdown symbols.
export function stripLexMarkdown(body) {
  if (typeof body !== "string") return body;
  return body
    .replace(/\[\[\s*PDF[^\]]*\]\]/gi, "")
    .replace(/^\s*(-{3,}|\*{3,}|_{3,})\s*$/gm, "")
    .replace(/^\s*#{1,6}\s+/gm, "")
    .replace(/^[ \t]*\|?[ \t]*:?-{2,}.*$/gm, "")
    .replace(/^[ \t]*\|(.*)\|[ \t]*$/gm, (_, row) => row.split("|").map(c => c.trim()).filter(Boolean).join(" — "))
    .replace(/\*\*|__|`/g, "")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Lex adds [[PDF: Title]] when the user asks for a PDF — strip it (wherever it is) and expose the title.
const PDF_TAG_RE = /\[\[\s*PDF\s*:?\s*([^\]]*)\]\]/i;
export function extractPdfTag(body) {
  if (typeof body !== "string") return { body, pdfTitle: null };
  const m = PDF_TAG_RE.exec(body);
  if (!m) return { body: body.replace(/\[\[\s*PDF[^\]]*$/i, "").trimEnd(), pdfTitle: null };
  return { body: body.replace(new RegExp(PDF_TAG_RE.source, "gi"), "").trimEnd(), pdfTitle: (m[1] || "").trim() || "AI Advocate document" };
}
