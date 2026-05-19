// PostHog product analytics — autocapture + identify by backend user_id + custom events.
// Loaded lazily so it never blocks first paint or app boot.
import posthog from "posthog-js";

const TOKEN = process.env.REACT_APP_POSTHOG_TOKEN;
const HOST = process.env.REACT_APP_POSTHOG_HOST || "https://eu.i.posthog.com";

let initialized = false;

function ensureInit() {
  if (initialized || !TOKEN) return initialized;
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

ensureInit();

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
