# AI Advocate — Native Build Handoff (Phase 1 → Phase 2)

This folder + the `ios/` and `android/` folders one level up are everything you need to ship to the App Store and Google Play. Phase 1 (preparation) is done. Phase 2 (Mac/Studio steps) is yours.

---

## 📦 What's in this build

- **App ID** `uk.co.aiadvocate.official`
- **App name** AI Advocate
- **Version** 1.0.0 (build 1)
- **Backend** `https://aiadvocate.co.uk` (production-hardcoded — 0 preview refs verified)
- **Icons** 15 iOS sizes + 11 Android sizes + Play Store 512px — all copied into native projects
- **Splash** Black canvas + centred shield logo, configured for 2732×2732 → auto-scales
- **Permissions** 9 iOS `UsageDescription` strings added to `Info.plist` (camera, mic, location, photos, contacts, Face ID — Apple auto-rejects without these)

---

## 🍎 Phase 2 — iOS submission (your Mac)

1. **Get the code on your Mac**
   - Use the "Save to GitHub" button in the Emergent chat, push to your repo
   - On your Mac: `git clone <your-repo>`
   - `cd <repo>/frontend && yarn install`

2. **Open Xcode**
   ```
   open ios/App/App.xcworkspace     # ← important: .xcworkspace, NOT .xcodeproj
   ```

3. **Sign with your Apple Developer team**
   - Click "App" in the left sidebar → "Signing & Capabilities" tab
   - Team: pick your Apple Developer team
   - Bundle Identifier: confirm `uk.co.aiadvocate.official`
   - "Automatically manage signing" → ✓

4. **Capabilities to enable** (Signing & Capabilities → "+ Capability"):
   - **Push Notifications** (you'll need this for the P1 push feature later)
   - **Sign in with Apple** (if you offer Apple sign-in)
   - **In-App Purchase** (only if you plan native IAP for top-ups; otherwise skip and just use Stripe via the web)

5. **Pick "Any iOS Device (arm64)" as the target** (top bar, not a simulator)

6. **Product → Archive**
   - Xcode builds + archives. Takes ~5 min the first time.
   - When done, Organizer window opens.

7. **Distribute App → App Store Connect → Upload**
   - Xcode walks you through it
   - Wait 10-30 min for App Store Connect to finish processing
   - You'll get an email when the build is ready to submit for review

8. **In App Store Connect**
   - Fill in screenshots (6.7" + 6.5" iPhone + 12.9" iPad), description, keywords
   - Privacy Nutrition Label (this is a separate form — use `aiadvocate.co.uk/privacy.html` as reference)
   - Age rating: 12+ (legal content / occasional reference to violence in emergency mode)
   - Pricing: Free (subscriptions handled via Stripe)
   - Submit for Review

**Apple review time** typically 24-48 hours.

---

## 🤖 Phase 2 — Android submission (Android Studio)

Android Studio runs on Mac, Windows, AND Linux — so if you don't have a Mac yet you can do Android first.

1. **Open Android Studio**
   ```
   cd <repo>/frontend && npx cap open android
   ```

2. **Build → Generate Signed Bundle / APK**
   - Pick **Android App Bundle (.aab)** — Play Store requires this format now
   - Create a new keystore (first time) — **back this up — losing it means you can never update the app again**
   - Build: release variant

3. **Upload `.aab` to Google Play Console**
   - Production track → Create release
   - Upload the `.aab` file
   - Fill in: short description, full description, screenshots (phone + 7" tablet + 10" tablet)
   - **Data Safety form** — declares what data you collect (use `privacy.html` as reference)
   - **Content rating questionnaire** — 5 min
   - Content guidelines / target audience

**Google review time** typically 2-24 hours.

---

## 🔧 If anything needs changing after submission

You **always** need a Mac for iOS builds (Apple's rule, not a code limitation). Android can be rebuilt from any OS.

For most JS/CSS changes after launch, you have **two options**:

| Change type | Mac needed? | How |
|---|---|---|
| Backend / API / DB | ❌ No | Redeploy from Emergent platform |
| Web app (`aiadvocate.co.uk`) | ❌ No | Redeploy from Emergent platform |
| iOS — JS/CSS only (Capacitor sync) | ⚠️ Yes, but quick | Run `yarn build && npx cap sync ios` on your Mac, then Xcode → Archive → Upload (~10 min) |
| iOS — native plugin / Info.plist change | ✅ Yes | Same as above |
| Android — JS/CSS only | ⚠️ Any OS | `yarn build && npx cap sync android && cd android && ./gradlew bundleRelease` |
| Android — native | ⚠️ Any OS | Same as above |

**Faster updates after launch** — once you have an iOS build live, you can update the web bundle **without re-submitting to Apple** using:
- **Capacitor Live Updates** ($29/mo, official)
- **AppFlow** (Ionic, free tier available)
- **expo-updates** (if you ever switch to Expo)

These let you push JS/CSS changes OTA — only resubmit through Apple for native-code changes (plugin updates, permissions, version bumps).

---

## 🆘 Common gotchas

- **"App Sandbox" / "Hardened Runtime" errors in Xcode** — these are automatic on iOS apps, just keep the defaults.
- **Pods missing** — on your Mac, run `cd ios/App && pod install`
- **Android Gradle version mismatch** — Android Studio will offer to update; let it.
- **Splash screen doesn't show** — verify the launch image set in `ios/App/App/Assets.xcassets/Splash.imageset` matches the screen resolution.
- **App size warnings** — your bundle is ~5MB; well under Apple's 4GB limit.

---

## ❓ Questions for support

If something fails, file the issue on Apple Developer Forums (response in days) or Stack Overflow (response in hours). The most common errors are about provisioning profiles — these are signing related, and **always** Apple Developer Portal issues, never code issues.

Good luck — you're ~2 hours of clicks away from being live on both stores.
