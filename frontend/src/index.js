// Sentry MUST be the first import — captures errors that happen before React mounts.
import "@/sentry";
import { setSentryUser } from "@/sentry"; // re-exported intentionally for downstream use
import React from "react";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";
import "@/index.css";
import App from "@/App";
import FirmPortal from "@/FirmPortal";

const path = window.location.pathname || "";
const isFirmPortal = path.startsWith("/firm-portal") || path.startsWith("/firm");

const root = ReactDOM.createRoot(document.getElementById("root"), {
  onUncaughtError: Sentry.reactErrorHandler(),
  onCaughtError: Sentry.reactErrorHandler(),
  onRecoverableError: Sentry.reactErrorHandler(),
});
root.render(
  <React.StrictMode>
    {isFirmPortal ? <FirmPortal /> : <App />}
  </React.StrictMode>,
);

// expose for legacy module imports (keeps tree-shaking happy)
export { setSentryUser };
