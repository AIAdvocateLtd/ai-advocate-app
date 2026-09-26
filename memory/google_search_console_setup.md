# Google Search Console Setup — AI Advocate

Get your site indexed properly + start tracking Google search performance.
Total time: ~15 minutes.

---

## Step 1 — Create the property (2 min)

1. Go to https://search.google.com/search-console
2. Sign in with the Google account you want to own this property (recommend: a business/founder account, not personal)
3. Top-left, click **"Add property"**
4. Choose **"Domain"** property (not URL prefix) — this covers `aiadvocate.co.uk`, `www.aiadvocate.co.uk`, `https://`, `http://`, everything at once
5. Enter: `aiadvocate.co.uk` (no https://, no www)
6. Click **Continue**

## Step 2 — Verify ownership via DNS (5 min)

Google will show you a TXT record like:
```
google-site-verification=YourUniqueCodeHere
```

You add this to your DNS provider (wherever you bought the domain — Cloudflare, GoDaddy, Namecheap, etc.):

### If your DNS is at Cloudflare
1. Log in to Cloudflare → click aiadvocate.co.uk
2. Left sidebar → **DNS → Records**
3. Click **"Add record"**
4. Type: **TXT**
5. Name: **@** (or leave blank — means root)
6. Content: **paste the exact string Google gave you** (starts with `google-site-verification=`)
7. TTL: Auto
8. Save

### If your DNS is at GoDaddy
1. My Products → aiadvocate.co.uk → **DNS**
2. Add → **TXT**
3. Host: **@**
4. TXT Value: **paste the exact string**
5. Save

Wait 5-10 minutes for DNS to propagate, then back in Search Console click **Verify**.

## Step 3 — Submit your sitemap (2 min)

Once verified:
1. Left sidebar → **Sitemaps**
2. Under "Add a new sitemap" enter: `sitemap.xml`
3. Click **Submit**
4. Status will say "Success" within 24 hours

## Step 4 — Request indexing of key pages (3 min)

Speed up Google noticing your best pages:
1. Top search bar → paste `https://aiadvocate.co.uk/`
2. Click "Request indexing"
3. Wait ~1 min for the check
4. Repeat for: `/welcome.html`, `/for-organisations.html`, and any blog posts you add

## Step 5 — Also set up Bing Webmaster Tools (5 min)

10% of UK search traffic — worth doing:
1. Go to https://www.bing.com/webmasters
2. Sign in with Microsoft account
3. **Import from Google Search Console** (Bing has 1-click import — saves reverifying)
4. Or add manually, same DNS TXT approach

---

## What to watch for after 2-4 weeks

Once Google has indexed your site (usually 5-10 days), check:

- **Performance report** — shows every search query people used to find you, positions, clicks, impressions
- **Coverage report** — pages successfully indexed vs pages with errors
- **Core Web Vitals** — page speed / mobile UX scores (Google ranks fast sites higher)
- **Manual actions** — if Google penalised you (rare, but check monthly)

## Quick SEO wins from Search Console data

1. Once you see which queries you're already ranking for (positions 5-20), write more content targeting those exact queries → move them into positions 1-3
2. Any queries in positions 1-3 with low CTR → your title/description isn't compelling. Rewrite them.
3. Check "Referring domains" — every backlink you earn shows here. Contact those sites to build relationships.

## Bonus tools to install (all free)

- **Ahrefs Webmaster Tools** (free version) — competitor backlink analysis
- **Ubersuggest** or **AnswerThePublic** — keyword research
- **PageSpeed Insights** — https://pagespeed.web.dev/ — check Core Web Vitals

## When to expect results

- **Week 1-2**: Google discovers and indexes your pages
- **Week 3-6**: Long-tail queries start ranking (positions 30-50 typically)
- **Month 2-4**: With consistent content + backlinks, long-tail keywords climb to positions 5-15
- **Month 6+**: Domain authority builds, some primary keywords (e.g. "AI lawyer UK") become achievable

---

**Rule of thumb**: SEO is a compounding investment. First 2 months feel slow. Month 6 onwards, traffic doubles every quarter if you're consistent.
