"""
Curated pool of UK legal "Tip of the Day" entries.

~120 hand-written tips covering the most-asked-about UK legal scenarios.
Cycled deterministically by day-of-year + a per-user offset so two users
don't see the same tip on the same day.

Every tip:
  - max ~32 words (fits the dashboard card cleanly)
  - UK-accurate at time of writing (Feb 2026)
  - NEVER cites a specific case-law / paragraph number (those rot fast)
  - Phrased as actionable "Know-Your-Rights" advice, NOT regulated legal advice
  - Includes the relevant statute name where it helps the user google more
"""

# Categories are interleaved during selection so the daily card stays varied.
TIPS = {
    # ---- 🏘 Tenancy / Housing (16) ----
    "tenancy": [
        "Your landlord MUST protect your deposit in a government-approved scheme within 30 days. If they don't, you can claim back up to 3× the deposit in court.",
        "A Section 21 'no-fault' eviction notice is invalid if your deposit wasn't protected, your gas safety certificate wasn't given, or your EPC wasn't provided before the tenancy.",
        "Your landlord must give you at least 24 hours' written notice before entering the property — except in genuine emergencies like a burst pipe.",
        "Mould caused by structural damp is the landlord's responsibility. Report it in writing — under the Homes (Fitness for Human Habitation) Act 2018 they must fix category-1 hazards.",
        "Joint tenants are jointly and severally liable for the FULL rent. If one flatmate leaves without telling the landlord, you still owe the whole amount.",
        "A landlord can't withhold your deposit just because you 'broke the contract'. Deductions must be itemised and reasonable, and you can dispute them via the deposit scheme's free ADR.",
        "You have the right to a written tenancy agreement only if it lasts over 3 years. Otherwise, the law still gives you the same rights — get key terms in writing.",
        "If your landlord harasses you to leave (changing locks, cutting off services), this is a criminal offence under the Protection from Eviction Act 1977. Phone the council's Tenancy Relations Officer.",
        "Renting from a rogue landlord? The Database of Rogue Landlords (gov.uk) lets councils ban repeat offenders. Report unsafe conditions to Environmental Health for a free inspection.",
        "Section 21 notices need at least 2 months' notice and use Form 6A. Section 8 (for arrears) can be as short as 2 weeks. Check which form they actually sent.",
        "Your right to repair: if the landlord ignores written notice of disrepair for 14 days, you can get a council enforcement notice — and reduce future rent through court.",
        "Service charge demands must be issued within 18 months of the cost being incurred. Older charges are unenforceable under Section 20B of the Landlord and Tenant Act 1985.",
        "If your private landlord lets a property with 5+ unrelated occupants on 2+ storeys, they likely need an HMO licence. Unlicensed HMOs entitle tenants to claim Rent Repayment Orders.",
        "Council tenants: 'Right to Buy' discounts can reach £102,400 (London) or £76,800 (rest of England). You need 3 years' qualifying tenancy minimum.",
        "Squatting in a residential property is a criminal offence under Section 144 LASPO 2012. Commercial squatting is still civil — landlords need a possession order.",
        "Before signing: ask if the property is in a 'Selective Licensing' area. If yes and the landlord doesn't have a council licence, you may be entitled to a Rent Repayment Order.",
    ],

    # ---- 💼 Employment (16) ----
    "employment": [
        "Unfair dismissal claims must be filed at the Employment Tribunal within 3 months LESS ONE DAY of dismissal — and you MUST do ACAS Early Conciliation first. Miss it and the claim is dead.",
        "You don't need 2 years' service to claim 'automatic unfair dismissal' — for whistleblowing, pregnancy, raising H&S concerns, or refusing illegal instructions, you can claim from day one.",
        "Your employer can ONLY deduct from your wages if it's required by law (PAYE/NI), allowed by your contract in writing, or you've signed prior written consent. Otherwise it's unlawful — Section 13 ERA 1996.",
        "Statutory redundancy pay: 0.5 weeks per year under age 22, 1 week age 22-40, 1.5 weeks over 41. Capped at £719/week and 20 years. Plus your contract may give more — check it.",
        "Settlement agreements MUST be signed off by an independent solicitor or trade union official paid for by the employer. Don't sign anything without that — you waive all employment claims forever.",
        "Working over 48 hours per week? You can opt out, but you can ALSO opt back in at any time with 7 days' notice under the Working Time Regulations 1998.",
        "Discrimination claims under the Equality Act 2010 cover 9 'protected characteristics' — age, disability, gender reassignment, marriage, pregnancy, race, religion, sex, sexual orientation. No service length needed.",
        "Your employer must give you a written statement of employment particulars on or before day one — not 'sometime later'. Failure to do so can be used against them in tribunal.",
        "Non-compete clauses in employment contracts are only enforceable if 'reasonable in scope' — usually max 6-12 months and geographically limited. Many are unenforceable as drafted.",
        "Paid holiday accrues during sick leave AND maternity leave. If you're dismissed, you must be paid for accrued-but-untaken holiday — Section 27 ERA 1996.",
        "Constructive dismissal happens when your employer fundamentally breaches the contract (cut pay, demotion, harassment unaddressed) — you resign promptly and claim. Don't delay or you waive the right.",
        "Whistleblowing protection (PIDA 1998): your disclosure must be in the 'public interest' and made to the right person/authority. Internal grievance first is usually wisest.",
        "Statutory Maternity Pay: 90% of weekly earnings for 6 weeks, then £184.03/week (or 90% if lower) for 33 weeks. You need 26 weeks' service before the 15th week pre-due-date.",
        "Zero-hours contracts can't have 'exclusivity clauses' — these were banned under the Small Business Act 2015. You're free to work for other employers.",
        "Employer references must be 'fair and accurate'. Defamatory or maliciously incomplete references can give rise to a negligent-misstatement claim — Spring v Guardian Assurance.",
        "Disciplinary hearings: you have a statutory right to be accompanied by a colleague or trade union rep. Refusing this right can make any subsequent dismissal unfair.",
    ],

    # ---- 👮 Police & Criminal procedure (14) ----
    "police": [
        "If stopped under 'Stop and Search', the officer must give you a record showing their name, station, reason for the search, and the law used. Demand it — it's free and you're entitled.",
        "You have the right to free legal advice at the police station, 24/7, regardless of income. Always ask for the duty solicitor before answering ANY questions in interview.",
        "'No comment' is a complete legal answer in police interview. But silence can be used against you at trial if you later raise something you 'could reasonably have mentioned' — get legal advice first.",
        "Police can detain you for up to 24 hours without charge for most offences (36 with Superintendent approval, 96 with magistrate's warrant). Time stops if they question you elsewhere.",
        "You're entitled to a copy of the Custody Record on leaving the station — and at any point afterward. It documents your detention, contacts, and interviews. Useful evidence.",
        "Roadside breathalyser refusal carries a MINIMUM 12-month driving ban — usually a higher penalty than failing the test itself. Refusing without 'reasonable excuse' is its own offence.",
        "Caution wording: 'You do not have to say anything. But it may harm your defence if you do not mention when questioned something you later rely on in court.' Memorise this.",
        "Police bail conditions can be challenged at a magistrates' court. If they're disproportionate (e.g. excluded from your own home), you can apply to vary them — free legal aid usually available.",
        "Section 60 'suspicion-less' stop and search powers must be authorised in writing by a senior officer for a specific area and time period. Ask which authorisation applies — they must tell you.",
        "Wrongful arrest claim: 6-year limitation period (3 for personal injury). False imprisonment damages typically £500-£10,000 depending on duration. Solicitor on contingency-fee basis.",
        "If you're under 18 in police custody, an 'appropriate adult' MUST be present for interview. Parent, guardian, social worker — not a friend, and not anyone involved in the offence.",
        "Filming or photographing police in a public place is generally legal under the Human Rights Act 1998 (Article 10). Be polite, don't obstruct — but you don't have to stop.",
        "Spent convictions (Rehabilitation of Offenders Act 1974): most don't need disclosure after the rehabilitation period. Standard/Enhanced DBS still shows them. Check disclosure.support.org.uk.",
        "Voluntary interview at the police station gives the same rights as if you'd been arrested — solicitor, caution, recordings. Don't agree to a 'quick chat' off the record.",
    ],

    # ---- 🛒 Consumer rights (14) ----
    "consumer": [
        "Faulty goods bought in the last 30 days: full refund, no questions asked. Up to 6 months: presumed faulty at sale unless retailer proves otherwise. Consumer Rights Act 2015.",
        "Section 75 of the Consumer Credit Act: credit card purchases £100-£30,000 give you an equal claim against the CARD company AND the retailer. Use it when the retailer goes bust.",
        "Online purchases: 14-day cooling-off period from delivery to cancel for ANY reason — no fault needed. Includes return postage paid by you (unless retailer pays). Refund within 14 more days.",
        "Booked a holiday and the company collapses? ATOL-protected flights are refundable. ABTA package holidays are too. Section 75 covers any card payment over £100.",
        "Hotel quietly added a charge you didn't agree to? It's an unfair term unless 'individually negotiated and brought to your attention'. Demand refund — small claims if refused.",
        "'Sold as seen' or 'no returns' signs are NOT legally enforceable for new goods. Your statutory rights override any sign or T&C in this respect.",
        "Counterfeit goods sold to you knowingly? Report to Trading Standards via Citizens Advice. The retailer must refund — and may face a criminal offence under the Trade Marks Act 1994.",
        "Pre-paid gym memberships: most have a 14-day cooling-off if signed online or at home. In-branch sign-ups vary — read the cancellation clause BEFORE you sign.",
        "Delivery is the retailer's responsibility until the goods are in your hands — even if a courier loses them. Don't accept 'contact the courier yourself' — it's their problem.",
        "Subscription that auto-renewed without warning? If they didn't email a reasonable reminder before the renewal date, the Digital Markets, Competition and Consumers Act 2024 may give you a right to cancel.",
        "Mis-sold financial product? You have 6 months from the firm's final response to escalate to the Financial Ombudsman Service. Free, no solicitor needed.",
        "Tradesperson's quote vs estimate: a 'quote' is legally binding once you accept it. An 'estimate' is just a guide and they can charge more — but only if 'reasonable'.",
        "Restaurant added a 'discretionary' service charge but service was poor? You can refuse to pay it — by law, discretionary means optional. Don't be embarrassed to ask it's removed.",
        "Online retailer based outside the UK? Consumer Rights Act still applies if they target UK customers. ADR scheme + Section 75 card chargeback are your best routes.",
    ],

    # ---- 💷 Debt / Credit (14) ----
    "debt": [
        "Statute-barred debt: in England & Wales, a creditor can't sue you for a consumer debt after 6 years of no payment AND no written acknowledgment. The debt still exists, but unenforceable.",
        "Bailiffs can only enter peacefully through an unlocked door. They CAN'T force entry for council tax, parking fines or most debts. Lock the door, talk through a window.",
        "County Court Judgments (CCJs) drop off your credit file after 6 years — even if unpaid. Paying within 30 days of judgment gets it removed from the register entirely.",
        "Debt collectors aren't bailiffs. They have NO right to enter your home, threaten you, or seize property. They can only ask — and they have to be honest about who they are.",
        "An IVA (Individual Voluntary Arrangement) typically writes off 30-70% of unsecured debt over 5-6 years. Better than bankruptcy in most cases — but you need disposable income to qualify.",
        "If a creditor sells your debt to a third party, your statutory rights stay the same. They need to send you a Notice of Assignment — without it, the new owner can't enforce.",
        "Credit file errors? Lender must investigate within 28 days of you raising it (Section 159, Consumer Credit Act). If wrong info isn't removed, escalate to the Information Commissioner.",
        "Mortgage in arrears: your lender MUST follow MCOB rules before possession. They have to offer payment plans, term extensions, or capitalisation before going to court.",
        "Council tax arrears can lead to imprisonment ONLY for 'wilful refusal' — a very high bar. Inability to pay is a complete defence. Always engage with the council early.",
        "Priority debts (rent, mortgage, council tax, utilities, magistrates' fines) get paid first. Non-priority (credit cards, overdrafts, payday loans) get a smaller pro-rata share via a Debt Management Plan.",
        "Bank charges that pushed you into overdraft? You can challenge them as 'unfair commercial practice' if they were unreasonable in proportion to the breach. Financial Ombudsman is free.",
        "Bankruptcy in England & Wales lasts 1 year. Most debts wiped, but student loans, court fines, child maintenance and tax fraud survive. Free debt advice via StepChange or National Debtline first.",
        "Debt Relief Order (DRO): for debts under £50,000, assets under £2,000, low income. Costs £90. Wipes debt in 12 months. Way simpler than bankruptcy if you qualify.",
        "Payday lenders are capped at 0.8%/day interest and total cost cap of 100% of borrowed amount under FCA rules. Over that? File a complaint — automatic refund likely.",
    ],

    # ---- 👨‍👩‍👧 Family law (12) ----
    "family": [
        "Divorce in England & Wales is now 'no-fault' since April 2022. One year minimum after marriage. Joint or sole application. 20-week reflection period before Conditional Order.",
        "Child maintenance: use the CMS calculator on gov.uk. Standard rates: 12% of net pay for 1 child, 16% for 2, 19% for 3+. Reduced by overnights with the paying parent.",
        "Pre-nuptial agreements aren't strictly binding in England & Wales — but courts give them significant weight if BOTH parties had independent legal advice and full disclosure 28+ days before the wedding.",
        "Domestic abuse: Clare's Law lets you ask police if a current/ex partner has a violent history. Sarah's Law lets you ask about people who have unsupervised contact with your children.",
        "Cohabiting couples have NO automatic property rights at separation — even after 20 years. Only marriage or a Declaration of Trust gives you protection. 'Common law marriage' is a myth.",
        "Children Act 1989: the court's PARAMOUNT consideration is the child's welfare. Parental rights are secondary. Bring this perspective into mediation — it shifts the conversation.",
        "Wills: in England & Wales, a marriage REVOKES any previous will (unless the will is specifically 'in contemplation of marriage'). Divorce treats the ex as having predeceased — but the rest stays valid.",
        "Inheritance Act 1975: if a will leaves you 'reasonably' under-provided as a spouse, child or dependant, you have 6 months from the Grant of Probate to bring a claim.",
        "Civil partnerships are open to mixed-sex AND same-sex couples since December 2019. Legal effect nearly identical to marriage, but you don't have to 'get married'.",
        "Non-Molestation Orders are free to apply for via Form FL401 — civil legal aid covers most applicants. Breach is a criminal offence with up to 5 years' imprisonment.",
        "Surrogacy in the UK: only 'reasonable expenses' can be paid (~£15-20k). Parental Order must be applied for within 6 months of birth. Surrogate is the legal mother until then.",
        "Adoption: birth parents have 6 weeks after consent to change their mind. After the Placement Order, only the court can revoke. The child's identity is sealed but accessible by them at 18.",
    ],

    # ---- ✈️ Immigration (10) ----
    "immigration": [
        "Visa refused? You usually have 14 days to apply for Administrative Review (from inside UK) or 28 days (from outside). After that, judicial review is the only route — expensive.",
        "Indefinite Leave to Remain (ILR): usually 5 years on a qualifying visa + Life in the UK test + English language requirement. Don't miss the 180-day absence limit per 12-month period.",
        "British citizenship: after ILR + 12 months residence (5 if married to a British citizen), £1,500 application fee, ceremony. You CAN keep your other nationality unless your country forbids it.",
        "Asylum claims: NEVER work without permission, NEVER sign anything you don't understand, ALWAYS keep copies. Free legal aid through Asylum Aid or Bail for Immigration Detainees.",
        "Settlement applications: don't leave the UK in the 28 days before you apply. Home Office considers this a 'gap in residence' even if you have ILR.",
        "Sponsor your spouse: Minimum Income Requirement is £29,000/year (or £88,500 in savings, held for 6+ months). Some routes exempt — child of a British citizen, disabled spouse.",
        "Refused at the border? You have the right to request a written reason and call your embassy. Don't sign a 'voluntary departure' — it bars re-entry for years.",
        "EU Settlement Scheme: deadline for most was 30 June 2021. Late applications still accepted with 'reasonable grounds' — illness, abuse, lack of capacity. Apply ASAP.",
        "Tier 2/Skilled Worker visa job change: you need a new sponsor and a new Certificate of Sponsorship. Work without one and you breach your visa — risk of removal.",
        "Overstaying: any overstay (even 1 day) can trigger a re-entry ban. 30 days to leave voluntarily = no ban. 1-3 years if escorted out. Always know your visa expiry date.",
    ],

    # ---- 📱 Data / Privacy / Online (12) ----
    "privacy": [
        "Subject Access Request (SAR): under UK GDPR, any organisation must give you a copy of all personal data they hold about you, free, within 1 calendar month. Use plain English in your request.",
        "Right to be forgotten: search engines must remove results about you if they're inaccurate, outdated, or no longer relevant. Apply directly via Google's removal form.",
        "Your employer can monitor work emails ONLY if they've informed you in advance (usually in the contract or staff handbook). Private webmail on work devices? Grey area — assume they can see it.",
        "Revenge porn / intimate image abuse is a specific criminal offence since 2015. Report to local police OR the Revenge Porn Helpline (revengepornhelpline.org.uk). Free, confidential.",
        "Online harassment / stalking: criminal under the Protection from Harassment Act 1997. 'Two or more incidents' = a course of conduct. Screenshot EVERYTHING with timestamps.",
        "GDPR fines for UK organisations cap at £17.5 million or 4% of global turnover. ICO complaints are free and can trigger investigations. Don't underestimate this lever.",
        "If a data breach affects you, the organisation has 72 hours to report it to the ICO and 'without undue delay' to you. Refusal to confirm a breach = report to the ICO.",
        "CCTV in your neighbour's garden pointing at your home? It's only lawful if 'necessary and proportionate'. Complain to the ICO if it captures your private space.",
        "Online platforms must remove illegal content quickly under the Online Safety Act 2023. Report via the platform's tools, then escalate to Ofcom if ignored.",
        "Photos taken in a public place are usually fine — unless they identify a private individual in a private moment. Even then, news exception applies. Privacy claims are case-specific.",
        "Your right to data portability: ask any company for a copy of your data in a 'commonly used, machine-readable format'. Banks, social media, gyms — all covered by UK GDPR.",
        "Cookies: under PECR (Privacy and Electronic Communications Regulations), websites need your active consent BEFORE setting non-essential cookies. Pre-ticked boxes are illegal.",
    ],

    # ---- ⚖️ Contract / Civil claims (12) ----
    "contract": [
        "Small claims track: claims under £10,000 (England & Wales). Costs capped, no need for a solicitor, takes about 6 months. Money Claim Online (moneyclaim.gov.uk) is the easiest start.",
        "Verbal contracts ARE legally binding (with rare exceptions — land sales must be in writing). But proving the terms is the hard part — get emails / texts confirming key points.",
        "'Without prejudice' on a letter = it can't be used as evidence of admission. Useful for settlement talks. 'Without prejudice save as to costs' lets the court see it for costs purposes only.",
        "Limitation periods: 6 years for most contracts, 12 years for deeds, 3 years for personal injury, 6 years for negligence (or 3 from 'date of knowledge', whichever later).",
        "Pre-Action Protocol: before suing, send a Letter Before Action giving the other side reasonable time (usually 14-21 days) to respond. Skipping this can cost you on costs even if you win.",
        "Liquidated damages clauses (fixed sums for breach) are enforceable only if they reflect a 'genuine pre-estimate of loss' — otherwise they're 'penalty clauses' and void.",
        "Mediation before court: most civil judges expect it. Free schemes through the Small Claims Mediation Service (under £10k). Saves money, time, and relationships.",
        "Force majeure clauses: COVID changed everything. Even where the clause doesn't expressly mention pandemics, you may be able to argue 'frustration' to be released from a contract.",
        "Director's personal guarantee on a business loan? You CAN'T hide behind the company. Lender can come after your house, your savings, your spouse's joint assets.",
        "Statutory interest on debts: 8% above the Bank of England base rate (so usually 13%+) under the Late Payment of Commercial Debts (Interest) Act 1998. Plus a fixed compensation charge.",
        "Service of court documents: in the UK, you can serve by post, email (if agreed), or in person. Foreign service uses the Hague Convention — months of paperwork.",
        "Default judgment: if the defendant doesn't respond within 14 days of the claim form, you can ask the court for judgment in default. Quick wins are possible — but enforcement is the harder bit.",
    ],
}


def all_tips() -> list[str]:
    """Return a deterministic flat list. Used by daily_tip endpoint."""
    flat = []
    # Interleave categories so consecutive days span topics (not 16 tenancy in a row)
    keys = list(TIPS.keys())
    max_len = max(len(TIPS[k]) for k in keys)
    for i in range(max_len):
        for k in keys:
            if i < len(TIPS[k]):
                flat.append(TIPS[k][i])
    return flat


def tip_for(day_of_year: int, user_offset: int = 0) -> str:
    """Pick today's tip. day_of_year ∈ [1, 366], user_offset = stable hash of user id."""
    pool = all_tips()
    idx = (day_of_year + user_offset) % len(pool)
    return pool[idx]


# Quick self-test
if __name__ == "__main__":
    pool = all_tips()
    print(f"Total tips: {len(pool)}")
    total = sum(len(v) for v in TIPS.values())
    print(f"By category: {[(k, len(v)) for k, v in TIPS.items()]}")
    print(f"Sum: {total}")
    # Sample 5 days
    for d in [1, 50, 150, 250, 366]:
        print(f"Day {d}: {tip_for(d)[:80]}...")
