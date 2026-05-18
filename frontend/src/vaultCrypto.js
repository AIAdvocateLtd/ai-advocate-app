// Client-side Vault encryption helper using Web Crypto API.
// - PIN → PBKDF2 (250k iterations, SHA-256) → 256-bit AES-GCM key
// - PIN verifier sent to server: SHA-256(PIN || salt) hex — server can't recover PIN
// - Files encrypted with AES-GCM (12-byte random IV per item)
// - Returns base64-encoded ciphertext for transport

const enc = new TextEncoder();
const dec = new TextDecoder();

const b64 = {
  encode: (buf) => {
    const bytes = new Uint8Array(buf);
    let s = "";
    for (let i = 0; i < bytes.length; i += 0x8000) {
      s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    }
    return btoa(s);
  },
  decode: (str) => {
    const bin = atob(str);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out.buffer;
  },
};

const hex = {
  encode: (buf) => Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join(""),
};

export const generateSalt = () => {
  const s = crypto.getRandomValues(new Uint8Array(16));
  return b64.encode(s.buffer);
};

const deriveKey = async (pin, saltB64) => {
  const salt = b64.decode(saltB64);
  const baseKey = await crypto.subtle.importKey(
    "raw", enc.encode(pin), { name: "PBKDF2" }, false, ["deriveKey", "deriveBits"]
  );
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: 250000, hash: "SHA-256" },
    baseKey,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
};

// SHA-256(PIN || salt-bytes) hex — for server-side verifier (does NOT reveal PIN)
export const pinVerifier = async (pin, saltB64) => {
  const salt = new Uint8Array(b64.decode(saltB64));
  const pinBytes = enc.encode(pin);
  const merged = new Uint8Array(pinBytes.length + salt.length);
  merged.set(pinBytes, 0);
  merged.set(salt, pinBytes.length);
  const digest = await crypto.subtle.digest("SHA-256", merged);
  return hex.encode(digest);
};

export const encryptBlob = async (pin, saltB64, blob) => {
  const key = await deriveKey(pin, saltB64);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const arr = await blob.arrayBuffer();
  const cipher = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, arr);
  return { file_b64: b64.encode(cipher), file_iv: b64.encode(iv.buffer) };
};

export const decryptBlob = async (pin, saltB64, cipherB64, ivB64, mime = "application/octet-stream") => {
  const key = await deriveKey(pin, saltB64);
  const iv = new Uint8Array(b64.decode(ivB64));
  const cipher = b64.decode(cipherB64);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, cipher);
  return new Blob([plain], { type: mime });
};

export const encryptText = async (pin, saltB64, text) => {
  if (!text) return { ct: null, iv: null };
  const key = await deriveKey(pin, saltB64);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const cipher = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(text));
  return { ct: b64.encode(cipher), iv: b64.encode(iv.buffer) };
};

export const decryptText = async (pin, saltB64, ctB64, ivB64) => {
  if (!ctB64) return "";
  try {
    const key = await deriveKey(pin, saltB64);
    const iv = new Uint8Array(b64.decode(ivB64));
    const cipher = b64.decode(ctB64);
    const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, cipher);
    return dec.decode(plain);
  } catch {
    return "[unable to decrypt]";
  }
};
