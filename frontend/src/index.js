// Sentry MUST be the first import — captures errors that happen before React mounts.
import "@/sentry";
import { setSentryUser } from "@/sentry"; // re-exported intentionally for downstream use
import React from "react";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";
import "@/index.css";
import App from "@/App";
import FirmPortal from "@/FirmPortal";
import FirmSign from "@/FirmSign";

const path = window.location.pathname || "";
const isFirmSign = path.startsWith("/firm-sign/");
// Match /firm-portal exactly + any sub-paths. /firm-sign/* must NOT route to portal.
const isFirmPortal = !isFirmSign && (path.startsWith("/firm-portal") || path === "/firm" || path.startsWith("/firm/"));

const root = ReactDOM.createRoot(document.getElementById("root"), {
  onUncaughtError: Sentry.reactErrorHandler(),
  onCaughtError: Sentry.reactErrorHandler(),
  onRecoverableError: Sentry.reactErrorHandler(),
});
root.render(
  <React.StrictMode>
    {isFirmSign ? <FirmSign /> : isFirmPortal ? <FirmPortal /> : <App />}
  </React.StrictMode>,
);

// expose for legacy module imports (keeps tree-shaking happy)
export { setSentryUser };
