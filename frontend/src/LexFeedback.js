// 👍 / 👎 / "Report wrong answer" under each Lex reply — feeds Lex's learning loop.
import React, { useState } from "react";
import { ThumbsUp, ThumbsDown, Flag } from "lucide-react";

const pill = (active) => ({
  background: active ? "rgba(247,201,72,0.18)" : "transparent", border: "1px solid var(--line)",
  color: active ? "var(--gold)" : "var(--text-muted)", borderRadius: 8, padding: "2px 8px", fontSize: 11,
  cursor: active ? "default" : "pointer", display: "inline-flex", alignItems: "center", gap: 4,
});

export function LexFeedback({ api, toast, prompt, sessionId, question, answer, idx }) {
  const [sent, setSent] = useState(null);
  const send = async (rating, note = "") => {
    if (sent) return;
    try {
      await api.post("/lex/feedback", { session_id: sessionId, rating, note, question, answer });
      setSent(rating);
      toast(rating === "wrong" ? "Thanks — we'll review this and teach Lex the right answer" : "Thanks for the feedback", "success");
    } catch { toast("Couldn't send feedback", "error"); }
  };
  const report = async () => {
    const note = await prompt({ title: "What was wrong?", message: "Tell us briefly what Lex got wrong (e.g. a date, deadline or rule).",
      placeholder: "e.g. You need ILR for 12 months, not 2 months", confirmLabel: "Send report" });
    if (note && note.trim()) send("wrong", note.trim());
  };
  return (
    <span style={{ display: "inline-flex", gap: 6 }}>
      <button data-testid={`lex-thumb-up-${idx}`} title="Helpful" disabled={!!sent} onClick={() => send("up")} style={pill(sent === "up")}>
        <ThumbsUp size={12} />
      </button>
      <button data-testid={`lex-thumb-down-${idx}`} title="Not helpful" disabled={!!sent} onClick={() => send("down")} style={pill(sent === "down")}>
        <ThumbsDown size={12} />
      </button>
      <button data-testid={`lex-report-wrong-${idx}`} title="Report a wrong answer" disabled={!!sent} onClick={report} style={pill(sent === "wrong")}>
        <Flag size={12} /> {sent === "wrong" ? "Reported" : "Report wrong answer"}
      </button>
    </span>
  );
}
