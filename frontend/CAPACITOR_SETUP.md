# Capacitor iOS + Android Wrap — Setup Guide

This folder contains the **Capacitor config** that turns the AI Advocate web app into native iOS and Android binaries.

The actual native builds **must be run on your machine** — the cloud preview environment doesn't have Xcode or Android Studio. Below is the exact sequence.

---

## Prerequisites (your Mac for iOS, any OS for Android)

```bash
# Node 20+ already used by yarn
node -v

# For iOS — Xcode 15+ from App Store, then:
xcode-select --install
sudo gem install cocoapods

# For Android — install Android Studio Hedgehog or newer
# Set ANDROID_HOME / JAVA_HOME per Android Studio's first-run wizard.
```

---

## One-time setup

```bash
cd /app/frontend
yarn add @capacitor/core @capacitor/cli @capacitor/ios @capacitor/android
yarn build              # produces /app/frontend/build
npx cap init             # use existing capacitor.config.json — accept defaults
npx cap add ios
npx cap add android
```

This creates `/app/frontend/ios` and `/app/frontend/android` directories that you commit alongside the web code.

---

## Reader-App compliance (Apple's 30 % rule)

Apple requires that subscriptions sold INSIDE the iOS app go through Apple's In-App Purchase (30 % fee). The **Reader App rule** lets you avoid this by:

1. **Hiding** all `Subscribe` / `Upgrade` buttons when running inside the native iOS binary.
2. Letting the user create / manage their subscription **only on the web** (aiadvocate.co.uk/subscribe).

The frontend already detects native via:

```js
const isCapacitorNative = !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
```

When `isCapacitorNative === true`, we:
- Hide the Subscribe buttons (Settings, banners, tile lock screens).
- Replace them with: *"Manage your subscription on aiadvocate.co.uk"* with a tappable link.

This passes Apple Review under Guideline 3.1.3(a) — Reader Apps. (Stripe Live billing still happens on the web; users sign in to the iOS app with the same account.)

---

## Wake-word & background mic (iOS)

iOS Safari blocks always-listening for security. The native iOS build can request the **background microphone** entitlement and use the standard `AVAudioSession` for true "Hey Lex" wake-word detection while the app is backgrounded.

Add to `ios/App/App/Info.plist` after `npx cap add ios`:

```xml
<key>NSMicrophoneUsageDescription</key>
<string>Lex needs the microphone for voice conversations and wake-word detection.</string>
<key>NSCameraUsageDescription</key>
<string>Used to capture photo and video evidence.</string>
<key>NSLocationWhenInUseUsageDescription</key>
<string>Used (optionally) to stamp the location on evidence you record.</string>
<key>NSContactsUsageDescription</key>
<string>Used to set up your emergency contact.</string>
<key>UIBackgroundModes</key>
<array>
  <string>audio</string>
</array>
```

For Android, add to `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO"/>
<uses-permission android:name="android.permission.CAMERA"/>
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
<uses-permission android:name="android.permission.READ_CONTACTS"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
```

---

## Build commands

```bash
cd /app/frontend
yarn build && npx cap sync          # rebuild web, copy into native projects
npx cap open ios                     # launches Xcode — Product → Archive → upload to App Store Connect
npx cap open android                 # launches Android Studio — Build → Generate Signed Bundle (.aab) → upload to Play Console
```

---

## App Store Connect / Play Console assets

You'll need:
- App icon 1024×1024 PNG (use the gold logo from the web app)
- 5 screenshots per device size (iPhone 6.7", 6.5", 5.5"; iPad 12.9")
- Privacy Policy URL: `https://aiadvocate.co.uk/privacy`
- Support URL: `mailto:support@aiadvocate.co.uk`
- Apple App-Specific-Password for Apple Sign-In review (already in `.env`)

App Privacy nutrition labels — declare:
- Data linked to user: Contact info (email), Identifiers (User ID), Audio data (voice chats), Photos (evidence), Usage data
- Data NOT collected for tracking
- All data encrypted in transit (TLS) and at rest (Mongo Atlas + Stripe)
