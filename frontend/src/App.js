import React, { useState, useEffect, useRef, useCallback } from "react";
import "@/App.css";
import axios from "axios";
import {
  MessageCircle, Mic, Folder, FileText, Gavel, Globe, Briefcase, Home as HomeIcon,
  Stethoscope, Scale, X, Send, Upload, Languages, LogOut, Check, ArrowLeft, Square, Play,
  Camera, MapPin, Phone, ExternalLink, Settings as SettingsIcon, Star, Building2, Image as ImageIcon,
  Download
} from "lucide-react";
import { STRINGS, t, RTL_LANGS } from "@/i18n";
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
  return (
    <div className="modal-bg" data-testid="terms-modal">
      <div className="modal-card" style={{ padding: 22 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 12 }}>
          <h2 className="brand-font gold" style={{ fontSize: 22 }}>{t(lang, "termsTitle")}</h2>
          <button className="btn-gold" data-testid="terms-lang-btn" onClick={onChangeLang}
                  style={{ padding: "6px 14px", fontSize: 13 }}>
            <Languages size={14} style={{ display: "inline", marginRight: 6 }} />{t(lang, "lang")}
          </button>
        </div>
        <p style={{ color: "var(--text-dim)", fontSize: 13 }}>
          Effective date: {new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}.
          You must read and accept these Terms and the Privacy Policy below to use AI Advocate.
        </p>
        <div data-testid="terms-body" style={{ overflowY: "auto", maxHeight: "48vh", padding: 14, background: "#0a0a0a", borderRadius: 12, border: "1px solid var(--line)", marginTop: 10, fontSize: 12.5, color: "var(--text-dim)", lineHeight: 1.65 }}>
          <p style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>TERMS OF SERVICE</p>

          <p><strong>1. About AI Advocate.</strong> AI Advocate ("the App", "we", "us", "our") is a software product operated by the AI Advocate team. We provide an AI-powered legal-information assistant called "Lex", document tooling, photo/contract analysis, formal-letter generation, and a directory of independent law firms. We are <strong>NOT a law firm</strong>, we are <strong>NOT solicitors, barristers, attorneys, or any other regulated legal professionals</strong>, and we do <strong>NOT</strong> provide legal services, legal advice, or legal representation.</p>

          <p><strong>2. No Legal Advice — Information Only.</strong> All content generated by Lex or any other feature of the App is <strong>general legal information only</strong>. It is generated by artificial intelligence and is not legal advice. It cannot and does not replace the advice of a qualified, regulated lawyer in your own jurisdiction who has reviewed the specific facts of your case. You must consult a qualified lawyer before taking any action that has legal consequences. Reliance on Lex alone is at your sole risk.</p>

          <p><strong>3. No Attorney/Solicitor–Client Relationship.</strong> Using the App, communicating with Lex, uploading documents, or paying for a subscription does <strong>not</strong> create an attorney-client, solicitor-client, advocate-client, or any other professional or fiduciary relationship between you and AI Advocate or any of its operators, employees, agents, or contractors. Communications you send through the App are <strong>not</strong> protected by legal professional privilege, attorney-client privilege, or any equivalent doctrine.</p>

          <p><strong>4. AI Accuracy &amp; Hallucination Disclaimer.</strong> Large Language Models (including those that power Lex) can produce inaccurate, outdated, incomplete, or fabricated information ("hallucinations"), including invented case citations and statute references. We make no representation or warranty that any output is accurate, current, complete, applicable to your jurisdiction, or fit for any purpose. <strong>You must independently verify every legal proposition with a qualified lawyer before relying on it.</strong></p>

          <p><strong>5. Eligibility.</strong> You must be at least 18 years old (or the age of legal majority in your jurisdiction, whichever is higher) and legally capable of entering into a binding contract. You confirm you are not subject to any sanctions list or prohibited from using the App under applicable law.</p>

          <p><strong>6. Subscription, Free Trial, Auto-Renewal &amp; Refunds.</strong> The App offers a 14-day free trial followed by an auto-renewing monthly or annual subscription. By subscribing through Apple App Store, Google Play, or our web payment processor (Stripe), you authorise recurring charges to your selected payment method until you cancel. Cancel any time at least 24 hours before the next renewal in your App Store / Google Play / Stripe settings. Refunds are governed by the rules of the store/processor that processed your payment; we do not issue refunds directly except where required by law (e.g. UK Consumer Contracts Regulations 14-day cooling-off for non-digital subscriptions, where applicable).</p>

          <p><strong>7. Acceptable Use.</strong> You agree not to (a) use the App for any unlawful purpose; (b) submit content that is illegal, defamatory, infringing, or contains malware; (c) attempt to reverse-engineer, scrape, or circumvent technical protections; (d) use the App to draft or send threats, harassment, fraud, or content designed to evade the law; (e) impersonate a lawyer or hold yourself out as receiving legal advice from the App; (f) input third-party personal data without lawful basis. We may suspend or terminate accounts that violate these rules without refund.</p>

          <p><strong>8. Your Content &amp; Licence.</strong> You retain ownership of documents, photos, recordings, and messages you upload ("Your Content"). You grant us a worldwide, non-exclusive, royalty-free licence to host, process, transmit, display, and analyse Your Content solely to provide the App's features to you, to comply with law, and (in anonymised, aggregated form only) to improve the service. You represent that you have all rights necessary to grant this licence.</p>

          <p><strong>9. Privacy &amp; Data Protection.</strong> Our Privacy Policy below is incorporated into these Terms. We process personal data in accordance with the UK GDPR, the EU GDPR, the California Consumer Privacy Act (CCPA/CPRA) where applicable, and other applicable privacy laws.</p>

          <p><strong>10. Intellectual Property.</strong> The App, the "AI Advocate" and "Lex" names, logos, the Lex avatar, the visual design, source code, and all underlying technology are owned by AI Advocate and protected by copyright, trade-mark, and other intellectual-property laws. You receive a limited, revocable, non-transferable licence to use the App for personal, non-commercial purposes only.</p>

          <p><strong>11. Third-Party Services.</strong> The App integrates with third-party services including Anthropic (Claude), Google (Gemini), OpenAI (Whisper/TTS), Stripe, Apple Sign-In, Google Sign-In, and law-firm directories. Use of those services may be subject to their own terms; we are not responsible for outages, errors, or data practices of third-party providers.</p>

          <p><strong>12. LIMITATION OF LIABILITY.</strong> <strong>TO THE MAXIMUM EXTENT PERMITTED BY LAW, AI ADVOCATE, ITS OPERATORS, OFFICERS, DIRECTORS, EMPLOYEES, AGENTS, LICENSORS, AND SUPPLIERS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, REVENUE, DATA, GOODWILL, BUSINESS, LIBERTY, FAVOURABLE LEGAL OUTCOME, OR OPPORTUNITY, WHETHER ARISING IN CONTRACT, TORT (INCLUDING NEGLIGENCE), STATUTE, OR OTHERWISE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. OUR TOTAL CUMULATIVE LIABILITY TO YOU FOR ALL CLAIMS RELATING TO THE APP SHALL NOT EXCEED THE GREATER OF (A) THE AMOUNT YOU ACTUALLY PAID US IN THE THREE (3) MONTHS IMMEDIATELY PRECEDING THE EVENT GIVING RISE TO LIABILITY, OR (B) £50 / US$50.</strong> Nothing in these Terms excludes liability for death or personal injury caused by our negligence, fraud, or any other liability that cannot lawfully be excluded.</p>

          <p><strong>13. NO WARRANTY.</strong> THE APP IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTY OF ANY KIND, WHETHER EXPRESS, IMPLIED, OR STATUTORY, INCLUDING WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, ACCURACY, AVAILABILITY, NON-INFRINGEMENT, AND ANY WARRANTY ARISING FROM COURSE OF DEALING OR USAGE OF TRADE.</p>

          <p><strong>14. Indemnification.</strong> You agree to defend, indemnify, and hold harmless AI Advocate from and against any and all claims, liabilities, damages, losses, costs, and expenses (including reasonable legal fees) arising out of or related to (a) your use of the App; (b) Your Content; (c) your violation of these Terms; or (d) any decision or action you take based on output produced by the App.</p>

          <p><strong>15. Governing Law &amp; Jurisdiction.</strong> These Terms are governed by the laws of <strong>England &amp; Wales</strong>, without regard to conflict-of-law rules. Subject to clause 16, the courts of England &amp; Wales have exclusive jurisdiction over any dispute that is not subject to arbitration.</p>

          <p><strong>16. Mandatory Arbitration &amp; Class-Action Waiver.</strong> Any dispute, claim, or controversy arising out of or relating to these Terms or the App shall be finally resolved by binding arbitration administered by the International Chamber of Commerce (ICC) under its Rules of Arbitration. The seat shall be London, England. The arbitration shall be conducted in English by a single arbitrator. <strong>YOU AND AI ADVOCATE EACH WAIVE THE RIGHT TO A JURY TRIAL AND THE RIGHT TO BRING OR PARTICIPATE IN ANY CLASS, COLLECTIVE, OR REPRESENTATIVE ACTION.</strong> Awards may be enforced in any court of competent jurisdiction under the 1958 New York Convention. This clause does not prevent either party from seeking interim or injunctive relief in any competent court.</p>

          <p><strong>17. EU / UK Consumer Rights.</strong> If you are a consumer resident in the EU, UK, or another jurisdiction whose mandatory consumer-protection laws cannot be waived, nothing in these Terms limits any rights you have under those laws. EU/UK consumers may also use the European Commission's online dispute resolution platform.</p>

          <p><strong>18. California Residents (CCPA/CPRA Notice).</strong> California residents have specific privacy rights including the right to know, delete, correct, and opt out of "sale" or "sharing" of personal information. To exercise these rights, email <em>privacy@aiadvocate.app</em>. We do not sell personal information for monetary consideration.</p>

          <p><strong>19. Changes to These Terms.</strong> We may update these Terms from time to time. Material changes will be notified in-app or by email at least 14 days before they take effect. Continued use of the App after the effective date constitutes acceptance.</p>

          <p><strong>20. Termination.</strong> You may stop using the App at any time and delete your account from Settings. We may suspend or terminate access if you breach these Terms, if required by law, or if continued provision is no longer commercially viable. Sections 2-4, 8-18, and 20 survive termination.</p>

          <p><strong>21. Severability &amp; Entire Agreement.</strong> If any provision of these Terms is held unenforceable, the remainder will continue in force. These Terms (together with the Privacy Policy) are the entire agreement between you and AI Advocate concerning the App and supersede all prior communications.</p>

          <p><strong>22. Contact.</strong> Questions: <em>legal@aiadvocate.app</em>.</p>

          <p style={{ color: "var(--gold)", fontWeight: 600, marginTop: 14, marginBottom: 6 }}>PRIVACY POLICY (SUMMARY)</p>

          <p><strong>A. Data We Collect.</strong> (i) Account data: name, email, hashed password, language and country preference, Apple/Google sub-IDs if you use social sign-in. (ii) Content data: chats with Lex, uploaded documents/photos/recordings, generated letters and analyses. (iii) Usage data: device info, IP address, app interactions, crash logs. (iv) Location data (only if you grant permission): coarse latitude/longitude used to find nearby law firms. (v) Payment data is processed directly by Apple, Google Play, or Stripe — we never see your full card number.</p>

          <p><strong>B. Lawful Basis (UK/EU GDPR).</strong> We process your data on the basis of contract performance (to provide the App), legitimate interests (to improve and secure the App), legal obligation (to comply with law), and consent (for optional features like location and marketing emails). You can withdraw consent at any time.</p>

          <p><strong>C. Purposes.</strong> We use your data to provide and operate the App, generate AI responses, store your chat history and files, find lawyers near you, process payments, send essential service emails, detect fraud and abuse, and comply with legal obligations.</p>

          <p><strong>D. Third-Party Processors.</strong> Your content may be transmitted to: Anthropic (Claude), Google (Gemini), OpenAI (Whisper / TTS), Stripe, MongoDB Atlas, our cloud hosting provider, Apple, and Google. Each acts as a processor under contractual data-protection terms. Data may be transferred outside the UK/EEA under Standard Contractual Clauses or equivalent safeguards.</p>

          <p><strong>E. Retention.</strong> Account &amp; chat data: retained while your account is active and for up to 24 months after deletion request (for legal/audit purposes), then permanently erased. Anonymised aggregate data may be kept indefinitely.</p>

          <p><strong>F. Your Rights.</strong> Under UK/EU GDPR you have the right to access, rectify, erase, restrict, port, and object to processing of your personal data, and to lodge a complaint with the UK ICO (ico.org.uk) or your local data-protection authority. Email <em>privacy@aiadvocate.app</em> to exercise these rights — we will respond within 30 days.</p>

          <p><strong>G. Security.</strong> We use industry-standard encryption (TLS in transit, encrypted-at-rest databases), hashed passwords (bcrypt), and access controls. No system is 100% secure; you use the App at your own risk.</p>

          <p><strong>H. Children.</strong> The App is not directed to children under 18. We do not knowingly collect data from anyone under 18.</p>

          <p><strong>I. Cookies / Local Storage.</strong> We use essential local storage for authentication tokens, language preference, and trial state. We do not use third-party advertising cookies.</p>

          <p><strong>J. International Users.</strong> By using the App you consent to the transfer and processing of your data in the United Kingdom, the European Union, and the United States, where our service providers are located.</p>

          <p style={{ marginTop: 14, color: "var(--gold-soft)" }}><em>By tapping "Accept &amp; Continue" below, you confirm you have read, understood, and agreed to these Terms and Privacy Policy in full, and you accept that AI Advocate is an information tool, not a substitute for a qualified lawyer.</em></p>
        </div>
        <label className="flex items-center gap-2" style={{ marginTop: 14, cursor: "pointer" }}>
          <input type="checkbox" data-testid="agree-checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)}
                 style={{ width: 18, height: 18, accentColor: "var(--gold)" }} />
          <span style={{ fontSize: 14 }}>{t(lang, "iAgree")}</span>
        </label>
        <div className="flex gap-2" style={{ marginTop: 14 }}>
          <button className="btn-gold" data-testid="accept-terms-btn" disabled={!agree} style={{ flex: 2 }} onClick={onAccept}>{t(lang, "accept")}</button>
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
    if (!window.google?.accounts?.id) { alert("Google not loaded"); return; }
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
    if (!window.AppleID?.auth) { alert("Apple not loaded — refresh the page"); return; }
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
    } catch (e) { alert("Microphone access denied"); }
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
        // Match common variants across languages (rough but effective)
        if (/(^|\s)(hey|hi|okay|ok|hola|salam|你好|bonjour|hallo|ciao|olá|namaste)[ ,.]*(lex|leks|lekss|лекс)\b/.test(transcript)) {
          try { rec.stop(); } catch {}
          onWake();
          return;
        }
      }
    };
    rec.onend = () => {
      // auto-restart unless user disabled it
      if (!stoppedRef.current) {
        try { rec.start(); } catch {}
      }
    };
    rec.onerror = (e) => {
      // Permission denied, network etc. — silently back off; user can retry by toggling.
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

// ---------- Lex Chat ----------
function LexChat({ lang, country, category, title, onClose, autoMic = false }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const { recording, start, stop } = useRecorder();
  const audioRef = useRef(null);
  const scrollRef = useRef(null);
  const autoStartedRef = useRef(false);

  useEffect(() => { scrollRef.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [messages, busy]);

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
    setMessages(m => [...m, { role: "user", content: text }]); setInput(""); setBusy(true);
    try {
      const { data } = await api.post("/lex/chat", { message: text, session_id: sessionId, language: lang, country, category });
      setSessionId(data.session_id);
      setMessages(m => [...m, { role: "lex", content: data.response }]);
      // TTS playback
      try {
        const r = await api.post("/voice/tts", { text: data.response.slice(0, 1500), voice: "onyx" }, { responseType: "blob" });
        const url = URL.createObjectURL(r.data);
        if (audioRef.current) { audioRef.current.src = url; audioRef.current.play().catch(() => {}); }
      } catch {}
    } catch (e) {
      setMessages(m => [...m, { role: "lex", content: e?.response?.data?.detail || "Error: try again" }]);
    } finally { setBusy(false); }
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
          <button onClick={onClose} data-testid="lex-close-btn" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}>
            <X size={24} />
          </button>
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
            <div key={i} className={m.role === "user" ? "bubble-user" : "bubble-lex"}
                 data-testid={`msg-${m.role}-${i}`}
                 style={{ alignSelf: m.role === "user" ? "flex-end" : "flex-start", padding: "10px 14px", borderRadius: 14, maxWidth: "82%", whiteSpace: "pre-wrap", lineHeight: 1.5, fontSize: 14 }}>
              {m.content}
            </div>
          ))}
          {busy && <div className="bubble-lex" style={{ alignSelf: "flex-start", padding: "10px 14px", borderRadius: 14 }}><span className="spinner" /> Lex thinking…</div>}
        </div>

        <div className="flex items-center gap-2" style={{ padding: 12, borderTop: "1px solid var(--line)" }}>
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
function EmergencyModal({ lang, country, onClose }) {
  const [rights, setRights] = useState("");
  const [busy, setBusy] = useState(true);
  const [note, setNote] = useState("");
  const [coords, setCoords] = useState(null);

  const fetchRights = useCallback(async (n) => {
    setBusy(true);
    try {
      const { data } = await api.post("/emergency/rights", { language: lang, country, note: n || undefined,
        location: coords ? `${coords.latitude.toFixed(4)},${coords.longitude.toFixed(4)}` : undefined });
      setRights(data.rights_script);
    } catch (e) { setRights(e?.response?.data?.detail || "Could not load rights. Stay silent. Ask for a lawyer."); }
    finally { setBusy(false); }
  }, [lang, country, coords]);

  useEffect(() => {
    // try to grab coords quickly
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
        () => {}, { timeout: 4000 }
      );
    }
    fetchRights("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="modal-bg" data-testid="emergency-modal" style={{ background: "rgba(60,0,0,0.85)" }}>
      <div className="modal-card" style={{ padding: 18, maxHeight: "95vh", border: "2px solid #dc2626" }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 10 }}>
          <h2 style={{ fontSize: 20, color: "#fca5a5", fontFamily: "Cinzel, serif", letterSpacing: "0.04em" }}>EMERGENCY — YOUR RIGHTS</h2>
          <button onClick={onClose} data-testid="emergency-close" style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}>
            <X size={24} />
          </button>
        </div>
        <div style={{ fontSize: 12, color: "#fca5a5", marginBottom: 8 }}>Country: <strong>{country}</strong>. Stay calm. Read this aloud if needed.</div>
        <div data-testid="rights-script" style={{ overflowY: "auto", maxHeight: "55vh", padding: 14, background: "#0a0000",
                     borderRadius: 12, border: "1px solid #7f1d1d", fontSize: 14, color: "var(--text)",
                     lineHeight: 1.65, whiteSpace: "pre-wrap" }}>
          {busy ? <span className="spinner" /> : rights}
        </div>
        <textarea className="input" data-testid="emergency-note" rows={2} placeholder="Optional: one line about what happened (helps Lex tailor advice)"
          value={note} onChange={(e) => setNote(e.target.value)} style={{ marginTop: 10 }} />
        <div className="flex gap-2" style={{ marginTop: 10 }}>
          <button className="btn-gold" data-testid="rights-refresh" disabled={busy} onClick={() => fetchRights(note)} style={{ flex: 1 }}>
            Re-generate with note
          </button>
          <button className="btn-ghost" onClick={onClose} style={{ flex: 1 }}>Close</button>
        </div>
        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 10, textAlign: "center" }}>
          Information only — not legal advice. If you can, call a duty solicitor immediately.
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
          <h2 className="brand-font gold" style={{ fontSize: 18, letterSpacing: "0.04em" }}>COURTROOM TRAINER</h2>
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
                <div style={{ fontSize: 12, color: "var(--text-dim)", marginBottom: 6 }}>Lex will role-play your toughest opponent so you can rehearse out loud. Pick a role and brief the facts. Safe to use anywhere — no recording sent to anyone.</div>
                <select className="input" data-testid="practice-role" value={role} onChange={(e) => setRole(e.target.value)} style={{ marginBottom: 8 }}>
                  {PRACTICE_ROLES.map(r => <option key={r.v} value={r.v}>{r.label}</option>)}
                </select>
                <textarea className="input" data-testid="practice-facts" rows={3} value={facts} onChange={(e) => setFacts(e.target.value)} placeholder="Brief Lex on your case (e.g. arrested for drink-driving, blew 60mg, claims he wasn't driving)" />
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
                    Live Legal Assist listens to your conversation and tells you what to say in real time. <strong>Recording inside an active courtroom is a criminal offence</strong> in the UK and most jurisdictions and AI Advocate refuses to be used for that.
                    <br /><br />
                    Use this ONLY in:
                    <ul style={{ marginLeft: 18, marginTop: 6 }}>
                      <li>Police interview (with your legal rep present)</li>
                      <li>Tribunal hearings where recording is permitted</li>
                      <li>Calls with your own lawyer</li>
                      <li>Mediation / arbitration with all-party consent</li>
                      <li>Internal disciplinary / HR hearings</li>
                    </ul>
                  </div>
                </div>
                <label className="flex items-start gap-2" style={{ cursor: "pointer" }}>
                  <input type="checkbox" data-testid="consent-checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)}
                    style={{ width: 18, height: 18, accentColor: "var(--gold)", marginTop: 3 }} />
                  <span style={{ fontSize: 12.5, color: "var(--text-dim)" }}>I confirm I have lawful permission to record this conversation, that I am NOT in an active courtroom, and I accept full responsibility for the legality of this use in my jurisdiction.</span>
                </label>
                <button className="btn-gold w-full" data-testid="consent-continue" disabled={!consent} onClick={() => setConsent(true)} style={{ marginTop: 14 }}>Continue</button>
              </div>
            ) : (
              <>
                {!liveActive && (
                  <>
                    <select className="input" data-testid="live-scenario" value={scenario} onChange={(e) => setScenario(e.target.value)} style={{ marginBottom: 8 }}>
                      {LIVE_SCENARIOS.map(s => <option key={s.v} value={s.v}>{s.label}</option>)}
                    </select>
                    <textarea className="input" data-testid="live-facts" rows={2} value={lFacts} onChange={(e) => setLFacts(e.target.value)} placeholder="One-line case brief (helps Lex give sharper advice)" />
                  </>
                )}
                <button className="btn-gold w-full" data-testid={liveActive ? "live-stop" : "live-start"} onClick={liveActive ? stopLive : startLive}
                  style={{ marginTop: 10, background: liveActive ? "#dc2626" : undefined, color: liveActive ? "#fff" : undefined }}>
                  {liveActive ? "STOP listening" : "START listening"}
                </button>
                {liveActive && <div style={{ textAlign: "center", color: "var(--gold)", fontSize: 12, marginTop: 6 }}>🎙 Listening — Lex will whisper advice as the other side speaks</div>}
                <div style={{ flex: 1, overflowY: "auto", marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                  {advice.length === 0 && liveActive && <div style={{ color: "var(--text-muted)", textAlign: "center", padding: 20, fontSize: 13 }}>Waiting for the other side to speak…</div>}
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
            <input className="input" data-testid="letter-search" placeholder="Search templates…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ marginBottom: 12 }} />
            <div style={{ overflowY: "auto", maxHeight: "70vh" }}>
              {Object.entries(grouped).map(([cat, items]) => (
                <div key={cat} style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 11, color: "var(--gold)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 6 }}>{cat}</div>
                  {items.map(tpl => (
                    <button key={tpl.id} data-testid={`tpl-${tpl.id}`} onClick={() => setSel(tpl)}
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
            <input className="input" data-testid="letter-name" placeholder="Your full name" value={form.your_name} onChange={(e) => setForm({ ...form, your_name: e.target.value })} style={{ marginBottom: 8 }} />
            <input className="input" data-testid="letter-recipient" placeholder="Recipient name & address" value={form.recipient} onChange={(e) => setForm({ ...form, recipient: e.target.value })} style={{ marginBottom: 8 }} />
            <textarea className="input" data-testid="letter-facts" rows={5} placeholder="Tell Lex what happened (dates, amounts, key facts)" value={form.facts} onChange={(e) => setForm({ ...form, facts: e.target.value })} />
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
              <button className="btn-ghost" onClick={() => { setLetter(""); setLetterId(null); }} style={{ flex: 1 }}>Edit / Re-do</button>
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
          <h2 className="brand-font gold" style={{ fontSize: 20 }}>Contract Review</h2>
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
              <button className="btn-ghost" onClick={() => setLetter("")} style={{ flex: 1 }}>New letter</button>
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
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>Transcript</div>
            <div style={{ background: "#0a0a0a", padding: 12, borderRadius: 10, color: "var(--text-dim)", fontSize: 13.5, marginBottom: 14 }}>{result.transcript}</div>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>Lex's Analysis</div>
            <div style={{ background: "#0a0a0a", padding: 12, borderRadius: 10, color: "var(--text-dim)", fontSize: 13.5, whiteSpace: "pre-wrap" }}>{result.analysis}</div>
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <button className="btn-gold" data-testid="record-pdf-btn" onClick={() => pdfForFile(result.id, result.filename || "recording")} style={{ flex: 1 }}>
                <Download size={16} style={{ display: "inline", marginRight: 6 }} />Download PDF
              </button>
              <button className="btn-ghost" onClick={() => setResult(null)} style={{ flex: 1 }}>Record another</button>
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
            {files.length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 20 }}>No files yet.</p>}
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

// ---------- Snap Evidence (camera + upload) ----------
function SnapEvidenceModal({ lang, country, onClose }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [evidenceType, setEvidenceType] = useState("auto");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const cameraRef = useRef(null);
  const libraryRef = useRef(null);

  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("evidence_type", evidenceType);
    fd.append("description", description);
    fd.append("language", lang);
    fd.append("country", country);
    try {
      const { data } = await api.post("/evidence/analyze", fd);
      setResult(data);
    } catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
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
        {!result ? (
          <div style={{ overflowY: "auto" }}>
            {!preview ? (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <button data-testid="evidence-camera-btn" onClick={() => cameraRef.current?.click()}
                  style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 24, color: "var(--gold)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                  <Camera size={36} /><span style={{ fontSize: 13, color: "var(--text)" }}>{t(lang, "takePhoto")}</span>
                </button>
                <button data-testid="evidence-library-btn" onClick={() => libraryRef.current?.click()}
                  style={{ background: "var(--bg-card)", border: "1px solid var(--gold-deep)", borderRadius: 14, padding: 24, color: "var(--gold)", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
                  <ImageIcon size={36} /><span style={{ fontSize: 13, color: "var(--text)" }}>{t(lang, "chooseFromLibrary")}</span>
                </button>
                <input ref={cameraRef} data-testid="evidence-camera-input" type="file" accept="image/*" capture="environment" onChange={onFile} style={{ display: "none" }} />
                <input ref={libraryRef} data-testid="evidence-library-input" type="file" accept="image/*,.pdf,.docx" onChange={onFile} style={{ display: "none" }} />
              </div>
            ) : (
              <>
                <div style={{ position: "relative", borderRadius: 14, overflow: "hidden", border: "1px solid var(--line)", marginBottom: 12 }}>
                  {file?.type?.startsWith("image/") ? (
                    <img src={preview} alt="" style={{ width: "100%", maxHeight: 320, objectFit: "contain", background: "#0a0a0a" }} />
                  ) : (
                    <div style={{ padding: 30, textAlign: "center", color: "var(--text-dim)" }}>{file?.name}</div>
                  )}
                  <button onClick={() => { setFile(null); setPreview(null); }}
                    style={{ position: "absolute", top: 8, right: 8, background: "rgba(0,0,0,0.7)", border: "1px solid var(--line)", color: "var(--text)", borderRadius: "50%", width: 32, height: 32, cursor: "pointer" }}>
                    <X size={16} />
                  </button>
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
                  {busy ? <span className="spinner" /> : t(lang, "analyzePhoto")}
                </button>
              </>
            )}
          </div>
        ) : (
          <div style={{ overflowY: "auto" }}>
            <div style={{ color: "var(--gold)", fontWeight: 600, marginBottom: 8 }}>{result.filename}</div>
            <div style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.6, color: "var(--text-dim)" }}>{result.analysis}</div>
            <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
              <button className="btn-gold" data-testid="evidence-pdf-btn" onClick={() => pdfForFile(result.id, result.filename || "evidence")} style={{ flex: 1 }}>
                <Download size={16} style={{ display: "inline", marginRight: 6 }} />Download PDF
              </button>
              <button className="btn-ghost" onClick={() => { setResult(null); setFile(null); setPreview(null); setDescription(""); }} style={{ flex: 1 }}>
                Snap another
              </button>
            </div>
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
              {!busy && firms.length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: 20 }}>No firms found.</p>}
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
            <h3 style={{ color: "var(--gold)", marginTop: 12 }}>Message sent</h3>
            <p style={{ color: "var(--text-dim)", fontSize: 14 }}>{selected.name} will get back to you soon.</p>
            <button className="btn-ghost w-full" onClick={() => { setSelected(null); setSent(false); }} style={{ marginTop: 16 }}>Back to list</button>
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
            <input className="input" data-testid="inq-name" value={inquiry.name} onChange={(e) => setInquiry({ ...inquiry, name: e.target.value })} placeholder="Name" style={{ marginBottom: 8 }} />
            <input className="input" data-testid="inq-email" value={inquiry.email} onChange={(e) => setInquiry({ ...inquiry, email: e.target.value })} placeholder="Email" style={{ marginBottom: 8 }} />
            <input className="input" data-testid="inq-phone" value={inquiry.phone} onChange={(e) => setInquiry({ ...inquiry, phone: e.target.value })} placeholder="Phone (optional)" style={{ marginBottom: 8 }} />
            <textarea className="input" data-testid="inq-message" rows={3} value={inquiry.message} onChange={(e) => setInquiry({ ...inquiry, message: e.target.value })} placeholder="Your message" />
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
      if (!navigator.geolocation) { alert("Geolocation not supported"); return; }
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
          } catch (e) { alert("Failed to save"); }
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
      } catch (e) { alert("Failed"); }
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
      <div className="modal-card" style={{ padding: 22 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 18 }}>
          <h2 className="brand-font gold" style={{ fontSize: 22 }}>{t(lang, "settings")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)", cursor: "pointer" }}><X size={22} /></button>
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
            Lex applies the laws of your selected country
          </div>
        </div>
      </div>
    </div>
  );
}


// ---------- Subscribe Modal ----------
function SubscribeModal({ lang, user, onClose, onActivated }) {
  const [busy, setBusy] = useState(false);
  const checkout = async (plan) => {
    setBusy(true);
    try { const { data } = await api.post("/subscription/checkout", { plan }); window.location.href = data.checkout_url; }
    catch (e) { alert(e?.response?.data?.detail || "Failed"); setBusy(false); }
  };
  const demoActivate = async () => {
    setBusy(true);
    try { const { data } = await api.post("/subscription/activate-test"); onActivated(data); }
    catch (e) { alert(e?.response?.data?.detail || "Failed"); }
    finally { setBusy(false); }
  };
  return (
    <div className="modal-bg" data-testid="subscribe-modal">
      <div className="modal-card" style={{ padding: 22 }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 14 }}>
          <h2 className="brand-font gold" style={{ fontSize: 22 }}>{t(lang, "plansTitle")}</h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", color: "var(--text)" }}><X size={22} /></button>
        </div>
        <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 16, padding: 16, marginBottom: 12 }}>
          <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{t(lang, "monthly")}</div>
          <div style={{ fontSize: 28, color: "var(--gold)", fontWeight: 600 }}>£14.99 <span style={{ fontSize: 14, color: "var(--text-muted)" }}>/mo</span></div>
          <button className="btn-gold w-full" data-testid="checkout-monthly-btn" onClick={() => checkout("monthly")} disabled={busy} style={{ marginTop: 10 }}>
            {busy ? <span className="spinner" /> : t(lang, "subscribe")}
          </button>
        </div>
        <div style={{ background: "var(--bg-card)", border: "1px solid var(--gold)", borderRadius: 16, padding: 16, position: "relative" }}>
          <div style={{ position: "absolute", top: -10, right: 14, background: "var(--gold)", color: "#1a1300", padding: "2px 10px", fontSize: 12, borderRadius: 8, fontWeight: 600 }}>{t(lang, "bestValue")}</div>
          <div style={{ fontSize: 13, color: "var(--text-muted)" }}>{t(lang, "yearly")}</div>
          <div style={{ fontSize: 28, color: "var(--gold)", fontWeight: 600 }}>£119.99 <span style={{ fontSize: 14, color: "var(--text-muted)" }}>/yr</span></div>
          <button className="btn-gold w-full" data-testid="checkout-yearly-btn" onClick={() => checkout("yearly")} disabled={busy} style={{ marginTop: 10 }}>
            {busy ? <span className="spinner" /> : t(lang, "subscribe")}
          </button>
        </div>
        <button className="btn-ghost w-full" data-testid="demo-activate-btn" onClick={demoActivate} disabled={busy} style={{ marginTop: 12, fontSize: 13 }}>
          Activate (demo / no payment)
        </button>
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
          <div style={{
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
  const [showSettings, setShowSettings] = useState(false);
  const [showAdvertise, setShowAdvertise] = useState(false);
  const [showEmergency, setShowEmergency] = useState(false);
  const [wakeOn, setWakeOn] = useState(() => localStorage.getItem("aa_wake") !== "0");

  // "Hey Lex" wake word — opens Ask Lex when user says it
  const handleWake = useCallback(() => {
    if (modal) return; // don't interrupt an open modal
    if (!user.has_access) { setShowSub(true); return; }
    setModal({ type: "chat", title: t(lang, "askLex"), category: "ask_lex", autoMic: true });
  }, [modal, user.has_access, lang]);
  useHeyLex({ enabled: wakeOn && !modal && user.has_access, lang, onWake: handleWake });

  const tiles = [
    { id: "ask_lex", label: t(lang, "askLex"), sub: t(lang, "askLexSub"), Icon: AskLexIcon, cat: "ask_lex" },
    { id: "courtroom", label: "Courtroom Trainer", Icon: CourtIcon },
    { id: "record", label: t(lang, "recordLegal"), Icon: RecordIcon, cat: "record" },
    { id: "snap", label: t(lang, "snapEvidence"), Icon: CameraIcon },
    { id: "lawyers", label: t(lang, "findLawyer"), Icon: LawyerIcon },
    { id: "files", label: t(lang, "myFiles"), Icon: FilesIcon },
    { id: "letter", label: "Letter Library", Icon: LetterIcon },
    { id: "immigration", label: t(lang, "immigration"), Icon: ImmigrationIcon, cat: "immigration" },
    { id: "employment", label: t(lang, "employment"), Icon: EmploymentIcon, cat: "employment" },
    { id: "property", label: t(lang, "property"), Icon: PropertyIcon, cat: "property" },
    { id: "medical", label: t(lang, "medical"), Icon: MedicalIcon, cat: "medical_negligence" },
  ];

  const onTile = (tile) => {
    // Free for all tiles: lawyers + files (don't gate behind subscription)
    const free = ["lawyers", "files"];
    if (!user.has_access && !free.includes(tile.id)) { setShowSub(true); return; }
    if (tile.id === "files") setModal({ type: "files" });
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
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>Hi, <span style={{ color: "var(--gold)" }}>{user.full_name || user.email.split("@")[0]}</span></div>
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
        <span style={{ fontSize: 18 }}>⚠</span> I've Been Arrested — My Rights NOW
      </button>

      {!user.has_access ? (
        <div className="trial-banner" data-testid="trial-banner-ended" style={{ marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>{t(lang, "trialEnded")}</span>
          <button className="btn-gold" data-testid="open-subscribe-btn" onClick={() => setShowSub(true)} style={{ padding: "8px 14px", fontSize: 13 }}>
            {t(lang, "subscribe")}
          </button>
        </div>
      ) : user.subscription_status === "trial" ? (
        <div className="trial-banner" data-testid="trial-banner" style={{ marginBottom: 14 }}>
          {t(lang, "trialDays", { n: user.trial_days_remaining })}
        </div>
      ) : null}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4, rowGap: 18 }}>
        {tiles.map(tile => (
          <button key={tile.id} className="tile-clean" data-testid={`tile-${tile.id}`} onClick={() => onTile(tile)}>
            <tile.Icon size={48} />
            <div className="tile-clean-title">{tile.label}</div>
            {tile.sub && <div className="tile-clean-sub">{tile.sub}</div>}
          </button>
        ))}
      </div>

      <BottomNav lang={lang} active="home"
        onNav={(k) => {
          if (k === "lex") setModal({ type: "chat", title: "LEX", category: "ask_lex" });
          else if (k === "files") setModal({ type: "files" });
          else if (k === "lawyers") setModal({ type: "lawyers" });
          else if (k === "settings") setShowSettings(true);
        }} hasAccess={user.has_access} requireSub={() => setShowSub(true)} />

      {modal?.type === "chat" && <LexChat lang={lang} country={country} category={modal.category} title={modal.title} autoMic={!!modal.autoMic} onClose={() => setModal(null)} />}
      {modal?.type === "courtroom" && <CourtroomModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "letter_lib" && <LetterLibraryModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "files" && <FilesModal lang={lang} onClose={() => setModal(null)} />}
      {modal?.type === "letter" && <LegalLetterModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "record" && <RecordModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "snap" && <SnapEvidenceModal lang={lang} country={country} onClose={() => setModal(null)} />}
      {modal?.type === "lawyers" && <LawyersModal lang={lang} country={country} user={user} onClose={() => setModal(null)} openAdvertise={() => { setModal(null); setShowAdvertise(true); }} />}
      {showEmergency && <EmergencyModal lang={lang} country={country} onClose={() => setShowEmergency(false)} />}
      {showLang && <LanguagePicker initial={lang} lang={lang} onConfirm={(l) => { setLang(l); setShowLang(false); api.patch("/auth/preferences", { language: l }).catch(() => {}); }} />}
      {showSub && <SubscribeModal lang={lang} user={user} onClose={() => setShowSub(false)} onActivated={(u) => { refreshUser(u); setShowSub(false); }} />}
      {showSettings && <SettingsModal lang={lang} country={country} user={user} onClose={() => setShowSettings(false)} onUpdate={(u) => refreshUser(u)} setLang={setLang} setCountry={setCountry} />}
      {showAdvertise && <AdvertiseModal lang={lang} onClose={() => setShowAdvertise(false)} />}
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
