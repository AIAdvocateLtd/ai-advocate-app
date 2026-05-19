// Custom Heraldic SVG Icons for AI Advocate — Style B (Solid Filled Gold)
import React from "react";

// Style B base — filled gold with subtle stroke outline.
// Icons with internal cutouts use fill="#000" (or stroke-only via <line>) to carve the negative space.
const base = {
  fill: "currentColor",
  stroke: "currentColor",
  strokeWidth: 1.2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

// Helper for inner "cutout" detail lines that should be invisible on the gold fill
const cut = { stroke: "#0a0a0a", strokeWidth: 1.8, strokeLinecap: "round", fill: "none" };
const cutFill = { fill: "#0a0a0a", stroke: "none" };

export const AskLexIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M14 24 Q14 14 24 14 H40 Q50 14 50 24 V36 Q50 44 42 44 H30 L22 50 V44 Q14 44 14 36 Z"/>
    <line {...cut} x1="22" y1="26" x2="42" y2="26"/>
    <line {...cut} x1="22" y1="32" x2="38" y2="32"/>
  </svg>
);

export const RecordIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="26" y="10" width="12" height="26" rx="6"/>
    <path fill="none" d="M20 30 Q20 42 32 42 Q44 42 44 30" strokeWidth="2.5"/>
    <line x1="32" y1="42" x2="32" y2="52" strokeWidth="2.5"/>
    <line x1="24" y1="52" x2="40" y2="52" strokeWidth="2.5"/>
  </svg>
);

export const CameraIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="8" y="20" width="48" height="32" rx="3"/>
    <path d="M22 20 L26 14 H38 L42 20 Z"/>
    <circle {...cutFill} cx="32" cy="36" r="9"/>
    <circle cx="32" cy="36" r="5"/>
    <circle {...cutFill} cx="32" cy="36" r="2.5"/>
    <rect x="46" y="24" width="6" height="3" rx="1"/>
  </svg>
);

export const LawyerIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M10 20 L32 8 L54 20 Z"/>
    <rect x="6" y="50" width="52" height="6" rx="1"/>
    <rect x="12" y="22" width="6" height="26"/>
    <rect x="22" y="22" width="6" height="26"/>
    <rect x="36" y="22" width="6" height="26"/>
    <rect x="46" y="22" width="6" height="26"/>
  </svg>
);

export const FilesIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="12" y="8" width="40" height="48" rx="3"/>
    <rect {...cutFill} x="20" y="8" width="1.5" height="48"/>
    <line {...cut} x1="26" y1="20" x2="46" y2="20"/>
    <line {...cut} x1="26" y1="28" x2="46" y2="28"/>
    <line {...cut} x1="26" y1="36" x2="42" y2="36"/>
  </svg>
);

export const LetterIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M14 14 Q14 10 18 10 H46 Q50 10 50 14 V50 Q50 54 46 54 H18 Q14 54 14 50 Z"/>
    <line {...cut} x1="22" y1="22" x2="42" y2="22"/>
    <line {...cut} x1="22" y1="30" x2="42" y2="30"/>
    <line {...cut} x1="22" y1="38" x2="38" y2="38"/>
    <path d="M48 6 L60 18 L52 22 L46 16 Z"/>
  </svg>
);

export const CourtIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M8 20 L32 10 L56 20 Z"/>
    <rect x="14" y="22" width="6" height="22"/>
    <rect x="24" y="22" width="6" height="22"/>
    <rect x="34" y="22" width="6" height="22"/>
    <rect x="44" y="22" width="6" height="22"/>
    <rect x="6" y="46" width="52" height="6" rx="1"/>
  </svg>
);

export const ImmigrationIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <circle cx="32" cy="32" r="22"/>
    <ellipse {...cut} cx="32" cy="32" rx="10" ry="22"/>
    <line {...cut} x1="10" y1="32" x2="54" y2="32"/>
    <line {...cut} x1="32" y1="10" x2="32" y2="54"/>
  </svg>
);

export const EmploymentIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="8" y="22" width="48" height="32" rx="3"/>
    <path d="M22 22 V14 Q22 10 26 10 H38 Q42 10 42 14 V22 Z"/>
    <line {...cut} x1="8" y1="34" x2="56" y2="34"/>
    <rect {...cutFill} x="28" y="32" width="8" height="6" rx="1"/>
  </svg>
);

export const PropertyIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M8 30 L32 12 L56 30 V54 H8 Z"/>
    <rect {...cutFill} x="28" y="38" width="8" height="16"/>
    <rect {...cutFill} x="14" y="34" width="8" height="8" rx="1"/>
    <rect {...cutFill} x="42" y="34" width="8" height="8" rx="1"/>
  </svg>
);

export const MedicalIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="14" y="26" width="36" height="12" rx="2"/>
    <rect x="26" y="14" width="12" height="36" rx="2"/>
  </svg>
);

// OutcomeIcon — filled circle with check + percent
export const OutcomeIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <circle cx="32" cy="32" r="22"/>
    <path {...cut} strokeWidth="3" d="M22 36 L29 43 L44 28"/>
  </svg>
);

// CostIcon — wallet with £
export const CostIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M10 20 L18 14 H46 L54 20 V50 H10 Z"/>
    <circle {...cutFill} cx="44" cy="34" r="2.5"/>
    <text x="26" y="42" textAnchor="middle" fontSize="18" fontWeight="800"
          stroke="none" {...cutFill} fontFamily="serif">£</text>
  </svg>
);

// ContractIcon — document with check seal
export const ContractIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M14 10 H38 L50 22 V54 H14 Z"/>
    <path {...cutFill} d="M38 10 L50 22 H38 Z"/>
    <line {...cut} x1="20" y1="32" x2="42" y2="32"/>
    <line {...cut} x1="20" y1="38" x2="42" y2="38"/>
    <line {...cut} x1="20" y1="44" x2="34" y2="44"/>
  </svg>
);

// DraftIcon — paper + quill
export const DraftIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M12 12 H38 V46 H12 Z"/>
    <line {...cut} x1="18" y1="22" x2="32" y2="22"/>
    <line {...cut} x1="18" y1="28" x2="32" y2="28"/>
    <line {...cut} x1="18" y1="34" x2="28" y2="34"/>
    <path d="M44 16 L54 26 L34 46 L24 48 L26 38 Z"/>
  </svg>
);

// HearingIcon — podium + mic
export const HearingIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="26" y="10" width="12" height="22" rx="6"/>
    <path fill="none" strokeWidth="2.5" d="M20 28 Q20 38 32 38 Q44 38 44 28"/>
    <line strokeWidth="2.5" x1="32" y1="38" x2="32" y2="46"/>
    <path d="M18 54 L26 44 H38 L46 54 Z"/>
  </svg>
);

// AidIcon — crowned shield with scales
export const AidIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M24 14 L26 10 L29 14 L32 9 L35 14 L38 10 L40 14 L40 18 H24 Z"/>
    <path d="M16 20 H48 V36 Q48 50 32 56 Q16 50 16 36 Z"/>
    <line {...cut} strokeWidth="2" x1="32" y1="26" x2="32" y2="44"/>
    <line {...cut} strokeWidth="2" x1="22" y1="30" x2="42" y2="30"/>
    <path {...cutFill} d="M20 30 L17 38 H23 Z"/>
    <path {...cutFill} d="M44 30 L41 38 H47 Z"/>
  </svg>
);

// ReminderIcon — calendar with bell badge
export const ReminderIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="10" y="16" width="40" height="36" rx="3"/>
    <rect {...cutFill} x="10" y="22" width="40" height="2"/>
    <rect x="18" y="10" width="3" height="10" rx="1"/>
    <rect x="39" y="10" width="3" height="10" rx="1"/>
    <circle {...cutFill} cx="22" cy="32" r="2"/>
    <circle {...cutFill} cx="30" cy="32" r="2"/>
    <circle {...cutFill} cx="22" cy="40" r="2"/>
    <circle {...cutFill} cx="30" cy="40" r="2"/>
    {/* bell badge */}
    <circle fill="#cf2222" stroke="#0a0a0a" strokeWidth="1.5" cx="50" cy="20" r="9"/>
    <path stroke="#fff" strokeWidth="1.6" fill="none" d="M47 18 V16 Q47 13 50 13 Q53 13 53 16 V18 M45 22 H55"/>
  </svg>
);

// VaultIcon — solid heraldic shield with keyhole cutout
export const VaultIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M32 6 L52 12 V32 Q52 46 32 58 Q12 46 12 32 V12 Z"/>
    <path {...cutFill} d="M32 12 L46 16 V32 Q46 42 32 51 Q18 42 18 32 V16 Z"/>
    <path d="M32 16 L42 19 V32 Q42 40 32 47 Q22 40 22 32 V19 Z"/>
    {/* keyhole cut */}
    <circle {...cutFill} cx="32" cy="28" r="3.5"/>
    <rect {...cutFill} x="30.5" y="29" width="3" height="9"/>
  </svg>
);

// SuggestIcon — lightbulb
export const SuggestIcon = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
    <path d="M8 14a5 5 0 1 1 8 0c-.6.8-1 1.5-1 3v1H9v-1c0-1.5-.4-2.2-1-3z"/>
    <rect x="9" y="17.5" width="6" height="1.5" rx="0.4" {...cutFill}/>
    <rect x="10" y="20.5" width="4" height="1.5" rx="0.4"/>
  </svg>
);

// HandshakeIcon — two hands clasping (Style B filled)
export const HandshakeIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M4 28 L14 18 H28 L34 26 L26 36 L18 28 Z"/>
    <path d="M30 26 L38 18 H52 L60 28 V42 L50 52 H42 L34 44 Z"/>
    <line {...cut} strokeWidth="1.6" x1="22" y1="32" x2="28" y2="38"/>
    <line {...cut} strokeWidth="1.6" x1="26" y1="36" x2="32" y2="42"/>
  </svg>
);
