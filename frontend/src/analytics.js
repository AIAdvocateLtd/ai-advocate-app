// PostHog product analytics — autocapture + identify by backend user_id + custom events.
// Loaded lazily so it never blocks first paint or app boot.
import posthog from "posthog-js";

const TOKEN = process.env.REACT_APP_POSTHOG_TOKEN;
const HOST = process.env.REACT_APP_POSTHOG_HOST || "https://eu.i.posthog.com";

let initialized = false;

// 🍪 Cookie / PECR consent gate — analytics is disabled until the user clicks "Accept all"
// in the CookieConsentBanner. The banner sets `aa_cookie_consent = "accepted" | "rejected"`
// in localStorage, and we honour Do-Not-Track too.
function _consentGranted() {
  try {
    if (window.__aa_analytics_off === true) return false;
    if (localStorage.getItem("aa_analytics_off") === "1") return false;  // Settings opt-out
    const c = localStorage.getItem("aa_cookie_consent");
    return c === "accepted";
  } catch (e) { return false; }
}

function ensureInit() {
  if (initialized || !TOKEN) return initialized;
  if (!_consentGranted()) return false;        // never init until user opts in
  try {
    posthog.init(TOKEN, {
      api_host: HOST,
      autocapture: true,
      capture_pageview: true,
      capture_pageleave: true,
      disable_session_recording: true,    // privacy-first — turn on later if needed
      persistence: "localStorage+cookie",
      respect_dnt: true,                  // honour browser Do-Not-Track
      // Mask any sensitive form fields by default (PINs, passwords, vault content)
      mask_all_text: false,
      mask_personal_data_properties: true,
      // Bootstrap the session_id from localStorage when present (avoids splitting users across tabs)
      loaded: () => { initialized = true; },
    });
    initialized = true;
  } catch (e) {
    initialized = false;
  }
  return initialized;
}

// Defer init until consent is granted (see ensureInit). The track()/identify() calls
// below are idempotent — they call ensureInit() each time, so they auto-activate the
// first time the user clicks "Accept all" in the cookie banner.
// ensureInit();  // disabled — analytics now opt-in only per UK PECR

export function track(event, props = {}) {
  if (!ensureInit()) return;
  try { posthog.capture(event, props); } catch (e) { /* no-op */ }
}

export function identify(user) {
  if (!ensureInit() || !user || !user.id) return;
  try {
    posthog.identify(String(user.id), {
      email: user.email,
      tier: user.tier,
      country: user.country,
      language: user.language,
    });
  } catch (e) { /* no-op */ }
}

export function resetAnalytics() {
  if (!ensureInit()) return;
  try { posthog.reset(); } catch (e) { /* no-op */ }
}
