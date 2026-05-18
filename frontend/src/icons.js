// Custom Heraldic SVG Icons for AI Advocate (Option 3 — no box backgrounds)
import React from "react";

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export const AskLexIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M14 24 Q14 14 24 14 H40 Q50 14 50 24 V36 Q50 44 42 44 H30 L22 50 V44 Q14 44 14 36 Z"/>
    <line x1="22" y1="26" x2="42" y2="26"/>
    <line x1="22" y1="32" x2="38" y2="32"/>
  </svg>
);

export const RecordIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="26" y="10" width="12" height="26" rx="6"/>
    <path d="M20 30 Q20 42 32 42 Q44 42 44 30"/>
    <line x1="32" y1="42" x2="32" y2="52"/>
    <line x1="24" y1="52" x2="40" y2="52"/>
    <circle cx="32" cy="20" r="1" fill="currentColor"/>
  </svg>
);

export const CameraIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="8" y="20" width="48" height="32" rx="3"/>
    <path d="M22 20 L26 14 H38 L42 20"/>
    <circle cx="32" cy="36" r="9"/>
    <circle cx="32" cy="36" r="4"/>
    <rect x="46" y="24" width="6" height="3" rx="1"/>
  </svg>
);

export const LawyerIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M10 20 L32 8 L54 20"/>
    <line x1="10" y1="20" x2="54" y2="20"/>
    <line x1="14" y1="24" x2="14" y2="46"/>
    <line x1="24" y1="24" x2="24" y2="46"/>
    <line x1="40" y1="24" x2="40" y2="46"/>
    <line x1="50" y1="24" x2="50" y2="46"/>
    <line x1="8" y1="50" x2="56" y2="50"/>
    <line x1="6" y1="54" x2="58" y2="54"/>
  </svg>
);

export const FilesIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="12" y="8" width="40" height="48" rx="2"/>
    <line x1="20" y1="8" x2="20" y2="56"/>
    <line x1="26" y1="18" x2="46" y2="18"/>
    <line x1="26" y1="26" x2="46" y2="26"/>
    <line x1="26" y1="34" x2="42" y2="34"/>
    <path d="M26 44 L36 44 L36 50 L31 47 L26 50 Z"/>
  </svg>
);

export const LetterIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M14 14 Q14 10 18 10 H46 Q50 10 50 14 V50 Q50 54 46 54 H18 Q14 54 14 50 Z"/>
    <line x1="22" y1="22" x2="42" y2="22"/>
    <line x1="22" y1="30" x2="42" y2="30"/>
    <line x1="22" y1="38" x2="38" y2="38"/>
    <path d="M48 6 L60 18 L52 22 L46 16 Z"/>
    <line x1="40" y1="30" x2="50" y2="20"/>
  </svg>
);

export const CourtIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <line x1="32" y1="10" x2="32" y2="54"/>
    <circle cx="32" cy="8" r="2.5"/>
    <line x1="14" y1="18" x2="50" y2="18"/>
    <line x1="14" y1="18" x2="8" y2="32"/>
    <line x1="14" y1="18" x2="20" y2="32"/>
    <path d="M6 32 Q6 36 14 36 Q22 36 22 32"/>
    <line x1="50" y1="18" x2="44" y2="32"/>
    <line x1="50" y1="18" x2="56" y2="32"/>
    <path d="M42 32 Q42 36 50 36 Q58 36 58 32"/>
    <line x1="22" y1="54" x2="42" y2="54"/>
    <rect x="28" y="50" width="8" height="4"/>
  </svg>
);

export const ImmigrationIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <circle cx="32" cy="32" r="22"/>
    <ellipse cx="32" cy="32" rx="10" ry="22"/>
    <line x1="10" y1="32" x2="54" y2="32"/>
    <line x1="32" y1="10" x2="32" y2="54"/>
    <path d="M44 18 L50 12 L52 14 L46 20" strokeWidth="2"/>
  </svg>
);

export const EmploymentIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <rect x="8" y="20" width="48" height="34" rx="3"/>
    <path d="M22 20 V14 Q22 10 26 10 H38 Q42 10 42 14 V20"/>
    <line x1="8" y1="34" x2="56" y2="34"/>
    <rect x="28" y="32" width="8" height="6" rx="1"/>
  </svg>
);

export const PropertyIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M8 28 L32 10 L56 28"/>
    <line x1="14" y1="28" x2="14" y2="54"/>
    <line x1="50" y1="28" x2="50" y2="54"/>
    <line x1="22" y1="34" x2="22" y2="54"/>
    <line x1="42" y1="34" x2="42" y2="54"/>
    <line x1="10" y1="54" x2="54" y2="54"/>
    <rect x="28" y="40" width="8" height="14"/>
  </svg>
);

export const MedicalIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <line x1="32" y1="10" x2="32" y2="54"/>
    <path d="M32 14 Q24 18 24 24 Q24 30 32 32 Q40 34 40 40 Q40 46 32 50"/>
    <path d="M32 14 Q40 18 40 24 Q40 30 32 32 Q24 34 24 40 Q24 46 32 50"/>
    <path d="M28 12 Q32 8 36 12 L34 16 H30 Z"/>
  </svg>
);


// ---------- Round 2 icons ----------

// OutcomeIcon — scales of justice + percent (Predict Outcome)
export const OutcomeIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <circle cx="32" cy="32" r="20"/>
    <path d="M22 38 L28 32 L34 36 L44 24"/>
    <path d="M40 24 H44 V28"/>
    <text x="32" y="20" textAnchor="middle" fontSize="10" fontWeight="700"
          stroke="none" fill="currentColor" fontFamily="sans-serif">%</text>
  </svg>
);

// CostIcon — wallet with £ (Lawyer Cost)
export const CostIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M12 22 H52 V48 H12 Z"/>
    <path d="M12 22 L18 16 H44 L52 22"/>
    <circle cx="44" cy="35" r="2.5" fill="currentColor"/>
    <text x="26" y="40" textAnchor="middle" fontSize="14" fontWeight="700"
          stroke="none" fill="currentColor" fontFamily="serif">£</text>
  </svg>
);

// ContractIcon — document with checkmark seal (Contract Reader)
export const ContractIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M16 10 H38 L48 20 V54 H16 Z"/>
    <path d="M38 10 V20 H48"/>
    <line x1="22" y1="30" x2="42" y2="30"/>
    <line x1="22" y1="36" x2="42" y2="36"/>
    <line x1="22" y1="42" x2="34" y2="42"/>
    <circle cx="46" cy="46" r="7"/>
    <path d="M43 46 L45.5 48.5 L49 44"/>
  </svg>
);

// DraftIcon — quill writing on paper (Contract Drafter)
export const DraftIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M14 14 H40 V46 H14 Z"/>
    <line x1="20" y1="22" x2="34" y2="22"/>
    <line x1="20" y1="28" x2="34" y2="28"/>
    <line x1="20" y1="34" x2="28" y2="34"/>
    <path d="M44 18 L52 26 L36 42 L28 44 L30 36 Z"/>
    <line x1="44" y1="18" x2="50" y2="12"/>
  </svg>
);

// HearingIcon — podium / lectern mic (Hearing Recorder)
export const HearingIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <line x1="32" y1="14" x2="32" y2="22"/>
    <rect x="28" y="22" width="8" height="14" rx="4"/>
    <path d="M22 30 Q22 38 32 38 Q42 38 42 30"/>
    <line x1="32" y1="38" x2="32" y2="46"/>
    <path d="M20 54 L26 46 H38 L44 54 Z"/>
    <line x1="14" y1="20" x2="18" y2="22"/>
    <line x1="46" y1="22" x2="50" y2="20"/>
  </svg>
);

// AidIcon — government-style crowned shield with scales (Legal Aid)
// Original art evoking the UK Legal Aid Agency / MoJ visual language
// without copying the actual trademarked logo.
export const AidIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    {/* small crown at the top */}
    <path d="M24 14 L26 10 L29 14 L32 9 L35 14 L38 10 L40 14 L40 18 H24 Z"/>
    <line x1="24" y1="14" x2="40" y2="14"/>
    {/* shield outline */}
    <path d="M16 20 H48 V36 Q48 50 32 56 Q16 50 16 36 Z"/>
    {/* scales of justice inside the shield */}
    <line x1="32" y1="26" x2="32" y2="44"/>
    <line x1="22" y1="30" x2="42" y2="30"/>
    <path d="M22 30 L19 38 H25 Z"/>
    <path d="M42 30 L39 38 H45 Z"/>
  </svg>
);

// ReminderIcon — calendar with a small bell badge (Reminders)
export const ReminderIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    {/* calendar body */}
    <rect x="12" y="16" width="36" height="34" rx="3"/>
    <line x1="12" y1="24" x2="48" y2="24"/>
    {/* hangers */}
    <line x1="20" y1="12" x2="20" y2="20"/>
    <line x1="40" y1="12" x2="40" y2="20"/>
    {/* date dot grid */}
    <circle cx="22" cy="32" r="1.4" fill="currentColor"/>
    <circle cx="30" cy="32" r="1.4" fill="currentColor"/>
    <circle cx="22" cy="40" r="1.4" fill="currentColor"/>
    <circle cx="30" cy="40" r="1.4" fill="currentColor"/>
    {/* bell badge top-right */}
    <circle cx="50" cy="20" r="9" fill="#000" stroke="currentColor"/>
    <path d="M47 18 V16 Q47 13 50 13 Q53 13 53 16 V18"/>
    <path d="M45 22 H55"/>
    <path d="M49 24 Q50 25 51 24"/>
  </svg>
);

// VaultIcon — heraldic shield with a keyhole (encrypted vault)
export const VaultIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    {/* shield outline */}
    <path d="M32 6 L52 12 V32 Q52 46 32 58 Q12 46 12 32 V12 Z"/>
    {/* inner shield band (gold inset) */}
    <path d="M32 12 L46 16 V32 Q46 42 32 51 Q18 42 18 32 V16 Z"/>
    {/* keyhole */}
    <circle cx="32" cy="28" r="3.5" fill="currentColor"/>
    <rect x="30.5" y="29" width="3" height="9" fill="currentColor"/>
    {/* lock plate detail */}
    <line x1="26" y1="44" x2="38" y2="44"/>
  </svg>
);

// SuggestIcon — lightbulb (feature suggestion)
export const SuggestIcon = ({ size = 22 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" {...base}>
    <path d="M9 18h6"/>
    <path d="M10 22h4"/>
    <path d="M8 14a5 5 0 1 1 8 0c-.6.8-1 1.5-1 3v1H9v-1c0-1.5-.4-2.2-1-3z"/>
  </svg>
);

// HandshakeIcon — two hands clasping (matches stroke-only heraldic style)
export const HandshakeIcon = ({ size = 44 }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" {...base}>
    <path d="M6 30 L14 22 H26 L32 28 L26 34 L20 28"/>
    <path d="M32 28 L38 22 H50 L58 30 V42 L50 50 H42 L36 44"/>
    <path d="M20 28 L14 34 V42 L22 50 H30 L36 44"/>
    <line x1="32" y1="36" x2="38" y2="42"/>
    <line x1="28" y1="40" x2="34" y2="46"/>
  </svg>
);


