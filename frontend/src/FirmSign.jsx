/**
 * FirmSign.jsx — Public agreement-signing page.
 *
 * Route: /firm-sign/<token>  (matched in index.js)
 *
 * Flow:
 *   1. GET /api/firm-agreements/<token>      → fetch metadata (no auth)
 *   2. If status === "signed", show a "Already signed — download PDF" view.
 *   3. Otherwise, render the full Founding Firm Agreement on screen + a typed-name
 *      field + canvas signature pad.
 *   4. POST /api/firm-agreements/<token>/sign with { firm_signer_name, firm_signature_data_url }
 *   5. On success, show "Signed!" with a download button.
 *
 * Legally binding under UK Electronic Communications Act 2000 + eIDAS.
 */

import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";

const API = (process.env.REACT_APP_BACKEND_URL || "") + "/api";
const GOLD = "#f7c948";
const GOLD_DEEP = "#b8860b";
const INK = "#1a1a1a";

// ---------- Inline signature canvas ----------
// Lightweight (~50 lines) — no library dep needed for the simple use-case.
// Captures pointer events, draws a smooth black line, exposes `toDataURL()`.
function SignatureCanvas({ onChange, width = 460, height = 130 }) {
  const ref = useRef(null);
  const drawingRef = useRef(false);
  const lastRef = useRef(null);

  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const ctx = cv.getContext("2d");
    // Crisp lines on retina
    const dpr = window.devicePixelRatio || 1;
    cv.width = width * dpr; cv.height = height * dpr;
    cv.style.width = `${width}px`; cv.style.height = `${height}px`;
    ctx.scale(dpr, dpr);
    ctx.strokeStyle = "#1a1a1a";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
  }, [width, height]);

  const pos = (e) => {
    const cv = ref.current;
    const r = cv.getBoundingClientRect();
    const t = e.touches ? e.touches[0] : e;
    return { x: t.clientX - r.left, y: t.clientY - r.top };
  };
  const start = (e) => {
    e.preventDefault();
    drawingRef.current = true;
    lastRef.current = pos(e);
  };
  const move = (e) => {
    if (!drawingRef.current) return;
    e.preventDefault();
    const p = pos(e);
    const ctx = ref.current.getContext("2d");
    ctx.beginPath();
    ctx.moveTo(lastRef.current.x, lastRef.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    lastRef.current = p;
  };
  const end = () => {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    if (onChange && ref.current) onChange(ref.current.toDataURL("image/png"));
  };
  const clear = () => {
    const cv = ref.current; if (!cv) return;
    const ctx = cv.getContext("2d");
    ctx.clearRect(0, 0, cv.width, cv.height);
    if (onChange) onChange("");
  };

  return (
    <div data-testid="signature-canvas-wrap" style={{ position: "relative", display: "inline-block" }}>
      <canvas ref={ref}
              onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
              onTouchStart={start} onTouchMove={move} onTouchEnd={end}
              style={{ background: "#fff", border: "1px dashed #c0a04a", borderRadius: 8, touchAction: "none", cursor: "crosshair", display: "block" }}
              data-testid="signature-canvas" />
      <button type="button" onClick={clear}
              data-testid="signature-clear-btn"
              style={{ position: "absolute", top: 6, right: 6, background: "rgba(0,0,0,0.04)", color: "#888", border: "1px solid #ddd", borderRadius: 6, padding: "3px 8px", fontSize: 11, cursor: "pointer" }}>
        Clear
      </button>
    </div>
  );
}

// ---------- The terms displayed on-screen ----------
// Kept in sync with backend/tools/generate_founding_firm_agreement.py
// If you update one, update the other.
function AgreementBody({ firm }) {
  return (
    <div style={{ fontSize: 14.5, lineHeight: 1.65, color: INK }}>
      <div style={{ marginBottom: 18 }}>
        <strong style={{ color: GOLD_DEEP }}>BETWEEN:</strong>{" "}
        <strong>AI Advocate Ltd.</strong> (Company No. 16612244, ICO Registration ZC158457), registered in England &amp; Wales (<em>"AI Advocate"</em>)
        <br/>
        <strong style={{ color: GOLD_DEEP }}>AND:</strong>{" "}
        <strong>{firm.firm_name}</strong>
        {firm.sra && <> · SRA Number: <strong>{firm.sra}</strong></>}
        {firm.address && <><br/>{firm.address}</>}
        {" "}(<em>"the Firm"</em>)
      </div>

      <p>AI Advocate is launching a UK consumer + B2B legal-technology platform at <a href="https://aiadvocate.co.uk" style={{ color: GOLD_DEEP }}>aiadvocate.co.uk</a>. The first 20 partner firms onboarded during the pre-launch cohort are designated <strong>Founding Firms</strong> and receive the lifetime benefits set out below in recognition of their early support.</p>

      <h3 style={{ color: GOLD_DEEP, marginTop: 24 }}>1. FOUNDING FIRM BENEFITS</h3>
      <ul style={{ paddingLeft: 22 }}>
        <li><strong>Founding £199/month rate, lock-in survival</strong> — the Firm is granted the Premium tier at £199 per month. If AI Advocate raises the public Premium rate above £199 at any point during the Firm's continuous subscription, the Firm's rate stays at £199 (or the then-current Premium rate, whichever is lower) for the duration of that continuous subscription. Subject to clause 3.4.</li>
        <li><strong>90-day free trial</strong> — the first 90 days are entirely complimentary. No card required. The Firm may cancel at any time during this period with no obligation.</li>
        <li><strong>Founding Firm badge</strong> — displayed on the Firm's directory listing while the Firm remains an active Founding Firm subscriber.</li>
        <li><strong>Ranking boost</strong> — the Firm's listing receives priority placement in the postcode and specialism searches relevant to its practice.</li>
        <li><strong>App Store launch marketing</strong> — subject to App Store approval and successful platform launch, the Firm is featured in screenshots and promotional collateral for the AI Advocate iOS / Android release within 12 months of agreement signing.</li>
        <li><strong>Enhanced revenue-share on direct referrals</strong> — when an AI Advocate user instructs the Firm via the platform and the Firm receives a fee from that user, the Firm retains <strong>70%</strong> of the fee and remits <strong>30%</strong> to AI Advocate as referral commission. This Founding Firm split is locked for the lifetime of the Firm's continuous subscription. AI Advocate's standard (non-Founding) referral commission rate shall not exceed <strong>35%</strong> for a minimum of 24 months from public launch.</li>
        <li><strong>Two-way Lex integration</strong> — clients may share their full AI Advocate chat history with the Firm upon engagement, dramatically reducing initial consultation time.</li>
        <li><strong>Quarterly roadmap input</strong> — a 30-minute call each quarter with the AI Advocate product team.</li>
        <li><strong>Direct success-manager contact</strong> — a named contact at AI Advocate for any service issues; target response within 24 working hours, Monday–Friday.</li>
      </ul>

      <h3 style={{ color: GOLD_DEEP, marginTop: 24 }}>2. THE FIRM'S COMMITMENTS</h3>
      <ul style={{ paddingLeft: 22 }}>
        <li>Maintain a complete firm profile (logo, specialties, opening hours, photo) within the AI Advocate Firm Portal.</li>
        <li>Respond to qualified client invites received via AI Advocate within <strong>48 working hours</strong>.</li>
        <li>Provide a 1–2 sentence testimonial after 60 days of the trial, if it is working for the Firm. The Firm reserves the right to decline if the trial is unsatisfactory.</li>
        <li>Operate in accordance with the regulatory rules applicable to the Firm (SRA / LSS / LSNI).</li>
        <li>Notify AI Advocate within 5 working days of any material change to the Firm's regulatory status.</li>
      </ul>

      <h3 style={{ color: GOLD_DEEP, marginTop: 24 }}>3. TERM AND TERMINATION</h3>
      <p><strong>3.1 Initial term</strong> — 12 months from the date of the first paid month (i.e. after the 90-day trial). Auto-renews monthly thereafter unless terminated.</p>
      <p><strong>3.2 Cancellation</strong> — the Firm may cancel at any time with 30 days' written notice, no fees, no penalty. If cancelled, the Firm's £199 rate is forfeit; re-onboarding would be at then-current public pricing.</p>
      <p><strong>3.3 Termination by AI Advocate</strong> — only for cause (loss of regulatory authorisation, material breach of these terms, or 60+ days of unanswered client invites). 30 days' notice and cure period.</p>
      <p><strong>3.4 £199 rate survival</strong> — provided the Firm has not cancelled or been terminated for cause, the £199 rate remains in force during the Firm's continuous subscription. Binding on AI Advocate Ltd. (Company No. 16612244). In the event of a sale or merger, the successor entity shall honour the Founding Firm rate for the remainder of the Firm's then-current annual term.</p>

      <h3 style={{ color: GOLD_DEEP, marginTop: 24 }}>4. NON-ADVICE POSITIONING</h3>
      <p>4.1 The AI Advocate consumer-facing service provides general legal <em>information</em> only and not advice. AI Advocate is not a regulated provider of legal services in the United Kingdom under the Legal Services Act 2007.</p>
      <p>4.2 Once a user engages the Firm via the AI Advocate platform, the regulated solicitor–client relationship exists solely between the user and the Firm. AI Advocate is not a party to that engagement.</p>
      <p>4.3 The Firm bears full professional responsibility for any advice or representation provided to users referred via the AI Advocate platform. AI Advocate's liability is capped at three months of fees paid by the Firm.</p>

      <h3 style={{ color: GOLD_DEEP, marginTop: 24 }}>5. DATA PROTECTION</h3>
      <p>Both parties act as separate data controllers in respect of their own operations. Where the Firm processes personal data of users introduced via AI Advocate, the Firm is the data controller in respect of that processing. Both parties commit to UK GDPR compliance and to notify each other of any data incident affecting jointly-introduced users within 72 hours.</p>
    </div>
  );
}

// ---------- Main page ----------
export default function FirmSign() {
  const token = useMemo(() => {
    const m = window.location.pathname.match(/^\/firm-sign\/([A-Za-z0-9_-]+)/);
    return m ? m[1] : null;
  }, []);

  const [loading, setLoading] = useState(true);
  const [agreement, setAgreement] = useState(null);
  const [error, setError] = useState("");
  const [signerName, setSignerName] = useState("");
  const [signatureDataUrl, setSignatureDataUrl] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [signedJustNow, setSignedJustNow] = useState(false);

  useEffect(() => {
    if (!token) { setError("Invalid signing link."); setLoading(false); return; }
    axios.get(`${API}/firm-agreements/${token}`)
      .then(r => { setAgreement(r.data); setLoading(false); })
      .catch(e => { setError(e?.response?.data?.detail || "Agreement not found or link expired."); setLoading(false); });
  }, [token]);

  const submit = async () => {
    setError("");
    if (signerName.trim().length < 2) { setError("Please type your full name."); return; }
    if (!signatureDataUrl) { setError("Please draw your signature in the box."); return; }
    if (!accepted) { setError("Please tick the acceptance checkbox."); return; }
    setSubmitting(true);
    try {
      await axios.post(`${API}/firm-agreements/${token}/sign`, {
        firm_signer_name: signerName.trim(),
        firm_signature_data_url: signatureDataUrl,
      });
      setSignedJustNow(true);
      // Refresh agreement so we show the "signed" view
      const r = await axios.get(`${API}/firm-agreements/${token}`);
      setAgreement(r.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not sign. Please try again.");
    } finally { setSubmitting(false); }
  };

  if (loading) {
    return <div style={{ padding: 40, textAlign: "center", color: "#666" }}>Loading agreement…</div>;
  }
  if (error && !agreement) {
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <h2 style={{ color: "#b00" }}>Couldn't load agreement</h2>
        <p>{error}</p>
        <p style={{ color: "#666", fontSize: 13 }}>If you think this is a mistake, contact <a href="mailto:firms@aiadvocate.co.uk">firms@aiadvocate.co.uk</a>.</p>
      </div>
    );
  }

  const isSigned = agreement.status === "signed";

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(180deg, #fdfaf0 0%, #fff 200px)",
      padding: "32px 18px 60px",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      color: INK,
    }}>
      <div style={{ maxWidth: 720, margin: "0 auto", background: "#fff", borderRadius: 16, padding: "32px 28px", boxShadow: "0 8px 32px rgba(0,0,0,0.06)", border: "1px solid #f0e8c8" }}>
        <div style={{ height: 3, background: GOLD, borderRadius: 2, marginBottom: 20 }} />

        <h1 style={{ fontFamily: "'Cinzel', Georgia, serif", color: "#1a1300", letterSpacing: "0.04em", fontSize: 26, margin: "0 0 4px" }}>AI ADVOCATE</h1>
        <div style={{ color: GOLD_DEEP, fontWeight: 600, fontSize: 13, letterSpacing: "0.08em", marginBottom: 6 }}>FOUNDING FIRM AGREEMENT · LIFETIME £199/MO LOCK-IN</div>
        <div style={{ color: "#888", fontSize: 12, marginBottom: 24 }}>
          {isSigned
            ? <>✓ Signed on {(agreement.signed_at || "").slice(0, 10)}</>
            : <>Sent {(agreement.sent_at || "").slice(0, 10)} · Please review &amp; sign below</>
          }
        </div>

        {isSigned ? (
          <div data-testid="firm-sign-success" style={{ background: "#f0fff4", border: "1px solid #4ade80", borderRadius: 10, padding: 20, marginBottom: 18 }}>
            <h2 style={{ color: "#166534", margin: "0 0 8px" }}>{signedJustNow ? "🎉 Agreement signed!" : "Agreement already signed"}</h2>
            <p style={{ margin: 0, color: "#166534", fontSize: 14 }}>
              Signed by <strong>{agreement.firm_signer_name}</strong> for <strong>{agreement.firm_name}</strong>.
              A signed PDF copy has been emailed to <strong>{agreement.contact_email}</strong>.
            </p>
            <div style={{ marginTop: 14 }}>
              <a href={`${API}/firm-agreements/${token}/pdf`} target="_blank" rel="noreferrer"
                 data-testid="firm-sign-download-btn"
                 style={{ background: GOLD, color: "#1a1300", padding: "10px 18px", borderRadius: 8, textDecoration: "none", fontWeight: 700, display: "inline-block" }}>
                Download signed PDF →
              </a>
            </div>
          </div>
        ) : null}

        <AgreementBody firm={agreement} />

        {!isSigned && (
          <div style={{ marginTop: 32, padding: 22, background: "#fff8e1", border: "1px solid #f0d56a", borderRadius: 12 }}>
            <h3 style={{ color: GOLD_DEEP, margin: "0 0 14px" }}>6. SIGNATURES</h3>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginBottom: 14 }}>
              <div>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>For AI Advocate Ltd.</div>
                <div style={{ fontStyle: "italic", color: "#1a1300", padding: "8px 0", borderBottom: "1px solid #c0a04a", minHeight: 28 }}>
                  ✓ Pre-signed
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, marginTop: 6 }}>Samuel Malick</div>
                <div style={{ fontSize: 12, color: "#666" }}>Founder &amp; CEO</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>For {agreement.firm_name}</div>
                <input type="text" data-testid="firm-signer-name" placeholder="Type your full name *"
                       value={signerName} onChange={(e) => setSignerName(e.target.value)}
                       style={{ width: "100%", padding: "8px 0", border: "none", borderBottom: "1px solid #c0a04a", background: "transparent", fontSize: 16, outline: "none", color: "#1a1300" }} />
                <div style={{ fontSize: 13, color: "#1a1300", marginTop: 6 }}>{agreement.contact_name}</div>
                <div style={{ fontSize: 12, color: "#666" }}>{agreement.firm_name}</div>
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>Draw your signature below (mouse or finger):</div>
              <SignatureCanvas onChange={setSignatureDataUrl} width={Math.min(window.innerWidth - 80, 460)} height={130} />
            </div>

            <label style={{ display: "flex", alignItems: "flex-start", gap: 10, marginTop: 18, fontSize: 13.5, lineHeight: 1.5, cursor: "pointer" }}>
              <input type="checkbox" data-testid="firm-accept-checkbox"
                     checked={accepted} onChange={(e) => setAccepted(e.target.checked)}
                     style={{ marginTop: 3 }} />
              <span>I have authority to sign on behalf of <strong>{agreement.firm_name}</strong>. I have read and agree to the Founding Firm Agreement above. My typed name and drawn signature constitute a legally binding electronic signature under the UK Electronic Communications Act 2000 and eIDAS Regulation.</span>
            </label>

            {error && (
              <div data-testid="firm-sign-error" style={{ background: "#fee", border: "1px solid #fcc", color: "#b00", padding: "10px 14px", borderRadius: 8, marginTop: 14, fontSize: 13 }}>{error}</div>
            )}

            <button type="button" onClick={submit} disabled={submitting}
                    data-testid="firm-sign-submit-btn"
                    style={{ marginTop: 22, background: GOLD, color: "#1a1300", border: "none", padding: "14px 32px", borderRadius: 10, fontWeight: 700, fontSize: 15, cursor: submitting ? "wait" : "pointer", width: "100%", opacity: submitting ? 0.7 : 1 }}>
              {submitting ? "Signing…" : "Sign and accept agreement →"}
            </button>
            <div style={{ fontSize: 11, color: "#888", marginTop: 10, textAlign: "center" }}>
              By clicking Sign, your IP address and the time of signing are recorded for audit purposes.
            </div>
          </div>
        )}

        <div style={{ marginTop: 30, paddingTop: 16, borderTop: "1px solid #f0e8c8", fontSize: 11, color: "#888", textAlign: "center" }}>
          AI Advocate Ltd. · ICO Registration ZC158457 · <a href="mailto:firms@aiadvocate.co.uk" style={{ color: GOLD_DEEP }}>firms@aiadvocate.co.uk</a> · Governed by the laws of England &amp; Wales.
        </div>
      </div>
    </div>
  );
}
