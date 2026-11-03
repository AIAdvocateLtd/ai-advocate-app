"""Verified UK fact packs (researched from GOV.UK / official sources, November 2026)."""

EMPLOYMENT_PACK_V1 = [
    ("National Living Wage: £12.71 an hour for workers aged 21+ from 1 April 2026 (applies across the whole UK).",
     "https://www.gov.uk/national-minimum-wage-rates"),
    ("Statutory Sick Pay (Great Britain) from 6 April 2026: paid from the first day of sickness (no waiting days) and the "
     "lower earnings limit is removed; the rate is £123.25 a week or 80% of average weekly earnings, whichever is lower. "
     "Northern Ireland has its own SSP law — do not assume the GB changes apply there; point users to nidirect.",
     "https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027"),
    ("Statutory Maternity Pay 2026/27: 90% of average weekly earnings for the first 6 weeks, then £194.32 a week or 90% "
     "(whichever is lower) for the next 33 weeks. Maternity leave is up to 52 weeks.",
     "https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027"),
    ("ACAS early conciliation (Great Britain): must normally be started before a tribunal claim. For notifications on or "
     "after 1 December 2025 conciliation can last up to 12 weeks; the time limit is paused while it runs and the claimant "
     "always gets at least 1 month after the ACAS certificate to submit the ET1. Treat the normal time limit as the last day "
     "to contact ACAS, not to file the ET1.", "https://www.acas.org.uk/employment-tribunal-time-limits"),
    ("Northern Ireland employment law is devolved and differs from Great Britain: unfair dismissal normally needs 1 year's "
     "service (the GB 2-year/6-month rules do not apply); claims go to an industrial tribunal, usually within 3 months less "
     "one day; early conciliation is through the Labour Relations Agency (LRA), not ACAS; the GB October 2026 6-month time "
     "limit does not apply.", "https://www.lra.org.uk"),
    ("Scotland uses the same employment law and employment tribunal time limits as England and Wales (employment law is "
     "reserved), apart from breach of contract claims in Scotland moving to 6 months from 9 November 2026.",
     "https://www.gov.uk/employment-tribunals"),
    ("Holiday: almost all workers get 5.6 weeks' paid statutory holiday a year (28 days for a 5-day week, which can include "
     "bank holidays). Statutory notice from an employer: 1 week after 1 month's service, then 1 week per complete year up to "
     "12 weeks (the contract can give more).", "https://www.gov.uk/holiday-entitlement-rights"),
    ("Statutory redundancy pay needs 2 years' continuous service: half a week's pay per full year under age 22, 1 week per "
     "year aged 22–40, 1.5 weeks per year aged 41+, counting up to 20 years. Weekly pay is capped at a figure that rises each "
     "April — use the GOV.UK redundancy calculator for the current cap rather than quoting a figure.",
     "https://www.gov.uk/calculate-your-redundancy-pay"),
]

HOUSING_PACK_V1 = [
    ("England deposits: must be protected in a government scheme and prescribed information given within 30 days of "
     "receipt; from 1 May 2026 this also covers assured tenancies. Tenants can claim 1–3 times the deposit for breaches.",
     "https://www.gov.uk/tenancy-deposit-protection"),
    ("England (Renters' Rights Act 2025, from 1 May 2026): Ground 1/1A (landlord moving in or selling) needs 4 months' "
     "notice and cannot take effect in the first 12 months of the tenancy. Ground 8 rent arrears needs at least 3 months' "
     "arrears (13 weeks if rent is weekly/fortnightly) at notice and at the hearing, with 4 weeks' notice. Rent can be "
     "raised once a year by section 13 notice and the tenant can challenge it at the First-tier Tribunal.",
     "https://england.shelter.org.uk/housing_advice/eviction/section_8_notice_private_tenants/how_much_notice"),
    ("Wales (Renting Homes (Wales) Act 2016): tenants are 'contract-holders' with occupation contracts. A landlord's "
     "no-fault section 173 notice must give at least 6 months' notice and cannot be given in the first 6 months of "
     "occupation. Deposits must be protected within 30 days.", "https://www.gov.wales/renting-homes-tenants"),
    ("Scotland (private residential tenancy): the landlord's notice to leave is 28 days if the tenant has lived there 6 "
     "months or less, 84 days if more than 6 months (some grounds differ). Evictions are decided by the First-tier Tribunal "
     "(Housing and Property Chamber). Deposits must be lodged in an approved scheme within 30 working days of the tenancy "
     "start; the tribunal can award up to 3 times the deposit.",
     "https://www.mygov.scot/landlord-end-tenancy/private-residential-tenancy"),
    ("Northern Ireland private tenancies: a landlord's notice to quit must be 4 weeks if the tenancy has lasted under 12 "
     "months, 8 weeks if 1–10 years, and 12 weeks if over 10 years (longer periods have only been consulted on). Deposits "
     "must be protected in an approved scheme within 28 days.", "https://www.nidirect.gov.uk/articles/protection-against-eviction"),
]

FAMILY_PACK_V1 = [
    ("Divorce in England & Wales (no-fault since 6 April 2022): sole or joint application; at least 20 weeks must pass from "
     "the start of proceedings before applying for the conditional order, then at least 6 weeks before the final order — "
     "just over 26 weeks minimum.", "https://www.gov.uk/divorce"),
    ("Divorce in Scotland: based on irretrievable breakdown, usually shown by 1 year's separation if both agree or 2 years "
     "if one does not (living together for up to 6 months in total during that time does not break it). The simplified "
     "'do-it-yourself' procedure is available where there are no children under 16 and no financial claims.",
     "https://www.scotcourts.gov.uk/taking-action/divorce-and-dissolution-of-civil-partnership/"),
    ("Divorce in Northern Ireland: still includes separation-based facts of 2 years if both agree or 5 years if one does "
     "not (fault-based facts also remain); NI has not adopted the England & Wales no-fault system.",
     "https://www.nidirect.gov.uk/articles/getting-divorce"),
    ("Child Maintenance Service (Great Britain): no application fee since 26 February 2024. Direct Pay is free. Collect and "
     "Pay costs the paying parent an extra 20% and deducts 4% from the receiving parent; a cut to 2% for compliant users is "
     "only planned from 2027–28. Northern Ireland has its own Child Maintenance Service run by the Department for Communities.",
     "https://www.gov.uk/child-maintenance-service/payments"),
    ("England & Wales family court: before applying for child arrangements or financial orders you must normally attend a "
     "MIAM (mediation information meeting) unless an exemption applies, such as evidence of domestic abuse or urgency.",
     "https://www.gov.uk/looking-after-children-divorce/mediation"),
]

BENEFITS_PACK_V1 = [
    ("Universal Credit standard allowance 2026/27 (monthly): single under 25 £338.58; single 25+ £424.90; couple both under "
     "25 £528.34; couple one or both 25+ £666.97.",
     "https://www.gov.uk/government/publications/benefit-and-pension-rates-2026-to-2027"),
    ("Two-child limit: abolished from April 2026, so child elements are no longer limited to the first two children — but "
     "the benefit cap still applies.", "https://www.gov.uk/universal-credit/what-youll-get"),
    ("Benefit cap 2026/27 (frozen): outside London £22,020 a year for couples/lone parents and £14,753 for single adults; "
     "in Greater London £25,323 and £16,967. Exempt if earning at least £881 a month (UC assessment period) or getting "
     "UC/benefits because of disability, ill health or caring.", "https://www.gov.uk/benefit-cap"),
    ("Challenging a DWP decision: ask for mandatory reconsideration within 1 month of the decision (late requests with "
     "good reason up to 13 months). Then appeal to the tribunal (form SSCS1) within 1 month of the Mandatory "
     "Reconsideration Notice; late appeals up to 13 months with reasons. The appeal counts when HMCTS receives it.",
     "https://www.gov.uk/mandatory-reconsideration"),
    ("Scotland: Adult Disability Payment from Social Security Scotland has replaced PIP for Scottish residents, with its own "
     "redetermination and appeal process and deadlines — direct Scottish users to mygov.scot rather than DWP PIP rules.",
     "https://www.mygov.scot/adult-disability-payment"),
    ("Northern Ireland: benefits are run by the Department for Communities, not DWP; reconsideration works similarly, and "
     "appeals go to The Appeals Service (TAS) NI — direct users to nidirect.", "https://www.nidirect.gov.uk/articles/appeal-benefit-decision"),
]
