// Sentry browser instrumentation — MUST be imported FIRST in index.js
// so early errors are captured before any React render.
import * as Sentry from "@sentry/react";

const dsn = process.env.REACT_APP_SENTRY_DSN;

// 🔒 User opt-out — respected at init time + each beforeSend. Set in Settings →
// Privacy & analytics. localStorage key: aa_crash_off = "1"
function _crashOptedOut() {
  try { return localStorage.getItem("aa_crash_off") === "1"; } catch (e) { return false; }
}

if (dsn && !_crashOptedOut()) {
  Sentry.init({
    dsn,
    sendDefaultPii: true,
    environment: process.env.NODE_ENV || "production",
    tracesSampleRate: 0.2,
    integrations: [
      Sentry.browserTracingIntegration(),
    ],
    // Drop events on the floor if the user has flipped the toggle since init
    beforeSend: (event) => (_crashOptedOut() ? null : event),
    ignoreErrors: [
      "ResizeObserver loop limit exceeded",
      "Non-Error promise rejection captured",
      "NetworkError when attempting to fetch resource",
      "Load failed",
      // user just cancelled an action mid-fetch
      "AbortError",
    ],
    // Reduce noise from common 3rd-party browser extension errors
    denyUrls: [
      /extensions\//i, /^chrome:\/\//i, /^chrome-extension:\/\//i, /^moz-extension:\/\//i,
    ],
  });
}

// Optional helper: lets non-React modules set the current user once login happens.
export const setSentryUser = (user) => {
  if (!dsn || !user) return;
  try {
    Sentry.setUser({ id: user.id, email: user.email, tier: user.tier });
  } catch (e) { /* no-op */ }
};

export const clearSentryUser = () => {
  if (!dsn) return;
  try { Sentry.setUser(null); } catch (e) { /* no-op */ }
};
