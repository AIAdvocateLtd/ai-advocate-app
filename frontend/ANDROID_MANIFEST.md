# Android — AndroidManifest.xml Permissions

After `npx cap add android`, open `android/app/src/main/AndroidManifest.xml`
and add the entries below. Capacitor auto-generates a working manifest; you
just need to merge these `<uses-permission>` and `<queries>` blocks.

---

## Permissions

Insert just inside the top-level `<manifest>` tag, above `<application>`:

```xml
<!-- Location: SOS, Live Tracking, geolocated lawyer/embassy lookup. We use
     ACCESS_FINE_LOCATION (precise) and ACCESS_COARSE_LOCATION (for the
     "approximate" privacy toggle on Android 12+). -->
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />

<!-- Microphone: Encounter recordings, Hearing recorder, Lex voice mode -->
<uses-permission android:name="android.permission.RECORD_AUDIO" />

<!-- Camera: Snap Evidence, document scan -->
<uses-permission android:name="android.permission.CAMERA" />

<!-- Internet (already declared by Capacitor, but explicit is fine) -->
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

<!-- Biometric: Vault unlock with fingerprint / face -->
<uses-permission android:name="android.permission.USE_BIOMETRIC" />
<uses-permission android:name="android.permission.USE_FINGERPRINT" />

<!-- Vibrate: SOS haptics (handled by Capacitor Haptics plugin) -->
<uses-permission android:name="android.permission.VIBRATE" />

<!-- Storage (Android 9 and below) — Android 10+ uses scoped storage which doesn't need these -->
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
    android:maxSdkVersion="32" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"
    android:maxSdkVersion="29" />

<!-- Photo picker / media (Android 13+ replaces READ_EXTERNAL_STORAGE) -->
<uses-permission android:name="android.permission.READ_MEDIA_IMAGES" />
<uses-permission android:name="android.permission.READ_MEDIA_VIDEO" />
<uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />

<!-- Foreground service for extended SOS Live Tracking (only if you ever ship
     background tracking — leave commented out for first Play release) -->
<!--
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_BACKGROUND_LOCATION" />
-->

<!-- Required for the SMS intent fallback (sms:) to be visible to Android 11+
     when using PackageManager.queryIntentActivities() — Capacitor's Share
     plugin handles this internally, but we declare it for transparency. -->
<queries>
  <intent>
    <action android:name="android.intent.action.SENDTO" />
    <data android:scheme="smsto" />
  </intent>
  <intent>
    <action android:name="android.intent.action.SEND" />
  </intent>
  <intent>
    <action android:name="android.intent.action.VIEW" />
    <data android:scheme="tel" />
  </intent>
  <intent>
    <action android:name="android.intent.action.VIEW" />
    <data android:scheme="https" />
  </intent>
</queries>
```

---

## Hardware features (optional declarations for the Play Store filter)

Inside `<manifest>`, mark hardware features as non-required so users with
unusual devices (e.g. tablets without GPS) can still install:

```xml
<uses-feature android:name="android.hardware.location" android:required="false" />
<uses-feature android:name="android.hardware.location.gps" android:required="false" />
<uses-feature android:name="android.hardware.microphone" android:required="false" />
<uses-feature android:name="android.hardware.camera" android:required="false" />
<uses-feature android:name="android.hardware.fingerprint" android:required="false" />
```

---

## Application-level attributes

Capacitor generates the `<application>` tag for you. Two important attributes
to verify:

```xml
<application
    android:allowBackup="false"           <!-- prevent ADB backup of vault data -->
    android:dataExtractionRules="@xml/data_extraction_rules"
    android:fullBackupContent="false"
    android:icon="@mipmap/ic_launcher"
    android:label="@string/app_name"
    android:roundIcon="@mipmap/ic_launcher_round"
    android:supportsRtl="true"
    android:theme="@style/AppTheme">
```

Set **`android:allowBackup="false"`** — we have an encrypted Vault, you don't
want ADB siphoning it.

---

## Deep links (Universal Links / App Links)

Add inside the `<activity android:name=".MainActivity">` block:

```xml
<intent-filter android:autoVerify="true">
  <action android:name="android.intent.action.VIEW" />
  <category android:name="android.intent.category.DEFAULT" />
  <category android:name="android.intent.category.BROWSABLE" />
  <data android:scheme="https" android:host="aiadvocate.co.uk" />
  <data android:pathPrefix="/engage" />
</intent-filter>
```

You'll also need to host `/.well-known/assetlinks.json` on `aiadvocate.co.uk`
with the SHA256 fingerprint of your release keystore — Android equivalent of
Apple's `apple-app-site-association`.

---

## Network security config

Capacitor 7 ships with a sensible default that allows only HTTPS. If you
need to talk to a `localhost` backend during development, create
`android/app/src/main/res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <domain-config cleartextTrafficPermitted="true">
    <domain includeSubdomains="true">10.0.2.2</domain>     <!-- emulator → host -->
    <domain includeSubdomains="true">localhost</domain>
  </domain-config>
</network-security-config>
```

Then reference it in `AndroidManifest.xml`:

```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ... >
```

For production builds, leave the default config (HTTPS only) to satisfy the
Play Store's privacy review.
