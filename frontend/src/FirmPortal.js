import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { X, ArrowLeft, Send, Download, Building2, LogOut, Plus, Copy, Mail, Briefcase, Sparkles, Users, Palette } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const FIRM_TOKEN_KEY = "aa_firm_token";

const fapi = axios.create({ baseURL: API });
const setHdr = (tok) => { if (tok) fapi.defaults.headers.common["Authorization"] = `Bearer ${tok}`; else delete fapi.defaults.headers.common["Authorization"]; };

// =============================== AUTH SCREEN ===============================
function FirmAuth({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [data, setData] = useState({ email: "", password: "", firm_name: "", contact_name: "", country: "GB", city: "", sra_number: "", specialties: "employment" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [forgot, setForgot] = useState({ open: false, email: "", sent: false, busy: false });

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const body = mode === "login"
        ? { email: data.email, password: data.password }
        : { ...data, specialties: data.specialties.split(",").map(s => s.trim()).filter(Boolean) };
      const { data: resp } = await fapi.post(`/firm/${mode === "login" ? "login" : "signup"}`, body);
      localStorage.setItem(FIRM_TOKEN_KEY, resp.access_token);
      setHdr(resp.access_token);
      onLogin(resp.firm);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Failed.");
    } finally { setBusy(false); }
  };

  const submitForgot = async () => {
    setForgot(f => ({ ...f, busy: true }));
    try {
      await fapi.post("/firm/forgot-password", { email: forgot.email.trim() });
    } catch { /* always 200 */ }
    setForgot(f => ({ ...f, busy: false, sent: true }));
  };

  return (
    <div style={{ minHeight: "100dvh", background: "#000", color: "#fff", display: "flex", flexDirection: "column", alignItems: "center", padding: "60px 20px" }}>
      <div style={{ fontFamily: "Cinzel, serif", fontSize: 32, color: "#f7c948", letterSpacing: "0.08em", marginBottom: 8 }}>AI ADVOCATE</div>
      <div style={{ fontSize: 12, color: "#888", marginBottom: 32, letterSpacing: "0.2em" }}>FIRM PORTAL</div>

      <div style={{ width: "100%", maxWidth: 420, background: "#0c0c0c", border: "1px solid #222", borderRadius: 14, padding: 24 }}>
        <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
          <button data-testid="firm-mode-login" onClick={() => setMode("login")} style={{ flex: 1, padding: 10, background: mode === "login" ? "#f7c948" : "transparent", color: mode === "login" ? "#000" : "#f7c948", border: "1px solid #f7c948", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>Sign in</button>
          <button data-testid="firm-mode-signup" onClick={() => setMode("signup")} style={{ flex: 1, padding: 10, background: mode === "signup" ? "#f7c948" : "transparent", color: mode === "signup" ? "#000" : "#f7c948", border: "1px solid #f7c948", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>Register firm</button>
        </div>

        {mode === "signup" && (
          <>
            <input data-testid="firm-input-name" placeholder="Firm name" value={data.firm_name} onChange={(e) => setData({ ...data, firm_name: e.target.value })} style={inp} />
            <input data-testid="firm-input-contact" placeholder="Your name (primary contact)" value={data.contact_name} onChange={(e) => setData({ ...data, contact_name: e.target.value })} style={inp} />
            <input data-testid="firm-input-sra" placeholder="SRA number (optional)" value={data.sra_number} onChange={(e) => setData({ ...data, sra_number: e.target.value })} style={inp} />
            <input data-testid="firm-input-city" placeholder="City" value={data.city} onChange={(e) => setData({ ...data, city: e.target.value })} style={inp} />
            <input data-testid="firm-input-spec" placeholder="Specialties (comma-separated)" value={data.specialties} onChange={(e) => setData({ ...data, specialties: e.target.value })} style={inp} />
          </>
        )}
        <input data-testid="firm-input-email" placeholder="Email" type="email" value={data.email} onChange={(e) => setData({ ...data, email: e.target.value })} style={inp} />
        <input data-testid="firm-input-pwd" placeholder="Password" type="password" value={data.password} onChange={(e) => setData({ ...data, password: e.target.value })} style={inp} />

        {err && <div style={{ color: "#fca5a5", fontSize: 12, marginBottom: 10 }} data-testid="firm-auth-err">{err}</div>}

        <button data-testid="firm-auth-submit" onClick={submit} disabled={busy} style={{ width: "100%", padding: 12, background: "linear-gradient(135deg,#f7c948,#d6a017)", color: "#1a1300", border: "none", borderRadius: 10, fontWeight: 700, fontSize: 14, cursor: "pointer", marginTop: 6 }}>
          {busy ? "…" : (mode === "login" ? "Sign in" : "Create firm account")}
        </button>

        {mode === "login" && (
          <button type="button" data-testid="firm-forgot-link"
                  onClick={() => setForgot({ open: true, email: data.email, sent: false, busy: false })}
                  style={{ width: "100%", marginTop: 10, background: "transparent", border: "none", color: "#f7c948", fontSize: 12.5, cursor: "pointer", textDecoration: "underline" }}>
            Forgot password?
          </button>
        )}

        <div style={{ marginTop: 16, fontSize: 11, color: "#888", textAlign: "center", lineHeight: 1.5 }}>
          Need help? <a href="mailto:admin@aiadvocate.co.uk" style={{ color: "#f7c948" }}>admin@aiadvocate.co.uk</a>
        </div>
      </div>

      <a href="/" style={{ marginTop: 24, fontSize: 12, color: "#888" }}>← Back to consumer app</a>

      {forgot.open && (
        <div onClick={() => setForgot({ open: false, email: "", sent: false, busy: false })}
             style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ width: "100%", maxWidth: 420, background: "#0c0c0c", border: "1px solid #222", borderRadius: 14, padding: 24, color: "#fff" }}>
            <h3 style={{ fontFamily: "Cinzel, serif", color: "#f7c948", fontSize: 18, margin: "0 0 12px" }}>Reset firm password</h3>
            {!forgot.sent ? (
              <>
                <p style={{ fontSize: 13, color: "#888", margin: "0 0 14px", lineHeight: 1.55 }}>
                  Enter the email registered to your firm account. We'll send a secure reset link that expires in 60 minutes.
                </p>
                <input data-testid="firm-forgot-email" type="email" placeholder="firm@example.co.uk" autoFocus
                       value={forgot.email}
                       onChange={(e) => setForgot(f => ({ ...f, email: e.target.value }))}
                       onKeyDown={(e) => e.key === "Enter" && forgot.email.trim() && submitForgot()}
                       style={inp} />
                <button data-testid="firm-forgot-submit" onClick={submitForgot}
                        disabled={forgot.busy || !forgot.email.trim()}
                        style={{ width: "100%", padding: 12, background: "linear-gradient(135deg,#f7c948,#d6a017)", color: "#1a1300", border: "none", borderRadius: 10, fontWeight: 700, fontSize: 14, cursor: "pointer" }}>
                  {forgot.busy ? "…" : "Send reset link"}
                </button>
              </>
            ) : (
              <>
                <p style={{ fontSize: 13, color: "#fff", margin: "0 0 14px", lineHeight: 1.55 }}>
                  If an account exists for <strong>{forgot.email}</strong>, a reset link has been sent. Check your inbox (and spam folder).
                </p>
                <button onClick={() => setForgot({ open: false, email: "", sent: false, busy: false })}
                        style={{ width: "100%", padding: 12, background: "transparent", color: "#f7c948", border: "1px solid #f7c948", borderRadius: 10, fontWeight: 700, fontSize: 14, cursor: "pointer" }}>
                  Got it
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const inp = { width: "100%", padding: "10px 12px", background: "#080808", border: "1px solid #222", borderRadius: 8, color: "#fff", fontSize: 13, marginBottom: 10, boxSizing: "border-box" };

// =============================== DASHBOARD ===============================
function FirmDashboard({ firm, onLogout }) {
  const [engagements, setEngagements] = useState([]);
  const [tier, setTier] = useState("free");
  const [limit, setLimit] = useState(0);
  const [activeCount, setActiveCount] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [activeEng, setActiveEng] = useState(null);
  const [showBilling, setShowBilling] = useState(false);
  const [showBranding, setShowBranding] = useState(false);
  const [showSeats, setShowSeats] = useState(false);
  const [branding, setBranding] = useState({ logo_url: "", brand_color: "", accent_color: "", tier_allows: false });

  const load = async () => {
    try {
      const { data } = await fapi.get("/firm/engagements");
      setEngagements(data.engagements || []);
      setTier(data.tier); setLimit(data.limit); setActiveCount(data.active_count);
    } catch (e) { /* no-op */ }
    try {
      const { data } = await fapi.get("/firm/branding");
      setBranding(data || branding);
    } catch (e) { /* no-op */ }
  };
  useEffect(() => { load(); }, []);

  if (activeEng) return <FirmEngagementThread engagement={activeEng} onBack={() => { setActiveEng(null); load(); }} branding={branding} />;

  const canInvite = limit > 0;
  const brandPrimary = branding.brand_color || "#f7c948";
  const brandAccent = branding.accent_color || "#d4af37";

  return (
    <div style={shell}>
      <header style={{ ...hdr, borderBottom: `2px solid ${brandPrimary}` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {branding.logo_url ? (
            <img src={branding.logo_url} alt={firm.firm_name} style={{ height: 38, width: "auto", borderRadius: 4 }}
                 onError={(e) => { e.target.style.display = "none"; }} />
          ) : null}
          <div>
            <div style={{ fontFamily: "Cinzel, serif", fontSize: 18, color: brandPrimary }}>{firm.firm_name}</div>
            <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>
              {firm.email} · Plan: <span style={{ color: brandPrimary, textTransform: "uppercase" }}>{tier}</span>
              {firm.acting_user ? <> · Signed in as <strong>{firm.acting_user.full_name || firm.acting_user.email}</strong></> : null}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button data-testid="firm-seats-btn" onClick={() => setShowSeats(true)} style={btnGhost}><Users size={14} /> Seats</button>
          <button data-testid="firm-branding-btn" onClick={() => setShowBranding(true)} style={btnGhost}><Palette size={14} /> Branding</button>
          <button data-testid="firm-billing-btn" onClick={() => setShowBilling(true)} style={btnGhost}><Sparkles size={14} /> Plan</button>
          <button data-testid="firm-logout-btn" onClick={onLogout} style={btnGhost}><LogOut size={14} /></button>
        </div>
      </header>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 20px" }}>
        {/* 🎁 Trial banner — shows when the firm is on a comped/auto trial */}
        {firm.trial_active && firm.trial_days_remaining !== undefined && (
          <div data-testid="firm-trial-banner" style={{
            background: "linear-gradient(135deg, rgba(247,201,72,0.18), rgba(247,201,72,0.05))",
            border: "1px solid #f7c948", borderRadius: 14, padding: 14, marginBottom: 18,
            display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
          }}>
            <div style={{ fontSize: 28 }}>🎁</div>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ color: "#f7c948", fontWeight: 700, fontSize: 14, marginBottom: 3 }}>
                You're on a free <span style={{ textTransform: "uppercase" }}>{firm.trial_tier || "featured"}</span> trial
              </div>
              <div style={{ color: "#ddd", fontSize: 12.5, lineHeight: 1.5 }}>
                {firm.trial_days_remaining > 0
                  ? <><strong style={{ color: firm.trial_days_remaining < 7 ? "#fca5a5" : "#f7c948" }}>{firm.trial_days_remaining} day{firm.trial_days_remaining === 1 ? "" : "s"} remaining</strong> — convert to lock in this tier&apos;s pricing.</>
                  : <><strong style={{ color: "#fca5a5" }}>Trial ends in less than 24 hours.</strong> Convert now to keep your leads.</>}
              </div>
            </div>
            <button data-testid="firm-trial-upgrade-btn" onClick={() => setShowBilling(true)}
              style={{ background: "#f7c948", color: "#0a0a0a", border: "none", borderRadius: 10, padding: "9px 16px", fontSize: 12.5, fontWeight: 700, cursor: "pointer" }}>
              Convert &amp; lock in
            </button>
          </div>
        )}

        {/* Engagement quota meter */}
        <div style={{ background: "#0c0c0c", border: "1px solid #222", borderRadius: 14, padding: 16, marginBottom: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div>
              <div style={{ fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 2 }}>Active engagements</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#fff" }}>{activeCount} <span style={{ color: "#666", fontWeight: 400, fontSize: 14 }}>/ {limit === 999999 ? "∞" : limit}</span></div>
            </div>
            <button data-testid="firm-new-eng-btn" disabled={!canInvite || activeCount >= limit} onClick={() => setShowCreate(true)}
                    style={{ ...btnGold, opacity: canInvite && activeCount < limit ? 1 : 0.4 }}>
              <Plus size={14} /> Invite a client
            </button>
          </div>
          {!canInvite && (
            <div style={{ fontSize: 12, color: "#fca5a5", marginTop: 6 }}>
              Upgrade to <strong>Premium</strong> or <strong>Practice</strong> to invite clients. <button onClick={() => setShowBilling(true)} style={{ background: "none", border: "none", color: "#f7c948", cursor: "pointer", padding: 0, textDecoration: "underline" }}>View plans</button>
            </div>
          )}
        </div>

        {/* Engagements list */}
        <h2 style={{ fontSize: 14, color: "#f7c948", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 10 }}>Your engagements</h2>
        {engagements.length === 0 ? (
          <div style={{ textAlign: "center", color: "#666", padding: 40, border: "1px dashed #222", borderRadius: 12 }}>
            <Briefcase size={36} style={{ opacity: 0.3, marginBottom: 10 }} />
            <div style={{ fontSize: 13 }}>No engagements yet. Invite your first client above.</div>
          </div>
        ) : engagements.map(e => (
          <button key={e.id} data-testid={`firm-eng-${e.id}`} onClick={() => setActiveEng(e)} style={engRow}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
              <div style={{ fontWeight: 600, color: "#fff" }}>{e.client_email_invited || "—"}</div>
              <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", padding: "2px 8px", borderRadius: 6,
                background: e.status === "active" ? "rgba(34,197,94,0.15)" : e.status === "closed" ? "rgba(239,68,68,0.12)" : "rgba(247,201,72,0.15)",
                color: e.status === "active" ? "#86efac" : e.status === "closed" ? "#fca5a5" : "#f7c948",
              }}>{e.status}</span>
            </div>
            <div style={{ fontSize: 12, color: "#888" }}>Matter: {e.matter}</div>
            {e.case_summary && <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>{e.case_summary.slice(0, 140)}{e.case_summary.length > 140 ? "…" : ""}</div>}
            {e.invite_token && e.status === "invited" && (
              <div style={{ fontSize: 11, color: "#f7c948", marginTop: 6 }}>
                Invite link ready · <code style={{ background: "#1a1a1a", padding: "1px 6px", borderRadius: 4 }}>/engage/{e.invite_token.slice(0, 10)}…</code>
              </div>
            )}
          </button>
        ))}
      </div>

      {showCreate && <NewEngagementModal onClose={() => setShowCreate(false)} onCreated={async () => { setShowCreate(false); await load(); }} />}
      {showBilling && <BillingModal firmEmail={firm.email} currentTier={tier} onClose={() => setShowBilling(false)} />}
      {showBranding && <BrandingModal initial={branding} tier={tier} firmName={firm.firm_name}
                                       onClose={() => setShowBranding(false)}
                                       onSaved={(b) => { setBranding(b); }} />}
      {showSeats && <SeatsModal tier={tier} firmName={firm.firm_name}
                                onClose={() => setShowSeats(false)} />}
    </div>
  );
}

function NewEngagementModal({ onClose, onCreated }) {
  const [data, setData] = useState({ client_email: "", matter: "Employment", case_summary: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [created, setCreated] = useState(null);

  const submit = async () => {
    setBusy(true); setErr("");
    try {
      const { data: r } = await fapi.post("/firm/engagements", data);
      setCreated(r);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Failed.");
    } finally { setBusy(false); }
  };

  if (created) {
    return (
      <div style={overlay}>
        <div style={{ ...modalCard }}>
          <h3 style={modalTitle}>Invite created</h3>
          <p style={{ fontSize: 13, color: "#aaa", marginBottom: 14 }}>Send this link to your client. They'll be prompted to sign in (or create an AI Advocate account) and accept.</p>
          <div style={{ background: "#080808", border: "1px solid #222", borderRadius: 8, padding: 12, marginBottom: 12, wordBreak: "break-all", fontSize: 12, color: "#f7c948" }}>{created.invite_url}</div>
          <div style={{ display: "flex", gap: 8 }}>
            <button data-testid="copy-invite" onClick={() => { navigator.clipboard.writeText(created.invite_url); }} style={btnGold}><Copy size={14} /> Copy link</button>
            <a data-testid="email-invite" href={`mailto:?subject=Secure%20case%20portal%20via%20AI%20Advocate&body=${encodeURIComponent(`I've set up a secure shared case file for you in AI Advocate. Please open this link to accept:\n\n${created.invite_url}\n\nAll messages and documents we exchange there are end-to-end encrypted.`)}`}
               style={btnGhost}><Mail size={14} /> Email it</a>
          </div>
          <button onClick={() => onCreated()} style={{ ...btnGhost, width: "100%", marginTop: 14 }}>Done</button>
        </div>
      </div>
    );
  }

  return (
    <div style={overlay}>
      <div style={modalCard}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h3 style={modalTitle}>New engagement</h3>
          <button onClick={onClose} style={btnPlain}><X size={18} /></button>
        </div>
        <input data-testid="new-eng-email" placeholder="Client email (we'll lock the invite to this address)" value={data.client_email} onChange={(e) => setData({ ...data, client_email: e.target.value })} style={inp} />
        <input data-testid="new-eng-matter" placeholder="Matter (e.g. Employment, Property)" value={data.matter} onChange={(e) => setData({ ...data, matter: e.target.value })} style={inp} />
        <textarea data-testid="new-eng-summary" placeholder="Brief case summary (optional, end-to-end encrypted)" rows={3} value={data.case_summary} onChange={(e) => setData({ ...data, case_summary: e.target.value })} style={{ ...inp, resize: "vertical" }} />
        {err && <div style={{ color: "#fca5a5", fontSize: 12, marginBottom: 10 }} data-testid="new-eng-err">{err}</div>}
        <button data-testid="new-eng-create" onClick={submit} disabled={busy || !data.client_email} style={{ ...btnGold, width: "100%" }}>
          {busy ? "Creating…" : "Create engagement & generate invite"}
        </button>
      </div>
    </div>
  );
}

function FirmEngagementThread({ engagement, onBack }) {
  const [messages, setMessages] = useState([]);
  const [files, setFiles] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [lexOut, setLexOut] = useState("");
  const messagesEndRef = useRef(null);
  const eid = engagement.id;
  const isClosed = engagement.status === "closed";

  const load = async () => {
    try {
      const [m, f] = await Promise.all([
        fapi.get(`/engagements/${eid}/messages`),
        fapi.get(`/engagements/${eid}/files`),
      ]);
      setMessages(m.data.messages || []);
      setFiles(f.data.files || []);
    } catch (e) { /* no-op */ }
  };
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length]);

  const send = async () => {
    if (!draft.trim() || isClosed) return;
    setBusy(true);
    try { await fapi.post(`/engagements/${eid}/messages`, { body: draft.trim() }); setDraft(""); setLexOut(""); await load(); }
    catch (e) { alert(e?.response?.data?.detail || "Failed."); }
    finally { setBusy(false); }
  };

  const askLex = async (kind) => {
    setBusy(true); setLexOut("");
    try {
      const { data } = await fapi.post(`/engagements/${eid}/lex-assist`, { kind });
      setLexOut(data.output || "");
      if (kind === "draft_reply") setDraft(data.output || "");
    } catch (e) { alert("Lex temporarily unavailable."); }
    finally { setBusy(false); }
  };

  const close = async () => {
    if (!window.confirm("Close this engagement? Both parties can still read the thread but cannot send new messages or files.")) return;
    try { await fapi.patch(`/engagements/${eid}/close`); onBack(); }
    catch (e) { alert("Failed to close."); }
  };

  return (
    <div style={shell}>
      <header style={hdr}>
        <button onClick={onBack} data-testid="firm-thread-back" style={{ ...btnGhost, gap: 6 }}><ArrowLeft size={14} /> Engagements</button>
        <div style={{ flex: 1, textAlign: "center", color: "#f7c948", fontFamily: "Cinzel, serif" }}>
          {engagement.client_email_invited || engagement.client_user_id} · {engagement.matter}
        </div>
        {!isClosed && <button data-testid="firm-close-eng" onClick={close} style={{ ...btnGhost, color: "#fca5a5", borderColor: "#7f1d1d" }}>Close</button>}
      </header>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "20px 20px 80px", display: "flex", flexDirection: "column", height: "calc(100dvh - 64px)" }}>
        <div style={{ flex: 1, overflowY: "auto" }}>
          {messages.map(m => (
            <div key={m.id} data-testid={`firm-msg-${m.id}`} style={{ display: "flex", justifyContent: m.sender_kind === "firm" ? "flex-end" : "flex-start", marginBottom: 10 }}>
              <div style={{
                maxWidth: "76%", padding: "10px 14px", borderRadius: 14,
                background: m.sender_kind === "firm" ? "linear-gradient(135deg,#d6a017,#b88a1e)" : "#1a1a1a",
                border: m.sender_kind === "firm" ? "none" : "1px solid #2a2a2a",
                color: m.sender_kind === "firm" ? "#1a1300" : "#eee",
                fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap",
              }}>
                {m.body}
                <div style={{ fontSize: 10, opacity: 0.7, marginTop: 4 }}>{m.sender_kind === "firm" ? "You" : "Client"} · {new Date(m.created_at).toLocaleString()}</div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {files.length > 0 && (
          <div style={{ background: "#0c0c0c", border: "1px solid #f7c94833", borderRadius: 10, padding: 10, marginTop: 8 }}>
            <div style={{ fontSize: 10, color: "#f7c948", fontWeight: 700, marginBottom: 6, textTransform: "uppercase" }}>📎 Shared files ({files.length})</div>
            {files.map(f => (
              <div key={f.id} style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "3px 0", color: "#ddd" }}>
                <span>{f.title} <span style={{ color: "#666", fontSize: 10 }}>({Math.round(f.size_bytes / 1024)} KB · from {f.uploader_kind})</span></span>
                <button onClick={async () => {
                  try {
                    const { data } = await fapi.get(`/engagements/${eid}/files/${f.id}`);
                    const blob = new Blob([Uint8Array.from(atob(data.file_b64), c => c.charCodeAt(0))], { type: data.mime_type });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a"); a.href = url; a.download = f.title; document.body.appendChild(a); a.click();
                    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
                  } catch (e) { alert("Download failed"); }
                }} style={{ ...btnPlain, color: "#f7c948" }}><Download size={12} /></button>
              </div>
            ))}
          </div>
        )}

        {lexOut && (
          <div style={{ marginTop: 8, padding: 10, background: "#f7c94815", border: "1px solid #f7c94855", borderRadius: 10 }}>
            <div style={{ fontSize: 10, color: "#f7c948", fontWeight: 700, marginBottom: 6, textTransform: "uppercase" }}>🤖 Lex</div>
            <div style={{ fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap", color: "#eee" }}>{lexOut}</div>
            <button onClick={() => setLexOut("")} style={{ background: "transparent", border: "none", color: "#888", fontSize: 11, marginTop: 6, cursor: "pointer" }}>Dismiss</button>
          </div>
        )}

        {!isClosed && (
          <>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button data-testid="firm-lex-draft" onClick={() => askLex("draft_reply")} disabled={busy} style={btnGhost}>✨ Draft reply</button>
              <button data-testid="firm-lex-sum" onClick={() => askLex("summarise")} disabled={busy} style={btnGhost}>📋 Summary</button>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <textarea data-testid="firm-thread-input" rows={2} value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Type a message to your client…" style={{ ...inp, marginBottom: 0, resize: "none" }} />
              <button data-testid="firm-thread-send" onClick={send} disabled={busy || !draft.trim()} style={{ ...btnGold, alignSelf: "flex-end" }}><Send size={14} /></button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function BillingModal({ firmEmail, currentTier, onClose }) {
  const [busy, setBusy] = useState("");
  const plans = [
    { id: "featured", name: "Featured", price: "£49 /mo", desc: "Top-of-list directory placement + sponsored badge", features: ["Priority directory listing", "Sponsored gold badge", "Direct client enquiries"] },
    { id: "premium",  name: "Premium",  price: "£199 /mo", desc: "Listing + secure client portal + Lex AI", features: ["Everything in Featured", "Up to 25 active client engagements", "Encrypted case threads + shared files", "Lex AI: 100 assists/mo", "Verified badge"] },
    { id: "practice", name: "Practice", price: "£399 /mo", desc: "Unlimited engagements + multi-user + priority support", features: ["Everything in Premium", "Unlimited active engagements", "Up to 5 lawyer seats", "Lex AI: 1,000 assists/mo", "Priority support"] },
  ];
  const checkout = async (id) => {
    setBusy(id);
    try {
      const { data } = await fapi.post(`/firm/subscribe?plan=${id}`);
      if (data.checkout_url) window.location.href = data.checkout_url;
    } catch (e) { alert(e?.response?.data?.detail || "Billing not yet configured. Email admin@aiadvocate.co.uk."); }
    finally { setBusy(""); }
  };
  return (
    <div style={overlay}>
      <div style={{ ...modalCard, maxWidth: 880 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <h3 style={modalTitle}>Firm plans</h3>
          <button onClick={onClose} style={btnPlain}><X size={18} /></button>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
          {plans.map(p => (
            <div key={p.id} data-testid={`firm-plan-${p.id}`} style={{ background: "#080808", border: currentTier === p.id ? "2px solid #f7c948" : "1px solid #222", borderRadius: 12, padding: 16, position: "relative" }}>
              {currentTier === p.id && <span style={{ position: "absolute", top: -10, left: 12, background: "#f7c948", color: "#1a1300", fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 6, textTransform: "uppercase" }}>Your plan</span>}
              <div style={{ fontFamily: "Cinzel, serif", fontSize: 18, color: "#f7c948", marginBottom: 4 }}>{p.name}</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: "#fff", marginBottom: 6 }}>{p.price}</div>
              <div style={{ fontSize: 11, color: "#888", marginBottom: 12, lineHeight: 1.4 }}>{p.desc}</div>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", marginBottom: 14, fontSize: 12, color: "#ccc" }}>
                {p.features.map((f, i) => <li key={i} style={{ padding: "3px 0" }}>✓ {f}</li>)}
              </ul>
              <button data-testid={`firm-plan-${p.id}-cta`} disabled={busy || currentTier === p.id} onClick={() => checkout(p.id)} style={{ ...btnGold, width: "100%", opacity: currentTier === p.id ? 0.5 : 1 }}>
                {busy === p.id ? "…" : currentTier === p.id ? "Current plan" : "Choose plan"}
              </button>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 11, color: "#666", textAlign: "center", marginTop: 14 }}>Cancel anytime. Powered by Stripe. £{firmEmail ? "" : ""}</div>
      </div>
    </div>
  );
}

// =============================== BRANDING MODAL + PREVIEW ===============================
// Lets firms upload logo URL + colors, see live preview in a sample engagement chat.
// Tier-gated to Premium/Practice — Featured users see an upgrade nudge instead.
function BrandingModal({ initial, tier, firmName, onClose, onSaved }) {
  const [logoUrl, setLogoUrl] = useState(initial.logo_url || "");
  const [brandColor, setBrandColor] = useState(initial.brand_color || "#1a4d8f");
  const [accentColor, setAccentColor] = useState(initial.accent_color || "#f7c948");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [savedMsg, setSavedMsg] = useState("");
  const fileInputRef = useRef(null);

  const canEdit = ["premium", "practice"].includes(tier);

  // 📷 Pick logo from device — converts to a base64 data: URL the backend stores directly.
  // Keeps the flow dead-simple for non-technical firm owners (no hosting / URL fiddling).
  const handleLogoFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file (PNG, JPG, or SVG)."); return;
    }
    if (file.size > 500 * 1024) {
      setError("Image is too large (max 500KB). Please pick a smaller logo."); return;
    }
    const reader = new FileReader();
    reader.onload = () => setLogoUrl(String(reader.result || ""));
    reader.onerror = () => setError("Could not read that image — try another file.");
    reader.readAsDataURL(file);
  };

  const save = async () => {
    setError(""); setSavedMsg(""); setSaving(true);
    try {
      const { data } = await fapi.patch("/firm/branding", { logo_url: logoUrl, brand_color: brandColor, accent_color: accentColor });
      setSavedMsg("✓ Branding updated. Clients will see this in their engagement chats.");
      onSaved && onSaved({ logo_url: data.logo_url ?? logoUrl, brand_color: data.brand_color ?? brandColor, accent_color: data.accent_color ?? accentColor, tier_allows: true });
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to save");
    } finally { setSaving(false); }
  };

  return (
    <div style={overlay} onClick={onClose} data-testid="branding-modal">
      <div style={{ ...modalCard, maxWidth: 720 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <h3 style={modalTitle}><Palette size={18} style={{ verticalAlign: -3, marginRight: 6 }} />Custom branding</h3>
          <button onClick={onClose} style={btnPlain}><X size={18} /></button>
        </div>

        {!canEdit && (
          <div data-testid="branding-tier-gate" style={{
            background: "rgba(247,201,72,0.10)", border: "1px solid #f7c948",
            color: "#f7c948", padding: 12, borderRadius: 10, marginBottom: 14, fontSize: 13,
          }}>
            ⚡ Custom branding is unlocked on <strong>Premium (£199/mo)</strong> and <strong>Practice (£399/mo)</strong>.
            Make every client engagement feel like <em>your</em> firm, not generic.
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
          {/* Inputs */}
          <div>
            <label style={lbl}>Company logo</label>
            <div data-testid="branding-logo-uploader"
                 style={{ display: "flex", gap: 10, alignItems: "center",
                          padding: 12, background: "rgba(255,255,255,0.02)",
                          border: "1px dashed #3a3a3a", borderRadius: 10 }}>
              {logoUrl ? (
                <img src={logoUrl} alt="Logo preview"
                     style={{ width: 56, height: 56, objectFit: "contain",
                              background: "#fff", borderRadius: 8, padding: 4,
                              border: "1px solid #2a2a2a" }} />
              ) : (
                <div style={{ width: 56, height: 56, borderRadius: 8,
                              background: "rgba(247,201,72,0.08)",
                              border: "1px dashed #5a4a1a", display: "flex",
                              alignItems: "center", justifyContent: "center",
                              color: "#f7c948", fontSize: 22 }}>📷</div>
              )}
              <div style={{ flex: 1, minWidth: 0 }}>
                <input ref={fileInputRef} type="file"
                       accept="image/png,image/jpeg,image/svg+xml,image/webp"
                       onChange={handleLogoFile} disabled={!canEdit}
                       data-testid="branding-logo-file" style={{ display: "none" }} />
                <button type="button" disabled={!canEdit}
                        data-testid="branding-logo-pick-btn"
                        onClick={() => fileInputRef.current?.click()}
                        style={{ ...btnGold, padding: "8px 14px", fontSize: 13,
                                 opacity: !canEdit ? 0.5 : 1 }}>
                  {logoUrl ? "Change logo" : "Choose from phone"}
                </button>
                {logoUrl && (
                  <button type="button" disabled={!canEdit}
                          data-testid="branding-logo-remove-btn"
                          onClick={() => { setLogoUrl(""); if (fileInputRef.current) fileInputRef.current.value = ""; }}
                          style={{ ...btnPlain, marginLeft: 8, fontSize: 12, color: "#fca5a5" }}>
                    Remove
                  </button>
                )}
                <div style={{ fontSize: 11, color: "#888", marginTop: 6 }}>
                  PNG, JPG or SVG · max 500KB
                </div>
              </div>
            </div>

            <label style={{ ...lbl, marginTop: 12 }}>Primary brand colour</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input data-testid="branding-color-picker" disabled={!canEdit} type="color"
                     value={brandColor} onChange={(e) => setBrandColor(e.target.value)}
                     style={{ width: 50, height: 38, padding: 2, background: "transparent", border: "1px solid #2a2a2a", borderRadius: 6 }} />
              <input data-testid="branding-color-text" disabled={!canEdit} value={brandColor}
                     onChange={(e) => setBrandColor(e.target.value)} style={{ ...inp, flex: 1 }} />
            </div>

            <label style={{ ...lbl, marginTop: 12 }}>Accent colour (optional)</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input disabled={!canEdit} type="color" value={accentColor}
                     onChange={(e) => setAccentColor(e.target.value)}
                     style={{ width: 50, height: 38, padding: 2, background: "transparent", border: "1px solid #2a2a2a", borderRadius: 6 }} />
              <input disabled={!canEdit} value={accentColor}
                     onChange={(e) => setAccentColor(e.target.value)} style={{ ...inp, flex: 1 }} />
            </div>

            {error && <div style={{ color: "#fca5a5", fontSize: 12, marginTop: 10 }}>{error}</div>}
            {savedMsg && <div style={{ color: "#86efac", fontSize: 12, marginTop: 10 }}>{savedMsg}</div>}

            <button data-testid="branding-save-btn" disabled={!canEdit || saving} onClick={save}
                    style={{ ...btnGold, width: "100%", marginTop: 14, opacity: !canEdit || saving ? 0.5 : 1 }}>
              {saving ? "Saving…" : "Save branding"}
            </button>
          </div>

          {/* Live preview */}
          <div data-testid="branding-preview">
            <div style={{ fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>
              Live preview — what your clients will see
            </div>
            <div style={{
              border: `2px solid ${brandColor}`, borderRadius: 12, overflow: "hidden",
              background: "#fff", color: "#111", fontFamily: "system-ui",
            }}>
              {/* Preview header */}
              <div style={{ background: brandColor, color: "#fff", padding: "12px 14px",
                            display: "flex", alignItems: "center", gap: 10 }}>
                {logoUrl ? (
                  <img src={logoUrl} alt="logo"
                       style={{ height: 30, width: "auto", background: "#fff", borderRadius: 4, padding: 3 }}
                       onError={(e) => { e.target.style.display = "none"; }} />
                ) : (
                  <div style={{ width: 30, height: 30, background: "rgba(255,255,255,0.2)",
                                borderRadius: 4, display: "flex", alignItems: "center", justifyContent: "center",
                                fontSize: 11, fontWeight: 700 }}>{(firmName || "F")[0]}</div>
                )}
                <div style={{ fontSize: 13, fontWeight: 700 }}>{firmName || "Your Firm"}</div>
              </div>
              {/* Preview body — sample engagement chat */}
              <div style={{ padding: 14, fontSize: 12.5, lineHeight: 1.5, maxHeight: 240, overflow: "auto" }}>
                <div style={{ background: "#f3f3f5", padding: 8, borderRadius: 10,
                              borderLeft: `3px solid ${brandColor}`, marginBottom: 8 }}>
                  <div style={{ fontWeight: 700, fontSize: 11, color: brandColor, marginBottom: 3 }}>Client · Sarah</div>
                  Hi — I had a question about my deposit. My landlord won't return it after I moved out 6 weeks ago.
                </div>
                <div style={{ background: brandColor, color: "#fff", padding: 8, borderRadius: 10, marginBottom: 8,
                              alignSelf: "flex-end", marginLeft: 30 }}>
                  <div style={{ fontWeight: 700, fontSize: 11, color: accentColor, marginBottom: 3 }}>{firmName || "Your Firm"} · Reply</div>
                  Hi Sarah — happy to help. Under the Housing Act 2004, your deposit must be returned within 10 days of agreement. Was the deposit protected in TDS, DPS or MyDeposits?
                </div>
                <button style={{
                  background: brandColor, color: "#fff", border: "none",
                  padding: "8px 14px", borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: "default",
                }}>Reply now</button>
              </div>
              <div style={{ background: "#f9f9fb", borderTop: "1px solid #e5e5e9",
                            padding: "8px 14px", fontSize: 10, color: "#777", display: "flex",
                            justifyContent: "space-between" }}>
                <span>Powered by AI Advocate</span>
                <span style={{ color: accentColor, fontWeight: 700 }}>Confidential · Encrypted</span>
              </div>
            </div>
            <div style={{ fontSize: 10.5, color: "#666", marginTop: 8, lineHeight: 1.4 }}>
              💡 Tip: upload a square PNG logo (200×200px+) for crisp display. Use your firm's primary
              brand colour for the header; the accent colour highlights names and key links.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================== SEATS MODAL ===============================
// Lets the firm owner / admin invite / list / remove fee-earner seats.
function SeatsModal({ tier, firmName, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [inviteRole, setInviteRole] = useState("fee_earner");
  const [error, setError] = useState("");
  const [lastInvite, setLastInvite] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await fapi.get("/firm/users");
      setData(data);
    } catch (e) { /* no-op */ }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const invite = async (e) => {
    e.preventDefault(); setError(""); setLastInvite(null);
    if (!inviteEmail || !inviteName) { setError("Email and name required"); return; }
    try {
      const { data } = await fapi.post("/firm/users/invite", { email: inviteEmail, full_name: inviteName, role: inviteRole });
      setLastInvite(data);
      setInviteEmail(""); setInviteName("");
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail || "Invite failed");
    }
  };

  const removeUser = async (id) => {
    if (!window.confirm("Remove this fee-earner? They'll lose access immediately.")) return;
    try { await fapi.delete(`/firm/users/${id}`); await load(); }
    catch (e) { setError(e?.response?.data?.detail || "Remove failed"); }
  };

  return (
    <div style={overlay} onClick={onClose} data-testid="seats-modal">
      <div style={modalCard} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          <h3 style={modalTitle}><Users size={18} style={{ verticalAlign: -3, marginRight: 6 }} />Fee-earner seats</h3>
          <button onClick={onClose} style={btnPlain}><X size={18} /></button>
        </div>

        {loading ? (
          <div style={{ color: "#888", fontSize: 13, padding: 20 }}>Loading…</div>
        ) : data ? (
          <>
            <div style={{
              background: "rgba(247,201,72,0.06)", border: "1px solid #2a2a2a", borderRadius: 10,
              padding: 12, fontSize: 12.5, marginBottom: 16, color: "#ddd",
            }}>
              <strong style={{ color: "#f7c948" }}>{data.active_count} / {data.seat_limit}</strong> seats in use on <strong style={{ textTransform: "uppercase" }}>{data.tier}</strong> tier.
              {!data.can_invite_more && (
                <div style={{ marginTop: 6, color: "#fca5a5" }}>Seat limit reached — upgrade your plan to add more fee-earners.</div>
              )}
            </div>

            {/* Seat list */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ ...rowSeat, background: "#0a1f0a", borderColor: "#1f3a1f" }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{data.owner.full_name || data.owner.email}</div>
                  <div style={{ fontSize: 11, color: "#888" }}>{data.owner.email} · OWNER</div>
                </div>
                <span style={pillActive}>Active</span>
              </div>
              {data.users.map((u) => (
                <div key={u.id} style={{
                  ...rowSeat,
                  opacity: u.status === "removed" ? 0.4 : 1,
                  background: u.status === "removed" ? "#1a1a1a" : "#0c0c0c",
                }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{u.full_name}</div>
                    <div style={{ fontSize: 11, color: "#888" }}>
                      {u.email} · {u.role.toUpperCase()}{u.status !== "active" ? ` · ${u.status.toUpperCase()}` : ""}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    {u.status === "active" && <span style={pillActive}>Active</span>}
                    {u.status === "pending" && <span style={pillPending}>Pending</span>}
                    {u.status === "removed" && <span style={pillRemoved}>Removed</span>}
                    {u.status !== "removed" && (
                      <button data-testid={`seat-remove-${u.id}`} onClick={() => removeUser(u.id)}
                              style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: 11 }}>
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Invite new */}
            {data.can_invite_more && (
              <form onSubmit={invite} style={{ background: "#080808", border: "1px solid #1a1a1a", borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: 12, color: "#f7c948", marginBottom: 8, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase" }}>Invite a fee-earner</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
                  <input data-testid="seat-invite-name" placeholder="Full name" value={inviteName}
                         onChange={(e) => setInviteName(e.target.value)} style={inp} required />
                  <input data-testid="seat-invite-email" type="email" placeholder="Email" value={inviteEmail}
                         onChange={(e) => setInviteEmail(e.target.value)} style={inp} required />
                </div>
                <select data-testid="seat-invite-role" value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}
                        style={{ ...inp, marginBottom: 8 }}>
                  <option value="fee_earner">Fee-earner (can handle engagements + Lex)</option>
                  <option value="admin">Admin (also manages users + branding)</option>
                </select>
                <button data-testid="seat-invite-submit" type="submit" style={{ ...btnGold, width: "100%" }}>
                  <Plus size={14} /> Send invitation
                </button>
                {error && <div style={{ color: "#fca5a5", fontSize: 12, marginTop: 8 }}>{error}</div>}
                {lastInvite && (
                  <div data-testid="invite-link-out" style={{
                    background: "rgba(34,197,94,0.10)", border: "1px solid #22c55e",
                    color: "#86efac", borderRadius: 8, padding: 10, marginTop: 10, fontSize: 11.5,
                  }}>
                    ✓ Invitation created. Share this link with them (expires in 14 days):
                    <div style={{ marginTop: 6, display: "flex", gap: 6 }}>
                      <code style={{ flex: 1, background: "#000", padding: "6px 10px", borderRadius: 6,
                                     fontSize: 11, color: "#86efac", wordBreak: "break-all", border: "1px solid #1a3a1a" }}>
                        {lastInvite.invite_url}
                      </code>
                      <button onClick={() => navigator.clipboard.writeText(lastInvite.invite_url)}
                              style={{ ...btnGhost, padding: "6px 10px" }}>
                        <Copy size={12} />
                      </button>
                    </div>
                  </div>
                )}
              </form>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}


// =============================== STYLES ===============================
const shell = { minHeight: "100dvh", background: "#000", color: "#fff", fontFamily: "system-ui, -apple-system, sans-serif" };
const hdr = { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 20px", borderBottom: "1px solid #1a1a1a", background: "#050505", position: "sticky", top: 0, zIndex: 10 };
const btnGold = { display: "inline-flex", alignItems: "center", gap: 6, padding: "9px 14px", background: "linear-gradient(135deg,#f7c948,#d6a017)", color: "#1a1300", border: "none", borderRadius: 8, fontWeight: 700, fontSize: 13, cursor: "pointer" };
const btnGhost = { display: "inline-flex", alignItems: "center", gap: 4, padding: "8px 12px", background: "transparent", border: "1px solid #2a2a2a", color: "#f7c948", borderRadius: 8, fontSize: 12, cursor: "pointer", textDecoration: "none" };
const btnPlain = { background: "transparent", border: "none", color: "#aaa", cursor: "pointer" };
const engRow = { width: "100%", textAlign: "left", background: "#0c0c0c", border: "1px solid #222", borderRadius: 12, padding: 14, marginBottom: 10, cursor: "pointer", color: "#fff", display: "block" };
const overlay = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20, zIndex: 1000 };
const modalCard = { background: "#0c0c0c", border: "1px solid #222", borderRadius: 14, padding: 24, width: "100%", maxWidth: 540, maxHeight: "86dvh", overflow: "auto" };
const modalTitle = { fontFamily: "Cinzel, serif", fontSize: 18, color: "#f7c948", margin: 0 };
const lbl = { display: "block", fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 5, fontWeight: 600 };
const rowSeat = { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", border: "1px solid #1a1a1a", borderRadius: 8, marginBottom: 6 };
const pillActive = { fontSize: 10, fontWeight: 700, textTransform: "uppercase", padding: "3px 8px", borderRadius: 4, background: "rgba(34,197,94,0.15)", color: "#86efac" };
const pillPending = { fontSize: 10, fontWeight: 700, textTransform: "uppercase", padding: "3px 8px", borderRadius: 4, background: "rgba(247,201,72,0.15)", color: "#f7c948" };
const pillRemoved = { fontSize: 10, fontWeight: 700, textTransform: "uppercase", padding: "3px 8px", borderRadius: 4, background: "rgba(239,68,68,0.12)", color: "#fca5a5" };

// =============================== INVITE ACCEPT FLOW ===============================
// Lands the invitee at /firm-accept-invite?token=<token>. They set a password,
// we activate the seat and log them in directly.
function FirmAcceptInvite({ token, onSuccess }) {
  const [password, setPassword] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    if (password.length < 8) { setError("Password must be 8+ characters"); return; }
    if (password !== confirmPw) { setError("Passwords don't match"); return; }
    setBusy(true); setError("");
    try {
      const { data } = await fapi.post("/firm/users/accept", { invite_token: token, password });
      localStorage.setItem(FIRM_TOKEN_KEY, data.access_token);
      setHdr(data.access_token);
      onSuccess(data.firm);
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not accept invitation");
      setBusy(false);
    }
  };

  return (
    <div style={{ ...shell, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 420, background: "#0c0c0c", border: "1px solid #2a2a2a", borderRadius: 16, padding: 28 }}>
        <div style={{ textAlign: "center", marginBottom: 18 }}>
          <Building2 size={36} color="#f7c948" />
          <h2 style={{ fontFamily: "Cinzel, serif", fontSize: 22, color: "#f7c948", margin: "10px 0 4px" }}>Accept your firm invite</h2>
          <p style={{ fontSize: 13, color: "#888", margin: 0 }}>Set a password to activate your seat.</p>
        </div>
        <form onSubmit={submit}>
          <label style={lbl}>New password (8+ chars)</label>
          <input data-testid="invite-password" type="password" value={password}
                 onChange={(e) => setPassword(e.target.value)} required
                 style={{ width: "100%", padding: "10px 12px", background: "#080808", border: "1px solid #222", borderRadius: 8, color: "#fff", fontSize: 13, marginBottom: 10, boxSizing: "border-box" }} />
          <label style={lbl}>Confirm password</label>
          <input data-testid="invite-confirm-password" type="password" value={confirmPw}
                 onChange={(e) => setConfirmPw(e.target.value)} required
                 style={{ width: "100%", padding: "10px 12px", background: "#080808", border: "1px solid #222", borderRadius: 8, color: "#fff", fontSize: 13, marginBottom: 14, boxSizing: "border-box" }} />
          {error && <div style={{ color: "#fca5a5", fontSize: 12, marginBottom: 10 }}>{error}</div>}
          <button data-testid="invite-accept-submit" type="submit" disabled={busy} style={{ ...btnGold, width: "100%" }}>
            {busy ? "Activating…" : "Activate seat & sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}


// =============================== ROOT ===============================
export default function FirmPortal() {
  const [firm, setFirm] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check if user landed via invite link (/firm-accept-invite?token=...)
  const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  const inviteToken = (window.location.pathname || "").includes("firm-accept-invite") ? (params && params.get("token")) : null;

  useEffect(() => {
    if (inviteToken) { setLoading(false); return; }     // skip auto-login on invite path
    const token = localStorage.getItem(FIRM_TOKEN_KEY);
    if (!token) { setLoading(false); return; }
    setHdr(token);
    fapi.get("/firm/me")
      .then(r => setFirm(r.data))
      .catch(() => { localStorage.removeItem(FIRM_TOKEN_KEY); setHdr(null); })
      .finally(() => setLoading(false));
  }, [inviteToken]);

  if (loading) return <div style={{ ...shell, display: "flex", alignItems: "center", justifyContent: "center" }}>Loading…</div>;
  if (inviteToken) return <FirmAcceptInvite token={inviteToken} onSuccess={(f) => {
    window.history.replaceState({}, "", "/firm-portal");
    setFirm(f);
  }} />;
  if (!firm) return <FirmAuth onLogin={(f) => setFirm(f)} />;
  return <FirmDashboard firm={firm} onLogout={() => { localStorage.removeItem(FIRM_TOKEN_KEY); setHdr(null); setFirm(null); }} />;
}
