# iOS Info.plist — Required Privacy & Capability Keys

After `npx cap add ios`, open `ios/App/App/Info.plist` in Xcode and add the
keys below. Every string is **mandatory** for App Store review when the
matching feature ships.

---

## Privacy usage descriptions (Apple rejects builds missing these)

```xml
<!-- Location: SOS, Live Tracking, Geolocated lawyer/embassy finder -->
<key>NSLocationWhenInUseUsageDescription</key>
<string>AI Advocate uses your location to (1) attach GPS metadata to evidence recordings during a police stop or encounter, (2) share your live location with your chosen emergency contacts when you trigger SOS, and (3) find nearby lawyers / embassies. Your location is never collected in the background and is only shared with the contacts you explicitly add.</string>

<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
<string>If you enable extended SOS Live Tracking (up to 24 hours), AI Advocate continues to send your location to your emergency contacts until tracking expires or you stop it. Tracking always runs in the foreground.</string>

<!-- Microphone: Encounter recordings, Hearing recorder, Lex voice mode, Translation mode, Whisper mode -->
<key>NSMicrophoneUsageDescription</key>
<string>AI Advocate records audio so you can capture interactions with police or authorities, transcribe hearings, dictate questions to Lex, and use Translation/Whisper modes during foreign stops. All recordings stay on your device unless you explicitly save them to your encrypted Vault.</string>

<!-- Speech recognition: Whisper STT runs server-side, but iOS still asks if we use any SFSpeechRecognizer fallback -->
<key>NSSpeechRecognitionUsageDescription</key>
<string>AI Advocate transcribes your voice recordings so Lex can analyse what was said and recommend next steps.</string>

<!-- Camera: Snap Evidence, multi-photo upload, document scan -->
<key>NSCameraUsageDescription</key>
<string>AI Advocate uses the camera so you can photograph documents, injuries, scenes, and other physical evidence and have them analysed by Lex.</string>

<!-- Photo Library: alternative to camera -->
<key>NSPhotoLibraryUsageDescription</key>
<string>AI Advocate lets you upload existing photos from your library as evidence (e.g. screenshots of messages, photos of injuries, or copies of legal documents).</string>

<key>NSPhotoLibraryAddUsageDescription</key>
<string>AI Advocate can save generated documents (e.g. court-ready PDFs) into your Photos library when you tap Export.</string>

<!-- Face ID / Touch ID: Vault unlock -->
<key>NSFaceIDUsageDescription</key>
<string>AI Advocate uses Face ID to unlock your encrypted Vault, which stores sensitive evidence and case documents.</string>

<!-- Contacts: only if we add a contact picker; current implementation does NOT need this. Leave commented out unless you ship the contact picker.
<key>NSContactsUsageDescription</key>
<string>AI Advocate can import contacts so you can quickly add them as emergency contacts for SOS alerts.</string>
-->
```

---

## Background modes (only if extended tracking ever needs background updates)

Currently AI Advocate runs all GPS tracking in the foreground only. **Leave
this section commented out for the first TestFlight submission** — Apple is
strict about background location and will request a written justification.

```xml
<!--
<key>UIBackgroundModes</key>
<array>
  <string>location</string>
</array>
-->
```

---

## App Transport Security

We talk to HTTPS only, so the default ATS settings are fine. **Do not**
disable `NSAllowsArbitraryLoads` unless you have a very specific reason.

If you need to allow `localhost` calls from the device during development
(rare — usually the device should hit the preview URL), add:

```xml
<key>NSAppTransportSecurity</key>
<dict>
  <key>NSAllowsLocalNetworking</key>
  <true/>
</dict>
```

---

## URL schemes (deep links)

For Universal Links (e.g. `https://aiadvocate.co.uk/engage/<token>`):

1. **Apple Developer portal**: enable Associated Domains for your App ID.
2. **Info.plist**: nothing needed — Universal Links use the `apple-app-site-association` file you host at `https://aiadvocate.co.uk/.well-known/apple-app-site-association`.
3. **Capacitor config**: already supports this via the `App.addListener("appUrlOpen", ...)` API.

For custom-scheme deep links (e.g. `aiadvocate://engage/...`):

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLName</key>
    <string>uk.co.aiadvocate.official</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>aiadvocate</string>
    </array>
  </dict>
</array>
```

---

## Apple Sign-in entitlement

If you ship Sign-in with Apple (server side is already wired):

1. In Xcode → Signing & Capabilities → `+ Capability` → **Sign in with Apple**.
2. This creates `App.entitlements` with `com.apple.developer.applesignin`.

No Info.plist edit needed.

---

## Push Notifications (deferred — ship with P2 deadline reminders)

Don't add the push capability for the first build. It's a P2 feature.
