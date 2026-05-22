// AI Advocate icon set — Style D (Embossed 3D Gold, photorealistic Nano Banana renders)
// Replaces the previous SVG implementations with PNG images served from /icons/*.png
// Each icon component preserves the API: <Icon size={44} />
import React from "react";

// Tweak per-icon size offset if needed (some icons look better slightly larger/smaller)
const ICON_SIZE_SCALE = 1.0;

const make = (file, label) => {
  const Comp = ({ size = 44, alt = label }) => (
    <img
      src={`/icons/${file}`}
      alt={alt}
      width={size * ICON_SIZE_SCALE}
      height={size * ICON_SIZE_SCALE}
      loading="eager"
      decoding="async"
      fetchpriority="high"
      style={{
        display: "inline-block",
        objectFit: "contain",
        // Keep "gold" colour even when the tile applies a CSS color tint
        // (img can't be re-coloured, so we let the PNG carry the colour fully)
        filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.5))",
        userSelect: "none",
        pointerEvents: "none",
        // Background is transparent in the optimized PNGs — never paint a box
        background: "transparent",
      }}
      draggable={false}
    />
  );
  Comp.displayName = label;
  return Comp;
};

// --- Dashboard tile icons ---
export const AskLexIcon       = make("ask_lex.png",     "Ask Lex");
export const RecordIcon       = make("record.png",      "Record");
export const CameraIcon       = make("camera.png",      "Camera");
export const LawyerIcon       = make("lawyer.png",      "Lawyer");
export const FilesIcon        = make("files.png",       "Files");
export const LetterIcon       = make("letter.png",      "Letter");
export const CourtIcon        = make("court.png",       "Court");
export const ContractIcon     = make("contract.png",    "Contract");
export const DraftIcon        = make("draft.png",       "Draft");
export const HearingIcon      = make("hearing.png",     "Hearing");
export const AidIcon          = make("aid.png",         "Legal Aid");
export const ReminderIcon     = make("reminder.png",    "Reminder");
export const VaultIcon        = make("vault.png",       "Vault");
export const HandshakeIcon    = make("solicitor.png",   "My Solicitor");
export const ImmigrationIcon  = make("immigration.png", "Immigration");
export const EmploymentIcon   = make("employment.png",  "Employment");
export const PropertyIcon     = make("property.png",    "Property");
export const MedicalIcon      = make("medical.png",     "Medical");
export const OutcomeIcon      = make("outcome.png",     "Outcome");
export const CostIcon         = make("cost.png",        "Cost");

// 🗑 Recycle Bin — inline SVG matched to the embossed-gold tile aesthetic.
// We don't have a PNG render yet, so we hand-craft the same gold gradient + drop-shadow
// the other tiles use, so it sits naturally next to them in the dashboard grid.
export const RecycleIcon = ({ size = 44, alt = "Recycle Bin" }) => (
  <svg
    width={size * ICON_SIZE_SCALE}
    height={size * ICON_SIZE_SCALE}
    viewBox="0 0 64 64"
    role="img"
    aria-label={alt}
    style={{
      display: "inline-block",
      filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.5))",
      userSelect: "none",
      pointerEvents: "none",
    }}
  >
    <defs>
      <linearGradient id="aaRecycleGold" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"   stopColor="#fde68a" />
        <stop offset="35%"  stopColor="#f7c948" />
        <stop offset="60%"  stopColor="#c89324" />
        <stop offset="100%" stopColor="#7a5a12" />
      </linearGradient>
      <linearGradient id="aaRecycleRim" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"   stopColor="#fff3c4" />
        <stop offset="50%"  stopColor="#f7c948" />
        <stop offset="100%" stopColor="#8a6612" />
      </linearGradient>
    </defs>
    {/* Lid */}
    <rect x="8" y="14" width="48" height="7" rx="2.5" fill="url(#aaRecycleRim)" stroke="#5a3f0a" strokeWidth="1.2" />
    {/* Handle */}
    <rect x="24" y="8" width="16" height="5" rx="2.2" fill="url(#aaRecycleRim)" stroke="#5a3f0a" strokeWidth="1.2" />
    {/* Body */}
    <path
      d="M12 22 L52 22 L48 56 Q47 60 43 60 L21 60 Q17 60 16 56 Z"
      fill="url(#aaRecycleGold)"
      stroke="#5a3f0a"
      strokeWidth="1.4"
    />
    {/* Vertical embossed lines */}
    <path d="M24 27 L23 55" stroke="#5a3f0a" strokeOpacity="0.55" strokeWidth="1.4" strokeLinecap="round" />
    <path d="M32 27 L32 55" stroke="#5a3f0a" strokeOpacity="0.55" strokeWidth="1.4" strokeLinecap="round" />
    <path d="M40 27 L41 55" stroke="#5a3f0a" strokeOpacity="0.55" strokeWidth="1.4" strokeLinecap="round" />
    {/* Top highlight */}
    <path d="M14 23 Q32 21 50 23" stroke="#fff7d6" strokeOpacity="0.6" strokeWidth="1" fill="none" />
  </svg>
);

// SuggestIcon was a lightbulb (Settings → Suggest a feature) — keep small SVG, no PNG needed
export const SuggestIcon = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24"
       style={{ fill: "currentColor", stroke: "currentColor", strokeWidth: 1.3, strokeLinecap: "round", strokeLinejoin: "round" }}>
    <path d="M8 14a5 5 0 1 1 8 0c-.6.8-1 1.5-1 3v1H9v-1c0-1.5-.4-2.2-1-3z"/>
    <rect x="9" y="17.5" width="6" height="1.5" rx="0.4" style={{ fill: "#0a0a0a", stroke: "none" }}/>
    <rect x="10" y="20.5" width="4" height="1.5" rx="0.4"/>
  </svg>
);
