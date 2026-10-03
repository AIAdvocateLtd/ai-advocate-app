// PWA Install Prompt — custom "Add to Home Screen" UX for Android (Chrome)
// and iOS (Safari). This replaces the Apple App Store route for new users.
//
// Behaviour:
//  • On Android/desktop Chrome: listens to `beforeinstallprompt`, shows a
//    branded "Install app" card with an in-app install button.
//  • On iOS Safari: Safari doesn't fire `beforeinstallprompt`, so we show
//    a card with illustrated Share → "Add to Home Screen" instructions.
//  • Suppressed when: already installed (standalone), inside a native
//    Capacitor wrapper, inside the Emergent preview iframe, user has
//    dismissed within the last 7 days, or user already installed once.
//  • Appears ~12s after first mount so it doesn't fight the splash/tour.

import React, { useEffect, useState } from "react";
import { X, Share, Plus, Download } from "lucide-react";

const DISMISS_KEY = "aa_pwa_dismiss_ts";
const INSTALLED_KEY = "aa_pwa_installed";
const DISMISS_WINDOW_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

const isStandalone = () =>
  (typeof window !== "undefined") &&
  ((window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) ||
    window.navigator.standalone === true);

const isCapacitorNative = () =>
  typeof window !== "undefined" &&
  (window.Capacitor?.isNativePlatform?.() === true || !!window.Capacitor?.getPlatform?.().match?.(/^(ios|android)$/));

const isInIframe = () => {
  try { return window.self !== window.top; } catch { return true; }
};

const detectIOS = () => {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  const iOS = /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  return iOS && isSafari;
};

const recentlyDismissed = () => {
  const ts = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
  return ts && (Date.now() - ts) < DISMISS_WINDOW_MS;
};

export default function PWAInstallPrompt() {
  const [visible, setVisible] = useState(false);
  const [deferredEvt, setDeferredEvt] = useState(null);
  const [mode, setMode] = useState(null); // "android" | "ios"
  const [showIOSSheet, setShowIOSSheet] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (isStandalone()) return;
    if (isCapacitorNative()) return;
    if (isInIframe()) return; // never show in Emergent preview iframe
    if (localStorage.getItem(INSTALLED_KEY) === "1") return;
    if (recentlyDismissed()) return;

    let delayTimer;

    // Android/Chrome path — real install event
    const onBIP = (e) => {
      e.preventDefault();
      setDeferredEvt(e);
      setMode("android");
      delayTimer = setTimeout(() => setVisible(true), 12000);
    };
    window.addEventListener("beforeinstallprompt", onBIP);

    // Once installed via Chrome prompt, remember it
    const onInstalled = () => {
      localStorage.setItem(INSTALLED_KEY, "1");
      setVisible(false);
    };
    window.addEventListener("appinstalled", onInstalled);

    // iOS Safari path — no BIP event, so proactively surface after delay
    if (detectIOS()) {
      setMode("ios");
      delayTimer = setTimeout(() => setVisible(true), 12000);
    }

    return () => {
      window.removeEventListener("beforeinstallprompt", onBIP);
      window.removeEventListener("appinstalled", onInstalled);
      if (delayTimer) clearTimeout(delayTimer);
    };
  }, []);

  const dismiss = () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    setVisible(false);
    setShowIOSSheet(false);
  };

  const triggerAndroidInstall = async () => {
    if (!deferredEvt) return;
    try {
      deferredEvt.prompt();
      const choice = await deferredEvt.userChoice;
      if (choice?.outcome === "accepted") {
        localStorage.setItem(INSTALLED_KEY, "1");
      } else {
        localStorage.setItem(DISMISS_KEY, String(Date.now()));
      }
    } catch { /* no-op */ }
    setDeferredEvt(null);
    setVisible(false);
  };

  const openIOSInstructions = () => setShowIOSSheet(true);

  if (!visible && !showIOSSheet) return null;

  // Shared card wrapper
  const card = {
    position: "fixed",
    left: 12,
    right: 12,
    bottom: `calc(env(safe-area-inset-bottom, 0px) + 14px)`,
    maxWidth: 440,
    margin: "0 auto",
    background: "linear-gradient(135deg, #1a1300 0%, #0f0b02 100%)",
    border: "1px solid #d6a017",
    borderRadius: 14,
    padding: 14,
    color: "#fefdf8",
    boxShadow: "0 16px 48px rgba(0,0,0,0.6), 0 0 0 1px rgba(247,201,72,0.08)",
    zIndex: 10050,
    display: "flex",
    alignItems: "flex-start",
    gap: 12,
    animation: "aaSlideUp .35s ease-out both",
  };

  const btnGold = {
    background: "linear-gradient(180deg, #f7c948, #d6a017)",
    color: "#1a1300",
    border: "none",
    borderRadius: 10,
    padding: "9px 14px",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  };

  // iOS instructions sheet (step-by-step)
  if (showIOSSheet) {
    return (
      <>
        <style>{`
          @keyframes aaSlideUp { from { transform: translateY(24px); opacity: 0 } to { transform: translateY(0); opacity: 1 } }
        `}</style>
        <div data-testid="pwa-ios-sheet"
          onClick={dismiss}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.72)",
            zIndex: 10060, display: "flex", alignItems: "flex-end",
            justifyContent: "center", padding: 12,
            animation: "aaSlideUp .25s ease-out both",
          }}>
          <div onClick={(e) => e.stopPropagation()}
            style={{
              width: "100%", maxWidth: 460,
              background: "linear-gradient(135deg, #1a1300 0%, #0f0b02 100%)",
              border: "1px solid #d6a017", borderRadius: 18,
              padding: 20, color: "#fefdf8",
              boxShadow: "0 24px 64px rgba(0,0,0,0.7)",
            }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 11, color: "#f7c948", letterSpacing: 1.2, fontWeight: 700, marginBottom: 4 }}>
                  INSTALL AI ADVOCATE
                </div>
                <h3 style={{ margin: 0, fontSize: 18, color: "#fde68a", fontWeight: 700 }}>
                  Get the app on your home screen
                </h3>
              </div>
              <button data-testid="pwa-ios-close" onClick={dismiss}
                style={{ background: "transparent", border: "none", color: "#c9bfa6", cursor: "pointer", padding: 4 }}>
                <X size={20} />
              </button>
            </div>
            <p style={{ fontSize: 13, color: "#c9bfa6", margin: "6px 0 14px", lineHeight: 1.5 }}>
              AI Advocate works best as an app. Three taps and you're done — no App Store needed.
            </p>
            <ol style={{ margin: 0, paddingLeft: 0, listStyle: "none" }}>
              <li style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 14, padding: 10, background: "rgba(247,201,72,0.06)", border: "1px solid #2a2218", borderRadius: 10 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: "#d6a017", color: "#1a1300", fontWeight: 800, fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>1</div>
                <div style={{ flex: 1, fontSize: 14 }}>
                  Tap the <strong style={{ color: "#f7c948" }}>Share</strong> button
                  <Share size={16} style={{ display: "inline", verticalAlign: "middle", margin: "0 4px", color: "#60a5fa" }} />
                  at the bottom of Safari
                </div>
              </li>
              <li style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 14, padding: 10, background: "rgba(247,201,72,0.06)", border: "1px solid #2a2218", borderRadius: 10 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: "#d6a017", color: "#1a1300", fontWeight: 800, fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>2</div>
                <div style={{ flex: 1, fontSize: 14 }}>
                  Scroll and tap <strong style={{ color: "#f7c948" }}>Add to Home Screen</strong>
                  <Plus size={16} style={{ display: "inline", verticalAlign: "middle", margin: "0 4px" }} />
                </div>
              </li>
              <li style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 4, padding: 10, background: "rgba(247,201,72,0.06)", border: "1px solid #2a2218", borderRadius: 10 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: "#d6a017", color: "#1a1300", fontWeight: 800, fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>3</div>
                <div style={{ flex: 1, fontSize: 14 }}>
                  Tap <strong style={{ color: "#f7c948" }}>Add</strong> — your Lex icon lands on your home screen.
                </div>
              </li>
            </ol>
            <button data-testid="pwa-ios-got-it" onClick={dismiss}
              style={{ ...btnGold, width: "100%", justifyContent: "center", marginTop: 16, padding: "11px 14px", fontSize: 14 }}>
              Got it
            </button>
          </div>
        </div>
      </>
    );
  }

  // Main compact card
  return (
    <>
      <style>{`
        @keyframes aaSlideUp { from { transform: translateY(24px); opacity: 0 } to { transform: translateY(0); opacity: 1 } }
      `}</style>
      <div data-testid="pwa-install-prompt" style={card}>
        <img src="/assets/icon-192.png" alt="AI Advocate"
          width={44} height={44}
          style={{ borderRadius: 10, flexShrink: 0, boxShadow: "0 2px 10px rgba(0,0,0,0.5)" }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#fde68a", marginBottom: 2 }}>
            Install AI Advocate
          </div>
          <div style={{ fontSize: 12, color: "#c9bfa6", lineHeight: 1.4 }}>
            {mode === "ios"
              ? "Add to your home screen — like a real app, no App Store needed."
              : "One tap to install. Works offline. Opens like a native app."}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            {mode === "android" ? (
              <button data-testid="pwa-android-install" onClick={triggerAndroidInstall} style={btnGold}>
                <Download size={14} /> Install
              </button>
            ) : (
              <button data-testid="pwa-ios-show" onClick={openIOSInstructions} style={btnGold}>
                <Plus size={14} /> Show me how
              </button>
            )}
            <button data-testid="pwa-dismiss" onClick={dismiss}
              style={{
                background: "transparent",
                color: "#c9bfa6",
                border: "1px solid #2a2218",
                borderRadius: 10,
                padding: "9px 12px",
                fontSize: 13,
                cursor: "pointer",
              }}>
              Not now
            </button>
          </div>
        </div>
        <button data-testid="pwa-close" onClick={dismiss}
          style={{ background: "transparent", border: "none", color: "#8a8270", cursor: "pointer", padding: 2, flexShrink: 0 }}
          aria-label="Dismiss install prompt">
          <X size={16} />
        </button>
      </div>
    </>
  );
}
