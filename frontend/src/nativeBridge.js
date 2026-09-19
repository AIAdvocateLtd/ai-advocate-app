// AI Advocate — Native Bridge
// ------------------------------------------------------------------
// A thin layer that lets the same React code work in both:
//   • web browser (today's preview / production website)
//   • Capacitor-wrapped iOS / Android native app (TestFlight / Play)
//
// Every method below has TWO implementations:
//   1. A native one that uses Capacitor plugins when running inside the wrap.
//   2. A web fallback that uses the existing browser APIs.
//
// The result: NO existing UI code has to change — components keep calling
// `navigator.share`, `navigator.geolocation`, `localStorage` etc. as today.
// When we want to upgrade a specific surface to use native APIs (e.g. switch
// the Vault key from localStorage to Keychain), we replace just that one call
// site with the equivalent from this bridge.
//
// Import:  import { native, isNative, ... } from "@/nativeBridge";
// ------------------------------------------------------------------

import { Capacitor } from "@capacitor/core";

// ---------- Platform detection ----------
export const isNative = () => Capacitor.isNativePlatform?.() === true;
export const getPlatform = () => Capacitor.getPlatform?.() || "web";

// Lazy-load each plugin only if we're on native — keeps web bundle small.
async function lazy(name) {
  if (!isNative()) return null;
  try {
    switch (name) {
      case "Geolocation": return (await import("@capacitor/geolocation")).Geolocation;
      case "Filesystem":  return await import("@capacitor/filesystem");
      case "Share":       return (await import("@capacitor/share")).Share;
      case "Preferences": return (await import("@capacitor/preferences")).Preferences;
      case "SplashScreen":return (await import("@capacitor/splash-screen")).SplashScreen;
      case "StatusBar":   return (await import("@capacitor/status-bar")).StatusBar;
      case "App":         return (await import("@capacitor/app")).App;
      case "Haptics":     return await import("@capacitor/haptics");
      case "Network":     return (await import("@capacitor/network")).Network;
      case "Device":      return (await import("@capacitor/device")).Device;
      case "Clipboard":   return (await import("@capacitor/clipboard")).Clipboard;
      case "Browser":     return (await import("@capacitor/browser")).Browser;
      case "Keyboard":    return (await import("@capacitor/keyboard")).Keyboard;
      default: return null;
    }
  } catch (e) {
    console.warn(`[nativeBridge] failed to load ${name}:`, e);
    return null;
  }
}

// ---------- Geolocation ----------
// Web: navigator.geolocation.getCurrentPosition
// Native: Capacitor Geolocation API (more reliable on iOS background + better
// permission UX). Returns same shape {lat, lng, accuracy, ts} either way.
export async function getPosition({ timeout = 10000, highAccuracy = true } = {}) {
  if (isNative()) {
    const Geo = await lazy("Geolocation");
    if (Geo) {
      try {
        const perm = await Geo.checkPermissions();
        if (perm.location !== "granted") await Geo.requestPermissions();
        const p = await Geo.getCurrentPosition({ enableHighAccuracy: highAccuracy, timeout });
        return {
          lat: p.coords.latitude,
          lng: p.coords.longitude,
          accuracy: p.coords.accuracy,
          ts: p.timestamp,
        };
      } catch (e) {
        console.warn("[nativeBridge] Capacitor geolocation failed, falling back to web:", e);
      }
    }
  }
  // Web fallback
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("Geolocation unsupported"));
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({
        lat: p.coords.latitude,
        lng: p.coords.longitude,
        accuracy: p.coords.accuracy,
        ts: p.timestamp,
      }),
      (e) => reject(e),
      { enableHighAccuracy: highAccuracy, timeout, maximumAge: 0 }
    );
  });
}

// ---------- Share ----------
// Web: navigator.share (mobile Safari/Chrome only) → fallback to clipboard.
// Native: Capacitor Share — full native share sheet with iMessage, Mail, etc.
export async function share({ title = "AI Advocate", text = "", url = "" }) {
  if (isNative()) {
    const S = await lazy("Share");
    if (S) {
      try { await S.share({ title, text, url, dialogTitle: title }); return true; }
      catch (e) { /* user cancelled or unsupported, fall through */ }
    }
  }
  if (typeof navigator !== "undefined" && navigator.share) {
    try { await navigator.share({ title, text, url }); return true; } catch (e) { /* user cancelled */ }
  }
  // Last-resort: copy to clipboard
  try {
    await navigator.clipboard.writeText(url || text);
    return "copied";
  } catch (e) { return false; }
}

// ---------- Secure key/value storage ----------
// Web: localStorage (today's behaviour).
// Native: Capacitor Preferences → backed by iOS Keychain / Android EncryptedSharedPreferences,
// which is what you want for the Vault unlock token, refresh tokens, etc.
export async function secureGet(key) {
  if (isNative()) {
    const P = await lazy("Preferences");
    if (P) { try { const { value } = await P.get({ key }); return value; } catch (e) {} }
  }
  try { return localStorage.getItem(key); } catch (e) { return null; }
}
export async function secureSet(key, value) {
  if (isNative()) {
    const P = await lazy("Preferences");
    if (P) { try { await P.set({ key, value: String(value) }); return true; } catch (e) {} }
  }
  try { localStorage.setItem(key, String(value)); return true; } catch (e) { return false; }
}
export async function secureRemove(key) {
  if (isNative()) {
    const P = await lazy("Preferences");
    if (P) { try { await P.remove({ key }); return true; } catch (e) {} }
  }
  try { localStorage.removeItem(key); return true; } catch (e) { return false; }
}

// ---------- External URL opener ----------
// Web: window.open(_blank).
// Native: in-app SafariViewController / Chrome Custom Tab via Capacitor Browser.
// Critical because App Store reject apps that bounce to mobile Safari for
// long-form content (e.g. tapping a BAILII citation pill).
export async function openExternal(url) {
  if (!url) return;
  if (isNative()) {
    const B = await lazy("Browser");
    if (B) { try { await B.open({ url, presentationStyle: "popover" }); return; } catch (e) {} }
  }
  try { window.open(url, "_blank", "noopener,noreferrer"); } catch (e) {}
}

// ---------- Haptics (SOS, panic, success confirmation) ----------
export async function vibrate(kind = "medium") {
  if (isNative()) {
    const H = await lazy("Haptics");
    if (H) {
      try {
        if (kind === "success") return await H.Haptics.notification({ type: H.NotificationType.Success });
        if (kind === "warning") return await H.Haptics.notification({ type: H.NotificationType.Warning });
        if (kind === "error")   return await H.Haptics.notification({ type: H.NotificationType.Error });
        if (kind === "heavy")   return await H.Haptics.impact({ style: H.ImpactStyle.Heavy });
        if (kind === "light")   return await H.Haptics.impact({ style: H.ImpactStyle.Light });
        return await H.Haptics.impact({ style: H.ImpactStyle.Medium });
      } catch (e) {}
    }
  }
  if (typeof navigator !== "undefined" && navigator.vibrate) {
    const pat = { light: 20, medium: 50, heavy: 100, error: [100, 50, 100], success: 30, warning: [50, 100, 50] };
    try { navigator.vibrate(pat[kind] || 50); } catch (e) {}
  }
}

// ---------- Network status ----------
export async function getNetworkStatus() {
  if (isNative()) {
    const N = await lazy("Network");
    if (N) { try { return await N.getStatus(); } catch (e) {} }
  }
  return {
    connected: typeof navigator !== "undefined" ? navigator.onLine : true,
    connectionType: typeof navigator !== "undefined" && navigator.connection?.effectiveType ? navigator.connection.effectiveType : "unknown",
  };
}

// ---------- Splash screen control ----------
// Call this from App.js once the React tree has fully booted + the auth check
// has finished, so the native splash hides at the right moment (instead of
// the Capacitor default 1.8s timer).
export async function hideSplash() {
  if (!isNative()) return;
  const S = await lazy("SplashScreen");
  if (S) { try { await S.hide({ fadeOutDuration: 250 }); } catch (e) {} }
}

// ---------- App lifecycle listeners (background / foreground / back button) ----------
export async function addAppListeners({ onResume, onPause, onBackButton } = {}) {
  if (!isNative()) return () => {};
  const App = await lazy("App");
  if (!App) return () => {};
  const subs = [];
  if (onResume) subs.push(await App.addListener("appStateChange", (s) => { if (s.isActive) onResume(); else onPause?.(); }));
  if (onBackButton) subs.push(await App.addListener("backButton", onBackButton));
  return () => subs.forEach(s => s.remove?.());
}

// ---------- File export (GDPR data export & similar) ----------
// Web: triggers a browser download via <a download>. Works everywhere except
//      WKWebView (Capacitor iOS) where the anchor click is a silent no-op.
// Native: writes the file to app cache dir with Filesystem, then opens the
//         iOS Share sheet so the user can Save to Files / Mail / AirDrop.
// Returns { ok: true, method: 'native'|'web', path? } or { ok: false, error }.
export async function exportFile({ filename = "export.json", contents = "", mimeType = "application/json" } = {}) {
  if (isNative()) {
    let step = "init";
    try {
      step = "load-filesystem";
      const FS = await lazy("Filesystem");
      step = "load-share";
      const S = await lazy("Share");
      if (!FS) throw new Error("Filesystem plugin unavailable");
      if (!S)  throw new Error("Share plugin unavailable");
      step = "writeFile";
      // Write file to app cache dir (auto-cleaned by iOS, no permission prompt).
      const write = await FS.Filesystem.writeFile({
        path: filename,
        data: contents,
        directory: FS.Directory.Cache,
        encoding: FS.Encoding.UTF8,
      });
      step = "getUri";
      // On iOS, `write.uri` is already a valid file:// URL. Belt-and-braces:
      // explicitly resolve via getUri so we always share a native path.
      let uri = write?.uri;
      try {
        const resolved = await FS.Filesystem.getUri({ directory: FS.Directory.Cache, path: filename });
        if (resolved?.uri) uri = resolved.uri;
      } catch (e) { /* fall through with write.uri */ }
      if (!uri) throw new Error("Could not resolve file URI after write");
      step = "share";
      // Capacitor Share on iOS accepts `url` (file:// URI) OR `files` array.
      // Try the modern `files` field first, fall back to `url`.
      try {
        await S.share({
          title: "AI Advocate — Data Export",
          text: "Your AI Advocate data export.",
          files: [uri],
          dialogTitle: "Save or share your data",
        });
      } catch (shareErr) {
        // Retry with url field (Capacitor Share v4-v6 style)
        await S.share({
          title: "AI Advocate — Data Export",
          text: "Your AI Advocate data export.",
          url: uri,
          dialogTitle: "Save or share your data",
        });
      }
      return { ok: true, method: "native", path: uri };
    } catch (e) {
      const msg = e?.message || String(e);
      console.warn(`[nativeBridge] Native export failed at step=${step}:`, msg);
      // iOS Share sheet returns an error if the user simply *cancels* — treat
      // that as a soft success so we don't show a scary red toast.
      if (/cancel/i.test(msg) || /dismiss/i.test(msg)) {
        return { ok: true, method: "native-cancelled" };
      }
      // Otherwise, return the error so the caller can display a real message.
      return { ok: false, error: `${step}: ${msg}`, native: true };
    }
  }
  // Web fallback — standard <a download> click (does NOT work in WKWebView).
  try {
    const blob = new Blob([contents], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.rel = "noopener";
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 800);
    return { ok: true, method: "web" };
  } catch (e) {
    return { ok: false, error: e?.message || String(e) };
  }
}

// ---------- Keyboard height tracking (iOS chat-input fix) ----------
// Publishes `--kb-height` on <html> whenever the software keyboard opens/closes
// so any bottom-anchored UI (like the Lex chat input) can lift itself above it.
// Web version leaves it as 0px — Safari handles keyboard viewport natively.
// Returns a cleanup fn.
export async function attachKeyboardListeners() {
  if (!isNative()) return () => {};
  const K = await lazy("Keyboard");
  if (!K) return () => {};
  const root = document.documentElement;
  const setKb = (h) => root.style.setProperty("--kb-height", (h || 0) + "px");
  setKb(0);
  const subs = [];
  try {
    subs.push(await K.addListener("keyboardWillShow", (info) => setKb(info?.keyboardHeight || 0)));
    subs.push(await K.addListener("keyboardDidShow",  (info) => setKb(info?.keyboardHeight || 0)));
    subs.push(await K.addListener("keyboardWillHide", () => setKb(0)));
    subs.push(await K.addListener("keyboardDidHide",  () => setKb(0)));
  } catch (e) { console.warn("[nativeBridge] Keyboard listeners failed:", e); }
  return () => subs.forEach(s => s.remove?.());
}

// Default export — handy for `import native from "@/nativeBridge"`
const native = {
  isNative, getPlatform,
  getPosition, share, openExternal,
  secureGet, secureSet, secureRemove,
  vibrate, getNetworkStatus, hideSplash, addAppListeners,
  attachKeyboardListeners, exportFile,
};
export default native;
