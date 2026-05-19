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

// SuggestIcon was a lightbulb (Settings → Suggest a feature) — keep small SVG, no PNG needed
export const SuggestIcon = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24"
       style={{ fill: "currentColor", stroke: "currentColor", strokeWidth: 1.3, strokeLinecap: "round", strokeLinejoin: "round" }}>
    <path d="M8 14a5 5 0 1 1 8 0c-.6.8-1 1.5-1 3v1H9v-1c0-1.5-.4-2.2-1-3z"/>
    <rect x="9" y="17.5" width="6" height="1.5" rx="0.4" style={{ fill: "#0a0a0a", stroke: "none" }}/>
    <rect x="10" y="20.5" width="4" height="1.5" rx="0.4"/>
  </svg>
);
