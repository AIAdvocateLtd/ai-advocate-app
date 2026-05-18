// Recording-legality reference data for AI Advocate's recording features.
// Used by RecordingConsentGate to show country-aware warnings before any
// audio/video recording starts.
//
// NOTE: this is INFORMATION, not legal advice. Laws change. Every screen
// using this MUST also display a disclaimer linking to the Terms of Service.

// Country code → human-readable warnings.
// "consent" — what kind of consent is needed for the recorder to capture audio of others
// "court" — the rule about courts/tribunals
// "ok" — what is generally fine to record
// "danger" — examples that are illegal or risky
export const RECORDING_LAW = {
  GB: {
    flag: "🇬🇧",
    countryName: "United Kingdom",
    consent: "One-party consent — you can record a conversation you are part of, but you should ideally inform the other person.",
    court: "Recording in any court is a CRIMINAL OFFENCE under Section 9 of the Contempt of Court Act 1981 (up to 2 years prison + unlimited fine). This includes phone recording, photography and sketching.",
    ok: ["Employment tribunals (with the judge's permission)", "Disciplinary / grievance hearings at work", "Conversations you are part of", "Meetings on private property where you have consent"],
    danger: ["Any court — Magistrates, Crown, Family, Civil", "Police custody interviews (use PACE recording)", "Recording someone without their knowledge to use commercially"],
  },
  IE: {
    flag: "🇮🇪",
    countryName: "Ireland",
    consent: "One-party consent — you can record a conversation you are part of.",
    court: "Recording in court is an offence under the Courts of Justice Act 1924 s.91 (as amended) and Court Service rules. The judge will hold you in contempt of court.",
    ok: ["Workplace Relations Commission hearings (with consent)", "Conversations you are part of"],
    danger: ["All courts and tribunals where the judge has not consented", "Wiretap of others' calls"],
  },
  US: {
    flag: "🇺🇸",
    countryName: "United States",
    consent: "Federal law: one-party consent. BUT 12 states (California, Florida, Connecticut, Delaware, Illinois, Maryland, Massachusetts, Michigan, Montana, New Hampshire, Pennsylvania, Washington) require TWO-PARTY (all-party) consent — recording without is a criminal offence.",
    court: "Recording in federal court is generally banned (Fed. R. Crim. P. 53). Most state courts also ban it. ALWAYS ask the court clerk first.",
    ok: ["Conversations you're part of in one-party states", "Recordings with all-party consent in two-party states"],
    danger: ["Federal courts (Fed. R. Crim. P. 53)", "Recording calls in two-party states without consent", "Police body-cam areas in some states"],
  },
  CA: {
    flag: "🇨🇦",
    countryName: "Canada",
    consent: "One-party consent under s. 184(2) Criminal Code.",
    court: "Recording inside a Canadian courtroom without judicial authorisation is contempt of court. Most provinces also prohibit it by statute.",
    ok: ["Conversations you're a party to", "Tribunal hearings where the chair permits it"],
    danger: ["All courts without explicit permission"],
  },
  AU: {
    flag: "🇦🇺",
    countryName: "Australia",
    consent: "Varies by state. NSW, VIC, WA require two-party consent (Listening Devices Acts). QLD, NT, SA, TAS allow one-party.",
    court: "Recording in any Australian court is a criminal offence — penalties under state Court Suppression and Non-Publication legislation.",
    ok: ["Tribunals (e.g. Fair Work Commission) with leave of the member", "Conversations you're a party to (in one-party-consent states)"],
    danger: ["All courts", "Two-party states (NSW/VIC/WA) without all parties' consent"],
  },
  FR: {
    flag: "🇫🇷",
    countryName: "France",
    consent: "Two-party (all-party) consent required for any recording of a private conversation — Article 226-1 Code pénal. Penalty: 1 year prison + €45,000 fine.",
    court: "Recording in any French court is banned under Article 38 ter Law of 29 July 1881. Penalty: 4,500 € fine.",
    ok: ["With explicit consent of all parties"],
    danger: ["Hidden / non-consensual recording — criminal offence"],
  },
  DE: {
    flag: "🇩🇪",
    countryName: "Germany",
    consent: "Two-party consent. §201 StGB makes it a criminal offence to record a non-public spoken word of another without consent. Up to 3 years prison.",
    court: "§169 GVG bans recording in court (audio + image). Judges enforce strictly.",
    ok: ["With explicit consent of all parties", "Voice memos of yourself"],
    danger: ["Hidden recording of others — criminal", "All courts"],
  },
  PK: {
    flag: "🇵🇰",
    countryName: "Pakistan",
    consent: "One-party consent in practice, though the Telegraph Act 1885 and Investigation for Fair Trial Act 2013 govern lawful interception.",
    court: "Recording in court (any level) is contempt of court under the Contempt of Court Ordinance 2003.",
    ok: ["Conversations you're part of (not for commercial release without consent)"],
    danger: ["All courts and tribunals without leave"],
  },
  IN: {
    flag: "🇮🇳",
    countryName: "India",
    consent: "One-party consent generally permitted. Sharing publicly requires consent under IT Act 2000 + IPC.",
    court: "Recording in any court is contempt under the Contempt of Courts Act 1971 (max 6 months prison or ₹2,000 fine).",
    ok: ["Conversations you're a party to (for personal use)"],
    danger: ["All courts and tribunals without judge's leave", "Sharing recordings of others without consent"],
  },
};

export const lawFor = (countryCode) => {
  return RECORDING_LAW[countryCode] || RECORDING_LAW.GB;
};

// ------- Court proximity data --------------------------------------------
// Selection of UK + key international court/tribunal locations for the
// "smart safety alert" feature. Coordinates are PUBLIC court addresses.
// On-device only — no network call required for distance check.

export const KNOWN_COURTS = [
  // ===== UK — England & Wales =====
  { n: "Royal Courts of Justice (London)", lat: 51.5142, lng: -0.1133, c: "GB" },
  { n: "The Supreme Court (London)", lat: 51.5004, lng: -0.1276, c: "GB" },
  { n: "Old Bailey (Central Criminal Court)", lat: 51.5159, lng: -0.1017, c: "GB" },
  { n: "Westminster Magistrates' Court", lat: 51.5219, lng: -0.1670, c: "GB" },
  { n: "Southwark Crown Court", lat: 51.5050, lng: -0.0790, c: "GB" },
  { n: "Wood Green Crown Court", lat: 51.5957, lng: -0.1093, c: "GB" },
  { n: "Snaresbrook Crown Court", lat: 51.5854, lng: 0.0204, c: "GB" },
  { n: "Inner London Crown Court", lat: 51.4926, lng: -0.0985, c: "GB" },
  { n: "Family Court (Holborn)", lat: 51.5176, lng: -0.1192, c: "GB" },
  { n: "Central London Employment Tribunal", lat: 51.5151, lng: -0.1311, c: "GB" },
  { n: "Manchester Crown Court", lat: 53.4778, lng: -2.2451, c: "GB" },
  { n: "Manchester Civil Justice Centre", lat: 53.4790, lng: -2.2541, c: "GB" },
  { n: "Birmingham Crown Court", lat: 52.4783, lng: -1.8989, c: "GB" },
  { n: "Birmingham Civil Justice Centre", lat: 52.4773, lng: -1.9011, c: "GB" },
  { n: "Leeds Crown Court", lat: 53.7976, lng: -1.5448, c: "GB" },
  { n: "Liverpool Crown Court", lat: 53.4087, lng: -2.9928, c: "GB" },
  { n: "Sheffield Crown Court", lat: 53.3850, lng: -1.4685, c: "GB" },
  { n: "Cardiff Crown Court", lat: 51.4790, lng: -3.1819, c: "GB" },
  { n: "Bristol Crown Court", lat: 51.4536, lng: -2.5950, c: "GB" },
  { n: "Newcastle Crown Court", lat: 54.9683, lng: -1.6080, c: "GB" },
  { n: "Nottingham Crown Court", lat: 52.9520, lng: -1.1486, c: "GB" },
  // ===== UK — Scotland =====
  { n: "High Court of Justiciary (Edinburgh)", lat: 55.9491, lng: -3.1907, c: "GB" },
  { n: "Court of Session (Edinburgh)", lat: 55.9495, lng: -3.1907, c: "GB" },
  { n: "Glasgow Sheriff Court", lat: 55.8579, lng: -4.2588, c: "GB" },
  // ===== Ireland =====
  { n: "Four Courts (Dublin)", lat: 53.3461, lng: -6.2731, c: "IE" },
  { n: "Criminal Courts of Justice (Dublin)", lat: 53.3458, lng: -6.2887, c: "IE" },
  // ===== US — federal & supreme =====
  { n: "Supreme Court of the United States", lat: 38.8906, lng: -77.0044, c: "US" },
  { n: "U.S. District Court SDNY (Manhattan)", lat: 40.7137, lng: -74.0027, c: "US" },
  { n: "U.S. District Court CDCA (Los Angeles)", lat: 34.0533, lng: -118.2620, c: "US" },
  // ===== Canada =====
  { n: "Supreme Court of Canada (Ottawa)", lat: 45.4220, lng: -75.7028, c: "CA" },
  { n: "Ontario Superior Court (Toronto)", lat: 43.6505, lng: -79.3886, c: "CA" },
  // ===== Australia =====
  { n: "High Court of Australia (Canberra)", lat: -35.2992, lng: 149.1369, c: "AU" },
  { n: "Sydney Federal Court", lat: -33.8696, lng: 151.2104, c: "AU" },
  // ===== France / Germany — selected =====
  { n: "Palais de Justice (Paris)", lat: 48.8556, lng: 2.3454, c: "FR" },
  { n: "Bundesgerichtshof (Karlsruhe)", lat: 48.9952, lng: 8.3973, c: "DE" },
  // ===== Pakistan / India — selected =====
  { n: "Supreme Court of Pakistan (Islamabad)", lat: 33.7222, lng: 73.0902, c: "PK" },
  { n: "Supreme Court of India (New Delhi)", lat: 28.6219, lng: 77.2378, c: "IN" },
];

// Haversine distance in metres
export const haversineMeters = (a, b) => {
  const R = 6_371_000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
};

// Returns { court, distance_m } if the user is within `maxMeters` of any
// known court — otherwise null. ALL on-device, no network.
export const nearestCourtWithin = (userLat, userLng, maxMeters = 150) => {
  const me = { lat: userLat, lng: userLng };
  let best = null;
  for (const c of KNOWN_COURTS) {
    const d = haversineMeters(me, { lat: c.lat, lng: c.lng });
    if (d <= maxMeters && (!best || d < best.distance_m)) {
      best = { court: c, distance_m: Math.round(d) };
    }
  }
  return best;
};

// Try to obtain a one-shot location (only when the user taps Record).
// Returns Promise<{lat,lng} | null>. Never throws.
export const tryGetLocationOnce = () =>
  new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    let done = false;
    const onSuccess = (p) => { if (!done) { done = true; resolve({ lat: p.coords.latitude, lng: p.coords.longitude }); } };
    const onError = () => { if (!done) { done = true; resolve(null); } };
    try {
      navigator.geolocation.getCurrentPosition(onSuccess, onError, { enableHighAccuracy: false, timeout: 4000, maximumAge: 60000 });
    } catch { resolve(null); }
    setTimeout(() => { if (!done) { done = true; resolve(null); } }, 4500);
  });

// Suspicious words in a recording title that suggest court usage.
export const COURT_KEYWORDS = ["court", "judge", "magistrate", "crown", "old bailey", "sheriff", "high court", "supreme court"];

export const containsCourtKeyword = (title) => {
  const t = (title || "").toLowerCase();
  return COURT_KEYWORDS.some((k) => t.includes(k));
};
