import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import "@/App.css";
import axios from "axios";
import {
  MessageCircle, Mic, Folder, FileText, Gavel, Globe, Briefcase, Home as HomeIcon,
  Stethoscope, Scale, X, Send, Upload, Languages, LogOut, Check, ArrowLeft, Square, Play,
  Camera, MapPin, Phone, ExternalLink, Settings as SettingsIcon, Star, Building2, Image as ImageIcon,
  Download, Trash2, Video, Lock, Unlock, ShieldCheck, AlertTriangle, Share2, KeyRound, Fingerprint, Sparkles, Volume2
} from "lucide-react";
import { STRINGS, t, RTL_LANGS } from "@/i18n";
import { setAppIconBadge } from "@/appBadge";
import { setSentryUser, clearSentryUser } from "@/sentry";
import { identify as identifyAnalytics, resetAnalytics, track } from "@/analytics";
import native, { isNative, hideSplash, openExternal as nativeOpenExternal } from "@/nativeBridge";

// Apple Reader-App compliance — when running inside the native iOS binary,
// we hide all Subscribe / Upgrade buttons (and replace them with a web-billing notice).
// This passes Apple Guideline 3.1.3(a). Web users see Stripe checkout as normal.
const IS_NATIVE = typeof window !== "undefined" && !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
import {
  AskLexIcon, RecordIcon, CameraIcon, LawyerIcon, FilesIcon, LetterIcon,
  CourtIcon, ImmigrationIcon, EmploymentIcon, PropertyIcon, MedicalIcon,
  OutcomeIcon, CostIcon, HearingIcon, AidIcon, ReminderIcon,
  ContractIcon, DraftIcon, VaultIcon, SuggestIcon, HandshakeIcon, RecycleIcon
} from "@/icons";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COUNTRIES = [
  { code: "GB", name: "United Kingdom" }, { code: "US", name: "United States" },
  { code: "ES", name: "Spain" }, { code: "FR", name: "France" }, { code: "IQ", name: "Iraq" },
  { code: "PL", name: "Poland" }, { code: "DE", name: "Germany" }, { code: "IN", name: "India" },
  { code: "PK", name: "Pakistan" }, { code: "IT", name: "Italy" }, { code: "PT", name: "Portugal" },
  { code: "CN", name: "China" }, { code: "AE", name: "UAE" }, { code: "AU", name: "Australia" },
  { code: "CA", name: "Canada" },
];

const LANGS = [
  { code: "en-GB", name: "English", flag: "🇬🇧", cc: "gb" }, { code: "es-ES", name: "Español", flag: "🇪🇸", cc: "es" },
  { code: "fr-FR", name: "Français", flag: "🇫🇷", cc: "fr" }, { code: "ar-IQ", name: "العربية", flag: "🇮🇶", cc: "iq" },
  { code: "pl-PL", name: "Polski", flag: "🇵🇱", cc: "pl" }, { code: "de-DE", name: "Deutsch", flag: "🇩🇪", cc: "de" },
  { code: "hi-IN", name: "हिन्दी", flag: "🇮🇳", cc: "in" }, { code: "ur-PK", name: "اردو", flag: "🇵🇰", cc: "pk" },
  { code: "it-IT", name: "Italiano", flag: "🇮🇹", cc: "it" }, { code: "pt-PT", name: "Português", flag: "🇵🇹", cc: "pt" },
  { code: "zh-CN", name: "中文 (简体)", flag: "🇨🇳", cc: "cn" },
];

// Cross-platform flag — uses flagcdn.com SVGs so flags render
// identically on Windows/Edge (which doesn't render emoji flags) and on iOS/Android.
const Flag = ({ cc, size = 22, alt = "" }) => (
  <img
    src={`https://flagcdn.com/w40/${cc}.png`}
    srcSet={`https://flagcdn.com/w80/${cc}.png 2x`}
    width={Math.round(size * 1.4)}
    height={size}
    alt={alt}
    loading="lazy"
    style={{
      display: "inline-block",
      verticalAlign: "middle",
      borderRadius: 3,
      boxShadow: "0 0 0 1px rgba(0,0,0,0.25)",
      objectFit: "cover",
    }}
  />
);

// ---------- API helpers ----------
const api = axios.create({ baseURL: API });
const setAuthHeader = (token) => {
  if (token) api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  else delete api.defaults.headers.common["Authorization"];
};

// ---------- In-app confirm + toast (replaces window.confirm/alert) ----------
// Why: native window.confirm() is suppressed in some mobile browsers (Brave/iOS,
// preview iframes) so users tap delete and nothing seems to happen. These render
// our own gold-themed dialog/toast that always shows, regardless of browser.
const __aaUI = { confirm: null, toast: null };
const aaConfirm = (opts) => new Promise((resolve) => {
  if (!__aaUI.confirm) { resolve(window.confirm(typeof opts === "string" ? opts : (opts?.message || ""))); return; }
  __aaUI.confirm(typeof opts === "string" ? { message: opts } : opts, resolve);
});
const aaToast = (msg, type = "success") => {
  if (!__aaUI.toast) { try { console.log(`[toast/${type}]`, msg); } catch (e) {} return; }
  __aaUI.toast(msg, type);
};

function AAConfirmHost() {
  const [c, setC] = useState(null);   // { message, title, danger, confirmLabel, cancelLabel, resolve }
  const [toasts, setToasts] = useState([]);
  useEffect(() => {
    __aaUI.confirm = (opts, resolve) => setC({ ...opts, resolve });
    __aaUI.toast = (msg, type) => {
      const id = Date.now() + Math.random();
      setToasts(ts => [...ts, { id, msg, type }]);
      setTimeout(() => setToasts(ts => ts.filter(t => t.id !== id)), type === "error" ? 5000 : 3000);
    };
    return () => { __aaUI.confirm = null; __aaUI.toast = null; };
  }, []);
  const close = (ok) => { if (c) { c.resolve(ok); setC(null); } };
  return (
    <>
      {c && (
        <div data-testid="aa-confirm" style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 100000,
          display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
        }} onClick={() => close(false)}>
          <div onClick={(e) => e.stopPropagation()} style={{
            background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14,
            padding: 22, maxWidth: 360, width: "100%", boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
          }}>
            {c.title && <div style={{ color: "var(--gold)", fontWeight: 700, fontSize: 15, marginBottom: 8 }}>{c.title}</div>}
            <div style={{ color: "var(--text)", fontSize: 13.5, lineHeight: 1.55, marginBottom: 18, whiteSpace: "pre-wrap" }}>
              {c.message}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button data-testid="aa-confirm-cancel" onClick={() => close(false)} className="btn-ghost"
                style={{ flex: 1, padding: "10px 14px", fontSize: 13 }}>
                {c.cancelLabel || "Cancel"}
              </button>
              <button data-testid="aa-confirm-ok" onClick={() => close(true)}
                style={{
                  flex: 1, padding: "10px 14px", fontSize: 13, fontWeight: 700, borderRadius: 10, cursor: "pointer",
                  background: c.danger ? "#7f1d1d" : "var(--gold)",
                  color: c.danger ? "#fff" : "#0a0a0a",
                  border: c.danger ? "1px solid #b91c1c" : "1px solid var(--gold-deep)",
                }}>
                {c.confirmLabel || (c.danger ? "Delete" : "Confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Stack of toasts, bottom-center, gold theme */}
      <div style={{
        position: "fixed", bottom: 80, left: "50%", transform: "translateX(-50%)",
        zIndex: 100001, display: "flex", flexDirection: "column", gap: 8, pointerEvents: "none",
        width: "min(420px, calc(100% - 28px))",
      }}>
        {toasts.map(t => (
          <div key={t.id} data-testid={`aa-toast-${t.type}`} style={{
            background: t.type === "error" ? "#3a0e0e" : t.type === "info" ? "#102a36" : "#1a1300",
            border: `1px solid ${t.type === "error" ? "#7f1d1d" : t.type === "info" ? "#155e75" : "var(--gold-deep)"}`,
            borderRadius: 10, padding: "11px 14px", fontSize: 13,
            color: t.type === "error" ? "#fecaca" : t.type === "info" ? "#67e8f9" : "var(--gold)",
            boxShadow: "0 10px 30px rgba(0,0,0,0.5)", pointerEvents: "auto",
          }}>{t.msg}</div>
        ))}
      </div>
    </>
  );
}

// 🍪 Cookie / analytics consent banner — PECR + UK-GDPR requirement.
// Shows on first visit; persists choice in localStorage. If user declines analytics,
// we still serve the app but skip identifyAnalytics / track() calls.
function CookieConsentBanner() {
  const [show, setShow] = useState(() => {
    try { return !localStorage.getItem("aa_cookie_consent"); } catch (e) { return false; }
  });
  if (!show) return null;
  const choose = (decision) => {
    try { localStorage.setItem("aa_cookie_consent", decision); } catch (e) {}
    try { localStorage.setItem("aa_cookie_consent_at", new Date().toISOString()); } catch (e) {}
    if (decision === "rejected") {
      // Best-effort: block subsequent analytics calls by setting a global flag
      try { window.__aa_analytics_off = true; } catch (e) {}
    }
    setShow(false);
  };
  return (
    <div data-testid="cookie-consent" style={{
      position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 99999,
      background: "rgba(10,10,10,0.96)", backdropFilter: "blur(10px)",
      borderTop: "1px solid var(--gold-deep)", padding: 14,
      display: "flex", flexDirection: "column", gap: 10,
      boxShadow: "0 -8px 24px rgba(0,0,0,0.5)",
    }}>
      <div style={{ color: "var(--text)", fontSize: 12.5, lineHeight: 1.5, maxWidth: 580, margin: "0 auto" }}>
        We use essential cookies to keep you signed in and run the app. With your permission, we also use
        <strong style={{ color: "var(--gold-soft)" }}> anonymous analytics</strong> (which features get used) and
        <strong style={{ color: "var(--gold-soft)" }}> crash reporting</strong> (Sentry) — both can be turned off any time in Settings.
        See our <a href="/privacy.html" target="_blank" rel="noopener noreferrer" style={{ color: "var(--gold)" }}>Privacy Policy</a>.
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
        <button data-testid="cookie-reject" onClick={() => choose("rejected")}
          className="btn-ghost" style={{ flex: 1, maxWidth: 200, padding: "9px 14px", fontSize: 12 }}>
          Essential only
        </button>
        <button data-testid="cookie-accept" onClick={() => choose("accepted")}
          className="btn-gold" style={{ flex: 1, maxWidth: 200, padding: "9px 14px", fontSize: 12, fontWeight: 700 }}>
          Accept all
        </button>
      </div>
    </div>
  );
}

// ---------- PDF download helper ----------
const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a);
  a.click(); a.remove(); URL.revokeObjectURL(url);
};

const pdfInline = async ({ title, body, subtitle, meta, filename }) => {
  const r = await api.post("/pdf/inline", { title, body, subtitle, meta, filename }, { responseType: "blob" });
  downloadBlob(r.data, filename || "ai_advocate.pdf");
};

const pdfForFile = async (fileId, filename) => {
  const r = await api.get(`/pdf/file/${fileId}`, { responseType: "blob" });
  downloadBlob(r.data, (filename || "ai_advocate") + ".pdf");
};

// ---------- Logo / Lex visuals ----------
const Logo = ({ size = "lg", lang = "en-GB" }) => {
  const w = size === "lg" ? 220 : size === "md" ? 140 : 80;
  const showTagline = size === "lg";
  return (
    <div className="flex flex-col items-center" data-testid="app-logo">
      <div className="aa-logo-shimmer" style={{ width: w, display: "inline-block" }}>
        <img src="/assets/logo-notag.png" alt="AI Advocate"
             style={{ width: w, height: "auto", display: "block" }} />
      </div>
      {showTagline && (
        <div style={{ color: "var(--gold)", fontSize: 11, letterSpacing: "0.08em",
                      marginTop: 6, opacity: 0.85, textAlign: "center" }}>
          {t(lang, "tagline")}
        </div>
      )}
    </div>
  );
};

const LexAvatar = ({ size = 70, recording = false, onClick }) => (
  <div className={`lex-circle ${recording ? "recording" : ""}`} onClick={onClick}
       style={{ width: size, height: size, padding: 0, overflow: "hidden",
                background: "#000" }} data-testid="lex-avatar">
    <img src="/assets/lex.jpg" alt="Lex"
         style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%",
                  mixBlendMode: "lighten" }} />
  </div>
);

// ---------- Onboarding ----------
function LanguagePicker({ initial, onConfirm, lang }) {
  const [sel, setSel] = useState(initial || "en-GB");
  return (
    <div className="modal-bg" data-testid="lang-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <h2 className="brand-font gold" style={{ fontSize: 22, marginTop: 6 }}>{t(lang, "selectLanguage")}</h2>
        <div style={{ overflowY: "auto", maxHeight: "60vh", marginTop: 10 }}>
          {LANGS.map(l => (
            <button key={l.code} onClick={() => setSel(l.code)}
              data-testid={`lang-${l.code}`}
              className="flex items-center gap-3 w-full p-3 rounded-lg"
              style={{
                background: sel === l.code ? "rgba(247,201,72,0.1)" : "transparent",
                border: sel === l.code ? "1px solid var(--gold)" : "1px solid transparent",
                marginBottom: 6, color: "var(--text)", textAlign: "left", cursor: "pointer"
              }}>
              <Flag cc={l.cc} size={22} alt={l.name} />
              <span style={{ flex: 1, marginLeft: 4 }}>{l.name}</span>
              <span style={{ color: "var(--text-muted)", fontSize: 13 }}>({l.code})</span>
            </button>
          ))}
        </div>
        <button className="btn-gold w-full" data-testid="lang-ok-btn" onClick={() => onConfirm(sel)} style={{ marginTop: 12 }}>
          {t(lang, "ok")}
        </button>
      </div>
    </div>
  );
}

function TermsScreen({ lang, onAccept, onDecline, onChangeLang }) {
  const [agree, setAgree] = useState(false);
  const [over18, setOver18] = useState(false);
  const [body, setBody] = useState("");
  const [note, setNote] = useState("");
  const [englishFull, setEnglishFull] = useState("");
  const [showEnglish, setShowEnglish] = useState(false);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setShowEnglish(false);
    api.get(`/legal/terms?language=${encodeURIComponent(lang)}`)
      .then(r => { if (!cancelled) {
        setBody(r.data.body || "");
        setNote(r.data.note || "");
        setEnglishFull(r.data.english_full || "");
      }})
      .catch(() => { if (!cancelled) setBody(""); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [lang]);

  const dateStr = new Date().toLocaleDateString(lang.replace("_", "-"), { day: "numeric", month: "long", year: "numeric" });
  const isRTL = ["ar-IQ", "ur-PK"].includes(lang);
  return (
    <div className="modal-bg" data-testid="terms-modal">
      <div className="modal-card" style={{ padding: 22, height: "92vh", display: "flex", flexDirection: "column" }} dir={isRTL ? "rtl" : "ltr"}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12, flexShrink: 0 }}>
          <h2 className="brand-font gold" style={{ fontSize: 22 }}>{t(lang, "termsTitle")}</h2>
          <button className="btn-gold" data-testid="terms-lang-btn" onClick={onChangeLang}
                  title={t(lang, "changeLanguage")}
                  style={{ padding: "8px 12px", lineHeight: 1, display: "inline-flex", alignItems: "center" }}>
            <Flag cc={(LANGS.find(l => l.code === lang) || LANGS[0]).cc} size={20} />
          </button>
        </div>
        <p style={{ color: "var(--text-dim)", fontSize: 13, flexShrink: 0 }}>
          {t(lang, "effectiveDate", { date: dateStr })}
        </p>
        {note && (
          <p style={{ color: "var(--gold-soft)", fontSize: 11, flexShrink: 0, marginTop: 4, fontStyle: "italic" }}>
            {note}
          </p>
        )}
        <div data-testid="terms-body" style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: 14, background: "#0a0a0a", borderRadius: 12, border: "1px solid var(--line)", marginTop: 10, fontSize: 12.5, color: "var(--text-dim)", lineHeight: 1.65, whiteSpace: "pre-wrap" }}>
          {busy ? <span className="spinner" /> : (showEnglish ? englishFull : body)}
        </div>
        {englishFull && !showEnglish && (
          <button data-testid="show-english-btn" onClick={() => setShowEnglish(true)}
            style={{ marginTop: 8, padding: "8px 12px", background: "transparent", color: "var(--gold)",
                     border: "1px solid var(--gold-deep)", borderRadius: 10, fontSize: 12, cursor: "pointer", flexShrink: 0 }}>
            View full English authoritative version
          </button>
        )}
        {showEnglish && (
          <button data-testid="show-summary-btn" onClick={() => setShowEnglish(false)}
            style={{ marginTop: 8, padding: "8px 12px", background: "transparent", color: "var(--gold)",
                     border: "1px solid var(--gold-deep)", borderRadius: 10, fontSize: 12, cursor: "pointer", flexShrink: 0 }}>
            Back to summary
          </button>
        )}
        <label className="flex items-center gap-2" style={{ marginTop: 14, cursor: "pointer", flexShrink: 0 }}>
          <input type="checkbox" data-testid="agree-checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)}
                 style={{ width: 18, height: 18, accentColor: "var(--gold)" }} />
          <span style={{ fontSize: 14 }}>{t(lang, "iAgree")}</span>
        </label>
        {/* 🛡 18+ age gate — required for App Store 17+ rating + UK consumer law */}
        <label className="flex items-center gap-2" style={{ marginTop: 10, cursor: "pointer", flexShrink: 0 }}>
          <input type="checkbox" data-testid="age-gate-checkbox" checked={over18} onChange={(e) => setOver18(e.target.checked)}
                 style={{ width: 18, height: 18, accentColor: "var(--gold)" }} />
          <span style={{ fontSize: 13, color: "var(--text-dim)" }}>I confirm I am <strong style={{ color: "var(--gold-soft)" }}>18 years or older</strong>.</span>
        </label>
        <div className="flex gap-2" style={{ marginTop: 14, flexShrink: 0 }}>
          <button className="btn-gold" data-testid="accept-terms-btn" disabled={!agree || !over18 || busy} style={{ flex: 2 }} onClick={onAccept}>{t(lang, "accept")}</button>
          <button className="btn-ghost" data-testid="decline-terms-btn" onClick={onDecline} style={{ flex: 1 }}>{t(lang, "decline")}</button>
        </div>
      </div>
    </div>
  );
}

// ---------- Auth ----------
function AuthScreen({ lang, country, onAuth }) {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [name, setName] = useState(""); const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [providers, setProviders] = useState({ google_enabled: false, apple_enabled: false });

  // First-run experience: show onboarding tour then taster Lex on initial visit
  const [showWelcome, setShowWelcome] = useState(() => !localStorage.getItem("aa_welcomed"));
  const [showTaster, setShowTaster] = useState(false);

  useEffect(() => { api.get("/auth/providers").then(r => setProviders(r.data)).catch(() => {}); }, []);

  // Inject Google Identity Services script when enabled
  useEffect(() => {
    if (!providers.google_enabled || !providers.google_client_id) return;
    if (document.getElementById("google-id-script")) return;
    const s = document.createElement("script");
    s.id = "google-id-script"; s.src = "https://accounts.google.com/gsi/client"; s.async = true;
    document.body.appendChild(s);
  }, [providers]);

  // Inject Apple Sign-In script when enabled
  useEffect(() => {
    if (!providers.apple_enabled || !providers.apple_services_id) return;
    if (document.getElementById("apple-id-script")) return;
    const s = document.createElement("script");
    s.id = "apple-id-script";
    s.src = "https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js";
    s.async = true;
    s.onload = () => {
      try {
        window.AppleID.auth.init({
          clientId: providers.apple_services_id,
          scope: "name email",
          redirectURI: window.location.origin + "/",
          usePopup: true,
        });
      } catch {}
    };
    document.body.appendChild(s);
  }, [providers]);

  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const path = mode === "signup" ? "/auth/signup" : "/auth/login";
      const body = mode === "signup" ? { email, password, full_name: name, language: lang, country } : { email, password };
      const { data } = await api.post(path, body);
      onAuth(data);
    } catch (e) { setErr(e?.response?.data?.detail || "Auth failed"); }
    finally { setBusy(false); }
  };

  const googleReal = () => {
    if (!window.google?.accounts?.oauth2) { alert(t(lang, "googleNotLoaded")); return; }
    try {
      const client = window.google.accounts.oauth2.initTokenClient({
        client_id: providers.google_client_id,
        scope: "openid email profile",
        callback: async (resp) => {
          if (resp.error) { setErr(`Google sign-in failed: ${resp.error}`); return; }
          if (!resp.access_token) { setErr("Google sign-in failed: no access token returned"); return; }
          try {
            const { data } = await api.post("/auth/google", { access_token: resp.access_token });
            onAuth(data);
          } catch (e) { setErr(e?.response?.data?.detail || "Google sign-in failed"); }
        },
        error_callback: (err) => {
          setErr(`Google sign-in failed: ${err?.type || "popup_closed"}`);
        },
      });
      client.requestAccessToken({ prompt: "consent" });
    } catch (e) {
      setErr("Google sign-in failed to initialize");
    }
  };

  const googleDemo = async () => {
    setBusy(true); setErr("");
    try {
      const fakeId = "g_" + Math.random().toString(36).slice(2);
      const { data } = await api.post("/auth/google", { email: `demo.${fakeId.slice(0,6)}@gmail.com`, name: "Google User", google_id: fakeId });
      onAuth(data);
    } catch (e) { setErr(e?.response?.data?.detail || "Google sign-in failed"); }
    finally { setBusy(false); }
  };

  const appleSignIn = async () => {
    if (!window.AppleID?.auth) { alert(t(lang, "appleNotLoaded")); return; }
    setBusy(true); setErr("");
    try {
      const r = await window.AppleID.auth.signIn();
      const idToken = r?.authorization?.id_token;
      if (!idToken) {
        setErr("Apple did not return an ID token. Check Services ID config.");
        return;
      }
      const { data } = await api.post("/auth/apple", {
        identity_token: idToken,
        user: r.user,
      });
      onAuth(data);
    } catch (e) {
      // Apple errors look like {error: "popup_closed_by_user", ...}
      const appleErr = e?.error || e?.message || "";
      let msg = e?.response?.data?.detail || appleErr || "Apple sign-in failed";
      if (appleErr === "popup_closed_by_user") msg = "Sign-in cancelled.";
      if (appleErr === "invalid_client") msg = "Apple says: invalid_client. Domain/Services ID not configured correctly.";
      if (appleErr === "popup_blocked_by_browser") msg = "Pop-up blocked — allow popups for this site.";
      console.error("Apple sign-in error:", e);
      setErr(msg);
    }
    finally { setBusy(false); }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24 }} data-testid="auth-screen">
      <Logo lang={lang} />
      <form onSubmit={submit} style={{ width: "100%", maxWidth: 380, marginTop: 30 }}>
        {mode === "signup" && (
          <input className="input" data-testid="name-input" placeholder={t(lang, "fullName")} value={name} onChange={(e) => setName(e.target.value)} style={{ marginBottom: 10 }} />
        )}
        <input className="input" type="email" data-testid="email-input" placeholder={t(lang, "email")} value={email} onChange={(e) => setEmail(e.target.value)} required style={{ marginBottom: 10 }} />
        <input className="input" type="password" data-testid="password-input" placeholder={t(lang, "password")} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} style={{ marginBottom: 10 }} />
        {err && <div style={{ color: "var(--danger)", fontSize: 13, marginBottom: 8 }}>{err}</div>}
        <button className="btn-gold w-full" data-testid="auth-submit-btn" type="submit" disabled={busy}>
          {busy ? <span className="spinner" /> : (mode === "signup" ? t(lang, "signUp") : t(lang, "signIn"))}
        </button>
      </form>
      <div style={{ width: "100%", maxWidth: 380, marginTop: 16, textAlign: "center", color: "var(--text-muted)" }}>
        — {t(lang, "or")} —
      </div>
      <button className="btn-ghost" data-testid="google-btn"
              onClick={providers.google_enabled ? googleReal : googleDemo}
              disabled={busy} style={{ width: "100%", maxWidth: 380, marginTop: 12 }}>
        {t(lang, "continueWithGoogle")}
      </button>
      {providers.apple_enabled && (
        <button onClick={appleSignIn} disabled={busy} data-testid="apple-btn"
                style={{ width: "100%", maxWidth: 380, marginTop: 8, padding: "12px 18px",
                  background: "#000", color: "#fff", border: "1px solid #fff", borderRadius: 14, cursor: "pointer",
                  fontSize: 15, fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
           Sign in with Apple
        </button>
      )}
      <button data-testid="toggle-mode-btn" onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
              style={{ marginTop: 20, color: "var(--gold-soft)", background: "transparent", border: "none", cursor: "pointer" }}>
        {mode === "signin" ? t(lang, "noAccount") + " " + t(lang, "signUp") : t(lang, "haveAccount") + " " + t(lang, "signIn")}
      </button>

      {/* Try Lex Free — single CTA below auth, always available */}
      <button data-testid="try-lex-free-btn" onClick={() => setShowTaster(true)}
              style={{
                marginTop: 22,
                padding: "10px 18px",
                background: "transparent",
                color: "var(--gold)",
                border: "1px solid var(--gold-deep)",
                borderRadius: 12,
                cursor: "pointer",
                fontSize: 13,
                letterSpacing: "0.02em",
                display: "inline-flex", alignItems: "center", gap: 8,
              }}>
        <Sparkles size={14} /> {t(lang, "tryLexFree")}
      </button>

      {showWelcome && (
        <WelcomeTour lang={lang} onDone={() => { localStorage.setItem("aa_welcomed", "1"); setShowWelcome(false); setShowTaster(true); }} />
      )}
      {showTaster && (
        <TasterLex lang={lang} country={country} onClose={() => setShowTaster(false)} onSignupClick={() => { setShowTaster(false); setMode("signup"); }} />
      )}
    </div>
  );
}

// ---------- First-run onboarding (3 swipeable cards) ----------
function WelcomeTour({ lang, onDone }) {
  const [step, setStep] = useState(0);
  const cards = [
    { icon: "/icons/ask_lex.png", title: t(lang, "tourTitle1"), body: t(lang, "tourBody1") },
    { icon: "/icons/camera.png",  title: t(lang, "tourTitle2"), body: t(lang, "tourBody2") },
    { icon: "/icons/vault.png",   title: t(lang, "tourTitle3"), body: t(lang, "tourBody3") },
  ];
  const next = () => step < cards.length - 1 ? setStep(step + 1) : onDone();
  const c = cards[step];
  return (
    <div className="modal-bg" data-testid="welcome-tour" style={{ zIndex: 10000 }}>
      <div className="modal-card" style={{ padding: 28, maxWidth: 420, textAlign: "center" }}>
        <img src={c.icon} alt="" style={{ width: 96, height: 96, objectFit: "contain", margin: "0 auto 14px", filter: "drop-shadow(0 4px 16px rgba(247,201,72,0.35))" }} />
        <h2 style={{ fontFamily: "'Cinzel', serif", color: "var(--gold)", fontSize: 20, margin: "0 0 10px", letterSpacing: "0.05em" }}>{c.title}</h2>
        <p style={{ color: "var(--text)", fontSize: 14, lineHeight: 1.55, margin: "0 0 24px" }}>{c.body}</p>
        <div style={{ display: "flex", justifyContent: "center", gap: 6, marginBottom: 20 }}>
          {cards.map((_, i) => (
            <span key={i} style={{ width: i === step ? 18 : 6, height: 6, borderRadius: 3, background: i === step ? "var(--gold)" : "var(--line)", transition: "0.2s" }} />
          ))}
        </div>
        <button className="btn-gold w-full" data-testid="welcome-tour-next" onClick={next}>
          {step < cards.length - 1 ? t(lang, "next") : t(lang, "tourCta")}
        </button>
        <button data-testid="welcome-tour-skip" onClick={onDone}
                style={{ marginTop: 10, background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: 12 }}>
          {t(lang, "skip")}
        </button>
      </div>
    </div>
  );
}

// ---------- Free taster Lex chat (no signup, 1 question) ----------
function TasterLex({ lang, country, onClose, onSignupClick }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [available, setAvailable] = useState(true);

  // Stable per-device id (survives reloads, not incognito)
  const deviceId = useMemo(() => {
    let d = localStorage.getItem("aa_device_id");
    if (!d) { d = (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`); localStorage.setItem("aa_device_id", d); }
    return d;
  }, []);

  useEffect(() => {
    api.get(`/lex/taster/status?device_id=${encodeURIComponent(deviceId)}`)
      .then(r => setAvailable(!!r.data?.available))
      .catch(() => {});
  }, [deviceId]);

  const ask = async (e) => {
    e?.preventDefault?.();
    if (!question.trim() || busy) return;
    setBusy(true); setErr(""); setAnswer("");
    try {
      const { data } = await api.post("/lex/taster", {
        message: question.trim(), device_id: deviceId, language: lang, country,
      });
      setAnswer(data.response);
      setAvailable(false);
    } catch (e2) {
      setErr(e2?.response?.data?.detail || "Lex is busy — try again");
      if (e2?.response?.status === 429) setAvailable(false);
    } finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="taster-lex" style={{ zIndex: 10000 }}>
      <div className="modal-card" style={{ padding: 22, maxWidth: 480 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <img src="/icons/ask_lex.png" alt="" style={{ width: 36, height: 36, objectFit: "contain" }} />
            <div>
              <h2 style={{ fontFamily: "'Cinzel', serif", color: "var(--gold)", fontSize: 17, margin: 0, letterSpacing: "0.04em" }}>{t(lang, "tasterTitle")}</h2>
              <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 2 }}>{t(lang, "tasterSubtitle")}</div>
            </div>
          </div>
          <button onClick={onClose} data-testid="taster-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={20} /></button>
        </div>

        {!answer && available && (
          <form onSubmit={ask}>
            <textarea data-testid="taster-input"
              value={question} onChange={(e) => setQuestion(e.target.value)}
              placeholder={t(lang, "tasterPlaceholder")}
              maxLength={500} rows={4}
              style={{ width: "100%", padding: 12, background: "var(--bg-elev)", border: "1px solid var(--line)", borderRadius: 12, color: "var(--text)", fontSize: 14, fontFamily: "inherit", resize: "vertical" }} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6, fontSize: 11, color: "var(--text-muted)" }}>
              <span>{question.length}/500</span>
              <span>{t(lang, "tasterLimitNote")}</span>
            </div>
            {err && <div style={{ color: "var(--danger)", fontSize: 13, marginTop: 8 }}>{err}</div>}
            <button type="submit" className="btn-gold w-full" data-testid="taster-submit"
                    disabled={busy || question.trim().length < 4}
                    style={{ marginTop: 14 }}>
              {busy ? <span className="spinner" /> : t(lang, "tasterAskBtn")}
            </button>
          </form>
        )}

        {answer && (
          <div data-testid="taster-answer">
            <div style={{ background: "rgba(247,201,72,0.06)", border: "1px solid var(--gold-deep)", borderRadius: 12, padding: 14, fontSize: 13, lineHeight: 1.6, color: "var(--text)", whiteSpace: "pre-wrap", maxHeight: "55vh", overflowY: "auto" }}>
              {answer}
            </div>
            <div style={{ marginTop: 16, padding: 14, background: "linear-gradient(135deg, rgba(247,201,72,0.12), rgba(247,201,72,0.02))", border: "1px solid var(--gold)", borderRadius: 12 }}>
              <div style={{ color: "var(--gold)", fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{t(lang, "tasterUpsellTitle")}</div>
              <div style={{ color: "var(--text)", fontSize: 12, lineHeight: 1.5 }}>{t(lang, "tasterUpsellBody")}</div>
              <button className="btn-gold w-full" data-testid="taster-signup-btn" onClick={onSignupClick} style={{ marginTop: 12 }}>
                {t(lang, "tasterUpsellCta")}
              </button>
            </div>
          </div>
        )}

        {!available && !answer && (
          <div data-testid="taster-exhausted" style={{ padding: 16, background: "rgba(247,201,72,0.06)", border: "1px solid var(--gold-deep)", borderRadius: 12, textAlign: "center" }}>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>{t(lang, "tasterExhaustedTitle")}</div>
            <div style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.5, marginBottom: 14 }}>{t(lang, "tasterExhaustedBody")}</div>
            <button className="btn-gold w-full" data-testid="taster-signup-exhausted" onClick={onSignupClick}>
              {t(lang, "tasterUpsellCta")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Lex metadata parser (Confidence / Sources / Connected-to) ----------
// Strips structured markers from Lex's reply body and returns { body, confidence, sources, connectedTo }.
// Markers are expected on their OWN line at the end of the reply, e.g.
//   [CONFIDENCE: HIGH]
//   [SOURCES: Housing Act 2004 s.213; Smith v Jones [2019] EWCA Civ 123]
//   [CONNECTED_TO: deposit dispute with previous landlord]
function parseLexMetadata(raw) {
  if (!raw || typeof raw !== "string") return { body: raw || "", confidence: null, sources: [], connectedTo: null };
  let confidence = null, sources = [], connectedTo = null;
  // Line-based match so source values can contain [...] (e.g. "Smith v Jones [2019]")
  const lineRe = /^\s*\[(CONFIDENCE|SOURCES|CONNECTED_TO):\s*([\s\S]*?)\]\s*$/im;
  const lines = raw.split(/\r?\n/);
  const kept = [];
  for (const line of lines) {
    const m = line.match(lineRe);
    if (m) {
      const key = m[1].toUpperCase();
      const val = m[2].trim();
      if (key === "CONFIDENCE") confidence = val.toUpperCase();
      else if (key === "SOURCES") {
        sources = val.split(/[;|]/).map(s => s.trim()).filter(s => s && s !== "—" && s !== "-");
      } else if (key === "CONNECTED_TO") {
        // Strip leading "#N" reference (used for backend → session_id lookup) so chip text is clean
        connectedTo = val.replace(/^#\d+\s*[-:|–]?\s*/, "").replace(/^["']|["']$/g, "").trim();
      }
    } else {
      kept.push(line);
    }
  }
  const body = kept.join("\n").replace(/\n{3,}/g, "\n\n").trim();
  return { body, confidence, sources, connectedTo };
}

// Map a source citation string to its best-guess official-source URL.
// UK case ("X v Y [YYYY]")              → BAILII search
// EU regulation / directive             → EUR-Lex search
// UK statute ("X Act YYYY")              → legislation.gov.uk search
// fallback                              → Google site-restricted search
function buildSourceUrl(source) {
  if (!source || typeof source !== "string") return null;
  const s = source.trim();
  if (!s || s === "—" || s === "-") return null;
  const q = encodeURIComponent(s);

  // UK case law: " v " or " v. " with surrounding name parts
  if (/\b[A-Z][\w'.-]+\s+v\.?\s+[A-Z][\w'.-]+/.test(s)) {
    return `https://www.bailii.org/cgi-bin/sino_search_1.cgi?query=${q}`;
  }
  // EU regulation or directive
  if (/regulation\s*\(eu\)/i.test(s) || /^directive\s+\d/i.test(s) || /\beu\s+\d{4}\/\d+/i.test(s)) {
    return `https://eur-lex.europa.eu/search.html?qid=&text=${q}`;
  }
  // UK statute ("Housing Act 2004", "s.213 Housing Act", "Consumer Rights Act 2015 s.54")
  if (/\bact\s+\d{4}\b/i.test(s) || /^s\.?\s*\d/i.test(s) || /\bschedule\s+\d/i.test(s)) {
    return `https://www.legislation.gov.uk/search?text=${q}`;
  }
  // Fallback — Google scoped to canonical legal sources
  return `https://www.google.com/search?q=${q}+site%3Alegislation.gov.uk+OR+site%3Abailii.org+OR+site%3Aeur-lex.europa.eu`;
}

// Render Lex message body with inline [1], [2] citation pills that open the actual
// BAILII / legislation.gov.uk source URL. Falls back to the raw text if no citations.
function renderWithCitationPills(text, citations, msgIdx) {
  if (!text || !Array.isArray(citations) || citations.length === 0) return text;
  const byN = new Map(citations.map((c) => [c.n, c]));
  // Split on any [n] marker, keeping the markers
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, idx) => {
    const m = /^\[(\d+)\]$/.exec(part);
    if (m) {
      const n = parseInt(m[1], 10);
      const cite = byN.get(n);
      if (cite && cite.url) {
        return (
          <a
            key={idx}
            href={cite.url}
            target="_blank"
            rel="noopener noreferrer"
            title={cite.title}
            data-testid={`citation-pill-${msgIdx}-${n}`}
            onClick={(e) => {
              e.stopPropagation();
              // On native (iOS/Android), open in the in-app browser sheet (Safari View
              // Controller / Chrome Custom Tab) so users stay inside the app — this is
              // also required for App Store approval (no bouncing to mobile Safari).
              if (isNative()) {
                e.preventDefault();
                nativeOpenExternal(cite.url);
              }
            }}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 2,
              background: cite.source === "official" ? "var(--gold)" : "rgba(247,201,72,0.2)",
              color: cite.source === "official" ? "#0a0a0a" : "var(--gold)",
              border: `1px solid ${cite.source === "official" ? "var(--gold-deep)" : "var(--gold-deep)"}`,
              borderRadius: 999,
              padding: "1px 7px",
              fontSize: 10.5,
              fontWeight: 700,
              textDecoration: "none",
              margin: "0 1px",
              lineHeight: 1.4,
              verticalAlign: "baseline",
            }}
          >
            [{n}]
          </a>
        );
      }
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

// ---------- Voice Recording Hook ----------
const useRecorder = () => {
  const mr = useRef(null); const chunks = useRef([]);
  const [recording, setRecording] = useState(false);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunks.current = [];
      recorder.ondataavailable = (e) => chunks.current.push(e.data);
      recorder.start();
      mr.current = { recorder, stream };
      setRecording(true);
    } catch (e) { alert(t(lang, "micAccessDenied")); }
  };
  const stop = () => new Promise((resolve) => {
    if (!mr.current) return resolve(null);
    const { recorder, stream } = mr.current;
    recorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      const blob = new Blob(chunks.current, { type: "audio/webm" });
      mr.current = null; setRecording(false); resolve(blob);
    };
    recorder.stop();
  });
  return { recording, start, stop };
};

// ---------- "Hey Lex" Wake-Word Hook ----------
// Continuous SpeechRecognition listening for the phrase "hey lex" / "hi lex" / "ok lex".
// When detected, fires onWake(). Works in Chrome / Edge / Safari (with permission).
// Multilingual: uses the user's chosen lang so the recognizer picks up local accents.
const useHeyLex = ({ enabled, lang, onWake }) => {
  const recRef = useRef(null);
  const stoppedRef = useRef(false);
  // Buffer to also catch any text spoken right after the wake word in the same utterance
  const trailingRef = useRef("");

  useEffect(() => {
    if (!enabled) {
      try { recRef.current?.stop(); } catch {}
      recRef.current = null;
      stoppedRef.current = true;
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return; // unsupported browser

    stoppedRef.current = false;
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = lang || "en-GB";

    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = (event.results[i][0].transcript || "").toLowerCase().trim();
        // Wake-word variants across languages
        const wakeMatch = transcript.match(/(?:^|\s)(?:hey|hi|okay|ok|hola|salam|你好|bonjour|hallo|ciao|olá|namaste)[ ,.]*(?:lex|leks|lekss|лекс)\b(.*)$/);
        if (wakeMatch) {
          // Capture anything spoken AFTER "hey lex" in the same utterance (e.g. "hey lex, my landlord is keeping my deposit")
          const trailing = (wakeMatch[1] || "").trim();
          trailingRef.current = trailing;
          try { rec.stop(); } catch {}
          onWake(trailing);
          return;
        }
      }
    };
    rec.onend = () => {
      if (!stoppedRef.current) {
        try { rec.start(); } catch {}
      }
    };
    rec.onerror = (e) => {
      if (e?.error === "not-allowed" || e?.error === "service-not-allowed") {
        stoppedRef.current = true;
      }
    };
    try { rec.start(); recRef.current = rec; } catch {}

    return () => {
      stoppedRef.current = true;
      try { rec.stop(); } catch {}
      recRef.current = null;
    };
  }, [enabled, lang, onWake]);
};

// ---------- Siri-style Voice Mode (hands-free, cross-platform reliable) ----------
// Uses MediaRecorder + WebAudio silence detection + Whisper STT + OpenAI TTS.
// Works on iOS Safari, Android, Chrome, Edge, Firefox.
//
// iOS audio-unlock trick: on first ever user gesture in the app, we prime an AudioContext
// + a silent <audio> element so subsequent programmatic playback isn't blocked.
let _audioUnlocked = false;
const unlockAudio = () => {
  if (_audioUnlocked) return;
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (Ctx) {
      const ctx = new Ctx();
      const buffer = ctx.createBuffer(1, 1, 22050);
      const src = ctx.createBufferSource();
      src.buffer = buffer; src.connect(ctx.destination); src.start(0);
      ctx.resume?.();
    }
    const a = document.createElement("audio");
    a.muted = true; a.playsInline = true; a.preload = "auto";
    a.src = "data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQwAADB8AhSmxhIBHHCk6ABMjMTRgQRMAAAAAA////////////////////////////////////////////////////8AAAA8";
    a.play().catch(() => {});
    _audioUnlocked = true;
  } catch {}
};

function VoiceModeOverlay({ lang, country, category, initialText, onClose }) {
  const [phase, setPhase] = useState("ready"); // ready | listening | thinking | speaking | tap-to-play
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [pendingAudioUrl, setPendingAudioUrl] = useState(null);

  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const rafRef = useRef(null);
  const silenceStartRef = useRef(0);
  const speakingDetectedRef = useRef(false);
  const audioElRef = useRef(null);
  const cancelledRef = useRef(false);
  const startTimeRef = useRef(0);

  const SILENCE_MS = 1200;
  const SPEECH_THRESH = 0.012;
  const MAX_RECORD_MS = 30000;

  const stopAll = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    try { recorderRef.current?.stop(); } catch {}
    recorderRef.current = null;
    try { audioCtxRef.current?.close(); } catch {}
    audioCtxRef.current = null; analyserRef.current = null;
    try { streamRef.current?.getTracks().forEach(t => t.stop()); } catch {}
    streamRef.current = null;
    try { audioElRef.current?.pause(); } catch {}
  }, []);

  // Attempt to play TTS; if iOS autoplay blocks, surface a "Tap to hear" button
  const tryPlayAudio = useCallback(async (url) => {
    const a = audioElRef.current;
    if (!a) { startListening(); return; }
    a.src = url;
    a.onended = () => { if (!cancelledRef.current) startListening(); };
    try {
      await a.play();
      setPendingAudioUrl(null);
    } catch (err) {
      // iOS blocked it — show the tap button
      setPendingAudioUrl(url);
      setPhase("tap-to-play");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sendAudio = useCallback(async (blob) => {
    if (!blob || blob.size < 1500) {
      if (!cancelledRef.current) startListening();
      return;
    }
    setPhase("thinking");
    try {
      const fd = new FormData();
      fd.append("audio", blob, "voice.webm");
      fd.append("language", (lang || "en").split("-")[0]);
      const stt = await api.post("/voice/transcribe", fd);
      const userText = (stt.data?.text || "").trim();
      if (cancelledRef.current) return;
      if (!userText) { startListening(); return; }
      setTranscript(userText);
      const chat = await api.post("/lex/chat", {
        session_id: sessionId, message: userText, language: lang, country, category: category || "ask_lex",
      });
      if (cancelledRef.current) return;
      setSessionId(chat.data.session_id);
      setReply(chat.data.response);
      setPhase("speaking");
      const tts = await api.post("/voice/tts",
        { text: chat.data.response, language: (lang || "en").split("-")[0] },
        { responseType: "blob" });
      if (cancelledRef.current) return;
      tryPlayAudio(URL.createObjectURL(tts.data));
    } catch (e) {
      const msg = e?.response?.data?.detail || e?.message || "Network error";
      setError(msg);
      setPhase("ready");
      setTimeout(() => { if (!cancelledRef.current) { setError(""); startListening(); } }, 1500);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, lang, country, category, tryPlayAudio]);

  const startListening = useCallback(async () => {
    if (cancelledRef.current) return;
    setTranscript(""); setReply(""); setError(""); setPendingAudioUrl(null);
    setPhase("listening");
    speakingDetectedRef.current = false;
    silenceStartRef.current = 0;
    chunksRef.current = [];

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (e) {
      setError("Microphone permission denied. Please enable it in your browser settings.");
      setPhase("ready");
      return;
    }
    streamRef.current = stream;
    startTimeRef.current = Date.now();

    const mime = (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported) ?
      (MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4" :
       MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" :
       MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "") : "";
    let recorder;
    try { recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream); }
    catch (e) { setError("Recording not supported in this browser."); setPhase("ready"); return; }
    recorderRef.current = recorder;

    recorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunksRef.current.push(e.data); };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: mime || "audio/webm" });
      try { streamRef.current?.getTracks().forEach(t => t.stop()); } catch {}
      try { audioCtxRef.current?.close(); } catch {}
      audioCtxRef.current = null; analyserRef.current = null;
      streamRef.current = null;
      sendAudio(blob);
    };
    try { recorder.start(); } catch (e) { setError("Could not start recorder"); setPhase("ready"); return; }

    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      const ctx = new Ctx();
      audioCtxRef.current = ctx;
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      analyserRef.current = analyser;
      src.connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);

      const tick = () => {
        if (!analyserRef.current || cancelledRef.current) return;
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        const now = Date.now();
        const elapsed = now - startTimeRef.current;
        if (rms > SPEECH_THRESH) {
          speakingDetectedRef.current = true;
          silenceStartRef.current = 0;
        } else if (speakingDetectedRef.current) {
          if (silenceStartRef.current === 0) silenceStartRef.current = now;
          else if (now - silenceStartRef.current > SILENCE_MS) {
            try { recorder.stop(); } catch {}
            return;
          }
        }
        if (elapsed > MAX_RECORD_MS) { try { recorder.stop(); } catch {}; return; }
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch (e) {
      setTimeout(() => { try { recorder.stop(); } catch {} }, 8000);
    }
  }, [sendAudio]);

  const sendInitialText = useCallback(async (text) => {
    setPhase("thinking");
    setTranscript(text);
    try {
      const chat = await api.post("/lex/chat", { session_id: sessionId, message: text, language: lang, country, category: category || "ask_lex" });
      if (cancelledRef.current) return;
      setSessionId(chat.data.session_id);
      setReply(chat.data.response);
      setPhase("speaking");
      const tts = await api.post("/voice/tts", { text: chat.data.response, language: (lang || "en").split("-")[0] }, { responseType: "blob" });
      if (cancelledRef.current) return;
      tryPlayAudio(URL.createObjectURL(tts.data));
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not reach Lex.");
      setPhase("ready");
      setTimeout(() => { if (!cancelledRef.current) { setError(""); startListening(); } }, 1500);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, lang, country, category, tryPlayAudio, startListening]);

  useEffect(() => {
    cancelledRef.current = false;
    unlockAudio();
    const initial = (initialText || "").trim();
    if (initial.length > 2) sendInitialText(initial);
    else startListening();
    return () => { cancelledRef.current = true; stopAll(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const phaseLabel = phase === "listening" ? "Listening…"
                    : phase === "thinking" ? "Thinking…"
                    : phase === "speaking" ? "Lex is speaking…"
                    : phase === "tap-to-play" ? "Tap to hear Lex"
                    : "Tap mic to speak";

  return (
    <div className="modal-bg" data-testid="voice-mode-overlay" style={{ background: "rgba(0,0,0,0.96)" }}>
      <div style={{ maxWidth: 480, margin: "0 auto", padding: 24, height: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", position: "relative" }}>
        <button onClick={onClose} data-testid="voice-mode-close" style={{ position: "absolute", top: 22, right: 22, background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}>
          <X size={28} />
        </button>

        <div className={`voice-orb ${phase}`} data-testid="voice-orb" style={{
          width: 180, height: 180, borderRadius: "50%",
          background: "#000",
          border: "3px solid var(--gold)",
          overflow: "hidden",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: phase === "speaking" ? "0 0 60px rgba(247,201,72,0.85)"
                    : phase === "thinking" ? "0 0 30px rgba(247,201,72,0.45)"
                    : phase === "listening" ? "0 0 50px rgba(247,201,72,0.75)"
                    : "0 0 18px rgba(247,201,72,0.35)",
          marginBottom: 26,
          animation: phase === "listening" ? "voicePulse 1.6s ease-in-out infinite" : "none",
        }}>
          <img src="/assets/lex.jpg" alt="Lex" style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%", mixBlendMode: "lighten" }} />
        </div>

        <div data-testid="voice-mode-phase" style={{ fontSize: 14, color: "var(--gold)", letterSpacing: "0.08em", textTransform: "uppercase", fontFamily: "Cinzel, serif", marginBottom: 16 }}>
          {phaseLabel}
        </div>

        {transcript && (
          <div data-testid="voice-mode-transcript" style={{ color: "var(--text-dim)", fontSize: 13, textAlign: "center", padding: "0 14px", marginBottom: 10, fontStyle: "italic" }}>
            "{transcript}"
          </div>
        )}
        {reply && (
          <div data-testid="voice-mode-reply" style={{ color: "var(--text)", fontSize: 14, textAlign: "center", padding: "0 14px", maxHeight: "26vh", overflowY: "auto", lineHeight: 1.55 }}>
            {reply}
          </div>
        )}
        {error && (
          <div data-testid="voice-mode-error" style={{ color: "#fca5a5", fontSize: 13, textAlign: "center", padding: "10px 14px", marginTop: 8, background: "rgba(127,29,29,0.3)", border: "1px solid #7f1d1d", borderRadius: 10 }}>
            {error}
          </div>
        )}

        {/* "Tap to hear Lex" fallback for iOS autoplay block */}
        {phase === "tap-to-play" && pendingAudioUrl && (
          <button data-testid="voice-mode-tap-to-play"
            onClick={async () => {
              const a = audioElRef.current;
              if (!a) return;
              try { await a.play(); setPhase("speaking"); setPendingAudioUrl(null); }
              catch (err) { setError("Could not play audio. " + (err?.message || "")); }
            }}
            style={{ marginTop: 16, padding: "14px 24px", background: "var(--gold)", color: "#1a1300",
                     border: "none", borderRadius: 30, fontWeight: 700, fontSize: 15,
                     boxShadow: "0 0 24px rgba(247,201,72,0.7)", cursor: "pointer",
                     fontFamily: "Cinzel, serif", letterSpacing: "0.06em" }}>
            ▶ TAP TO HEAR LEX
          </button>
        )}

        <div style={{ marginTop: "auto", display: "flex", gap: 12 }}>
          <button onClick={() => { unlockAudio(); stopAll(); try { audioElRef.current?.pause(); } catch {}; startListening(); }}
            data-testid="voice-mode-mic" title={t(lang, "talkToLex")}
            style={{ background: "#000", border: "2px solid var(--gold)", borderRadius: "50%",
                     width: 76, height: 76, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                     boxShadow: phase === "listening" ? "0 0 20px rgba(247,201,72,0.6)" : "none" }}>
            <Mic size={32} style={{ color: "var(--gold)" }} />
          </button>
        </div>

        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 14, textAlign: "center", padding: "0 20px" }}>
          Speak naturally. Lex will respond when you pause for ~2 seconds.
          <br/>Tap the gold mic to re-speak · Tap X to close.
        </div>

        <audio ref={audioElRef} style={{ display: "none" }} playsInline />
      </div>
    </div>
  );
}

// ---------- Lex Chat ----------
function LexChat({ lang, country, category, title, onClose, autoMic = false, tier = "free", onSwitchCategory, initialSeed = "" }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [deepThink, setDeepThink] = useState(false);
  const [dtUsed, setDtUsed] = useState(null); // {used, limit}
  const [smartCat, setSmartCat] = useState(null);  // suggested category banner
  const { recording, start, stop } = useRecorder();
  const audioRef = useRef(null);
  const scrollRef = useRef(null);
  const autoStartedRef = useRef(false);
  const seedSentRef = useRef(false);
  const classifiedRef = useRef(false);

  // ⚖ One-time UPL acknowledgment — App Store + UK Legal Services Act 2007 evidence trail.
  // Persisted per-device so users only see this once. Required disclosure: this is
  // information, not regulated legal advice, no solicitor-client relationship.
  const [showUplAck, setShowUplAck] = useState(() => !localStorage.getItem("aa_lex_upl_ack"));
  const acceptUpl = () => { localStorage.setItem("aa_lex_upl_ack", new Date().toISOString()); setShowUplAck(false); };

  const isPro = tier === "pro" || tier === "yearly" || tier === "trial_pro";

  useEffect(() => { scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [messages, busy]);

  // Load Deep Think usage so the user sees their counter (Pro-only)
  useEffect(() => {
    if (!isPro) return;
    api.get("/subscription/usage").then(r => {
      const u = r.data?.usage?.deep_think;
      if (u) setDtUsed({ used: u.used, limit: u.limit });
    }).catch(() => {});
  }, [isPro]);

  // Auto-start mic when triggered by "Hey Lex" wake word
  useEffect(() => {
    if (autoMic && !autoStartedRef.current) {
      autoStartedRef.current = true;
      // small delay so the modal animation finishes
      const id = setTimeout(() => { start(); }, 350);
      return () => clearTimeout(id);
    }
  }, [autoMic, start]);

  // Auto-send an initial seed message (e.g. from Courtroom Live Assist "Ask Lex to review")
  useEffect(() => {
    if (initialSeed && !seedSentRef.current) {
      seedSentRef.current = true;
      // small delay so the modal animates open first
      const id = setTimeout(() => { send(initialSeed); }, 200);
      return () => clearTimeout(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialSeed]);

  const send = async (text) => {
    if (!text.trim()) return;
    setMessages(m => [...m, { role: "user", content: text, at: new Date().toISOString() }]); setInput(""); setBusy(true);

    const autoDetect = localStorage.getItem("aa_autodetect") !== "0";
    // 🚀 Real SSE streaming — tokens render as the LLM produces them.
    // We use fetch + ReadableStream (EventSource doesn't support POST).
    // If the stream fails for any reason we fall back to the buffered endpoint.
    let streamed = false;
    try {
      const token = localStorage.getItem("aa_token");
      const resp = await fetch(`${API}/lex/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "text/event-stream",
                   ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          message: text, session_id: sessionId, language: lang, country, category,
          deep_think: deepThink && isPro, auto_detect: autoDetect,
        }),
      });
      if (!resp.ok || !resp.body) throw new Error(`stream ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let lexMsgIndex = -1;          // index of the in-flight assistant bubble
      let assembled = "";            // running accumulated text (raw)
      let finalMeta = null;          // meta event payload
      let finalDone = null;          // done event payload

      // Helper to strip Lex's internal markers from displayed text.
      // The full marker block is at the END of the response, so we cut from
      // the first occurrence of any of these onwards.
      const stripMarkers = (s) => {
        if (!s) return s;
        const cuts = ["[CONFIDENCE:", "[SOURCES:", "[CONNECTED_TO:", "\nDisclaimer:"];
        let earliest = s.length;
        for (const c of cuts) {
          const i = s.indexOf(c);
          if (i >= 0 && i < earliest) earliest = i;
        }
        return s.slice(0, earliest).trimEnd();
      };

      // Insert the placeholder Lex bubble immediately so the user sees "typing…"
      setMessages(ms => {
        const next = [...ms, { role: "lex", content: "", at: new Date().toISOString(), _typing: true, citations: [], model: null, replyLang: null, connectedSessionId: null }];
        lexMsgIndex = next.length - 1;
        return next;
      });

      // Client-side typewriter reveal that runs IN PARALLEL with token arrival.
      // Why? Emergent's LLM proxy currently buffers the full response — even with
      // stream=True, all tokens arrive as one burst at the end. The typewriter
      // gives us a smooth reveal regardless of whether tokens trickle (true SSE,
      // once Emergent enables it) or land in a burst (current proxy behaviour).
      let displayed = 0;
      let revealTimer = null;
      let streamDone = false;
      const stepChars = 30;
      const stepMs = 25;
      const tickReveal = () => {
        const visible = stripMarkers(assembled);
        if (displayed >= visible.length) {
          if (streamDone) {
            setMessages(ms => ms.map((mm, idx) => idx === lexMsgIndex
              ? { ...mm, content: visible, _typing: false, connectedSessionId: finalDone?.connected_session_id || null }
              : mm));
            return;
          }
          // Waiting for more tokens — re-check soon
          revealTimer = setTimeout(tickReveal, stepMs);
          return;
        }
        displayed = Math.min(visible.length, displayed + stepChars);
        const slice = visible.slice(0, displayed);
        setMessages(ms => ms.map((mm, idx) => idx === lexMsgIndex ? { ...mm, content: slice } : mm));
        revealTimer = setTimeout(tickReveal, stepMs);
      };
      tickReveal();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE events are separated by \n\n
        let nlIdx;
        while ((nlIdx = buffer.indexOf("\n\n")) >= 0) {
          const chunk = buffer.slice(0, nlIdx).trim();
          buffer = buffer.slice(nlIdx + 2);
          if (!chunk.startsWith("data:")) continue;
          let payload;
          try { payload = JSON.parse(chunk.slice(5).trim()); } catch { continue; }

          if (payload.type === "meta") {
            finalMeta = payload;
            setSessionId(payload.session_id);
            setMessages(ms => ms.map((mm, idx) => idx === lexMsgIndex
              ? { ...mm, citations: payload.citations || [], model: payload.model, replyLang: payload.reply_language }
              : mm));
          } else if (payload.type === "token") {
            // Just accumulate — the typewriter loop drives the visual reveal.
            // (Currently Emergent's proxy buffers and emits the whole response
            // as one chunk, but if real streaming ever lands, this still works.)
            assembled += payload.text || "";
          } else if (payload.type === "done") {
            finalDone = payload;
            // If `done` arrived before any tokens (rare error path), make sure
            // we still surface the full_text the backend computed.
            if (!assembled && payload.full_text) assembled = payload.full_text;
          } else if (payload.type === "error") {
            throw new Error(payload.message || "stream error");
          }
        }
      }

      // Signal the typewriter that no more tokens are coming — it will finish
      // revealing whatever's left then mark the bubble as no longer typing.
      streamDone = true;
      streamed = true;

      // Post-stream side effects (smart category, deep-think usage, reminders/deadlines)
      const finalText = stripMarkers(finalDone?.full_text || assembled);
      const data = { response: finalText, reply_language: finalMeta?.reply_language, model: finalMeta?.model };
      if (category === "ask_lex" && !classifiedRef.current && onSwitchCategory) {
        classifiedRef.current = true;
        api.post("/lex/classify", { text }).then(rc => {
          const d = rc?.data;
          const known = { employment: "employment", property: "property", immigration: "immigration", medical: "medical_negligence" };
          if (d && d.confidence !== "low" && known[d.category]) setSmartCat({ category: d.category, mapped: known[d.category] });
        }).catch(() => {});
      }
      if (isPro && deepThink) {
        api.get("/subscription/usage").then(r => {
          const u = r.data?.usage?.deep_think;
          if (u) setDtUsed({ used: u.used, limit: u.limit });
        }).catch(() => {});
      }
      const fd = new FormData();
      fd.append("message", text); fd.append("language", lang); fd.append("country", country);
      api.post("/reminders/detect", fd).then(r => {
        const dls = r.data?.deadlines || [];
        if (dls.length) setMessages(m => [...m, { role: "deadlines", content: "", at: new Date().toISOString(), deadlines: dls }]);
      }).catch(() => {});
      try {
        const r = await api.post("/voice/tts", { text: finalText.slice(0, 1500), voice: "fable", language: data.reply_language }, { responseType: "blob" });
        const url = URL.createObjectURL(r.data);
        if (audioRef.current) { audioRef.current.src = url; audioRef.current.play().catch(() => {}); }
      } catch {}
    } catch (streamErr) {
      // Streaming failed — fall back to the buffered endpoint with the original
      // typewriter animation. User sees a tiny delay but never a broken chat.
      if (streamed) { setBusy(false); return; }
      console.warn("Streaming chat failed, falling back to buffered:", streamErr);
      try {
        const { data } = await api.post("/lex/chat", {
          message: text, session_id: sessionId, language: lang, country, category,
          deep_think: deepThink && isPro, auto_detect: autoDetect,
        });
        setSessionId(data.session_id);
        const fullText = data.response;
        const lexMsg = { role: "lex", content: "", _fullContent: fullText, at: new Date().toISOString(), model: data.model, replyLang: data.reply_language, connectedSessionId: data.connected_session_id || null, citations: data.citations || [], _typing: true };
        setMessages(m => [...m, lexMsg]);
        let revealed = 0;
        const step = 30;
        const tick = () => {
          if (revealed >= fullText.length) {
            setMessages(ms => ms.map((mm, idx) => idx === ms.length - 1 && mm._typing ? { ...mm, content: fullText, _typing: false, _fullContent: undefined } : mm));
            return;
          }
          revealed += step;
          const slice = fullText.slice(0, revealed);
          setMessages(ms => ms.map((mm, idx) => idx === ms.length - 1 && mm._typing ? { ...mm, content: slice } : mm));
          setTimeout(tick, 25);
        };
        tick();
        try {
          const r = await api.post("/voice/tts", { text: data.response.slice(0, 1500), voice: "fable", language: data.reply_language }, { responseType: "blob" });
          const url = URL.createObjectURL(r.data);
          if (audioRef.current) { audioRef.current.src = url; audioRef.current.play().catch(() => {}); }
        } catch {}
      } catch (e) {
        setMessages(m => [...m, { role: "lex", content: e?.response?.data?.detail || "Error: try again" }]);
      }
    } finally { setBusy(false); }
  };

  const addDeadlineAsReminder = async (dl, idx) => {
    try {
      await api.post("/reminders", { title: dl.title, due_at: dl.due_at, kind: dl.kind || "deadline" });
      // Mark this deadline as "added" in the local message
      setMessages(ms => ms.map((m, i) => {
        if (m.role !== "deadlines") return m;
        const newDls = m.deadlines.map((d, di) => di === idx ? { ...d, _added: true } : d);
        return { ...m, deadlines: newDls };
      }));
    } catch (e) {
      alert(e?.response?.data?.detail || t(lang, "failed"));
    }
  };

  const onMic = async () => {
    if (recording) {
      const blob = await stop();
      if (!blob) return;
      setBusy(true);
      const fd = new FormData(); fd.append("audio", blob, "rec.webm"); fd.append("language", lang.split("-")[0]);
      try {
        const { data } = await api.post("/voice/transcribe", fd);
        if (data.text) await send(data.text);
        else setBusy(false);
      } catch (e) { setBusy(false); alert(e?.response?.data?.detail || "Transcribe failed"); }
    } else { start(); }
  };

  return (
    <div className="modal-bg" data-testid="lex-chat-modal">
      {/* ⚖ First-use UPL acknowledgment — UK Legal Services Act 2007 evidence trail */}
      {showUplAck && (
        <div data-testid="lex-upl-modal" style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 100002,
          display: "flex", alignItems: "center", justifyContent: "center", padding: 20,
        }}>
          <div style={{
            background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 16,
            padding: 24, maxWidth: 400, width: "100%", boxShadow: "0 20px 60px rgba(0,0,0,0.7)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
              <ShieldCheck size={22} style={{ color: "var(--gold)" }} />
              <div className="brand-font gold" style={{ fontSize: 16, letterSpacing: "0.05em" }}>Before you ask Lex</div>
            </div>
            <div style={{ color: "var(--text)", fontSize: 13.5, lineHeight: 1.6, marginBottom: 18 }}>
              <p style={{ marginTop: 0 }}>Lex is an <strong style={{ color: "var(--gold-soft)" }}>AI legal information assistant</strong> — not a solicitor, barrister, or qualified lawyer.</p>
              <p style={{ margin: "12px 0 0" }}>By continuing you confirm you understand:</p>
              <ul style={{ marginTop: 6, paddingLeft: 18, color: "var(--text-dim)", fontSize: 12.5 }}>
                <li>Lex provides <strong>general legal information</strong>, not regulated legal advice.</li>
                <li>No solicitor-client relationship is created (Legal Services Act 2007).</li>
                <li>AI can be wrong — <strong>always verify</strong> with a qualified solicitor before acting.</li>
                <li>For arrests, court hearings, or life-changing decisions, instruct a regulated lawyer.</li>
              </ul>
            </div>
            <button data-testid="lex-upl-accept" onClick={acceptUpl}
              className="btn-gold" style={{ width: "100%", padding: "12px 16px", fontSize: 14, fontWeight: 700 }}>
              I understand — continue to Lex
            </button>
            <button data-testid="lex-upl-decline" onClick={() => { setShowUplAck(false); onClose(); }}
              style={{ width: "100%", marginTop: 8, padding: "10px 16px", background: "transparent", color: "var(--text-muted)", border: "1px solid var(--line)", borderRadius: 10, fontSize: 12, cursor: "pointer" }}>
              Cancel
            </button>
          </div>
        </div>
      )}
      <div className="modal-card" style={{ height: "90vh" }}>
        <div className="flex items-center justify-between" style={{ padding: 16, borderBottom: "1px solid var(--line)" }}>
          <div>
            <div className="brand-font gold" style={{ fontSize: 18, letterSpacing: "0.04em" }}>{title || "LEX"}</div>
            <div style={{ fontSize: 11, color: "var(--text-muted)" }}>AI Advocate</div>
          </div>
          <div className="flex items-center gap-2">
            {/* Deep Think toggle — Pro only with monthly counter */}
            <button data-testid="deep-think-toggle"
              onClick={() => {
                if (!isPro) { alert(t(lang, "deepThinkProOnly")); return; }
                setDeepThink(v => !v);
              }}
              title={t(lang, "deepThink") + (dtUsed && dtUsed.limit != null ? ` — ${dtUsed.used}/${dtUsed.limit}` : "")}
              style={{
                background: deepThink && isPro ? "var(--gold)" : "transparent",
                color: deepThink && isPro ? "#1a1300" : (isPro ? "var(--gold)" : "var(--text-muted)"),
                border: `1px solid ${isPro ? "var(--gold-deep)" : "var(--line)"}`,
                borderRadius: 16, padding: "5px 10px", fontSize: 11, cursor: "pointer",
                fontWeight: 600, letterSpacing: "0.04em",
              }}>
              🧠 {deepThink && isPro ? t(lang, "deepThinkOn") : t(lang, "deepThink")}
              {isPro && dtUsed && dtUsed.limit != null ? (
                <span data-testid="dt-counter" style={{ marginLeft: 6, fontSize: 10, opacity: 0.8 }}>
                  {dtUsed.used}/{dtUsed.limit}
                </span>
              ) : (!isPro ? " 🔒" : null)}
            </button>
            <button onClick={onClose} data-testid="lex-close-btn" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}>
              <X size={24} />
            </button>
          </div>
        </div>

        <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
          {/* Legal disclaimer — dismissible, shown once per session */}
          <LexDisclaimerBanner lang={lang} />
          {messages.length === 0 && (
            <div style={{ textAlign: "center", color: "var(--text-muted)", marginTop: 24, padding: "0 6px" }}>
              <p style={{ marginTop: 6, marginBottom: 6 }}>{t(lang, "chatPlaceholder")}</p>
              {!category || category === "ask_lex" ? (
                <>
                  <div style={{ fontSize: 11, color: "var(--gold)", marginTop: 18, marginBottom: 8, letterSpacing: "0.06em", textTransform: "uppercase" }}>
                    {t(lang, "suggestionsTitle")}
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center" }}>
                    {["sug1", "sug2", "sug3", "sug4", "sug5", "sug6"].map(k => (
                      <button key={k} data-testid={`suggestion-${k}`} onClick={() => send(t(lang, k))}
                              style={{ background: "rgba(247,201,72,0.08)", border: "1px solid var(--gold-deep)", color: "var(--gold-soft)", borderRadius: 16, padding: "7px 12px", fontSize: 12, cursor: "pointer", fontFamily: "Outfit, sans-serif" }}>
                        {t(lang, k)}
                      </button>
                    ))}
                  </div>
                </>
              ) : null}
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
              {m.role === "deadlines" ? (
                <div data-testid={`deadline-card-${i}`} style={{ background: "rgba(220,38,38,0.15)", border: "1px solid #fca5a5", borderRadius: 12, padding: 12, width: "100%", marginTop: 4 }}>
                  <div style={{ color: "#fca5a5", fontWeight: 700, fontSize: 12, marginBottom: 6 }}>⏰ {t(lang, "deadlineFound")}</div>
                  {(m.deadlines || []).map((dl, di) => (
                    <div key={di} style={{ marginBottom: 6 }}>
                      <div style={{ color: "var(--text)", fontSize: 13, fontWeight: 600 }}>{dl.title}</div>
                      <div style={{ color: "var(--text-muted)", fontSize: 11, marginBottom: 4 }}>
                        Due {new Date(dl.due_at).toLocaleString()}
                      </div>
                      <button data-testid={`add-deadline-${i}-${di}`} onClick={() => addDeadlineAsReminder(dl, di)} disabled={dl._added}
                        style={{ background: dl._added ? "var(--bg-card)" : "var(--gold)", color: dl._added ? "var(--text-muted)" : "#1a1300",
                                 border: "none", borderRadius: 12, padding: "5px 12px", fontSize: 11, fontWeight: 600, cursor: dl._added ? "default" : "pointer" }}>
                        {dl._added ? "✓ Added" : t(lang, "addToReminders")}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <>
                  {(() => {
                    const meta = m.role === "lex" ? parseLexMetadata(m.content) : { body: m.content, confidence: null, sources: [], connectedTo: null };
                    return (
                      <>
                        {meta.connectedTo && (() => {
                          const targetId = m.connectedSessionId;
                          const clickable = !!targetId;
                          const handler = clickable ? async () => {
                            try {
                              setBusy(true);
                              const r = await api.get(`/lex/sessions/${targetId}`);
                              const loaded = (r.data || []).flatMap(row => [
                                { role: "user", content: row.user_message, at: row.created_at },
                                { role: "lex", content: row.assistant_response, at: row.created_at, model: row.model_used, citations: row.citations || [] },
                              ]);
                              setMessages(loaded);
                              setSessionId(targetId);
                              classifiedRef.current = true;  // skip auto-categorisation on loaded thread
                            } catch {
                              // silent — fail gracefully, user can still keep chatting in current session
                            } finally {
                              setBusy(false);
                            }
                          } : undefined;
                          return (
                            <div data-testid={`connected-${i}`}
                                 onClick={handler}
                                 title={clickable ? "Tap to open this earlier conversation" : ""}
                                 style={{
                                   display: "inline-flex", alignItems: "center", gap: 6,
                                   background: "rgba(247,201,72,0.08)",
                                   border: `1px solid ${clickable ? "var(--gold)" : "var(--gold-deep)"}`,
                                   color: "var(--gold)", borderRadius: 999, padding: "3px 10px",
                                   fontSize: 11, marginBottom: 6, alignSelf: "flex-start",
                                   cursor: clickable ? "pointer" : "default",
                                   transition: "background 150ms, transform 150ms",
                                 }}
                                 onMouseEnter={(e) => { if (clickable) e.currentTarget.style.background = "rgba(247,201,72,0.18)"; }}
                                 onMouseLeave={(e) => { if (clickable) e.currentTarget.style.background = "rgba(247,201,72,0.08)"; }}>
                              <Sparkles size={11} /> Connected to: {meta.connectedTo}
                              {clickable && <ExternalLink size={10} style={{ opacity: 0.8, marginLeft: 2 }} />}
                            </div>
                          );
                        })()}
                        <div className={m.role === "user" ? "bubble-user" : "bubble-lex"}
                             data-testid={`msg-${m.role}-${i}`}
                             style={{ padding: "10px 14px", borderRadius: 14, maxWidth: "82%", whiteSpace: "pre-wrap", lineHeight: 1.5, fontSize: 14 }}>
                          {m.role === "lex" && Array.isArray(m.citations) && m.citations.length > 0
                            ? renderWithCitationPills(meta.body, m.citations, i)
                            : meta.body}
                        </div>
                        {/* RAG citations list — appears under the bubble when Tavily returned sources */}
                        {m.role === "lex" && Array.isArray(m.citations) && m.citations.length > 0 && (
                          <div data-testid={`citations-${i}`} style={{
                            display: "flex", flexDirection: "column", gap: 4, marginTop: 6,
                            alignSelf: "flex-start", maxWidth: "82%",
                            background: "rgba(247,201,72,0.05)", border: "1px solid var(--line)",
                            borderRadius: 10, padding: "8px 10px",
                          }}>
                            <div style={{ fontSize: 9, color: "var(--gold-soft)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>
                              📜 Sources cited above — tap to verify
                            </div>
                            {m.citations.map((c) => (
                              <a key={c.n} href={c.url} target="_blank" rel="noopener noreferrer"
                                 data-testid={`citation-row-${i}-${c.n}`}
                                 style={{
                                   color: "var(--gold-soft)", fontSize: 11, textDecoration: "none",
                                   display: "flex", alignItems: "center", gap: 6, lineHeight: 1.4,
                                 }}
                                 onMouseEnter={(e) => { e.currentTarget.style.color = "var(--gold)"; }}
                                 onMouseLeave={(e) => { e.currentTarget.style.color = "var(--gold-soft)"; }}>
                                <span style={{
                                  background: c.source === "official" ? "var(--gold)" : "var(--gold-deep)",
                                  color: c.source === "official" ? "#0a0a0a" : "#1a1300",
                                  borderRadius: 999, padding: "1px 6px",
                                  fontSize: 9, fontWeight: 700, flexShrink: 0,
                                }}>[{c.n}]</span>
                                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.title}</span>
                                <ExternalLink size={10} style={{ opacity: 0.65, flexShrink: 0 }} />
                              </a>
                            ))}
                          </div>
                        )}
                        {m.role === "lex" && (meta.confidence || meta.sources.length > 0) && (
                          <div data-testid={`lex-meta-${i}`} style={{
                            display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6, alignSelf: "flex-start", maxWidth: "82%",
                          }}>
                            {meta.confidence && (
                              <span style={{
                                display: "inline-flex", alignItems: "center", gap: 4,
                                background: meta.confidence === "HIGH" ? "rgba(34,197,94,0.12)"
                                          : meta.confidence === "MEDIUM" ? "rgba(247,201,72,0.12)"
                                          : "rgba(239,68,68,0.12)",
                                border: `1px solid ${meta.confidence === "HIGH" ? "#22c55e" : meta.confidence === "MEDIUM" ? "var(--gold-deep)" : "#ef4444"}`,
                                color: meta.confidence === "HIGH" ? "#22c55e" : meta.confidence === "MEDIUM" ? "var(--gold)" : "#ef4444",
                                fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                                padding: "2px 8px", borderRadius: 999,
                              }}>
                                <ShieldCheck size={10} /> {meta.confidence}
                              </span>
                            )}
                            {meta.sources.map((src, si) => {
                              const url = buildSourceUrl(src);
                              const chipStyle = {
                                display: "inline-flex", alignItems: "center", gap: 4,
                                background: "rgba(255,255,255,0.04)", border: "1px solid var(--line)",
                                color: "var(--gold-soft)", fontSize: 10, padding: "2px 8px",
                                borderRadius: 999, textDecoration: "none",
                                transition: "background 150ms, border-color 150ms",
                              };
                              return url ? (
                                <a key={si} href={url} target="_blank" rel="noopener noreferrer"
                                   title={`Open ${src} on the official source`}
                                   data-testid={`source-link-${i}-${si}`}
                                   onClick={(e) => e.stopPropagation()}
                                   onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(247,201,72,0.10)"; e.currentTarget.style.borderColor = "var(--gold-deep)"; }}
                                   onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.04)"; e.currentTarget.style.borderColor = "var(--line)"; }}
                                   style={chipStyle}>
                                  {src} <ExternalLink size={9} style={{ opacity: 0.7 }} />
                                </a>
                              ) : (
                                <span key={si} title="Source Lex cited" style={{ ...chipStyle, color: "var(--text-dim)" }}>
                                  {src}
                                </span>
                              );
                            })}
                          </div>
                        )}
                      </>
                    );
                  })()}
                  {m.role === "lex" && (
                    <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                      <button data-testid={`fb-up-${i}`} title="Helpful" disabled={m._fb}
                        onClick={async () => {
                          try { await api.post("/feedback", { rating: "up", session_id: sessionId, surface: "lex_chat" }); } catch {}
                          setMessages(ms => ms.map((mm, ii) => ii === i ? { ...mm, _fb: "up" } : mm));
                        }}
                        style={{ background: m._fb === "up" ? "rgba(34,197,94,0.2)" : "transparent",
                                 border: "1px solid var(--line)", color: m._fb === "up" ? "#22c55e" : "var(--text-muted)",
                                 borderRadius: 8, padding: "2px 8px", fontSize: 11, cursor: m._fb ? "default" : "pointer" }}>
                        👍
                      </button>
                      <button data-testid={`fb-down-${i}`} title="Not helpful" disabled={m._fb}
                        onClick={async () => {
                          try { await api.post("/feedback", { rating: "down", session_id: sessionId, surface: "lex_chat" }); } catch {}
                          setMessages(ms => ms.map((mm, ii) => ii === i ? { ...mm, _fb: "down" } : mm));
                        }}
                        style={{ background: m._fb === "down" ? "rgba(239,68,68,0.2)" : "transparent",
                                 border: "1px solid var(--line)", color: m._fb === "down" ? "#ef4444" : "var(--text-muted)",
                                 borderRadius: 8, padding: "2px 8px", fontSize: 11, cursor: m._fb ? "default" : "pointer" }}>
                        👎
                      </button>
                    </div>
                  )}
                  {m.at && (
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2, padding: "0 6px" }} data-testid={`ts-${i}`}>
                      {new Date(m.at).toLocaleString()}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
          {busy && (
            <div className="bubble-lex aa-lex-typing" style={{ alignSelf: "flex-start", padding: "10px 14px", borderRadius: 14, display: "inline-flex", alignItems: "center", gap: 8 }}>
              <span className="aa-typing-dots"><span /><span /><span /></span>
              <span style={{ color: "var(--text-dim)", fontSize: 13 }}>
                {messages.length > 1 ? "Lex is reading the conversation…" : "Lex is thinking…"}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2" style={{ padding: "12px 12px 56px", borderTop: "1px solid var(--line)" }}>
          <button onClick={onMic} data-testid="mic-btn"
                  style={{ background: "#000", border: `2px solid ${recording ? "var(--danger)" : "var(--gold)"}`,
                           borderRadius: "50%", width: 48, height: 48, cursor: "pointer", padding: 0, overflow: "hidden",
                           display: "flex", alignItems: "center", justifyContent: "center", position: "relative",
                           boxShadow: recording ? "0 0 0 4px rgba(220,38,38,0.25)" : "0 0 14px rgba(247,201,72,0.35)" }}
                  className={recording ? "recording" : ""}>
            {recording ? (
              <Square size={18} style={{ color: "var(--danger)" }} />
            ) : (
              <img src="/assets/lex.jpg" alt="Lex"
                   style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%", mixBlendMode: "lighten" }} />
            )}
          </button>
          <input className="input" data-testid="chat-input" placeholder={t(lang, "chatPlaceholder")} value={input} onChange={(e) => setInput(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && send(input)} style={{ flex: 1 }} />
          <button className="btn-gold" data-testid="send-btn" onClick={() => send(input)} disabled={!input.trim() || busy} style={{ padding: "12px 16px" }}>
            <Send size={18} />
          </button>
        </div>
        {/* ⚖ Persistent UPL footer — required to evidence "general legal information, not advice"
            on every Lex chat surface. Apple App Review checks for this on AI legal apps. */}
        <div data-testid="lex-upl-footer" style={{
          padding: "6px 16px 8px", textAlign: "center",
          fontSize: 10, color: "var(--text-muted)", lineHeight: 1.4, letterSpacing: "0.02em",
        }}>
          <ShieldCheck size={9} style={{ display: "inline", marginRight: 4, opacity: 0.6 }} />
          AI-generated legal <strong style={{ color: "var(--gold-soft)" }}>information</strong>, not legal advice. Always verify with a regulated solicitor before acting.
        </div>
        {smartCat && (
          <div data-testid="smart-cat-banner" style={{ margin: "10px 16px 0", padding: 10, background: "rgba(247,201,72,0.12)", border: "1px solid var(--gold-deep)", borderRadius: 10, display: "flex", alignItems: "center", gap: 10 }}>
            <Scale size={16} style={{ color: "var(--gold)", flexShrink: 0 }} />
            <div style={{ flex: 1, fontSize: 12, color: "var(--text)" }}>
              {t(lang, "smartCatBanner").replace("{category}", smartCat.category)}
            </div>
            <button data-testid="smart-cat-switch" onClick={() => { onSwitchCategory && onSwitchCategory(smartCat.mapped); setSmartCat(null); }}
                    style={{ fontSize: 11, padding: "5px 10px", background: "var(--gold)", color: "#1a1300", border: "none", borderRadius: 6, fontWeight: 700, cursor: "pointer" }}>
              {t(lang, "smartCatSwitch")}
            </button>
            <button data-testid="smart-cat-dismiss" onClick={() => setSmartCat(null)}
                    style={{ fontSize: 10, padding: "5px 8px", background: "transparent", color: "var(--text-dim)", border: "none", cursor: "pointer" }}>
              <X size={12} />
            </button>
          </div>
        )}
        <audio ref={audioRef} style={{ display: "none" }} />
      </div>
    </div>
  );
}

// ---------- Emergency Mode ("I've Been Arrested") ----------
function EmergencyModal({ lang, country, user, onClose }) {
  const [rights, setRights] = useState("");
  const [busy, setBusy] = useState(true);
  const [note, setNote] = useState("");
  const [coords, setCoords] = useState(null);
  const [reading, setReading] = useState(false);
  const [profile, setProfile] = useState(null);          // { contacts, lawyer_standby_enabled, ... }
  const [sosBusy, setSosBusy] = useState(false);
  const [sosResult, setSosResult] = useState(null);      // {notified, standby_pinged}
  const [embassy, setEmbassy] = useState(null);
  const [nearbyLawyers, setNearbyLawyers] = useState([]);
  const [lawyersBusy, setLawyersBusy] = useState(false);
  const [trackSession, setTrackSession] = useState(null); // {sos_id, expires_at, window_minutes}
  const [trackRemain, setTrackRemain] = useState(0);      // seconds remaining
  const [batteryLowPrompt, setBatteryLowPrompt] = useState(null); // {level, charging}
  const batteryHandledRef = useRef(false);
  const trackPingHandleRef = useRef(null);
  const trackTickHandleRef = useRef(null);
  const audioRef = useRef(null);

  // Load emergency profile + embassy + lawyer-near-me in parallel as soon as we know GPS
  useEffect(() => {
    api.get("/emergency/contacts").then(r => setProfile(r.data)).catch(() => setProfile({ contacts: [] }));
    if (country) api.get(`/embassy/lookup?country=${country}`).then(r => setEmbassy(r.data)).catch(() => {});
  }, [country]);
  useEffect(() => {
    if (!coords) return;
    setLawyersBusy(true);
    api.get(`/lawfirms?latitude=${coords.latitude}&longitude=${coords.longitude}&max_km=50`)
      .then(r => setNearbyLawyers((r.data || []).slice(0, 5)))
      .catch(() => setNearbyLawyers([]))
      .finally(() => setLawyersBusy(false));
  }, [coords]);

  const fetchRights = useCallback(async (n) => {
    setBusy(true);
    try {
      const { data } = await api.post("/emergency/rights", { language: lang, country, note: n || undefined,
        location: coords ? `${coords.latitude.toFixed(4)},${coords.longitude.toFixed(4)}` : undefined });
      setRights(data.rights_script);
    } catch (e) { setRights(e?.response?.data?.detail || "Could not load rights. Stay silent. Ask for a lawyer."); }
    finally { setBusy(false); }
  }, [lang, country, coords]);

  // ⚠ THE BIG BUTTON. Records the SOS server-side (for audit + Lawyer Standby firm pings),
  // then opens the native SMS composer with ALL contacts pre-loaded so the user only
  // taps Send. SMS goes from the user's own number → family instantly recognises them.
  // Email contacts (if any) get a parallel mailto:.
  const buildSosBody = (coordsOverride, sosId) => {
    const c = coordsOverride || coords;
    const parts = [
      `🚨 EMERGENCY: ${user?.full_name || user?.email || "I"} need help.`,
      profile?.sos_message?.trim() || note?.trim() || "I've been stopped or detained.",
    ];
    if (c) {
      parts.push(`📍 My location: https://maps.google.com/?q=${c.latitude},${c.longitude}`);
      if (c.accuracy) parts.push(`(±${Math.round(c.accuracy)}m)`);
    } else {
      parts.push("📍 Location not available (GPS off or denied).");
    }
    // Live tracking link — family can follow movement in real-time for the configured window
    if (sosId) {
      const origin = (process.env.REACT_APP_BACKEND_URL || window.location.origin).replace(/\/$/, "");
      parts.push(`🔴 Live location (auto-updates): ${origin}/track.html?sid=${sosId}`);
    }
    if (country) parts.push(`Country: ${country}`);
    parts.push("(Sent via AI Advocate.)");
    return parts.join(" ");
  };

  // Fetch fresh GPS just-in-time before composing the SOS. This is the safety net:
  // even if the initial mount-time fetch failed/timed-out, we get one more shot
  // right at the moment the user needs it. Tries hi-accuracy first, low-accuracy fallback.
  const fetchFreshCoords = () => new Promise((resolve) => {
    if (!navigator.geolocation) { resolve(null); return; }
    const fallback = setTimeout(() => {
      navigator.geolocation.getCurrentPosition(
        (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy: p.coords.accuracy }),
        () => resolve(null),
        { timeout: 5000, enableHighAccuracy: false, maximumAge: 300000 },
      );
    }, 4500); // if hi-accuracy hasn't responded in 4.5s, try low-accuracy
    navigator.geolocation.getCurrentPosition(
      (p) => { clearTimeout(fallback); resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy: p.coords.accuracy }); },
      () => { /* let fallback run */ },
      { timeout: 6000, enableHighAccuracy: true, maximumAge: 60000 },
    );
  });

  const openNativeSms = (phones, body) => {
    if (!phones.length) return;
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    const sep = isIOS ? "&" : "?";
    const list = phones.map(p => p.replace(/\s/g, "")).join(",");
    window.location.href = `sms:${list}${sep}body=${encodeURIComponent(body)}`;
  };

  const openNativeEmail = (emails, body) => {
    if (!emails.length) return;
    const subject = encodeURIComponent("🚨 EMERGENCY — please help");
    const to = emails.join(",");
    window.location.href = `mailto:${to}?subject=${subject}&body=${encodeURIComponent(body)}`;
  };

  const fireSilentSOS = async () => {
    if (sosBusy) return;
    setSosBusy(true);
    try {
      // 0) Get the freshest possible location BEFORE composing the SMS. Use the existing
      // coords if we have them (instant) and kick off a fresh fetch in parallel — whichever
      // resolves first wins. This makes "location included" the rule, not the exception.
      let liveCoords = coords;
      if (!liveCoords) {
        liveCoords = await fetchFreshCoords();
        if (liveCoords) setCoords(liveCoords);
      }

      // 1) Record server-side (audit log + Lawyer Standby firm pings if Pro enabled)
      const { data } = await api.post("/emergency/silent-sos", {
        silent: true,
        latitude: liveCoords?.latitude, longitude: liveCoords?.longitude,
        country, note: note || profile?.sos_message || "",
        source: "phone",
      });
      setSosResult(data);

      // 2) Open the user's native SMS composer with all SOS-included contacts pre-filled.
      const sosContacts = (profile?.contacts || []).filter(c => c.include_in_sos);
      const phones = sosContacts.map(c => c.phone).filter(Boolean);
      const emails = sosContacts.map(c => c.email).filter(Boolean);
      const body = buildSosBody(liveCoords, data.sos_id);

      if (phones.length) {
        setTimeout(() => openNativeSms(phones, body), 250);
      }
      if (emails.length && !phones.length) {
        setTimeout(() => openNativeEmail(emails, body), 250);
      }
      window.__aaLastSos = { phones, emails, body };

      // 3) Start the live-location ping loop. Every 2 min, send current GPS to the server
      // for the configured window. Family's track.html page auto-refreshes from the same data.
      if (data.track_session?.sos_id) {
        startLiveTracking(data.track_session);
      }
    } catch (e) {
      setSosResult({ error: e?.response?.data?.detail || "Could not send SOS." });
    } finally {
      setSosBusy(false);
    }
  };

  const startLiveTracking = (session) => {
    setTrackSession(session);
    batteryHandledRef.current = false;
    // Tick a 1-second countdown for the banner
    const expiresAt = new Date(session.expires_at).getTime();
    const tick = () => {
      const r = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
      setTrackRemain(r);
      if (r <= 0) stopLiveTracking(true);
    };
    tick();
    if (trackTickHandleRef.current) clearInterval(trackTickHandleRef.current);
    trackTickHandleRef.current = setInterval(tick, 1000);
    // Ping immediately, then every 2 minutes
    const pingNow = async () => {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(async (pos) => {
        try {
          await api.post("/emergency/track/ping", {
            sos_id: session.sos_id,
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy: pos.coords.accuracy,
            source: "phone",
          });
        } catch {}
      }, () => {}, { timeout: 8000, enableHighAccuracy: true, maximumAge: 60000 });
    };
    pingNow();
    if (trackPingHandleRef.current) clearInterval(trackPingHandleRef.current);
    trackPingHandleRef.current = setInterval(pingNow, 120000); // every 2 minutes

    // 🔋 Battery monitor — if phone drops below 15% AND is discharging, prompt to extend
    // the window to max so family doesn't lose visibility right when the phone dies.
    // Only Android Chrome currently exposes the Battery API; on iOS Safari this is a no-op
    // (we still show a manual "Extend to max" button on the banner as a universal fallback).
    if (navigator.getBattery) {
      navigator.getBattery().then((battery) => {
        const check = () => {
          if (batteryHandledRef.current) return;
          if (!battery.charging && battery.level < 0.15) {
            batteryHandledRef.current = true;
            setBatteryLowPrompt({ level: battery.level, charging: battery.charging });
          }
        };
        check();
        battery.addEventListener("levelchange", check);
        battery.addEventListener("chargingchange", check);
      }).catch(() => {});
    }
  };

  // Extend the active track session to the user's tier-maximum (24h Pro, 2h Free).
  // Triggered by the battery-low banner or the manual "Extend" button on the SOS banner.
  const extendTrackToMax = async () => {
    if (!trackSession?.sos_id) return;
    try {
      const { data } = await api.post(`/emergency/track/${trackSession.sos_id}/extend`);
      if (data.already_at_max) {
        alert("Your SOS is already at the maximum tracking window.");
      } else if (data.expires_at) {
        // Update local countdown
        setTrackSession(s => ({ ...s, expires_at: data.expires_at, window_minutes: data.max_window_minutes }));
        const expiresAt = new Date(data.expires_at).getTime();
        if (trackTickHandleRef.current) clearInterval(trackTickHandleRef.current);
        trackTickHandleRef.current = setInterval(() => {
          const r = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
          setTrackRemain(r);
          if (r <= 0) stopLiveTracking(true);
        }, 1000);
      }
      setBatteryLowPrompt(null);
    } catch (e) {
      alert(e?.response?.data?.detail || "Could not extend.");
      setBatteryLowPrompt(null);
    }
  };

  const stopLiveTracking = async (auto = false) => {
    if (trackPingHandleRef.current) { clearInterval(trackPingHandleRef.current); trackPingHandleRef.current = null; }
    if (trackTickHandleRef.current) { clearInterval(trackTickHandleRef.current); trackTickHandleRef.current = null; }
    if (trackSession?.sos_id && !auto) {
      try { await api.post(`/emergency/track/${trackSession.sos_id}/stop`); } catch {}
    }
    setTrackSession(null);
    setTrackRemain(0);
  };

  // Cleanup ping loops when modal unmounts (does NOT stop server-side track — it keeps
  // pinging from background until window expires, which is what families need)
  useEffect(() => () => {
    if (trackPingHandleRef.current) clearInterval(trackPingHandleRef.current);
    if (trackTickHandleRef.current) clearInterval(trackTickHandleRef.current);
  }, []);

  const fmtRemain = (sec) => {
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  // Manual location prompt — fires when the user taps the "Enable location" pill
  const requestLocationNow = async () => {
    const c = await fetchFreshCoords();
    if (c) setCoords(c);
    else alert("Location permission denied. Open your device settings to enable GPS for AI Advocate, then try again.");
  };

  const callEmbassy = () => {
    const phone = embassy?.found ? embassy.embassy?.phone : embassy?.fallback?.phone;
    if (phone) window.location.href = `tel:${phone.replace(/\s/g, "")}`;
  };

  const readAloud = async () => {
    if (reading) {
      try { audioRef.current?.pause(); } catch {}
      setReading(false);
      return;
    }
    if (!rights) return;
    try {
      setReading(true);
      const r = await api.post("/voice/tts", { text: rights, language: lang }, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = new Audio(url);
      audioRef.current = a;
      a.onended = () => { setReading(false); URL.revokeObjectURL(url); };
      a.onerror = () => { setReading(false); };
      await a.play();
    } catch (e) {
      setReading(false);
    }
  };

  useEffect(() => {
    return () => { try { audioRef.current?.pause(); } catch {} };
  }, []);

  useEffect(() => {
    // Aggressive geo-fetch on mount: hi-accuracy first, fall back to low-accuracy after 4s.
    // This makes GPS-included-in-SOS the norm rather than the exception.
    if (navigator.geolocation) {
      let lowAccTimer = setTimeout(() => {
        navigator.geolocation.getCurrentPosition(
          (pos) => setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy }),
          () => {},
          { timeout: 6000, enableHighAccuracy: false, maximumAge: 600000 },
        );
      }, 4000);
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          clearTimeout(lowAccTimer);
          setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy });
        },
        () => { /* let the low-acc fallback try */ },
        { timeout: 5000, enableHighAccuracy: true, maximumAge: 60000 },
      );
    }
    fetchRights("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="modal-bg" data-testid="emergency-modal" style={{ background: "rgba(60,0,0,0.85)" }}>
      <div className="modal-card" style={{ padding: 18, border: "2px solid #dc2626", maxHeight: "94vh", overflowY: "auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 10 }}>
          <h2 style={{ fontSize: 20, color: "#fca5a5", fontFamily: "Cinzel, serif", letterSpacing: "0.04em" }}>{t(lang, "emergencyTitle")}</h2>
          <button onClick={onClose} data-testid="emergency-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}>
            <X size={24} />
          </button>
        </div>

        {/* 🚨 LIFE-SAFETY DISCLAIMER — App Store + UK coroner risk. Must be visually
            prominent so it's impossible to miss. Tappable to dial 999 immediately. */}
        <a href="tel:999" data-testid="emergency-999-banner"
          style={{
            display: "flex", alignItems: "center", gap: 10,
            background: "rgba(220,38,38,0.18)", border: "2px solid #dc2626",
            borderRadius: 12, padding: "10px 12px", marginBottom: 10,
            color: "#fca5a5", textDecoration: "none", fontSize: 12.5, lineHeight: 1.4,
          }}>
          <AlertTriangle size={18} style={{ color: "#fca5a5", flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <strong style={{ color: "#fee2e2" }}>In immediate danger? Call emergency services first.</strong><br/>
            <span style={{ opacity: 0.85 }}>UK 999 · EU 112 · US/CA 911. AI Advocate is a supplementary tool, not a replacement for police, fire, ambulance or coastguard.</span>
          </div>
          <Phone size={16} style={{ color: "#fee2e2", flexShrink: 0 }} />
        </a>

        {/* GPS status pill — gives the user clear, up-front confidence that their
            location IS in the SOS text. If permission denied / not yet resolved,
            shows a tappable "Enable location" button. */}
        <button data-testid="sos-gps-status" onClick={coords ? undefined : requestLocationNow}
          disabled={!!coords}
          style={{
            width: "100%", marginBottom: 8, padding: "8px 12px", borderRadius: 10,
            background: coords ? "rgba(34,197,94,0.10)" : "rgba(247,201,72,0.08)",
            border: `1px solid ${coords ? "#22c55e" : "var(--gold)"}`,
            color: coords ? "#86efac" : "var(--gold)",
            cursor: coords ? "default" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
            fontSize: 11.5, fontWeight: 600,
          }}>
          {coords
            ? `📍 Location ON — will be included in SOS (±${Math.round(coords.accuracy || 0)}m)`
            : "📍 Tap to enable location (recommended for SOS)"}
        </button>

        {/* 🚨 THE BIG SOS BUTTON — fires SOS to all stored contacts + Lawyer Standby */}
        <button data-testid="emergency-sos-fire" onClick={fireSilentSOS} disabled={sosBusy}
          style={{
            width: "100%", padding: "14px 16px", marginBottom: 8,
            background: sosResult ? "rgba(34,197,94,0.15)" : "linear-gradient(135deg,#dc2626,#7f1d1d)",
            border: sosResult ? "1px solid #22c55e" : "1px solid #fca5a5",
            color: sosResult ? "#86efac" : "#fff",
            borderRadius: 12, fontWeight: 800, fontSize: 14, letterSpacing: "0.04em",
            cursor: sosBusy ? "wait" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          }}>
          {sosBusy ? <span className="spinner" /> : sosResult ? <Check size={18} /> : <AlertTriangle size={18} />}
          {sosBusy ? "Recording SOS…"
            : sosResult?.error ? sosResult.error
            : sosResult ? `✓ SOS recorded — your SMS app opened with ${sosResult.notified} contact(s) pre-loaded. Tap Send.`
            : "🚨 SEND SOS TO MY CONTACTS"}
        </button>
        {/* Re-open native SMS / email composer if user accidentally cancelled the OS popup */}
        {sosResult && !sosResult.error && (
          <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <button data-testid="sos-reopen-sms" onClick={() => {
              const s = window.__aaLastSos; if (s?.phones?.length) openNativeSms(s.phones, s.body);
            }} style={{ flex: 1, padding: "8px 10px", background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 10, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
              📱 Re-open SMS
            </button>
            <button data-testid="sos-email-family" onClick={() => {
              const s = window.__aaLastSos; if (s?.emails?.length) openNativeEmail(s.emails, s.body);
              else alert("No email addresses on your SOS contacts. Add one in Settings → Emergency Contacts.");
            }} style={{ flex: 1, padding: "8px 10px", background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 10, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
              ✉ Email family
            </button>
          </div>
        )}

        {/* 📍 Live tracking active banner — pulsing red dot, countdown, STOP button. */}
        {trackSession && trackRemain > 0 && (
          <div data-testid="sos-live-tracking-banner" style={{
            background: "linear-gradient(135deg, rgba(220,38,38,0.18), rgba(34,211,238,0.12))",
            border: "1px solid #67e8f9", borderRadius: 12, padding: 12, marginBottom: 12,
            display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
          }}>
            <span style={{
              width: 10, height: 10, borderRadius: "50%", background: "#ef4444",
              animation: "lex-pulse 1.2s ease-in-out infinite", flexShrink: 0,
            }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#67e8f9" }}>📍 Live location active</div>
              <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Sharing your position with family. Auto-stops in <strong style={{ color: "#fff" }}>{fmtRemain(trackRemain)}</strong>.</div>
            </div>
            <button data-testid="sos-extend-tracking" onClick={extendTrackToMax}
              title="Extend the tracking window to your tier maximum (24h Pro / 2h Free)"
              style={{ background: "transparent", border: "1px solid var(--gold)", color: "var(--gold)", borderRadius: 8, padding: "5px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
              ⏱ EXTEND
            </button>
            <button data-testid="sos-stop-tracking" onClick={() => stopLiveTracking(false)}
              style={{ background: "transparent", border: "1px solid #fca5a5", color: "#fca5a5", borderRadius: 8, padding: "5px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
              STOP
            </button>
          </div>
        )}

        {/* 🔋 Battery-low extend prompt — auto-fires when phone hits <15% while tracking is active. */}
        {batteryLowPrompt && trackSession && (
          <div data-testid="sos-battery-prompt" style={{
            background: "linear-gradient(135deg, rgba(220,38,38,0.25), rgba(247,201,72,0.15))",
            border: "2px solid var(--gold)", borderRadius: 12, padding: 14, marginBottom: 12,
            boxShadow: "0 0 20px rgba(247,201,72,0.4)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 22 }}>🔋</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 800, color: "var(--gold)" }}>BATTERY LOW · {Math.round(batteryLowPrompt.level * 100)}%</div>
                <div style={{ fontSize: 11, color: "var(--text-dim)" }}>Your phone is about to die — extend SOS to max so family doesn't lose you.</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button data-testid="sos-battery-extend" onClick={extendTrackToMax} className="btn-gold" style={{ flex: 2, fontSize: 13, fontWeight: 800 }}>
                ⏱ Extend to maximum
              </button>
              <button data-testid="sos-battery-dismiss" onClick={() => setBatteryLowPrompt(null)}
                style={{ flex: 1, background: "transparent", border: "1px solid var(--line)", color: "var(--text-muted)", borderRadius: 10, fontSize: 12, cursor: "pointer" }}>
                Dismiss
              </button>
            </div>
          </div>
        )}
        {(!profile?.contacts || profile.contacts.length === 0) && !sosResult && (
          <div style={{ background: "rgba(247,201,72,0.08)", border: "1px solid var(--gold-deep)", borderRadius: 8, padding: 8, marginBottom: 12, fontSize: 11.5, color: "var(--gold)" }}>
            ⚠ No emergency contacts saved yet. Go to Settings → Emergency Contacts to add family + your lawyer for instant SOS.
          </div>
        )}

        {/* Embassy quick-dial — only abroad (country differs from user's home country may not be set; we show it if found) */}
        {embassy && (
          <button data-testid="emergency-embassy-call" onClick={callEmbassy}
            style={{ width: "100%", padding: "10px 14px", marginBottom: 10, background: "transparent",
                     border: "1px solid #67e8f9", color: "#67e8f9", borderRadius: 12, fontWeight: 700, fontSize: 13, cursor: "pointer",
                     display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            🏛 Call my embassy — {embassy.found ? embassy.embassy.name : embassy.fallback.name}
          </button>
        )}

        {/* Nearest lawyer — only shows when GPS available and at least one firm in 50km */}
        {(nearbyLawyers.length > 0 || lawyersBusy) && (
          <div data-testid="emergency-nearby-lawyers" style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 10, padding: 10, marginBottom: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--gold)", marginBottom: 6 }}>📍 NEAREST LAWYERS TO YOU</div>
            {lawyersBusy && <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Searching…</div>}
            {nearbyLawyers.slice(0, 3).map(f => (
              <div key={f.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 0", borderTop: "1px solid var(--line)" }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, color: "var(--text)", fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.name}</div>
                  <div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>{f.city} · {f.distance_km != null ? `${f.distance_km}km` : "—"}</div>
                </div>
                {f.phone && (
                  <a href={`tel:${f.phone.replace(/\s/g, "")}`} data-testid={`emergency-call-firm-${f.id}`}
                    style={{ background: "var(--gold)", color: "#1a1300", padding: "5px 10px", borderRadius: 8, fontSize: 11, fontWeight: 700, textDecoration: "none" }}>
                    📞 Call
                  </a>
                )}
              </div>
            ))}
          </div>
        )}

        <div style={{ fontSize: 12, color: "#fca5a5", marginBottom: 8 }}>{t(lang, "emergencyStayCalm", { country })}</div>
        <div data-testid="rights-script" style={{ overflowY: "auto", maxHeight: "40vh", padding: 14, background: "#0a0000",
                     borderRadius: 12, border: "1px solid #7f1d1d", fontSize: 14, color: "var(--text)",
                     lineHeight: 1.65, whiteSpace: "pre-wrap" }}>
          {busy ? <span className="spinner" /> : rights}
        </div>
        <button data-testid="emergency-read-aloud" onClick={readAloud} disabled={busy || !rights}
          style={{ width: "100%", marginTop: 10, padding: "10px 14px",
                   background: reading ? "var(--gold)" : "transparent",
                   color: reading ? "#1a1300" : "var(--gold)",
                   border: "1px solid var(--gold-deep)", borderRadius: 12, fontWeight: 600,
                   cursor: "pointer", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
          🔊 {reading ? t(lang, "emergencyStopReading") : t(lang, "emergencyReadAloud")}
        </button>
        <textarea className="input" data-testid="emergency-note" rows={2} placeholder={t(lang, "emergencyNotePlaceholder")}
          value={note} onChange={(e) => setNote(e.target.value)} style={{ marginTop: 10 }} />
        <div className="flex gap-2" style={{ marginTop: 10 }}>
          <button className="btn-gold" data-testid="rights-refresh" disabled={busy} onClick={() => fetchRights(note)} style={{ flex: 1 }}>
            {t(lang, "emergencyRegenWithNote")}
          </button>
          <button className="btn-ghost" onClick={onClose} style={{ flex: 1 }}>{t(lang, "emergencyClose")}</button>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 10, textAlign: "center" }}>
          {t(lang, "emergencyDisclaimer")}
        </div>
      </div>
    </div>
  );
}

// ---------- Practice + Live Legal Assist Modal (combined) ----------
const PRACTICE_ROLES = [
  { v: "police_uk", label: "UK Police Interview" },
  { v: "police_us", label: "US Police Interrogation" },
  { v: "prosecutor", label: "Cross-Examination by Prosecutor" },
  { v: "tribunal", label: "Employment Tribunal" },
  { v: "immigration", label: "Immigration Interview" },
  { v: "judge", label: "Mitigation Before a Judge" },
  { v: "opposing_counsel", label: "Opposing Counsel (Civil)" },
  { v: "boss_disciplinary", label: "HR Disciplinary Hearing" },
];
const LIVE_SCENARIOS = [
  { v: "police_interview", label: "Police interview (with rep present)" },
  { v: "tribunal", label: "Tribunal hearing (recording permitted)" },
  { v: "lawyer_call", label: "Call with my own lawyer" },
  { v: "mediation", label: "Mediation / Arbitration (consented)" },
  { v: "disciplinary", label: "Internal disciplinary / HR" },
  { v: "other", label: "Other permitted conversation" },
];

function CourtroomModal({ lang, country, onClose }) {
  const [tab, setTab] = useState("practice"); // practice | live
  // Practice state
  const [role, setRole] = useState("police_uk");
  const [facts, setFacts] = useState("");
  const [pMsgs, setPMsgs] = useState([]);
  const [pInput, setPInput] = useState("");
  const [pBusy, setPBusy] = useState(false);
  const [pSession, setPSession] = useState(null);
  const { recording, start, stop } = useRecorder();
  const pScroll = useRef(null);
  useEffect(() => { pScroll.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [pMsgs, pBusy]);

  const sendPractice = async (text) => {
    if (!text.trim()) return;
    setPMsgs(m => [...m, { role: "user", content: text }]); setPInput(""); setPBusy(true);
    try {
      const { data } = await api.post("/lex/practice", { session_id: pSession, role, message: text, language: lang, country, facts });
      setPSession(data.session_id);
      setPMsgs(m => [...m, { role: "lex", content: data.response }]);
    } catch (e) {
      setPMsgs(m => [...m, { role: "lex", content: e?.response?.data?.detail || "Error" }]);
    } finally { setPBusy(false); }
  };

  const onPracticeMic = async () => {
    if (recording) {
      const blob = await stop();
      if (!blob) return;
      setPBusy(true);
      const fd = new FormData(); fd.append("audio", blob, "rec.webm"); fd.append("language", lang.split("-")[0]);
      try {
        const { data } = await api.post("/voice/transcribe", fd);
        if (data.text) await sendPractice(data.text);
        else setPBusy(false);
      } catch { setPBusy(false); }
    } else { start(); }
  };

  // Live Assist state
  const [consentChecked, setConsentChecked] = useState(false); // tick box state
  const [consent, setConsent] = useState(false);               // gate passed (Accept clicked)
  const [scenario, setScenario] = useState("police_interview");
  const [liveActive, setLiveActive] = useState(false);
  const [lFacts, setLFacts] = useState("");
  const [advice, setAdvice] = useState([]); // {at, said, advice}
  const [reviewBusy, setReviewBusy] = useState(false);         // "Send to Lex for review" loading
  const [liveStatus, setLiveStatus] = useState("");            // "listening" | "transcribing" | "thinking" | ""
  const lStreamRef = useRef(null);
  const lRecRef = useRef(null);
  const lChunkLoopRef = useRef(null);                          // setInterval handle for chunk rotation
  const lSessionRef = useRef(null);
  const lStartedAtRef = useRef(null);                          // ISO timestamp of session start
  const lLiveActiveRef = useRef(false);                        // mirrors liveActive for use in async callbacks

  // Send a finalised audio chunk through Whisper → Lex live-assist, append to advice list.
  // Runs in the background so the next chunk can record while this one is being processed.
  const processChunk = async (blob) => {
    if (!blob || blob.size < 2000) return; // skip tiny / silent chunks
    try {
      setLiveStatus("transcribing");
      const fd = new FormData();
      fd.append("audio", blob, `chunk-${Date.now()}.webm`);
      fd.append("language", (lang || "en-GB").split("-")[0]);
      const tx = await api.post("/voice/transcribe", fd);
      const said = (tx?.data?.text || "").trim();
      if (!said || said.length < 4) {
        setLiveStatus(lLiveActiveRef.current ? "listening" : "");
        return;
      }
      setLiveStatus("thinking");
      const { data } = await api.post("/lex/live-assist", {
        session_id: lSessionRef.current, scenario,
        other_party_said: said, my_facts: lFacts, language: lang, country,
      });
      lSessionRef.current = data.session_id;
      setAdvice(a => [{ at: new Date().toLocaleTimeString(), said, advice: data.response }, ...a].slice(0, 50));
      // Persist timestamped notes server-side
      api.post("/live/notes", { session_id: data.session_id, speaker: "other_party", text: said }).catch(() => {});
      api.post("/live/notes", { session_id: data.session_id, speaker: "lex", text: data.response, note_kind: "advice" }).catch(() => {});
    } catch (e) {
      // never crash the recording loop
      console.warn("live-assist chunk failed", e?.response?.data || e?.message);
    } finally {
      setLiveStatus(lLiveActiveRef.current ? "listening" : "");
    }
  };

  // Rotate the MediaRecorder every 8s: stop -> capture blob -> process -> start a new one.
  // This lets Whisper transcribe in near-real-time while the next slice is being recorded.
  const rotateRecorder = () => {
    const old = lRecRef.current;
    const stream = lStreamRef.current;
    if (!stream || !lLiveActiveRef.current) return;
    try {
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4"
        : MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      const fresh = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      const chunks = [];
      fresh.ondataavailable = (ev) => { if (ev.data && ev.data.size > 0) chunks.push(ev.data); };
      fresh.onstop = () => {
        const blob = new Blob(chunks, { type: fresh.mimeType || "audio/webm" });
        processChunk(blob); // fire-and-forget — runs in background
      };
      fresh.start();
      lRecRef.current = fresh;
      // Stop the previous recorder (its onstop will process the blob)
      if (old && old.state !== "inactive") {
        try { old.stop(); } catch {}
      }
    } catch (e) {
      console.error("rotateRecorder failed", e);
    }
  };

  const startLive = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      alert("Microphone not supported in this browser. Use Chrome, Safari, or Edge.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      lStreamRef.current = stream;
      lStartedAtRef.current = new Date().toISOString();
      lLiveActiveRef.current = true;
      setLiveActive(true);
      setLiveStatus("listening");
      // First chunk
      rotateRecorder();
      // Rotate every 8 seconds → balance latency vs Whisper accuracy
      lChunkLoopRef.current = setInterval(() => rotateRecorder(), 8000);
    } catch (e) {
      alert("Microphone permission denied. Open Settings → Microphone access to grant it.");
    }
  };

  const stopLive = () => {
    lLiveActiveRef.current = false;
    setLiveActive(false);
    setLiveStatus("");
    if (lChunkLoopRef.current) { clearInterval(lChunkLoopRef.current); lChunkLoopRef.current = null; }
    try {
      if (lRecRef.current && lRecRef.current.state !== "inactive") {
        lRecRef.current.stop(); // last blob flushes through processChunk
      }
    } catch {}
    lRecRef.current = null;
    // Release the microphone
    if (lStreamRef.current) {
      try { lStreamRef.current.getTracks().forEach(t => t.stop()); } catch {}
      lStreamRef.current = null;
    }
  };

  useEffect(() => () => {
    // Cleanup on unmount
    lLiveActiveRef.current = false;
    if (lChunkLoopRef.current) clearInterval(lChunkLoopRef.current);
    try { lRecRef.current?.stop?.(); } catch {}
    try { lStreamRef.current?.getTracks?.().forEach(t => t.stop()); } catch {}
  }, []);

  // ============= Translation Mode state =============
  // Bidirectional live interpreter for travellers stopped abroad.
  const [tLanguages, setTLanguages] = useState([]);            // {code, name, native}[]
  const [tTheirLang, setTTheirLang] = useState("ar");          // language spoken by the other party
  const [tMyLang, setTMyLang]       = useState("en");          // user's language
  const [tContext, setTContext]     = useState("");            // e.g. "Iraqi checkpoint, traveller"
  const [tActive, setTActive]       = useState(false);         // listening for the OTHER party
  const [tStatus, setTStatus]       = useState("");            // "listening" | "transcribing" | "translating"
  const [tHistory, setTHistory]     = useState([]);            // {at, dir, original, translation, tip, suggested_reply}
  const [tConsent, setTConsent]     = useState(false);
  const [tConsentChecked, setTConsentChecked] = useState(false);
  const [tReplyBusy, setTReplyBusy] = useState(false);
  const tSessionRef = useRef(null);
  const tStreamRef = useRef(null);
  const tRecRef = useRef(null);
  const tChunkLoopRef = useRef(null);
  const tActiveRef = useRef(false);
  const tTheirLangRef = useRef("ar");
  const tMyLangRef = useRef("en");
  useEffect(() => { tTheirLangRef.current = tTheirLang; }, [tTheirLang]);
  useEffect(() => { tMyLangRef.current = tMyLang; }, [tMyLang]);

  // Load Whisper language list once
  useEffect(() => {
    api.get("/lex/translate/languages")
      .then(r => setTLanguages(r.data?.languages || []))
      .catch(() => setTLanguages([]));
  }, []);

  const playTTS = async (text, language) => {
    if (!text) return;
    try {
      const r = await api.post("/voice/tts", { text, language }, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch (e) { console.warn("TTS failed", e?.response?.data || e?.message); }
  };

  // Process one incoming chunk for Translation Mode
  const processTransChunk = async (blob) => {
    if (!blob || blob.size < 2000) return;
    try {
      setTStatus("transcribing");
      const fd = new FormData();
      fd.append("audio", blob, `chunk-${Date.now()}.webm`);
      fd.append("language", tTheirLangRef.current);
      const tx = await api.post("/voice/transcribe", fd);
      const heard = (tx?.data?.text || "").trim();
      if (!heard || heard.length < 3) { setTStatus(tActiveRef.current ? "listening" : ""); return; }
      setTStatus("translating");
      const { data } = await api.post("/lex/translate", {
        session_id: tSessionRef.current,
        text: heard,
        source_lang: tTheirLangRef.current,
        target_lang: tMyLangRef.current,
        direction: "incoming",
        context: tContext,
        country,
      });
      tSessionRef.current = data.session_id;
      const entry = {
        at: new Date().toLocaleTimeString(),
        dir: "incoming",
        original: heard,
        translation: data.translation || "",
        tip: data.tip || "",
        suggested_reply: data.suggested_reply || "",
      };
      setTHistory(h => [entry, ...h].slice(0, 50));
    } catch (e) {
      console.warn("trans chunk failed", e?.response?.data || e?.message);
    } finally {
      setTStatus(tActiveRef.current ? "listening" : "");
    }
  };

  const rotateTransRecorder = () => {
    const old = tRecRef.current;
    const stream = tStreamRef.current;
    if (!stream || !tActiveRef.current) return;
    try {
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4"
        : MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      const fresh = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      const chunks = [];
      fresh.ondataavailable = (ev) => { if (ev.data?.size > 0) chunks.push(ev.data); };
      fresh.onstop = () => {
        const blob = new Blob(chunks, { type: fresh.mimeType || "audio/webm" });
        processTransChunk(blob);
      };
      fresh.start();
      tRecRef.current = fresh;
      if (old && old.state !== "inactive") { try { old.stop(); } catch {} }
    } catch (e) { console.error("rotateTransRecorder failed", e); }
  };

  const startTranslation = async () => {
    if (!navigator.mediaDevices?.getUserMedia) { alert("Microphone not supported."); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      tStreamRef.current = stream;
      tActiveRef.current = true;
      setTActive(true); setTStatus("listening");
      rotateTransRecorder();
      tChunkLoopRef.current = setInterval(() => rotateTransRecorder(), 6000);
    } catch (e) {
      alert("Microphone permission denied. Go to Settings → Microphone access to grant it.");
    }
  };

  const stopTranslation = () => {
    tActiveRef.current = false;
    setTActive(false); setTStatus("");
    if (tChunkLoopRef.current) { clearInterval(tChunkLoopRef.current); tChunkLoopRef.current = null; }
    try { if (tRecRef.current?.state !== "inactive") tRecRef.current?.stop?.(); } catch {}
    tRecRef.current = null;
    if (tStreamRef.current) {
      try { tStreamRef.current.getTracks().forEach(t => t.stop()); } catch {}
      tStreamRef.current = null;
    }
  };

  // User wants to reply IN their language → translate to other-party language → speak it out loud.
  const speakMyReply = async (myText) => {
    if (!myText?.trim() || tReplyBusy) return;
    setTReplyBusy(true);
    try {
      const { data } = await api.post("/lex/translate", {
        session_id: tSessionRef.current,
        text: myText.trim(),
        source_lang: tMyLang,
        target_lang: tTheirLang,
        direction: "outgoing",
      });
      tSessionRef.current = data.session_id;
      const entry = {
        at: new Date().toLocaleTimeString(),
        dir: "outgoing",
        original: myText.trim(),
        translation: data.translation || "",
        tip: "", suggested_reply: "",
      };
      setTHistory(h => [entry, ...h].slice(0, 50));
      // Speak the translation aloud for the OTHER party
      await playTTS(data.translation, tTheirLang);
    } catch (e) {
      alert("Translation failed. Try again.");
    } finally {
      setTReplyBusy(false);
    }
  };

  useEffect(() => () => {
    tActiveRef.current = false;
    if (tChunkLoopRef.current) clearInterval(tChunkLoopRef.current);
    try { tRecRef.current?.stop?.(); } catch {}
    try { tStreamRef.current?.getTracks?.().forEach(t => t.stop()); } catch {}
  }, []);

  return (
    <div className="modal-bg" data-testid="courtroom-modal">
      <div className="modal-card" style={{ height: "92vh", padding: 0 }}>
        <div className="flex items-center justify-between" style={{ padding: 14, borderBottom: "1px solid var(--line)" }}>
          <h2 className="brand-font gold" style={{ fontSize: 18, letterSpacing: "0.04em" }}>{t(lang, "courtroomTrainer").toUpperCase()}</h2>
          <button onClick={onClose} data-testid="courtroom-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>
        <div style={{ display: "flex", padding: "10px 14px", gap: 6 }}>
          <button data-testid="tab-practice" onClick={() => setTab("practice")}
            style={{ flex: 1, padding: "8px 8px", borderRadius: 10, cursor: "pointer", fontSize: 12,
              background: tab === "practice" ? "var(--gold)" : "transparent",
              color: tab === "practice" ? "#1a1300" : "var(--gold)", border: "1px solid var(--gold-deep)", fontWeight: 600 }}>
            Practice
          </button>
          <button data-testid="tab-live" onClick={() => setTab("live")}
            style={{ flex: 1, padding: "8px 8px", borderRadius: 10, cursor: "pointer", fontSize: 12,
              background: tab === "live" ? "var(--gold)" : "transparent",
              color: tab === "live" ? "#1a1300" : "var(--gold)", border: "1px solid var(--gold-deep)", fontWeight: 600 }}>
            Live Assist
          </button>
          <button data-testid="tab-translate" onClick={() => setTab("translate")}
            style={{ flex: 1, padding: "8px 8px", borderRadius: 10, cursor: "pointer", fontSize: 12,
              background: tab === "translate" ? "var(--gold)" : "transparent",
              color: tab === "translate" ? "#1a1300" : "var(--gold)", border: "1px solid var(--gold-deep)", fontWeight: 600 }}>
            🌍 Translate
          </button>
        </div>

        {tab === "practice" ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "0 14px 14px", overflow: "hidden" }}>
            {pMsgs.length === 0 && (
              <>
                <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 6 }}>{t(lang, "practiceIntro")}</div>
                <select className="input" data-testid="practice-role" value={role} onChange={(e) => setRole(e.target.value)} style={{ marginBottom: 8 }}>
                  {PRACTICE_ROLES.map(r => <option key={r.v} value={r.v}>{r.label}</option>)}
                </select>
                <textarea className="input" data-testid="practice-facts" rows={3} value={facts} onChange={(e) => setFacts(e.target.value)} placeholder={t(lang, "practiceFactsPlaceholder")} />
              </>
            )}
            <div ref={pScroll} style={{ flex: 1, overflowY: "auto", marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              {pMsgs.map((m, i) => (
                <div key={i} className={m.role === "user" ? "bubble-user" : "bubble-lex"}
                     style={{ alignSelf: m.role === "user" ? "flex-end" : "flex-start", padding: "9px 12px", borderRadius: 14, maxWidth: "82%", whiteSpace: "pre-wrap", fontSize: 14 }}>
                  {m.content}
                </div>
              ))}
              {pBusy && <div className="bubble-lex" style={{ alignSelf: "flex-start", padding: "9px 12px", borderRadius: 14 }}><span className="spinner" /></div>}
            </div>
            <div className="flex items-center gap-2" style={{ marginTop: 10 }}>
              <button onClick={onPracticeMic} data-testid="practice-mic"
                style={{ background: "#000", border: `2px solid ${recording ? "var(--danger)" : "var(--gold)"}`, borderRadius: "50%", width: 44, height: 44, cursor: "pointer", padding: 0, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
                {recording ? <Square size={18} style={{ color: "var(--danger)" }} /> : <Mic size={18} style={{ color: "var(--gold)" }} />}
              </button>
              <input className="input" data-testid="practice-input" placeholder={pMsgs.length === 0 ? "Type your opening reply or tap mic…" : "Reply…"} value={pInput} onChange={(e) => setPInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendPractice(pInput)} style={{ flex: 1 }} />
              <button className="btn-gold" data-testid="practice-send" onClick={() => sendPractice(pInput || (pMsgs.length === 0 ? "Begin." : ""))} disabled={pBusy} style={{ padding: "10px 14px" }}>
                <Send size={16} />
              </button>
            </div>
          </div>
        ) : tab === "live" ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "0 14px 14px", overflow: "hidden" }}>
            {!consent ? (
              <div style={{ padding: 8, overflowY: "auto" }}>
                <div style={{ background: "#2a0a0a", border: "1px solid #7f1d1d", borderRadius: 12, padding: 14, marginBottom: 10 }}>
                  <div style={{ color: "#fca5a5", fontWeight: 600, marginBottom: 6 }}>⚠ Permitted use only</div>
                  <div style={{ fontSize: 12.5, color: "var(--text-dim)", lineHeight: 1.6 }}>
                    {t(lang, "liveAssistWarning")}
                    <br /><br />
                    {t(lang, "liveAssistAllowed")}
                    <ul style={{ marginLeft: 18, marginTop: 6 }}>
                      <li>{t(lang, "liveUse1")}</li>
                      <li>{t(lang, "liveUse2")}</li>
                      <li>{t(lang, "liveUse3")}</li>
                      <li>{t(lang, "liveUse4")}</li>
                      <li>{t(lang, "liveUse5")}</li>
                    </ul>
                  </div>
                </div>
                <a href="/terms.html" target="_blank" rel="noopener noreferrer"
                   data-testid="live-consent-terms-link"
                   style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--gold)", fontSize: 12.5, textDecoration: "underline", marginBottom: 12 }}>
                  <FileText size={14} /> Read full Terms & Conditions
                </a>
                <label className="flex items-start gap-2" style={{ cursor: "pointer" }}>
                  <input type="checkbox" data-testid="consent-checkbox" checked={consentChecked}
                    onChange={(e) => setConsentChecked(e.target.checked)}
                    style={{ width: 18, height: 18, accentColor: "var(--gold)", marginTop: 3 }} />
                  <span style={{ fontSize: 12.5, color: "var(--text-dim)" }}>I have read and understood the Terms above. I confirm I have lawful permission to record this conversation, that I am NOT in an active courtroom, and I accept full responsibility for the legality of this use in my jurisdiction.</span>
                </label>
                <button className="btn-gold w-full" data-testid="consent-continue"
                  disabled={!consentChecked}
                  onClick={() => setConsent(true)}
                  style={{
                    marginTop: 14,
                    opacity: consentChecked ? 1 : 0.4,
                    cursor: consentChecked ? "pointer" : "not-allowed",
                  }}>
                  {consentChecked ? "Accept & continue" : "Tick the box to continue"}
                </button>
              </div>
            ) : (
              <>
                {!liveActive && (
                  <>
                    <select className="input" data-testid="live-scenario" value={scenario} onChange={(e) => setScenario(e.target.value)} style={{ marginBottom: 8 }}>
                      {LIVE_SCENARIOS.map(s => <option key={s.v} value={s.v}>{s.label}</option>)}
                    </select>
                    <textarea className="input" data-testid="live-facts" rows={2} value={lFacts} onChange={(e) => setLFacts(e.target.value)} placeholder={t(lang, "liveFactsPlaceholder")} />
                  </>
                )}
                <button className="btn-gold w-full" data-testid={liveActive ? "live-stop" : "live-start"} onClick={liveActive ? stopLive : startLive}
                  style={{ marginTop: 10, background: liveActive ? "#dc2626" : undefined, color: liveActive ? "#fff" : undefined }}>
                  {liveActive ? "STOP listening" : "START listening"}
                </button>
                {liveActive && (
                  <div style={{
                    background: "rgba(247,201,72,0.08)",
                    border: "1px solid var(--gold-deep)",
                    borderRadius: 10, padding: "8px 12px", marginTop: 8,
                    display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                    fontSize: 12, color: "var(--gold)",
                  }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: "50%",
                      background: liveStatus === "listening" ? "#ef4444" : liveStatus === "thinking" ? "var(--gold)" : "#86efac",
                      animation: "lex-pulse 1.4s ease-in-out infinite",
                    }} />
                    {liveStatus === "transcribing" ? "📝 Transcribing what they said…"
                      : liveStatus === "thinking" ? "🧠 Lex is preparing your reply…"
                      : "🎙 Listening — speak naturally"}
                  </div>
                )}

                {/* Latest "SAY THIS" card — pinned at top so user reads it without looking away */}
                {liveActive && advice.length > 0 && (
                  <div data-testid="live-say-this" style={{
                    background: "linear-gradient(135deg, rgba(247,201,72,0.18), rgba(247,201,72,0.06))",
                    border: "2px solid var(--gold)",
                    borderRadius: 14, padding: 14, marginTop: 10,
                    boxShadow: "0 0 24px rgba(247,201,72,0.25)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6, gap: 8 }}>
                      <div style={{
                        fontSize: 10, fontWeight: 800, letterSpacing: "0.12em",
                        color: "var(--gold)",
                      }}>💬 SAY THIS — {advice[0].at}</div>
                      <WhisperButton text={advice[0].advice} language={lang} />
                    </div>
                    <div style={{
                      fontSize: 16, fontWeight: 600, color: "#fff", lineHeight: 1.45,
                    }}>{advice[0].advice}</div>
                    <div style={{
                      fontSize: 11, color: "var(--text-dim)", marginTop: 8, fontStyle: "italic",
                      borderTop: "1px solid var(--gold-deep)", paddingTop: 6,
                    }}>They said: "{advice[0].said}"</div>
                  </div>
                )}
                {!liveActive && lSessionRef.current && advice.length > 0 && (
                  <>
                    <div data-testid="live-saved-indicator" style={{
                      background: "rgba(34,197,94,0.1)", border: "1px solid #22c55e",
                      borderRadius: 10, padding: 10, marginTop: 8, fontSize: 12, color: "#86efac",
                      display: "flex", alignItems: "center", gap: 8,
                    }}>
                      <Check size={14} />
                      <span>Session saved · {advice.length} turn{advice.length === 1 ? "" : "s"} · started {lStartedAtRef.current ? new Date(lStartedAtRef.current).toLocaleString() : "just now"}</span>
                    </div>
                    <button data-testid="export-live-pdf" onClick={async () => {
                      try {
                        const r = await fetch(`${API}/live/notes/${lSessionRef.current}/export`, {
                          headers: { Authorization: `Bearer ${localStorage.getItem("aa_token")}` },
                        });
                        const blob = await r.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url; a.download = `ai-advocate-session-${lSessionRef.current.slice(0,8)}.pdf`;
                        document.body.appendChild(a); a.click(); a.remove();
                        URL.revokeObjectURL(url);
                      } catch (e) { alert("Export failed"); }
                    }} className="btn-ghost w-full" style={{ marginTop: 8, fontSize: 13 }}>
                      <Download size={14} style={{ display: "inline", marginRight: 6 }} />
                      Export timestamped notes (PDF)
                    </button>
                    <button data-testid="lex-review-session" disabled={reviewBusy} onClick={async () => {
                      // Build a structured summary of the live session and hand it to Lex chat
                      // for a full advisory — what was said, what was advised in the moment,
                      // and now what should the user do next (especially for police interviews
                      // or HR / disciplinary). Opens the normal Lex chat with this as the seed.
                      setReviewBusy(true);
                      try {
                        const lines = advice.slice().reverse().map((a, i) => (
                          `[${a.at}] Other party: "${a.said}"\n[${a.at}] Lex (in the moment): ${a.advice}`
                        )).join("\n\n");
                        const seed = (
                          `I've just finished a recorded ${scenario.replace(/_/g, " ")} session.\n\n` +
                          `My situation / facts:\n${lFacts || "(none provided)"}\n\n` +
                          `Transcript & in-the-moment advice (chronological):\n${lines}\n\n` +
                          `Please review the FULL session and tell me:\n` +
                          `1) What did I do well?\n` +
                          `2) What did I get wrong or should have answered differently?\n` +
                          `3) What are my next steps right now?\n` +
                          `4) Any red flags I should escalate (legal aid, formal complaint, solicitor)?\n` +
                          `Treat this as the most important review you'll do today.`
                        );
                        // Hand off to the main Lex chat — close this modal first.
                        window.dispatchEvent(new CustomEvent("aa:open-lex-with-seed", {
                          detail: { seed, category: "ask_lex", title: "Lex — Session Review" }
                        }));
                        onClose();
                      } catch (e) {
                        alert("Couldn't hand off to Lex. Please try again.");
                      } finally {
                        setReviewBusy(false);
                      }
                    }} className="btn-gold w-full" style={{ marginTop: 8, fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
                      {reviewBusy ? <span className="spinner" /> : <Sparkles size={14} />}
                      Ask Lex to review this session
                    </button>
                  </>
                )}
                <div style={{ flex: 1, overflowY: "auto", marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                  {advice.length === 0 && liveActive && <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 20, fontSize: 13 }}>{t(lang, "waitingForOtherSide")}</div>}
                  {/* During live mode the latest advice is shown in the SAY THIS pinned card above — skip it here to avoid duplication. */}
                  {(liveActive ? advice.slice(1) : advice).map((a, i) => (
                    <div key={i} style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 12, padding: 10 }}>
                      <div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>{a.at} — They said:</div>
                      <div style={{ fontSize: 12.5, color: "var(--text-dim)", fontStyle: "italic", marginBottom: 6 }}>"{a.said}"</div>
                      <div style={{ fontSize: 14, color: "var(--gold)", fontWeight: 600 }}>{a.advice}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        ) : (
          /* ============= TRANSLATION MODE TAB ============= */
          <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "0 14px 14px", overflow: "hidden" }}>
            {!tConsent ? (
              <div style={{ padding: 8, overflowY: "auto" }}>
                <div style={{ background: "#0a1f2a", border: "1px solid #155e75", borderRadius: 12, padding: 14, marginBottom: 10 }}>
                  <div style={{ color: "#67e8f9", fontWeight: 600, marginBottom: 6 }}>🌍 Live Translation Mode</div>
                  <div style={{ fontSize: 12.5, color: "var(--text-dim)", lineHeight: 1.6 }}>
                    For travellers, expats, and migrants in a foreign-language conversation (checkpoint, hospital, immigration, hotel, taxi). Lex listens to the other party, translates to YOUR language, and suggests a safe reply. You can speak back and Lex will translate it into their language and read it aloud.
                    <br /><br />
                    <strong style={{ color: "#fca5a5" }}>⚠ Not for use in courtrooms or sworn legal proceedings.</strong> AI translation is best-effort — for binding legal proceedings, you must request a certified court interpreter.
                  </div>
                </div>
                <a href="/terms.html" target="_blank" rel="noopener noreferrer"
                   data-testid="trans-consent-terms-link"
                   style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--gold)", fontSize: 12.5, textDecoration: "underline", marginBottom: 12 }}>
                  <FileText size={14} /> Read full Terms & Conditions
                </a>
                <label className="flex items-start gap-2" style={{ cursor: "pointer" }}>
                  <input type="checkbox" data-testid="trans-consent-checkbox" checked={tConsentChecked}
                    onChange={(e) => setTConsentChecked(e.target.checked)}
                    style={{ width: 18, height: 18, accentColor: "var(--gold)", marginTop: 3 }} />
                  <span style={{ fontSize: 12.5, color: "var(--text-dim)" }}>I understand AI translation is best-effort, not a substitute for a certified interpreter in legal proceedings, and that I am responsible for the lawful use of recording in the jurisdiction I'm in.</span>
                </label>
                <button className="btn-gold w-full" data-testid="trans-consent-continue"
                  disabled={!tConsentChecked} onClick={() => setTConsent(true)}
                  style={{ marginTop: 14, opacity: tConsentChecked ? 1 : 0.4, cursor: tConsentChecked ? "pointer" : "not-allowed" }}>
                  {tConsentChecked ? "Accept & continue" : "Tick the box to continue"}
                </button>
              </div>
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 10 }}>
                  <div>
                    <label style={{ fontSize: 10.5, color: "var(--text-muted)", letterSpacing: "0.06em" }}>THEIR LANGUAGE</label>
                    <select className="input" data-testid="trans-their-lang" value={tTheirLang}
                      onChange={(e) => setTTheirLang(e.target.value)} style={{ width: "100%" }} disabled={tActive}>
                      {tLanguages.map(l => <option key={l.code} value={l.code}>{l.native} — {l.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: 10.5, color: "var(--text-muted)", letterSpacing: "0.06em" }}>MY LANGUAGE</label>
                    <select className="input" data-testid="trans-my-lang" value={tMyLang}
                      onChange={(e) => setTMyLang(e.target.value)} style={{ width: "100%" }} disabled={tActive}>
                      {tLanguages.map(l => <option key={l.code} value={l.code}>{l.native} — {l.name}</option>)}
                    </select>
                  </div>
                </div>
                <input className="input" data-testid="trans-context" placeholder="Context (optional, e.g. 'Iraqi checkpoint, tourist')"
                  value={tContext} onChange={(e) => setTContext(e.target.value)} style={{ marginBottom: 10 }} disabled={tActive} />
                <div className="flex items-center gap-2" style={{ marginBottom: 6 }}>
                  {!tActive ? (
                    <button className="btn-gold flex-1" data-testid="trans-start" onClick={startTranslation}
                      style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                      <Mic size={16} /> Start listening
                    </button>
                  ) : (
                    <button className="btn-ghost flex-1" data-testid="trans-stop" onClick={stopTranslation}
                      style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, borderColor: "var(--danger)", color: "var(--danger)" }}>
                      <Square size={16} /> Stop
                    </button>
                  )}
                </div>

                {tActive && (
                  <div style={{
                    background: "rgba(34,211,238,0.08)", border: "1px solid #155e75",
                    borderRadius: 10, padding: "8px 12px", marginTop: 4,
                    display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                    fontSize: 12, color: "#67e8f9",
                  }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: "50%",
                      background: tStatus === "listening" ? "#ef4444" : tStatus === "translating" ? "#67e8f9" : "#86efac",
                      animation: "lex-pulse 1.4s ease-in-out infinite",
                    }} />
                    {tStatus === "transcribing" ? "📝 Transcribing what they said…"
                      : tStatus === "translating" ? "🌍 Translating…"
                      : `🎙 Listening in ${tLanguages.find(l => l.code === tTheirLang)?.native || tTheirLang}`}
                  </div>
                )}

                {tHistory.length > 0 && (
                  <div data-testid="trans-latest" style={{
                    background: tHistory[0].dir === "incoming"
                      ? "linear-gradient(135deg, rgba(34,211,238,0.16), rgba(34,211,238,0.04))"
                      : "linear-gradient(135deg, rgba(247,201,72,0.16), rgba(247,201,72,0.04))",
                    border: `2px solid ${tHistory[0].dir === "incoming" ? "#22d3ee" : "var(--gold)"}`,
                    borderRadius: 14, padding: 14, marginTop: 10,
                    boxShadow: tHistory[0].dir === "incoming"
                      ? "0 0 24px rgba(34,211,238,0.25)"
                      : "0 0 24px rgba(247,201,72,0.25)",
                  }}>
                    <div style={{
                      fontSize: 10, fontWeight: 800, letterSpacing: "0.12em",
                      color: tHistory[0].dir === "incoming" ? "#67e8f9" : "var(--gold)",
                      marginBottom: 6,
                    }}>
                      {tHistory[0].dir === "incoming" ? `💬 THEY SAID (${tLanguages.find(l => l.code === tTheirLang)?.native || tTheirLang} → ${tLanguages.find(l => l.code === tMyLang)?.native || tMyLang})` : "📢 YOU SAID (translated & spoken)"} — {tHistory[0].at}
                    </div>
                    <div style={{ fontSize: 12.5, color: "var(--text-dim)", fontStyle: "italic", marginBottom: 6 }}>"{tHistory[0].original}"</div>
                    <div style={{
                      fontSize: 16, fontWeight: 600, color: "#fff", lineHeight: 1.45,
                      direction: ["ar","fa","he","ur"].includes(tHistory[0].dir === "incoming" ? tMyLang : tTheirLang) ? "rtl" : "ltr",
                    }}>{tHistory[0].translation}</div>
                    {tHistory[0].dir === "incoming" && (
                      <button data-testid="trans-replay" onClick={() => playTTS(tHistory[0].translation, tMyLang)}
                        style={{ marginTop: 8, background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 8, padding: "4px 10px", fontSize: 11, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <Volume2 size={12} /> Hear translation
                      </button>
                    )}
                    {tHistory[0].dir === "incoming" && tHistory[0].tip && (
                      <div style={{ marginTop: 10, padding: 8, background: "rgba(247,201,72,0.08)", borderLeft: "3px solid var(--gold)", borderRadius: 4, fontSize: 12, color: "var(--gold)" }}>
                        💡 {tHistory[0].tip}
                      </div>
                    )}
                    {tHistory[0].dir === "incoming" && tHistory[0].suggested_reply && (
                      <div style={{ marginTop: 8, padding: 10, background: "rgba(34,197,94,0.08)", border: "1px dashed #22c55e", borderRadius: 8 }}>
                        <div style={{ fontSize: 10, fontWeight: 800, color: "#86efac", marginBottom: 4 }}>SUGGESTED REPLY</div>
                        <div style={{ fontSize: 13, color: "#fff", marginBottom: 6 }}>{tHistory[0].suggested_reply}</div>
                        <button data-testid="trans-speak-suggested" onClick={() => speakMyReply(tHistory[0].suggested_reply)} disabled={tReplyBusy}
                          className="btn-gold" style={{ fontSize: 11, padding: "5px 10px", display: "inline-flex", alignItems: "center", gap: 4 }}>
                          {tReplyBusy ? <span className="spinner" /> : <Volume2 size={12} />} Speak this reply
                        </button>
                      </div>
                    )}
                  </div>
                )}

                <TransReplyBar lang={lang} myLang={tMyLang} disabled={tReplyBusy} onSend={speakMyReply} />

                <div style={{ flex: 1, overflowY: "auto", marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                  {tHistory.length === 0 && tActive && <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 20, fontSize: 13 }}>Waiting for the other party to speak…</div>}
                  {tHistory.slice(1).map((h, i) => (
                    <div key={i} style={{
                      background: "var(--bg-card)", border: `1px solid ${h.dir === "incoming" ? "#155e75" : "var(--gold-deep)"}`,
                      borderRadius: 10, padding: 10,
                    }}>
                      <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4 }}>
                        {h.at} — {h.dir === "incoming" ? "They said" : "You said"}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-dim)", fontStyle: "italic", marginBottom: 4 }}>"{h.original}"</div>
                      <div style={{ fontSize: 13, color: h.dir === "incoming" ? "#67e8f9" : "var(--gold)", fontWeight: 600 }}>{h.translation}</div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Whisper Mode button — TTS read-aloud for the SAY THIS card.
// Includes a court-proximity warning with one-tap override (legitimate uses:
// waiting rooms, prep meetings, lawyer-client conversations near courts).
// "Auto-play" remembers the user's preference in localStorage so future advice
// is read aloud automatically when arrives.
function WhisperButton({ text, language }) {
  const [busy, setBusy] = useState(false);
  const [auto, setAuto] = useState(() => localStorage.getItem("aa_whisper_auto") === "1");
  const [override, setOverride] = useState(() => sessionStorage.getItem("aa_court_override") === "1");
  const [nearCourt, setNearCourt] = useState(false);
  const audioRef = useRef(null);
  const lastSpokenRef = useRef("");

  // Best-effort court-proximity check — only flags if recordingLaw helper exists
  // and explicitly returns isNearCourt:true. Otherwise assume safe.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mod = await import("./recordingLaw").catch(() => null);
        if (!mod || !mod.detectNearCourt || cancelled) return;
        const near = await mod.detectNearCourt();
        if (!cancelled) setNearCourt(!!near);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, []);

  const play = async () => {
    if (!text || busy) return;
    if (nearCourt && !override) return;          // visual only inside court
    setBusy(true);
    try {
      const r = await api.post("/voice/tts", { text, language }, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      if (audioRef.current) { try { audioRef.current.pause(); } catch {} }
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch (e) {
      console.warn("whisper TTS failed", e?.response?.data || e?.message);
    } finally {
      setBusy(false);
    }
  };

  // Auto-play newly-arrived advice (skips repeats by text-hash)
  useEffect(() => {
    if (!auto || !text || lastSpokenRef.current === text) return;
    lastSpokenRef.current = text;
    if (nearCourt && !override) return;
    play();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, auto]);

  const toggleAuto = () => {
    const next = !auto;
    setAuto(next);
    localStorage.setItem("aa_whisper_auto", next ? "1" : "0");
  };

  if (nearCourt && !override) {
    return (
      <button data-testid="whisper-court-override" onClick={() => { sessionStorage.setItem("aa_court_override", "1"); setOverride(true); }}
        title="Court area detected — tap to confirm you're in the waiting area, not the courtroom"
        style={{ background: "transparent", border: "1px solid #fca5a5", color: "#fca5a5", borderRadius: 8, padding: "3px 8px", fontSize: 10, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 4 }}>
        🚫 Audio off near court — tap to enable
      </button>
    );
  }

  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <button data-testid="whisper-play" onClick={play} disabled={busy}
        title="Read aloud — pair AirPods for discreet listening"
        style={{ background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 8, padding: "3px 8px", fontSize: 11, cursor: busy ? "wait" : "pointer", display: "inline-flex", alignItems: "center", gap: 4 }}>
        {busy ? <span className="spinner" style={{ width: 10, height: 10 }} /> : <Volume2 size={12} />}
        Listen
      </button>
      <button data-testid="whisper-auto-toggle" onClick={toggleAuto}
        title={auto ? "Auto-play ON: new advice will be spoken automatically" : "Tap to auto-play future advice"}
        style={{
          background: auto ? "var(--gold)" : "transparent",
          border: "1px solid var(--gold-deep)",
          color: auto ? "#1a1300" : "var(--gold)",
          borderRadius: 8, padding: "3px 8px", fontSize: 10, fontWeight: 700,
          cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 3,
        }}>
        {auto ? "AUTO ✓" : "Auto"}
      </button>
    </div>
  );
}

// Compact text/mic input for Translation Mode replies
function TransReplyBar({ lang, myLang, disabled, onSend }) {
  const [val, setVal] = useState("");
  const { recording, start, stop } = useRecorder();
  const handleMic = async () => {
    if (recording) {
      const blob = await stop();
      if (!blob) return;
      try {
        const fd = new FormData();
        fd.append("audio", blob, "reply.webm");
        fd.append("language", myLang);
        const tx = await api.post("/voice/transcribe", fd);
        const heard = (tx?.data?.text || "").trim();
        if (heard) setVal(v => (v ? v + " " : "") + heard);
      } catch {}
    } else {
      try { await start(); } catch { alert("Microphone needed for voice reply."); }
    }
  };
  const submit = () => {
    if (!val.trim()) return;
    onSend(val.trim());
    setVal("");
  };
  return (
    <div className="flex items-center gap-2" style={{ marginTop: 10 }}>
      <button onClick={handleMic} data-testid="trans-reply-mic"
        style={{ background: "#000", border: `2px solid ${recording ? "var(--danger)" : "var(--gold)"}`, borderRadius: "50%", width: 40, height: 40, cursor: "pointer", padding: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
        {recording ? <Square size={16} style={{ color: "var(--danger)" }} /> : <Mic size={16} style={{ color: "var(--gold)" }} />}
      </button>
      <input className="input" data-testid="trans-reply-input"
        placeholder="Type your reply (or tap mic) — Lex will speak it in their language"
        value={val} onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()} style={{ flex: 1 }} disabled={disabled} />
      <button className="btn-gold" data-testid="trans-reply-send" onClick={submit} disabled={disabled || !val.trim()} style={{ padding: "9px 12px" }}>
        <Volume2 size={14} />
      </button>
    </div>
  );
}

// ---------- Letter Library Modal ----------
function LetterLibraryModal({ lang, country, onClose }) {
  const [tpls, setTpls] = useState([]);
  const [sel, setSel] = useState(null);
  const [form, setForm] = useState({ your_name: "", recipient: "", facts: "" });
  const [busy, setBusy] = useState(false);
  const [letter, setLetter] = useState("");
  const [letterId, setLetterId] = useState(null);
  const [search, setSearch] = useState("");

  useEffect(() => { api.get("/letters/templates").then(r => setTpls(r.data)).catch(() => {}); }, []);

  const filtered = tpls.filter(t => !search ||
    t.title.toLowerCase().includes(search.toLowerCase()) ||
    t.category.toLowerCase().includes(search.toLowerCase()));
  const grouped = filtered.reduce((acc, t) => { (acc[t.category] = acc[t.category] || []).push(t); return acc; }, {});

  const generate = async () => {
    setBusy(true); setLetter("");
    try {
      const { data } = await api.post("/letters/generate", { template_id: sel.id, language: lang, country, ...form });
      setLetter(data.letter); setLetterId(data.id);
    } catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="letter-lib-modal">
      <div className="modal-card" style={{ padding: 18 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12, flexShrink: 0 }}>
          <h2 className="brand-font gold" style={{ fontSize: 18 }}>{sel ? sel.title : "Letter Library"}</h2>
          <button onClick={onClose} data-testid="letter-lib-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>

        {!sel && (
          <>
            <input className="input" data-testid="letter-search" placeholder={t(lang, "searchTemplates")} value={search} onChange={(e) => setSearch(e.target.value)} style={{ marginBottom: 12, flexShrink: 0 }} />
            <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
              {filtered.length === 0 && search && (
                <div style={{ color: "var(--text-dim)", fontSize: 13, textAlign: "center", padding: 20 }}>
                  No templates found for "{search}". Try a different keyword.
                </div>
              )}
              {Object.entries(grouped).map(([cat, items]) => (
                <div key={cat} style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 11, color: "var(--gold)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{cat}</div>
                  {items.map(tpl => (
                    <button key={tpl.id} data-testid={`letter-tpl-${tpl.id}`} onClick={() => setSel(tpl)}
                      style={{ display: "block", width: "100%", textAlign: "left", padding: "10px 12px", marginBottom: 6,
                               background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10,
                               color: "var(--text)", cursor: "pointer", fontSize: 13.5 }}>
                      {tpl.title}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </>
        )}

        {sel && !letter && (
          <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
            <button className="btn-ghost" onClick={() => setSel(null)} style={{ marginBottom: 10, padding: "6px 12px" }}>
              <ArrowLeft size={14} style={{ display: "inline", marginRight: 4 }} />Back
            </button>
            <input className="input" data-testid="letter-name" placeholder={t(lang, "yourFullName")} value={form.your_name} onChange={(e) => setForm({ ...form, your_name: e.target.value })} style={{ marginBottom: 8 }} />
            <input className="input" data-testid="letter-recipient" placeholder={t(lang, "recipientNameAddr")} value={form.recipient} onChange={(e) => setForm({ ...form, recipient: e.target.value })} style={{ marginBottom: 8 }} />
            <textarea className="input" data-testid="letter-facts" rows={5} placeholder={t(lang, "letterFactsPlaceholder")} value={form.facts} onChange={(e) => setForm({ ...form, facts: e.target.value })} />
            <button className="btn-gold w-full" data-testid="letter-gen-btn" onClick={generate} disabled={busy || !form.your_name || !form.recipient || !form.facts} style={{ marginTop: 12 }}>
              {busy ? <span className="spinner" /> : "Generate Letter"}
            </button>
          </div>
        )}

        {letter && (
          <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
            <div data-testid="letter-output" style={{ whiteSpace: "pre-wrap", fontSize: 13.5, color: "var(--text-dim)", lineHeight: 1.6,
                          background: "#0a0a0a", border: "1px solid var(--line)", borderRadius: 10, padding: 14 }}>{letter}</div>
            <div className="flex gap-2" style={{ marginTop: 12 }}>
              <button className="btn-gold" data-testid="letter-pdf"
                onClick={() => pdfInline({ title: sel.title, subtitle: form.recipient, body: letter, filename: `${sel.id}.pdf` })}
                style={{ flex: 1 }}>
                <Download size={14} style={{ display: "inline", marginRight: 6 }} />Download PDF
              </button>
              <button className="btn-ghost" onClick={() => { setLetter(""); setLetterId(null); }} style={{ flex: 1 }}>{t(lang, "letterRedo")}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Contract Upload ----------
function ContractUploader({ lang, country, onClose }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const upload = async () => {
    if (!file) return; setBusy(true);
    const fd = new FormData(); fd.append("file", file); fd.append("language", lang); fd.append("country", country);
    try {
      const { data } = await api.post("/contracts/analyze", fd);
      setResult(data);
    } catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="contract-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "contractReview")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={24} /></button>
        </div>
        {!result ? (
          <>
            <label htmlFor="cfile" style={{ display: "block", border: "2px dashed var(--gold-deep)", borderRadius: 14, padding: 30, textAlign: "center", cursor: "pointer", color: "var(--text-dim)" }} data-testid="contract-dropzone">
              <Upload size={32} style={{ color: "var(--gold)", marginBottom: 8 }} />
              <div>{file ? file.name : "Click to upload PDF, DOCX, or image"}</div>
            </label>
            <input id="cfile" data-testid="contract-file-input" type="file" accept=".pdf,.docx,.txt,image/*" onChange={(e) => setFile(e.target.files[0])} style={{ display: "none" }} />
            <button className="btn-gold w-full" data-testid="contract-analyze-btn" disabled={!file || busy} onClick={upload} style={{ marginTop: 16 }}>
              {busy ? <span className="spinner" /> : t(lang, "upload")}
            </button>
            {busy && <div style={{ textAlign: "center", color: "var(--gold-soft)", marginTop: 14 }}>{t(lang, "analysisRunning")}</div>}
          </>
        ) : (
          <div style={{ overflowY: "auto", flex: 1 }}>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 8 }}>{result.filename}</div>
            <div style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.6, color: "var(--text-dim)" }}>{result.analysis}</div>
            <button className="btn-ghost w-full" onClick={() => { setResult(null); setFile(null); }} style={{ marginTop: 16 }}>
              Analyze another
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Legal Letter ----------
function LegalLetterModal({ lang, country, onClose }) {
  const [form, setForm] = useState({ letter_type: "", recipient: "", your_name: "", details: "" });
  const [letter, setLetter] = useState(""); const [busy, setBusy] = useState(false);

  const generate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/legal-letter", { ...form, language: lang });
      setLetter(data.letter);
    } catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="letter-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "legalLetterTitle")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={24} /></button>
        </div>
        {!letter ? (
          <div style={{ overflowY: "auto" }}>
            <input className="input" data-testid="letter-type" placeholder={t(lang, "letterType")} value={form.letter_type} onChange={(e) => setForm({ ...form, letter_type: e.target.value })} style={{ marginBottom: 10 }} />
            <input className="input" data-testid="letter-yourname" placeholder={t(lang, "yourName")} value={form.your_name} onChange={(e) => setForm({ ...form, your_name: e.target.value })} style={{ marginBottom: 10 }} />
            <input className="input" data-testid="letter-recipient" placeholder={t(lang, "recipient")} value={form.recipient} onChange={(e) => setForm({ ...form, recipient: e.target.value })} style={{ marginBottom: 10 }} />
            <textarea className="input" data-testid="letter-details" placeholder={t(lang, "details")} rows={6} value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} />
            <button className="btn-gold w-full" data-testid="letter-generate-btn" onClick={generate} disabled={busy || !form.letter_type || !form.details} style={{ marginTop: 12 }}>
              {busy ? <span className="spinner" /> : t(lang, "generate")}
            </button>
          </div>
        ) : (
          <div style={{ overflowY: "auto" }}>
            <pre style={{ background: "#0a0a0a", padding: 16, borderRadius: 12, whiteSpace: "pre-wrap", color: "var(--text-dim)", fontSize: 13.5, fontFamily: "Outfit, sans-serif" }}>{letter}</pre>
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="btn-gold" data-testid="letter-pdf-btn" onClick={() => pdfInline({
                title: form.letter_type || "Legal Letter",
                subtitle: `From: ${form.your_name} · To: ${form.recipient}`,
                body: letter,
                meta: { Date: new Date().toLocaleDateString() },
                filename: `${(form.letter_type || "letter").replace(/[^A-Za-z0-9]/g, "_")}.pdf`
              })} style={{ flex: 1 }}>
                <Download size={16} style={{ display: "inline", marginRight: 6 }} />Download PDF
              </button>
              <button className="btn-ghost" onClick={() => setLetter("")} style={{ flex: 1 }}>{t(lang, "letterNewLetter")}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Record Hub (unified entry: Encounter ↔ Hearing) ----------
// One tile, two modes. Encounter = the original RecordModal (Plus tier, panic-mic GPS-stamped).
// Hearing = HearingRecorderModal (Pro tier, title field + file upload, no GPS).
// Mode persists per-user via localStorage so frequent users land on their preferred mode.
function RecordHub({ lang, country, user, hasTier, onUpsell, onClose }) {
  const [mode, setMode] = useState(() => localStorage.getItem("aa_record_mode") || "encounter");
  const setModePersist = (m) => {
    if (m === "hearing" && !hasTier("pro")) {
      onUpsell?.();
      return;
    }
    setMode(m);
    localStorage.setItem("aa_record_mode", m);
  };
  const ModePill = ({ k, icon, label, tierBadge }) => (
    <button data-testid={`record-mode-${k}`} onClick={() => setModePersist(k)}
      style={{
        flex: 1, padding: "10px 8px", borderRadius: 999, cursor: "pointer",
        background: mode === k ? "var(--gold)" : "transparent",
        color: mode === k ? "#0a0a0a" : "var(--gold)",
        border: `1px solid ${mode === k ? "var(--gold)" : "var(--gold-deep)"}`,
        fontSize: 12.5, fontWeight: 700, letterSpacing: "0.04em",
        display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
      }}>
      <span style={{ fontSize: 14 }}>{icon}</span>{label}
      {tierBadge && (
        <span style={{
          fontSize: 9, padding: "1px 5px", borderRadius: 6,
          background: mode === k ? "rgba(0,0,0,0.15)" : "rgba(247,201,72,0.15)",
          letterSpacing: "0.06em",
        }}>{tierBadge}</span>
      )}
    </button>
  );
  return (
    <>
      {/* Floating mode-picker sits above the chosen sub-modal */}
      <div data-testid="record-hub-modeswitch" style={{
        position: "fixed", top: 18, left: "50%", transform: "translateX(-50%)",
        zIndex: 1001, background: "rgba(10,10,10,0.92)", backdropFilter: "blur(10px)",
        border: "1px solid var(--gold-deep)", borderRadius: 999, padding: 4,
        display: "flex", gap: 4, width: "min(360px, calc(100% - 24px))",
        boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
      }}>
        <ModePill k="encounter" icon="🚔" label="Encounter" />
        <ModePill k="hearing" icon="🏛" label="Hearing" tierBadge={!hasTier("pro") ? "PRO" : null} />
      </div>
      {mode === "hearing"
        ? <HearingRecorderModal lang={lang} country={country} onClose={onClose} />
        : <RecordModal lang={lang} country={country} onClose={onClose} />}
    </>
  );
}

// ---------- Record Legal Interaction ----------
function RecordModal({ lang, country, onClose }) {
  const { recording, start, stop } = useRecorder();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [meta, setMeta] = useState(null);  // {started_at, ended_at, duration_s, location}
  const startedAtRef = useRef(null);
  const { ensureConsent, GateModal } = useRecordingConsent({ lang, country, surface: "record_legal", recordingTitle: "" });

  // Best-effort GPS: silently captured ONCE, after the user starts recording.
  // Permission may be denied — that's fine, we just omit location from the evidence header.
  const captureLocation = () => new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({
        lat: pos.coords.latitude.toFixed(5),
        lng: pos.coords.longitude.toFixed(5),
        accuracy_m: Math.round(pos.coords.accuracy || 0),
      }),
      () => resolve(null),
      { enableHighAccuracy: false, timeout: 4000, maximumAge: 60000 }
    );
  });

  const onMic = async () => {
    if (recording) {
      // STOP — capture wall-clock end time + duration
      const endedAt = new Date();
      const blob = await stop(); if (!blob) return;
      const startedAt = startedAtRef.current || new Date(endedAt.getTime());
      const durationS = Math.max(1, Math.round((endedAt - startedAt) / 1000));
      setBusy(true);
      const fd = new FormData();
      fd.append("audio", blob, "rec.webm");
      fd.append("language", lang);
      fd.append("country", country);
      fd.append("recorded_at", startedAt.toISOString());
      fd.append("ended_at", endedAt.toISOString());
      fd.append("duration_seconds", String(durationS));
      fd.append("timezone", Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC");
      // Attach the location we captured at start (if user granted permission)
      const loc = startedAtRef.current?.__loc;
      if (loc) {
        fd.append("location_lat", loc.lat);
        fd.append("location_lng", loc.lng);
        fd.append("location_accuracy_m", String(loc.accuracy_m));
      }
      try {
        const { data } = await api.post("/record/analyze", fd);
        setResult(data);
        setMeta({
          started_at: startedAt.toISOString(),
          ended_at: endedAt.toISOString(),
          duration_s: durationS,
          location: loc || null,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
        });
      } catch (e) {
        alert(e?.response?.data?.detail || "Failed");
      } finally {
        setBusy(false);
        startedAtRef.current = null;
      }
    } else {
      // START — stamp wall-clock now, request location in parallel (non-blocking)
      const now = new Date();
      startedAtRef.current = now;
      captureLocation().then((loc) => { if (loc && startedAtRef.current) startedAtRef.current.__loc = loc; });
      start();
    }
  };

  // Wrap mic press in consent gate (only fires before first start, not for stop)
  const onMicGated = recording ? onMic : ensureConsent(onMic);

  // Pretty time helpers
  const fmtTime = (iso) => {
    try {
      const d = new Date(iso);
      return d.toLocaleString(lang || "en-GB", {
        year: "numeric", month: "short", day: "2-digit",
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        timeZoneName: "short",
      });
    } catch { return iso; }
  };
  const fmtDur = (s) => {
    if (!s) return "0s";
    const m = Math.floor(s / 60); const r = s % 60;
    return m > 0 ? `${m}m ${r}s` : `${r}s`;
  };

  return (
    <div className="modal-bg" data-testid="record-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "recordLegal")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={24} /></button>
        </div>
        {!result ? (
          <div style={{ textAlign: "center", padding: "30px 10px" }}>
            <p style={{ color: "var(--text-dim)", marginBottom: 20 }}>
              Record your interaction with police, court, or any legal authority. Every recording is time-stamped (UTC + your local time) and optionally tagged with GPS location for evidentiary use. Lex will transcribe and analyse it.
            </p>
            <button onClick={onMicGated} disabled={busy} data-testid="record-mic-btn"
                    className={recording ? "lex-circle recording" : ""}
                    style={{ width: 100, height: 100, borderRadius: "50%", background: recording ? "var(--danger)" : "var(--bg-card)",
                             border: "2px solid var(--gold)", color: "var(--gold)", margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
              {busy ? <span className="spinner" /> : (recording ? <Square size={36} /> : <Mic size={36} />)}
            </button>
            <p style={{ marginTop: 14, color: "var(--gold-soft)" }}>
              {busy ? t(lang, "analyzing") : (recording ? t(lang, "recording") : t(lang, "tapToRecord"))}
            </p>
            {recording && startedAtRef.current && (
              <div data-testid="record-live-stamp" style={{ marginTop: 14, padding: "8px 12px", background: "rgba(247,201,72,0.06)", border: "1px solid var(--gold-deep)", borderRadius: 10, display: "inline-block", color: "var(--gold)", fontSize: 11, letterSpacing: "0.03em" }}>
                ● Started: {fmtTime(startedAtRef.current.toISOString())}
              </div>
            )}
          </div>
        ) : (
          <div style={{ overflowY: "auto" }}>
            {/* Evidence header — time-stamped, prominent */}
            {meta && (
              <div data-testid="record-evidence-header" style={{ background: "linear-gradient(135deg, rgba(247,201,72,0.10), rgba(247,201,72,0.02))", border: "1px solid var(--gold)", borderRadius: 12, padding: 12, marginBottom: 14 }}>
                <div style={{ color: "var(--gold)", fontWeight: 700, fontSize: 11, letterSpacing: "0.14em", marginBottom: 6 }}>⚖ EVIDENCE METADATA</div>
                <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px", fontSize: 12, color: "var(--text)" }}>
                  <div style={{ color: "var(--gold-soft)" }}>Started:</div><div>{fmtTime(meta.started_at)}</div>
                  <div style={{ color: "var(--gold-soft)" }}>Ended:</div><div>{fmtTime(meta.ended_at)}</div>
                  <div style={{ color: "var(--gold-soft)" }}>Duration:</div><div>{fmtDur(meta.duration_s)}</div>
                  <div style={{ color: "var(--gold-soft)" }}>Timezone:</div><div>{meta.timezone}</div>
                  {meta.location && (
                    <><div style={{ color: "var(--gold-soft)" }}>Location:</div><div>{meta.location.lat}, {meta.location.lng} (±{meta.location.accuracy_m}m)</div></>
                  )}
                </div>
              </div>
            )}
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>{t(lang, "transcript")}</div>
            <div style={{ background: "#0a0a0a", padding: 12, borderRadius: 10, color: "var(--text-dim)", fontSize: 13.5, marginBottom: 14 }}>{result.transcript}</div>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>{t(lang, "lexAnalysis")}</div>
            <div style={{ background: "#0a0a0a", padding: 12, borderRadius: 10, color: "var(--text-dim)", fontSize: 13.5, whiteSpace: "pre-wrap" }}>{result.analysis}</div>
            <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
              <button className="btn-gold" data-testid="record-pdf-btn" onClick={() => pdfForFile(result.id, result.filename || "recording")} style={{ flex: 1, minWidth: 120 }}>
                <Download size={16} style={{ display: "inline", marginRight: 6 }} />Download PDF
              </button>
              {/* Save the encounter recording's transcript + analysis into the Vault. */}
              <button className="btn-ghost" data-testid="record-vault-btn"
                onClick={async () => {
                  if (!result?.id) { aaToast("Save unavailable.", "error"); return; }
                  try {
                    const bundle = JSON.stringify({ transcript: result.transcript, analysis: result.analysis, meta }, null, 2);
                    await api.post(`/legal-files/${result.id}/save-to-vault`, {
                      file_id: result.id,
                      encrypted_content: btoa(unescape(encodeURIComponent(bundle))),
                      iv: "record-shim",
                      label: `Encounter — ${new Date().toLocaleDateString()}`,
                    });
                    aaToast("Saved to Vault", "success");
                  } catch (e) { aaToast(e?.response?.data?.detail || "Save failed", "error"); }
                }}
                style={{ flex: 1, minWidth: 120 }}>
                <ShieldCheck size={14} style={{ display: "inline", marginRight: 6 }} />Save to Vault
              </button>
              <button className="btn-ghost" onClick={() => { setResult(null); setMeta(null); }} style={{ flex: 1, minWidth: 120 }}>{t(lang, "recordAnother")}</button>
            </div>
          </div>
        )}
      </div>
      {GateModal}
    </div>
  );
}

// ---------- My Files ----------
function FilesModal({ lang, onClose }) {
  const [files, setFiles] = useState([]); const [open, setOpen] = useState(null); const [busy, setBusy] = useState(false);
  const load = () => api.get("/legal-files").then(r => setFiles(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);
  const removeFile = async (id, e) => {
    e?.stopPropagation?.();
    const ok = await aaConfirm({
      title: "Delete file?",
      message: "It'll move to your Recycle Bin and stay there for 30 days. You can restore it anytime.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.delete(`/legal-files/${id}`);
      if (open?.id === id) setOpen(null);
      setFiles(prev => prev.filter(f => f.id !== id));
      load();
      aaToast("File moved to Recycle Bin", "success");
    } catch (err) { aaToast(err?.response?.data?.detail || "Delete failed", "error"); }
    finally { setBusy(false); }
  };
  // Save the currently-open file's content into the Vault. Encryption happens on the
  // server side using the user's Fernet envelope (the client-side AES wrap is layered
  // on top inside the Vault modal itself when the user unlocks).
  const saveToVault = async (f) => {
    if (!f) return;
    setBusy(true);
    try {
      const body = (f.content || f.analysis || f.transcript || JSON.stringify(f)).slice(0, 50000);
      await api.post(`/legal-files/${f.id}/save-to-vault`, {
        file_id: f.id,
        encrypted_content: btoa(unescape(encodeURIComponent(body))),
        iv: "legal-file-shim",
        label: f.filename || f.type || "Legal file",
      });
      aaToast("Saved to Vault", "success");
    } catch (err) { aaToast(err?.response?.data?.detail || "Save to Vault failed", "error"); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-bg" data-testid="files-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "myFiles")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={24} /></button>
        </div>
        {!open ? (
          <div style={{ overflowY: "auto" }}>
            {files.length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 20 }}>{t(lang, "noFilesYet")}</p>}
            {files.map(f => (
              <div key={f.id} style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                <button onClick={() => setOpen(f)} className="w-full" data-testid={`file-${f.id}`}
                        style={{ flex: 1, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 14, color: "var(--text)", textAlign: "left", cursor: "pointer" }}>
                  <div style={{ color: "var(--gold)", fontWeight: 600 }}>{f.filename || f.type}</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{new Date(f.created_at).toLocaleString()}</div>
                </button>
                <button data-testid={`file-delete-${f.id}`} title="Delete file" disabled={busy}
                        onClick={(e) => removeFile(f.id, e)}
                        style={{ background: "transparent", border: "1px solid #7f1d1d", color: "#fca5a5", borderRadius: 10, padding: "0 12px", cursor: "pointer" }}>
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ overflowY: "auto" }}>
            <button className="btn-ghost" onClick={() => setOpen(null)} style={{ marginBottom: 12, padding: "8px 14px" }}><ArrowLeft size={16} /> Back</button>
            <h3 style={{ color: "var(--gold)" }}>{open.filename}</h3>
            {open.transcript && <><div style={{ color: "var(--gold)", marginTop: 10 }}>Transcript</div><div style={{ background: "#0a0a0a", padding: 10, borderRadius: 8, color: "var(--text-dim)", fontSize: 13 }}>{open.transcript}</div></>}
            {(open.analysis || open.content) && <><div style={{ color: "var(--gold)", marginTop: 10 }}>Content</div><div style={{ background: "#0a0a0a", padding: 10, borderRadius: 8, whiteSpace: "pre-wrap", color: "var(--text-dim)", fontSize: 13 }}>{open.analysis || open.content}</div></>}
            <div style={{ display: "flex", gap: 8, marginTop: 14, flexWrap: "wrap" }}>
              <button className="btn-gold" data-testid="file-pdf-btn" onClick={() => pdfForFile(open.id, open.filename || "ai_advocate")} style={{ flex: 1, minWidth: 120 }}>
                <Download size={16} style={{ display: "inline", marginRight: 6 }} />Download PDF
              </button>
              <button className="btn-ghost" data-testid="file-vault-btn" disabled={busy} onClick={() => saveToVault(open)}
                      style={{ flex: 1, minWidth: 120 }}>
                <ShieldCheck size={14} style={{ display: "inline", marginRight: 6 }} />Save to Vault
              </button>
              <button data-testid="file-delete-detail-btn" disabled={busy} onClick={(e) => removeFile(open.id, e)}
                      style={{ background: "transparent", border: "1px solid #7f1d1d", color: "#fca5a5", borderRadius: 10, padding: "10px 14px", cursor: "pointer", fontSize: 13, fontWeight: 600 }}>
                <Trash2 size={14} style={{ display: "inline", marginRight: 6 }} />Delete
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Case Files (group chats / photos / videos / letters per case) ----------
function CaseFilesModal({ lang, onClose, openCaseId }) {
  const [cases, setCases] = useState([]);
  const [open, setOpen] = useState(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/cases").then(r => setCases(r.data.cases || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  // Deep-link support: timeline taps a case → opens that case directly
  useEffect(() => {
    if (!openCaseId) return;
    let cancelled = false;
    api.get(`/cases/${openCaseId}`).then(r => { if (!cancelled) setOpen(r.data); }).catch(() => {});
    return () => { cancelled = true; };
  }, [openCaseId]);

  // Escape closes detail-view first, then closes the whole modal
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      if (open) { setOpen(null); }
      else { onClose(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const openCase = async (c) => {
    const r = await api.get(`/cases/${c.id}`);
    setOpen(r.data);
  };

  const createCase = async () => {
    if (!newName.trim() && !creating) return;
    setBusy(true);
    try {
      const r = await api.post("/cases", { name: newName.trim() || "Untitled case" });
      setNewName(""); setCreating(false); await load(); openCase(r.data);
    } catch (e) { alert(e?.response?.data?.detail || t(lang, "failed")); }
    finally { setBusy(false); }
  };

  const rename = async () => {
    const v = prompt(t(lang, "renameCase"), open.name);
    if (!v || !v.trim()) return;
    const r = await api.patch(`/cases/${open.id}`, { name: v.trim() });
    setOpen({ ...open, name: r.data.name }); load();
  };

  const remove = async () => {
    const ok = await aaConfirm({
      title: "Delete this case?",
      message: "It'll move to your Recycle Bin and stay there for 30 days. You can restore it anytime.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    await api.delete(`/cases/${open.id}`);
    aaToast("Case moved to Recycle Bin", "success");
    setOpen(null); load();
  };

  // Upload an arbitrary file (doc/photo/audio/video) into the open case as a new item.
  const uploadRef = useRef(null);
  const onUpload = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (f.size > 50 * 1024 * 1024) { alert("File too large (50MB max)."); return; }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("title", f.name);
      await api.post(`/cases/${open.id}/upload-file`, fd);
      const r = await api.get(`/cases/${open.id}`);
      setOpen(r.data);
    } catch (err) { alert(err?.response?.data?.detail || "Upload failed"); }
    finally { setBusy(false); }
  };

  // Soft-delete a single item in the case (file/photo/recording/letter).
  const deleteItem = async (itemId) => {
    const ok = await aaConfirm({
      title: "Delete this item?",
      message: "It'll move to your Recycle Bin and stay there for 30 days. You can restore it anytime.",
      confirmLabel: "Delete",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.delete(`/case-items/${itemId}`);
      const r = await api.get(`/cases/${open.id}`);
      setOpen(r.data);
      aaToast("Item moved to Recycle Bin", "success");
    } catch (err) { aaToast(err?.response?.data?.detail || "Delete failed", "error"); }
    finally { setBusy(false); }
  };

  // Save a case-item to the Vault. We let the user save the human-readable preview/title
  // (the bytes themselves aren't stored on the server for evidence items — Vault stores
  // a labelled snapshot of the item's metadata + preview that the user can recover later).
  const saveItemToVault = async (it) => {
    // Reuse the legal-files save-to-vault endpoint by first writing a tiny legal_file
    // shadow with the item's content, then calling save-to-vault. Simpler: dispatch a
    // global event so the Vault modal can pick it up — keeps logic isolated.
    window.dispatchEvent(new CustomEvent("aa:save-to-vault", { detail: {
      kind: it.item_type || "case_item",
      label: it.title || it.filename || "Case item",
      preview: it.preview || it.title || "",
    }}));
    alert("Open the Vault to confirm encrypting and saving this item.");
  };

  const exportPdf = async () => {
    try {
      const r = await api.get(`/cases/${open.id}/export-pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `case-${open.id.slice(0,8)}.pdf`; a.click();
    } catch (e) { alert(e?.response?.data?.detail || t(lang, "failed")); }
  };

  const shareCase = async () => {
    try {
      const { data } = await api.post(`/cases/${open.id}/share`);
      await navigator.clipboard.writeText(data.url).catch(() => {});
      alert(`Read-only share link copied to clipboard:\n\n${data.url}\n\nExpires in 30 days.`);
    } catch (e) { alert(e?.response?.data?.detail || "Failed to create share link"); }
  };

  return (
    <div className="modal-bg" data-testid="cases-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "caseFiles")}</h2>
          <button onClick={onClose} data-testid="cases-close" style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={24} /></button>
        </div>
        {!open ? (
          <div style={{ overflowY: "auto", paddingBottom: 60 }}>
            {!creating ? (
              <button className="btn-gold w-full" data-testid="new-case-btn" onClick={() => setCreating(true)} style={{ marginBottom: 12 }}>
                + {t(lang, "newCase")}
              </button>
            ) : (
              <div style={{ marginBottom: 12 }}>
                <input className="input" data-testid="new-case-name" placeholder={t(lang, "caseNamePlaceholder")} value={newName} onChange={(e) => setNewName(e.target.value)} style={{ marginBottom: 8 }} />
                <div className="flex gap-2">
                  <button className="btn-gold" data-testid="create-case-confirm" disabled={busy} onClick={createCase} style={{ flex: 1 }}>{busy ? <span className="spinner" /> : t(lang, "save")}</button>
                  <button className="btn-ghost" onClick={() => { setCreating(false); setNewName(""); }} style={{ flex: 1 }}>{t(lang, "cancel")}</button>
                </div>
              </div>
            )}
            {cases.length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 20 }}>{t(lang, "noCases")}</p>}
            {cases.map(c => (
              <button key={c.id} onClick={() => openCase(c)} data-testid={`case-${c.id}`} className="w-full"
                      style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, padding: 14, marginBottom: 8, color: "var(--text)", textAlign: "left", cursor: "pointer" }}>
                <div style={{ color: "var(--gold)", fontWeight: 600 }}>{c.name}</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                  {c.status === "open" ? t(lang, "caseStatusOpen") : t(lang, "caseStatusClosed")} · {t(lang, "itemsInCase", { n: c.items_count || 0 })} · {new Date(c.updated_at).toLocaleDateString()}
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div style={{ overflowY: "auto", paddingBottom: 60 }}>
            <button className="btn-ghost" onClick={() => setOpen(null)} style={{ marginBottom: 12, padding: "6px 12px", fontSize: 13 }}><ArrowLeft size={14} /> {t(lang, "backToList")}</button>
            <h3 style={{ color: "var(--gold)", marginBottom: 4 }}>{open.name}</h3>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 14 }}>
              {t(lang, "timestamp")}: {new Date(open.created_at).toLocaleString()}
            </div>
            <div className="flex gap-2" style={{ marginBottom: 14 }}>
              <button className="btn-ghost" onClick={rename} data-testid="rename-case-btn" style={{ flex: 1, fontSize: 12 }}>{t(lang, "renameCase")}</button>
              <button className="btn-ghost" onClick={exportPdf} data-testid="export-case-btn" style={{ flex: 1, fontSize: 12 }}>{t(lang, "exportCasePdf")}</button>
              <button className="btn-ghost" onClick={shareCase} data-testid="share-case-btn" style={{ flex: 1, fontSize: 12 }}>Share</button>
              <button className="btn-ghost" onClick={remove} data-testid="delete-case-btn" style={{ flex: 0.7, fontSize: 12, color: "#fca5a5" }}><Trash2 size={14} /></button>
            </div>
            {/* Upload to case — accepts document/photo/audio/video. Stored as a case_item with SHA256 + timestamp. */}
            <input ref={uploadRef} type="file" accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.txt"
                   onChange={onUpload} style={{ display: "none" }} data-testid="case-upload-input" />
            <button className="btn-ghost w-full" data-testid="case-upload-btn" disabled={busy}
                    onClick={() => uploadRef.current?.click()}
                    style={{ marginBottom: 12, padding: 10, fontSize: 12, borderStyle: "dashed" }}>
              {busy ? <span className="spinner" /> : <>+ Upload file to this case</>}
            </button>
            {(open.items || []).length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 14, fontSize: 13 }}>{t(lang, "noFilesYet")}</p>}
            {(open.items || []).map(it => (
              <div key={it.id} data-testid={`case-item-${it.id}`} style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 12, marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span style={{ background: "var(--gold-deep)", color: "#1a1300", padding: "2px 7px", borderRadius: 8, fontSize: 10, fontWeight: 700, letterSpacing: "0.05em" }}>{(it.item_type || "ITEM").toUpperCase()}</span>
                  <span style={{ color: "var(--gold)", fontSize: 13, fontWeight: 600, flex: 1 }}>{it.title}</span>
                </div>
                {it.preview && <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4, whiteSpace: "pre-wrap" }}>{it.preview}</div>}
                <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }}>
                  {new Date(it.timestamp_utc || it.created_at).toLocaleString()}
                  {it.location && ` · 📍 ${it.location}`}
                  {it.sha256 && ` · sha256:${it.sha256.slice(0,8)}…`}
                </div>
                {/* Per-item actions — Save to Vault + Delete (soft, restorable for 30 days) */}
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  <button data-testid={`case-item-vault-${it.id}`} onClick={() => saveItemToVault(it)}
                          className="btn-ghost" style={{ flex: 1, fontSize: 11, padding: "6px 8px" }}>
                    🛡 Save to Vault
                  </button>
                  <button data-testid={`case-item-delete-${it.id}`} onClick={() => deleteItem(it.id)} disabled={busy}
                          style={{ background: "transparent", border: "1px solid #7f1d1d", color: "#fca5a5", borderRadius: 8, padding: "6px 12px", fontSize: 11, cursor: "pointer" }}>
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Reminders / Limitation Periods ----------
function RemindersModal({ lang, onClose }) {
  const [reminders, setReminders] = useState([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", due_at: "" });
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/reminders").then(r => setReminders(r.data.reminders || [])).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.title.trim() || !form.due_at) return;
    setBusy(true);
    try {
      // Ensure ISO format
      const dueIso = new Date(form.due_at).toISOString();
      await api.post("/reminders", { title: form.title, description: form.description, due_at: dueIso });
      setForm({ title: "", description: "", due_at: "" }); setAdding(false); load();
    } catch (e) { alert(e?.response?.data?.detail || t(lang, "failed")); }
    finally { setBusy(false); }
  };

  const markDone = async (rid) => { await api.patch(`/reminders/${rid}?status=done`); load(); };

  return (
    <div className="modal-bg" data-testid="reminders-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "reminders")}</h2>
          <button onClick={onClose} data-testid="reminders-close" style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={24} /></button>
        </div>
        <div style={{ overflowY: "auto", paddingBottom: 60 }}>
          {!adding ? (
            <button className="btn-gold w-full" data-testid="add-reminder-btn" onClick={() => setAdding(true)} style={{ marginBottom: 12 }}>+ {t(lang, "addReminder")}</button>
          ) : (
            <div style={{ marginBottom: 12 }}>
              <input className="input" data-testid="rem-title" placeholder={t(lang, "reminderTitle")} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} style={{ marginBottom: 8 }} />
              <textarea className="input" data-testid="rem-desc" rows={2} placeholder={t(lang, "reminderDescription")} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} style={{ marginBottom: 8 }} />
              <input className="input" data-testid="rem-due" type="datetime-local" value={form.due_at} onChange={(e) => setForm({ ...form, due_at: e.target.value })} style={{ marginBottom: 8 }} />
              <div className="flex gap-2">
                <button className="btn-gold" data-testid="save-rem-btn" disabled={busy} onClick={create} style={{ flex: 1 }}>{busy ? <span className="spinner" /> : t(lang, "save")}</button>
                <button className="btn-ghost" onClick={() => setAdding(false)} style={{ flex: 1 }}>{t(lang, "cancel")}</button>
              </div>
            </div>
          )}
          {reminders.length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 20 }}>{t(lang, "noReminders")}</p>}
          {reminders.map(r => {
            const due = new Date(r.due_at);
            const daysOut = Math.ceil((due - new Date()) / (24 * 3600 * 1000));
            const urgent = daysOut <= 3;
            return (
              <div key={r.id} data-testid={`rem-${r.id}`}
                   style={{ background: "var(--bg-card)", border: `1px solid ${urgent ? "#dc2626" : "var(--line)"}`, borderRadius: 10, padding: 12, marginBottom: 8 }}>
                <div style={{ color: urgent ? "#fca5a5" : "var(--gold)", fontWeight: 600 }}>
                  {urgent && "⚠ "}{r.title}
                </div>
                {r.description && <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4 }}>{r.description}</div>}
                <div style={{ fontSize: 11, color: urgent ? "#fca5a5" : "var(--text-muted)", marginTop: 6 }}>
                  Due {due.toLocaleString()} · {daysOut > 0 ? `${daysOut}d left` : `${-daysOut}d overdue`}
                </div>
                <button className="btn-ghost" onClick={() => markDone(r.id)} data-testid={`done-${r.id}`} style={{ marginTop: 8, padding: "4px 10px", fontSize: 11 }}>
                  ✓ {t(lang, "reminderMarkDone")}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------- Trustpilot pre-renewal review prompt ----------
function ReviewPrompt({ lang, onClose, daysLeft }) {
  return (
    <div className="modal-bg" data-testid="review-prompt" style={{ zIndex: 10001 }}>
      <div className="modal-card" style={{ padding: 22, maxHeight: "60vh", textAlign: "center" }}>
        <div style={{ fontSize: 38, marginBottom: 8 }}>⭐</div>
        <h2 className="brand-font gold" style={{ fontSize: 22, marginBottom: 8 }}>{t(lang, "leaveReview")}</h2>
        <p style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.6, marginBottom: 18 }}>
          {t(lang, "reviewSubText")}
          {daysLeft != null && daysLeft > 0 && (
            <><br /><strong style={{ color: "var(--gold)" }}>{daysLeft}d</strong></>
          )}
        </p>
        <a href="https://www.trustpilot.com/review/aiadvocate.co.uk" target="_blank" rel="noreferrer"
           data-testid="trustpilot-link"
           onClick={() => { api.post("/review/recorded").catch(() => {}); setTimeout(onClose, 200); }}
           className="btn-gold" style={{ display: "block", padding: "12px 18px", marginBottom: 10, textDecoration: "none" }}>
          ⭐ {t(lang, "rateOnTrustpilot")}
        </a>
        <button className="btn-ghost" data-testid="review-not-now" onClick={onClose} style={{ padding: "10px 18px", fontSize: 13 }}>
          {t(lang, "notNow")}
        </button>
      </div>
    </div>
  );
}



// ---------- Snap Evidence (camera + upload + video record) ----------
function SnapEvidenceModal({ lang, country, onClose }) {
  const [files, setFiles] = useState([]); // [{ file, preview }]
  const [evidenceType, setEvidenceType] = useState("auto");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState([]); // [{ filename, analysis, id }]
  const [videoResult, setVideoResult] = useState(null); // {transcript, analysis, evidence_hash}
  const [recordedBlob, setRecordedBlob] = useState(null);
  const [recordedUrl, setRecordedUrl] = useState(null);
  const cameraRef = useRef(null);
  const libraryRef = useRef(null);
  const videoFileRef = useRef(null);      // capture="environment" → opens device camera to record
  const videoLibraryRef = useRef(null);   // no capture → opens gallery / file picker

  // Open the native OS camera app to record video. This is the most reliable approach across:
  // - iOS Safari (any version since iOS 6)
  // - Android Chrome (Camera or Gallery picker)
  // - Desktop browsers (file chooser to upload an existing video)
  // We deliberately AVOID MediaRecorder because (a) iOS Safari support is patchy until 16+,
  // and (b) the Emergent preview iframe blocks getUserMedia permission prompts.
  const openCameraToRecord = () => {
    if (!videoFileRef.current) return;
    videoFileRef.current.click();
  };
  // Pick an existing video file from the device's library (for evidence already recorded earlier)
  const openVideoLibrary = () => {
    if (!videoLibraryRef.current) return;
    videoLibraryRef.current.click();
  };

  // Native file-input handler — fires when the user finishes recording in iOS/Android camera, or picks a video file
  const onVideoFile = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setRecordedBlob(f);
    setRecordedUrl(URL.createObjectURL(f));
  };

  // Send the recorded video's audio track to /api/video/analyze.
  // Browsers can't strip audio cheaply, so we send the whole file — backend extracts via Whisper.
  const analyzeVideo = async () => {
    if (!recordedBlob) return;
    setBusy(true);
    try {
      // Optional GPS stamp
      let loc = null;
      if (localStorage.getItem("aa_locstamp") === "1" && navigator.geolocation) {
        try {
          loc = await new Promise((resolve) =>
            navigator.geolocation.getCurrentPosition(
              (p) => resolve(`${p.coords.latitude.toFixed(5)},${p.coords.longitude.toFixed(5)}`),
              () => resolve(null),
              { timeout: 4000 }));
        } catch {}
      }
      const fd = new FormData();
      fd.append("audio", recordedBlob, recordedBlob.name || `video-${Date.now()}.mp4`);
      fd.append("language", lang);
      fd.append("country", country);
      if (loc) fd.append("location", loc);
      const { data } = await api.post("/video/analyze", fd);
      setVideoResult(data);
    } catch (e) {
      alert(e?.response?.data?.detail || e.message || "Analysis failed");
    } finally {
      setBusy(false);
    }
  };

  const resetVideo = () => {
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    setRecordedBlob(null); setRecordedUrl(null); setVideoResult(null);
  };

  useEffect(() => {
    return () => {
      if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    };
  // eslint-disable-next-line
  }, []);

  const addFiles = (fileList) => {
    const arr = Array.from(fileList || []).slice(0, 10 - files.length); // max 10
    const next = arr.map(f => ({ file: f, preview: f.type?.startsWith("image/") ? URL.createObjectURL(f) : null, id: `${f.name}_${f.size}_${Date.now()}_${Math.random()}` }));
    setFiles(prev => [...prev, ...next]);
  };
  const onFile = (e) => { addFiles(e.target.files); e.target.value = ""; };
  const removeFile = (id) => setFiles(prev => prev.filter(f => f.id !== id));

  const submit = async () => {
    if (files.length === 0) return;
    setBusy(true);
    const out = [];
    for (const f of files) {
      try {
        const fd = new FormData();
        fd.append("file", f.file);
        fd.append("evidence_type", evidenceType);
        fd.append("description", description);
        fd.append("language", lang);
        fd.append("country", country);
        const { data } = await api.post("/evidence/analyze", fd);
        out.push(data);
      } catch (e) {
        out.push({ filename: f.file.name, analysis: `Error analysing this file: ${e?.response?.data?.detail || e.message}` });
      }
    }
    setResults(out);
    setBusy(false);
  };

  const types = [
    { v: "auto", k: "evidenceTypeAuto" },
    { v: "contract", k: "evidenceTypeContract" },
    { v: "parking_ticket", k: "evidenceTypeTicket" },
    { v: "scene", k: "evidenceTypeScene" },
    { v: "document", k: "evidenceTypeDocument" },
    { v: "signage", k: "evidenceTypeSignage" },
  ];

  return (
    <div className="modal-bg" data-testid="evidence-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "snapEvidence")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        {results.length === 0 && !videoResult && !recordedUrl ? (
          <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
              <button data-testid="evidence-camera-btn" onClick={() => cameraRef.current?.click()}
                style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 18, color: "var(--gold)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <Camera size={28} /><span style={{ fontSize: 12, color: "var(--text)" }}>{t(lang, "takePhoto")}</span>
              </button>
              <button data-testid="evidence-library-btn" onClick={() => libraryRef.current?.click()}
                style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 18, color: "var(--gold)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <ImageIcon size={28} /><span style={{ fontSize: 12, color: "var(--text)" }}>{t(lang, "addMultiplePhotos")}</span>
              </button>
              <button data-testid="evidence-record-video-btn" onClick={openCameraToRecord}
                style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 16, color: "var(--gold)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <Video size={26} /><span style={{ fontSize: 12, color: "var(--text)" }}>{t(lang, "recordVideo")}</span>
              </button>
              <button data-testid="evidence-video-library-btn" onClick={openVideoLibrary}
                style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 16, color: "var(--gold)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <Folder size={26} /><span style={{ fontSize: 12, color: "var(--text)" }}>{t(lang, "pickVideo")}</span>
              </button>
              <input ref={cameraRef} data-testid="evidence-camera-input" type="file" accept="image/*" capture="environment" onChange={onFile} style={{ display: "none" }} />
              <input ref={libraryRef} data-testid="evidence-library-input" type="file" accept="image/*,.pdf,.docx" multiple onChange={onFile} style={{ display: "none" }} />
              <input ref={videoFileRef} data-testid="evidence-video-input" type="file" accept="video/*" capture="environment" onChange={onVideoFile} style={{ display: "none" }} />
              <input ref={videoLibraryRef} data-testid="evidence-video-library-input" type="file" accept="video/*" onChange={onVideoFile} style={{ display: "none" }} />
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 14, padding: "0 4px", lineHeight: 1.5 }}>
              {t(lang, "videoLegalNote")}
            </div>

            {files.length > 0 && (
              <>
                <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>{t(lang, "filesSelectedMax", { n: files.length })}</div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 14 }}>
                  {files.map(f => (
                    <div key={f.id} style={{ position: "relative", borderRadius: 10, overflow: "hidden", border: "1px solid var(--line)", aspectRatio: "1 / 1", background: "#0a0a0a" }}>
                      {f.preview ? (
                        <img src={f.preview} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      ) : (
                        <div style={{ padding: 10, fontSize: 10, color: "var(--text-dim)", display: "flex", alignItems: "center", justifyContent: "center", height: "100%", textAlign: "center", wordBreak: "break-all" }}>{f.file.name}</div>
                      )}
                      <button onClick={() => removeFile(f.id)} data-testid={`remove-file-${f.id.slice(0,12)}`}
                        style={{ position: "absolute", top: 4, right: 4, background: "rgba(0,0,0,0.8)", border: "1px solid var(--line)", color: "var(--text)", borderRadius: "50%", width: 24, height: 24, cursor: "pointer", padding: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
                  {types.map(typ => (
                    <button key={typ.v} data-testid={`evtype-${typ.v}`} onClick={() => setEvidenceType(typ.v)}
                      style={{
                        padding: "6px 12px", borderRadius: 16, fontSize: 12, cursor: "pointer",
                        background: evidenceType === typ.v ? "var(--gold)" : "transparent",
                        color: evidenceType === typ.v ? "#1a1300" : "var(--gold)",
                        border: "1px solid var(--gold-deep)",
                      }}>{t(lang, typ.k)}</button>
                  ))}
                </div>
                <textarea className="input" data-testid="evidence-note" rows={3} placeholder={t(lang, "addNote")}
                  value={description} onChange={(e) => setDescription(e.target.value)} />
                <button className="btn-gold w-full" data-testid="evidence-analyze-btn" disabled={busy} onClick={submit} style={{ marginTop: 12 }}>
                  {busy ? <span className="spinner" /> : t(lang, "analyseNFiles", { n: files.length })}
                </button>
              </>
            )}
          </div>
        ) : recordedUrl && !videoResult ? (
          <div data-testid="video-preview" style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
            <video src={recordedUrl} controls playsInline data-testid="video-preview-player"
                   style={{ width: "100%", borderRadius: 12, marginBottom: 12, maxHeight: "40vh", background: "#000" }} />
            <div className="flex gap-2" style={{ marginBottom: 10 }}>
              <button className="btn-gold" disabled={busy} onClick={analyzeVideo} data-testid="analyze-video-btn" style={{ flex: 2, padding: 14 }}>
                {busy ? <span className="spinner" /> : `🧠 ${t(lang, "analyseNFiles", { n: 1 })}`}
              </button>
              <button className="btn-ghost" onClick={resetVideo} data-testid="discard-video-btn" style={{ flex: 1, padding: 14 }}>
                {t(lang, "cancel")}
              </button>
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5, padding: "0 4px" }}>
              {t(lang, "videoLegalNote")}
            </div>
          </div>
        ) : videoResult ? (
          <div data-testid="video-result" style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
            <h3 className="gold" style={{ fontSize: 16, marginBottom: 10 }}>🎥 {t(lang, "videoEvidenceTitle")}</h3>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 10 }}>
              {t(lang, "evidenceHash")}: <code style={{ background: "#0a0a0a", padding: "2px 6px", borderRadius: 4 }}>{(videoResult.evidence_hash || "").slice(0, 24)}…</code>
            </div>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6, fontSize: 13 }}>{t(lang, "transcript")}</div>
            <div style={{ background: "#0a0a0a", padding: 10, borderRadius: 8, color: "var(--text-dim)", fontSize: 12, lineHeight: 1.5, marginBottom: 14, maxHeight: 200, overflowY: "auto", whiteSpace: "pre-wrap" }}>
              {videoResult.transcript}
            </div>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6, fontSize: 13 }}>{t(lang, "lexAnalysis")}</div>
            <div style={{ background: "#0a0a0a", padding: 10, borderRadius: 8, color: "var(--text)", fontSize: 13, lineHeight: 1.55, marginBottom: 14, whiteSpace: "pre-wrap" }}>
              {videoResult.analysis}
            </div>
            <button className="btn-gold w-full" data-testid="record-another-video-btn" onClick={resetVideo}>{t(lang, "recordAnother")}</button>
          </div>
        ) : (
          <div style={{ overflowY: "auto", flex: 1, minHeight: 0 }}>
            {results.map((r, i) => (
              <div key={i} data-testid={`result-${i}`} style={{ marginBottom: 18, paddingBottom: 14, borderBottom: i < results.length - 1 ? "1px solid var(--line)" : "none" }}>
                <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6, fontSize: 13 }}>{r.filename || `File ${i + 1}`}</div>
                <div style={{ whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.55, color: "var(--text-dim)" }}>{r.analysis}</div>
                {r.id && (
                  <button className="btn-ghost" data-testid={`result-pdf-${i}`} onClick={() => pdfForFile(r.id, r.filename || "evidence")} style={{ marginTop: 8, padding: "6px 12px", fontSize: 12 }}>
                    <Download size={12} style={{ display: "inline", marginRight: 4 }} />PDF
                  </button>
                )}
              </div>
            ))}
            <button className="btn-gold w-full" onClick={() => { setResults([]); setFiles([]); setDescription(""); }}>
              {t(lang, "analyseMore")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Find a Lawyer ----------
function LawyersModal({ lang, country, user, onClose, openAdvertise }) {
  const [firms, setFirms] = useState([]);
  const [tab, setTab] = useState("nearby"); // nearby | all
  const [busy, setBusy] = useState(true);
  const [selected, setSelected] = useState(null);
  const [inquiry, setInquiry] = useState({ name: user.full_name || "", email: user.email, phone: "", message: "" });
  const [sent, setSent] = useState(false);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const params = {};
      if (tab === "nearby" && user.location_enabled && user.latitude && user.longitude) {
        params.latitude = user.latitude; params.longitude = user.longitude;
      } else if (tab === "nearby" && country) {
        params.country = country;
      }
      const { data } = await api.get("/lawfirms", { params });
      setFirms(data);
    } catch (e) { /* ignore */ }
    finally { setBusy(false); }
  }, [tab, user.latitude, user.longitude, user.location_enabled, country]);

  useEffect(() => { load(); }, [load]);

  const sendInquiry = async () => {
    try {
      await api.post("/lawfirms/inquiry", { firm_id: selected.id, ...inquiry });
      setSent(true);
    } catch (e) { alert(e?.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="modal-bg" data-testid="lawyers-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "findLawyer")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>

        {!selected ? (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 12 }}>{t(lang, "seekAdvice")}</p>
            <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
              <button data-testid="tab-nearby" onClick={() => setTab("nearby")}
                style={{ flex: 1, padding: "8px 12px", borderRadius: 10, cursor: "pointer",
                  background: tab === "nearby" ? "var(--gold)" : "transparent",
                  color: tab === "nearby" ? "#1a1300" : "var(--gold)", border: "1px solid var(--gold-deep)" }}>
                {t(lang, "nearbyLawyers")}
              </button>
              <button data-testid="tab-all" onClick={() => setTab("all")}
                style={{ flex: 1, padding: "8px 12px", borderRadius: 10, cursor: "pointer",
                  background: tab === "all" ? "var(--gold)" : "transparent",
                  color: tab === "all" ? "#1a1300" : "var(--gold)", border: "1px solid var(--gold-deep)" }}>
                {t(lang, "allFirms")}
              </button>
            </div>

            {tab === "nearby" && !user.location_enabled && (
              <div className="trial-banner" style={{ marginBottom: 12, fontSize: 13 }}>
                {t(lang, "enableLocation")}
              </div>
            )}

            <div style={{ overflowY: "auto", flex: 1 }}>
              {busy && <div style={{ textAlign: "center", padding: 24 }}><span className="spinner" /></div>}
              {!busy && firms.length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 20 }}>{t(lang, "noFirmsFound")}</p>}
              {firms.map(f => (
                <button key={f.id} data-testid={`firm-${f.id}`} onClick={() => { setSelected(f); setSent(false); }} className="w-full"
                  style={{ background: "var(--bg-card)", border: f.sponsored ? "1px solid var(--gold)" : "1px solid var(--line)", borderRadius: 12, padding: 14, marginBottom: 10, color: "var(--text)", textAlign: "left", cursor: "pointer", position: "relative" }}>
                  {f.sponsored && (
                    <span style={{ position: "absolute", top: -8, right: 12, background: "var(--gold)", color: "#1a1300", fontSize: 10, padding: "2px 8px", borderRadius: 6, fontWeight: 600 }}>
                      {t(lang, "sponsored")}
                    </span>
                  )}
                  <div style={{ color: "var(--gold)", fontWeight: 600, fontSize: 15 }}>{f.name}</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                    <MapPin size={12} style={{ display: "inline", marginRight: 4 }} />
                    {f.city}, {f.country}{f.distance_km != null ? ` · ${t(lang, "distanceAway", { n: f.distance_km })}` : ""}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 6 }}>
                    {(f.specialties || []).slice(0, 3).join(" · ")}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 6 }}>
                    <Star size={12} style={{ color: "var(--gold)" }} fill="currentColor" />
                    <span style={{ fontSize: 12, color: "var(--gold-soft)" }}>{f.rating?.toFixed(1) || "—"}</span>
                  </div>
                </button>
              ))}
            </div>

            <button className="btn-ghost w-full" data-testid="advertise-btn" onClick={openAdvertise} style={{ marginTop: 10 }}>
              <Building2 size={16} style={{ display: "inline", marginRight: 6 }} />
              {t(lang, "listLawFirm")}
            </button>
          </>
        ) : sent ? (
          <div style={{ textAlign: "center", padding: 30 }}>
            <Check size={48} style={{ color: "var(--gold)" }} />
            <h3 style={{ color: "var(--gold)", marginTop: 12 }}>{t(lang, "messageSent")}</h3>
            <p style={{ color: "var(--text-dim)", fontSize: 14 }}>{selected.name} will get back to you soon.</p>
            <button className="btn-ghost w-full" onClick={() => { setSelected(null); setSent(false); }} style={{ marginTop: 16 }}>{t(lang, "backToList")}</button>
          </div>
        ) : (
          <div style={{ overflowY: "auto" }}>
            <button className="btn-ghost" data-testid="back-firms" onClick={() => setSelected(null)} style={{ marginBottom: 12, padding: "6px 12px" }}>
              <ArrowLeft size={14} style={{ display: "inline" }} /> Back
            </button>
            <h3 style={{ color: "var(--gold)" }}>{selected.name}</h3>
            <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 8 }}>{selected.address}</div>
            <p style={{ color: "var(--text-dim)", fontSize: 14 }}>{selected.description}</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
              {(selected.specialties || []).map(s => (
                <span key={s} style={{ fontSize: 11, padding: "3px 9px", borderRadius: 12, background: "rgba(247,201,72,0.1)", color: "var(--gold)", border: "1px solid var(--gold-deep)" }}>{s}</span>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <a href={`tel:${selected.phone}`} className="btn-ghost" style={{ flex: 1, textAlign: "center", textDecoration: "none", padding: "10px 12px" }}>
                <Phone size={14} style={{ display: "inline", marginRight: 4 }} />{t(lang, "call")}
              </a>
              <a href={selected.website} target="_blank" rel="noreferrer" className="btn-ghost" style={{ flex: 1, textAlign: "center", textDecoration: "none", padding: "10px 12px" }}>
                <ExternalLink size={14} style={{ display: "inline", marginRight: 4 }} />{t(lang, "visit")}
              </a>
            </div>
            <h4 style={{ color: "var(--gold)", marginTop: 18 }}>{t(lang, "inquireTitle")}</h4>
            <input className="input" data-testid="inq-name" value={inquiry.name} onChange={(e) => setInquiry({ ...inquiry, name: e.target.value })} placeholder={t(lang, "name")} style={{ marginBottom: 8 }} />
            <input className="input" data-testid="inq-email" value={inquiry.email} onChange={(e) => setInquiry({ ...inquiry, email: e.target.value })} placeholder={t(lang, "email")} style={{ marginBottom: 8 }} />
            <input className="input" data-testid="inq-phone" value={inquiry.phone} onChange={(e) => setInquiry({ ...inquiry, phone: e.target.value })} placeholder={t(lang, "phoneOptional")} style={{ marginBottom: 8 }} />
            <textarea className="input" data-testid="inq-message" rows={3} value={inquiry.message} onChange={(e) => setInquiry({ ...inquiry, message: e.target.value })} placeholder={t(lang, "yourMessage")} />
            <button className="btn-gold w-full" data-testid="send-inquiry-btn" onClick={sendInquiry} disabled={!inquiry.name || !inquiry.email || !inquiry.message} style={{ marginTop: 10 }}>
              {t(lang, "sendInquiry")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Advertise (Law firm signup) ----------
function AdvertiseModal({ lang, onClose }) {
  const [form, setForm] = useState({ firm_name: "", contact_name: "", email: "", phone: "", country: "GB", city: "", specialties: "", website: "", notes: "" });
  const [busy, setBusy] = useState(false); const [done, setDone] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await api.post("/lawfirms/advertise", { ...form, specialties: form.specialties.split(",").map(s => s.trim()).filter(Boolean) });
      setDone(true);
    } catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-bg" data-testid="advertise-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "advertiseTitle")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        {done ? (
          <div style={{ textAlign: "center", padding: 30 }}>
            <Check size={48} style={{ color: "var(--gold)" }} />
            <h3 style={{ color: "var(--gold)", marginTop: 12 }}>{t(lang, "appReceived")}</h3>
          </div>
        ) : (
          <div style={{ overflowY: "auto" }}>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 12 }}>{t(lang, "advertiseSubtitle")}</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 8, marginBottom: 14 }}>
              <div style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 12, padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                  <span style={{ color: "var(--gold)", fontSize: 13, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase" }}>Featured</span>
                  <span style={{ color: "var(--text)", fontSize: 18, fontWeight: 700 }}>£49<span style={{ fontSize: 11, color: "var(--text-muted)" }}>/mo</span></span>
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: 11, lineHeight: 1.5 }}>Directory listing · Top of search · Sponsored badge · Direct client enquiries</div>
              </div>
              <div style={{ background: "linear-gradient(135deg, rgba(247,201,72,0.12), rgba(247,201,72,0.02))", border: "1px solid var(--gold)", borderRadius: 12, padding: 12, position: "relative" }}>
                <div style={{ position: "absolute", top: -8, right: 12, background: "var(--gold)", color: "#1a1300", fontSize: 9, padding: "2px 8px", borderRadius: 6, fontWeight: 700, letterSpacing: "0.05em" }}>MOST POPULAR</div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                  <span style={{ color: "var(--gold)", fontSize: 13, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase" }}>Premium</span>
                  <span style={{ color: "var(--text)", fontSize: 18, fontWeight: 700 }}>£199<span style={{ fontSize: 11, color: "var(--text-muted)" }}>/mo</span></span>
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: 11, lineHeight: 1.5 }}>Everything in Featured · Verified badge · <strong style={{ color: "var(--gold)" }}>Secure client portal (25 engagements)</strong> · 100 Lex AI assists/mo</div>
              </div>
              <div style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 12, padding: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
                  <span style={{ color: "var(--gold)", fontSize: 13, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase" }}>Practice</span>
                  <span style={{ color: "var(--text)", fontSize: 18, fontWeight: 700 }}>£399<span style={{ fontSize: 11, color: "var(--text-muted)" }}>/mo</span></span>
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: 11, lineHeight: 1.5 }}>Everything in Premium · <strong style={{ color: "var(--gold)" }}>Unlimited engagements</strong> · 5 lawyer seats · 1,000 Lex AI assists/mo · Priority support</div>
              </div>
            </div>
            <a href="/firm-portal" data-testid="adv-firm-portal-link" target="_blank" rel="noreferrer"
               style={{ display: "block", textAlign: "center", padding: "10px", background: "rgba(247,201,72,0.08)", border: "1px solid var(--gold-deep)", borderRadius: 10, color: "var(--gold)", fontSize: 12, fontWeight: 600, marginBottom: 14, textDecoration: "none" }}>
              Already a customer? Sign in to the Firm Portal →
            </a>
            <input className="input" data-testid="adv-firm" placeholder={t(lang, "firmName")} value={form.firm_name} onChange={(e) => setForm({ ...form, firm_name: e.target.value })} style={{ marginBottom: 8 }} />
            <input className="input" data-testid="adv-contact" placeholder={t(lang, "contactName")} value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} style={{ marginBottom: 8 }} />
            <input className="input" data-testid="adv-email" type="email" placeholder={t(lang, "email")} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} style={{ marginBottom: 8 }} />
            <input className="input" data-testid="adv-phone" placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} style={{ marginBottom: 8 }} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 8 }}>
              <select className="input" data-testid="adv-country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })}>
                {COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.name}</option>)}
              </select>
              <input className="input" data-testid="adv-city" placeholder="City" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
            </div>
            <input className="input" data-testid="adv-spec" placeholder="Specialties (comma-separated, e.g. employment, property)" value={form.specialties} onChange={(e) => setForm({ ...form, specialties: e.target.value })} style={{ marginBottom: 8 }} />
            <input className="input" data-testid="adv-website" placeholder="Website" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} style={{ marginBottom: 8 }} />
            <textarea className="input" data-testid="adv-notes" rows={3} placeholder="Tell us about your firm" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            <button className="btn-gold w-full" data-testid="adv-submit-btn" disabled={busy || !form.firm_name || !form.email || !form.contact_name} onClick={submit} style={{ marginTop: 12 }}>
              {busy ? <span className="spinner" /> : t(lang, "apply")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Settings ----------
function SettingsModal({ lang, country, user, onClose, onUpdate, setLang, setCountry }) {
  const [busy, setBusy] = useState(false);
  const [locOn, setLocOn] = useState(!!user.location_enabled);
  // Proper React state for each Settings toggle — fixes stale-localStorage render bug
  const [wakeOn, setWakeOn] = useState(localStorage.getItem("aa_wake") === "1");
  const [autoDetectOn, setAutoDetectOn] = useState(localStorage.getItem("aa_autodetect") !== "0");
  const [locStampOn, setLocStampOn] = useState(localStorage.getItem("aa_locstamp") === "1");
  const [smartLocOn, setSmartLocOn] = useState(localStorage.getItem("aa_loc_safety") !== "0");
  const [legalDoc, setLegalDoc] = useState(null);   // "tos" | "privacy" | null
  const [showManage, setShowManage] = useState(false);

  const toggleLocation = async () => {
    if (!locOn) {
      // Turn ON — request geolocation
      if (!navigator.geolocation) { alert(t(lang, "geolocationNotSupported")); return; }
      setBusy(true);
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const { data } = await api.patch("/auth/preferences", {
              location_enabled: true,
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
            });
            onUpdate(data); setLocOn(true);
          } catch (e) { alert(t(lang, "failedToSave")); }
          finally { setBusy(false); }
        },
        (err) => { setBusy(false); alert(t(lang, "locationBlocked")); },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    } else {
      setBusy(true);
      try {
        const { data } = await api.patch("/auth/preferences", { location_enabled: false });
        onUpdate(data); setLocOn(false);
      } catch (e) { alert(t(lang, "failed")); }
      finally { setBusy(false); }
    }
  };

  const setCountryAndSave = async (c) => {
    setCountry(c);
    try { const { data } = await api.patch("/auth/preferences", { country: c }); onUpdate(data); }
    catch {}
  };

  return (
    <>
    <div className="modal-bg" data-testid="settings-modal">
      <div className="modal-card" style={{ padding: 22, display: "flex", flexDirection: "column" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 18, flexShrink: 0 }}>
          <h2 className="brand-font gold" style={{ fontSize: 22 }}>{t(lang, "settings")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>
        <div style={{ flex: 1, overflowY: "auto" }}>
        {/* Subscription */}
        <div data-testid="settings-subscription" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <Star size={18} style={{ color: "var(--gold)" }} fill="currentColor" />
            <span style={{ fontWeight: 600 }}>{t(lang, "subscription")}</span>
          </div>
          <div style={{ fontSize: 13, color: "var(--text-dim)" }}>
            {t(lang, "currentPlan")}: <strong style={{ color: "var(--gold)" }}>{(user.tier || "free").toUpperCase()}</strong>
            {user.subscription_status === "active" && <span style={{ marginLeft: 8, fontSize: 11, color: "#16a34a" }}>● {t(lang, "active")}</span>}
            {user.subscription_status === "past_due" && <span style={{ marginLeft: 8, fontSize: 11, color: "#dc2626" }}>● {t(lang, "pastDue")}</span>}
            {user.tier === "trial_pro" && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--gold)" }}>{t(lang, "trialLeft", { n: user.trial_days_remaining })}</span>}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            {!IS_NATIVE && (
              <button className="btn-gold" data-testid="settings-upgrade-btn"
                onClick={() => { onClose(); window.dispatchEvent(new CustomEvent("aa:open-subscribe", { detail: { preset: "pro" } })); }}
                style={{ flex: 1, padding: "8px 12px", fontSize: 13 }}>
                {user.tier === "free" ? t(lang, "upgrade") : t(lang, "changePlan")}
              </button>
            )}
            {IS_NATIVE && (
              <a href="https://aiadvocate.co.uk/subscribe" data-testid="settings-upgrade-web-link"
                 style={{ flex: 1, padding: "8px 12px", fontSize: 12, background: "var(--bg-card)", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 10, textAlign: "center", textDecoration: "none" }}>
                {t(lang, "manageOnWeb")}
              </a>
            )}
            {user.stripe_customer_id && !IS_NATIVE && (
              <button className="btn-ghost" data-testid="settings-portal-btn"
                onClick={async () => { try { const { data } = await api.post("/subscription/portal"); window.location.href = data.portal_url; } catch (e) { alert(e?.response?.data?.detail || t(lang, "failed")); } }}
                style={{ flex: 1, padding: "8px 12px", fontSize: 13 }}>
                {t(lang, "manageBilling")}
              </button>
            )}
          </div>
        </div>

        {/* Location */}
        <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <MapPin size={18} style={{ color: "var(--gold)" }} />
                <span style={{ fontWeight: 500 }}>{t(lang, "locationServices")}</span>
              </div>
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                {locOn ? t(lang, "locationOn") : t(lang, "locationOff")}
              </div>
            </div>
            <button data-testid="loc-toggle" onClick={toggleLocation} disabled={busy}
              style={{ width: 50, height: 28, borderRadius: 14, border: "none", cursor: "pointer",
                background: locOn ? "var(--gold)" : "#333", position: "relative", transition: "background 200ms" }}>
              <span style={{ position: "absolute", top: 3, left: locOn ? 25 : 3, width: 22, height: 22, borderRadius: "50%", background: "#fff", transition: "left 200ms" }} />
            </button>
          </div>
          {!locOn && (
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>
              {t(lang, "enableLocation")}
            </div>
          )}
        </div>

        {/* Country */}
        <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>{t(lang, "country")}</div>
          <select className="input" data-testid="settings-country" value={country} onChange={(e) => setCountryAndSave(e.target.value)}>
            {COUNTRIES.map(c => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
            {t(lang, "countryLawApplied")}
          </div>
        </div>

        {/* "Hey Lex" wake word toggle — hidden pre-launch.
            Re-enable when SiriKit Shortcuts arrive in the Capacitor iOS wrap. */}
        {false && (
        <div data-testid="settings-heylex" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Mic size={18} style={{ color: "var(--gold)" }} />
              <span style={{ fontWeight: 600 }}>{t(lang, "heyLexWake")}</span>
            </div>
            <label style={{ position: "relative", display: "inline-block", width: 48, height: 26, cursor: "pointer" }}>
              <input type="checkbox" data-testid="heylex-toggle" checked={wakeOn}
                onChange={async (e) => {
                  const v = e.target.checked;
                  if (v) {
                    try {
                      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                      stream.getTracks().forEach(tr => tr.stop());
                    } catch (err) {
                      alert(t(lang, "micPermDenied"));
                      return;
                    }
                  }
                  setWakeOn(v);
                  localStorage.setItem("aa_wake", v ? "1" : "0");
                  window.dispatchEvent(new CustomEvent("aa:wake-toggle", { detail: { enabled: v } }));
                }}
                style={{ opacity: 0, width: 0, height: 0 }} />
              <span style={{ position: "absolute", inset: 0, background: wakeOn ? "var(--gold)" : "var(--line)",
                             borderRadius: 13, transition: "0.2s" }}>
                <span style={{ position: "absolute", height: 20, width: 20, left: wakeOn ? 25 : 3, top: 3,
                               background: "#000", borderRadius: "50%", transition: "0.2s" }} />
              </span>
            </label>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5 }}>
            {t(lang, "heyLexDesc")}
            <br/><strong style={{ color: "var(--gold-soft)" }}>{t(lang, "heyLexIosNote")}</strong>
          </div>
        </div>
        )}

        {/* Customise Quick Nav — first bottom-nav slot is user-pickable */}
        <div data-testid="settings-nav-slot1" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <SettingsIcon size={18} style={{ color: "var(--gold)" }} />
            <span style={{ fontWeight: 600 }}>Customise quick nav</span>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 10 }}>
            Choose which shortcut sits next to Lex in the bottom bar.
          </div>
          <NavSlotPicker lang={lang} />
        </div>

        {/* Microphone Access — explicit opt-in, replaces the implicit startup prompt */}
        <div data-testid="settings-mic-access" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Mic size={18} style={{ color: "var(--gold)" }} />
            <span style={{ fontWeight: 600 }}>Microphone access</span>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 10 }}>
            Lex uses your microphone for voice questions, the Hearing Recorder, and live transcription. Tap below to grant or test access.
          </div>
          <MicAccessButton />
        </div>

        {/* 🚨 Emergency Contacts + Lawyer Standby + Watch SOS — life-safety section */}
        <EmergencyContactsCard lang={lang} user={user} />

        {/* 🎁 OWNER ONLY — comp Pro access for family / friends / customer service */}
        {user?.is_owner && <CompProAdminCard lang={lang} />}
        {/* 🏛 OWNER ONLY — comp tier access for law firms (founding-firm cohort) */}
        {user?.is_owner && <CompFirmAdminCard lang={lang} />}

        {/* Auto-detect language toggle */}
        <div data-testid="settings-autodetect" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Languages size={18} style={{ color: "var(--gold)" }} />
              <span style={{ fontWeight: 600 }}>{t(lang, "autoDetectLang")}</span>
            </div>
            <label style={{ position: "relative", display: "inline-block", width: 48, height: 26, cursor: "pointer" }}>
              <input type="checkbox" data-testid="autodetect-toggle" checked={autoDetectOn}
                onChange={(e) => { setAutoDetectOn(e.target.checked); localStorage.setItem("aa_autodetect", e.target.checked ? "1" : "0"); }}
                style={{ opacity: 0, width: 0, height: 0 }} />
              <span style={{ position: "absolute", inset: 0, background: autoDetectOn ? "var(--gold)" : "var(--line)",
                             borderRadius: 13, transition: "0.2s" }}>
                <span style={{ position: "absolute", height: 20, width: 20, left: autoDetectOn ? 25 : 3, top: 3,
                               background: "#000", borderRadius: "50%", transition: "0.2s" }} />
              </span>
            </label>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5 }}>
            {t(lang, "autoDetectDesc")}
          </div>
        </div>

        {/* Location stamping toggle for evidence */}
        <div data-testid="settings-location-stamp" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <MapPin size={18} style={{ color: "var(--gold)" }} />
              <span style={{ fontWeight: 600 }}>{t(lang, "locationStamp")}</span>
            </div>
            <label style={{ position: "relative", display: "inline-block", width: 48, height: 26, cursor: "pointer" }}>
              <input type="checkbox" data-testid="locstamp-toggle" checked={locStampOn}
                onChange={(e) => { setLocStampOn(e.target.checked); localStorage.setItem("aa_locstamp", e.target.checked ? "1" : "0"); }}
                style={{ opacity: 0, width: 0, height: 0 }} />
              <span style={{ position: "absolute", inset: 0, background: locStampOn ? "var(--gold)" : "var(--line)",
                             borderRadius: 13, transition: "0.2s" }}>
                <span style={{ position: "absolute", height: 20, width: 20, left: locStampOn ? 25 : 3, top: 3,
                               background: "#000", borderRadius: "50%", transition: "0.2s" }} />
              </span>
            </label>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5 }}>
            {t(lang, "locationStampDesc")}
          </div>
        </div>

        {/* Cloud Backup — Plus+ data export */}
        <div data-testid="settings-cloud-backup" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Folder size={18} style={{ color: "var(--gold)" }} />
            <span style={{ fontWeight: 600 }}>{t(lang, "cloudBackup")}</span>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 10 }}>
            {t(lang, "cloudBackupDesc")}
          </div>
          <button data-testid="export-backup-btn" className="btn-ghost" style={{ width: "100%", padding: "10px", fontSize: 13 }}
            onClick={async () => {
              try {
                const r = await api.get("/backup/export", { responseType: "blob" });
                const url = URL.createObjectURL(r.data);
                const a = document.createElement("a"); a.href = url; a.download = `ai-advocate-backup-${Date.now()}.json`; a.click();
                URL.revokeObjectURL(url);
              } catch (e) {
                alert(e?.response?.data?.detail || t(lang, "failed"));
              }
            }}>
            📥 {t(lang, "downloadBackup")}
          </button>
        </div>

        {/* Contact & Support */}
        <div data-testid="settings-contact" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <MessageCircle size={18} style={{ color: "var(--gold)" }} />
            <span style={{ fontWeight: 600 }}>{t(lang, "contactSupport")}</span>
          </div>
          {[
            { label: t(lang, "customerSupport"), email: "support@aiadvocate.co.uk" },
            { label: t(lang, "businessPartnerships"), email: "admin@aiadvocate.co.uk" },
            { label: t(lang, "pressEnquiries"), email: "press@aiadvocate.co.uk" },
            { label: t(lang, "generalInfo"), email: "info@aiadvocate.co.uk" },
          ].map(c => (
            <a key={c.email} href={`mailto:${c.email}`} data-testid={`contact-${c.email.split("@")[0]}`}
              style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--line)",
                       textDecoration: "none", color: "var(--text)" }}>
              <span style={{ fontSize: 13 }}>{c.label}</span>
              <span style={{ fontSize: 12, color: "var(--gold)" }}>{c.email}</span>
            </a>
          ))}
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8 }}>
            {t(lang, "replyWithin24h")}
          </div>
        </div>

        {/* Rate us on Trustpilot */}
        <a href="https://www.trustpilot.com/review/aiadvocate.co.uk" target="_blank" rel="noreferrer" data-testid="settings-trustpilot"
          style={{ display: "block", textAlign: "center", padding: "10px 12px", background: "var(--bg-card)",
                   border: "1px solid var(--gold-deep)", borderRadius: 12, color: "var(--gold)",
                   textDecoration: "none", fontSize: 13, marginBottom: 12 }}>
          ⭐ {t(lang, "rateOnTrustpilot")}
        </a>

        {/* Smart location safety toggle */}
        <div data-testid="loc-safety-row" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, padding: 12, marginBottom: 10, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ flex: 1, paddingRight: 10 }}>
            <div style={{ fontSize: 13, color: "var(--text)", fontWeight: 600 }}>{t(lang, "locSafetyTitle")}</div>
            <div style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 3 }}>{t(lang, "locSafetyBody")}</div>
          </div>
          <button onClick={() => { const next = !smartLocOn; setSmartLocOn(next); localStorage.setItem("aa_loc_safety", next ? "1" : "0"); }}
                  data-testid="loc-safety-toggle"
                  style={{ width: 44, height: 24, borderRadius: 12, background: smartLocOn ? "var(--gold)" : "var(--line)", border: "none", cursor: "pointer", position: "relative" }}>
            <span style={{ position: "absolute", top: 2, left: smartLocOn ? 22 : 2, width: 20, height: 20, borderRadius: 10, background: "#fff", transition: "left 0.18s ease" }}></span>
          </button>
        </div>

        {/* Legal & data section */}
        <div data-testid="legal-section" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, padding: 10, marginBottom: 12 }}>
          <div style={{ color: "var(--gold)", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8, paddingLeft: 4 }}>
            {t(lang, "legalAndData")}
          </div>
          <button onClick={() => setLegalDoc("tos")} data-testid="open-tos" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "10px 12px", background: "transparent", border: "none", color: "var(--text)", fontSize: 13, cursor: "pointer", borderRadius: 8 }}>
            <span>📜 {t(lang, "tosTitle")}</span> <ExternalLink size={14} style={{ color: "var(--text-dim)" }} />
          </button>
          <button onClick={() => setLegalDoc("privacy")} data-testid="open-privacy" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "10px 12px", background: "transparent", border: "none", color: "var(--text)", fontSize: 13, cursor: "pointer", borderRadius: 8 }}>
            <span>🔒 {t(lang, "privacyTitle")}</span> <ExternalLink size={14} style={{ color: "var(--text-dim)" }} />
          </button>
          <button onClick={() => setShowManage(true)} data-testid="open-manage-data" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "10px 12px", background: "transparent", border: "none", color: "var(--text)", fontSize: 13, cursor: "pointer", borderRadius: 8 }}>
            <span>🗂️ {t(lang, "manageDataTitle")}</span> <ExternalLink size={14} style={{ color: "var(--text-dim)" }} />
          </button>
          {/* App Store 5.1.1(v) — clear in-app account deletion entry */}
          <button onClick={() => setShowManage(true)} data-testid="open-delete-account"
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "10px 12px", background: "transparent", border: "none", color: "#fca5a5", fontSize: 13, cursor: "pointer", borderRadius: 8, marginTop: 4 }}>
            <span>🗑️ {t(lang, "deleteAccountSettings")}</span> <ExternalLink size={14} style={{ color: "#fca5a5" }} />
          </button>
        </div>
        </div>
      </div>
    </div>
    {legalDoc && <LegalDocModal kind={legalDoc} lang={lang} onClose={() => setLegalDoc(null)} />}
    {showManage && <ManageDataModal lang={lang} onClose={() => setShowManage(false)} onAccountDeleted={() => { setShowManage(false); window.location.reload(); }} />}
    </>
  );
}


// ---------- Subscribe Modal ----------
function SubscribeModal({ lang, user, onClose, onActivated, presetPlan }) {
  const [busy, setBusy] = useState(false);
  const [tiers, setTiers] = useState([]);
  const [picked, setPicked] = useState(presetPlan || "plus");
  // Tabs: "subs" (recurring subscriptions) vs "topups" (one-time packs)
  // Top-ups are hidden on native iOS to comply with Apple's Reader-App rules.
  const [tab, setTab] = useState("subs");
  const [topups, setTopups] = useState({ packs: [], active: null, loaded: false });
  const [buyingPack, setBuyingPack] = useState(null);

  useEffect(() => { api.get("/subscription/tiers").then(r => setTiers(r.data.tiers)).catch(() => {}); }, []);

  // Lazy-fetch top-up packs on first tab switch (also on mount so the badge/active state is fresh)
  useEffect(() => {
    if (IS_NATIVE) return;
    api.get("/topups/packs").then(r => setTopups({ packs: r.data.packs || [], active: r.data.active, loaded: true }))
      .catch(() => setTopups({ packs: [], active: null, loaded: true }));
  }, []);

  const checkout = async (plan) => {
    setBusy(true);
    try {
      const { data } = await api.post("/subscription/checkout", { plan });
      track("subscription_checkout_started", { plan });
      window.location.href = data.checkout_url;
    } catch (e) { alert(e?.response?.data?.detail || "Failed"); setBusy(false); }
  };
  const openPortal = async () => {
    setBusy(true);
    try { const { data } = await api.post("/subscription/portal"); window.location.href = data.portal_url; }
    catch (e) { alert(e?.response?.data?.detail || "Failed"); setBusy(false); }
  };
  const demoActivate = async () => {
    setBusy(true);
    try { const { data } = await api.post(`/subscription/activate-test?plan=${picked}`); onActivated(data); }
    catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };

  const buyTopup = async (pack) => {
    if (!pack.configured) {
      alert("This top-up is coming soon — Stripe price not yet configured.");
      return;
    }
    setBuyingPack(pack.id);
    try {
      const { data } = await api.post("/topups/checkout", { pack_id: pack.id });
      track("topup_checkout_started", { pack: pack.id, price_gbp: pack.price_gbp });
      window.location.href = data.checkout_url;
    } catch (e) {
      alert(e?.response?.data?.detail || "Could not start checkout. Please try again.");
      setBuyingPack(null);
    }
  };

  const onTier = user.tier || "free";
  const isCurrent = (id) => onTier === id || (onTier === "yearly" && id === "yearly")
                              || (onTier === "trial_pro" && id === "pro");

  return (
    <div className="modal-bg" data-testid="subscribe-modal">
      <div className="modal-card" style={{ padding: 18, height: "94vh", display: "flex", flexDirection: "column" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 10, flexShrink: 0 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "chooseYourPlan")}</h2>
          <button onClick={onClose} data-testid="subscribe-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>
        <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12, flexShrink: 0 }}>
          You're on <strong style={{ color: "var(--gold)" }}>{onTier === "trial_pro" ? "Free Trial (Pro features)" : onTier.toUpperCase()}</strong>.
          {onTier !== "free" && onTier !== "trial_pro" && (
            <button onClick={openPortal} data-testid="manage-sub-btn" style={{ marginLeft: 8, background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 14, padding: "3px 10px", fontSize: 11, cursor: "pointer" }}>{t(lang, "manageSubscription")}</button>
          )}
        </div>

        {/* Tab switcher — only show top-ups option on web (Apple Reader-App compliance) */}
        {!IS_NATIVE && (
          <div data-testid="subscribe-tab-switcher" style={{
            display: "flex", gap: 6, background: "var(--bg-card)",
            border: "1px solid var(--line)", borderRadius: 12, padding: 4, marginBottom: 12, flexShrink: 0,
          }}>
            <button data-testid="tab-subs-btn" onClick={() => setTab("subs")}
              style={{
                flex: 1, padding: "8px 10px", fontSize: 12.5, fontWeight: 700, borderRadius: 9,
                border: "none", cursor: "pointer",
                background: tab === "subs" ? "var(--gold)" : "transparent",
                color: tab === "subs" ? "#1a1300" : "var(--text-dim)",
              }}>
              Subscriptions
            </button>
            <button data-testid="tab-topups-btn" onClick={() => setTab("topups")}
              style={{
                flex: 1, padding: "8px 10px", fontSize: 12.5, fontWeight: 700, borderRadius: 9,
                border: "none", cursor: "pointer",
                background: tab === "topups" ? "var(--gold)" : "transparent",
                color: tab === "topups" ? "#1a1300" : "var(--text-dim)",
              }}>
              One-time top-ups
            </button>
          </div>
        )}

        {tab === "topups" && !IS_NATIVE ? (
          <div data-testid="topups-panel" style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
            {topups.active && (
              <div data-testid="topup-active-banner" style={{
                background: "linear-gradient(135deg, rgba(247,201,72,0.20), rgba(247,201,72,0.05))",
                border: "1px solid var(--gold-deep)", borderRadius: 12, padding: "10px 12px",
              }}>
                <div style={{ fontSize: 11, color: "var(--gold)", fontWeight: 800, letterSpacing: "0.05em" }}>
                  ACTIVE TOP-UP
                </div>
                <div style={{ fontSize: 13, color: "#fff", marginTop: 2 }}>
                  {topups.active.label} · grants <strong style={{ color: "var(--gold)" }}>{(topups.active.grants_tier || "plus").toUpperCase()}</strong>
                  {typeof user.topup_active?.hours_remaining === "number" && (
                    <span style={{ color: "var(--text-muted)" }}> · {user.topup_active.hours_remaining}h remaining</span>
                  )}
                </div>
              </div>
            )}
            <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.4 }}>
              Need help right now but don't want to subscribe? Buy a one-off pack. No auto-renew.
            </div>
            {!topups.loaded && <div style={{ textAlign: "center", color: "var(--text-muted)", padding: 20 }}><span className="spinner" /></div>}
            {topups.loaded && topups.packs.map(pack => {
              const isPro = pack.grants_tier === "pro";
              return (
                <div key={pack.id} data-testid={`topup-card-${pack.id}`}
                  style={{
                    background: "var(--bg-card)",
                    border: `2px solid ${isPro ? "var(--gold)" : "var(--line)"}`,
                    borderRadius: 14, padding: 14, position: "relative",
                    opacity: pack.configured ? 1 : 0.55,
                  }}>
                  {isPro && (
                    <div style={{ position: "absolute", top: -10, right: 14, background: "var(--gold)", color: "#1a1300", padding: "2px 10px", fontSize: 10.5, borderRadius: 8, fontWeight: 800 }}>
                      PRO FEATURES
                    </div>
                  )}
                  <div className="flex items-center justify-between">
                    <div style={{ fontSize: 16, color: "var(--gold)", fontWeight: 700, fontFamily: "Cinzel, serif" }}>{pack.label}</div>
                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: 20, color: "var(--gold)", fontWeight: 600 }}>£{pack.price_gbp}</span>
                      <span style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 4 }}>one-off</span>
                    </div>
                  </div>
                  <div style={{ fontSize: 12.5, color: "var(--text-dim)", marginTop: 6, lineHeight: 1.4 }}>
                    {pack.tagline}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                    Valid for {pack.duration_hours >= 24 ? `${Math.round(pack.duration_hours / 24)} day${pack.duration_hours >= 48 ? "s" : ""}` : `${pack.duration_hours}h`} after purchase.
                  </div>
                  <button
                    data-testid={`buy-topup-${pack.id}-btn`}
                    onClick={() => buyTopup(pack)}
                    disabled={buyingPack === pack.id || !pack.configured}
                    className="btn-gold w-full"
                    style={{ marginTop: 10, padding: "8px 12px", fontSize: 13 }}>
                    {buyingPack === pack.id ? <span className="spinner" /> : pack.configured ? `Buy — £${pack.price_gbp}` : "Coming soon"}
                  </button>
                </div>
              );
            })}
            <div style={{ fontSize: 10.5, color: "var(--text-muted)", textAlign: "center", marginTop: 4, lineHeight: 1.4 }}>
              Top-ups stack on top of your current plan. One-off payment — no auto-renew. Powered by Stripe.
            </div>
          </div>
        ) : (
        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
          {tiers.map(t => {
            const selected = picked === t.id;
            const current = isCurrent(t.id);
            return (
              <div key={t.id} data-testid={`tier-card-${t.id}`}
                onClick={() => setPicked(t.id)}
                style={{
                  background: "var(--bg-card)",
                  border: `2px solid ${selected ? "var(--gold)" : t.best_value ? "var(--gold-deep)" : "var(--line)"}`,
                  borderRadius: 16, padding: 14, position: "relative", cursor: "pointer",
                  boxShadow: selected ? "0 0 18px rgba(247,201,72,0.35)" : "none",
                }}>
                {t.best_value && (
                  <div style={{ position: "absolute", top: -10, right: 14, background: "var(--gold)", color: "#1a1300", padding: "2px 10px", fontSize: 11, borderRadius: 8, fontWeight: 700 }}>
                    BEST VALUE · {t.savings_pct}% off
                  </div>
                )}
                {current && (
                  <div style={{ position: "absolute", top: -10, left: 14, background: "#16a34a", color: "#fff", padding: "2px 10px", fontSize: 11, borderRadius: 8, fontWeight: 700 }}>
                    YOUR PLAN
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <div style={{ fontSize: 17, color: "var(--gold)", fontWeight: 700, fontFamily: "Cinzel, serif" }}>{t.name}</div>
                  <div style={{ textAlign: "right" }}>
                    {t.price_gbp === 0 ? (
                      <>
                        <span style={{ fontSize: 22, color: "var(--gold)", fontWeight: 600 }}>£0</span>
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}> /forever</span>
                      </>
                    ) : (
                      <>
                        <span style={{ fontSize: 22, color: "var(--gold)", fontWeight: 600 }}>£{t.price_gbp}</span>
                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>/{t.period === "year" ? "yr" : t.period === "month" ? "mo" : ""}</span>
                      </>
                    )}
                  </div>
                </div>
                <ul style={{ marginTop: 8, paddingLeft: 0, listStyle: "none" }}>
                  {t.highlights.map((h, i) => (
                    <li key={i} style={{ fontSize: 12.5, color: "var(--text-dim)", padding: "3px 0", display: "flex", gap: 8 }}>
                      <Check size={13} style={{ color: "var(--gold)", flexShrink: 0, marginTop: 2 }} />
                      <span>{h}</span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
        )}

        {tab === "subs" && (
        <div style={{ flexShrink: 0, marginTop: 12 }}>
          {picked === "free" ? (
            <button className="btn-ghost w-full" data-testid="stay-free-btn" onClick={onClose}>
              Stay on Free
            </button>
          ) : (
            <button className="btn-gold w-full" data-testid={`checkout-${picked}-btn`} onClick={() => checkout(picked)} disabled={busy}>
              {busy ? <span className="spinner" /> : `Subscribe — £${tiers.find(x => x.id === picked)?.price_gbp || ""}/${tiers.find(x => x.id === picked)?.period === "year" ? "yr" : "mo"}`}
            </button>
          )}
          <button className="btn-ghost w-full" data-testid="demo-activate-btn" onClick={demoActivate} disabled={busy || picked === "free"} style={{ marginTop: 8, fontSize: 12, opacity: 0.7 }}>
            Activate {picked.toUpperCase()} (demo / no payment)
          </button>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8, textAlign: "center" }}>
            Cancel any time. Powered by Stripe. Subscribing on the web saves you the Apple/Google fee.
          </div>
        </div>
        )}
      </div>
    </div>
  );
}

// ---------- Bottom Navigation ----------
// ---------- Case Timeline (cross-thread visual map) ----------
function CaseTimeline({ lang, onClose, onOpenChat, onOpenReminders, onOpenCase }) {
  const [data, setData] = useState({ items: [], stats: { total_chats: 0, open_deadlines: 0, cases: 0, vault_items: 0 } });
  const [busy, setBusy] = useState(true);
  const [savedAt, setSavedAt] = useState(null);   // last successful save timestamp (this session)
  const [unsavedChanges, setUnsavedChanges] = useState(false);

  const load = () => {
    setBusy(true);
    api.get("/timeline").then(r => {
      setData(r.data || { items: [], stats: {} });
      setUnsavedChanges(true);   // any newly-loaded data hasn't been snapshotted yet
    }).catch(() => {}).finally(() => setBusy(false));
  };
  useEffect(() => { load(); }, []);

  // Save a snapshot to My Legal Files so the user can recover the timeline later
  // (and export it as PDF, save to Vault, etc.). Resets the "unsaved" flag.
  const saveSnapshot = async () => {
    setBusy(true);
    try {
      await api.post("/timeline/snapshot");
      setSavedAt(new Date());
      setUnsavedChanges(false);
      aaToast("Timeline saved to My Legal Files", "success");
    } catch (e) { aaToast(e?.response?.data?.detail || "Failed to save snapshot", "error"); }
    finally { setBusy(false); }
  };

  // Clear timeline: soft-deletes all conversation history + reminders (cases preserved).
  // If the user hasn't saved a snapshot first, we prompt to save before clearing.
  const clearTimeline = async () => {
    if (unsavedChanges) {
      const saveFirst = await aaConfirm({
        title: "Save before clearing?",
        message: "You haven't saved this timeline yet. Save a copy to My Legal Files first so you can recover it later?",
        confirmLabel: "Save & clear",
        cancelLabel: "Cancel",
      });
      if (!saveFirst) return;
      try { await api.post("/timeline/snapshot"); }
      catch (e) { aaToast("Save failed — aborting clear", "error"); return; }
    }
    const ok = await aaConfirm({
      title: "Clear timeline?",
      message: "Chats & deadlines move to Recycle Bin for 30 days. Cases are kept.",
      confirmLabel: "Clear",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.delete("/timeline");
      load();
      aaToast("Timeline cleared", "success");
    } catch (e) { aaToast(e?.response?.data?.detail || "Failed to clear", "error"); }
    finally { setBusy(false); }
  };

  const iconFor = (kind, cat) => {
    if (kind === "deadline") return "/icons/reminder.png";
    if (kind === "case") return "/icons/files.png";
    if (kind === "chat") {
      if (cat === "employment") return "/icons/employment.png";
      if (cat === "property") return "/icons/property.png";
      if (cat === "immigration") return "/icons/immigration.png";
      if (cat === "medical_negligence" || cat === "medical") return "/icons/medical.png";
      return "/icons/ask_lex.png";
    }
    return "/icons/ask_lex.png";
  };

  // Route a timeline tap → its source surface
  const handleItemClick = (it) => {
    if (it.kind === "chat" && onOpenChat) onOpenChat(it.id);
    else if (it.kind === "deadline" && onOpenReminders) onOpenReminders();
    else if (it.kind === "case" && onOpenCase) onOpenCase(it.id);
  };

  const fmtDate = (iso) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = (now - d) / 1000;
      if (diff < 60) return "just now";
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
      return d.toLocaleDateString();
    } catch { return ""; }
  };

  return (
    <div className="modal-bg" data-testid="case-timeline" style={{ zIndex: 100 }}>
      <div className="modal-card" style={{ padding: 0, maxWidth: 720, width: "100%", height: "92vh", display: "flex", flexDirection: "column" }}>
        {/* Header */}
        <div style={{ padding: 18, borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <img src="/icons/files.png" alt="" style={{ width: 36, height: 36, objectFit: "contain" }} />
            <div>
              <h2 style={{ fontFamily: "'Cinzel', serif", color: "var(--gold)", fontSize: 17, margin: 0, letterSpacing: "0.06em" }}>Case Timeline</h2>
              <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 2 }}>Your whole legal life in one view</div>
            </div>
          </div>
          <button onClick={onClose} data-testid="timeline-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={20} /></button>
        </div>

        {/* Action strip — Save + Clear */}
        <div style={{ display: "flex", gap: 8, padding: "10px 18px 0" }}>
          <button data-testid="timeline-save-btn" disabled={busy || data.items.length === 0} onClick={saveSnapshot}
                  className="btn-gold" style={{ flex: 1, padding: "8px 12px", fontSize: 12 }}>
            <Download size={13} style={{ display: "inline", marginRight: 6 }} />
            {savedAt && !unsavedChanges ? "Saved ✓" : "Save timeline"}
          </button>
          <button data-testid="timeline-clear-btn" disabled={busy || data.items.length === 0} onClick={clearTimeline}
                  className="btn-ghost" style={{ flex: 1, padding: "8px 12px", fontSize: 12, color: "#fca5a5" }}>
            <Trash2 size={13} style={{ display: "inline", marginRight: 6 }} />Clear timeline
          </button>
        </div>

        {/* Stat strip */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, padding: "14px 18px 0" }}>
          {[
            { n: data.stats?.total_chats || 0,    l: "Chats" },
            { n: data.stats?.open_deadlines || 0, l: "Open deadlines" },
            { n: data.stats?.cases || 0,          l: "Case files" },
            { n: data.stats?.vault_items || 0,    l: "Vault items" },
          ].map((s, i) => (
            <div key={i} style={{ background: "var(--bg-elev)", border: "1px solid var(--line)", borderRadius: 10, padding: "10px 12px", textAlign: "center" }}>
              <div style={{ color: "var(--gold)", fontSize: 18, fontWeight: 700, lineHeight: 1 }}>{s.n}</div>
              <div style={{ color: "var(--text-muted)", fontSize: 9, marginTop: 4, letterSpacing: "0.06em", textTransform: "uppercase" }}>{s.l}</div>
            </div>
          ))}
        </div>

        {/* Timeline */}
        <div data-testid="timeline-list" style={{ flex: 1, overflowY: "auto", padding: "14px 18px 24px" }}>
          {busy && (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: 40 }}>
              <span className="aa-typing-dots"><span/><span/><span/></span> Loading your timeline…
            </div>
          )}
          {!busy && data.items.length === 0 && (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: 40, fontSize: 13 }}>
              Nothing yet. Ask Lex a question, add a deadline, or open a case file — they'll all appear here.
            </div>
          )}
          {data.items.map((it, idx) => {
            const clickable = it.kind === "chat" || it.kind === "deadline" || it.kind === "case";
            return (
            <div key={it.id || idx} data-testid={`timeline-item-${idx}`}
                 onClick={() => clickable && handleItemClick(it)}
                 style={{
                   display: "flex", gap: 12, padding: "12px 0",
                   borderBottom: idx < data.items.length - 1 ? "1px solid var(--line)" : "none",
                   cursor: clickable ? "pointer" : "default",
                 }}>
              {/* Time-rail dot */}
              <div style={{ position: "relative", width: 28, flexShrink: 0, display: "flex", justifyContent: "center" }}>
                <div style={{
                  position: "absolute", top: 6, width: 10, height: 10, borderRadius: "50%",
                  background: it.kind === "deadline" && !it.completed ? "var(--gold)"
                            : it.kind === "deadline" && it.completed ? "#22c55e"
                            : "var(--gold-deep)",
                  boxShadow: it.kind === "deadline" && !it.completed ? "0 0 8px rgba(247,201,72,0.6)" : "none",
                }} />
                {idx < data.items.length - 1 && (
                  <div style={{ position: "absolute", top: 16, left: "50%", marginLeft: -1, width: 2, bottom: -12, background: "var(--line)" }} />
                )}
              </div>
              {/* Icon */}
              <img src={iconFor(it.kind, it.category)} alt="" style={{ width: 32, height: 32, objectFit: "contain", marginTop: 2, flexShrink: 0 }} />
              {/* Body */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <span style={{
                    fontSize: 9, padding: "2px 7px", borderRadius: 999, letterSpacing: "0.06em", textTransform: "uppercase",
                    background: it.kind === "deadline" ? "rgba(247,201,72,0.15)" : it.kind === "case" ? "rgba(247,201,72,0.08)" : "rgba(255,255,255,0.05)",
                    border: "1px solid var(--line)", color: "var(--gold-soft)",
                  }}>{it.kind}</span>
                  <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{fmtDate(it.updated_at || it.due_at)}</span>
                  {it.kind === "chat" && it.turns > 1 && (
                    <span style={{ fontSize: 10, color: "var(--text-muted)" }}>· {it.turns} turns</span>
                  )}
                  {it.kind === "deadline" && it.completed && (
                    <span style={{ fontSize: 10, color: "#22c55e" }}>✓ done</span>
                  )}
                  {clickable && (
                    <span style={{ fontSize: 10, color: "var(--gold)", marginLeft: "auto" }}>open →</span>
                  )}
                </div>
                <div style={{ color: "var(--text)", fontSize: 13, marginTop: 4, lineHeight: 1.4, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                  {it.title}
                </div>
              </div>
            </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------- Sponsor Footer (single firm partnership, opt-out via /api/sponsor) ----------
// Discreet "In partnership with [Firm Name]" line above the bottom nav on the home screen.
// Renders nothing if no active sponsor is configured server-side.
function SponsorFooter() {
  const [sponsor, setSponsor] = useState(null);
  useEffect(() => {
    let cancelled = false;
    api.get("/sponsor").then(r => { if (!cancelled && r.data?.active) setSponsor(r.data); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);
  if (!sponsor) return null;
  const inner = (
    <div data-testid="sponsor-footer" style={{
      display: "inline-flex", alignItems: "center", gap: 10,
      padding: "8px 14px",
      background: "rgba(247,201,72,0.05)",
      border: "1px solid var(--gold-deep)",
      borderRadius: 999,
      color: "var(--gold-soft)",
      fontSize: 11,
      letterSpacing: "0.04em",
      textDecoration: "none",
    }}>
      <span style={{ opacity: 0.75 }}>{sponsor.tagline || "In partnership with"}</span>
      {sponsor.logo_url && (
        <img src={sponsor.logo_url} alt={sponsor.name} style={{ height: 16, objectFit: "contain", filter: "brightness(1.1)" }} />
      )}
      <strong style={{ color: "var(--gold)", letterSpacing: "0.08em" }}>{sponsor.name}</strong>
    </div>
  );
  return (
    <div style={{ display: "flex", justifyContent: "center", margin: "8px 0 80px" }}>
      {sponsor.url ? (
        <a href={sponsor.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>{inner}</a>
      ) : inner}
    </div>
  );
}

// Bottom-nav slot storage. Up to 4 items; LEX is always pinned centre.
// First 2 entries render LEFT of LEX, last 2 entries render RIGHT.
const NAV_SLOT_MAX = 4;
function loadNavSlots() {
  try {
    const raw = localStorage.getItem("aa_nav_slots");
    if (raw) {
      const arr = JSON.parse(raw);
      if (Array.isArray(arr)) {
        // dedupe + cap
        const seen = new Set();
        const out = [];
        for (const k of arr) {
          if (typeof k === "string" && !seen.has(k)) { seen.add(k); out.push(k); }
          if (out.length >= NAV_SLOT_MAX) break;
        }
        return out;
      }
    }
  } catch (e) { /* fall through */ }
  // Migrate the old single-slot key (which caused the duplication bug)
  const legacy = localStorage.getItem("aa_nav_slot1");
  const def = ["reminders", "vault", "lawyers", "cases"];
  if (legacy && !def.includes(legacy)) def[0] = legacy;
  localStorage.removeItem("aa_nav_slot1");
  localStorage.setItem("aa_nav_slots", JSON.stringify(def));
  return def;
}
function saveNavSlots(arr) {
  localStorage.setItem("aa_nav_slots", JSON.stringify(arr));
  window.dispatchEvent(new CustomEvent("aa:nav-slots", { detail: { slots: arr } }));
}

function NavSlotPicker({ lang }) {
  const OPTIONS = [
    { k: "reminders", lbl: t(lang, "reminders") || "Reminders" },
    { k: "vault",     lbl: t(lang, "vault") || "Vault" },
    { k: "cases",     lbl: t(lang, "cases") || "Cases" },
    { k: "lawyers",   lbl: t(lang, "lawyers") || "Lawyers" },
    { k: "hearing",   lbl: t(lang, "hearingRecorder") || "Hearings" },
    { k: "letter",    lbl: "Letters" },
    { k: "contracts", lbl: "Contracts" },
    { k: "legal_aid", lbl: t(lang, "freeLegalAid") || "Legal Aid" },
  ];
  const [slots, setSlots] = useState(() => loadNavSlots());
  const toggle = (k) => {
    const has = slots.includes(k);
    let next;
    if (has) {
      next = slots.filter(x => x !== k);
    } else {
      if (slots.length >= NAV_SLOT_MAX) return;
      next = [...slots, k];
    }
    setSlots(next);
    saveNavSlots(next);
  };
  return (
    <div data-testid="nav-slots-picker">
      <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 10 }}>
        Pick up to {NAV_SLOT_MAX} · <strong style={{ color: "var(--gold)" }}>{slots.length}/{NAV_SLOT_MAX}</strong> selected · tap to add or remove
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {OPTIONS.map(o => {
          const sel = slots.includes(o.k);
          const idx = slots.indexOf(o.k);
          const disabled = !sel && slots.length >= NAV_SLOT_MAX;
          return (
            <button key={o.k} data-testid={`nav-slot-opt-${o.k}`} onClick={() => toggle(o.k)} disabled={disabled}
              style={{
                padding: "6px 12px", borderRadius: 999,
                cursor: disabled ? "not-allowed" : "pointer",
                background: sel ? "var(--gold)" : "transparent",
                color: sel ? "#1a1300" : (disabled ? "var(--text-muted)" : "var(--gold-soft)"),
                border: `1px solid ${sel ? "var(--gold)" : "var(--line)"}`,
                fontSize: 12, fontWeight: 600,
                opacity: disabled ? 0.45 : 1,
                display: "inline-flex", alignItems: "center", gap: 6,
              }}>
              {sel && <span style={{
                background: "#1a1300", color: "var(--gold)",
                borderRadius: "50%", width: 16, height: 16, fontSize: 9,
                display: "inline-flex", alignItems: "center", justifyContent: "center",
              }}>{idx + 1}</span>}
              {o.lbl}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// 🗑 RecycleBinModal — full-screen modal opened from the dashboard tile. Lists every
// soft-deleted item across kinds (legal_files, cases, case_items, conversations, reminders,
// hearings). 30-day window with auto-purge sweeper on the backend.
function RecycleBinModal({ lang, onClose }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setBusy(true);
    api.get("/recycle-bin").then(r => setItems(r.data?.items || [])).catch(() => {}).finally(() => setBusy(false));
  };
  useEffect(() => { load(); }, []);

  const restore = async (it) => {
    setBusy(true);
    try {
      await api.post(`/recycle-bin/restore/${it.kind}/${it.id}`);
      load();
      aaToast(`Restored "${it.label}"`, "success");
    } catch (e) { aaToast(e?.response?.data?.detail || "Restore failed", "error"); }
    finally { setBusy(false); }
  };
  const purge = async (it) => {
    const ok = await aaConfirm({
      title: "Delete permanently?",
      message: `"${it.label}" will be gone forever. This can't be undone.`,
      confirmLabel: "Delete forever",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.delete(`/recycle-bin/${it.kind}/${it.id}`);
      load();
      aaToast("Permanently deleted", "success");
    } catch (e) { aaToast(e?.response?.data?.detail || "Delete failed", "error"); }
    finally { setBusy(false); }
  };
  const emptyAll = async () => {
    const ok = await aaConfirm({
      title: "Empty Recycle Bin?",
      message: `All ${items.length} item${items.length === 1 ? "" : "s"} will be deleted forever. This can't be undone.`,
      confirmLabel: "Empty bin",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.delete("/recycle-bin");
      load();
      aaToast("Recycle Bin emptied", "success");
    } catch (e) { aaToast(e?.response?.data?.detail || "Empty failed", "error"); }
    finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="recycle-bin-modal">
      <div className="modal-card" style={{ padding: 20, overflowY: "auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 10 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20, display: "flex", alignItems: "center", gap: 10 }}>
            <RecycleIcon size={26} />
            Recycle Bin
          </h2>
          <button onClick={onClose} data-testid="recycle-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        <p style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 14 }}>
          Deleted items stay here for <strong style={{ color: "var(--gold-soft)" }}>30 days</strong>. Tap restore to bring them back, or empty the bin to permanently delete now.
        </p>
        {items.length > 0 && (
          <button data-testid="recycle-empty-btn" disabled={busy} onClick={emptyAll}
            style={{ background: "transparent", border: "1px solid #7f1d1d", color: "#fca5a5", borderRadius: 10, padding: "10px 14px", width: "100%", marginBottom: 14, fontSize: 13, cursor: "pointer" }}>
            <Trash2 size={13} style={{ display: "inline", marginRight: 6 }} />
            Empty bin permanently ({items.length})
          </button>
        )}
        {busy && items.length === 0 && (
          <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: "center", padding: 30 }}>
            <span className="aa-typing-dots"><span/><span/><span/></span> Loading…
          </div>
        )}
        {!busy && items.length === 0 && (
          <div style={{ color: "var(--text-muted)", fontSize: 13, textAlign: "center", padding: 30, border: "1px dashed var(--line)", borderRadius: 12 }}>
            Recycle bin is empty. Anything you delete from Files, Cases, Hearings, Reminders or Chats will appear here for 30 days.
          </div>
        )}
        {items.map(it => (
          <div key={`${it.kind}-${it.id}`} data-testid={`recycle-item-${it.id}`}
            style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, padding: 12, marginBottom: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span style={{ background: "var(--gold-deep)", color: "#1a1300", padding: "2px 7px", borderRadius: 6, fontSize: 9, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase" }}>
                {it.kind.replace("_", " ")}
              </span>
              <span style={{ color: "var(--gold)", fontSize: 13.5, fontWeight: 600, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {it.label}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 10 }}>
              Deleted {new Date(it.deleted_at).toLocaleDateString()} ·
              <span style={{ color: it.days_left < 7 ? "#fca5a5" : "var(--text-muted)", marginLeft: 4 }}>
                {it.days_left}d left
              </span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button data-testid={`recycle-restore-${it.id}`} disabled={busy} onClick={() => restore(it)}
                className="btn-gold" style={{ flex: 1, padding: "8px 12px", fontSize: 12 }}>Restore</button>
              <button data-testid={`recycle-purge-${it.id}`} disabled={busy} onClick={() => purge(it)}
                style={{ background: "transparent", border: "1px solid #7f1d1d", color: "#fca5a5", borderRadius: 8, padding: "8px 14px", fontSize: 12, cursor: "pointer" }}>
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// 🏛 CompFirmAdminCard — grant Featured/Premium/Practice trial days to law firms.
// Same mental model as CompProAdminCard but operates on `firm_accounts` and lets
// the owner pick which tier the trial grants (default Featured).
function CompFirmAdminCard({ lang }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [days, setDays] = useState(30);
  const [tier, setTier] = useState("featured");
  const [reason, setReason] = useState("");
  const [activeComps, setActiveComps] = useState([]);
  const [showActive, setShowActive] = useState(false);

  const search = async (q) => {
    setQuery(q);
    if (!q.trim()) { setResults([]); return; }
    setSearching(true);
    try {
      const r = await api.get(`/admin/firms/search?q=${encodeURIComponent(q)}`);
      setResults(r.data?.firms || []);
    } catch (e) { setResults([]); }
    finally { setSearching(false); }
  };

  const loadActive = async () => {
    try {
      const r = await api.get("/admin/firms/comps/active");
      setActiveComps(r.data?.firms || []);
    } catch (e) {}
  };
  useEffect(() => { if (showActive) loadActive(); }, [showActive]);

  const grant = async (email) => {
    setActionBusy(true);
    try {
      const r = await api.post("/admin/firms/comp", { email, days, tier, reason });
      aaToast(`Trial granted: ${r.data.days_granted}d ${tier.toUpperCase()} → ${r.data.firm_name}`, "success");
      setQuery(""); setResults([]); setReason("");
      if (showActive) loadActive();
    } catch (e) { aaToast(e?.response?.data?.detail || "Grant failed", "error"); }
    finally { setActionBusy(false); }
  };

  const revoke = async (email) => {
    const ok = await aaConfirm({ title: "Revoke firm trial?", message: `End the trial for "${email}" immediately?`, danger: true, confirmLabel: "Revoke" });
    if (!ok) return;
    setActionBusy(true);
    try {
      await api.post("/admin/firms/uncomp", { email, days: 1, tier: "featured", reason: "Owner revoked" });
      aaToast("Trial revoked", "success");
      loadActive();
    } catch (e) { aaToast(e?.response?.data?.detail || "Revoke failed", "error"); }
    finally { setActionBusy(false); }
  };

  return (
    <div data-testid="admin-comp-firm-card" style={{
      background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14,
      padding: 16, marginBottom: 12,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <LawyerIcon size={20} />
        <span style={{ color: "var(--gold)", fontWeight: 700, fontSize: 14, letterSpacing: "0.04em" }}>
          🏛 Firm trial / founding-firm comps
        </span>
        <span style={{ background: "var(--gold-deep)", color: "#1a1300", fontSize: 9, fontWeight: 700, padding: "2px 7px", borderRadius: 999, letterSpacing: "0.05em" }}>OWNER</span>
      </div>
      <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 12 }}>
        Grant 30 / 60 / 90 days of Featured, Premium, or Practice tier free to selected firms.
        New firms automatically get a <strong style={{ color: "var(--gold-soft)" }}>14-day Featured trial</strong> on signup.
      </div>

      <input data-testid="admin-firm-search"
        placeholder="Search firm by email, name, or city…"
        value={query} onChange={(e) => search(e.target.value)}
        style={{ width: "100%", padding: "9px 12px", background: "rgba(0,0,0,0.4)", border: "1px solid var(--line)", borderRadius: 10, color: "var(--text)", fontSize: 13, marginBottom: 8 }} />

      {searching && <div style={{ fontSize: 11, color: "var(--text-muted)", padding: 6 }}>Searching…</div>}
      {results.length > 0 && (
        <div style={{ marginBottom: 10, maxHeight: 240, overflowY: "auto", border: "1px solid var(--line)", borderRadius: 10 }}>
          {results.map(f => (
            <div key={f.id} style={{ padding: 10, borderBottom: "1px solid var(--line)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
                <span style={{ color: "var(--gold)", fontWeight: 600, fontSize: 12.5 }}>{f.firm_name || "(no name)"}</span>
                <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{f.email}</span>
                {f.city && <span style={{ fontSize: 10, color: "var(--text-muted)" }}>· {f.city}</span>}
                {f.trial_until && new Date(f.trial_until) > new Date() && (
                  <span style={{ background: "rgba(247,201,72,0.18)", color: "var(--gold)", fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 6 }}>
                    ON {(f.trial_tier || "").toUpperCase()} TRIAL
                  </span>
                )}
              </div>
              <button data-testid={`admin-firm-grant-${f.email}`} disabled={actionBusy} onClick={() => grant(f.email)}
                className="btn-gold" style={{ padding: "6px 10px", fontSize: 11 }}>
                + Grant {days}d {tier.charAt(0).toUpperCase()+tier.slice(1)}
              </button>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6, marginBottom: 8 }}>
        {["featured", "premium", "practice"].map(t => (
          <button key={t} data-testid={`admin-firm-tier-${t}`} onClick={() => setTier(t)}
            style={{
              padding: "8px 6px", borderRadius: 8, fontSize: 11, fontWeight: 700, cursor: "pointer",
              background: tier === t ? "var(--gold)" : "transparent",
              color: tier === t ? "#0a0a0a" : "var(--gold)",
              border: `1px solid ${tier === t ? "var(--gold)" : "var(--gold-deep)"}`,
              letterSpacing: "0.04em", textTransform: "uppercase",
            }}>
            {t}
          </button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        {[14, 30, 60, 90].map(d => (
          <button key={d} data-testid={`admin-firm-days-${d}`} onClick={() => setDays(d)}
            style={{
              flex: 1, padding: "8px 4px", borderRadius: 8, fontSize: 11, fontWeight: 700, cursor: "pointer",
              background: days === d ? "var(--gold-deep)" : "transparent",
              color: days === d ? "#0a0a0a" : "var(--gold)",
              border: `1px solid ${days === d ? "var(--gold-deep)" : "var(--line)"}`,
            }}>
            {d}d
          </button>
        ))}
      </div>
      <input data-testid="admin-firm-reason" placeholder="Reason (founding cohort / customer service…)"
        value={reason} onChange={(e) => setReason(e.target.value)}
        style={{ width: "100%", padding: "8px 12px", background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 10, color: "var(--text)", fontSize: 12, marginBottom: 10 }} />

      <button data-testid="admin-firm-active-toggle" onClick={() => setShowActive(s => !s)}
        style={{ background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 8, padding: "6px 10px", fontSize: 11, cursor: "pointer" }}>
        {showActive ? "▲ Hide" : "▼ Show"} active firm trials
      </button>
      {showActive && (
        <div style={{ marginTop: 10, maxHeight: 280, overflowY: "auto", border: "1px solid var(--line)", borderRadius: 10 }}>
          {activeComps.length === 0 && (
            <div style={{ padding: 12, fontSize: 11, color: "var(--text-muted)", textAlign: "center" }}>
              No firms currently on trial.
            </div>
          )}
          {activeComps.map(f => (
            <div key={f.id} style={{ padding: 10, borderBottom: "1px solid var(--line)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: 4 }}>
                <span style={{ color: "var(--gold)", fontWeight: 600, fontSize: 12.5, flex: 1, minWidth: 100 }}>{f.firm_name || "(no name)"}</span>
                <span style={{ background: "var(--gold)", color: "#0a0a0a", fontSize: 9, fontWeight: 700, padding: "1px 6px", borderRadius: 6, letterSpacing: "0.05em" }}>
                  {(f.trial_tier || "").toUpperCase()}
                </span>
                <span style={{ fontSize: 10, color: f.days_remaining < 7 ? "#fca5a5" : "var(--text-muted)" }}>
                  {f.days_remaining}d left
                </span>
              </div>
              <div style={{ fontSize: 10, color: "var(--text-muted)", marginBottom: 4 }}>{f.email}{f.city ? ` · ${f.city}` : ""}</div>
              <button data-testid={`admin-firm-revoke-${f.email}`} disabled={actionBusy} onClick={() => revoke(f.email)}
                style={{ background: "transparent", border: "1px solid #7f1d1d", color: "#fca5a5", borderRadius: 8, padding: "5px 10px", fontSize: 10, cursor: "pointer" }}>
                Revoke
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


function CompProAdminCard({ lang }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [days, setDays] = useState(30);
  const [reason, setReason] = useState("");
  const [activeComps, setActiveComps] = useState([]);
  const [feedback, setFeedback] = useState(null);    // {ok:true, msg} | {ok:false, msg}

  const loadComps = () => {
    api.get("/admin/users/comps").then(r => setActiveComps(r.data?.comps || [])).catch(() => {});
  };
  useEffect(() => { loadComps(); }, []);

  const search = async () => {
    if (!query.trim() || query.trim().length < 2) { setResults([]); return; }
    setSearching(true);
    try {
      const r = await api.get(`/admin/users/search?q=${encodeURIComponent(query.trim())}`);
      setResults(r.data?.users || []);
    } catch (e) { setResults([]); }
    finally { setSearching(false); }
  };

  const grantComp = async (email) => {
    setActionBusy(true); setFeedback(null);
    try {
      const r = await api.post("/admin/users/comp", { email, days, reason });
      setFeedback({ ok: true, msg: r.data.is_lifetime
        ? `✓ Lifetime Pro granted to ${email}`
        : `✓ ${r.data.days_granted} days Pro granted to ${email} (until ${r.data.comp_pro_until.slice(0,10)})` });
      loadComps();
      // Refresh search to show new status
      if (query) search();
    } catch (e) {
      setFeedback({ ok: false, msg: e?.response?.data?.detail || "Could not grant." });
    } finally { setActionBusy(false); setTimeout(() => setFeedback(null), 4000); }
  };

  const revokeComp = async (email) => {
    if (!window.confirm(`Revoke Pro comp for ${email}?`)) return;
    setActionBusy(true); setFeedback(null);
    try {
      await api.post("/admin/users/uncomp", { email, reason: "Owner revoked" });
      setFeedback({ ok: true, msg: `✓ Comp revoked for ${email}` });
      loadComps();
      if (query) search();
    } catch (e) {
      setFeedback({ ok: false, msg: e?.response?.data?.detail || "Could not revoke." });
    } finally { setActionBusy(false); setTimeout(() => setFeedback(null), 4000); }
  };

  return (
    <div data-testid="settings-comp-pro" style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <Sparkles size={18} style={{ color: "var(--gold)" }} />
        <span style={{ fontWeight: 600, color: "var(--gold)" }}>Owner tool — Comp Pro Access</span>
      </div>
      <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 12 }}>
        Grant free Pro access to family, friends, or unhappy customers. Every grant is logged. Tap a preset, search a user by email, then tap "Grant".
      </div>

      {/* Days preset row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6, marginBottom: 10 }}>
        {[
          { d: 7, lbl: "7d" }, { d: 30, lbl: "1m" }, { d: 90, lbl: "3m" }, { d: 365, lbl: "1yr" }, { d: 0, lbl: "Lifetime" }
        ].map(opt => {
          const sel = days === opt.d;
          return (
            <button key={opt.d} data-testid={`comp-days-${opt.d}`} onClick={() => setDays(opt.d)}
              style={{
                padding: "8px 4px", borderRadius: 8, cursor: "pointer",
                background: sel ? "var(--gold)" : "transparent",
                color: sel ? "#1a1300" : "var(--gold-soft)",
                border: `1px solid ${sel ? "var(--gold)" : "var(--line)"}`,
                fontSize: 11, fontWeight: 700,
              }}>{opt.lbl}</button>
          );
        })}
      </div>
      <input className="input" data-testid="comp-reason" placeholder="Reason (e.g. 'Family — brother', 'Goodwill — complaint about Lex')"
        value={reason} onChange={(e) => setReason(e.target.value)} style={{ marginBottom: 10 }} />

      {/* User search */}
      <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
        <input className="input" data-testid="comp-search" placeholder="Search user by email…"
          value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()} style={{ flex: 1 }} />
        <button className="btn-gold" data-testid="comp-search-btn" onClick={search} disabled={searching || query.length < 2}>
          {searching ? <span className="spinner" /> : "🔍"}
        </button>
      </div>

      {/* Search results */}
      {results.length > 0 && (
        <div data-testid="comp-search-results" style={{ marginBottom: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          {results.map(u => {
            const hasComp = u.comp_pro_until && new Date(u.comp_pro_until) > new Date();
            return (
              <div key={u.id} style={{ background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 10, padding: 8, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, color: "var(--text)", fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{u.email}</div>
                  <div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>
                    {u.full_name || "—"} · {u.tier || "free"}
                    {hasComp && <span style={{ color: "var(--gold)" }}> · comp until {u.comp_pro_until.slice(0,10)}</span>}
                  </div>
                </div>
                {hasComp ? (
                  <button data-testid={`comp-revoke-${u.id}`} onClick={() => revokeComp(u.email)} disabled={actionBusy}
                    style={{ background: "transparent", border: "1px solid #fca5a5", color: "#fca5a5", borderRadius: 8, padding: "5px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
                    Revoke
                  </button>
                ) : (
                  <button data-testid={`comp-grant-${u.id}`} onClick={() => grantComp(u.email)} disabled={actionBusy}
                    style={{ background: "var(--gold)", border: "none", color: "#1a1300", borderRadius: 8, padding: "5px 12px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
                    Grant {days === 0 ? "lifetime" : `${days}d`}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {feedback && (
        <div data-testid="comp-feedback" style={{
          padding: 8, borderRadius: 8, marginBottom: 10, fontSize: 12,
          background: feedback.ok ? "rgba(34,197,94,0.10)" : "rgba(220,38,38,0.10)",
          border: `1px solid ${feedback.ok ? "#22c55e" : "#fca5a5"}`,
          color: feedback.ok ? "#86efac" : "#fca5a5",
        }}>{feedback.msg}</div>
      )}

      {/* Active comps dashboard */}
      {activeComps.length > 0 && (
        <div style={{ borderTop: "1px solid var(--line)", paddingTop: 10 }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6, fontWeight: 600, letterSpacing: "0.04em" }}>
            ACTIVE COMPS ({activeComps.length})
          </div>
          <div data-testid="comp-active-list" style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 160, overflowY: "auto" }}>
            {activeComps.map(c => {
              const isLifetime = new Date(c.comp_pro_until).getFullYear() > 2050;
              return (
                <div key={c.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, padding: "4px 0" }}>
                  <div style={{ fontSize: 11.5, color: "var(--text-dim)", minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {c.email}
                  </div>
                  <div style={{ fontSize: 10.5, color: isLifetime ? "var(--gold)" : "var(--text-muted)", whiteSpace: "nowrap" }}>
                    {isLifetime ? "Lifetime" : `until ${c.comp_pro_until.slice(0,10)}`}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function MicAccessButton() {
  const [state, setState] = useState("idle");
  useEffect(() => {
    if (!navigator.permissions || !navigator.permissions.query) return;
    navigator.permissions.query({ name: "microphone" }).then(p => {
      if (p.state === "granted") setState("granted");
      else if (p.state === "denied") setState("denied");
    }).catch(() => {});
  }, []);
  const request = async () => {
    if (!navigator.mediaDevices?.getUserMedia) { setState("unsupported"); return; }
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true });
      s.getTracks().forEach(tr => tr.stop());
      setState("granted");
    } catch (e) {
      setState("denied");
    }
  };
  const label = state === "granted" ? "✓ Microphone enabled"
    : state === "denied" ? "Blocked — open device settings"
    : state === "unsupported" ? "Not supported on this device"
    : "Enable microphone";
  return (
    <button data-testid="mic-access-btn" onClick={request} disabled={state === "granted" || state === "unsupported"}
      style={{
        padding: "10px 16px", borderRadius: 10, cursor: state === "granted" ? "default" : "pointer",
        background: state === "granted" ? "rgba(34,197,94,0.15)" : "var(--gold)",
        color: state === "granted" ? "#22c55e" : "#1a1300",
        border: state === "granted" ? "1px solid #22c55e" : "none",
        fontSize: 13, fontWeight: 700, width: "100%",
      }}>{label}</button>
  );
}

// Emergency Contacts + Lawyer Standby + Watch SOS setup — Settings section.
// This is the life-safety configuration the user fills in BEFORE they ever need it.
function EmergencyContactsCard({ lang, user }) {
  const [contacts, setContacts] = useState([]);
  const [standby, setStandby] = useState(false);
  const [radius, setRadius] = useState(25);
  const [sosMsg, setSosMsg] = useState("");
  const [watchToken, setWatchToken] = useState(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showWatch, setShowWatch] = useState(false);
  const [trackWindow, setTrackWindow] = useState(60);   // minutes

  useEffect(() => {
    api.get("/emergency/contacts").then(r => {
      setContacts(r.data?.contacts || []);
      setStandby(!!r.data?.lawyer_standby_enabled);
      setRadius(r.data?.lawyer_standby_radius_km || 25);
      setSosMsg(r.data?.sos_message || "");
      setWatchToken(r.data?.watch_token || null);
      setTrackWindow(r.data?.tracking_window_minutes || 60);
    }).catch(() => {});
  }, []);

  const addContact = () => {
    setContacts(c => [...c, { name: "", relationship: "", phone: "", include_in_sos: true, is_lawyer: false }]);
  };
  const updateContact = (i, patch) => {
    setContacts(c => c.map((x, idx) => idx === i ? { ...x, ...patch } : x));
  };
  const removeContact = async (i) => {
    // Persist the deletion immediately so re-opening Settings doesn't show the row again.
    // Previously we only mutated local state, which let stale contacts re-appear after refresh.
    const next = contacts.filter((_, idx) => idx !== i);
    setContacts(next);
    try {
      await api.post("/emergency/contacts", {
        contacts: next.filter(c => c.name && c.phone),
        lawyer_standby_enabled: standby,
        lawyer_standby_radius_km: radius,
        sos_message: sosMsg,
        tracking_window_minutes: trackWindow,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      // Don't roll back UI — user can re-save. Just surface a soft hint.
      console.warn("Auto-save after remove failed:", e);
    }
  };
  const save = async () => {
    setBusy(true); setSaved(false);
    try {
      await api.post("/emergency/contacts", {
        contacts: contacts.filter(c => c.name && c.phone),
        lawyer_standby_enabled: standby,
        lawyer_standby_radius_km: radius,
        sos_message: sosMsg,
        tracking_window_minutes: trackWindow,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) {
      alert(e?.response?.data?.detail || "Could not save.");
    } finally { setBusy(false); }
  };
  const generateWatchToken = async () => {
    try {
      const { data } = await api.post("/emergency/watch-token");
      setWatchToken(data.watch_token);
      setShowWatch(true);
    } catch (e) { alert("Could not generate token."); }
  };

  const apiOrigin = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
  const watchUrl = watchToken ? `${apiOrigin}/api/emergency/silent-sos?wt=${watchToken}&src=watch` : "";

  return (
    <div data-testid="settings-emergency-contacts" style={{ background: "var(--bg-card)", border: "1px solid #7f1d1d", borderRadius: 14, padding: 16, marginBottom: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <AlertTriangle size={18} style={{ color: "#fca5a5" }} />
        <span style={{ fontWeight: 600, color: "#fca5a5" }}>Emergency contacts & SOS</span>
      </div>
      <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 12 }}>
        These are the people Lex notifies the instant you press the red SOS button — family, your lawyer, anyone you trust. Star one as <strong>"My Lawyer"</strong>.
      </div>

      {contacts.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--text-muted)", textAlign: "center", padding: 14, border: "1px dashed var(--line)", borderRadius: 10, marginBottom: 10 }}>
          No contacts yet. Add at least one trusted person.
        </div>
      )}
      {contacts.map((c, i) => (
        <div key={i} data-testid={`ec-row-${i}`} style={{ background: "rgba(0,0,0,0.3)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, marginBottom: 8 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 6 }}>
            <input className="input" data-testid={`ec-name-${i}`} placeholder="Name" value={c.name || ""} onChange={(e) => updateContact(i, { name: e.target.value })} />
            <input className="input" data-testid={`ec-rel-${i}`} placeholder="Relationship" value={c.relationship || ""} onChange={(e) => updateContact(i, { relationship: e.target.value })} />
          </div>
          <input className="input" data-testid={`ec-phone-${i}`} placeholder="+44…" value={c.phone || ""} onChange={(e) => updateContact(i, { phone: e.target.value })} style={{ marginBottom: 6 }} />
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 11.5 }}>
              <input type="checkbox" data-testid={`ec-lawyer-${i}`} checked={!!c.is_lawyer}
                onChange={(e) => {
                  // Only ONE can be lawyer — uncheck others
                  setContacts(cs => cs.map((x, idx) => ({ ...x, is_lawyer: idx === i ? e.target.checked : (e.target.checked ? false : x.is_lawyer) })));
                }} style={{ accentColor: "var(--gold)" }} />
              <Star size={12} style={{ color: c.is_lawyer ? "var(--gold)" : "var(--text-muted)" }} />
              My Lawyer
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", fontSize: 11.5 }}>
              <input type="checkbox" data-testid={`ec-sos-${i}`} checked={!!c.include_in_sos}
                onChange={(e) => updateContact(i, { include_in_sos: e.target.checked })} style={{ accentColor: "var(--gold)" }} />
              SOS
            </label>
            <button data-testid={`ec-remove-${i}`} onClick={() => removeContact(i)}
              style={{ background: "transparent", border: "1px solid #7f1d1d", color: "#fca5a5", borderRadius: 8, padding: "4px 8px", fontSize: 11, cursor: "pointer" }}>
              <Trash2 size={11} />
            </button>
          </div>
        </div>
      ))}
      <button data-testid="ec-add" onClick={addContact} className="btn-ghost" style={{ width: "100%", marginTop: 4, fontSize: 12 }}>
        + Add another contact
      </button>

      <div style={{ borderTop: "1px solid var(--line)", margin: "14px 0 10px" }} />
      <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, cursor: "pointer", marginBottom: 8 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>Lawyer Standby fallback</div>
          <div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>If nobody acknowledges within 60s, alert the nearest 3 emergency-standby solicitors. <em>Pro only.</em></div>
        </div>
        <input type="checkbox" data-testid="ec-standby" checked={standby} onChange={(e) => setStandby(e.target.checked)}
          style={{ width: 38, height: 22, accentColor: "var(--gold)" }} />
      </label>
      {standby && (
        <div style={{ marginBottom: 10 }}>
          <label style={{ fontSize: 11, color: "var(--text-muted)" }}>Search radius: {radius}km</label>
          <input type="range" min={5} max={100} step={5} value={radius} onChange={(e) => setRadius(Number(e.target.value))} style={{ width: "100%", accentColor: "var(--gold)" }} />
        </div>
      )}
      <textarea className="input" data-testid="ec-sos-msg" rows={2} placeholder="Pre-written SOS message (e.g. 'I've been detained, please call my lawyer and embassy.')"
        value={sosMsg} onChange={(e) => setSosMsg(e.target.value)} style={{ marginBottom: 10 }} />

      {/* 📍 Live Location Tracking Window — how long the app keeps sharing location after SOS fires.
          Default 1h, max 24h Pro / 2h Free. Family taps the SMS link to watch live position. */}
      <div data-testid="ec-track-window" style={{ background: "rgba(34,211,238,0.05)", border: "1px solid #155e75", borderRadius: 10, padding: 10, marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4, color: "#67e8f9" }}>📍 Live Location after SOS</div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 10 }}>
          When you fire the SOS, your phone shares your live location for this long. Family taps the map link in the SMS to follow you in real-time. Auto-stops when the window ends — or stop it any time from the in-app banner.
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 6 }}>
          {[15, 60, 360, 720, 1440].map(min => {
            const label = min < 60 ? `${min}m` : min < 1440 ? `${min/60}h` : "24h";
            const sel = trackWindow === min;
            return (
              <button key={min} data-testid={`ec-track-${min}`} onClick={() => setTrackWindow(min)}
                style={{
                  padding: "8px 4px", borderRadius: 8, cursor: "pointer",
                  background: sel ? "#67e8f9" : "transparent",
                  color: sel ? "#012a36" : "#67e8f9",
                  border: `1px solid ${sel ? "#67e8f9" : "#155e75"}`,
                  fontSize: 12, fontWeight: 700,
                }}>
                {label}
              </button>
            );
          })}
        </div>
        <div style={{ fontSize: 10.5, color: "var(--text-muted)", marginTop: 8, lineHeight: 1.5 }}>
          Default: 1 hour. Hard maximum: 24 hours (GDPR proportionality). Available on every tier — life-safety should never be paywalled.
          <br />Lawful basis: vital interests (UK GDPR Art 6(1)(d)) — triggered only by your own SOS tap.
        </div>
      </div>

      <button onClick={save} disabled={busy} className="btn-gold w-full" data-testid="ec-save"
        style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6, marginBottom: 12 }}>
        {busy ? <span className="spinner" /> : saved ? <Check size={14} /> : null}
        {saved ? "Saved ✓" : "Save emergency settings"}
      </button>

      {/* WATCH SOS — covert smartwatch trigger */}
      <div style={{ borderTop: "1px solid var(--line)", paddingTop: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
          ⌚ Covert Watch SOS
        </div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 8 }}>
          For situations where you can't reach your phone — hostile interrogations abroad, abduction, intimidation. One-tap watch shortcut silently records the SOS and, if Lawyer Standby is on, pings the nearest 3 firms server-side.
          <br /><br />
          <strong style={{ color: "#fca5a5" }}>⚠ Limit:</strong> a watch-fired SOS does NOT send SMS to family — that requires your phone. For full family SMS dispatch, fire SOS from the phone's Emergency button. The watch is the silent backup that activates the law-firm fallback.
        </div>
        {!watchToken ? (
          <button onClick={generateWatchToken} className="btn-ghost w-full" data-testid="ec-watch-generate" style={{ fontSize: 12 }}>
            Generate covert watch link
          </button>
        ) : (
          <>
            <button onClick={() => setShowWatch(s => !s)} className="btn-ghost w-full" data-testid="ec-watch-toggle" style={{ fontSize: 12, marginBottom: 8 }}>
              {showWatch ? "Hide setup link" : "Show setup link"}
            </button>
            {showWatch && (
              <div data-testid="ec-watch-setup" style={{ background: "#0a0a0a", border: "1px solid var(--gold-deep)", borderRadius: 10, padding: 10, fontSize: 11, lineHeight: 1.6 }}>
                <div style={{ color: "var(--gold)", fontWeight: 700, marginBottom: 6 }}>YOUR PRIVATE SOS URL</div>
                <input className="input" readOnly value={watchUrl} onClick={(e) => e.target.select()} style={{ fontSize: 10.5, marginBottom: 8 }} data-testid="ec-watch-url" />
                <div style={{ color: "var(--text-dim)", marginBottom: 6 }}><strong>Apple Watch:</strong> on your iPhone, open <em>Shortcuts</em> → + → "Get Contents of URL" → paste the link above → set Method to GET → tap the share icon → "Add to Apple Watch". Now add the shortcut as a complication on your watch face. One tap = silent SOS.</div>
                <div style={{ color: "var(--text-dim)", marginBottom: 6 }}><strong>Android / Wear OS:</strong> install <em>HTTP Shortcuts</em> from the Play Store, add a GET request to the URL above, then save it as a Wear OS tile.</div>
                <div style={{ color: "#fca5a5", fontStyle: "italic", marginTop: 6 }}>⚠ Keep this URL private — anyone with it can fire an SOS as you. Regenerate any time to invalidate the old one.</div>
                <button onClick={generateWatchToken} className="btn-ghost" style={{ marginTop: 8, fontSize: 11, padding: "5px 10px" }} data-testid="ec-watch-rotate">
                  Rotate (invalidate old link)
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function BottomNav({ lang, active = "home", onNav, hasAccess, requireSub, badges = {} }) {
  // LEX is always centred. Up to 4 user-customisable slots: 2 left + 2 right.
  // Lawyer icon uses the GAVEL (lawyer.png) so it matches the "Find a Lawyer"
  // dashboard tile — tapping nav Lawyers opens that same screen.
  const NAV_OPTIONS = {
    reminders: { icon: "/icons/reminder.png", lbl: t(lang, "reminders") || "Reminders" },
    vault:     { icon: "/icons/vault.png",    lbl: t(lang, "vault") || "Vault" },
    cases:     { icon: "/icons/files.png",    lbl: t(lang, "cases") || "Cases" },
    lawyers:   { icon: "/icons/lawyer.png",   lbl: t(lang, "lawyers") || "Lawyers" },
    hearing:   { icon: "/icons/hearing.png",  lbl: t(lang, "hearingRecorder") || "Hearings" },
    letter:    { icon: "/icons/letter.png",   lbl: "Letters" },
    contracts: { icon: "/icons/contract.png", lbl: "Contracts" },
    legal_aid: { icon: "/icons/aid.png",      lbl: t(lang, "freeLegalAid") || "Aid" },
  };
  const [slots, setSlots] = useState(() => loadNavSlots());
  useEffect(() => {
    const sync = () => setSlots(loadNavSlots());
    window.addEventListener("aa:nav-slots", sync);
    return () => window.removeEventListener("aa:nav-slots", sync);
  }, []);

  const handle = (k) => {
    if (k === "lex" && !hasAccess) { requireSub(); return; }
    onNav(k);
  };

  // Pad arrays to exactly 2 either side so LEX is geometrically centred.
  const left = slots.slice(0, 2);
  const right = slots.slice(2, 4);
  const leftPadded = [...left, ...Array(Math.max(0, 2 - left.length)).fill(null)];
  const rightPadded = [...right, ...Array(Math.max(0, 2 - right.length)).fill(null)];

  const renderSlot = (k, fallbackKey) => {
    if (!k) {
      // empty placeholder keeps the LEX button centred
      return <div key={fallbackKey} style={{ flex: 1 }} />;
    }
    const cfg = NAV_OPTIONS[k];
    if (!cfg) return <div key={fallbackKey} style={{ flex: 1 }} />;
    return (
      <button key={k} data-testid={`nav-${k}`} onClick={() => handle(k)}
              style={{ background: "transparent", border: "none", display: "flex", flexDirection: "column", alignItems: "center", gap: 3, flex: 1, cursor: "pointer", padding: 4, position: "relative" }}>
        <div style={{ position: "relative", display: "inline-flex" }}>
          <img src={cfg.icon} alt="" style={{
            width: 26, height: 26, objectFit: "contain",
            opacity: active === k ? 1 : 0.65,
            filter: active === k ? "drop-shadow(0 0 6px rgba(247,201,72,0.55))" : "none",
            transition: "opacity 150ms, filter 150ms",
          }} />
          {badges[k] > 0 && (
            <span data-testid={`nav-${k}-badge`} style={{
              position: "absolute", top: -4, right: -6,
              minWidth: 14, height: 14, padding: "0 4px",
              borderRadius: 7, background: "var(--gold)", color: "#1a1300",
              fontSize: 9, fontWeight: 800, display: "inline-flex",
              alignItems: "center", justifyContent: "center",
              boxShadow: "0 0 8px rgba(247,201,72,0.7)",
            }}>{badges[k] > 9 ? "9+" : badges[k]}</span>
          )}
        </div>
        <span style={{ fontSize: 10, color: active === k ? "var(--gold)" : "var(--gold-soft)", letterSpacing: "0.04em" }}>{cfg.lbl}</span>
      </button>
    );
  };

  return (
    <nav data-testid="bottom-nav" style={{
      position: "fixed", bottom: 0, left: 0, right: 0,
      display: "flex", justifyContent: "space-around", alignItems: "center",
      background: "rgba(8,8,8,0.92)", backdropFilter: "blur(12px)",
      borderTop: "1px solid var(--line)",
      padding: "8px 8px 14px", zIndex: 50,
    }}>
      {leftPadded.map((k, i) => renderSlot(k, `L${i}`))}
      <div key="lex" data-testid="nav-lex" onClick={() => handle("lex")}
           style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1, cursor: "pointer" }}>
        <div data-testid="nav-lex-avatar" style={{
          width: 60, height: 60, borderRadius: "50%",
          background: "#000",
          border: "3px solid var(--gold)", marginTop: -22, overflow: "hidden",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 4px 22px rgba(247,201,72,0.55)",
        }}>
          <img src="/assets/lex.jpg" alt="Lex" style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%", mixBlendMode: "lighten" }} />
        </div>
      </div>
      {rightPadded.map((k, i) => renderSlot(k, `R${i}`))}
    </nav>
  );
}

// ---------- Dashboard ----------
// 🎁 Gift banner for users granted free Pro by the owner. Persists until they
// dismiss it (per comp_pro_until timestamp so a re-grant shows it again).
function CompGiftBanner({ user, lang }) {
  const compUntil = user?.comp_pro_until;
  const isComp = !!user?.is_comp && !!compUntil;
  const dismissKey = `aa_comp_gift_seen_${compUntil || ""}`;
  const [dismissed, setDismissed] = useState(() => isComp && localStorage.getItem(dismissKey) === "1");

  if (!isComp || dismissed) return null;

  const daysLeft = user.comp_pro_days_remaining ?? 0;
  const isLifetime = compUntil && new Date(compUntil).getFullYear() > 2050;

  const dismiss = () => {
    localStorage.setItem(dismissKey, "1");
    setDismissed(true);
  };

  return (
    <div data-testid="comp-gift-banner" style={{
      position: "relative",
      background: "linear-gradient(135deg, rgba(247,201,72,0.30), rgba(247,201,72,0.10) 60%, rgba(220,38,38,0.12))",
      border: "2px solid var(--gold)",
      borderRadius: 14, padding: "14px 16px", marginBottom: 14,
      boxShadow: "0 0 30px rgba(247,201,72,0.30)",
      overflow: "hidden",
    }}>
      {/* Subtle shimmer overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        background: "radial-gradient(ellipse at top right, rgba(255,255,255,0.18), transparent 60%)",
      }} />
      <div style={{ display: "flex", alignItems: "center", gap: 12, position: "relative" }}>
        <div style={{ fontSize: 30, lineHeight: 1, flexShrink: 0 }}>🎁</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 800, color: "var(--gold)", letterSpacing: "0.05em", marginBottom: 2 }}>
            YOU'VE BEEN GIFTED PRO ACCESS
          </div>
          <div style={{ fontSize: 12.5, color: "#fff", lineHeight: 1.45 }}>
            {isLifetime
              ? "The AI Advocate team has gifted you full Pro features — for life. Welcome to the inner circle."
              : `The AI Advocate team has gifted you full Pro features for ${daysLeft} more day${daysLeft === 1 ? "" : "s"}. Enjoy.`}
          </div>
          <div style={{ fontSize: 10.5, color: "var(--gold-soft)", marginTop: 4, opacity: 0.85 }}>
            ✓ Deep Think · ✓ Translation Mode · ✓ Whisper Mode · ✓ Lawyer Standby · ✓ 24h SOS tracking
          </div>
        </div>
        <button data-testid="comp-gift-dismiss" onClick={dismiss}
          aria-label="Dismiss"
          style={{
            background: "transparent", border: "1px solid var(--gold-deep)",
            color: "var(--gold)", borderRadius: 8, padding: "5px 10px",
            fontSize: 11, fontWeight: 700, cursor: "pointer", flexShrink: 0,
          }}>
          Got it
        </button>
      </div>
    </div>
  );
}

function Dashboard({ user, lang, country, setLang, setCountry, onLogout, refreshUser }) {
  const [modal, setModal] = useState(null); // {type, title, category}
  const [showLang, setShowLang] = useState(false);
  const [showSub, setShowSub] = useState(false);
  const [subPreset, setSubPreset] = useState("plus");
  const [showSettings, setShowSettings] = useState(false);
  const [showSuggest, setShowSuggest] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);
  const [showAdvertise, setShowAdvertise] = useState(false);
  const [showEmergency, setShowEmergency] = useState(false);
  const [wakeOn, setWakeOn] = useState(() => localStorage.getItem("aa_wake") === "1");

  const tier = user.tier || "free";
  const TIER_RANK = { free: 0, plus: 1, pro: 2, yearly: 2, trial_pro: 2 };
  const hasTier = useCallback((req) => TIER_RANK[tier] >= TIER_RANK[req], [tier]);

  // Allow other components (Settings) to open the Subscribe modal with a preset plan
  useEffect(() => {
    const handler = (e) => { setSubPreset(e?.detail?.preset || "pro"); setShowSub(true); };
    window.addEventListener("aa:open-subscribe", handler);
    const wakeHandler = (e) => setWakeOn(!!e?.detail?.enabled);
    window.addEventListener("aa:wake-toggle", wakeHandler);
    // Allow Courtroom Live Assist to hand off a session for full Lex review
    const seedHandler = (e) => {
      const seed = e?.detail?.seed || "";
      const category = e?.detail?.category || "ask_lex";
      const title = e?.detail?.title || "Lex";
      setModal({ type: "chat", category, title, _initialSeed: seed });
    };
    window.addEventListener("aa:open-lex-with-seed", seedHandler);
    return () => {
      window.removeEventListener("aa:open-subscribe", handler);
      window.removeEventListener("aa:wake-toggle", wakeHandler);
      window.removeEventListener("aa:open-lex-with-seed", seedHandler);
    };
  }, []);

  const [voiceMode, setVoiceMode] = useState(null); // {initialText} | null
  const [reviewPrompt, setReviewPrompt] = useState(null); // {daysLeft}
  const [securityAlerts, setSecurityAlerts] = useState([]); // unread security events
  const [casesBadge, setCasesBadge] = useState(0); // # reminders due ≤3 days

  // Trustpilot pre-renewal nudge — once per session, only if backend says it's the right window
  useEffect(() => {
    if (sessionStorage.getItem("aa_review_checked")) return;
    sessionStorage.setItem("aa_review_checked", "1");
    api.get("/review/should-prompt").then(r => {
      if (r.data?.should_prompt) setReviewPrompt({ daysLeft: r.data.days_left });
    }).catch(() => {});
  }, []);

  // 🎟 Top-up success/cancel return from Stripe Checkout. We strip the params
  // after handling so a page refresh doesn't re-fire the toast.
  const [topupToast, setTopupToast] = useState(null); // {pack} | "cancel" | null
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const status = params.get("topup");
      if (!status) return;
      if (status === "success") {
        setTopupToast({ pack: params.get("pack") || "" });
        // Webhook may take a couple of seconds to land — re-fetch the user a few times
        let n = 0;
        const poll = setInterval(() => {
          n += 1;
          refreshUser && refreshUser();
          if (n >= 4) clearInterval(poll);
        }, 1500);
      } else if (status === "cancel") {
        setTopupToast("cancel");
      }
      // Clean the URL
      params.delete("topup"); params.delete("pack");
      const qs = params.toString();
      window.history.replaceState({}, "", window.location.pathname + (qs ? "?" + qs : ""));
    } catch (e) { /* no-op */ }
  }, []);

  // Reminders badge — count items due within 3 days, sync to nav-dot + native app-icon
  useEffect(() => {
    let cancelled = false;
    const fetchBadge = async () => {
      try {
        const { data } = await api.get("/reminders/badge");
        if (cancelled) return;
        const n = Number(data?.count || 0);
        setCasesBadge(n);
        setAppIconBadge(n); // best-effort — silent if platform unsupported
      } catch (e) { /* no-op */ }
    };
    fetchBadge();
    const onVis = () => { if (document.visibilityState === "visible") fetchBadge(); };
    document.addEventListener("visibilitychange", onVis);
    const tick = setInterval(fetchBadge, 5 * 60 * 1000); // re-poll every 5 min
    return () => { cancelled = true; document.removeEventListener("visibilitychange", onVis); clearInterval(tick); };
  }, []);

  // If the user arrived via /engage/<token> deep-link, auto-open the Engagements modal
  useEffect(() => {
    if (sessionStorage.getItem("aa_pending_invite")) {
      setModal({ type: "engagements" });
    }
  }, []);

  // Fetch unread security events on mount (e.g. login-from-different-country alerts)
  useEffect(() => {
    api.get("/security/events").then(r => {
      const unread = (r.data?.events || []).filter(e => !e.acknowledged);
      setSecurityAlerts(unread);
    }).catch(() => {});
  }, []);
  // "Hey Lex" wake word — opens Siri-style Voice Mode (Plus+ only)
  const handleWake = useCallback((trailing) => {
    if (modal || voiceMode) return;
    if (!hasTier("plus")) { setSubPreset("plus"); setShowSub(true); return; }
    setVoiceMode({ initialText: trailing || "" });
  }, [modal, voiceMode, hasTier]);
  useHeyLex({ enabled: wakeOn && !modal && !voiceMode && hasTier("plus"), lang, onWake: handleWake });

  // Tier required per tile. "free" = available to all; emergency is separate.
  const tiles = [
    { id: "ask_lex", label: t(lang, "askLex"), sub: t(lang, "askLexSub"), Icon: AskLexIcon, cat: "ask_lex", req: "free" },
    { id: "courtroom", label: t(lang, "courtroomTrainer"), Icon: CourtIcon, req: "plus" },
    // Merged "Record" tile — opens RecordModal with two modes:
    // 🚔 Encounter (Plus tier, was the original "Record Legal Interaction")
    // 🏛 Hearing (Pro tier, was the "Hearing Recorder")
    // Uses the Hearing/vintage-mic icon per user preference.
    { id: "record", label: t(lang, "recordLegal"), Icon: HearingIcon, cat: "record", req: "plus" },
    { id: "snap", label: t(lang, "snapEvidence"), Icon: CameraIcon, req: "free" },
    { id: "letter_reader", label: t(lang, "letterReader"), Icon: LetterIcon, req: "free" },
    { id: "contracts", label: t(lang, "contractTools"), Icon: ContractIcon, req: "free" },
    { id: "engagements", label: t(lang, "mySolicitor"), sub: t(lang, "mySolicitorSub"), Icon: HandshakeIcon, req: "free" },
    { id: "vault", label: t(lang, "vaultTitle"), Icon: VaultIcon, req: "free" },
    { id: "outcome", label: t(lang, "predictOutcome"), Icon: OutcomeIcon, req: "pro" },
    { id: "cost", label: t(lang, "lawyerCost"), Icon: CostIcon, req: "free" },
    { id: "legal_aid", label: t(lang, "freeLegalAid"), sub: t(lang, "freeLegalAidSub"), Icon: AidIcon, req: "free" },
    { id: "lawyers", label: t(lang, "findLawyer"), Icon: LawyerIcon, req: "free" },
    { id: "files", label: t(lang, "myFiles"), Icon: FilesIcon, req: "free" },
    { id: "cases", label: t(lang, "caseFiles"), Icon: FilesIcon, req: "free" },
    { id: "reminders", label: t(lang, "reminders"), Icon: ReminderIcon, req: "free" },
    { id: "recycle", label: "Recycle Bin", Icon: RecycleIcon, req: "free" },
    { id: "letter", label: t(lang, "letterLibrary"), Icon: LetterIcon, req: "free" },
    { id: "immigration", label: t(lang, "immigration"), Icon: ImmigrationIcon, cat: "immigration", req: "plus" },
    { id: "employment", label: t(lang, "employment"), Icon: EmploymentIcon, cat: "employment", req: "plus" },
    { id: "property", label: t(lang, "property"), Icon: PropertyIcon, cat: "property", req: "plus" },
    { id: "medical", label: t(lang, "medical"), Icon: MedicalIcon, cat: "medical_negligence", req: "plus" },
  ];

  const onTile = (tile) => {
    if (!hasTier(tile.req)) {
      setSubPreset(tile.req === "pro" ? "pro" : "plus");
      setShowSub(true);
      return;
    }
    if (tile.id === "files") setModal({ type: "files" });
    else if (tile.id === "cases") setModal({ type: "cases" });
    else if (tile.id === "reminders") setModal({ type: "reminders" });
    else if (tile.id === "recycle") setModal({ type: "recycle" });
    else if (tile.id === "letter") setModal({ type: "letter_lib" });
    else if (tile.id === "record") setModal({ type: "record" });
    else if (tile.id === "snap") setModal({ type: "snap" });
    else if (tile.id === "letter_reader") setModal({ type: "letter_reader" });
    else if (tile.id === "contracts") setModal({ type: "contracts" });
    else if (tile.id === "engagements") setModal({ type: "engagements" });
    else if (tile.id === "vault") setModal({ type: "vault" });
    else if (tile.id === "outcome") setModal({ type: "outcome" });
    else if (tile.id === "cost") setModal({ type: "cost" });
    else if (tile.id === "legal_aid") setModal({ type: "legal_aid" });
    else if (tile.id === "lawyers") setModal({ type: "lawyers" });
    else if (tile.id === "courtroom") setModal({ type: "courtroom" });
    else if (tile.id === "ask_lex") setModal({ type: "chat", title: t(lang, "askLex"), category: tile.cat });
    else setModal({ type: "chat", title: tile.label, category: tile.cat });
  };

  const langInfo = LANGS.find(l => l.code === lang) || LANGS[0];

  return (
    <div className="app-shell" style={{ padding: "20px 18px calc(150px + env(safe-area-inset-bottom, 0px))", maxWidth: 760, margin: "0 auto" }} data-testid="dashboard">
      {securityAlerts.length > 0 && (
        <div data-testid="security-alert-banner" style={{
          background: "linear-gradient(135deg,#3a1410,#2a0808)", border: "1px solid #7f1d1d",
          borderRadius: 12, padding: "12px 14px", marginBottom: 14,
          display: "flex", alignItems: "flex-start", gap: 12,
        }}>
          <AlertTriangle size={20} style={{ color: "#fca5a5", flexShrink: 0, marginTop: 2 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#fca5a5", marginBottom: 4 }}>{t(lang, "secAlertTitle")}</div>
            {securityAlerts.slice(0, 1).map(a => (
              <div key={a.id} style={{ fontSize: 12, color: "#fecaca", lineHeight: 1.5 }}>
                {a.kind === "login_country_change"
                  ? t(lang, "secAlertCountryChange", { from: a.from_country, to: a.to_country })
                  : t(lang, "secAlertGeneric")}
              </div>
            ))}
            {securityAlerts.length > 1 && <div style={{ fontSize: 11, color: "#888", marginTop: 4 }}>+ {securityAlerts.length - 1} more</div>}
            <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
              <button data-testid="security-ack-btn" onClick={async () => {
                for (const a of securityAlerts) {
                  try { await api.post(`/security/events/${a.id}/ack`); } catch (e) { /* no-op */ }
                }
                setSecurityAlerts([]);
              }} style={{ background: "#fca5a5", color: "#1a0808", border: "none", padding: "6px 12px", borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
                {t(lang, "secAlertItWasMe")}
              </button>
              <button data-testid="security-change-pwd-btn" onClick={() => setShowSettings(true)} style={{ background: "transparent", border: "1px solid #fca5a5", color: "#fca5a5", padding: "6px 12px", borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: "pointer" }}>
                {t(lang, "secAlertChangePwd")}
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{t(lang, "hi")}, <span style={{ color: "var(--gold)" }}>{user.full_name || user.email.split("@")[0]}</span></div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowSettings(true)} data-testid="settings-btn" title={t(lang, "settings")}
                  style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--gold)", borderRadius: "50%", width: 34, height: 34, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <SettingsIcon size={16} />
          </button>
          <button onClick={() => setShowLang(true)} data-testid="lang-toggle-btn"
                  style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--gold)", borderRadius: 20, padding: "5px 10px", fontSize: 13, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Flag cc={langInfo.cc} size={14} />
            {langInfo.code.split("-")[0].toUpperCase()}
          </button>
          <button onClick={onLogout} data-testid="logout-btn" title={t(lang, "logout")}
                  style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--text-dim)", borderRadius: "50%", width: 34, height: 34, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <LogOut size={16} />
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginTop: 6, marginBottom: 14 }}>
        <Logo lang={lang} />
      </div>

      <DailyTipCard lang={lang} country={country} />

      <button data-testid="emergency-btn" onClick={() => setShowEmergency(true)}
        style={{ width: "100%", padding: "12px 16px", marginBottom: 14, borderRadius: 14,
                 background: "linear-gradient(135deg, #b91c1c 0%, #7f1d1d 100%)",
                 border: "1px solid #fca5a5", color: "#fff", fontWeight: 700,
                 letterSpacing: "0.04em", fontSize: 14, cursor: "pointer",
                 boxShadow: "0 0 18px rgba(220,38,38,0.55)", display: "flex",
                 alignItems: "center", justifyContent: "center", gap: 8,
                 fontFamily: "Cinzel, serif", textTransform: "uppercase" }}>
        <span style={{ fontSize: 18 }}>⚠</span> {t(lang, "arrestedBtn")}
      </button>

      {tier === "free" && !IS_NATIVE && (
        <div className="trial-banner" data-testid="trial-banner-free" style={{ marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{t(lang, "freePlanUnlock")}</span>
          <button className="btn-gold" data-testid="open-subscribe-btn" onClick={() => { setSubPreset("plus"); setShowSub(true); }} style={{ padding: "8px 14px", fontSize: 13 }}>
            {t(lang, "upgrade")}
          </button>
        </div>
      )}
      {tier === "free" && IS_NATIVE && (
        <div className="trial-banner" data-testid="trial-banner-free-native" style={{ marginBottom: 14, fontSize: 12 }}>
          <span>{t(lang, "freePlanUnlock")} — </span>
          <a href="https://aiadvocate.co.uk/subscribe" style={{ color: "var(--gold)", textDecoration: "underline" }}>aiadvocate.co.uk/subscribe</a>
        </div>
      )}
      {/* 🎁 Comp-Pro gift banner — fires once for users who've been comped by the owner.
          Tied to the specific `comp_pro_until` timestamp so re-comping shows it again. */}
      <CompGiftBanner user={user} lang={lang} />
      {tier === "trial_pro" && (
        <div className="trial-banner" data-testid="trial-banner" style={{ marginBottom: 14 }}>
          {t(lang, "trialDays", { n: user.trial_days_remaining })}
        </div>
      )}
      {tier === "plus" && (
        <div className="trial-banner" data-testid="tier-banner-plus" style={{ marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{t(lang, "plusActiveUpgrade")}</span>
          <button className="btn-gold" data-testid="open-pro-upgrade-btn" onClick={() => { setSubPreset("pro"); setShowSub(true); }} style={{ padding: "8px 14px", fontSize: 13 }}>
            {t(lang, "goPro")}
          </button>
        </div>
      )}
      {(tier === "pro" || tier === "yearly") && user.subscription_status === "active" && (
        <div className="trial-banner" data-testid="tier-banner-pro" style={{ marginBottom: 14, opacity: 0.85 }}>
          {t(lang, "proActiveFull", { tier: tier === "yearly" ? t(lang, "yearlyPro") : t(lang, "pro") })}
        </div>
      )}
      {/* 🎟 Active one-off top-up status pill */}
      {user.topup_active && user.topup_active.expires_at && (
        <div data-testid="topup-active-pill" style={{
          marginBottom: 14, padding: "10px 12px",
          background: "linear-gradient(135deg, rgba(247,201,72,0.20), rgba(247,201,72,0.05))",
          border: "1px solid var(--gold-deep)", borderRadius: 12,
          display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10,
        }}>
          <div>
            <div style={{ fontSize: 10.5, color: "var(--gold)", fontWeight: 800, letterSpacing: "0.05em" }}>ACTIVE TOP-UP</div>
            <div style={{ fontSize: 12.5, color: "#fff" }}>
              {user.topup_active.label || "Pack"} · grants <strong style={{ color: "var(--gold)" }}>{(user.topup_active.grants_tier || "plus").toUpperCase()}</strong>
              {typeof user.topup_active.hours_remaining === "number" && (
                <span style={{ color: "var(--text-muted)" }}> · {user.topup_active.hours_remaining}h left</span>
              )}
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4, rowGap: 18 }}>
        {tiles.map(tile => {
          const locked = !hasTier(tile.req);
          return (
            <button key={tile.id} className="tile-clean" data-testid={`tile-${tile.id}`} onClick={() => onTile(tile)}
                    style={{ position: "relative", opacity: locked ? 0.55 : 1 }}>
              <tile.Icon size={48} />
              <div className="tile-clean-title">{tile.label}</div>
              {tile.sub && <div className="tile-clean-sub">{tile.sub}</div>}
              {locked && (
                <div data-testid={`lock-${tile.id}`} style={{
                  position: "absolute", top: 4, right: 4,
                  background: tile.req === "pro" ? "linear-gradient(135deg,#7f1d1d,#dc2626)" : "var(--gold)",
                  color: tile.req === "pro" ? "#fff" : "#1a1300",
                  fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 6,
                  letterSpacing: "0.06em", textTransform: "uppercase",
                }}>
                  🔒 {tile.req}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* StatsWall hidden until we have real user counts post-launch */}
      {/* <StatsWall lang={lang} /> */}

      {/* Suggest-a-feature inline link — captures user demand for new legal areas */}
      <div style={{ textAlign: "center", padding: "20px 16px 16px", display: "flex", flexDirection: "column", gap: 10, alignItems: "center" }}>
        <button data-testid="open-timeline-btn" onClick={() => setShowTimeline(true)}
                style={{ background: "linear-gradient(135deg, rgba(247,201,72,0.10), rgba(247,201,72,0.02))", border: "1px solid var(--gold)", borderRadius: 12, padding: "12px 22px", color: "var(--gold)", fontSize: 13, fontWeight: 600, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 10, letterSpacing: "0.04em" }}>
          <img src="/icons/files.png" alt="" style={{ width: 18, height: 18, objectFit: "contain" }} /> Case Timeline
        </button>
        <button data-testid="suggest-feature-btn" onClick={() => setShowSuggest(true)}
                style={{ background: "transparent", border: "1px dashed var(--gold-deep)", borderRadius: 10, padding: "10px 18px", color: "var(--gold)", fontSize: 12, cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 8 }}>
          <SuggestIcon size={14} /> {t(lang, "suggestPrompt")}
        </button>
      </div>

      {showSuggest && <SuggestFeatureModal lang={lang} onClose={() => setShowSuggest(false)} />}
      {showTimeline && <CaseTimeline lang={lang} onClose={() => setShowTimeline(false)}
        onOpenChat={(sid) => { setShowTimeline(false); setModal({ type: "chat", category: "ask_lex", title: "Lex", _resumeSession: sid }); }}
        onOpenReminders={() => { setShowTimeline(false); setModal({ type: "reminders" }); }}
        onOpenCase={(cid) => { setShowTimeline(false); setModal({ type: "cases", _openCaseId: cid }); }}
      />}

      <SponsorFooter />

      <BottomNav lang={lang} active="home"
        badges={{ reminders: casesBadge }}
        onNav={(k) => {
          if (k === "lex") {
            // Tapping Lex centre button → open Siri-style Voice Mode (Plus+ only)
            if (!hasTier("plus")) { setSubPreset("plus"); setShowSub(true); return; }
            setVoiceMode({ initialText: "" });
          }
          else if (k === "vault") setModal({ type: "vault" });
          else if (k === "cases") setModal({ type: "cases" });
          else if (k === "lawyers") setModal({ type: "lawyers" });
          else if (k === "reminders") setModal({ type: "reminders" });
          else if (k === "hearing") setModal({ type: "hearing" });
          else if (k === "letter") setModal({ type: "letter_lib" });
          else if (k === "contracts") setModal({ type: "contracts" });
          else if (k === "legal_aid") setModal({ type: "legal_aid" });
        }} hasAccess={true} requireSub={() => setShowSub(true)} />

      {modal?.type === "chat" && <LexChat lang={lang} country={country} category={modal.category} title={modal.title} autoMic={!!modal.autoMic} initialSeed={modal._initialSeed || ""} tier={tier} onClose={() => setModal(null)} onSwitchCategory={(newCat) => {
        const labelByCat = { employment: t(lang, "employment"), property: t(lang, "property"), immigration: t(lang, "immigration"), medical_negligence: t(lang, "medical") };
        if (!hasTier("plus")) { setSubPreset("plus"); setShowSub(true); return; }
        setModal({ type: "chat", category: newCat, title: labelByCat[newCat] || "Lex" });
      }} />}
      {modal?.type === "courtroom" && <CourtroomModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "letter_lib" && <LetterLibraryModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "files" && <FilesModal lang={lang} onClose={() => setModal(null)} />}
      {modal?.type === "cases" && <CaseFilesModal lang={lang} openCaseId={modal._openCaseId} onClose={() => setModal(null)} />}
      {modal?.type === "reminders" && <RemindersModal lang={lang} onClose={() => setModal(null)} />}
      {modal?.type === "recycle" && <RecycleBinModal lang={lang} onClose={() => setModal(null)} />}
      {modal?.type === "letter" && <LegalLetterModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "record" && <RecordHub lang={lang} country={country} user={user} hasTier={hasTier} onUpsell={() => { setSubPreset("pro"); setShowSub(true); }} onClose={() => setModal(null)} />}
      {modal?.type === "snap" && <SnapEvidenceModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "letter_reader" && <LetterReaderModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "contracts" && <ContractsHubModal lang={lang} country={country} hasTier={hasTier} onUpsell={() => { setSubPreset("pro"); setShowSub(true); }} onClose={() => setModal(null)} />}
      {modal?.type === "vault" && <VaultModal lang={lang} hasTier={hasTier} onUpsell={() => { setSubPreset("pro"); setShowSub(true); }} onClose={() => setModal(null)} />}
      {modal?.type === "engagements" && <EngagementsModal lang={lang} country={country} user={user} onClose={() => setModal(null)} />}
      {modal?.type === "outcome" && <OutcomeModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "cost" && <CostEstimateModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "hearing" && <HearingRecorderModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {/* Legacy "hearing" tile id removed — merged into "record" via RecordHub. The
          modal route above stays for any external aa:open-modal events that still target it. */}
      {modal?.type === "legal_aid" && <LegalAidModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "lawyers" && <LawyersModal lang={lang} country={country} user={user} onClose={() => setModal(null)} openAdvertise={() => { setModal(null); setShowAdvertise(true); }} />}
      {showEmergency && <EmergencyModal lang={lang} country={country} user={user} onClose={() => setShowEmergency(false)} />}
      {voiceMode && <VoiceModeOverlay lang={lang} country={country} category="ask_lex" initialText={voiceMode.initialText} onClose={() => setVoiceMode(null)} />}
      {showLang && <LanguagePicker initial={lang} lang={lang} onConfirm={(l) => { setLang(l); setShowLang(false); api.patch("/auth/preferences", { language: l }).catch(() => {}); }} />}
      {showSub && <SubscribeModal lang={lang} user={user} presetPlan={subPreset} onClose={() => setShowSub(false)} onActivated={(u) => { refreshUser(u); setShowSub(false); }} />}
      {showSettings && <SettingsModal lang={lang} country={country} user={user} onClose={() => setShowSettings(false)} onUpdate={(u) => refreshUser(u)} setLang={setLang} setCountry={setCountry} />}
      {showAdvertise && <AdvertiseModal lang={lang} onClose={() => setShowAdvertise(false)} />}
      {reviewPrompt && <ReviewPrompt lang={lang} daysLeft={reviewPrompt.daysLeft} onClose={() => setReviewPrompt(null)} />}
      {topupToast && (
        <div data-testid="topup-toast" onClick={() => setTopupToast(null)}
          style={{
            position: "fixed", top: 16, left: "50%", transform: "translateX(-50%)",
            background: topupToast === "cancel" ? "rgba(80,10,10,0.95)" : "linear-gradient(135deg, rgba(247,201,72,0.95), rgba(220,175,40,0.95))",
            color: topupToast === "cancel" ? "#fff" : "#1a1300",
            border: `2px solid ${topupToast === "cancel" ? "#dc2626" : "var(--gold)"}`,
            borderRadius: 14, padding: "12px 18px", fontSize: 13, fontWeight: 700,
            boxShadow: "0 6px 30px rgba(0,0,0,0.4)", zIndex: 9999, cursor: "pointer",
            maxWidth: "92%", textAlign: "center",
          }}>
          {topupToast === "cancel"
            ? "Top-up cancelled — no charge was made."
            : `✓ Top-up activated! Your ${(topupToast.pack || "").replace(/_/g, " ")} is now live.`}
        </div>
      )}
    </div>
  );
}

// ---------- Outcome Predictor ----------
function OutcomeModal({ lang, country, onClose }) {
  const [summary, setSummary] = useState("");
  const [category, setCategory] = useState("");
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");
  const run = async () => {
    setBusy(true); setErr("");
    try {
      const { data } = await api.post("/outcome/predict", { case_summary: summary, category, language: lang, country });
      setR(data);
    } catch (e) { setErr(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  const pct = r?.success_probability_pct ?? 0;
  const ringColor = pct >= 70 ? "#22c55e" : pct >= 40 ? "#f7c948" : "#ef4444";
  return (
    <div className="modal-bg" data-testid="outcome-modal">
      <div className="modal-card" style={{ padding: 20, overflowY: "auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "outcomeTitle")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        {!r ? (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 12 }}>Describe your case in your own words. Lex gives a realistic % chance and cites similar past cases.</p>
            <textarea className="input" rows={6} value={summary} onChange={(e) => setSummary(e.target.value)} data-testid="outcome-summary" placeholder="e.g. My landlord didn't protect my deposit in a scheme and only returned it 6 months after I moved out…" style={{ marginBottom: 8 }} />
            <input className="input" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Category (employment / property / immigration…)" data-testid="outcome-category" style={{ marginBottom: 8 }} />
            {err && <div style={{ color: "#fca5a5", fontSize: 13, marginBottom: 8 }}>{err}</div>}
            <button className="btn-gold w-full" disabled={busy || summary.trim().length < 20} onClick={run} data-testid="outcome-run-btn">
              {busy ? <span className="spinner" /> : "Predict outcome"}
            </button>
          </>
        ) : (
          <div data-testid="outcome-result">
            <div style={{ display: "flex", justifyContent: "center", marginBottom: 14 }}>
              <div style={{ width: 130, height: 130, borderRadius: "50%", border: `8px solid ${ringColor}`, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <div style={{ fontSize: 32, fontWeight: 700, color: ringColor }}>{pct}%</div>
                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>chance of success</div>
              </div>
            </div>
            <div style={{ color: "var(--gold)", fontSize: 13, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 6 }}>Strategy</div>
            <p style={{ color: "var(--text)", fontSize: 14, lineHeight: 1.6, marginBottom: 14 }}>{r.recommended_strategy}</p>
            {r.key_factors_for?.length > 0 && (
              <>
                <div style={{ color: "#22c55e", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "10px 0 6px" }}>Working for you</div>
                <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.6 }}>{r.key_factors_for.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </>
            )}
            {r.key_factors_against?.length > 0 && (
              <>
                <div style={{ color: "#ef4444", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "10px 0 6px" }}>Risks</div>
                <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.6 }}>{r.key_factors_against.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </>
            )}
            {r.similar_cases?.length > 0 && (
              <>
                <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "14px 0 6px" }}>Similar Past Cases</div>
                {r.similar_cases.map((c, i) => (
                  <div key={i} style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, marginBottom: 6 }}>
                    <div style={{ color: "var(--gold)", fontSize: 13, fontWeight: 600 }}>{c.name}</div>
                    <div style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 2 }}>{c.outcome}</div>
                  </div>
                ))}
              </>
            )}
            <button className="btn-ghost w-full" onClick={() => { setR(null); setSummary(""); setCategory(""); }} style={{ marginTop: 14 }}>Predict another case</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Lawyer Cost Estimator ----------
function CostEstimateModal({ lang, country, onClose }) {
  const [summary, setSummary] = useState("");
  const [category, setCategory] = useState("");
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState(null);
  const run = async () => {
    setBusy(true);
    try { const { data } = await api.post("/cost/estimate", { case_summary: summary, category, country, language: lang }); setR(data); }
    catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-bg" data-testid="cost-modal">
      <div className="modal-card" style={{ padding: 20, overflowY: "auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "costTitle")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        {!r ? (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 12 }}>Find out roughly what a solicitor would charge for your matter.</p>
            <textarea className="input" rows={5} value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="Brief description of your case…" data-testid="cost-summary" style={{ marginBottom: 8 }} />
            <input className="input" value={category} onChange={(e) => setCategory(e.target.value)} placeholder="Category (optional)" data-testid="cost-category" style={{ marginBottom: 8 }} />
            <button className="btn-gold w-full" disabled={busy || summary.trim().length < 20} onClick={run} data-testid="cost-run-btn">
              {busy ? <span className="spinner" /> : "Estimate cost"}
            </button>
          </>
        ) : (
          <div data-testid="cost-result">
            <div style={{ textAlign: "center", margin: "8px 0 18px" }}>
              <div style={{ color: "var(--text-muted)", fontSize: 12, textTransform: "uppercase", letterSpacing: "0.1em" }}>Likely solicitor fee</div>
              <div style={{ color: "var(--gold)", fontSize: 32, fontWeight: 700, marginTop: 4 }}>£{r.low_estimate_gbp?.toLocaleString()} – £{r.high_estimate_gbp?.toLocaleString()}</div>
              <div style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 2 }}>+ court fees ≈ £{r.court_fees_gbp || 0}</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
              <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, textAlign: "center" }}>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>Typical hours</div>
                <div style={{ color: "var(--text)", fontWeight: 600 }}>{r.typical_hours}</div>
              </div>
              <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, textAlign: "center" }}>
                <div style={{ color: "var(--text-muted)", fontSize: 11 }}>Hourly rate</div>
                <div style={{ color: "var(--text)", fontWeight: 600 }}>£{r.hourly_rate_range_gbp}</div>
              </div>
            </div>
            {r.no_win_no_fee_available && (
              <div style={{ background: "rgba(34,197,94,0.1)", border: "1px solid #22c55e", color: "#86efac", padding: 10, borderRadius: 10, fontSize: 13, marginBottom: 12 }}>
                ✓ No Win No Fee may be available for this type of case.
              </div>
            )}
            <p style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.6, marginBottom: 14 }}>{r.explanation}</p>
            <div style={{ background: "linear-gradient(135deg, rgba(247,201,72,0.12), rgba(247,201,72,0.02))", border: "1px solid var(--gold)", borderRadius: 12, padding: 12, fontSize: 13, color: "var(--text)" }}>
              <strong style={{ color: "var(--gold)" }}>AI Advocate covers this from £19.99/mo</strong>
              <div style={{ color: "var(--text-dim)", marginTop: 4 }}>{r.ai_advocate_saving}</div>
            </div>
            <button className="btn-ghost w-full" onClick={() => { setR(null); setSummary(""); }} style={{ marginTop: 12 }}>Estimate another</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Legal Aid Finder ----------
function LegalAidModal({ lang, country, onClose }) {
  const [form, setForm] = useState({ monthly_income_gbp: "", savings_gbp: "", household_size: 1, case_category: "" });
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState(null);
  const run = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/legal-aid/check", {
        monthly_income_gbp: parseFloat(form.monthly_income_gbp) || 0,
        savings_gbp: parseFloat(form.savings_gbp) || 0,
        household_size: parseInt(form.household_size) || 1,
        case_category: form.case_category, country, language: lang,
      });
      setR(data);
    } catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-bg" data-testid="legal-aid-modal">
      <div className="modal-card" style={{ padding: 20, overflowY: "auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "legalAidTitle")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        {!r ? (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 12 }}>Quick check — are you eligible for free legal aid or pro-bono help? Indicative only.</p>
            <input className="input" type="number" placeholder="Monthly income (£)" value={form.monthly_income_gbp} onChange={(e) => setForm({ ...form, monthly_income_gbp: e.target.value })} data-testid="la-income" style={{ marginBottom: 8 }} />
            <input className="input" type="number" placeholder="Total savings (£)" value={form.savings_gbp} onChange={(e) => setForm({ ...form, savings_gbp: e.target.value })} data-testid="la-savings" style={{ marginBottom: 8 }} />
            <input className="input" type="number" placeholder="Household size" value={form.household_size} onChange={(e) => setForm({ ...form, household_size: e.target.value })} data-testid="la-household" style={{ marginBottom: 8 }} />
            <input className="input" placeholder="Case category (e.g. eviction)" value={form.case_category} onChange={(e) => setForm({ ...form, case_category: e.target.value })} data-testid="la-category" style={{ marginBottom: 8 }} />
            <button className="btn-gold w-full" disabled={busy || !form.monthly_income_gbp} onClick={run} data-testid="la-run-btn">
              {busy ? <span className="spinner" /> : "Check eligibility"}
            </button>
          </>
        ) : (
          <div data-testid="legal-aid-result">
            <div style={{ background: r.qualifies ? "rgba(34,197,94,0.1)" : "rgba(247,201,72,0.1)", border: `1px solid ${r.qualifies ? "#22c55e" : "var(--gold-deep)"}`, borderRadius: 12, padding: 14, marginBottom: 14 }}>
              <div style={{ color: r.qualifies ? "#86efac" : "var(--gold)", fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
                {r.qualifies ? "✓ Likely eligible" : "Probably not eligible"}
              </div>
              {(r.reasons || []).map((re, i) => <div key={i} style={{ color: "var(--text-dim)", fontSize: 13, marginTop: 4 }}>{re}</div>)}
            </div>
            <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", marginBottom: 8 }}>Free help near you</div>
            {(r.signposts || []).map((s, i) => (
              <a key={i} href={s.url} target="_blank" rel="noreferrer"
                 style={{ display: "block", background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 12, marginBottom: 6, color: "var(--text)", textDecoration: "none" }}>
                <div style={{ color: "var(--gold)", fontWeight: 600, fontSize: 14 }}>{s.name}</div>
                <div style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 2 }}>{s.url}</div>
              </a>
            ))}
            <p style={{ color: "var(--text-muted)", fontSize: 11, marginTop: 14, lineHeight: 1.5 }}>{r.disclaimer}</p>
            <button className="btn-ghost w-full" onClick={() => setR(null)} style={{ marginTop: 8 }}>Run another check</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Hearing Recorder ----------
function HearingRecorderModal({ lang, country, onClose }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState(null);
  const [recordingTitle, setRecordingTitle] = useState("");
  const fileRef = useRef(null);
  const { ensureConsent, GateModal } = useRecordingConsent({ lang, country, surface: "hearing", recordingTitle });

  // ---- Live recording state ----
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);    // seconds
  const mediaRecorderRef = useRef(null);
  const recChunksRef = useRef([]);
  const streamRef = useRef(null);
  const timerRef = useRef(null);

  const startRecording = async () => {
    if (recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
      const mr = new MediaRecorder(stream, { mimeType: mime });
      recChunksRef.current = [];
      mr.ondataavailable = (ev) => { if (ev.data && ev.data.size > 0) recChunksRef.current.push(ev.data); };
      mr.onstop = () => {
        const blob = new Blob(recChunksRef.current, { type: mime });
        const f = new File([blob], `hearing-${Date.now()}.webm`, { type: mime });
        setFile(f);
        // stop the mic track so the red dot in browser goes away
        streamRef.current?.getTracks().forEach(t => t.stop());
        streamRef.current = null;
      };
      mediaRecorderRef.current = mr;
      mr.start();
      setRecording(true); setElapsed(0);
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
    } catch (e) {
      alert(e?.message || "Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (!recording) return;
    setRecording(false);
    clearInterval(timerRef.current);
    try { mediaRecorderRef.current?.stop(); } catch (e) {}
  };

  // Cleanup when modal closes
  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach(t => t.stop());
  }, []);

  const fmtTime = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("audio", file); fd.append("language", lang); fd.append("country", country);
      const { data } = await api.post("/hearing/transcribe", fd);
      setR(data);
    } catch (e) { alert(e?.response?.data?.detail || "Transcription failed"); }
    finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="hearing-modal">
      <div className="modal-card" style={{ padding: 20, overflowY: "auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "hearingTitle")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        {!r ? (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 12 }}>{t(lang, "hearingIntro")}</p>

            {/* LIVE RECORDING */}
            <div style={{ background: "var(--bg-card)", border: `1px solid ${recording ? "#ef4444" : "var(--line)"}`, borderRadius: 12, padding: 14, marginBottom: 12, textAlign: "center" }}>
              {recording ? (
                <>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 8 }}>
                    <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ef4444", display: "inline-block", animation: "pulse 1.5s infinite" }}></span>
                    <span style={{ color: "#ef4444", fontWeight: 700, fontSize: 13 }}>RECORDING</span>
                  </div>
                  <div style={{ color: "var(--gold)", fontFamily: "Cinzel, serif", fontSize: 28, marginBottom: 8 }}>{fmtTime(elapsed)}</div>
                  <button data-testid="hearing-rec-stop" className="btn-gold" onClick={stopRecording}
                          style={{ background: "#ef4444", color: "#fff", width: "100%", padding: 12 }}>
                    {t(lang, "stop") || "Stop recording"}
                  </button>
                </>
              ) : file ? (
                <>
                  <div style={{ color: "var(--gold)", fontSize: 13, marginBottom: 8 }}>
                    ✓ Recording ready ({(file.size / 1024 / 1024).toFixed(1)} MB)
                  </div>
                  <button data-testid="hearing-rec-restart" className="btn-ghost" onClick={() => { setFile(null); }} style={{ width: "100%", padding: 8, fontSize: 12 }}>
                    Discard & record again
                  </button>
                </>
              ) : (
                <button data-testid="hearing-rec-start" className="btn-gold" onClick={ensureConsent(startRecording)}
                        style={{ width: "100%", padding: 12 }}>
                  <Mic size={16} style={{ display: "inline", marginRight: 6 }} />
                  Record now
                </button>
              )}
            </div>

            {/* OR — upload an existing file */}
            {!recording && !file && (
              <>
                <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 12, margin: "10px 0" }}>— or —</div>
                <input ref={fileRef} type="file" accept="audio/*,video/*" onChange={(e) => setFile(e.target.files?.[0])} style={{ display: "none" }} data-testid="hearing-file-input" />
                <button className="btn-ghost w-full" onClick={ensureConsent(() => fileRef.current?.click())} data-testid="hearing-pick-btn">
                  Upload existing audio file
                </button>
              </>
            )}

            {file && !busy && !recording && (
              <button className="btn-gold w-full" onClick={upload} data-testid="hearing-upload-btn" style={{ marginTop: 10 }}>
                {t(lang, "hearingUploadBtn")}
              </button>
            )}
            {busy && <div style={{ textAlign: "center", padding: 16 }}><span className="spinner" /><div style={{ color: "var(--text-dim)", marginTop: 8, fontSize: 13 }}>{t(lang, "hearingBusy") || "Transcribing — this can take a minute…"}</div></div>}
          </>
        ) : (
          <div data-testid="hearing-result">
            <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", marginBottom: 6 }}>{t(lang, "hearingSummary")}</div>
            <p style={{ color: "var(--text)", fontSize: 14, lineHeight: 1.6, marginBottom: 12 }}>{r.analysis?.summary}</p>
            {r.analysis?.favourable_moments?.length > 0 && (<>
              <div style={{ color: "#22c55e", fontSize: 12, fontWeight: 700, textTransform: "uppercase", marginBottom: 4 }}>{t(lang, "hearingWorked") || "Worked for you"}</div>
              <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.6 }}>{r.analysis.favourable_moments.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>)}
            {r.analysis?.unfavourable_moments?.length > 0 && (<>
              <div style={{ color: "#ef4444", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "10px 0 4px" }}>{t(lang, "hearingRisks") || "Risks"}</div>
              <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.6 }}>{r.analysis.unfavourable_moments.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>)}
            {r.analysis?.next_actions?.length > 0 && (<>
              <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "10px 0 4px" }}>{t(lang, "hearingNextActions") || "Next actions"}</div>
              <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.6 }}>{r.analysis.next_actions.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>)}
            <details style={{ marginTop: 14 }}>
              <summary style={{ color: "var(--gold)", fontSize: 13, cursor: "pointer" }}>{t(lang, "hearingFullTranscript") || "Full transcript"}</summary>
              <pre style={{ background: "#0a0a0a", padding: 10, borderRadius: 8, color: "var(--text-dim)", fontSize: 12, whiteSpace: "pre-wrap", marginTop: 8 }}>{r.transcript}</pre>
            </details>
            {/* Save the hearing's transcript + analysis bundle into the Vault. The
                transcribe endpoint already persisted a legal_file row (returned as r.id);
                we re-use that to wire up save-to-vault. */}
            <button data-testid="hearing-vault-save" className="btn-ghost w-full"
              onClick={async () => {
                if (!r?.id) { aaToast("Save unavailable — please re-transcribe.", "error"); return; }
                try {
                  const bundle = JSON.stringify({ transcript: r.transcript, analysis: r.analysis }, null, 2);
                  await api.post(`/legal-files/${r.id}/save-to-vault`, {
                    file_id: r.id,
                    encrypted_content: btoa(unescape(encodeURIComponent(bundle))),
                    iv: "hearing-shim",
                    label: `Hearing — ${new Date().toLocaleDateString()}`,
                  });
                  aaToast("Hearing saved to Vault", "success");
                } catch (e) { aaToast(e?.response?.data?.detail || "Save failed", "error"); }
              }}
              style={{ marginTop: 12, padding: "10px 14px", fontSize: 13 }}>
              <ShieldCheck size={14} style={{ display: "inline", marginRight: 6 }} />
              Save to Vault
            </button>
          </div>
        )}
      </div>
      {GateModal}
    </div>
  );
}


// ============================== LEX VAULT ==============================
// Zero-knowledge encrypted storage. PIN never leaves the device.

const VAULT_CATEGORIES = [
  { id: "evidence", label: "Evidence" },
  { id: "contracts", label: "Contracts" },
  { id: "letters", label: "Letters" },
  { id: "id", label: "ID Docs" },
  { id: "witness", label: "Witness" },
  { id: "court", label: "Court" },
  { id: "other", label: "Other" },
];

function VaultModal({ lang, hasTier, onUpsell, onClose }) {
  const VC = require("./vaultCrypto");
  const BIO = require("./vaultBiometric");
  const [stage, setStage] = useState("loading"); // loading | setup | locked | unlocked
  const [pinSalt, setPinSalt] = useState(null);
  const [pin, setPin] = useState("");
  const [pinConfirm, setPinConfirm] = useState("");
  const [err, setErr] = useState("");
  const [items, setItems] = useState([]);
  const [adding, setAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newCategory, setNewCategory] = useState("evidence");
  const [newNotes, setNewNotes] = useState("");
  const [newFile, setNewFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showWipeConfirm, setShowWipeConfirm] = useState(false);
  const uploadRef = useRef(null);
  const [decNotes, setDecNotes] = useState({});
  const [bioSupported, setBioSupported] = useState(false);
  const [bioEnabled, setBioEnabled] = useState(false);
  const [bioBusy, setBioBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const supported = await BIO.isBiometricSupported();
        if (alive) { setBioSupported(supported); setBioEnabled(BIO.isBiometricEnabled()); }
        const { data } = await api.get("/vault/status");
        if (!alive) return;
        if (!data.setup) setStage("setup");
        else { setPinSalt(data.pin_salt); setStage("locked"); }
      } catch (e) { setErr("Could not load vault."); }
    })();
    return () => { alive = false; };
  }, []);

  const refreshItems = async () => {
    const { data } = await api.get("/vault/items");
    setItems(data.items || []);
  };

  // Attempts biometric unlock — verifies the recovered PIN against the server.
  const doBiometricUnlock = async () => {
    setErr(""); setBioBusy(true);
    try {
      const recoveredPin = await BIO.unlockWithBiometric();
      const verifier = await VC.pinVerifier(recoveredPin, pinSalt);
      await api.post("/vault/unlock", { pin_verifier: verifier });
      track("vault_unlocked", { method: "biometric" });
      setPin(recoveredPin);
      setStage("unlocked");
      await refreshItems();
    } catch (e) {
      // If the stored PIN no longer matches the server (e.g. user wiped+re-setup), clear bio
      if (e?.response?.status === 401) {
        BIO.disableBiometric();
        setBioEnabled(false);
        setErr("Biometric data is out of date. Please unlock with your PIN and re-enable.");
      } else {
        setErr(e?.message || "Biometric unlock failed");
      }
    } finally { setBioBusy(false); }
  };

  const doEnableBiometric = async () => {
    if (!pin) { alert("PIN unavailable — please re-unlock and try again."); return; }
    setBioBusy(true);
    try {
      await BIO.enableBiometric(pin);
      setBioEnabled(true);
    } catch (e) {
      alert(e?.message || "Could not enable biometric");
    } finally { setBioBusy(false); }
  };

  const doDisableBiometric = () => {
    if (!confirm("Disable biometric unlock? You'll need your PIN next time.")) return;
    BIO.disableBiometric();
    setBioEnabled(false);
  };

  const doSetup = async () => {
    setErr("");
    if (pin.length < 4) { setErr("PIN must be at least 4 characters."); return; }
    if (pin !== pinConfirm) { setErr("PINs don't match."); return; }
    setBusy(true);
    try {
      const salt = VC.generateSalt();
      const verifier = await VC.pinVerifier(pin, salt);
      await api.post("/vault/setup", { pin_verifier: verifier, pin_salt: salt });
      setPinSalt(salt);
      setStage("unlocked");
      setPinConfirm("");
      await refreshItems();
    } catch (e) {
      setErr(e?.response?.data?.detail || "Setup failed.");
    } finally { setBusy(false); }
  };

  const doUnlock = async () => {
    setErr("");
    if (!pin) { setErr("Enter your PIN."); return; }
    setBusy(true);
    try {
      const verifier = await VC.pinVerifier(pin, pinSalt);
      await api.post("/vault/unlock", { pin_verifier: verifier });
      track("vault_unlocked", { method: "pin" });
      setStage("unlocked");
      await refreshItems();
    } catch (e) {
      setErr(e?.response?.status === 401 ? "Incorrect PIN." : "Unlock failed.");
      setPin("");
    } finally { setBusy(false); }
  };

  const handleFile = (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    if (f.size > 12 * 1024 * 1024) { alert("Max file size is 12MB."); return; }
    setNewFile(f);
    if (!newTitle) setNewTitle(f.name.replace(/\.[^.]+$/, ""));
  };

  const addItem = async () => {
    if (!newFile || !newTitle) return;
    setBusy(true); setErr("");
    try {
      const { file_b64, file_iv } = await VC.encryptBlob(pin, pinSalt, newFile);
      let notesPayload = { notes: null, note_iv: null };
      if (newNotes) {
        const enc = await VC.encryptText(pin, pinSalt, newNotes);
        notesPayload = { notes: enc.ct, note_iv: enc.iv };
      }
      await api.post("/vault/items", {
        title: newTitle, category: newCategory, ...notesPayload,
        file_b64, file_iv,
        file_mime: newFile.type || "application/octet-stream",
        file_name: newFile.name, file_size_bytes: newFile.size,
      });
      setAdding(false); setNewFile(null); setNewTitle(""); setNewNotes(""); setNewCategory("evidence");
      await refreshItems();
    } catch (e) {
      setErr(e?.response?.data?.detail || "Add failed.");
    } finally { setBusy(false); }
  };

  const downloadItem = async (it) => {
    try {
      const { data } = await api.get(`/vault/items/${it.id}`);
      // Strip the server's outer "enc:v1:" prefix that decrypt_text removed; here the file_b64 came back already server-decrypted by the GET endpoint.
      const blob = await VC.decryptBlob(pin, pinSalt, data.file_b64, data.file_iv, data.file_mime);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = data.file_name || it.title || "vault-item";
      document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
    } catch (e) { alert("Could not decrypt file. Wrong PIN?"); }
  };

  const decryptAndShowNote = async (it) => {
    if (!it.notes_enc) return;
    if (decNotes[it.id]) {
      setDecNotes((s) => { const n = { ...s }; delete n[it.id]; return n; });
      return;
    }
    const plain = await VC.decryptText(pin, pinSalt, it.notes_enc, it.note_iv);
    setDecNotes((s) => ({ ...s, [it.id]: plain }));
  };

  const removeItem = async (it) => {
    if (!confirm(`Delete "${it.title}"? This cannot be undone.`)) return;
    await api.delete(`/vault/items/${it.id}`);
    await refreshItems();
  };

  const doWipe = async () => {
    setBusy(true);
    try {
      await api.post("/vault/wipe");
      // Clear local biometric record too — server-side PIN no longer exists
      BIO.disableBiometric();
      setBioEnabled(false);
      setStage("setup"); setPin(""); setPinSalt(null); setItems([]);
      setShowWipeConfirm(false);
    } finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="vault-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20, display: "flex", alignItems: "center", gap: 8 }}>
            <ShieldCheck size={20} /> {t(lang, "vaultTitle")}
          </h2>
          <button onClick={onClose} data-testid="vault-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>

        {stage === "loading" && <div style={{ textAlign: "center", padding: 30 }}><span className="spinner" /></div>}

        {stage === "setup" && (
          <div data-testid="vault-setup">
            <div style={{ background: "rgba(247,201,72,0.08)", border: "1px solid var(--gold-deep)", borderRadius: 10, padding: 12, marginBottom: 14 }}>
              <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <KeyRound size={13} /> {t(lang, "vaultZK")}
              </div>
              <div style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.5 }}>
                {t(lang, "vaultZKBody")}
              </div>
            </div>
            <div style={{ color: "#fca5a5", fontSize: 12, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, padding: 10, marginBottom: 14, display: "flex", gap: 8 }}>
              <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
              <span>{t(lang, "vaultLostPinWarning")}</span>
            </div>
            <input type="password" inputMode="numeric" className="input" placeholder={t(lang, "vaultPinNew")} value={pin} onChange={(e) => setPin(e.target.value)} data-testid="vault-pin-new" style={{ marginBottom: 10 }} />
            <input type="password" inputMode="numeric" className="input" placeholder={t(lang, "vaultPinConfirm")} value={pinConfirm} onChange={(e) => setPinConfirm(e.target.value)} data-testid="vault-pin-confirm" style={{ marginBottom: 10 }} />
            {err && <div style={{ color: "#fca5a5", fontSize: 13, marginBottom: 10 }}>{err}</div>}
            <button className="btn-gold w-full" onClick={doSetup} disabled={busy} data-testid="vault-setup-btn">
              {busy ? <span className="spinner" /> : (<><Lock size={14} style={{ display: "inline", marginRight: 6 }} />{t(lang, "vaultSetupCta")}</>)}
            </button>
          </div>
        )}

        {stage === "locked" && (
          <div data-testid="vault-locked">
            <div style={{ textAlign: "center", padding: "30px 20px 20px" }}>
              <Lock size={48} style={{ color: "var(--gold)", marginBottom: 14, opacity: 0.7 }} />
              <div style={{ color: "var(--text)", fontSize: 16, fontWeight: 600, marginBottom: 6 }}>{t(lang, "vaultLocked")}</div>
              <div style={{ color: "var(--text-dim)", fontSize: 13 }}>{t(lang, "vaultEnterPin")}</div>
            </div>

            {bioSupported && bioEnabled && (
              <button onClick={doBiometricUnlock} disabled={bioBusy} data-testid="vault-bio-unlock-btn"
                      style={{ width: "100%", padding: 14, marginBottom: 14, background: "linear-gradient(135deg, rgba(247,201,72,0.18), rgba(247,201,72,0.04))", border: "1px solid var(--gold)", borderRadius: 12, color: "var(--gold)", fontWeight: 600, cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                {bioBusy ? <span className="spinner" /> : (<><Fingerprint size={18} /> {t(lang, "vaultBioUnlock")}</>)}
              </button>
            )}

            <input type="password" inputMode="numeric" autoFocus className="input" placeholder={t(lang, "vaultPin")} value={pin}
                   onChange={(e) => setPin(e.target.value)} onKeyDown={(e) => e.key === "Enter" && doUnlock()}
                   data-testid="vault-pin-input" style={{ marginBottom: 10, textAlign: "center", fontSize: 18, letterSpacing: 4 }} />
            {err && <div style={{ color: "#fca5a5", fontSize: 13, marginBottom: 10, textAlign: "center" }}>{err}</div>}
            <button className="btn-gold w-full" onClick={doUnlock} disabled={busy} data-testid="vault-unlock-btn">
              {busy ? <span className="spinner" /> : (<><Unlock size={14} style={{ display: "inline", marginRight: 6 }} />{t(lang, "vaultUnlock")}</>)}
            </button>
            <button onClick={() => setShowWipeConfirm(true)} data-testid="vault-forgot-btn"
                    style={{ width: "100%", marginTop: 16, background: "transparent", border: "none", color: "var(--text-dim)", fontSize: 12, cursor: "pointer", textDecoration: "underline" }}>
              {t(lang, "vaultForgot")}
            </button>
          </div>
        )}

        {stage === "unlocked" && !adding && (
          <div data-testid="vault-unlocked">
            <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
              <button className="btn-gold" data-testid="vault-add-btn" onClick={() => setAdding(true)} style={{ flex: 1 }}>
                <Upload size={14} style={{ display: "inline", marginRight: 6 }} /> {t(lang, "vaultAddItem")}
              </button>
              <button className="btn-ghost" data-testid="vault-lock-btn" onClick={() => { setPin(""); setStage("locked"); setItems([]); setDecNotes({}); }}>
                <Lock size={14} />
              </button>
            </div>

            {bioSupported && (
              <div style={{ marginBottom: 14, padding: 10, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: "rgba(247,201,72,0.12)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Fingerprint size={16} style={{ color: "var(--gold)" }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: "var(--text)", fontSize: 12, fontWeight: 600 }}>{t(lang, "vaultBioTitle")}</div>
                  <div style={{ color: "var(--text-dim)", fontSize: 11 }}>
                    {bioEnabled ? t(lang, "vaultBioOn") : t(lang, "vaultBioOff")}
                  </div>
                </div>
                {bioEnabled ? (
                  <button onClick={doDisableBiometric} data-testid="vault-bio-disable-btn"
                          style={{ fontSize: 11, padding: "6px 10px", background: "transparent", color: "var(--text-dim)", border: "1px solid var(--line)", borderRadius: 6, cursor: "pointer" }}>
                    {t(lang, "vaultBioTurnOff")}
                  </button>
                ) : (
                  <button onClick={doEnableBiometric} disabled={bioBusy} data-testid="vault-bio-enable-btn"
                          style={{ fontSize: 11, padding: "6px 10px", background: "var(--gold)", color: "#1a1300", border: "none", borderRadius: 6, fontWeight: 700, cursor: "pointer" }}>
                    {bioBusy ? "…" : t(lang, "vaultBioTurnOn")}
                  </button>
                )}
              </div>
            )}

            {items.length === 0 ? (
              <div style={{ textAlign: "center", padding: "30px 10px", color: "var(--text-dim)", fontSize: 13 }}>
                <ShieldCheck size={40} style={{ margin: "0 auto 10px", display: "block", opacity: 0.4 }} />
                {t(lang, "vaultEmpty")}
              </div>
            ) : (
              <div>
                <div style={{ color: "var(--text-dim)", fontSize: 11, marginBottom: 8 }}>{items.length} {t(lang, "vaultItemCount")}</div>
                {items.map(it => (
                  <div key={it.id} data-testid={`vault-item-${it.id}`} style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 12, marginBottom: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 36, height: 36, borderRadius: 8, background: "rgba(247,201,72,0.12)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        <Lock size={16} style={{ color: "var(--gold)" }} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ color: "var(--text)", fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.title}</div>
                        <div style={{ color: "var(--text-dim)", fontSize: 11, textTransform: "capitalize" }}>
                          {it.category} · {Math.round((it.file_size_bytes || 0) / 1024)} KB
                        </div>
                      </div>
                      <button onClick={() => downloadItem(it)} data-testid={`vault-dl-${it.id}`}
                              style={{ background: "transparent", border: "1px solid var(--gold-deep)", borderRadius: 8, padding: "6px 8px", color: "var(--gold)", cursor: "pointer" }}>
                        <Download size={14} />
                      </button>
                      <button onClick={() => removeItem(it)} data-testid={`vault-rm-${it.id}`}
                              style={{ background: "transparent", border: "1px solid rgba(239,68,68,0.4)", borderRadius: 8, padding: "6px 8px", color: "#fca5a5", cursor: "pointer" }}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                    {it.notes_enc && (
                      <>
                        <button onClick={() => decryptAndShowNote(it)} data-testid={`vault-note-toggle-${it.id}`}
                                style={{ marginTop: 8, fontSize: 11, background: "transparent", border: "none", color: "var(--text-dim)", cursor: "pointer", textDecoration: "underline" }}>
                          {decNotes[it.id] ? t(lang, "vaultHideNote") : t(lang, "vaultShowNote")}
                        </button>
                        {decNotes[it.id] && (
                          <div style={{ marginTop: 6, padding: 8, fontSize: 12, color: "var(--text-dim)", background: "#0a0a0a", border: "1px solid var(--line)", borderRadius: 8, whiteSpace: "pre-wrap" }}>
                            {decNotes[it.id]}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {stage === "unlocked" && adding && (
          <div data-testid="vault-add-form">
            <button className="btn-ghost" onClick={() => { setAdding(false); setNewFile(null); }} style={{ marginBottom: 12, padding: "6px 12px" }}>
              <ArrowLeft size={14} style={{ display: "inline", marginRight: 4 }} /> Back
            </button>

            <input type="file" ref={uploadRef} onChange={handleFile} style={{ display: "none" }}
                   accept="image/*,application/pdf,.doc,.docx,.txt,.zip" data-testid="vault-file-input" />
            <button className="btn-gold w-full" onClick={() => uploadRef.current?.click()} data-testid="vault-pick-file-btn" style={{ marginBottom: 10 }}>
              <Upload size={16} style={{ display: "inline", marginRight: 6 }} />
              {newFile ? `✓ ${newFile.name}` : t(lang, "vaultPickFile")}
            </button>
            {newFile && (
              <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 10, paddingLeft: 4 }}>
                {Math.round(newFile.size / 1024)} KB · {newFile.type || "file"} · Ready to encrypt and upload
              </div>
            )}

            <input className="input" placeholder={t(lang, "vaultItemTitle")} value={newTitle}
                   onChange={(e) => setNewTitle(e.target.value)} data-testid="vault-item-title" style={{ marginBottom: 10 }} />

            <div style={{ marginBottom: 10 }}>
              <div style={{ color: "var(--gold)", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                {t(lang, "vaultCategory")}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 6 }}>
                {VAULT_CATEGORIES.map(c => (
                  <button key={c.id} data-testid={`vault-cat-${c.id}`} onClick={() => setNewCategory(c.id)}
                          style={{ padding: 8, borderRadius: 8, fontSize: 11, cursor: "pointer",
                                   background: newCategory === c.id ? "rgba(247,201,72,0.15)" : "var(--bg-card)",
                                   border: newCategory === c.id ? "1px solid var(--gold)" : "1px solid var(--line)",
                                   color: newCategory === c.id ? "var(--gold)" : "var(--text)" }}>
                    {c.label}
                  </button>
                ))}
              </div>
            </div>

            <textarea className="input" rows={3} placeholder={t(lang, "vaultNotesPlaceholder")} value={newNotes}
                      onChange={(e) => setNewNotes(e.target.value)} data-testid="vault-notes" style={{ marginBottom: 12 }} />

            {err && <div style={{ color: "#fca5a5", fontSize: 13, marginBottom: 10 }}>{err}</div>}

            <button onClick={addItem} disabled={busy || !newFile || !newTitle} data-testid="vault-save-item-btn"
                    style={{
                      width: "100%", padding: "14px 16px", fontSize: 15, fontWeight: 700,
                      background: (busy || !newFile || !newTitle) ? "var(--bg-card)" : "linear-gradient(135deg,#f7c948,#d6a017)",
                      color: (busy || !newFile || !newTitle) ? "var(--text-dim)" : "#1a1300",
                      border: (busy || !newFile || !newTitle) ? "1px solid var(--line)" : "none",
                      borderRadius: 12, cursor: (busy || !newFile || !newTitle) ? "not-allowed" : "pointer",
                      boxShadow: (busy || !newFile || !newTitle) ? "none" : "0 4px 20px rgba(247,201,72,0.35)",
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                    }}>
              {busy ? <span className="spinner" /> : (<>
                <Lock size={16} /> {newFile && newTitle ? t(lang, "vaultUploadBtn") : t(lang, "vaultUploadDisabled")}
              </>)}
            </button>
            {(!newFile || !newTitle) && (
              <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8, textAlign: "center" }}>
                {!newFile ? "📎 Pick a file above to enable upload" : "✏️ Enter a title to enable upload"}
              </div>
            )}
          </div>
        )}

        {showWipeConfirm && (
          <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.92)", borderRadius: 24, padding: 24, display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <AlertTriangle size={40} style={{ color: "#ef4444", margin: "0 auto 14px", display: "block" }} />
            <div style={{ color: "var(--text)", fontWeight: 700, fontSize: 16, textAlign: "center", marginBottom: 8 }}>
              {t(lang, "vaultWipeTitle")}
            </div>
            <div style={{ color: "var(--text-dim)", fontSize: 13, textAlign: "center", lineHeight: 1.5, marginBottom: 18 }}>
              {t(lang, "vaultWipeBody")}
            </div>
            <button className="btn-ghost w-full" onClick={() => setShowWipeConfirm(false)} style={{ marginBottom: 8 }} data-testid="vault-wipe-cancel">
              {t(lang, "cancel")}
            </button>
            <button onClick={doWipe} data-testid="vault-wipe-confirm"
                    style={{ width: "100%", padding: 12, background: "linear-gradient(135deg,#7f1d1d,#dc2626)", color: "#fff", border: "none", borderRadius: 10, cursor: "pointer", fontWeight: 700 }}>
              {busy ? <span className="spinner" /> : t(lang, "vaultWipeConfirm")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SuggestFeatureModal({ lang, onClose }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const submit = async () => {
    if (text.trim().length < 5) return;
    setBusy(true);
    try { await api.post("/feedback/suggest", { text: text.trim() }); setSent(true); }
    catch { alert("Could not send. Try again later."); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-bg" data-testid="suggest-modal">
      <div className="modal-card" style={{ padding: 22 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
          <h2 className="brand-font gold" style={{ fontSize: 18 }}>{t(lang, "suggestPrompt")}</h2>
          <button onClick={onClose} data-testid="suggest-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>
        {sent ? (
          <div style={{ textAlign: "center", padding: 30 }}>
            <Check size={48} style={{ color: "#86efac", margin: "0 auto 14px", display: "block" }} />
            <div style={{ color: "var(--text)", fontSize: 14 }}>{t(lang, "suggestThanks")}</div>
            <button className="btn-ghost w-full" onClick={onClose} style={{ marginTop: 18 }}>Close</button>
          </div>
        ) : (
          <>
            <textarea className="input" rows={5} value={text} onChange={(e) => setText(e.target.value)}
                      placeholder={t(lang, "suggestPlaceholder")} data-testid="suggest-input" style={{ marginBottom: 12 }} />
            <button className="btn-gold w-full" onClick={submit} disabled={busy || text.trim().length < 5} data-testid="suggest-submit">
              {busy ? <span className="spinner" /> : t(lang, "suggestSubmit")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}

// ============================== RECORDING CONSENT GATE ==============================
// Wraps every audio/video record button. Shows country-aware legal warning before
// recording starts. Stores a one-time global consent + per-session "know your rights"
// acknowledgement.

function RecordingConsentGate({ lang, country, surface, onProceed, onCancel }) {
  const { lawFor, tryGetLocationOnce, nearestCourtWithin } = require("./recordingLaw");
  const law = lawFor(country || "GB");
  const [globalConsent, setGlobalConsent] = useState(() => localStorage.getItem("aa_record_consent_v1") === "1");
  const [proximityState, setProximityState] = useState({ checking: false, near: null, asked: false });
  const [showAllLaw, setShowAllLaw] = useState(false);
  const [overrideCourt, setOverrideCourt] = useState(false);

  // One-shot proximity check on first render
  useEffect(() => {
    let alive = true;
    const wantsLocationCheck = localStorage.getItem("aa_loc_safety") !== "0"; // default on
    if (!wantsLocationCheck) { setProximityState((s) => ({ ...s, checking: false, asked: true })); return; }
    setProximityState({ checking: true, near: null, asked: false });
    (async () => {
      const loc = await tryGetLocationOnce();
      if (!alive) return;
      if (!loc) { setProximityState({ checking: false, near: null, asked: true }); return; }
      const hit = nearestCourtWithin(loc.lat, loc.lng, 150);
      setProximityState({ checking: false, near: hit, asked: true });
    })();
    return () => { alive = false; };
  }, []);

  const acceptAndProceed = () => {
    localStorage.setItem("aa_record_consent_v1", "1");
    setGlobalConsent(true);
    onProceed();
  };

  // BLOCK state: court proximity hit AND user hasn't overridden
  const isCourtBlocked = proximityState.near && !overrideCourt;

  return (
    <div className="modal-bg" data-testid="recording-consent-gate"
         style={{ alignItems: "center", zIndex: 99999, background: "rgba(0,0,0,0.92)", backdropFilter: "blur(10px)" }}>
      <div className="modal-card" style={{ padding: 22, maxWidth: 520, borderRadius: 20, zIndex: 100000, maxHeight: "92dvh" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 18, display: "flex", alignItems: "center", gap: 8 }}>
            <ShieldCheck size={18} /> {t(lang, "rcGateTitle")}
          </h2>
          <button onClick={onCancel} data-testid="rc-gate-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>

        {/* Location proximity result */}
        {proximityState.checking && (
          <div data-testid="rc-checking" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, marginBottom: 12, fontSize: 12, color: "var(--text-dim)", display: "flex", alignItems: "center", gap: 8 }}>
            <span className="spinner" style={{ width: 12, height: 12 }} /> {t(lang, "rcCheckingLocation")}
          </div>
        )}

        {proximityState.near && (
          <div data-testid="rc-court-warning" style={{ background: "rgba(239,68,68,0.12)", border: "1px solid #ef4444", borderRadius: 12, padding: 14, marginBottom: 14 }}>
            <div style={{ color: "#fca5a5", fontWeight: 700, fontSize: 13, marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
              <AlertTriangle size={14} /> {t(lang, "rcCourtNearTitle")}
            </div>
            <div style={{ color: "var(--text)", fontSize: 13, lineHeight: 1.5 }}>
              {t(lang, "rcCourtNearBody").replace("{court}", proximityState.near.court.n).replace("{m}", String(proximityState.near.distance_m))}
            </div>
            <div style={{ color: "var(--text-dim)", fontSize: 11, marginTop: 6 }}>
              {t(lang, "rcCourtPenalty")}
            </div>
            <div style={{ marginTop: 10, padding: 8, background: "rgba(0,0,0,0.3)", borderRadius: 8, display: "flex", alignItems: "center", gap: 8 }}>
              <input type="checkbox" id="rc-not-in-court" data-testid="rc-not-in-court" checked={overrideCourt}
                     onChange={(e) => setOverrideCourt(e.target.checked)} style={{ accentColor: "var(--gold)" }} />
              <label htmlFor="rc-not-in-court" style={{ fontSize: 12, color: "var(--text)", cursor: "pointer" }}>
                {t(lang, "rcConfirmNotInCourt")}
              </label>
            </div>
          </div>
        )}

        {/* Country-specific legal summary */}
        <div style={{ background: "rgba(247,201,72,0.06)", border: "1px solid var(--gold-deep)", borderRadius: 12, padding: 14, marginBottom: 12 }}>
          <div style={{ color: "var(--gold)", fontWeight: 700, fontSize: 13, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
            {law.flag} {t(lang, "rcCountryRulesFor").replace("{country}", law.countryName)}
          </div>
          <div style={{ color: "var(--text)", fontSize: 12, lineHeight: 1.5, marginBottom: 8 }}>
            <strong style={{ color: "var(--gold)" }}>{t(lang, "rcConsentLabel")}:</strong> {law.consent}
          </div>
          <div style={{ color: "var(--text)", fontSize: 12, lineHeight: 1.5, marginBottom: 8 }}>
            <strong style={{ color: "#fca5a5" }}>{t(lang, "rcCourtLabel")}:</strong> {law.court}
          </div>
          <button onClick={() => setShowAllLaw((v) => !v)} data-testid="rc-toggle-detail"
                  style={{ background: "transparent", border: "none", color: "var(--gold)", fontSize: 11, cursor: "pointer", padding: 0, textDecoration: "underline" }}>
            {showAllLaw ? t(lang, "rcHideDetail") : t(lang, "rcShowDetail")}
          </button>
          {showAllLaw && (
            <div style={{ marginTop: 10, fontSize: 12, color: "var(--text-dim)", lineHeight: 1.5 }}>
              <div style={{ marginBottom: 6 }}><strong style={{ color: "#86efac" }}>{t(lang, "rcUsuallyOk")}:</strong></div>
              <ul style={{ paddingLeft: 18, marginBottom: 8 }}>{law.ok.map((x, i) => <li key={i}>{x}</li>)}</ul>
              <div style={{ marginBottom: 6 }}><strong style={{ color: "#fca5a5" }}>{t(lang, "rcAvoid")}:</strong></div>
              <ul style={{ paddingLeft: 18 }}>{law.danger.map((x, i) => <li key={i}>{x}</li>)}</ul>
            </div>
          )}
        </div>

        {/* First-time consent — saved forever after first acceptance */}
        {!globalConsent && (
          <div data-testid="rc-first-time" style={{ fontSize: 12, color: "var(--text-dim)", padding: 10, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 8, marginBottom: 12, lineHeight: 1.5 }}>
            {t(lang, "rcFirstTime")}
          </div>
        )}

        {/* Action buttons */}
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={onCancel} className="btn-ghost" data-testid="rc-cancel-btn" style={{ flex: 1 }}>
            {t(lang, "cancel")}
          </button>
          <button onClick={acceptAndProceed} disabled={isCourtBlocked} data-testid="rc-proceed-btn"
                  style={{
                    flex: 2, padding: 12, borderRadius: 10, fontWeight: 700, cursor: isCourtBlocked ? "not-allowed" : "pointer",
                    background: isCourtBlocked ? "rgba(247,201,72,0.2)" : "var(--gold)",
                    color: "#1a1300", border: "none", opacity: isCourtBlocked ? 0.5 : 1,
                  }}>
            {isCourtBlocked ? t(lang, "rcMustAcknowledge") : t(lang, "rcUnderstandProceed")}
          </button>
        </div>
      </div>
    </div>
  );
}

// Hook: wrap a recorder so that the first interaction shows the legality gate.
// The host modal uses const { ensureConsent, GateModal } = useRecordingConsent(...).
function useRecordingConsent({ lang, country, surface, recordingTitle }) {
  const [showGate, setShowGate] = useState(false);
  const [proceedFn, setProceedFn] = useState(null);
  const { containsCourtKeyword } = require("./recordingLaw");

  // Wrap a fn so that the gate fires first.
  const ensureConsent = (fn) => () => {
    // Keyword-based block
    if (recordingTitle && containsCourtKeyword(recordingTitle)) {
      if (!confirm("This recording title mentions a court. Recording in court is a criminal offence (Contempt of Court Act 1981 s.9 in the UK). Are you SURE this is not from a courtroom?")) {
        return;
      }
    }
    setProceedFn(() => fn);
    setShowGate(true);
  };

  const GateModal = showGate ? (
    <RecordingConsentGate
      lang={lang} country={country} surface={surface}
      onCancel={() => { setShowGate(false); setProceedFn(null); }}
      onProceed={() => { setShowGate(false); if (proceedFn) proceedFn(); setProceedFn(null); }}
    />
  ) : null;

  return { ensureConsent, GateModal };
}



// ---------- Contract Reader ----------
function ContractReaderBody({ lang, country, onSwitchToNegotiate }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");
  const cameraRef = useRef(null);
  const uploadRef = useRef(null);

  const choose = (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    if (preview) URL.revokeObjectURL(preview);
    setFile(f); setPreview(URL.createObjectURL(f)); setR(null); setErr("");
  };

  const analyze = async () => {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("language", lang);
      fd.append("country", country);
      const { data } = await api.post("/contract/analyze", fd);
      setR(data);
    } catch (e) { setErr(e?.response?.data?.detail || "Analysis failed"); }
    finally { setBusy(false); }
  };

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const VERDICT_STYLE = {
    green: { bg: "rgba(34,197,94,0.1)", border: "#22c55e", text: "#86efac", label: "SAFE TO SIGN" },
    amber: { bg: "rgba(247,201,72,0.1)", border: "var(--gold)", text: "var(--gold)", label: "PROCEED WITH CARE" },
    red: { bg: "rgba(239,68,68,0.1)", border: "#ef4444", text: "#fca5a5", label: "DO NOT SIGN YET" },
  };
  const RISK_DOT = { low: "#22c55e", medium: "#f7c948", high: "#ef4444" };

  return (
    <>
      {!r ? (
        <>
          <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 14 }}>
            {t(lang, "contractReaderIntro")}
          </p>

          {/* Hidden inputs */}
          <input ref={cameraRef} type="file" accept="image/*" capture="environment"
                 onChange={choose} style={{ display: "none" }} data-testid="contract-camera-input" />
          <input ref={uploadRef} type="file" accept="image/*,application/pdf,.doc,.docx,.txt"
                 onChange={choose} style={{ display: "none" }} data-testid="contract-upload-input" />

          {/* Dual choice: Camera + Upload */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
            <button className="btn-gold" data-testid="contract-camera-btn" onClick={() => cameraRef.current?.click()}
                    style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, padding: "18px 8px" }}>
              <Camera size={22} />
              <span style={{ fontSize: 13 }}>{t(lang, "contractTakePhoto")}</span>
            </button>
            <button className="btn-ghost" data-testid="contract-upload-btn" onClick={() => uploadRef.current?.click()}
                    style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, padding: "18px 8px", border: "1px solid var(--gold-deep)" }}>
              <Upload size={22} />
              <span style={{ fontSize: 13 }}>{t(lang, "contractUploadFile")}</span>
            </button>
          </div>

          {file && (
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, marginBottom: 10, display: "flex", alignItems: "center", gap: 10 }}>
              <FileText size={18} style={{ color: "var(--gold)" }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: "var(--text)", fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</div>
                <div style={{ color: "var(--text-dim)", fontSize: 11 }}>{(file.size / 1024).toFixed(1)} KB</div>
              </div>
              <button onClick={() => { if (preview) URL.revokeObjectURL(preview); setFile(null); setPreview(null); }}
                      style={{ background: "transparent", border: "none", color: "var(--text-dim)", cursor: "pointer" }}>
                <X size={16} />
              </button>
            </div>
          )}

          {preview && file?.type?.startsWith("image/") && (
            <div style={{ marginBottom: 10, borderRadius: 12, overflow: "hidden", border: "1px solid var(--line)" }}>
              <img src={preview} alt="Contract" style={{ width: "100%", display: "block", maxHeight: 280, objectFit: "contain", background: "#000" }} />
            </div>
          )}
          {file && !busy && (
            <button className="btn-gold w-full" data-testid="contract-analyze-btn" onClick={analyze} style={{ marginBottom: 8 }}>
              {t(lang, "contractReaderRead")}
            </button>
          )}
          {busy && <div style={{ textAlign: "center", padding: 16 }}><span className="spinner" /><div style={{ color: "var(--text-dim)", marginTop: 8, fontSize: 13 }}>{t(lang, "contractReaderBusy")}</div></div>}
          {err && <div style={{ background: "#2a0a0a", border: "1px solid #7f1d1d", color: "#fca5a5", padding: 10, borderRadius: 10, fontSize: 13 }}>{err}</div>}
        </>
      ) : (
        <div data-testid="contract-result">
          {(() => {
            const v = VERDICT_STYLE[r.overall_verdict] || VERDICT_STYLE.amber;
            return (
              <div style={{ background: v.bg, border: `1px solid ${v.border}`, borderRadius: 12, padding: 14, marginBottom: 14 }}>
                <div style={{ color: v.text, fontWeight: 700, fontSize: 13, letterSpacing: "0.1em", marginBottom: 4 }}>{v.label}</div>
                <div style={{ color: "var(--text)", fontSize: 14, lineHeight: 1.5 }}>{r.verdict_one_liner}</div>
              </div>
            );
          })()}
          <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>{t(lang, "contractReaderType")}</div>
          <div style={{ color: "var(--text)", fontSize: 14, textTransform: "capitalize", marginBottom: 10 }}>{r.contract_type?.replace(/_/g, " ")}</div>
          <p style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.6, marginBottom: 14 }}>{r.plain_english_summary}</p>

          {r.red_flags?.length > 0 && (
            <>
              <div style={{ color: "#ef4444", fontSize: 12, fontWeight: 700, textTransform: "uppercase", marginBottom: 6 }}>{t(lang, "contractRedFlags")}</div>
              {r.red_flags.map((f, i) => (
                <div key={i} style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, padding: 8, marginBottom: 6, fontSize: 13, color: "var(--text)" }}>🔴 {f}</div>
              ))}
            </>
          )}
          {r.amber_flags?.length > 0 && (
            <>
              <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "10px 0 6px" }}>{t(lang, "contractAmberFlags")}</div>
              {r.amber_flags.map((f, i) => (
                <div key={i} style={{ background: "rgba(247,201,72,0.1)", border: "1px solid var(--gold-deep)", borderRadius: 8, padding: 8, marginBottom: 6, fontSize: 13, color: "var(--text)" }}>🟡 {f}</div>
              ))}
            </>
          )}
          {r.clauses?.length > 0 && (
            <details style={{ marginTop: 14 }}>
              <summary style={{ color: "var(--gold)", fontSize: 13, cursor: "pointer", fontWeight: 600 }}>{t(lang, "contractClauseBreakdown")} ({r.clauses.length})</summary>
              <div style={{ marginTop: 10 }}>
                {r.clauses.map((c, i) => (
                  <div key={i} style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, marginBottom: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{ width: 8, height: 8, borderRadius: "50%", background: RISK_DOT[c.risk_level] || "#888" }}></span>
                      <span style={{ color: "var(--gold)", fontSize: 13, fontWeight: 600 }}>{c.title}</span>
                    </div>
                    <div style={{ color: "var(--text-dim)", fontSize: 12, lineHeight: 1.5 }}>{c.plain_english}</div>
                  </div>
                ))}
              </div>
            </details>
          )}
          {r.questions_to_ask?.length > 0 && (
            <>
              <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "14px 0 6px" }}>{t(lang, "contractQuestionsToAsk")}</div>
              <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.6 }}>{r.questions_to_ask.map((q, i) => <li key={i}>{q}</li>)}</ul>
            </>
          )}
          {r.solicitor_review_recommended && (
            <div style={{ background: "rgba(247,201,72,0.08)", border: "1px solid var(--gold-deep)", borderRadius: 10, padding: 10, marginTop: 14, fontSize: 13, color: "var(--text)" }}>
              ⚖️ {t(lang, "contractSolicitorRecommended")}
            </div>
          )}
          {/* Negotiate upsell — appears when there are clauses worth pushing back on */}
          {((r.red_flags?.length > 0) || (r.amber_flags?.length > 0)) && onSwitchToNegotiate && (
            <button data-testid="read-to-negotiate-upsell" onClick={onSwitchToNegotiate}
                    style={{
                      width: "100%", marginTop: 14, padding: 14, borderRadius: 12,
                      background: "linear-gradient(135deg, rgba(247,201,72,0.18), rgba(247,201,72,0.06))",
                      border: "1px solid var(--gold)", color: "var(--text)",
                      cursor: "pointer", textAlign: "left", display: "flex", alignItems: "center", gap: 12,
                    }}>
              <div style={{ width: 38, height: 38, borderRadius: "50%", background: "rgba(247,201,72,0.2)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Scale size={20} style={{ color: "var(--gold)" }} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: "var(--gold)", fontSize: 13, fontWeight: 700, marginBottom: 2, display: "flex", alignItems: "center", gap: 6 }}>
                  {t(lang, "readUpsellTitle")}
                  <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 5, background: "linear-gradient(135deg,#7f1d1d,#dc2626)", color: "#fff", letterSpacing: "0.05em" }}>
                    PRO
                  </span>
                </div>
                <div style={{ color: "var(--text-dim)", fontSize: 12, lineHeight: 1.4 }}>
                  {t(lang, "readUpsellSub")}
                </div>
              </div>
            </button>
          )}
          <button className="btn-ghost w-full" onClick={() => { setR(null); setFile(null); if (preview) URL.revokeObjectURL(preview); setPreview(null); }} style={{ marginTop: 14 }}>
            {t(lang, "contractAnother")}
          </button>
        </div>
      )}
    </>
  );
}

// ---------- Contract Drafter ----------
function ContractDrafterBody({ lang, country }) {
  const [step, setStep] = useState(1);   // 1: type, 2: party A, 3: party B, 4: terms, 5: result
  const [contractType, setContractType] = useState("employment");
  const [partyA, setPartyA] = useState({ name: "", address: "", registration_no: "", sector: "" });
  const [partyB, setPartyB] = useState({ name: "", address: "", role: "", email: "" });
  const [terms, setTerms] = useState({});
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState(null);

  const TYPES = [
    { v: "employment", label: t(lang, "ctEmployment") },
    { v: "contractor", label: t(lang, "ctContractor") },
    { v: "nda", label: t(lang, "ctNda") },
    { v: "lease", label: t(lang, "ctLease") },
    { v: "service", label: t(lang, "ctService") },
    { v: "consultancy", label: t(lang, "ctConsultancy") },
    { v: "sale", label: t(lang, "ctSale") },
    { v: "partnership", label: t(lang, "ctPartnership") },
  ];

  const generate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/contract/draft", {
        contract_type: contractType, party_a: partyA, party_b: partyB,
        terms, additional_notes: notes, language: lang, country,
      });
      setR(data); setStep(5);
    } catch (e) { alert(e?.response?.data?.detail || "Generation failed"); }
    finally { setBusy(false); }
  };

  const copyText = () => {
    if (!r?.full_contract_text) return;
    navigator.clipboard.writeText(r.full_contract_text);
    alert(t(lang, "copiedToClipboard"));
  };

  const StepHeader = () => (
    <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
      {[1, 2, 3, 4].map(n => (
        <div key={n} style={{ flex: 1, height: 4, borderRadius: 2, background: step >= n ? "var(--gold)" : "var(--line)" }}></div>
      ))}
    </div>
  );

  return (
    <>
      {step <= 4 && <StepHeader />}

        {step === 1 && (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 12 }}>{t(lang, "contractDrafterStep1")}</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 14 }}>
              {TYPES.map(ty => (
                <button key={ty.v} data-testid={`ct-type-${ty.v}`}
                        onClick={() => setContractType(ty.v)}
                        style={{ padding: 12, borderRadius: 10, fontSize: 13,
                                 background: contractType === ty.v ? "rgba(247,201,72,0.15)" : "var(--bg-card)",
                                 border: contractType === ty.v ? "1px solid var(--gold)" : "1px solid var(--line)",
                                 color: contractType === ty.v ? "var(--gold)" : "var(--text)", cursor: "pointer" }}>
                  {ty.label}
                </button>
              ))}
            </div>
            <button className="btn-gold w-full" onClick={() => setStep(2)} data-testid="ct-next-1">{t(lang, "next")}</button>
          </>
        )}

        {step === 2 && (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 10 }}>{t(lang, "contractDrafterStep2")}</p>
            <input className="input" placeholder={t(lang, "ctBusinessName")} value={partyA.name} onChange={(e) => setPartyA({ ...partyA, name: e.target.value })} data-testid="ct-pa-name" style={{ marginBottom: 8 }} />
            <input className="input" placeholder={t(lang, "ctAddress")} value={partyA.address} onChange={(e) => setPartyA({ ...partyA, address: e.target.value })} data-testid="ct-pa-addr" style={{ marginBottom: 8 }} />
            <input className="input" placeholder={t(lang, "ctRegistration")} value={partyA.registration_no} onChange={(e) => setPartyA({ ...partyA, registration_no: e.target.value })} data-testid="ct-pa-reg" style={{ marginBottom: 8 }} />
            <input className="input" placeholder={t(lang, "ctSector")} value={partyA.sector} onChange={(e) => setPartyA({ ...partyA, sector: e.target.value })} data-testid="ct-pa-sector" style={{ marginBottom: 8 }} />
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => setStep(1)}>{t(lang, "back")}</button>
              <button className="btn-gold" style={{ flex: 2 }} onClick={() => setStep(3)} disabled={!partyA.name} data-testid="ct-next-2">{t(lang, "next")}</button>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 10 }}>{t(lang, "contractDrafterStep3")}</p>
            <input className="input" placeholder={t(lang, "ctFullName")} value={partyB.name} onChange={(e) => setPartyB({ ...partyB, name: e.target.value })} data-testid="ct-pb-name" style={{ marginBottom: 8 }} />
            <input className="input" placeholder={t(lang, "ctAddress")} value={partyB.address} onChange={(e) => setPartyB({ ...partyB, address: e.target.value })} data-testid="ct-pb-addr" style={{ marginBottom: 8 }} />
            {contractType === "employment" || contractType === "contractor" || contractType === "consultancy" ? (
              <input className="input" placeholder={t(lang, "ctRole")} value={partyB.role} onChange={(e) => setPartyB({ ...partyB, role: e.target.value })} data-testid="ct-pb-role" style={{ marginBottom: 8 }} />
            ) : null}
            <input className="input" placeholder="Email" value={partyB.email} onChange={(e) => setPartyB({ ...partyB, email: e.target.value })} data-testid="ct-pb-email" style={{ marginBottom: 8 }} />
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => setStep(2)}>{t(lang, "back")}</button>
              <button className="btn-gold" style={{ flex: 2 }} onClick={() => setStep(4)} disabled={!partyB.name} data-testid="ct-next-3">{t(lang, "next")}</button>
            </div>
          </>
        )}

        {step === 4 && (
          <>
            <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 10 }}>{t(lang, "contractDrafterStep4")}</p>
            {/* type-specific term fields */}
            {(contractType === "employment" || contractType === "contractor" || contractType === "consultancy") && (
              <>
                <input className="input" type="number" placeholder={contractType === "employment" ? t(lang, "ctSalary") : t(lang, "ctDayRate")} value={terms.salary_gbp || ""} onChange={(e) => setTerms({ ...terms, salary_gbp: e.target.value })} data-testid="ct-salary" style={{ marginBottom: 8 }} />
                <input className="input" type="date" placeholder={t(lang, "ctStartDate")} value={terms.start_date || ""} onChange={(e) => setTerms({ ...terms, start_date: e.target.value })} data-testid="ct-start-date" style={{ marginBottom: 8 }} />
                <input className="input" type="number" placeholder={t(lang, "ctHoursPerWeek")} value={terms.hours_per_week || ""} onChange={(e) => setTerms({ ...terms, hours_per_week: e.target.value })} style={{ marginBottom: 8 }} />
                <input className="input" type="number" placeholder={t(lang, "ctNoticeWeeks")} value={terms.notice_period_weeks || ""} onChange={(e) => setTerms({ ...terms, notice_period_weeks: e.target.value })} style={{ marginBottom: 8 }} />
              </>
            )}
            {contractType === "lease" && (
              <>
                <input className="input" type="number" placeholder={t(lang, "ctRentMonthly")} value={terms.rent_gbp || ""} onChange={(e) => setTerms({ ...terms, rent_gbp: e.target.value })} style={{ marginBottom: 8 }} />
                <input className="input" type="date" placeholder={t(lang, "ctStartDate")} value={terms.start_date || ""} onChange={(e) => setTerms({ ...terms, start_date: e.target.value })} style={{ marginBottom: 8 }} />
                <input className="input" type="number" placeholder={t(lang, "ctTermMonths")} value={terms.term_months || ""} onChange={(e) => setTerms({ ...terms, term_months: e.target.value })} style={{ marginBottom: 8 }} />
                <input className="input" placeholder={t(lang, "ctPropertyAddr")} value={terms.property_address || ""} onChange={(e) => setTerms({ ...terms, property_address: e.target.value })} style={{ marginBottom: 8 }} />
              </>
            )}
            {contractType === "nda" && (
              <>
                <input className="input" type="number" placeholder={t(lang, "ctDurationMonths")} value={terms.duration_months || ""} onChange={(e) => setTerms({ ...terms, duration_months: e.target.value })} style={{ marginBottom: 8 }} />
                <input className="input" placeholder={t(lang, "ctPurpose")} value={terms.purpose || ""} onChange={(e) => setTerms({ ...terms, purpose: e.target.value })} style={{ marginBottom: 8 }} />
              </>
            )}
            {(contractType === "service" || contractType === "sale" || contractType === "partnership") && (
              <>
                <textarea className="input" rows={3} placeholder={t(lang, "ctKeyTerms")} value={terms.summary || ""} onChange={(e) => setTerms({ ...terms, summary: e.target.value })} style={{ marginBottom: 8 }} />
                <input className="input" type="number" placeholder={t(lang, "ctValueGbp")} value={terms.value_gbp || ""} onChange={(e) => setTerms({ ...terms, value_gbp: e.target.value })} style={{ marginBottom: 8 }} />
              </>
            )}
            <textarea className="input" rows={2} placeholder={t(lang, "ctAnythingElse")} value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="ct-notes" style={{ marginBottom: 8 }} />
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn-ghost" style={{ flex: 1 }} onClick={() => setStep(3)}>{t(lang, "back")}</button>
              <button className="btn-gold" style={{ flex: 2 }} onClick={generate} disabled={busy} data-testid="ct-generate-btn">
                {busy ? <span className="spinner" /> : t(lang, "contractDrafterGenerate")}
              </button>
            </div>
            {busy && <div style={{ textAlign: "center", color: "var(--text-dim)", fontSize: 12, marginTop: 10 }}>{t(lang, "contractDrafterBusy")}</div>}
          </>
        )}

        {step === 5 && r && (
          <div data-testid="contract-result">
            <div style={{ background: r.risk_level === "low" ? "rgba(34,197,94,0.1)" : r.risk_level === "high" ? "rgba(239,68,68,0.1)" : "rgba(247,201,72,0.1)",
                          border: `1px solid ${r.risk_level === "low" ? "#22c55e" : r.risk_level === "high" ? "#ef4444" : "var(--gold)"}`,
                          borderRadius: 12, padding: 12, marginBottom: 14, fontSize: 13, color: "var(--text)" }}>
              <strong>{r.contract_title}</strong>
              <div style={{ color: "var(--text-dim)", fontSize: 12, marginTop: 4 }}>
                {t(lang, "ctRiskLevel")}: <span style={{ textTransform: "uppercase" }}>{r.risk_level}</span>
                {r.statutory_clauses_included?.length > 0 && <span> · {r.statutory_clauses_included.length} {t(lang, "ctStatutoryClauses")}</span>}
              </div>
            </div>
            {r.solicitor_review_recommended && (
              <div style={{ background: "rgba(247,201,72,0.08)", border: "1px solid var(--gold-deep)", borderRadius: 10, padding: 10, marginBottom: 10, fontSize: 13, color: "var(--text)" }}>
                ⚖️ {t(lang, "contractSolicitorRecommended")}
              </div>
            )}
            <textarea className="input" rows={14} value={r.full_contract_text}
                      onChange={(e) => setR({ ...r, full_contract_text: e.target.value })}
                      style={{ fontSize: 12, lineHeight: 1.5, fontFamily: "monospace" }} data-testid="contract-text-area" />
            {r.next_steps_for_user?.length > 0 && (
              <>
                <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "10px 0 4px" }}>{t(lang, "ctNextSteps")}</div>
                <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.6 }}>{r.next_steps_for_user.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </>
            )}
            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="btn-gold" onClick={copyText} style={{ flex: 1 }} data-testid="ct-copy-btn">{t(lang, "contractCopy")}</button>
              <button className="btn-ghost" onClick={() => { setStep(1); setR(null); setTerms({}); }} style={{ flex: 1 }}>{t(lang, "contractAnother")}</button>
            </div>
          </div>
        )}
    </>
  );
}

// ---------- Contracts Hub (Read + Draft + Negotiate in tabbed modal) ----------
function ContractsHubModal({ lang, country, hasTier, onUpsell, onClose }) {
  const [tab, setTab] = useState("read"); // "read" | "draft" | "negotiate"
  const canDraft = hasTier("pro");
  const canNegotiate = hasTier("pro");

  const switchTab = (next) => {
    if ((next === "draft" && !canDraft) || (next === "negotiate" && !canNegotiate)) {
      onUpsell();
      return;
    }
    setTab(next);
  };

  const TabBtn = ({ id, icon: Icon, label, locked }) => (
    <button data-testid={`contracts-tab-${id}`} onClick={() => switchTab(id)}
            style={{
              flex: 1, padding: "10px 6px", borderRadius: 9, cursor: "pointer", fontSize: 12, fontWeight: 600,
              background: tab === id ? "var(--gold)" : "transparent",
              color: tab === id ? "#1a1300" : "var(--text-dim)",
              border: "none", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 5,
              position: "relative",
              whiteSpace: "nowrap",
            }}>
      <Icon size={13} /> {label}
      {locked && (
        <span style={{ fontSize: 8, fontWeight: 700, padding: "2px 4px", borderRadius: 4, background: "linear-gradient(135deg,#7f1d1d,#dc2626)", color: "#fff", marginLeft: 2, letterSpacing: "0.05em" }}>
          PRO
        </span>
      )}
    </button>
  );

  return (
    <div className="modal-bg" data-testid="contracts-hub-modal">
      <div className="modal-card" style={{ padding: 20, overflowY: "auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "contractTools")}</h2>
          <button onClick={onClose} data-testid="contracts-hub-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, padding: 4, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, marginBottom: 16 }}>
          <TabBtn id="read" icon={FileText} label={t(lang, "contractTabRead")} locked={false} />
          <TabBtn id="draft" icon={Gavel} label={t(lang, "contractTabDraft")} locked={!canDraft} />
          <TabBtn id="negotiate" icon={Scale} label={t(lang, "contractTabNegotiate")} locked={!canNegotiate} />
        </div>

        {tab === "read" && <ContractReaderBody lang={lang} country={country} onSwitchToNegotiate={() => switchTab("negotiate")} />}
        {tab === "draft" && canDraft && <ContractDrafterBody lang={lang} country={country} />}
        {tab === "negotiate" && canNegotiate && <ContractNegotiateBody lang={lang} country={country} />}
      </div>
    </div>
  );
}

// ---------- Contract Negotiate (Pro) ----------
function ContractNegotiateBody({ lang, country }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [priorities, setPriorities] = useState("");
  const [userRole, setUserRole] = useState("recipient");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState(null);
  const [err, setErr] = useState("");
  const cameraRef = useRef(null);
  const uploadRef = useRef(null);

  const choose = (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    if (preview) URL.revokeObjectURL(preview);
    setFile(f); setPreview(URL.createObjectURL(f)); setR(null); setErr("");
  };

  const analyze = async () => {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("priorities", priorities);
      fd.append("user_role", userRole);
      fd.append("language", lang);
      fd.append("country", country);
      const { data } = await api.post("/contract/negotiate", fd);
      setR(data);
    } catch (e) { setErr(e?.response?.data?.detail || "Negotiation analysis failed"); }
    finally { setBusy(false); }
  };

  const copyEmail = () => {
    if (!r?.ready_to_send_email) return;
    navigator.clipboard.writeText(r.ready_to_send_email);
    alert(t(lang, "copiedToClipboard"));
  };

  // Parse "Subject: ..." from the first line and return { subject, body }
  const parseEmailParts = (raw) => {
    if (!raw) return { subject: "", body: "" };
    const lines = raw.split(/\r?\n/);
    let subject = "";
    let bodyStart = 0;
    const first = (lines[0] || "").trim();
    const m = first.match(/^subject:\s*(.+)$/i);
    if (m) {
      subject = m[1].trim();
      bodyStart = 1;
      // Skip a blank line directly after subject if present
      if ((lines[1] || "").trim() === "") bodyStart = 2;
    }
    return { subject, body: lines.slice(bodyStart).join("\n") };
  };

  const sendEmail = () => {
    if (!r?.ready_to_send_email) return;
    const { subject, body } = parseEmailParts(r.ready_to_send_email);
    const to = (recipientEmail || "").trim();
    const qs = new URLSearchParams();
    if (subject) qs.set("subject", subject);
    if (body) qs.set("body", body);
    const url = `mailto:${encodeURIComponent(to)}?${qs.toString()}`;
    // mailto: links may be blocked in some webviews — open in a way that works on iOS Safari + native wrappers
    window.location.href = url;
  };

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const PRIORITY_STYLE = {
    "must-fix": { bg: "rgba(239,68,68,0.12)", border: "#ef4444", text: "#fca5a5", label: t(lang, "negMustFix") },
    "should-fix": { bg: "rgba(247,201,72,0.12)", border: "var(--gold)", text: "var(--gold)", label: t(lang, "negShouldFix") },
    "nice-to-have": { bg: "rgba(255,255,255,0.05)", border: "var(--line)", text: "var(--text-dim)", label: t(lang, "negNiceToHave") },
  };
  const DIFFICULTY = {
    easy: { color: "#86efac", label: t(lang, "negDifficultyEasy") },
    moderate: { color: "var(--gold)", label: t(lang, "negDifficultyModerate") },
    hard: { color: "#fca5a5", label: t(lang, "negDifficultyHard") },
  };

  return (
    <>
      {!r ? (
        <>
          <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 14 }}>
            {t(lang, "negIntro")}
          </p>

          {/* Hidden inputs */}
          <input ref={cameraRef} type="file" accept="image/*" capture="environment"
                 onChange={choose} style={{ display: "none" }} data-testid="neg-camera-input" />
          <input ref={uploadRef} type="file" accept="image/*,application/pdf,.doc,.docx,.txt"
                 onChange={choose} style={{ display: "none" }} data-testid="neg-upload-input" />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
            <button className="btn-gold" data-testid="neg-camera-btn" onClick={() => cameraRef.current?.click()}
                    style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, padding: "18px 8px" }}>
              <Camera size={22} />
              <span style={{ fontSize: 13 }}>{t(lang, "contractTakePhoto")}</span>
            </button>
            <button className="btn-ghost" data-testid="neg-upload-btn" onClick={() => uploadRef.current?.click()}
                    style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, padding: "18px 8px", border: "1px solid var(--gold-deep)" }}>
              <Upload size={22} />
              <span style={{ fontSize: 13 }}>{t(lang, "contractUploadFile")}</span>
            </button>
          </div>

          {file && (
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, marginBottom: 10, display: "flex", alignItems: "center", gap: 10 }}>
              <FileText size={18} style={{ color: "var(--gold)" }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: "var(--text)", fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</div>
                <div style={{ color: "var(--text-dim)", fontSize: 11 }}>{(file.size / 1024).toFixed(1)} KB</div>
              </div>
              <button onClick={() => { if (preview) URL.revokeObjectURL(preview); setFile(null); setPreview(null); }}
                      style={{ background: "transparent", border: "none", color: "var(--text-dim)", cursor: "pointer" }}>
                <X size={16} />
              </button>
            </div>
          )}

          {/* Role selector */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ color: "var(--gold)", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
              {t(lang, "negYourRole")}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <button data-testid="neg-role-recipient" onClick={() => setUserRole("recipient")}
                      style={{ padding: 10, borderRadius: 10, fontSize: 12,
                               background: userRole === "recipient" ? "rgba(247,201,72,0.15)" : "var(--bg-card)",
                               border: userRole === "recipient" ? "1px solid var(--gold)" : "1px solid var(--line)",
                               color: userRole === "recipient" ? "var(--gold)" : "var(--text)", cursor: "pointer" }}>
                {t(lang, "negRoleRecipient")}
              </button>
              <button data-testid="neg-role-offerer" onClick={() => setUserRole("offerer")}
                      style={{ padding: 10, borderRadius: 10, fontSize: 12,
                               background: userRole === "offerer" ? "rgba(247,201,72,0.15)" : "var(--bg-card)",
                               border: userRole === "offerer" ? "1px solid var(--gold)" : "1px solid var(--line)",
                               color: userRole === "offerer" ? "var(--gold)" : "var(--text)", cursor: "pointer" }}>
                {t(lang, "negRoleOfferer")}
              </button>
            </div>
          </div>

          {/* Priorities */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ color: "var(--gold)", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
              {t(lang, "negPriorities")}
            </div>
            <textarea className="input" rows={3} value={priorities} onChange={(e) => setPriorities(e.target.value)}
                      placeholder={t(lang, "negPrioritiesPlaceholder")} data-testid="neg-priorities-input" />
          </div>

          {file && !busy && (
            <button className="btn-gold w-full" data-testid="neg-analyze-btn" onClick={analyze} style={{ marginBottom: 8 }}>
              <Scale size={16} style={{ display: "inline", marginRight: 6 }} />
              {t(lang, "negAnalyzeBtn")}
            </button>
          )}
          {busy && <div style={{ textAlign: "center", padding: 16 }}><span className="spinner" /><div style={{ color: "var(--text-dim)", marginTop: 8, fontSize: 13 }}>{t(lang, "negBusy")}</div></div>}
          {err && <div style={{ background: "#2a0a0a", border: "1px solid #7f1d1d", color: "#fca5a5", padding: 10, borderRadius: 10, fontSize: 13 }}>{err}</div>}
        </>
      ) : (
        <div data-testid="neg-result">
          {/* Leverage banner */}
          <div style={{ background: "rgba(247,201,72,0.1)", border: "1px solid var(--gold-deep)", borderRadius: 12, padding: 12, marginBottom: 14 }}>
            <div style={{ color: "var(--gold)", fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", marginBottom: 4, textTransform: "uppercase" }}>
              {t(lang, "negLeverage")}
            </div>
            <div style={{ color: "var(--text)", fontSize: 14, lineHeight: 1.5 }}>{r.leverage_assessment}</div>
            {r.estimated_negotiation_difficulty && DIFFICULTY[r.estimated_negotiation_difficulty] && (
              <div style={{ marginTop: 6, fontSize: 11, color: DIFFICULTY[r.estimated_negotiation_difficulty].color }}>
                {t(lang, "negDifficulty")}: <strong>{DIFFICULTY[r.estimated_negotiation_difficulty].label}</strong>
              </div>
            )}
          </div>

          {/* Worst clauses */}
          {r.worst_clauses?.length > 0 && (
            <>
              <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
                {t(lang, "negWorstClauses")} ({r.worst_clauses.length})
              </div>
              {r.worst_clauses.map((c, i) => {
                const ps = PRIORITY_STYLE[c.priority] || PRIORITY_STYLE["should-fix"];
                return (
                  <div key={i} data-testid={`neg-clause-${i}`}
                       style={{ background: ps.bg, border: `1px solid ${ps.border}`, borderRadius: 10, padding: 12, marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <div style={{ color: "var(--gold)", fontSize: 13, fontWeight: 700 }}>{c.clause_title}</div>
                      <span style={{ fontSize: 9, fontWeight: 700, padding: "2px 6px", borderRadius: 4, background: ps.border, color: "#000", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                        {ps.label}
                      </span>
                    </div>
                    {c.current_text_quote && (
                      <div style={{ fontSize: 12, color: "var(--text-dim)", fontStyle: "italic", borderLeft: "2px solid var(--line)", paddingLeft: 8, marginBottom: 8 }}>
                        "{c.current_text_quote}"
                      </div>
                    )}
                    <div style={{ fontSize: 13, color: "var(--text)", marginBottom: 8, lineHeight: 1.5 }}>
                      <strong style={{ color: "#fca5a5" }}>{t(lang, "negWhyBad")}:</strong> {c.why_its_bad_for_user}
                    </div>
                    {c.suggested_redline && (
                      <div style={{ background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.3)", borderRadius: 8, padding: 8, marginBottom: 6 }}>
                        <div style={{ fontSize: 11, color: "#86efac", fontWeight: 700, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                          {t(lang, "negSuggestedRedline")}
                        </div>
                        <div style={{ fontSize: 12, color: "var(--text)", lineHeight: 1.5, fontFamily: "monospace" }}>{c.suggested_redline}</div>
                      </div>
                    )}
                    {c.fallback_position && (
                      <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 6 }}>
                        <strong style={{ color: "var(--gold)" }}>{t(lang, "negFallback")}:</strong> {c.fallback_position}
                      </div>
                    )}
                  </div>
                );
              })}
            </>
          )}

          {/* Missing protections */}
          {r.missing_protections?.length > 0 && (
            <>
              <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", margin: "14px 0 6px" }}>
                {t(lang, "negMissingProtections")}
              </div>
              <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.7 }}>
                {r.missing_protections.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </>
          )}

          {/* Bottom line */}
          {r.do_not_compromise_on?.length > 0 && (
            <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 10, padding: 12, marginTop: 14 }}>
              <div style={{ color: "#fca5a5", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                ⚠ {t(lang, "negDoNotCompromise")}
              </div>
              <ul style={{ color: "var(--text)", fontSize: 13, paddingLeft: 18, lineHeight: 1.7, margin: 0 }}>
                {r.do_not_compromise_on.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </div>
          )}

          {/* Walk away signals */}
          {r.walk_away_signals?.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div style={{ color: "#ef4444", fontSize: 12, fontWeight: 700, textTransform: "uppercase", marginBottom: 6 }}>
                🚪 {t(lang, "negWalkAway")}
              </div>
              <ul style={{ color: "var(--text-dim)", fontSize: 13, paddingLeft: 18, lineHeight: 1.7 }}>
                {r.walk_away_signals.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </div>
          )}

          {/* Strategy */}
          {r.negotiation_strategy && (
            <div style={{ marginTop: 14, padding: 12, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10 }}>
              <div style={{ color: "var(--gold)", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                {t(lang, "negStrategy")}
              </div>
              <div style={{ color: "var(--text)", fontSize: 13, lineHeight: 1.6 }}>{r.negotiation_strategy}</div>
            </div>
          )}

          {/* Ready-to-send email */}
          {r.ready_to_send_email && (
            <div style={{ marginTop: 14 }}>
              <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <Send size={13} /> {t(lang, "negReadyEmail")}
              </div>
              <textarea className="input" rows={10} value={r.ready_to_send_email}
                        onChange={(e) => setR({ ...r, ready_to_send_email: e.target.value })}
                        style={{ fontSize: 12, lineHeight: 1.6, fontFamily: "monospace" }} data-testid="neg-email-textarea" />

              {/* Recipient + Send */}
              <div style={{ marginTop: 10, padding: 12, background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10 }}>
                <label style={{ color: "var(--text-dim)", fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", display: "block", marginBottom: 6 }}>
                  {t(lang, "negRecipientEmail")}
                </label>
                <input type="email" className="input" value={recipientEmail}
                       onChange={(e) => setRecipientEmail(e.target.value)}
                       placeholder={t(lang, "negRecipientPlaceholder")}
                       data-testid="neg-recipient-input"
                       style={{ marginBottom: 8 }} />
                <button className="btn-gold w-full" onClick={sendEmail} data-testid="neg-send-email-btn"
                        style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                  <Send size={16} />
                  {t(lang, "negSendEmail")}
                </button>
                <div style={{ color: "var(--text-dim)", fontSize: 11, marginTop: 6, textAlign: "center" }}>
                  {t(lang, "negSendEmailHint")}
                </div>
              </div>

              <button className="btn-ghost w-full" onClick={copyEmail} style={{ marginTop: 8 }} data-testid="neg-copy-email-btn">
                {t(lang, "negCopyEmail")}
              </button>
            </div>
          )}

          <button className="btn-ghost w-full" onClick={() => { setR(null); setFile(null); if (preview) URL.revokeObjectURL(preview); setPreview(null); setPriorities(""); }} style={{ marginTop: 14 }}>
            {t(lang, "negAnother")}
          </button>
        </div>
      )}
    </>
  );
}

// ---------- Letter Reader (Document Auto-Responder) ----------
function LetterReaderModal({ lang, country, onClose }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");
  const inputRef = useRef(null);
  const uploadRef = useRef(null);

  const choose = (e) => {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    if (preview) URL.revokeObjectURL(preview);
    setFile(f); setPreview(URL.createObjectURL(f)); setResult(null); setErr("");
  };

  const analyze = async () => {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("language", lang);
      fd.append("country", country);
      const { data } = await api.post("/document/analyze", fd);
      setResult(data);
    } catch (e) {
      setErr(e?.response?.data?.detail || "Analysis failed");
    } finally { setBusy(false); }
  };

  const copyResponse = () => {
    if (!result?.suggested_response) return;
    navigator.clipboard.writeText(result.suggested_response);
    alert("Response copied to clipboard");
  };

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const SEV_COLOR = { low: "#22c55e", medium: "#f7c948", high: "#fb923c", urgent: "#ef4444" };

  return (
    <div className="modal-bg" data-testid="letter-reader-modal">
      <div className="modal-card" style={{ padding: 20, overflowY: "auto" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "letterReaderTitle")}</h2>
          <button onClick={onClose} data-testid="letter-reader-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 14 }}>
          Snap or upload any letter — parking tickets, eviction, debt, employment, council tax. Lex categorises it, extracts deadlines, and drafts your response.
        </p>

        {!result && (
          <>
            <input ref={inputRef} type="file" accept="image/*" capture="environment"
                   onChange={choose} style={{ display: "none" }} data-testid="letter-camera-input" />
            <input ref={uploadRef} type="file" accept="image/*,application/pdf,.doc,.docx,.txt"
                   onChange={choose} style={{ display: "none" }} data-testid="letter-upload-input" />

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 12 }}>
              <button className="btn-gold" data-testid="letter-camera-btn" onClick={() => inputRef.current?.click()}
                      style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, padding: "18px 8px" }}>
                <Camera size={22} />
                <span style={{ fontSize: 13 }}>{t(lang, "contractTakePhoto")}</span>
              </button>
              <button className="btn-ghost" data-testid="letter-upload-btn" onClick={() => uploadRef.current?.click()}
                      style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, padding: "18px 8px", border: "1px solid var(--gold-deep)" }}>
                <Upload size={22} />
                <span style={{ fontSize: 13 }}>{t(lang, "contractUploadFile")}</span>
              </button>
            </div>

            {file && (
              <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 10, marginBottom: 10, display: "flex", alignItems: "center", gap: 10 }}>
                <FileText size={18} style={{ color: "var(--gold)" }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ color: "var(--text)", fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</div>
                  <div style={{ color: "var(--text-dim)", fontSize: 11 }}>{(file.size / 1024).toFixed(1)} KB</div>
                </div>
                <button onClick={() => { if (preview) URL.revokeObjectURL(preview); setFile(null); setPreview(null); }}
                        style={{ background: "transparent", border: "none", color: "var(--text-dim)", cursor: "pointer" }}>
                  <X size={16} />
                </button>
              </div>
            )}

            {preview && file?.type?.startsWith("image/") && (
              <div style={{ marginBottom: 10, borderRadius: 12, overflow: "hidden", border: "1px solid var(--line)" }}>
                <img src={preview} alt="Letter" style={{ width: "100%", display: "block", maxHeight: 280, objectFit: "contain", background: "#000" }} />
              </div>
            )}
            {file && !busy && (
              <button className="btn-gold w-full" data-testid="letter-analyze-btn" onClick={analyze} style={{ marginBottom: 8 }}>
                Analyse with Lex
              </button>
            )}
            {busy && <div style={{ textAlign: "center", padding: 16 }}><span className="spinner" /><div style={{ color: "var(--text-dim)", marginTop: 8, fontSize: 13 }}>Lex is reading your letter…</div></div>}
            {err && <div style={{ background: "#2a0a0a", border: "1px solid #7f1d1d", color: "#fca5a5", padding: 10, borderRadius: 10, fontSize: 13 }}>{err}</div>}
          </>
        )}

        {result && (
          <div data-testid="letter-result">
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <span style={{ background: SEV_COLOR[result.severity] || "#888", color: "#000", padding: "3px 10px", borderRadius: 12, fontSize: 11, fontWeight: 700, textTransform: "uppercase" }}>
                {result.severity}
              </span>
              <span style={{ color: "var(--gold)", fontSize: 13, textTransform: "capitalize" }}>{result.category?.replace(/_/g, " ")}</span>
            </div>
            <div style={{ color: "var(--text)", fontSize: 14, lineHeight: 1.6, marginBottom: 14 }}>{result.summary}</div>

            {result.deadlines?.length > 0 && (
              <>
                <h4 style={{ color: "var(--gold)", fontSize: 13, margin: "8px 0", letterSpacing: "0.05em", textTransform: "uppercase" }}>Deadlines</h4>
                {result.deadlines.map((d, i) => (
                  <div key={i} style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 10, padding: 10, marginBottom: 6, fontSize: 13 }}>
                    <strong style={{ color: "var(--gold)" }}>{d.date_iso}</strong> — {d.label}
                  </div>
                ))}
              </>
            )}

            {result.next_steps?.length > 0 && (
              <>
                <h4 style={{ color: "var(--gold)", fontSize: 13, margin: "14px 0 8px", letterSpacing: "0.05em", textTransform: "uppercase" }}>Next steps</h4>
                <ul style={{ paddingLeft: 18, color: "var(--text-dim)", fontSize: 13, lineHeight: 1.7 }}>
                  {result.next_steps.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </>
            )}

            {result.suggested_response && (
              <>
                <h4 style={{ color: "var(--gold)", fontSize: 13, margin: "14px 0 8px", letterSpacing: "0.05em", textTransform: "uppercase" }}>Drafted response</h4>
                <textarea className="input" rows={10} value={result.suggested_response}
                  onChange={(e) => setResult({ ...result, suggested_response: e.target.value })}
                  data-testid="letter-response-textarea"
                  style={{ fontSize: 13, lineHeight: 1.5, fontFamily: "inherit" }} />
                <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                  <button className="btn-gold" data-testid="letter-copy-btn" onClick={copyResponse} style={{ flex: 1 }}>Copy response</button>
                  <button className="btn-ghost" data-testid="letter-new-btn" onClick={() => { setResult(null); setFile(null); if (preview) URL.revokeObjectURL(preview); setPreview(null); }} style={{ flex: 1 }}>Analyse another</button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Stats Wall (anonymous social proof) ----------
function StatsWall({ lang }) {
  const [s, setS] = useState(null);
  useEffect(() => {
    api.get("/stats/public").then(r => setS(r.data)).catch(() => {});
  }, []);
  if (!s) return null;
  const fmt = (n) => (n || 0).toLocaleString();
  const items = [
    { label: t(lang, "statsPeopleHelped"), value: fmt(s.users_helped_total) },
    { label: t(lang, "statsCasesTracked"), value: fmt(s.cases_active) },
    { label: t(lang, "statsLettersDrafted"), value: fmt(s.letters_drafted) },
    { label: t(lang, "statsDocsAnalysed"), value: fmt(s.documents_analysed) },
  ];
  return (
    <div data-testid="stats-wall" style={{ marginTop: 20, padding: "12px 14px", background: "rgba(247,201,72,0.04)", border: "1px solid var(--line)", borderRadius: 14 }}>
      <div style={{ color: "var(--gold)", fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8, textAlign: "center" }}>
        {t(lang, "statsTitle")}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {items.map((it, i) => (
          <div key={i} style={{ textAlign: "center" }}>
            <div style={{ color: "var(--gold)", fontSize: 20, fontWeight: 700, fontFamily: "Cinzel, serif" }}>{it.value}</div>
            <div style={{ color: "var(--text-muted)", fontSize: 11 }}>{it.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Daily Tip Card (lives at top of dashboard) ----------
function DailyTipCard({ lang, country }) {
  const [tip, setTip] = useState(null);
  useEffect(() => {
    api.get("/tips/daily", { params: { language: lang, country } })
       .then(r => setTip(r.data?.tip))
       .catch(() => {});
  }, [lang, country]);
  if (!tip) return null;
  return (
    <div data-testid="daily-tip-card"
         style={{ background: "linear-gradient(135deg, rgba(247,201,72,0.08) 0%, rgba(247,201,72,0.02) 100%)",
                  border: "1px solid var(--gold-deep)", borderRadius: 14, padding: "10px 14px",
                  marginBottom: 12, display: "flex", alignItems: "flex-start", gap: 10 }}>
      <div style={{ color: "var(--gold)", fontSize: 18, lineHeight: 1 }}>💡</div>
      <div>
        <div style={{ color: "var(--gold)", fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 2 }}>
          {t(lang, "tipOfTheDay")}
        </div>
        <div style={{ color: "var(--text)", fontSize: 13, lineHeight: 1.5 }}>{tip}</div>
      </div>
    </div>
  );
}

// ---------- Root App ----------
function SplashScreen({ onDone }) {
  const videoRef = useRef(null);
  const [fadeOut, setFadeOut] = useState(false);
  const calledRef = useRef(false);

  const finish = useCallback(() => {
    if (calledRef.current) return;
    calledRef.current = true;
    setFadeOut(true);
    setTimeout(() => onDone(), 600);
  }, [onDone]);

  useEffect(() => {
    // New video is 3.15s — cap slightly longer in case of network buffering
    const t = setTimeout(finish, 3600);
    return () => clearTimeout(t);
  }, [finish]);

  return (
    <div data-testid="splash-screen"
      style={{
        position: "fixed", inset: 0, background: "#000",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 9999, opacity: fadeOut ? 0 : 1,
        transition: "opacity 0.6s ease-out", pointerEvents: fadeOut ? "none" : "auto",
        overflow: "hidden",
      }}
      onClick={finish}
    >
      {/* Static poster image behind the video — shows the logo INSTANTLY while the
          MP4 is still buffering its first frame. Same size + mask as the video so the
          handover is invisible. Removes the perceived "flicker / refreshing" feel. */}
      <img
        src="/assets/splash-midframe.jpg"
        alt=""
        aria-hidden="true"
        draggable={false}
        style={{
          position: "absolute",
          top: "50%", left: "50%",
          transform: "translate(-50%, -50%)",
          width: "min(75vmin, 520px)",
          height: "min(75vmin, 520px)",
          objectFit: "contain",
          filter: "brightness(1.15) saturate(1.2)",
          // Tighter circular mask: fully opaque inside 38%, fully transparent by 65%.
          // Kills the rectangular video boundary completely — only the logo + its
          // immediate halo are visible, the surrounding dark backdrop is gone.
          WebkitMaskImage:
            "radial-gradient(circle at center, #000 38%, rgba(0,0,0,0.6) 52%, rgba(0,0,0,0) 65%)",
          maskImage:
            "radial-gradient(circle at center, #000 38%, rgba(0,0,0,0.6) 52%, rgba(0,0,0,0) 65%)",
          pointerEvents: "none",
        }}
      />
      <video
        ref={videoRef}
        src="/assets/splash-clean.mp4"
        autoPlay muted playsInline
        onEnded={finish}
        onError={finish}
        className="aa-splash-video"
        style={{
          position: "relative",
          width: "min(75vmin, 520px)",
          height: "min(75vmin, 520px)",
          objectFit: "contain",
          background: "transparent",
          display: "block",
          filter: "brightness(1.15) saturate(1.2)",
          WebkitMaskImage:
            "radial-gradient(circle at center, #000 38%, rgba(0,0,0,0.6) 52%, rgba(0,0,0,0) 65%)",
          maskImage:
            "radial-gradient(circle at center, #000 38%, rgba(0,0,0,0.6) 52%, rgba(0,0,0,0) 65%)",
        }}
      />
    </div>
  );
}


// ============================== LEX CHAT LEGAL DISCLAIMER ==============================
function LexDisclaimerBanner({ lang }) {
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem("aa_lex_disclaimer_seen") === "1");
  if (dismissed) return null;
  return (
    <div data-testid="lex-disclaimer-banner" style={{ padding: 10, background: "rgba(247,201,72,0.08)", border: "1px solid var(--gold-deep)", borderRadius: 10, fontSize: 11, color: "var(--text-dim)", lineHeight: 1.5, display: "flex", gap: 8 }}>
      <ShieldCheck size={14} style={{ color: "var(--gold)", flexShrink: 0, marginTop: 1 }} />
      <div style={{ flex: 1 }}>
        <span style={{ color: "var(--gold)", fontWeight: 600 }}>{t(lang, "lexDisclaimerTitle")}: </span>
        {t(lang, "lexDisclaimerBody")}
      </div>
      <button onClick={() => { sessionStorage.setItem("aa_lex_disclaimer_seen", "1"); setDismissed(true); }}
              data-testid="lex-disclaimer-dismiss"
              style={{ background: "transparent", border: "none", color: "var(--text-dim)", cursor: "pointer", padding: 0 }}>
        <X size={14} />
      </button>
    </div>
  );
}

// ============================== LEGAL DOC MODAL (TOS + PRIVACY) ==============================
const TOS_TEXT = `# Terms of Service

**AI Advocate** ("we", "us", "the App") provides AI-powered general legal information. By using the App, you agree to these terms.

**1. Not legal advice.** AI Advocate is an information service, NOT a regulated legal practice. The AI is not a solicitor, barrister, or qualified lawyer. Nothing in the App creates a solicitor-client relationship. For binding legal advice on your specific case, instruct a regulated solicitor (SRA in England & Wales; LSS in Scotland; LSNI in Northern Ireland; equivalent body in your country).

**2. Eligibility & age.** You must be 18 or older. By signing up, you confirm you are 18+.

**3. Accuracy.** We strive for accuracy but legal information can be wrong, out-of-date, or jurisdiction-specific. You bear the risk of acting on AI output. We are NOT liable for losses arising from reliance on AI responses.

**4. Recording features.** The App provides audio-recording features (Hearing Recorder, Record Legal Interaction). Recording laws vary by country and setting. You — not AI Advocate — are responsible for the legality of any recording you make. Recording in a courtroom is a criminal offence in the UK (Contempt of Court Act 1981 s.9) and most countries.

**5. Vault.** The Lex Vault uses end-to-end encryption with a PIN that only you know. If you lose your PIN, your vault items are PERMANENTLY UNRECOVERABLE. We do not hold a copy.

**6. Subscriptions, free trial & auto-renewal.** Free 7-day trial of paid features on signup. Paid plans renew automatically at £19.99/mo (Plus), £34.99/mo (Pro), or £319.99/yr (Yearly Pro). Cancel any time 24h before renewal. Refunds via the store that processed your payment (Apple/Google/Stripe).

**7. Misuse.** You may not use the App for: harassment, illegal recording, defamation, doxing, or building tools that compete with the App.

**8. Termination.** We may suspend accounts that violate these terms. You may delete your account at any time via Settings → Manage My Data.

**9. Limitation of liability.** To the maximum extent permitted by law, our total liability to you in any 12-month period is capped at the greater of (a) £100 or (b) the subscription fees you paid us in that period.

**10. Governing law.** These terms are governed by the laws of England & Wales. Disputes are subject to the exclusive jurisdiction of the English courts, unless your local consumer-protection law provides otherwise.

**11. Contact.** support@aiadvocate.app

Last updated: 2026-02-18.`;

const PRIVACY_TEXT = `# Privacy Policy

**AI Advocate** is committed to protecting your privacy. This policy explains what data we collect, why, and your rights under UK-GDPR and EU-GDPR.

## What we collect
- **Account data**: email, name, password hash (bcrypt), country, language preference.
- **Usage data**: which features you use, error logs, anonymous analytics (if enabled).
- **Lex chat content**: your messages + Lex's responses. **Encrypted at rest** in our database using AES-128 + HMAC.
- **Case files**: titles, summaries, uploaded documents. Summaries encrypted at rest.
- **Vault items**: encrypted on YOUR device with your PIN. We cannot read them.
- **Recording features**: audio files you record are sent to OpenAI Whisper for transcription, then DELETED from our servers. Transcript text is kept in your case files.
- **Payment data**: handled entirely by Stripe (PCI-DSS Level 1). We never see your card number.

## Why we collect it
- To provide the legal-information service you signed up for (lawful basis: contract).
- To improve the product (lawful basis: legitimate interest, anonymised aggregates only).
- To comply with tax/legal record-keeping (lawful basis: legal obligation, retention 6 years).

## Third parties we share with
- **Anthropic** (Claude) — your messages are sent to Claude for processing. Anthropic does NOT train on Universal-Key API traffic.
- **OpenAI** — Whisper for audio transcription; data deleted after processing.
- **Google** — Gemini for vision/extraction of contracts/photos.
- **Stripe** — payment processing.
- **Apple / Google** — if you use their sign-in: name, email, sub identifier.
- We do NOT sell your data to advertisers or data brokers, ever.

## Your rights under GDPR / UK-GDPR
- **Access**: request a copy of all your data (Settings → Export My Data).
- **Erasure**: delete your account and all personal data (Settings → Delete My Account).
- **Rectification**: edit your profile.
- **Portability**: export as JSON.
- **Objection / restriction**: email support@aiadvocate.app.
- **Complaint**: lodge a complaint with the ICO at ico.org.uk.

## Security
TLS 1.3 in transit. Bcrypt for passwords. Fernet (AES-128 + HMAC) for sensitive fields at rest. Vault uses client-side AES-GCM-256 with PIN-derived keys (PBKDF2 250k iterations).

## Children
The App is not for users under 18.

## Data retention
Active accounts: indefinitely while you remain a user. Deleted accounts: personal data permanently erased within 30 days (subscription/billing records anonymised after 6 years).

## International transfers
Our servers are in the EU. LLM processing may be in the US under Standard Contractual Clauses.

## Contact
For any privacy question: privacy@aiadvocate.app
Data Protection Officer: dpo@aiadvocate.app

Last updated: 2026-02-18.`;

function LegalDocModal({ kind, lang, onClose }) {
  const text = kind === "tos" ? TOS_TEXT : PRIVACY_TEXT;
  return (
    <div className="modal-bg" data-testid={`legal-${kind}-modal`}>
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
          <h2 className="brand-font gold" style={{ fontSize: 18 }}>{kind === "tos" ? t(lang, "tosTitle") : t(lang, "privacyTitle")}</h2>
          <button onClick={onClose} data-testid={`legal-${kind}-close`} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>
        <div style={{ overflowY: "auto", flex: 1, minHeight: 0, fontSize: 13, lineHeight: 1.6, color: "var(--text)", whiteSpace: "pre-wrap" }}>
          {text}
        </div>
      </div>
    </div>
  );
}

// ============================== MANAGE MY DATA (GDPR) ==============================
function ManageDataModal({ lang, onClose, onAccountDeleted }) {
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  const exportData = async () => {
    setBusy(true);
    try {
      const { data } = await api.get("/users/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `ai-advocate-export-${new Date().toISOString().slice(0,10)}.json`;
      document.body.appendChild(a); a.click();
      setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
    } catch (e) { alert("Export failed. Try again later."); }
    finally { setBusy(false); }
  };

  const deleteAccount = async () => {
    if (confirmText !== "DELETE") return;
    setBusy(true);
    try {
      await api.delete("/users/me");
      localStorage.removeItem("aa_token");
      onAccountDeleted && onAccountDeleted();
    } catch (e) { alert("Could not delete account. Email support@aiadvocate.app"); }
    finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="manage-data-modal">
      <div className="modal-card" style={{ padding: 20 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 18 }}>{t(lang, "manageDataTitle")}</h2>
          <button onClick={onClose} data-testid="manage-data-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>

        <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 14, marginBottom: 12 }}>
          <div style={{ color: "var(--gold)", fontSize: 12, fontWeight: 700, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            {t(lang, "exportTitle")}
          </div>
          <div style={{ color: "var(--text-dim)", fontSize: 12, lineHeight: 1.5, marginBottom: 10 }}>{t(lang, "exportBody")}</div>
          <button className="btn-gold w-full" onClick={exportData} disabled={busy} data-testid="export-data-btn">
            <Download size={14} style={{ display: "inline", marginRight: 6 }} /> {t(lang, "exportBtn")}
          </button>
        </div>

        <div style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 10, padding: 14 }}>
          <div style={{ color: "#fca5a5", fontSize: 12, fontWeight: 700, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            {t(lang, "deleteTitle")}
          </div>
          <div style={{ color: "var(--text-dim)", fontSize: 12, lineHeight: 1.5, marginBottom: 10 }}>{t(lang, "deleteBody")}</div>
          {!confirmDelete ? (
            <button onClick={() => setConfirmDelete(true)} data-testid="delete-account-init"
                    style={{ width: "100%", padding: 12, background: "transparent", border: "1px solid #ef4444", borderRadius: 10, color: "#fca5a5", cursor: "pointer", fontWeight: 600 }}>
              <Trash2 size={14} style={{ display: "inline", marginRight: 6 }} /> {t(lang, "deleteBtn")}
            </button>
          ) : (
            <>
              <div style={{ color: "#fca5a5", fontSize: 12, marginBottom: 8 }}>{t(lang, "deleteTypeConfirm")}</div>
              <input className="input" value={confirmText} onChange={(e) => setConfirmText(e.target.value.toUpperCase())}
                     placeholder="DELETE" data-testid="delete-confirm-input" style={{ marginBottom: 10 }} />
              <div style={{ display: "flex", gap: 6 }}>
                <button onClick={() => { setConfirmDelete(false); setConfirmText(""); }} className="btn-ghost" style={{ flex: 1 }}>Cancel</button>
                <button onClick={deleteAccount} disabled={busy || confirmText !== "DELETE"} data-testid="delete-account-confirm"
                        style={{ flex: 2, padding: 12, background: confirmText === "DELETE" ? "linear-gradient(135deg,#7f1d1d,#dc2626)" : "rgba(127,29,29,0.3)", color: "#fff", border: "none", borderRadius: 10, fontWeight: 700, cursor: confirmText === "DELETE" ? "pointer" : "not-allowed" }}>
                  {busy ? <span className="spinner" /> : t(lang, "deleteFinalBtn")}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [lang, setLang] = useState(localStorage.getItem("aa_lang") || "en-GB");
  const [country, setCountry] = useState(localStorage.getItem("aa_country") || "GB");
  const [step, setStep] = useState("loading"); // loading | lang | terms | auth | app
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("aa_token"));
  // Splash plays once per browser-tab session (not on every screen change)
  const [showSplash, setShowSplash] = useState(() => !sessionStorage.getItem("aa_splash_seen"));

  useEffect(() => { localStorage.setItem("aa_lang", lang); document.documentElement.dir = RTL_LANGS.includes(lang) ? "rtl" : "ltr"; }, [lang]);
  useEffect(() => { localStorage.setItem("aa_country", country); }, [country]);

  // Bootstrap
  useEffect(() => {
    if (token) {
      setAuthHeader(token);
      api.get("/auth/me").then(r => { setUser(r.data); setSentryUser(r.data); identifyAnalytics(r.data); setLang(r.data.language || lang); setCountry(r.data.country || country); setStep("app"); })
        .catch(() => { localStorage.removeItem("aa_token"); setToken(null); setStep(localStorage.getItem("aa_terms") ? "auth" : "lang"); });
    } else {
      setStep(localStorage.getItem("aa_terms") ? "auth" : "lang");
    }
  // eslint-disable-next-line
  }, []);

  // 📱 Hide the native Capacitor splash once React has rendered + auth resolved. No-op on web.
  useEffect(() => {
    if (step !== "loading") { hideSplash().catch(() => {}); }
  }, [step]);

  // Deep-link: /engage/<token> — store the invite token so EngagementsModal can auto-accept it after login
  useEffect(() => {
    const m = (window.location.pathname || "").match(/^\/engage\/([A-Za-z0-9_-]+)/);
    if (m && m[1]) {
      sessionStorage.setItem("aa_pending_invite", m[1]);
      // Replace the URL so the token is no longer visible in the address bar
      try { window.history.replaceState({}, "", "/"); } catch (e) { /* no-op */ }
    }
  }, []);

  // Unlock audio playback on the very first user gesture (any tap anywhere). This is iOS Safari's
  // requirement to allow programmatic audio.play() later (when the wake word triggers TTS).
  useEffect(() => {
    const unlock = () => {
      unlockAudio();
      window.removeEventListener("touchstart", unlock);
      window.removeEventListener("click", unlock);
    };
    window.addEventListener("touchstart", unlock, { once: true });
    window.addEventListener("click", unlock, { once: true });
    return () => {
      window.removeEventListener("touchstart", unlock);
      window.removeEventListener("click", unlock);
    };
  }, []);

  const onAuth = (data) => {
    localStorage.setItem("aa_token", data.access_token); setToken(data.access_token); setAuthHeader(data.access_token);
    setUser(data.user); setSentryUser(data.user); identifyAnalytics(data.user); track("user_signed_in"); setStep("app");
  };
  const onLogout = () => { localStorage.removeItem("aa_token"); setToken(null); setUser(null); setAuthHeader(null); clearSentryUser(); resetAnalytics(); setStep("auth"); };

  if (step === "loading") return <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}><span className="spinner" /></div>;

  return (
    <div className="App app-shell">
      <AAConfirmHost />
      <CookieConsentBanner />
      {showSplash && <SplashScreen onDone={() => { sessionStorage.setItem("aa_splash_seen", "1"); setShowSplash(false); }} />}
      {step === "lang" && <LanguagePicker lang={lang} initial={lang} onConfirm={(l) => { setLang(l); setStep("terms"); }} />}
      {step === "terms" && <TermsScreen lang={lang} onAccept={() => { localStorage.setItem("aa_terms", "1"); setStep("auth"); }} onDecline={() => setStep("lang")} onChangeLang={() => setStep("lang")} />}
      {step === "auth" && <AuthScreen lang={lang} country={country} onAuth={onAuth} />}
      {step === "app" && user && !showSplash && <Dashboard user={user} lang={lang} country={country} setLang={setLang} setCountry={setCountry} onLogout={onLogout} refreshUser={(u) => setUser(u)} />}
    </div>
  );
}

// ============================== ENGAGEMENTS MODAL (My Solicitor) ==============================
function EngagementsModal({ lang, country, user, onClose }) {
  const [view, setView] = useState("list");          // "list" | "thread"
  const [engagements, setEngagements] = useState([]);
  const [active, setActive] = useState(null);
  const [busy, setBusy] = useState(false);
  const [inviteInput, setInviteInput] = useState("");
  const [err, setErr] = useState("");

  const load = async () => {
    setBusy(true);
    try {
      const { data } = await api.get("/engagements");
      setEngagements(data.engagements || []);
    } catch (e) { setErr("Failed to load."); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    load();
    // Auto-consume any pending invite from a /engage/<token> deep-link
    const pending = sessionStorage.getItem("aa_pending_invite");
    if (pending) {
      sessionStorage.removeItem("aa_pending_invite");
      setInviteInput(pending);
    }
  }, []);

  const extractToken = (s) => {
    s = (s || "").trim();
    const m = s.match(/\/engage\/([A-Za-z0-9_-]+)/);
    return m ? m[1] : s;
  };

  const acceptInvite = async () => {
    const tok = extractToken(inviteInput);
    if (!tok) return;
    setBusy(true); setErr("");
    try {
      await api.post(`/engagements/accept/${tok}`);
      track("engagement_accepted");
      setInviteInput("");
      await load();
    } catch (e) {
      setErr(e?.response?.data?.detail || t(lang, "engInviteInvalid"));
    } finally { setBusy(false); }
  };

  if (view === "thread" && active) {
    return <EngagementThread lang={lang} engagement={active} onBack={() => { setView("list"); setActive(null); load(); }} onClose={onClose} />;
  }

  return (
    <div className="modal-bg" data-testid="engagements-modal">
      <div className="modal-card" style={{ padding: 22, display: "flex", flexDirection: "column" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 16, flexShrink: 0 }}>
          <h2 className="brand-font gold" style={{ fontSize: 22 }}>{t(lang, "mySolicitor")}</h2>
          <button onClick={onClose} data-testid="engagements-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>

        <div style={{ flex: 1, overflowY: "auto" }}>
          {/* Invite paste box */}
          <div style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 12, padding: 14, marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: "var(--gold)", fontWeight: 700, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              {t(lang, "engInviteCode")}
            </div>
            <input data-testid="invite-input" value={inviteInput} onChange={(e) => setInviteInput(e.target.value)}
                   placeholder={t(lang, "engPasteCode")}
                   style={{ width: "100%", padding: "10px 12px", background: "#0a0a0a", border: "1px solid var(--line)", borderRadius: 8, color: "var(--text)", fontSize: 13, marginBottom: 8 }} />
            <button data-testid="invite-accept-btn" className="btn-gold" onClick={acceptInvite} disabled={busy || !inviteInput.trim()}
                    style={{ width: "100%", padding: 10, fontSize: 13 }}>
              {t(lang, "engAcceptBtn")}
            </button>
            {err && <div style={{ color: "#fca5a5", fontSize: 12, marginTop: 8 }} data-testid="invite-err">{err}</div>}
          </div>

          {/* Engagements list */}
          {busy && engagements.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text-dim)", fontSize: 13, padding: 30 }}>Loading…</div>
          ) : engagements.length === 0 ? (
            <div data-testid="no-engagements" style={{ textAlign: "center", padding: 30, color: "var(--text-dim)" }}>
              <div style={{ color: "var(--gold)", opacity: 0.5, marginBottom: 12 }}><HandshakeIcon size={48} /></div>
              <div style={{ color: "var(--text)", fontWeight: 600, marginBottom: 8 }}>{t(lang, "noEngagementsTitle")}</div>
              <div style={{ fontSize: 12, lineHeight: 1.5 }}>{t(lang, "noEngagementsSub")}</div>
            </div>
          ) : (
            engagements.map(e => (
              <button key={e.id} data-testid={`engagement-${e.id}`} onClick={() => { setActive(e); setView("thread"); }}
                      style={{ display: "block", width: "100%", textAlign: "left", background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, padding: 14, marginBottom: 10, cursor: "pointer", color: "var(--text)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <div style={{ fontWeight: 700, color: "var(--gold)", fontSize: 14 }}>{e.firm_name || t(lang, "engInviteSent")}</div>
                  <span style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", padding: "2px 8px", borderRadius: 6,
                    background: e.status === "active" ? "rgba(34,197,94,0.15)" : e.status === "closed" ? "rgba(239,68,68,0.12)" : "rgba(247,201,72,0.15)",
                    color: e.status === "active" ? "#86efac" : e.status === "closed" ? "#fca5a5" : "var(--gold)",
                  }}>{t(lang, e.status === "active" ? "engStatusActive" : e.status === "closed" ? "engStatusClosed" : "engStatusInvited")}</span>
                </div>
                <div style={{ fontSize: 12, color: "var(--text-dim)" }}>{t(lang, "engCase")}: {e.matter}</div>
                {e.case_summary && <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>{e.case_summary.slice(0, 120)}{e.case_summary.length > 120 ? "…" : ""}</div>}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function EngagementThread({ lang, engagement, onBack, onClose }) {
  const [messages, setMessages] = useState([]);
  const [files, setFiles] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [lexOut, setLexOut] = useState("");
  const [showFileShare, setShowFileShare] = useState(false);
  const messagesEndRef = useRef(null);

  const eid = engagement.id;
  const isClosed = engagement.status === "closed";

  const load = async () => {
    try {
      const [m, f] = await Promise.all([
        api.get(`/engagements/${eid}/messages`),
        api.get(`/engagements/${eid}/files`),
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
    try {
      await api.post(`/engagements/${eid}/messages`, { body: draft.trim() });
      setDraft(""); setLexOut(""); await load();
    } catch (e) { alert(e?.response?.data?.detail || "Failed to send."); }
    finally { setBusy(false); }
  };

  const askLex = async (kind) => {
    setBusy(true); setLexOut("");
    try {
      const { data } = await api.post(`/engagements/${eid}/lex-assist`, { kind });
      setLexOut(data.output || "");
      if (kind === "draft_reply") setDraft(data.output || "");
    } catch (e) { alert("Lex temporarily unavailable. Try again."); }
    finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="engagement-thread">
      <div className="modal-card" style={{ padding: 18, display: "flex", flexDirection: "column" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12, flexShrink: 0 }}>
          <button onClick={onBack} data-testid="thread-back" style={{ background: "transparent", border: "none", color: "var(--gold)", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}>
            <ArrowLeft size={18} /> Back
          </button>
          <div style={{ flex: 1, textAlign: "center", color: "var(--gold)", fontFamily: "Cinzel, serif", fontSize: 14 }}>{engagement.firm_name}</div>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={20} /></button>
        </div>

        <div style={{ fontSize: 11, color: "var(--text-muted)", textAlign: "center", marginBottom: 12, padding: "0 8px" }}>
          🔒 End-to-end encrypted · {engagement.matter} · <span style={{ color: isClosed ? "#fca5a5" : "#86efac" }}>{t(lang, isClosed ? "engStatusClosed" : "engStatusActive")}</span>
        </div>

        <div style={{ flex: 1, overflowY: "auto", padding: "4px 2px" }}>
          {messages.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text-dim)", fontSize: 12, padding: 30 }}>{t(lang, "engThreadEmpty")}</div>
          ) : (
            messages.map(m => (
              <div key={m.id} data-testid={`msg-${m.id}`} style={{ display: "flex", justifyContent: m.sender_kind === "client" ? "flex-end" : "flex-start", marginBottom: 10 }}>
                <div style={{
                  maxWidth: "82%", padding: "8px 12px", borderRadius: 14,
                  background: m.sender_kind === "client" ? "linear-gradient(135deg,#d6a017,#b88a1e)" : "var(--bg-card)",
                  border: m.sender_kind === "client" ? "none" : "1px solid var(--line)",
                  color: m.sender_kind === "client" ? "#1a1300" : "var(--text)",
                  fontSize: 13, lineHeight: 1.5, whiteSpace: "pre-wrap",
                }}>
                  {m.body}
                  <div style={{ fontSize: 9, opacity: 0.7, marginTop: 4 }}>
                    {m.sender_kind === "client" ? t(lang, "engSentByYou") : t(lang, "engSentByFirm")} · {new Date(m.created_at).toLocaleString(lang)}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {files.length > 0 && (
          <div style={{ marginTop: 8, marginBottom: 6, padding: "8px 10px", background: "rgba(247,201,72,0.05)", border: "1px solid var(--gold-deep)", borderRadius: 10 }}>
            <div style={{ fontSize: 10, color: "var(--gold)", fontWeight: 700, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              📎 Shared files ({files.length})
            </div>
            {files.slice(0, 3).map(f => (
              <div key={f.id} data-testid={`file-${f.id}`} style={{ fontSize: 12, color: "var(--text)", padding: "3px 0", display: "flex", justifyContent: "space-between" }}>
                <span>{f.title} <span style={{ color: "var(--text-muted)", fontSize: 10 }}>({Math.round(f.size_bytes / 1024)} KB)</span></span>
                <button data-testid={`dl-${f.id}`} onClick={async () => {
                  try {
                    const { data } = await api.get(`/engagements/${eid}/files/${f.id}`);
                    const blob = new Blob([Uint8Array.from(atob(data.file_b64), c => c.charCodeAt(0))], { type: data.mime_type });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a"); a.href = url; a.download = f.title; document.body.appendChild(a); a.click();
                    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 500);
                  } catch (e) { alert("Failed to download."); }
                }} style={{ background: "transparent", border: "none", color: "var(--gold)", cursor: "pointer", fontSize: 11 }}>
                  <Download size={12} /> Download
                </button>
              </div>
            ))}
            {files.length > 3 && <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 4 }}>+ {files.length - 3} more</div>}
          </div>
        )}

        {lexOut && (
          <div style={{ marginTop: 6, padding: 10, background: "rgba(247,201,72,0.06)", border: "1px solid var(--gold-deep)", borderRadius: 10 }}>
            <div style={{ fontSize: 10, color: "var(--gold)", fontWeight: 700, marginBottom: 6, textTransform: "uppercase" }}>🤖 Lex</div>
            <div style={{ fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap", color: "var(--text)" }}>{lexOut}</div>
            <button onClick={() => setLexOut("")} style={{ background: "transparent", border: "none", color: "var(--text-dim)", fontSize: 11, marginTop: 6, cursor: "pointer" }}>Dismiss</button>
          </div>
        )}

        {!isClosed && (
          <>
            <div style={{ display: "flex", gap: 8, marginTop: 10, flexShrink: 0 }}>
              <button data-testid="lex-draft-btn" onClick={() => askLex("draft_reply")} disabled={busy}
                      style={{ flex: 1, padding: 8, background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 8, fontSize: 11, cursor: "pointer" }}>
                ✨ {t(lang, "engLexDraft")}
              </button>
              <button data-testid="lex-summary-btn" onClick={() => askLex("summarise")} disabled={busy}
                      style={{ flex: 1, padding: 8, background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 8, fontSize: 11, cursor: "pointer" }}>
                📋 {t(lang, "engLexSummary")}
              </button>
              <button data-testid="share-file-btn" onClick={() => setShowFileShare(true)} disabled={busy}
                      style={{ padding: 8, background: "transparent", border: "1px solid var(--gold-deep)", color: "var(--gold)", borderRadius: 8, fontSize: 11, cursor: "pointer" }}>
                📎
              </button>
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 10, flexShrink: 0, alignItems: "flex-end" }}>
              <textarea data-testid="thread-input" value={draft} onChange={(e) => setDraft(e.target.value)} rows={2}
                        placeholder={t(lang, "engTypeMsg")}
                        style={{ flex: 1, padding: 10, background: "#0a0a0a", border: "1px solid var(--line)", borderRadius: 10, color: "var(--text)", fontSize: 13, resize: "none" }} />
              <button data-testid="thread-send-btn" className="btn-gold" onClick={send} disabled={busy || !draft.trim()} style={{ padding: "10px 14px", fontSize: 13 }}>
                <Send size={14} />
              </button>
            </div>
          </>
        )}
        {isClosed && (
          <div style={{ textAlign: "center", padding: 12, color: "var(--text-dim)", fontSize: 12, borderTop: "1px solid var(--line)", marginTop: 10 }}>
            This engagement is closed. No new messages can be sent.
          </div>
        )}
      </div>

      {showFileShare && <EngagementFileShare lang={lang} eid={eid} onClose={() => setShowFileShare(false)} onUploaded={async () => { setShowFileShare(false); await load(); }} />}
    </div>
  );
}

function EngagementFileShare({ lang, eid, onClose, onUploaded }) {
  const [file, setFile] = useState(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const upload = async () => {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) { alert("Max 12MB per file."); return; }
    setBusy(true);
    try {
      const b64 = await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(",")[1]);
        r.onerror = rej; r.readAsDataURL(file);
      });
      await api.post(`/engagements/${eid}/files`, { title: file.name, mime_type: file.type || "application/octet-stream", file_b64: b64, note });
      onUploaded();
    } catch (e) { alert(e?.response?.data?.detail || "Upload failed."); }
    finally { setBusy(false); }
  };

  return (
    <div className="modal-bg" data-testid="file-share-modal" style={{ zIndex: 10001 }}>
      <div className="modal-card" style={{ padding: 20, maxHeight: 360 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h3 className="brand-font gold" style={{ fontSize: 17 }}>{t(lang, "engShareFile")}</h3>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={20} /></button>
        </div>
        <input type="file" data-testid="file-share-input" onChange={(e) => setFile(e.target.files[0])} style={{ marginBottom: 10, color: "var(--text)", fontSize: 13 }} />
        {file && <div style={{ fontSize: 11, color: "var(--text-dim)", marginBottom: 10 }}>{file.name} ({Math.round(file.size / 1024)} KB)</div>}
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder={t(lang, "engFileNote")}
                  style={{ width: "100%", padding: 10, background: "#0a0a0a", border: "1px solid var(--line)", borderRadius: 8, color: "var(--text)", fontSize: 13, marginBottom: 12 }} />
        <button data-testid="file-share-upload" className="btn-gold w-full" onClick={upload} disabled={busy || !file} style={{ padding: 10 }}>
          {busy ? "Uploading…" : t(lang, "engFileUpload")}
        </button>
        <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 8, textAlign: "center" }}>
          🔒 Encrypted at rest. Only you and your solicitor can access.
        </div>
      </div>
    </div>
  );
}

export default App;
