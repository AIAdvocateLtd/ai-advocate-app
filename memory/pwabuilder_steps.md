# PWABuilder → Google Play Store: Step-by-step

This is the **fastest** path to a published Android app for AI Advocate.
Total active time: ~45 minutes. Wait time (Play review): 1–7 days.

---

## ⚙️ Prerequisites (5 min)

- [ ] You're logged in to the live production site (`https://aiadvocate.co.uk`) and it loads.
- [ ] **One-time only:** Pay the £20 Google Play Developer fee at
      https://play.google.com/console/signup — this can take up to 48h to verify
      ID with Google, do this **today** if you haven't.
- [ ] Domain verified in Google Search Console for `aiadvocate.co.uk`.

---

## 1. Confirm the PWA passes (5 min)

1. Hit "Deploy" in Emergent to push the new `manifest.json` + `sw.js` to prod.
   ⚠ Copy any new env vars manually (there are none for this change).
2. Open `https://aiadvocate.co.uk` in Chrome desktop.
3. DevTools → **Application** tab → **Manifest** — confirm:
   - Name: AI Advocate — AI Lawyer in your Pocket
   - All 4 icons load, 2 marked `maskable`
   - Display: `standalone`
   - No red errors.
4. DevTools → **Application** → **Service Workers** — confirm `sw.js` is
   `activated and running`.
5. DevTools → **Lighthouse** → check only **Progressive Web App** → run.
   Target ≥ 90. Anything red here will be flagged by PWABuilder too.

---

## 2. Generate the Android bundle on PWABuilder (10 min)

1. Go to **https://www.pwabuilder.com/**
2. Paste `https://aiadvocate.co.uk` → click **Start**.
3. PWABuilder scores your PWA. Expect ≥ 90.
4. Click **Package For Stores** → **Android**.
5. Fill in **exactly**:
   - **Package ID**: `uk.co.aiadvocate.aiadvocate`
     *(if you prefer `co.uk.aiadvocate.app` or similar, change here — but
     this is permanent once published.)*
   - **App name**: `AI Advocate — Lawyer in your Pocket`
   - **Launcher name**: `AI Advocate`
   - **App version**: `1.0.0`
   - **App version code**: `1`
   - **Host**: `aiadvocate.co.uk`
   - **Start URL**: `/?source=pwa`
   - **Display mode**: `standalone`
   - **Status bar colour**: `#000000`
   - **Navigation colour**: `#000000`
   - **Splash colour**: `#000000`
   - **Signing key**: choose **"Create new"** (PWABuilder generates one).
     ⚠️ **DOWNLOAD AND BACK UP THE `.keystore` FILE + the password.**
     You cannot publish updates without it. Store both in 1Password.
6. Click **Generate** → download the `.zip`. It contains:
   - `app-release-signed.aab` ← upload this to Play Console
   - `app-release-signed.apk` ← for testing on your own device
   - `assetlinks.json` ← upload to your server (next step)
   - `signing-key-info.txt` ← keystore password
   - `next-steps.html` ← reference

---

## 3. Upload Digital Asset Links (5 min)

Without this file, Play will install your app but it'll open with a browser
URL bar (bad UX). With it, the TWA fully takes over the domain.

1. From the PWABuilder zip, copy `assetlinks.json`.
2. Upload to your production server so it's served at:
   **`https://aiadvocate.co.uk/.well-known/assetlinks.json`**
3. Confirm by visiting that URL in a browser — must serve as `application/json`.

   In this repo, place it at `/app/frontend/public/.well-known/assetlinks.json`
   then hit Deploy. Verify with:
   ```bash
   curl -I https://aiadvocate.co.uk/.well-known/assetlinks.json
   ```
   Expect `200 OK` and `content-type: application/json`.

---

## 4. Create the Play Console app (10 min)

1. https://play.google.com/console → **Create app**.
2. App details:
   - Name: `AI Advocate — Lawyer in your Pocket`
   - Default language: English (United Kingdom)
   - App or game: **App**
   - Free or paid: **Free** (subscriptions are in-app)
   - Declarations: tick both.
3. **Dashboard** → work through the "Set up your app" checklist:
   - Privacy policy → `https://aiadvocate.co.uk/privacy.html`
   - App access → "All functionality available without restrictions" + provide
     a test login (see `/app/memory/test_credentials.md`).
   - Ads → No
   - Content rating → complete questionnaire (see `google_play_listing.md` §5)
   - Target audience → 18+
   - News app → No
   - COVID-19 → No
   - Data safety → paste answers from `google_play_listing.md` §6
   - Government → No
   - Financial features → see `google_play_listing.md` §10

---

## 5. Upload the AAB to Internal Testing (5 min)

1. **Testing → Internal testing → Create new release**.
2. Drag in `app-release-signed.aab`.
3. Release name: `1.0.0 (1) — PWA TWA launch`.
4. Release notes (in `<en-GB>`):
   ```
   Initial public launch of AI Advocate — your AI lawyer in your pocket.
   • Ask Lex AI chat with UK-wide legal knowledge
   • Evidence vault, case files & timeline
   • Letter Writer with on-screen e-signature
   • Find Legal Aid solicitors near you
   • Contract Hub & Solicitor Sanity Check
   ```
5. Save → Review → Roll out to Internal Testing.
6. Add yourself + 4 friends as testers (Settings → Testers).
7. Install via the opt-in link Google emails you, run through every flow on
   a real Android device.

---

## 6. Promote to Production (5 min)

Once you've tested for a day:

1. **Testing → Internal testing → Promote release → Production**.
2. **Production → Countries / regions** → United Kingdom (start with UK only,
   add more later).
3. **Production → Release** → "Send for review".
4. Google reviews in 1–7 days. They will:
   - Verify the digital asset link (so don't break the file).
   - Spot-check screenshots & description.
   - Run the app in their emulator.
5. Once approved, you get an email and the listing goes live on Play Store
   within a few hours.

---

## 7. iOS App Store (deferred)

Apple does **not** accept TWA-style PWAs. You will need a Capacitor wrapper.
This is a separate ~3-day effort blocked on:
- Apple Developer account (£99/year, 24h ID verification)
- Capacitor scaffold (`@capacitor/core`, `@capacitor/ios`)
- StoreKit 2 in-app purchase wiring for Apple's 30% cut **OR** Apple's new
  "external purchase entitlement" (EU only) to keep Stripe.

We'll tackle this once Android is approved and revenue is flowing.

---

## 🚨 Common review rejections (and the fix)

| Rejection | Why | Fix |
|---|---|---|
| "App functionality is limited" | Reviewer didn't sign in | Provide a real test login in App Access |
| "Login wall on first launch" | Reviewer can't get past signup | Same — give them a working email/password |
| "Misleading metadata" | Title says "Lawyer" | Add disclaimer "Provides legal information, not advice — for complex matters consult a solicitor" to short description (already done in §3) |
| "Digital Asset Links missing" | `assetlinks.json` not at the .well-known URL | Re-upload and check `curl` returns JSON |
| "Background location" | Manifest declares location but app doesn't justify it | We declare *Approximate, foreground only* — keep it that way |

---

## 📁 Files to drop into the repo before Deploy

- ✅ `/app/frontend/public/manifest.json` (updated)
- ✅ `/app/frontend/public/sw.js` (new)
- ✅ `/app/frontend/public/index.html` (SW registration injected)
- ✅ `/app/frontend/public/assets/icon-192-maskable.png` (new)
- ✅ `/app/frontend/public/assets/icon-512-maskable.png` (new)
- 🟡 `/app/frontend/public/.well-known/assetlinks.json` (you'll add this in
     Step 3 after PWABuilder generates it for you)
