import { useCallback, useEffect, useState } from "react";

const card = { background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 };
const small = { fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5 };
const err = (e) => { const d = e?.response?.data?.detail; return typeof d === "string" ? d : "Something went wrong."; };

// Password (or an emailed code for Google/Apple accounts) before any security change.
const ConfirmIdentity = ({ st, api, value, onChange }) => {
  const [sent, setSent] = useState("");
  if (st.has_password) {
    return <input className="input" type="password" data-testid="security-password-input" placeholder="Your password"
                  value={value.password || ""} onChange={(e) => onChange({ password: e.target.value })} style={{ marginBottom: 8 }} />;
  }
  return (
    <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
      <input className="input" inputMode="numeric" data-testid="security-reauth-code-input" placeholder="Emailed code"
             value={value.email_code || ""} onChange={(e) => onChange({ email_code: e.target.value })} />
      <button className="btn-ghost" data-testid="security-reauth-send-btn"
              onClick={async () => { try { const { data } = await api.post("/auth/security/reauth-code"); setSent(`Sent to ${data.to}`); } catch (e) { setSent(err(e)); } }}>
        {sent || "Email me a code"}
      </button>
    </div>
  );
};

const RecoveryCodes = ({ codes }) => (
  <div data-testid="security-recovery-codes" style={{ background: "rgba(247,201,72,0.06)", border: "1px solid var(--gold-deep)", borderRadius: 10, padding: 12, marginTop: 10 }}>
    <div style={{ fontWeight: 700, fontSize: 13, color: "var(--gold)", marginBottom: 6 }}>Save your recovery codes</div>
    <div style={small}>Each code works once if you lose your phone. They will not be shown again.</div>
    <div style={{ fontFamily: "monospace", fontSize: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4, marginTop: 8 }}>
      {codes.map((c) => <span key={c}>{c}</span>)}
    </div>
  </div>
);

const AuthenticatorSetup = ({ api, st, onDone, onToken }) => {
  const [idv, setIdv] = useState({});
  const [qr, setQr] = useState(null);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const start = async () => { setMsg(""); try { const { data } = await api.post("/auth/2fa/setup", idv); setQr(data); } catch (e) { setMsg(err(e)); } };
  const verify = async () => {
    setMsg("");
    try { const { data } = await api.post("/auth/2fa/verify", { code }); onToken(data.access_token); onDone(data.backup_codes); }
    catch (e) { setMsg(err(e)); }
  };
  return (
    <div data-testid="security-totp-setup" style={{ marginTop: 10 }}>
      {!qr ? (<>
        <ConfirmIdentity st={st} api={api} value={idv} onChange={setIdv} />
        <button className="btn-gold" data-testid="security-totp-start-btn" onClick={start}>Show QR code</button>
      </>) : (<>
        <div style={small}>Scan with Google Authenticator, Microsoft Authenticator, Apple Passwords or similar. Or enter this key: <code data-testid="security-totp-secret">{qr.secret}</code></div>
        <img src={qr.qr_data_url} alt="Authenticator QR code" data-testid="security-totp-qr" style={{ width: 180, height: 180, background: "#fff", borderRadius: 8, margin: "10px 0" }} />
        <div style={{ display: "flex", gap: 8 }}>
          <input className="input" inputMode="numeric" data-testid="security-totp-code-input" placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)} />
          <button className="btn-gold" data-testid="security-totp-verify-btn" onClick={verify} disabled={!code}>Turn on</button>
        </div>
      </>)}
      {msg && <div data-testid="security-totp-error" style={{ color: "var(--danger)", fontSize: 12, marginTop: 6 }}>{msg}</div>}
    </div>
  );
};

const TurnOff = ({ api, st, totp, onDone }) => {
  const [idv, setIdv] = useState({});
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const go = async () => {
    try { await api.post(totp ? "/auth/2fa/disable" : "/auth/2fa/email/disable", totp ? { ...idv, code } : idv); onDone(); }
    catch (e) { setMsg(err(e)); }
  };
  return (
    <div data-testid="security-turn-off" style={{ marginTop: 10 }}>
      <ConfirmIdentity st={st} api={api} value={idv} onChange={setIdv} />
      {totp && <input className="input" inputMode="numeric" data-testid="security-off-code-input" placeholder="Authenticator code"
                      value={code} onChange={(e) => setCode(e.target.value)} style={{ marginBottom: 8 }} />}
      <button className="btn-ghost" data-testid="security-off-confirm-btn" onClick={go}>Confirm turn off</button>
      {msg && <div style={{ color: "var(--danger)", fontSize: 12, marginTop: 6 }}>{msg}</div>}
    </div>
  );
};

const EmailCodesOn = ({ api, st, onDone, onToken }) => {
  const [idv, setIdv] = useState({});
  const [msg, setMsg] = useState("");
  const go = async () => {
    try { const { data } = await api.post("/auth/2fa/email/enable", idv); onToken(data.access_token); onDone(); }
    catch (e) { setMsg(err(e)); }
  };
  return (
    <div data-testid="security-email-setup" style={{ marginTop: 10 }}>
      <ConfirmIdentity st={st} api={api} value={idv} onChange={setIdv} />
      <button className="btn-gold" data-testid="security-email-enable-btn" onClick={go}>Turn on email codes</button>
      {msg && <div style={{ color: "var(--danger)", fontSize: 12, marginTop: 6 }}>{msg}</div>}
    </div>
  );
};

const Sessions = ({ api, onToken }) => {
  const [msg, setMsg] = useState("");
  const others = async () => {
    try { const { data } = await api.post("/auth/sessions/revoke", { keep_current: true }); onToken(data.access_token); setMsg("Signed out of all other devices."); }
    catch (e) { setMsg(err(e)); }
  };
  const all = async () => {
    if (!window.confirm("Sign out everywhere, including this device?")) return;
    try { await api.post("/auth/sessions/revoke", { keep_current: false }); } catch (e) { setMsg(err(e)); return; }
    localStorage.removeItem("aa_token"); window.location.reload();
  };
  return (
    <div style={{ marginTop: 14, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
      <button className="btn-ghost" data-testid="security-signout-others-btn" onClick={others}>Sign out other devices</button>
      <button className="btn-ghost" data-testid="security-signout-all-btn" onClick={all}>Sign out all devices</button>
      {msg && <span data-testid="security-sessions-msg" style={small}>{msg}</span>}
    </div>
  );
};

export const SecuritySettingsCard = ({ api, onToken }) => {
  const [st, setSt] = useState(null);
  const [mode, setMode] = useState(null);
  const [codes, setCodes] = useState(null);
  const load = useCallback(() => api.get("/auth/security/status").then((r) => setSt(r.data)).catch(() => {}), [api]);
  useEffect(() => { load(); }, [load]);
  if (!st) return null;
  const done = (c) => { setMode(null); if (Array.isArray(c)) setCodes(c); load(); };
  const label = st.method === "totp" ? "On — authenticator app" : st.method === "email" ? "On — email codes" : "Off";
  return (
    <div data-testid="settings-security" style={card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontWeight: 700 }}>Two-step sign-in</div>
        <span data-testid="security-method-state" style={{ fontSize: 12, color: st.method ? "var(--success, #22c55e)" : "var(--text-muted)" }}>{label}</span>
      </div>
      <div style={{ ...small, marginTop: 6 }}>
        {st.is_admin ? "Admin accounts must use an authenticator app." : "Recommended. After your password, you'll also enter a 6-digit code. An authenticator app is the stronger option; email codes need no extra app."}
      </div>
      {!st.method && !mode && (
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
          <button className="btn-gold" data-testid="security-choose-totp-btn" onClick={() => setMode("totp")}>Use an authenticator app (stronger)</button>
          {!st.is_admin && <button className="btn-ghost" data-testid="security-choose-email-btn" onClick={() => setMode("email")}>Use email codes</button>}
        </div>
      )}
      {st.method && !mode && <button className="btn-ghost" data-testid="security-turn-off-btn" onClick={() => setMode("off")} style={{ marginTop: 10 }}>Turn off</button>}
      {st.method === "totp" && <div data-testid="security-recovery-left" style={{ ...small, marginTop: 6 }}>{st.recovery_codes_left} recovery codes left</div>}
      {mode === "totp" && <AuthenticatorSetup api={api} st={st} onDone={done} onToken={onToken} />}
      {mode === "email" && <EmailCodesOn api={api} st={st} onDone={done} onToken={onToken} />}
      {mode === "off" && <TurnOff api={api} st={st} totp={st.method === "totp"} onDone={done} />}
      {mode && <button data-testid="security-cancel-btn" onClick={() => setMode(null)} style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: 12, marginTop: 6, cursor: "pointer" }}>Cancel</button>}
      {codes && <RecoveryCodes codes={codes} />}
      <Sessions api={api} onToken={onToken} />
    </div>
  );
};
