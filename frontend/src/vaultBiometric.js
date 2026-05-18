// Biometric Vault unlock via WebAuthn platform authenticator
// (Face ID / Touch ID / Windows Hello / Android biometric).
//
// Threat model:
// - Strong vs casual snoopers with device access: the biometric prompt MUST
//   succeed before we will reveal the encrypted PIN.
// - The encrypted PIN lives in localStorage. The encryption key is derived
//   from the credential's rawId (public). This means a full localStorage
//   exfiltration is theoretically defeatable, but on real iOS/Android the
//   WebView storage is sandboxed per-origin and protected by device unlock.
// - For "bank-grade" security on native iOS/Android, this same UX will
//   later be backed by Keychain/Keystore once we wrap with Capacitor — at
//   which point we'll swap the localStorage backing for SecureStore plugin.

const LS_KEY = "aa_vault_bio_v1";

const b64Encode = (buf) => {
  const bytes = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return btoa(s);
};
const b64Decode = (str) => {
  const bin = atob(str);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
};

export const isBiometricSupported = async () => {
  if (!window.PublicKeyCredential) return false;
  if (!window.isSecureContext) return false;
  try {
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  } catch { return false; }
};

export const isBiometricEnabled = () => {
  try { return !!localStorage.getItem(LS_KEY); } catch { return false; }
};

const deriveWrapperKey = async (rawIdBytes) => {
  const digest = await crypto.subtle.digest("SHA-256", rawIdBytes);
  return crypto.subtle.importKey(
    "raw", digest, { name: "AES-GCM" }, false, ["encrypt", "decrypt"]
  );
};

export const enableBiometric = async (pin, userId = "vault-user") => {
  if (!pin) throw new Error("PIN required");
  const supported = await isBiometricSupported();
  if (!supported) throw new Error("Biometric not supported on this device");

  const challenge = crypto.getRandomValues(new Uint8Array(32));
  const userIdBytes = new TextEncoder().encode(userId);
  let cred;
  try {
    cred = await navigator.credentials.create({
      publicKey: {
        challenge,
        rp: { name: "AI Advocate" },
        user: { id: userIdBytes, name: "vault", displayName: "Vault" },
        pubKeyCredParams: [
          { type: "public-key", alg: -7 },    // ES256
          { type: "public-key", alg: -257 },  // RS256
        ],
        authenticatorSelection: {
          authenticatorAttachment: "platform",
          userVerification: "required",
          residentKey: "preferred",
        },
        timeout: 60000,
        attestation: "none",
      },
    });
  } catch (e) {
    throw new Error(e?.message || "Biometric setup was cancelled");
  }
  if (!cred) throw new Error("No credential returned");

  const rawId = new Uint8Array(cred.rawId);
  const key = await deriveWrapperKey(rawId);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const cipher = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv }, key, new TextEncoder().encode(pin)
  );
  const record = {
    credentialId: b64Encode(rawId.buffer),
    cipher: b64Encode(cipher),
    iv: b64Encode(iv.buffer),
    createdAt: new Date().toISOString(),
  };
  localStorage.setItem(LS_KEY, JSON.stringify(record));
  return true;
};

export const unlockWithBiometric = async () => {
  const raw = localStorage.getItem(LS_KEY);
  if (!raw) throw new Error("Biometric not enabled on this device");
  const record = JSON.parse(raw);
  const credIdBytes = b64Decode(record.credentialId);

  const challenge = crypto.getRandomValues(new Uint8Array(32));
  let assertion;
  try {
    assertion = await navigator.credentials.get({
      publicKey: {
        challenge,
        allowCredentials: [{ type: "public-key", id: credIdBytes.buffer }],
        userVerification: "required",
        timeout: 60000,
      },
    });
  } catch (e) {
    throw new Error(e?.message || "Biometric authentication was cancelled");
  }
  if (!assertion) throw new Error("Biometric prompt failed");

  // Biometric matched — derive same wrapper key and decrypt the PIN.
  const key = await deriveWrapperKey(credIdBytes);
  const iv = b64Decode(record.iv);
  const cipher = b64Decode(record.cipher);
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, cipher);
  return new TextDecoder().decode(plain);
};

export const disableBiometric = () => {
  try { localStorage.removeItem(LS_KEY); } catch (_) {}
};
