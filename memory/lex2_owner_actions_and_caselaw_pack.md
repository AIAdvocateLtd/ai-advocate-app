# Lex 2.0 — owner actions and case-law licence pack (prepared 2026-11-21)

## A. France: switch on Légifrance (free)
1. Go to https://piste.gouv.fr and click **Inscription**. Create an account using the company email and confirm the email.
2. In **API → Catalogue**, open **Légifrance** and accept the terms of use (CGU) for **Production**.
3. Go to **Applications → Créer une application**. Choose **Production**, name it "AI Advocate Lex", enter a contact email and tick the **Légifrance** API.
4. Open the application and copy the **OAuth Client ID** and **Client Secret**.
5. Tell Lex's builder "Légifrance keys ready". The builder will open a secure key card (LEGIFRANCE_CLIENT_ID / LEGIFRANCE_CLIENT_SECRET). **Never paste keys in chat.**
6. The builder then runs the focused French tests in preview: the code du travail and code de la consommation articles in the topic map, a check that a wrong article is rejected, and a consolidated-version date check. After that you approve the production release.
- Licence: Légifrance data is published under the Licence Ouverte / Etalab 2.0. Commercial reuse is allowed with attribution, which Lex already gives as "Légifrance (DILA)".

## B. New York: official statute feed (free)
1. Go to https://legislation.nysenate.gov and request a free API key using the company email. The key arrives by email.
2. Enter it in the secure key card **NYSENATE_API_KEY**.
3. The builder tests these sections: GOB 7-108 (deposits), RPP 226-c (notice before a lease ends), RPA 711 (eviction) and RPP 235-b (repairs).
- Texas (Texas Legislative Council files) and Florida (Florida Senate) are already connected directly, with no key needed.

## C. Monitoring activation (17 provisions)
- Status: the baseline is complete (17/17 fingerprints) and the 06:00 Europe/London cron is in the live build. The schedule is OFF.
- To activate: Admin → Settings → **Law monitoring** → switch on daily checks. This requires your admin sign-in and approval. The builder must not do it.

## D. National Archives "Find Case Law": licence for computational analysis
- Apply here: https://caselaw.nationalarchives.gov.uk/apply-for-a-licence
- Free. Typically a few weeks (Discovery Board meets monthly). Enquiries: caselawlicence@nationalarchives.gov.uk
- The form must be completed in one sitting. It has 29 questions in 6 sections; download the Word list of questions from the "What you need to apply" page first.
- **Main risk:** TNA treats the following as HIGH RISK:
  - "fully automated legal advice"
  - predicting outcomes for a consumer
  - directly influencing whether someone pursues legal action
- Lex must therefore be described honestly as **legal information with citations, a human-review pathway and no outcome prediction**. On question 25, answer "None of the above" only if that is true. Otherwise disclose it, and expect a restricted or refused transactional licence.
- Licence type to request: **Transactional** (commercial service, up to 5 years).

### Information you must supply
- Licence holder: a senior person responsible for compliance (name, email). Main contact: name and email.
- Organisation: legal name, other names, country and registered address, company type, company number, and any partners (Emergent as the hosting platform; Anthropic and OpenAI as AI model providers).
- Product: name "AI Advocate — Lex", URL https://aiadvocate.co.uk, purpose, and access type (restricted: registered users and subscribers).

### Draft public statement (≈150 words) — edit before submitting
AI Advocate helps people in the UK understand their legal position in plain language. Lex, our AI legal-information assistant, answers questions with citations to official legislation and, under this licence, to published judgments from Find Case Law. We will search Find Case Law only for judgments relevant to a user's question or cited in an answer. We retrieve the authoritative published version, show a short sourced extract and always link to the full judgment. We do not predict case outcomes, do not index judgment text on search engines and do not build profiles of individuals. Users are told that answers are AI-generated legal information, that the collection is incomplete, and when to seek a qualified lawyer. A qualified legal reviewer oversees our legal content, and we regularly check for bias and inaccuracy. Our aim is to widen access to reliable, transparent legal information.

### Governance answers to prepare (questions 16–27)
- Analysis focuses on individuals: **No**.
- Anonymised names are preserved, and there is no jigsaw re-identification.
- Regular bias review: **Yes**, with a quarterly sample review by the legal reviewer.
- Code of ethics: **Yes**.
- Impartial ethics review: needs a decision from you (for example an external adviser).
- Full record: link to the full judgment on Find Case Law. Extracted data published: only short quotes inside answers. Methodology published: **Yes**, on a transparency page (to write).
- Generative-AI notice: **Yes** (already shown).
- Collection limits explained: **Yes**.

### Nine-principles statement — risks and controls to describe
1. **Dignity and independence of the courts:** neutral extracts only, with no commentary on judges.
2. **Appropriate scrutiny:** "incomplete collection" warning on every case citation.
3. **Anti-discriminatory harm and anti-bias:** quarterly review, a user feedback route and takedown of reported outputs.
4. **Personal privacy:** UK GDPR. Customers' questions are not sent to TNA, and there is no profiling.
5. **Discoverability:** judgment text is never published to search engines. Answers sit behind login and are marked noindex.
6. **Algorithmic transparency:** a methodology page.
7. **Accurate representation:** re-check that a judgment still exists before each use (taken-down judgments are dropped), cache it for 7 days at most and show the judgment date and court.

## E. Case-law integration design (NOT enabled; build only after the licence is granted)
- **Switch:** app setting `caselaw_licence` = {granted: false, licence_ref, expires}. Off by default; turning it on is admin-only and audited.
- **Retrieval:** Find Case Law Atom search feed (`/atom.xml?query=…`) limited to the jurisdiction and topic. Judgment XML from `/{uri}/data.xml`. Maximum 3 judgments per answer.
- **Shared research layer:** uses the same `national_law`-style `read()` cache (7 days), fingerprints and the change queue (reporting takedowns and revisions).
- **Citation check:** every neutral citation Lex mentions (e.g. [2024] UKSC 12) is checked against Find Case Law. If it isn't found, it is marked "unverified". This reuses `check_citations`.
- **Labelling:** "Judgment from Find Case Law (incomplete collection), retrieved {date}; extract only — read the full judgment". Clearly separated from legislation. No prediction wording.
- **Cost:** free API with no per-call cost. Adds an estimated 0.3–0.8 s latency, plus about £0.001–0.003 of model input per answer for extracts.
- **Before enabling:** apply the licence terms, add the methodology page, run focused tests (existence check, takedown handling, no indexing) and get your approval.
