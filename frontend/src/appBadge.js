// ============================== APP BADGE ==============================
// Sets the native home-screen app-icon badge (e.g. iOS / Android / Chromium PWA).
// Works in three places:
//   1. Web App Badging API — Chromium, iOS 16.4+ when site is installed as PWA
//   2. Capacitor wrapper (native iOS / Android) — via @capacitor/badge if installed
//   3. In-app gold dot fallback — always works via React state in BottomNav
//
// Silent failure: if the platform doesn't support badging, we just no-op.
// The in-app dot still gives users the visual cue when they open the app.

export async function setAppIconBadge(count) {
  const n = Math.max(0, Math.floor(Number(count) || 0));

  // 1) Web App Badging API (works on installed Chromium PWAs and iOS 16.4+ PWAs)
  try {
    if (typeof navigator !== "undefined") {
      if (n > 0 && typeof navigator.setAppBadge === "function") {
        await navigator.setAppBadge(n);
      } else if (n === 0 && typeof navigator.clearAppBadge === "function") {
        await navigator.clearAppBadge();
      }
    }
  } catch (e) {
    // Permission may be required (Chrome) — we silently ignore. User will still see in-app dot.
  }

  // 2) Capacitor native badge (post-wrap). We dynamically reference the global so this file
  //    works fine in the web build where Capacitor isn't installed.
  try {
    const Cap = typeof window !== "undefined" ? window.Capacitor : null;
    if (Cap && Cap.isNativePlatform && Cap.isNativePlatform()) {
      const Badge = Cap.Plugins && Cap.Plugins.Badge;
      if (Badge) {
        if (n > 0) await Badge.set({ count: n });
        else if (Badge.clear) await Badge.clear();
      }
    }
  } catch (e) { /* no-op */ }
}

// Try to request notification permission once — required by some browsers (Chrome) for badging.
// Called lazily on first user interaction (e.g. settings toggle or first tile tap) — NOT at app boot.
export async function maybeRequestBadgePermission() {
  try {
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      await Notification.requestPermission();
    }
  } catch (e) { /* no-op */ }
}
