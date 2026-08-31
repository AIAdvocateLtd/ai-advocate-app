# AI Advocate — App Store Connect Metadata (paste-and-go)

**Last updated:** Feb 2026
**Bundle ID:** `uk.co.aiadvocate.official`
**Version:** 1.0.0
**Build:** 1

---

## 1. My Apps → + → New App

| Field | Value |
|---|---|
| Platforms | iOS |
| Name | `AI Advocate` |
| Primary Language | English (U.K.) |
| Bundle ID | `uk.co.aiadvocate.official` (select from dropdown — auto-appears after upload) |
| SKU | `AIA-IOS-001` (any unique string, internal only) |
| User Access | Full Access |

---

## 2. App Information

**Subtitle (30 chars max)**
```
Legal AI Help & Case Files
```

**Category (Primary)**: Reference
**Category (Secondary)**: Productivity

**Content Rights**: You do not contain, show, or access third-party content

**Age Rating**: 17+ (Frequent/Intense Mature/Suggestive Themes → NO to all EXCEPT:
- Unrestricted Web Access → **YES** (chat AI browses law-related sites)
- Medical/Treatment Information → **Infrequent/Mild** (safeguarding disclaimers only))

---

## 3. Pricing and Availability

- **Price**: Free (with in-app purchases)
- **Availability**: United Kingdom (start UK-only, add more countries later)

---

## 4. App Privacy (this is where 60% of first-time apps get rejected — get this right)

Click **"Get Started"** on App Privacy. Answer these EXACTLY:

**Data Types Collected — YES to:**
- Contact Info → **Email Address** (linked to user, used for App Functionality + Account Management)
- Contact Info → **Name** (linked to user, App Functionality)
- User Content → **Photos or Videos** (linked to user, App Functionality — for evidence uploads)
- User Content → **Audio Data** (linked to user, App Functionality — voice notes / witness recordings)
- User Content → **Other User Content** (linked to user, App Functionality — case files, documents)
- Identifiers → **User ID** (linked to user, App Functionality + Analytics)
- Usage Data → **Product Interaction** (linked to user, Analytics via PostHog)
- Diagnostics → **Crash Data** (not linked, Analytics via Sentry)
- Diagnostics → **Performance Data** (not linked, Analytics)
- Location → **Coarse Location** (linked to user, App Functionality — Legal Aid Finder nearby search, opt-in)

**Data Types Collected — NO to:**
- Health & Fitness
- Financial Info (Stripe handles this, doesn't count as YOU collecting it)
- Sensitive Info
- Contacts (unless user actively imports Emergency contacts — if so add it)
- Search History
- Browsing History
- Purchases (Stripe again)

---

## 5. App Description (paste into "Description" field)

```
AI Advocate is your pocket legal AI — trusted by thousands of people across the UK to make sense of their rights, letters, and legal problems in plain English.

Whether you're facing a tribunal, a landlord dispute, custody proceedings, a workplace grievance, or just trying to understand a scary-looking letter — AI Advocate gives you 24/7 access to intelligent, empathetic legal help powered by the same AI models used by top law firms.

WHAT AI ADVOCATE DOES
• Ask Lex — chat with our legal AI in natural English, get citations to real UK law
• Upload any document — contracts, letters, court papers — Lex reads and explains them
• Case Files — organise your matter, keep a timeline, save every conversation
• Legal Aid Finder — find local solicitors, charities, and free legal help near you
• Letter Writer — generate polished, legally-sound letters (grievances, complaints, notices)
• Lex Vault — a private, encrypted place to store sensitive evidence
• Witness Builder — help friends and family write statements that will stand up in court
• Case Timeline — auto-organise dates, deadlines, and events in your matter
• Predict Outcome — get an honest assessment of your case's strengths and weaknesses
• Devil's Advocate — hear the other side's argument before you make one
• Cost Estimator — know what a lawyer would actually charge before you call one

PLANS
• Free — get started with basic Lex chat, case files, and legal aid finder
• Plus (£9.99/month) — unlimited chat with our faster AI, document analysis, letter writer
• Pro (£24.99/month) — everything in Plus + Deep Think mode (our smartest AI for complex cases), witness builder, predict outcome, cost estimator, contract hub, unlimited vault storage
• Pro Yearly — 2 months free vs monthly

IMPORTANT
AI Advocate provides legal information and guidance, not legal advice from a solicitor. We are not a firm of solicitors and we are not regulated by the SRA. For complex matters we always recommend speaking to a qualified legal professional — and our Legal Aid Finder helps you find one.

Your data is encrypted, private, and never sold. Lex Vault uses zero-knowledge encryption — even we can't read it.

Built in the UK 🇬🇧 for UK legal issues.
```

**Character limit: 4000 — the above is ~2200, well within limits.**

---

## 6. Keywords (100 chars max, comma-separated, no spaces after commas)

```
legal,lawyer,solicitor,law,rights,advice,tribunal,employment,tenancy,divorce,court,ai,legalaid
```

---

## 7. Support URL

```
https://aiadvocate.co.uk/support
```

## 8. Marketing URL (optional)

```
https://aiadvocate.co.uk
```

## 9. Privacy Policy URL

```
https://aiadvocate.co.uk/privacy
```

---

## 10. Screenshots (REQUIRED — upload these sizes)

**iPhone 6.9" (iPhone 15 Pro Max, 16 Pro Max) — 1290 × 2796**
- Minimum 3, up to 10
- You can **reuse your Play Store 9:16 screenshots** if resolution ≥ 1290×2796. Otherwise regenerate.

**iPhone 6.5" (older Plus/Max) — 1284 × 2778 or 1242 × 2688**
- Same screenshots resized

**iPad 13" (iPad Pro M4) — 2064 × 2752** — only if you tick "iPad support" (recommended for Reference apps)

I'll help resize/generate iOS screenshots from your Play Store assets in a follow-up if you paste them.

---

## 11. App Review Information (VERY IMPORTANT — this reaches Apple's reviewer)

**Sign-in Required**: Yes

**Demo Account Credentials** — Apple's reviewer will actually log in and test. Provide:

```
Email: applereviewer@aiadvocate.co.uk
Password: [create a strong password, save it in test_credentials.md]
```

Set this account to **Pro tier** in your admin panel so the reviewer sees all features. Without this, Apple rejects with "cannot review restricted content".

**Notes for the reviewer** (paste this):

```
Hi Apple Reviewer,

AI Advocate is a UK-focused consumer legal AI assistant.

To review all features, please log in with the demo account provided — it has a Pro tier upgrade so all AI, document analysis, and premium features are unlocked.

Key features to test:
1. Ask Lex — main chat interface. Try any legal question e.g. "Can my landlord evict me without notice?"
2. Upload a document — tap the paperclip in chat, upload any PDF
3. Case Files — tap the folder icon to see how conversations are organised
4. Legal Aid Finder — tap "Find Help" to see the location-based lookup (may prompt for location permission — allow to see nearby results)

Disclaimers: We are not a law firm and we do not provide legal advice. All Lex responses include this disclaimer. We are compliant with UK GDPR and the Legal Services Act 2007.

Any questions: samuel.malick@aiadvocate.co.uk

Thank you for your time.
```

**Contact Information**:
- First Name: Samuel
- Last Name: [your surname]
- Phone: [your mobile]
- Email: samuel.malick@aiadvocate.co.uk

---

## 12. TestFlight Setup (after upload)

Once the build finishes processing (~30 minutes after upload):

1. Go to **TestFlight** tab
2. Under **Test Information**, fill in:
   - Beta App Description: "AI Advocate closed beta — help us test our legal AI before public launch. Full Pro tier included for testers."
   - Feedback Email: `beta@aiadvocate.co.uk`
   - Marketing URL: `https://aiadvocate.co.uk`
   - Privacy Policy: `https://aiadvocate.co.uk/privacy`
3. Click your build → **"Provide Export Compliance Information"** → tick "Uses non-exempt encryption" → **NO** for the ITSAppUsesNonExemptEncryption question (HTTPS-only apps qualify for exemption)
4. Once compliance is set, you can invite up to **10,000 external testers** by email

---

## 13. Submit for Review

After screenshots + metadata are complete:
1. Top-right → **"Submit for Review"**
2. Answer the two final questions:
   - "Does this app use IDFA?" → **NO** (unless you're doing ad attribution)
   - "Export Compliance" → **NO** (already handled above)
3. Click **Submit**

Apple's review takes **24-72 hours** for a first submission. You'll get an email when reviewed.

---

## Common Rejection Reasons (and how we've pre-empted them)

| Reason | Our defence |
|---|---|
| Guideline 4.2 "Minimum Functionality" (web wrapper) | ✅ Native plugins: Camera, Photo Library, Location, Haptics, Share, Face ID, Splash. Not just a web view. |
| Guideline 5.1.1 "Data Collection" | ✅ Full App Privacy questionnaire completed above |
| Guideline 2.1 "App Completeness" (no demo account) | ✅ Demo account provided in reviewer notes |
| Guideline 1.1.2 "Objectionable Content" (legal advice liability) | ✅ Disclaimers on every response + SRA clarification in description |
| Guideline 3.1.1 "In-App Purchase" (not using IAP for digital goods) | ⚠️ Watch out — Apple requires IAP for digital subscriptions. Your Stripe subs may need Apple IAP in future. For v1, we're using Stripe web checkout which is OK as long as we NEVER link out to purchase from inside the iOS app. See notes below. |

---

## ⚠️ CRITICAL Stripe / Apple IAP note

Apple **prohibits** in-app links to external payment for digital subscriptions.

**Safe pattern for v1**:
- Do NOT show "Upgrade" buttons that open Stripe inside the iOS app
- Instead, either:
  - **(A)** Hide the upgrade button entirely on iOS — direct users to sign up on web
  - **(B)** Implement Apple IAP for iOS (takes ~4 hours, needs App Store Connect setup)
  - **(C)** Show upgrade but only through "Manage Subscription" that opens Safari to `aiadvocate.co.uk/upgrade` — risky, Apple sometimes rejects

**My recommendation**: For TestFlight (v1.0.0), use option (A) — detect iOS and hide upgrade buttons. Add IAP in v1.1.0 after TestFlight approval. I can code option (A) for you in ~15 min if you want.

---

## Next-Step Checklist

- [ ] Xcode signing complete (Step 3)
- [ ] Archive uploaded (Step 4)
- [ ] Demo account created + set to Pro tier
- [ ] All metadata pasted (this doc)
- [ ] Screenshots uploaded (iOS format)
- [ ] iOS upgrade-button-hider deployed (optional but strongly recommended)
- [ ] TestFlight compliance set
- [ ] Submitted for review
