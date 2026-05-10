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
