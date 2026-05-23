# AI Advocate — iOS / Android Build Instructions

The web app is fully wrapped with [Capacitor 7](https://capacitorjs.com). All web
flows continue to work; the native wrap simply adds Geolocation, Filesystem,
Share, Preferences/Keychain, SplashScreen, StatusBar, Haptics, Browser, etc.

## Prerequisites

| Tool              | Version             |
| ----------------- | ------------------- |
| Node.js           | 20.x or 22.x        |
| Xcode             | 16.x (for iOS)      |
| iOS deployment    | 14.0 minimum        |
| Android Studio    | Hedgehog 2023.1+    |
| Android SDK       | API 33+             |
| Yarn              | 1.22+               |
| CocoaPods         | latest              |

## Initial setup (one-time, runs locally on your Mac)

```bash
git clone <repo>
cd ai-advocate/frontend
yarn install
yarn build              # produces /build for Capacitor to bundle
npx cap add ios
npx cap add android
npx cap sync            # copies build/ + plugins into ios/ + android/
```

After this you'll have new `ios/` and `android/` folders alongside the
existing `src/` and `build/`.

## Day-to-day workflow

```bash
# 1. Make your React changes as usual
yarn start              # web dev — works fine without native

# 2. When you want to test on a device or simulator:
yarn build
npx cap sync            # ALWAYS run this after a build
npx cap open ios        # opens Xcode → build & run on simulator / iPhone
npx cap open android    # opens Android Studio → build & run
```

## App Store / TestFlight checklist

### Identifiers
- **Bundle ID (iOS) / App ID (Android):** `uk.co.aiadvocate.official`
- **App name:** AI Advocate
- **Marketing version:** keep in sync with `package.json` `version`

### Capabilities to enable in Xcode → Signing & Capabilities
- **Push Notifications** (deferred — add when we ship deadline reminders, P2).
- **Background Modes → Location updates** (only if we ever enable
  background SOS tracking — current implementation requires foreground).
- **Sign in with Apple** (you already have this configured server-side).
- **Associated Domains** — add `applinks:aiadvocate.co.uk` if you want
  Universal Links (e.g. for `/engage/<token>` deep links).

### Required iOS files
Copy the privacy-string snippets from `IOS_INFO_PLIST.md` into
`ios/App/App/Info.plist` (Xcode creates this from the template — you just
need to paste in the keys).

### Required Android files
Copy the manifest snippets from `ANDROID_MANIFEST.md` into
`android/app/src/main/AndroidManifest.xml`.

### Icons + splash
Use [`@capacitor/assets`](https://github.com/ionic-team/capacitor-assets) to
auto-generate everything from one logo:

```bash
yarn add -D @capacitor/assets
# Place logo.png (1024x1024) and splash.png (2732x2732) in /assets, then:
npx capacitor-assets generate
```

The current splash background is `#0a0a0a` (matches the in-app theme).

## Native Vault Key migration (post-wrap)

The Vault unlock token currently lives in `localStorage`. On the wrapped app,
upgrade it to iOS Keychain / Android EncryptedSharedPreferences with **one
line change** in the Vault modal:

```js
// Before:
const tok = localStorage.getItem("aa_vault_unlock");

// After:
import { secureGet } from "@/nativeBridge";
const tok = await secureGet("aa_vault_unlock");
```

Same for `secureSet` / `secureRemove`. The bridge transparently falls back to
`localStorage` on web, so the change is safe to ship before TestFlight.

## Releasing

### iOS
1. Bump `MARKETING_VERSION` in Xcode (or run `agvtool new-marketing-version X.Y.Z`).
2. Bump `CURRENT_PROJECT_VERSION` (build number).
3. `Product → Archive` → upload to App Store Connect via Xcode Organizer.
4. Submit to TestFlight internal testers → external → App Review.

### Android
1. Bump `versionName` and `versionCode` in `android/app/build.gradle`.
2. `./gradlew bundleRelease` → produces an `.aab` in `android/app/build/outputs/bundle/release/`.
3. Upload to Play Console → Internal Testing → Closed → Production.

## Known gotchas

- **iOS Safari ↔ Capacitor difference:** `navigator.geolocation` on the web
  works but is rate-limited. Capacitor's `Geolocation` plugin uses
  `CoreLocation` directly and is more reliable on iPhones — already wired
  via `nativeBridge.getPosition()`.
- **Sharing files:** Capacitor's `Share` plugin needs the file to live in
  the app's sandbox (use `Filesystem.writeFile` first). The web fallback in
  `nativeBridge.share()` will just copy a URL to the clipboard — wrap web
  exports inside a download instead.
- **iOS local network permission:** if you ever want to call the local
  backend (`http://localhost:8001`) from the device, you need to set
  `NSAllowsLocalNetworking` in `Info.plist`. For production, traffic should
  always go to `REACT_APP_BACKEND_URL` (HTTPS), so this isn't normally needed.
