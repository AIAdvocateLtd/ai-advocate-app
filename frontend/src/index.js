import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import FirmPortal from "@/FirmPortal";

const path = window.location.pathname || "";
const isFirmPortal = path.startsWith("/firm-portal") || path.startsWith("/firm");

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    {isFirmPortal ? <FirmPortal /> : <App />}
  </React.StrictMode>,
);
