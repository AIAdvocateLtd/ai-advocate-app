import React, { useState, useEffect, useRef, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import {
  MessageCircle, Mic, Folder, FileText, Gavel, Globe, Briefcase, Home as HomeIcon,
  Stethoscope, Scale, X, Send, Upload, Languages, LogOut, Check, ArrowLeft, Square, Play,
  Camera, MapPin, Phone, ExternalLink, Settings as SettingsIcon, Star, Building2, Image as ImageIcon,
  Download, Trash2
} from "lucide-react";
import { STRINGS, t, RTL_LANGS } from "@/i18n";

// Apple Reader-App compliance — when running inside the native iOS binary,
// we hide all Subscribe / Upgrade buttons (and replace them with a web-billing notice).
// This passes Apple Guideline 3.1.3(a). Web users see Stripe checkout as normal.
const IS_NATIVE = typeof window !== "undefined" && !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
import {
  AskLexIcon, RecordIcon, CameraIcon, LawyerIcon, FilesIcon, LetterIcon,
  CourtIcon, ImmigrationIcon, EmploymentIcon, PropertyIcon, MedicalIcon
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
  { code: "en-GB", name: "English", flag: "🇬🇧" }, { code: "es-ES", name: "Español", flag: "🇪🇸" },
  { code: "fr-FR", name: "Français", flag: "🇫🇷" }, { code: "ar-IQ", name: "العربية", flag: "🇮🇶" },
  { code: "pl-PL", name: "Polski", flag: "🇵🇱" }, { code: "de-DE", name: "Deutsch", flag: "🇩🇪" },
  { code: "hi-IN", name: "हिन्दी", flag: "🇮🇳" }, { code: "ur-PK", name: "اردو", flag: "🇵🇰" },
  { code: "it-IT", name: "Italiano", flag: "🇮🇹" }, { code: "pt-PT", name: "Português", flag: "🇵🇹" },
  { code: "zh-CN", name: "中文 (简体)", flag: "🇨🇳" },
];

// ---------- API helpers ----------
const api = axios.create({ baseURL: API });
const setAuthHeader = (token) => {
  if (token) api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  else delete api.defaults.headers.common["Authorization"];
};

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
const Logo = ({ size = "lg" }) => {
  const w = size === "lg" ? 220 : size === "md" ? 140 : 80;
  return (
    <div className="flex flex-col items-center" data-testid="app-logo">
      <img src="/assets/logo.jpg" alt="AI Advocate"
           style={{ width: w, height: "auto", display: "block",
                    mixBlendMode: "lighten" }} />
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
              <span style={{ fontSize: 22 }}>{l.flag}</span>
              <span style={{ flex: 1 }}>{l.name}</span>
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
                  style={{ padding: "8px 14px", fontSize: 24, lineHeight: 1 }}>
            {(LANGS.find(l => l.code === lang) || LANGS[0]).flag}
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
        <div className="flex gap-2" style={{ marginTop: 14, flexShrink: 0 }}>
          <button className="btn-gold" data-testid="accept-terms-btn" disabled={!agree || busy} style={{ flex: 2 }} onClick={onAccept}>{t(lang, "accept")}</button>
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
    if (!window.google?.accounts?.id) { alert(t(lang, "googleNotLoaded")); return; }
    window.google.accounts.id.initialize({
      client_id: providers.google_client_id,
      callback: async (resp) => {
        try {
          const { data } = await api.post("/auth/google", { credential: resp.credential });
          onAuth(data);
        } catch (e) { setErr(e?.response?.data?.detail || "Google sign-in failed"); }
      },
    });
    window.google.accounts.id.prompt();
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
      <Logo />
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
    </div>
  );
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

  const SILENCE_MS = 2200;
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
function LexChat({ lang, country, category, title, onClose, autoMic = false, tier = "free" }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [deepThink, setDeepThink] = useState(false);
  const [dtUsed, setDtUsed] = useState(null); // {used, limit}
  const { recording, start, stop } = useRecorder();
  const audioRef = useRef(null);
  const scrollRef = useRef(null);
  const autoStartedRef = useRef(false);

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

  const send = async (text) => {
    if (!text.trim()) return;
    setMessages(m => [...m, { role: "user", content: text, at: new Date().toISOString() }]); setInput(""); setBusy(true);
    try {
      const autoDetect = localStorage.getItem("aa_autodetect") !== "0";
      const { data } = await api.post("/lex/chat", {
        message: text, session_id: sessionId, language: lang, country, category,
        deep_think: deepThink && isPro,
        auto_detect: autoDetect,
      });
      setSessionId(data.session_id);
      setMessages(m => [...m, { role: "lex", content: data.response, at: new Date().toISOString(), model: data.model, replyLang: data.reply_language }]);
      // Refresh Deep Think usage counter after each chat (Pro only)
      if (isPro && deepThink) {
        api.get("/subscription/usage").then(r => {
          const u = r.data?.usage?.deep_think;
          if (u) setDtUsed({ used: u.used, limit: u.limit });
        }).catch(() => {});
      }
      // ⏰ Limitation-period detector — fire-and-forget; if Lex finds a deadline, surface a one-tap "Add reminder" chip.
      const fd = new FormData();
      fd.append("message", text);
      fd.append("language", lang);
      fd.append("country", country);
      api.post("/reminders/detect", fd).then(r => {
        const dls = r.data?.deadlines || [];
        if (dls.length) {
          setMessages(m => [...m, { role: "deadlines", content: "", at: new Date().toISOString(), deadlines: dls }]);
        }
      }).catch(() => {});
      // TTS playback
      try {
        const r = await api.post("/voice/tts", { text: data.response.slice(0, 1500), voice: "onyx", language: data.reply_language }, { responseType: "blob" });
        const url = URL.createObjectURL(r.data);
        if (audioRef.current) { audioRef.current.src = url; audioRef.current.play().catch(() => {}); }
      } catch {}
    } catch (e) {
      setMessages(m => [...m, { role: "lex", content: e?.response?.data?.detail || "Error: try again" }]);
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
                  <div className={m.role === "user" ? "bubble-user" : "bubble-lex"}
                       data-testid={`msg-${m.role}-${i}`}
                       style={{ padding: "10px 14px", borderRadius: 14, maxWidth: "82%", whiteSpace: "pre-wrap", lineHeight: 1.5, fontSize: 14 }}>
                    {m.content}
                  </div>
                  {m.at && (
                    <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2, padding: "0 6px" }} data-testid={`ts-${i}`}>
                      {new Date(m.at).toLocaleString()}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
          {busy && <div className="bubble-lex" style={{ alignSelf: "flex-start", padding: "10px 14px", borderRadius: 14 }}><span className="spinner" /> Lex thinking…</div>}
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
  const audioRef = useRef(null);

  const fetchRights = useCallback(async (n) => {
    setBusy(true);
    try {
      const { data } = await api.post("/emergency/rights", { language: lang, country, note: n || undefined,
        location: coords ? `${coords.latitude.toFixed(4)},${coords.longitude.toFixed(4)}` : undefined });
      setRights(data.rights_script);
    } catch (e) { setRights(e?.response?.data?.detail || "Could not load rights. Stay silent. Ask for a lawyer."); }
    finally { setBusy(false); }
  }, [lang, country, coords]);

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
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
        () => {}, { timeout: 4000 }
      );
    }
    fetchRights("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Build SMS body with location + Google Maps link + a short alert
  const buildSms = () => {
    const lines = [
      `EMERGENCY: ${user?.full_name || user?.email || "I"} need help.`,
      "I've been stopped or arrested.",
    ];
    if (coords) {
      lines.push(`Location: https://maps.google.com/?q=${coords.latitude},${coords.longitude}`);
    }
    if (note) lines.push(`Note: ${note}`);
    lines.push("Sent from AI Advocate.");
    return lines.join(" ");
  };

  const sendSms = () => {
    const phone = (user?.emergency_contact_phone || "").trim();
    if (!phone) {
      alert(t(lang, "emergencyNoContact"));
      return;
    }
    const body = encodeURIComponent(buildSms());
    // iOS uses & before body; Android uses ?. Use ?body= which works on both.
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    const sep = isIOS ? "&" : "?";
    window.location.href = `sms:${phone}${sep}body=${body}`;
  };

  const callContact = () => {
    const phone = (user?.emergency_contact_phone || "").trim();
    if (!phone) {
      alert(t(lang, "emergencyNoContact"));
      return;
    }
    window.location.href = `tel:${phone}`;
  };

  const contactName = (user?.emergency_contact_name || t(lang, "yourContact")).trim();
  const hasContact = !!(user?.emergency_contact_phone || "").trim();

  return (
    <div className="modal-bg" data-testid="emergency-modal" style={{ background: "rgba(60,0,0,0.85)" }}>
      <div className="modal-card" style={{ padding: 18, maxHeight: "95vh", border: "2px solid #dc2626" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 10 }}>
          <h2 style={{ fontSize: 20, color: "#fca5a5", fontFamily: "Cinzel, serif", letterSpacing: "0.04em" }}>{t(lang, "emergencyTitle")}</h2>
          <button onClick={onClose} data-testid="emergency-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}>
            <X size={24} />
          </button>
        </div>

        {/* Contact actions row */}
        <div style={{ display: "grid", gridTemplateColumns: hasContact ? "1fr 1fr" : "1fr", gap: 8, marginBottom: 12 }}>
          <button data-testid="emergency-sms-btn" onClick={sendSms}
            style={{ padding: "11px 14px", background: hasContact ? "linear-gradient(135deg,#dc2626,#7f1d1d)" : "var(--bg-card)",
                     border: `1px solid ${hasContact ? "#fca5a5" : "var(--line)"}`,
                     color: hasContact ? "#fff" : "var(--text-muted)", borderRadius: 12, fontWeight: 700,
                     fontSize: 13, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
            📱 {hasContact ? t(lang, "emergencyTextContact", { name: contactName }) : t(lang, "emergencyAddContact")}
          </button>
          {hasContact && (
            <button data-testid="emergency-call-btn" onClick={callContact}
              style={{ padding: "11px 14px", background: "transparent", border: "1px solid var(--gold-deep)",
                       color: "var(--gold)", borderRadius: 12, fontWeight: 700, fontSize: 13, cursor: "pointer",
                       display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
              📞 {t(lang, "emergencyCallContact", { name: contactName })}
            </button>
          )}
        </div>

        <div style={{ fontSize: 12, color: "#fca5a5", marginBottom: 8 }}>{t(lang, "emergencyStayCalm", { country })}</div>
        <div data-testid="rights-script" style={{ overflowY: "auto", maxHeight: "40vh", padding: 14, background: "#0a0000",
                     borderRadius: 12, border: "1px solid #7f1d1d", fontSize: 14, color: "var(--text)",
                     lineHeight: 1.65, whiteSpace: "pre-wrap" }}>
          {busy ? <span className="spinner" /> : rights}
        </div>
        {/* Read aloud (TTS) — critical for distress moments where reading isn't possible */}
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
  const [consent, setConsent] = useState(false);
  const [scenario, setScenario] = useState("police_interview");
  const [liveActive, setLiveActive] = useState(false);
  const [lFacts, setLFacts] = useState("");
  const [advice, setAdvice] = useState([]); // {at, said, advice}
  const lRecRef = useRef(null);
  const lChunkBufRef = useRef("");
  const lSentRef = useRef(0);
  const lSessionRef = useRef(null);

  const startLive = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("This browser does not support live speech recognition. Use Chrome/Edge/Safari."); return; }
    const r = new SR();
    r.continuous = true; r.interimResults = true; r.lang = lang || "en-GB";
    r.onresult = async (ev) => {
      let finalText = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        if (ev.results[i].isFinal) finalText += ev.results[i][0].transcript + " ";
      }
      if (finalText.trim()) {
        lChunkBufRef.current += finalText;
        // dispatch every ~25 chars or after a final phrase
        const now = Date.now();
        if (lChunkBufRef.current.length > 25 && now - lSentRef.current > 3500) {
          const chunk = lChunkBufRef.current.trim();
          lChunkBufRef.current = "";
          lSentRef.current = now;
          try {
            const { data } = await api.post("/lex/live-assist", {
              session_id: lSessionRef.current, scenario,
              other_party_said: chunk, my_facts: lFacts, language: lang, country,
            });
            lSessionRef.current = data.session_id;
            setAdvice(a => [{ at: new Date().toLocaleTimeString(), said: chunk, advice: data.response }, ...a].slice(0, 30));
          } catch (e) { /* swallow */ }
        }
      }
    };
    r.onerror = () => {};
    r.onend = () => { if (liveActive) { try { r.start(); } catch {} } };
    try { r.start(); lRecRef.current = r; setLiveActive(true); } catch (e) { alert("Mic permission required."); }
  };
  const stopLive = () => {
    setLiveActive(false);
    try { lRecRef.current?.stop(); } catch {}
    lRecRef.current = null;
  };
  useEffect(() => () => { try { lRecRef.current?.stop(); } catch {} }, []);

  return (
    <div className="modal-bg" data-testid="courtroom-modal">
      <div className="modal-card" style={{ height: "92vh", padding: 0 }}>
        <div className="flex items-center justify-between" style={{ padding: 14, borderBottom: "1px solid var(--line)" }}>
          <h2 className="brand-font gold" style={{ fontSize: 18, letterSpacing: "0.04em" }}>{t(lang, "courtroomTrainer").toUpperCase()}</h2>
          <button onClick={onClose} data-testid="courtroom-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>
        <div style={{ display: "flex", padding: "10px 14px", gap: 6 }}>
          <button data-testid="tab-practice" onClick={() => setTab("practice")}
            style={{ flex: 1, padding: "8px 12px", borderRadius: 10, cursor: "pointer",
              background: tab === "practice" ? "var(--gold)" : "transparent",
              color: tab === "practice" ? "#1a1300" : "var(--gold)", border: "1px solid var(--gold-deep)", fontWeight: 600 }}>
            Practice Mode
          </button>
          <button data-testid="tab-live" onClick={() => setTab("live")}
            style={{ flex: 1, padding: "8px 12px", borderRadius: 10, cursor: "pointer",
              background: tab === "live" ? "var(--gold)" : "transparent",
              color: tab === "live" ? "#1a1300" : "var(--gold)", border: "1px solid var(--gold-deep)", fontWeight: 600 }}>
            Live Legal Assist
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
        ) : (
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
                <label className="flex items-start gap-2" style={{ cursor: "pointer" }}>
                  <input type="checkbox" data-testid="consent-checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
                    style={{ width: 18, height: 18, accentColor: "var(--gold)", marginTop: 3 }} />
                  <span style={{ fontSize: 12.5, color: "var(--text-dim)" }}>I confirm I have lawful permission to record this conversation, that I am NOT in an active courtroom, and I accept full responsibility for the legality of this use in my jurisdiction.</span>
                </label>
                <button className="btn-gold w-full" data-testid="consent-continue" disabled={!consent} onClick={() => setConsent(true)} style={{ marginTop: 14 }}>{t(lang, "consentContinue")}</button>
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
                {liveActive && <div style={{ textAlign: "center", color: "var(--gold)", fontSize: 12, marginTop: 6 }}>🎙 Listening — Lex will whisper advice as the other side speaks</div>}
                <div style={{ flex: 1, overflowY: "auto", marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                  {advice.length === 0 && liveActive && <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 20, fontSize: 13 }}>{t(lang, "waitingForOtherSide")}</div>}
                  {advice.map((a, i) => (
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
        )}
      </div>
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
      <div className="modal-card" style={{ padding: 18, maxHeight: "94vh" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
          <h2 className="brand-font gold" style={{ fontSize: 18 }}>{sel ? sel.title : "Letter Library"}</h2>
          <button onClick={onClose} data-testid="letter-lib-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
        </div>

        {!sel && (
          <>
            <input className="input" data-testid="letter-search" placeholder={t(lang, "searchTemplates")} value={search} onChange={(e) => setSearch(e.target.value)} style={{ marginBottom: 12 }} />
            <div style={{ overflowY: "auto", maxHeight: "70vh" }}>
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
          <div style={{ overflowY: "auto", maxHeight: "78vh" }}>
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
          <div style={{ overflowY: "auto", maxHeight: "78vh" }}>
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
      <div className="modal-card" style={{ padding: 20, maxHeight: "92vh" }}>
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
      <div className="modal-card" style={{ padding: 20, maxHeight: "92vh" }}>
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

// ---------- Record Legal Interaction ----------
function RecordModal({ lang, country, onClose }) {
  const { recording, start, stop } = useRecorder();
  const [busy, setBusy] = useState(false); const [result, setResult] = useState(null);

  const onMic = async () => {
    if (recording) {
      const blob = await stop(); if (!blob) return; setBusy(true);
      const fd = new FormData(); fd.append("audio", blob, "rec.webm"); fd.append("language", lang); fd.append("country", country);
      try { const { data } = await api.post("/record/analyze", fd); setResult(data); }
      catch (e) { alert(e?.response?.data?.detail || "Failed"); }
      finally { setBusy(false); }
    } else { start(); }
  };

  return (
    <div className="modal-bg" data-testid="record-modal">
      <div className="modal-card" style={{ padding: 20, maxHeight: "92vh" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "recordLegal")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={24} /></button>
        </div>
        {!result ? (
          <div style={{ textAlign: "center", padding: "30px 10px" }}>
            <p style={{ color: "var(--text-dim)", marginBottom: 20 }}>
              Record your interaction with police, court, or any legal authority. Lex will transcribe and analyse it.
            </p>
            <button onClick={onMic} disabled={busy} data-testid="record-mic-btn"
                    className={recording ? "lex-circle recording" : ""}
                    style={{ width: 100, height: 100, borderRadius: "50%", background: recording ? "var(--danger)" : "var(--bg-card)",
                             border: "2px solid var(--gold)", color: "var(--gold)", margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer" }}>
              {busy ? <span className="spinner" /> : (recording ? <Square size={36} /> : <Mic size={36} />)}
            </button>
            <p style={{ marginTop: 14, color: "var(--gold-soft)" }}>
              {busy ? t(lang, "analyzing") : (recording ? t(lang, "recording") : t(lang, "tapToRecord"))}
            </p>
          </div>
        ) : (
          <div style={{ overflowY: "auto" }}>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>{t(lang, "transcript")}</div>
            <div style={{ background: "#0a0a0a", padding: 12, borderRadius: 10, color: "var(--text-dim)", fontSize: 13.5, marginBottom: 14 }}>{result.transcript}</div>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>{t(lang, "lexAnalysis")}</div>
            <div style={{ background: "#0a0a0a", padding: 12, borderRadius: 10, color: "var(--text-dim)", fontSize: 13.5, whiteSpace: "pre-wrap" }}>{result.analysis}</div>
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <button className="btn-gold" data-testid="record-pdf-btn" onClick={() => pdfForFile(result.id, result.filename || "recording")} style={{ flex: 1 }}>
                <Download size={16} style={{ display: "inline", marginRight: 6 }} />Download PDF
              </button>
              <button className="btn-ghost" onClick={() => setResult(null)} style={{ flex: 1 }}>{t(lang, "recordAnother")}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- My Files ----------
function FilesModal({ lang, onClose }) {
  const [files, setFiles] = useState([]); const [open, setOpen] = useState(null);
  useEffect(() => { api.get("/legal-files").then(r => setFiles(r.data)).catch(() => {}); }, []);
  return (
    <div className="modal-bg" data-testid="files-modal">
      <div className="modal-card" style={{ padding: 20, maxHeight: "92vh" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "myFiles")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={24} /></button>
        </div>
        {!open ? (
          <div style={{ overflowY: "auto" }}>
            {files.length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 20 }}>{t(lang, "noFilesYet")}</p>}
            {files.map(f => (
              <button key={f.id} onClick={() => setOpen(f)} className="w-full" data-testid={`file-${f.id}`}
                      style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 14, marginBottom: 8, color: "var(--text)", textAlign: "left", cursor: "pointer" }}>
                <div style={{ color: "var(--gold)", fontWeight: 600 }}>{f.filename || f.type}</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{new Date(f.created_at).toLocaleString()}</div>
              </button>
            ))}
          </div>
        ) : (
          <div style={{ overflowY: "auto" }}>
            <button className="btn-ghost" onClick={() => setOpen(null)} style={{ marginBottom: 12, padding: "8px 14px" }}><ArrowLeft size={16} /> Back</button>
            <h3 style={{ color: "var(--gold)" }}>{open.filename}</h3>
            {open.transcript && <><div style={{ color: "var(--gold)", marginTop: 10 }}>Transcript</div><div style={{ background: "#0a0a0a", padding: 10, borderRadius: 8, color: "var(--text-dim)", fontSize: 13 }}>{open.transcript}</div></>}
            {(open.analysis || open.content) && <><div style={{ color: "var(--gold)", marginTop: 10 }}>Content</div><div style={{ background: "#0a0a0a", padding: 10, borderRadius: 8, whiteSpace: "pre-wrap", color: "var(--text-dim)", fontSize: 13 }}>{open.analysis || open.content}</div></>}
            <button className="btn-gold w-full" data-testid="file-pdf-btn" onClick={() => pdfForFile(open.id, open.filename || "ai_advocate")} style={{ marginTop: 14 }}>
              <Download size={16} style={{ display: "inline", marginRight: 6 }} />Download PDF
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Case Files (group chats / photos / videos / letters per case) ----------
function CaseFilesModal({ lang, onClose }) {
  const [cases, setCases] = useState([]);
  const [open, setOpen] = useState(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api.get("/cases").then(r => setCases(r.data.cases || [])).catch(() => {});
  useEffect(() => { load(); }, []);

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
    if (!window.confirm(t(lang, "deleteConfirm"))) return;
    await api.delete(`/cases/${open.id}`); setOpen(null); load();
  };

  const exportPdf = async () => {
    try {
      const r = await api.get(`/cases/${open.id}/export-pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `case-${open.id.slice(0,8)}.pdf`; a.click();
    } catch (e) { alert(e?.response?.data?.detail || t(lang, "failed")); }
  };

  return (
    <div className="modal-bg" data-testid="cases-modal">
      <div className="modal-card" style={{ padding: 20, maxHeight: "92vh" }}>
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
              <button className="btn-ghost" onClick={remove} data-testid="delete-case-btn" style={{ flex: 0.7, fontSize: 12, color: "#fca5a5" }}><Trash2 size={14} /></button>
            </div>
            {(open.items || []).length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 14, fontSize: 13 }}>{t(lang, "noFilesYet")}</p>}
            {(open.items || []).map(it => (
              <div key={it.id} data-testid={`case-item-${it.id}`} style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 10, padding: 12, marginBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span style={{ background: "var(--gold-deep)", color: "#1a1300", padding: "2px 7px", borderRadius: 8, fontSize: 10, fontWeight: 700, letterSpacing: "0.05em" }}>{it.item_type.toUpperCase()}</span>
                  <span style={{ color: "var(--gold)", fontSize: 13, fontWeight: 600 }}>{it.title}</span>
                </div>
                {it.preview && <div style={{ fontSize: 12, color: "var(--text-dim)", marginTop: 4, whiteSpace: "pre-wrap" }}>{it.preview}</div>}
                <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 6 }}>
                  {new Date(it.timestamp_utc || it.created_at).toLocaleString()}
                  {it.location && ` · 📍 ${it.location}`}
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
      <div className="modal-card" style={{ padding: 20, maxHeight: "92vh" }}>
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



// ---------- Snap Evidence (camera + upload) ----------
function SnapEvidenceModal({ lang, country, onClose }) {
  const [files, setFiles] = useState([]); // [{ file, preview }]
  const [evidenceType, setEvidenceType] = useState("auto");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState([]); // [{ filename, analysis, id }]
  const cameraRef = useRef(null);
  const libraryRef = useRef(null);

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
      <div className="modal-card" style={{ padding: 20, maxHeight: "94vh" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>{t(lang, "snapEvidence")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={24} /></button>
        </div>
        {results.length === 0 ? (
          <div style={{ overflowY: "auto", maxHeight: "80vh" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 14 }}>
              <button data-testid="evidence-camera-btn" onClick={() => cameraRef.current?.click()}
                style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 18, color: "var(--gold)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <Camera size={28} /><span style={{ fontSize: 12, color: "var(--text)" }}>{t(lang, "takePhoto")}</span>
              </button>
              <button data-testid="evidence-library-btn" onClick={() => libraryRef.current?.click()}
                style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 18, color: "var(--gold)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                <ImageIcon size={28} /><span style={{ fontSize: 12, color: "var(--text)" }}>{t(lang, "addMultiplePhotos")}</span>
              </button>
              <input ref={cameraRef} data-testid="evidence-camera-input" type="file" accept="image/*" capture="environment" onChange={onFile} style={{ display: "none" }} />
              <input ref={libraryRef} data-testid="evidence-library-input" type="file" accept="image/*,.pdf,.docx" multiple onChange={onFile} style={{ display: "none" }} />
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
        ) : (
          <div style={{ overflowY: "auto", maxHeight: "80vh" }}>
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
      <div className="modal-card" style={{ padding: 20, maxHeight: "94vh" }}>
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
      <div className="modal-card" style={{ padding: 20, maxHeight: "94vh" }}>
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
    <div className="modal-bg" data-testid="settings-modal">
      <div className="modal-card" style={{ padding: 22, maxHeight: "92vh", display: "flex", flexDirection: "column" }}>
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

        {/* Emergency Contact (used for "I've been arrested" SMS) */}
        <div data-testid="settings-emergency-contact" style={{ background: "var(--bg-card)", border: "1px solid #7f1d1d", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span style={{ color: "#fca5a5", fontSize: 18 }}>⚠</span>
            <span style={{ fontWeight: 600 }}>{t(lang, "emergencyContact")}</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 10, lineHeight: 1.5 }}>
            {t(lang, "emergencyContactDesc")}
          </div>
          {/* Native Contact Picker — works on Chrome Android & some iOS. Falls back to manual inputs below. */}
          {("contacts" in navigator) && ("ContactsManager" in window) && (
            <button data-testid="pick-contact-btn" className="btn-ghost" style={{ width: "100%", marginBottom: 10, padding: "10px", fontSize: 13 }}
              onClick={async () => {
                try {
                  const props = ["name", "tel"];
                  const opts = { multiple: false };
                  const result = await navigator.contacts.select(props, opts);
                  if (result && result.length) {
                    const c = result[0];
                    const name = (c.name && c.name[0]) || "";
                    const tel = (c.tel && c.tel[0]) ? c.tel[0].replace(/\s/g, "") : "";
                    try {
                      const r = await api.patch("/auth/preferences", { emergency_contact_name: name, emergency_contact_phone: tel });
                      onUpdate(r.data);
                    } catch (e) { alert(e?.response?.data?.detail || t(lang, "failedToSave")); }
                  }
                } catch (e) {
                  alert(t(lang, "contactPickerUnavailable"));
                }
              }}>
              📇 {t(lang, "pickFromContacts")}
            </button>
          )}
          <input className="input" data-testid="emergency-name-input" placeholder={t(lang, "emergencyNamePlaceholder")}
            defaultValue={user.emergency_contact_name || ""} key={`ename-${user.emergency_contact_name || ""}`}
            onBlur={async (e) => { await api.patch("/auth/preferences", { emergency_contact_name: e.target.value }).then(r => onUpdate(r.data)).catch(() => {}); }}
            style={{ marginBottom: 8 }} />
          <input className="input" data-testid="emergency-phone-input" placeholder={t(lang, "emergencyPhonePlaceholder")}
            type="tel" defaultValue={user.emergency_contact_phone || ""} key={`ephone-${user.emergency_contact_phone || ""}`}
            onBlur={async (e) => { await api.patch("/auth/preferences", { emergency_contact_phone: e.target.value.replace(/\s/g, "") }).then(r => onUpdate(r.data)).catch(() => {}); }} />
        </div>

        {/* "Hey Lex" wake word toggle */}
        <div data-testid="settings-heylex" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Mic size={18} style={{ color: "var(--gold)" }} />
              <span style={{ fontWeight: 600 }}>{t(lang, "heyLexWake")}</span>
            </div>
            <label style={{ position: "relative", display: "inline-block", width: 48, height: 26, cursor: "pointer" }}>
              <input type="checkbox" data-testid="heylex-toggle" defaultChecked={localStorage.getItem("aa_wake") !== "0"}
                onChange={async (e) => {
                  const v = e.target.checked;
                  localStorage.setItem("aa_wake", v ? "1" : "0");
                  if (v) {
                    // Request mic permission so the wake-word recognizer can actually start
                    try {
                      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                      stream.getTracks().forEach(tr => tr.stop());
                    } catch (err) {
                      alert(t(lang, "micPermDenied"));
                      localStorage.setItem("aa_wake", "0");
                      e.target.checked = false;
                      return;
                    }
                  }
                  window.dispatchEvent(new CustomEvent("aa:wake-toggle", { detail: { enabled: v } }));
                }}
                style={{ opacity: 0, width: 0, height: 0 }} />
              <span style={{ position: "absolute", inset: 0, background: localStorage.getItem("aa_wake") !== "0" ? "var(--gold)" : "var(--line)",
                             borderRadius: 13, transition: "0.2s",
                             }}>
                <span style={{ position: "absolute", height: 20, width: 20, left: localStorage.getItem("aa_wake") !== "0" ? 25 : 3, top: 3,
                               background: "#000", borderRadius: "50%", transition: "0.2s" }} />
              </span>
            </label>
          </div>
          <div style={{ fontSize: 11.5, color: "var(--text-muted)", lineHeight: 1.5 }}>
            {t(lang, "heyLexDesc")}
            <br/><strong style={{ color: "var(--gold-soft)" }}>{t(lang, "heyLexIosNote")}</strong>
          </div>
        </div>

        {/* Auto-detect language toggle */}
        <div data-testid="settings-autodetect" style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 14, padding: 16, marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Languages size={18} style={{ color: "var(--gold)" }} />
              <span style={{ fontWeight: 600 }}>{t(lang, "autoDetectLang")}</span>
            </div>
            <label style={{ position: "relative", display: "inline-block", width: 48, height: 26, cursor: "pointer" }}>
              <input type="checkbox" data-testid="autodetect-toggle" defaultChecked={localStorage.getItem("aa_autodetect") !== "0"}
                onChange={(e) => { localStorage.setItem("aa_autodetect", e.target.checked ? "1" : "0"); }}
                style={{ opacity: 0, width: 0, height: 0 }} />
              <span style={{ position: "absolute", inset: 0, background: localStorage.getItem("aa_autodetect") !== "0" ? "var(--gold)" : "var(--line)",
                             borderRadius: 13, transition: "0.2s" }}>
                <span style={{ position: "absolute", height: 20, width: 20, left: localStorage.getItem("aa_autodetect") !== "0" ? 25 : 3, top: 3,
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
              <input type="checkbox" data-testid="locstamp-toggle" defaultChecked={localStorage.getItem("aa_locstamp") === "1"}
                onChange={(e) => { localStorage.setItem("aa_locstamp", e.target.checked ? "1" : "0"); }}
                style={{ opacity: 0, width: 0, height: 0 }} />
              <span style={{ position: "absolute", inset: 0, background: localStorage.getItem("aa_locstamp") === "1" ? "var(--gold)" : "var(--line)",
                             borderRadius: 13, transition: "0.2s" }}>
                <span style={{ position: "absolute", height: 20, width: 20, left: localStorage.getItem("aa_locstamp") === "1" ? 25 : 3, top: 3,
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
        </div>
      </div>
    </div>
  );
}


// ---------- Subscribe Modal ----------
function SubscribeModal({ lang, user, onClose, onActivated, presetPlan }) {
  const [busy, setBusy] = useState(false);
  const [tiers, setTiers] = useState([]);
  const [picked, setPicked] = useState(presetPlan || "plus");

  useEffect(() => { api.get("/subscription/tiers").then(r => setTiers(r.data.tiers)).catch(() => {}); }, []);

  const checkout = async (plan) => {
    setBusy(true);
    try {
      const { data } = await api.post("/subscription/checkout", { plan });
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
      </div>
    </div>
  );
}

// ---------- Bottom Navigation ----------
function BottomNav({ lang, active = "home", onNav, hasAccess, requireSub }) {
  const items = [
    { k: "home", Icon: HomeIcon, lbl: t(lang, "home") },
    { k: "files", Icon: Folder, lbl: t(lang, "files") },
    { k: "lex", center: true },
    { k: "lawyers", Icon: Building2, lbl: t(lang, "lawyers") },
    { k: "settings", Icon: SettingsIcon, lbl: t(lang, "settings") },
  ];
  const handle = (k) => {
    if (k === "home") return; // already home
    if (k === "lex" && !hasAccess) { requireSub(); return; }
    onNav(k);
  };
  return (
    <nav data-testid="bottom-nav" style={{
      position: "fixed", bottom: 0, left: 0, right: 0,
      display: "flex", justifyContent: "space-around", alignItems: "center",
      background: "rgba(8,8,8,0.92)", backdropFilter: "blur(12px)",
      borderTop: "1px solid var(--line)",
      padding: "8px 8px 14px", zIndex: 50,
    }}>
      {items.map(it => it.center ? (
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
          <div style={{ fontSize: 10, color: "var(--gold)", fontWeight: 600, marginTop: 2, fontFamily: "Cinzel, serif", letterSpacing: "0.05em" }}>LEX</div>
        </div>
      ) : (
        <button key={it.k} data-testid={`nav-${it.k}`} onClick={() => handle(it.k)}
                style={{ background: "transparent", border: "none", display: "flex", flexDirection: "column", alignItems: "center", gap: 3, flex: 1, cursor: "pointer", padding: 4 }}>
          <it.Icon size={20} style={{ color: active === it.k ? "var(--gold)" : "var(--text-muted)" }} />
          <span style={{ fontSize: 10, color: active === it.k ? "var(--gold)" : "var(--text-muted)" }}>{it.lbl}</span>
        </button>
      ))}
    </nav>
  );
}

// ---------- Dashboard ----------
function Dashboard({ user, lang, country, setLang, setCountry, onLogout, refreshUser }) {
  const [modal, setModal] = useState(null); // {type, title, category}
  const [showLang, setShowLang] = useState(false);
  const [showSub, setShowSub] = useState(false);
  const [subPreset, setSubPreset] = useState("plus");
  const [showSettings, setShowSettings] = useState(false);
  const [showAdvertise, setShowAdvertise] = useState(false);
  const [showEmergency, setShowEmergency] = useState(false);
  const [wakeOn, setWakeOn] = useState(() => localStorage.getItem("aa_wake") !== "0");

  const tier = user.tier || "free";
  const TIER_RANK = { free: 0, plus: 1, pro: 2, yearly: 2, trial_pro: 2 };
  const hasTier = useCallback((req) => TIER_RANK[tier] >= TIER_RANK[req], [tier]);

  // Allow other components (Settings) to open the Subscribe modal with a preset plan
  useEffect(() => {
    const handler = (e) => { setSubPreset(e?.detail?.preset || "pro"); setShowSub(true); };
    window.addEventListener("aa:open-subscribe", handler);
    const wakeHandler = (e) => setWakeOn(!!e?.detail?.enabled);
    window.addEventListener("aa:wake-toggle", wakeHandler);
    return () => {
      window.removeEventListener("aa:open-subscribe", handler);
      window.removeEventListener("aa:wake-toggle", wakeHandler);
    };
  }, []);

  const [voiceMode, setVoiceMode] = useState(null); // {initialText} | null
  const [reviewPrompt, setReviewPrompt] = useState(null); // {daysLeft}

  // Trustpilot pre-renewal nudge — once per session, only if backend says it's the right window
  useEffect(() => {
    if (sessionStorage.getItem("aa_review_checked")) return;
    sessionStorage.setItem("aa_review_checked", "1");
    api.get("/review/should-prompt").then(r => {
      if (r.data?.should_prompt) setReviewPrompt({ daysLeft: r.data.days_left });
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
    { id: "record", label: t(lang, "recordLegal"), Icon: RecordIcon, cat: "record", req: "plus" },
    { id: "snap", label: t(lang, "snapEvidence"), Icon: CameraIcon, req: "free" },
    { id: "lawyers", label: t(lang, "findLawyer"), Icon: LawyerIcon, req: "free" },
    { id: "files", label: t(lang, "myFiles"), Icon: FilesIcon, req: "free" },
    { id: "cases", label: t(lang, "caseFiles"), Icon: FilesIcon, req: "free" },
    { id: "reminders", label: t(lang, "reminders"), Icon: FilesIcon, req: "free" },
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
    else if (tile.id === "letter") setModal({ type: "letter_lib" });
    else if (tile.id === "record") setModal({ type: "record" });
    else if (tile.id === "snap") setModal({ type: "snap" });
    else if (tile.id === "lawyers") setModal({ type: "lawyers" });
    else if (tile.id === "courtroom") setModal({ type: "courtroom" });
    else if (tile.id === "ask_lex") setModal({ type: "chat", title: t(lang, "askLex"), category: tile.cat });
    else setModal({ type: "chat", title: tile.label, category: tile.cat });
  };

  const langInfo = LANGS.find(l => l.code === lang) || LANGS[0];

  return (
    <div className="app-shell" style={{ padding: "20px 18px 130px", maxWidth: 760, margin: "0 auto" }} data-testid="dashboard">
      <div className="flex items-center justify-between" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{t(lang, "hi")}, <span style={{ color: "var(--gold)" }}>{user.full_name || user.email.split("@")[0]}</span></div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowSettings(true)} data-testid="settings-btn" title={t(lang, "settings")}
                  style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--gold)", borderRadius: "50%", width: 34, height: 34, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <SettingsIcon size={16} />
          </button>
          <button onClick={() => setShowLang(true)} data-testid="lang-toggle-btn"
                  style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--gold)", borderRadius: 20, padding: "5px 12px", fontSize: 13, cursor: "pointer" }}>
            {langInfo.flag} {langInfo.code.split("-")[0].toUpperCase()}
          </button>
          <button onClick={onLogout} data-testid="logout-btn" title={t(lang, "logout")}
                  style={{ background: "transparent", border: "1px solid var(--line)", color: "var(--text-dim)", borderRadius: "50%", width: 34, height: 34, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <LogOut size={16} />
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginTop: 6, marginBottom: 14 }}>
        <Logo />
      </div>

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

      <BottomNav lang={lang} active="home"
        onNav={(k) => {
          if (k === "lex") {
            // Tapping Lex centre button → open Siri-style Voice Mode (Plus+ only)
            if (!hasTier("plus")) { setSubPreset("plus"); setShowSub(true); return; }
            setVoiceMode({ initialText: "" });
          }
          else if (k === "files") setModal({ type: "files" });
          else if (k === "lawyers") setModal({ type: "lawyers" });
          else if (k === "settings") setShowSettings(true);
        }} hasAccess={true} requireSub={() => setShowSub(true)} />

      {modal?.type === "chat" && <LexChat lang={lang} country={country} category={modal.category} title={modal.title} autoMic={!!modal.autoMic} tier={tier} onClose={() => setModal(null)} />}
      {modal?.type === "courtroom" && <CourtroomModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "letter_lib" && <LetterLibraryModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "files" && <FilesModal lang={lang} onClose={() => setModal(null)} />}
      {modal?.type === "cases" && <CaseFilesModal lang={lang} onClose={() => setModal(null)} />}
      {modal?.type === "reminders" && <RemindersModal lang={lang} onClose={() => setModal(null)} />}
      {modal?.type === "letter" && <LegalLetterModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "record" && <RecordModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "snap" && <SnapEvidenceModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "lawyers" && <LawyersModal lang={lang} country={country} user={user} onClose={() => setModal(null)} openAdvertise={() => { setModal(null); setShowAdvertise(true); }} />}
      {showEmergency && <EmergencyModal lang={lang} country={country} user={user} onClose={() => setShowEmergency(false)} />}
      {voiceMode && <VoiceModeOverlay lang={lang} country={country} category="ask_lex" initialText={voiceMode.initialText} onClose={() => setVoiceMode(null)} />}
      {showLang && <LanguagePicker initial={lang} lang={lang} onConfirm={(l) => { setLang(l); setShowLang(false); api.patch("/auth/preferences", { language: l }).catch(() => {}); }} />}
      {showSub && <SubscribeModal lang={lang} user={user} presetPlan={subPreset} onClose={() => setShowSub(false)} onActivated={(u) => { refreshUser(u); setShowSub(false); }} />}
      {showSettings && <SettingsModal lang={lang} country={country} user={user} onClose={() => setShowSettings(false)} onUpdate={(u) => refreshUser(u)} setLang={setLang} setCountry={setCountry} />}
      {showAdvertise && <AdvertiseModal lang={lang} onClose={() => setShowAdvertise(false)} />}
      {reviewPrompt && <ReviewPrompt lang={lang} daysLeft={reviewPrompt.daysLeft} onClose={() => setReviewPrompt(null)} />}
    </div>
  );
}

// ---------- Root App ----------
function App() {
  const [lang, setLang] = useState(localStorage.getItem("aa_lang") || "en-GB");
  const [country, setCountry] = useState(localStorage.getItem("aa_country") || "GB");
  const [step, setStep] = useState("loading"); // loading | lang | terms | auth | app
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("aa_token"));

  useEffect(() => { localStorage.setItem("aa_lang", lang); document.documentElement.dir = RTL_LANGS.includes(lang) ? "rtl" : "ltr"; }, [lang]);
  useEffect(() => { localStorage.setItem("aa_country", country); }, [country]);

  // Bootstrap
  useEffect(() => {
    if (token) {
      setAuthHeader(token);
      api.get("/auth/me").then(r => { setUser(r.data); setLang(r.data.language || lang); setCountry(r.data.country || country); setStep("app"); })
        .catch(() => { localStorage.removeItem("aa_token"); setToken(null); setStep(localStorage.getItem("aa_terms") ? "auth" : "lang"); });
    } else {
      setStep(localStorage.getItem("aa_terms") ? "auth" : "lang");
    }
  // eslint-disable-next-line
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
    setUser(data.user); setStep("app");
  };
  const onLogout = () => { localStorage.removeItem("aa_token"); setToken(null); setUser(null); setAuthHeader(null); setStep("auth"); };

  if (step === "loading") return <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}><span className="spinner" /></div>;

  return (
    <div className="App app-shell">
      {step === "lang" && <LanguagePicker lang={lang} initial={lang} onConfirm={(l) => { setLang(l); setStep("terms"); }} />}
      {step === "terms" && <TermsScreen lang={lang} onAccept={() => { localStorage.setItem("aa_terms", "1"); setStep("auth"); }} onDecline={() => setStep("lang")} onChangeLang={() => setStep("lang")} />}
      {step === "auth" && <AuthScreen lang={lang} country={country} onAuth={onAuth} />}
      {step === "app" && user && <Dashboard user={user} lang={lang} country={country} setLang={setLang} setCountry={setCountry} onLogout={onLogout} refreshUser={(u) => setUser(u)} />}
    </div>
  );
}

export default App;
