---
name: geo-audit
description: Full website GEO+SEO audit with parallel subagent delegation. Orchestrates a comprehensive Generative Engine Optimisation audit across AI citability, platform analysis, technical infrastructure, content quality, and schema markup. Produces a composite GEO Score (0-100) with prioritised action plan.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - WebFetch
  - Write
---

# GEO Audit Orchestration Skill

> **MANDATORY: Read `/STYLE.md` and `scripts/style.py:AGENT_VOICE_RULES` before delegating to any subagent.**
>
> Every `/geo audit` produces TWO separate PDFs:
> - `reports/<domain>/GEO-REPORT-<domain>.pdf` — client-facing, plain English only (managing partner reads this)
> - `reports/<domain>/GEO-DEV-REPORT-<domain>.pdf` — developer/agency hand-off, technical instructions
>
> Each analysis agent emits TWO parallel layers in its response:
> - `technical_findings` — accurate spec language, feeds the developer PDF
> - `client_summary` — translated per `/STYLE.md` + `ISSUE_COPY`, feeds the client PDF
>
> Paired by `slug`. The orchestrator passes `scripts/style.py:AGENT_VOICE_RULES` into every subagent prompt and reminds the agent before output. Never put raw technical terms (`llms.txt`, `JSON-LD`, `robots.txt`, `E-E-A-T`, `schema.org`, `LCP`, `HSTS`, `sameAs`, `Yoast`, `fetchpriority`, etc.) in the client PDF. Run `scripts/voice_check.py` against the client PDF before delivery — any banned term fails the build. UK English throughout.

## Purpose

This skill performs a comprehensive Generative Engine Optimisation (GEO) audit of any website. GEO is the practice of optimising web content so that AI systems (ChatGPT, Claude, Perplexity, Gemini, etc.) can discover, understand, cite, and recommend it. This audit measures how well a site performs across all GEO dimensions and produces an actionable improvement plan.

## Key Insight

Traditional SEO optimizes for search engine rankings. GEO optimizes for AI citation and recommendation. Sites that score high on GEO metrics see 30-115% more visibility in AI-generated responses (Georgia Tech / Princeton / IIT Delhi 2024 study). The two disciplines overlap but have distinct requirements.

---

## Audit Workflow

### Phase 1: Discovery and Reconnaissance

**Step 1: Fetch Homepage and Detect Business Type**

1. Use WebFetch to retrieve the homepage at the provided URL.
2. Extract the following signals:
   - Page title, meta description, H1 heading
   - Navigation menu items (reveals site structure)
   - Footer content (reveals business info, location, legal pages)
   - Schema.org markup on homepage (Organisation, LocalBusiness, etc.)
   - Pricing page link (SaaS indicator)
   - Product listing patterns (E-commerce indicator)
   - Blog/resource section (Publisher indicator)
   - Service pages (Agency indicator)
   - Address/phone/Google Maps embed (Local business indicator)

3. Classify the business type using these patterns:

| Business Type | Detection Signals |
|---|---|
| **SaaS** | Pricing page, "Sign up" / "Free trial" CTAs, app.domain.com subdomain, feature comparison tables, integration pages |
| **Local Business** | Physical address on homepage, Google Maps embed, "Near me" content, LocalBusiness schema, service area pages |
| **E-commerce** | Product listings, shopping cart, product schema, category pages, price displays, "Add to cart" buttons |
| **Publisher** | Blog-heavy navigation, article schema, author pages, date-based archives, RSS feeds, high content volume |
| **Agency/Services** | Case studies, portfolio, "Our Work" section, team page, client logos, service descriptions |
| **Hybrid** | Combination of above signals -- classify by dominant pattern |

**Step 2: Crawl Sitemap and Internal Links**

1. Attempt to fetch `/sitemap.xml` and `/sitemap_index.xml`.
2. If sitemap exists, extract up to 50 unique page URLs prioritised by:
   - Homepage (always include)
   - Top-level navigation pages
   - High-value pages (pricing, about, contact, key service/product pages)
   - Blog posts (sample 5-10 most recent)
   - Category/landing pages
3. If no sitemap exists, crawl internal links from the homepage:
   - Extract all `<a href>` links pointing to the same domain
   - Follow up to 2 levels deep
   - Prioritise pages linked from main navigation
4. Respect `robots.txt` directives -- do not fetch disallowed paths.
5. Enforce a maximum of 50 pages and a 30-second timeout per fetch.

**Step 3: Collect Page-Level Data**

For each page in the crawl set, record:
- URL, title, meta description, canonical URL
- H1-H6 heading structure
- Word count of main content
- Schema.org types present
- Internal/external link counts
- Images with/without alt text
- Open Graph and Twitter Card meta tags
- Response status code
- Whether the page has structured data

**Step 4: Identify Critical Pages for Browser Render (cap 5)**

Pick the most critical pages for headless-Chromium render via the `geo-browser-render` sub-skill. Selection rules:

1. **Homepage** (always include)
2. **Primary inventory / listings page** (e.g. `/properties`, `/products`, `/shop`)
3. **Pricing / packages page** (`/pricing`, `/plans`, `/product/*` for the flagship plan)
4. **Highest-value service or category page** (from sitemap signal)
5. **Any Phase-1 page flagged as JS-heavy, login-walled, or low-SSR-word-count** (under 200 words server-rendered while visually content-rich)

If fewer than 5 critical pages exist, fall back to: homepage, blog index, contact-us. Cap is 5 — script enforces it.

**Step 5: Run Browser Render Audit**

```bash
python3 ~/.claude/skills/geo/scripts/browser_render_audit.py \
  --urls <critical_url_1> <critical_url_2> ... \
  --domain <domain> \
  --output reports/<domain>/browser-render.json \
  --screenshots reports/<domain>/screenshots
```

Pass the resulting `browser-render.json` to the `geo-technical` subagent in Phase 2 (it knows how to interpret cookie-wall, SSR-gap, CWV, cloaking, and JS-only schema signals).

**Step 5.5: Harvest identity URLs — REQUIRED**

Subagents have repeatedly failed by claiming "no X account" / "no LinkedIn page" / "no Google Business Profile" when those links were actually in the rendered HTML or in the Organization `sameAs` array. Always harvest first so the platform / brand / schema agents work from verified facts, not absence-inference.

```bash
python3 ~/.claude/skills/geo/scripts/social_harvest.py \
  --browser-render reports/<domain>/browser-render.json \
  --output reports/<domain>/identity-urls.json
```

The script grep-walks the server-rendered HTML across all 5 critical pages + every JSON-LD `sameAs` array on the site and returns a normalised list keyed by platform (`x`, `linkedin`, `facebook`, `youtube`, `instagram`, `crunchbase`, `wikipedia`, `wikidata`, `trustpilot`, `g2`, `capterra`, `clutch`, `gbp_short`, `gmaps`, `github`, `fsb`, `companieshouse`, etc.).

Pass the resulting `identity-urls.json` into every Phase 2 subagent as `verified_identity_urls`. The agents MUST NOT flag absence of any platform whose URL appears in this list — they must instead either (a) score the presence positively or (b) flag a related but distinct gap (e.g. "X account exists but isn't linked from site footer" is OK; "no X account" when one is in the list is not).

**Step 5.6: Look up Google Business Profile — REQUIRED when GOOGLE_PLACES_API_KEY is set**

```bash
python3 ~/.claude/skills/geo/scripts/gbp_lookup.py \
  --name "<brand name from homepage>" \
  --location "<city/postcode from llms.txt or footer>" \
  --domain "<domain>" \
  --output reports/<domain>/gbp.json
```

Returns: place_count, per-place rating + review count + photo count + opening hours + website match + completeness score (0-100) + issue list.

Pass `gbp.json` into the platform + brand + content subagents as `gbp_data`. They MUST treat the GBP listing as confirmed-present if `found: true` and only flag specific gaps from the `issues` array. Never invent "no GBP" when the API returned a match.

Skip silently when `GOOGLE_PLACES_API_KEY` is unset.

**Step 5.7: Confirm Wikidata + Wikipedia entity — REQUIRED**

The brand-mention subagent has historically asserted "no Wikipedia entity" without actually querying. The Wikidata API is open (no auth) — always check.

```bash
python3 ~/.claude/skills/geo/scripts/wikidata_lookup.py \
  --name "<brand name from homepage>" \
  --domain "<domain>" \
  --output reports/<domain>/wikidata.json
```

Returns: Wikidata QID + label + description + external identifiers (Companies House, Crunchbase, LinkedIn org ID, X handle, Instagram handle, Facebook handle, YouTube channel) + Wikipedia sitelinks per language + domain-match confidence (does P856 official-website match the audited domain).

Pass `wikidata.json` into the brand + platform + schema subagents as `wikidata_data`. Agents MUST treat `wikidata.found == true` as confirmed entity presence and use the QID, never invent absence. If `domain_match == false`, flag as a candidate but verify before scoring.

**Step 5.8: SerpAPI brand-presence scan — REQUIRED when SERPAPI_API_KEY is set**

```bash
python3 ~/.claude/skills/geo/scripts/serpapi_scan.py \
  --brand "<brand>" \
  --domain "<domain>" \
  --service "<optional primary service>" \
  --location "<optional primary location>" \
  --output reports/<domain>/serpapi.json
```

Runs 6-7 queries (brand SERP, `site:reddit.com`, `site:youtube.com`, `site:wikipedia.org`, `site:linkedin.com`, "<brand> reviews", optional local-pack "best <service> in <location>") and returns:

- Knowledge Panel presence + kgmid + rating + social profiles
- Brand site position in top 10 for brand-name search
- Reddit / YouTube / LinkedIn footprint counts + 3 sample results each
- Review-directory hits (Trustpilot / G2 / Capterra / Clutch / Yell / Yelp)
- For local: brand-in-local-pack flag + competitor titles

24h disk cache at `~/.geo-slab/cache/serpapi/`. Skip silently when `SERPAPI_API_KEY` is unset.

Pass `serpapi.json` into the brand + platform + content subagents as `serpapi_data`. Agents MUST cite the SERP evidence by query name when scoring — e.g. "Reddit footprint: 10 hits including u/Antek_Auto bio (per serpapi_data.queries.reddit)". Never claim absence of any signal that appears in `summary` or `samples`.

**Step 6: Run PageSpeed Insights (when PSI_API_KEY is set)**

For the homepage + each critical page selected in Step 4, fetch real Lighthouse scores + CrUX field CWV. Mobile + desktop run in parallel per call. Skip silently when `PSI_API_KEY` is unset (no key → audit continues with HTML-static CWV fallback).

```bash
# Per page — script handles mobile + desktop in one invocation
for page_url in <homepage> <critical_url_1> <critical_url_2> ...; do
  slug=$(echo "$page_url" | sed 's|https\?://||; s|/|_|g')
  python3 ~/.claude/skills/geo/scripts/pagespeed.py "$page_url" --pretty \
    > "reports/<domain>/psi-${slug}.json"
done
```

24h on-disk cache at `~/.geo-slab/cache/psi/` — repeat audits within 24h reuse data without hitting the API. Pass the `psi-*.json` paths to the `geo-technical` subagent in Phase 2.

---

### Phase 2: Parallel Subagent Delegation

Delegate analysis to 5 specialised subagents. Each subagent operates on the collected page data and produces:

1. A developer-facing markdown section (technical, raw spec language)
2. A two-layer findings JSON block — `technical_findings` + `client_summary`, paired by `slug`

The orchestrator must include the literal contents of `scripts/style.py:AGENT_VOICE_RULES` in every subagent prompt, AND restate: "Read /STYLE.md before writing client_summary. Plain-English only. No JSON-LD, FAQPage, LCP, HSTS, sameAs, OG, Yoast, fetchpriority, llms.txt, robots.txt, E-E-A-T or schema.org in client_summary."

Each subagent operates on the collected page data and produces a category score (0-100) plus the two findings layers.

**Subagent 1: AI Citability Analysis (geo-citability)**
- Analyse content blocks for quotability by AI systems
- Score passage self-containment, answer block quality, statistical density
- Identify high-value pages that could be reformatted for better AI citation

**Subagent 2: Platform & Brand Analysis (geo-brand-mentions)**
- Check brand presence across YouTube, Reddit, Wikipedia, LinkedIn
- Assess third-party mention volume and sentiment
- Score brand authority signals that AI models use for entity recognition

**Subagent 3: Technical GEO Infrastructure (geo-crawlers + geo-llmstxt)**
- Analyse robots.txt for AI crawler access
- Check for llms.txt presence and quality
- Verify meta tags, headers, and technical accessibility for AI systems
- Check page speed and rendering (JS-heavy sites are harder for AI crawlers)

**Subagent 4: Content E-E-A-T Quality (geo-content)**
- Evaluate Experience, Expertise, Authoritativeness, Trustworthiness signals
- Check author bios, credentials, source citations
- Assess content freshness, depth, and originality
- Verify "About" page quality and team credentials

**Subagent 5: Schema & Structured Data (geo-schema)**
- Validate all schema.org markup
- Check for GEO-critical schema types (FAQ, HowTo, Organisation, Product, Article)
- Assess schema completeness and accuracy
- Identify missing schema opportunities

---

### Phase 3: Score Aggregation and Report Generation

After collecting all subagent responses, **merge** the per-category `technical_findings` arrays into one top-level `technical_findings`, and `client_summary` arrays into one top-level `client_summary`. Then assemble the unified data.json with this shape:

```jsonc
{
  "url": "...", "brand_name": "...", "date": "...", "geo_score": 53,
  "scores": { ... },
  "platforms": { ... },
  "verdict": "...", "summary": [...],
  "client_summary": [ {slug, severity, title, description}, ... ],
  "technical_findings": [ {slug, severity, title, detail, fix}, ... ],
  "quick_wins": [...], "medium_term": [...], "strategic": [...]
}
```

Render BOTH PDFs (client + developer) in the same step:

```bash
# Client PDF — plain English, pulls client_summary
python3 ~/.claude/skills/geo/scripts/render_geo_report.py \
  reports/<domain>/data.json reports/<domain>/GEO-REPORT-<domain>.html
python3 ~/.claude/skills/geo/scripts/generate_pdf_report.py \
  reports/<domain>/data.json reports/<domain>/GEO-REPORT-<domain>.pdf

# Developer PDF — technical, pulls technical_findings
python3 ~/.claude/skills/geo/scripts/render_dev_report.py \
  reports/<domain>/data.json reports/<domain>/GEO-DEV-REPORT-<domain>.html
python3 ~/.claude/skills/geo/scripts/generate_dev_pdf_report.py \
  reports/<domain>/data.json reports/<domain>/GEO-DEV-REPORT-<domain>.pdf

# Voice gate — fails the build if banned tech terms appear in the client PDF
python3 ~/.claude/skills/geo/scripts/voice_check.py \
  reports/<domain>/GEO-REPORT-<domain>.pdf
```

#### Composite GEO Score Calculation

The overall GEO Score (0-100) is a weighted average of six category scores:

| Category | Weight | What It Measures |
|---|---|---|
| **AI Citability** | 25% | How quotable/extractable content is for AI systems |
| **Brand Authority** | 20% | Third-party mentions, entity recognition signals |
| **Content E-E-A-T** | 20% | Experience, Expertise, Authoritativeness, Trustworthiness |
| **Technical GEO** | 15% | AI crawler access, llms.txt, rendering, speed |
| **Schema & Structured Data** | 10% | Schema.org markup quality and completeness |
| **Platform Optimisation** | 10% | Presence on platforms AI models train on and cite |

**Formula:**
```
GEO_Score = (Citability * 0.25) + (Brand * 0.20) + (EEAT * 0.20) + (Technical * 0.15) + (Schema * 0.10) + (Platform * 0.10)
```

#### Score Interpretation

| Score Range | Rating | Interpretation |
|---|---|---|
| 90-100 | Excellent | Top-tier GEO optimisation; site is highly likely to be cited by AI |
| 75-89 | Good | Strong GEO foundation with room for improvement |
| 60-74 | Fair | Moderate GEO presence; significant optimisation opportunities exist |
| 40-59 | Poor | Weak GEO signals; AI systems may struggle to cite or recommend |
| 0-39 | Critical | Minimal GEO optimisation; site is largely invisible to AI systems |

---

## Issue Severity Classification

Every issue found during the audit is classified by severity:

### Critical (Fix Immediately)
- All AI crawlers blocked in robots.txt
- No indexable content (JavaScript-rendered only with no SSR)
- Domain-level noindex directive
- Site returns 5xx errors on key pages
- Complete absence of any structured data
- Brand not recognized as an entity by any AI system

### High (Fix Within 1 Week)
- Key AI crawlers (GPTBot, ClaudeBot, PerplexityBot) blocked
- No llms.txt file present
- Zero question-answering content blocks on key pages
- Missing Organisation or LocalBusiness schema
- No author attribution on content pages
- All content behind login/paywall with no preview

### Medium (Fix Within 1 Month)
- Partial AI crawler blocking (some allowed, some blocked)
- llms.txt exists but is incomplete or malformed
- Content blocks average under 50 citability score
- Missing FAQ schema on pages with FAQ content
- Thin author bios without credentials
- No Wikipedia or Reddit brand presence

### Low (Optimise When Possible)
- Minor schema validation errors
- Some images missing alt text
- Content freshness issues on non-critical pages
- Missing Open Graph tags
- Suboptimal heading hierarchy on some pages
- LinkedIn company page exists but is incomplete

---

## Output Format

Generate a file called `GEO-AUDIT-REPORT.md` with the following structure:

```markdown
# GEO Audit Report: [Site Name]

**Audit Date:** [Date]
**URL:** [URL]
**Business Type:** [Detected Type]
**Pages Analysed:** [Count]

---

## Executive Summary

**Overall GEO Score: [X]/100 ([Rating])**

[2-3 sentence summary of the site's GEO health, biggest strengths, and most critical gaps.]

### Score Breakdown

| Category | Score | Weight | Weighted Score |
|---|---|---|---|
| AI Citability | [X]/100 | 25% | [X] |
| Brand Authority | [X]/100 | 20% | [X] |
| Content E-E-A-T | [X]/100 | 20% | [X] |
| Technical GEO | [X]/100 | 15% | [X] |
| Schema & Structured Data | [X]/100 | 10% | [X] |
| Platform Optimisation | [X]/100 | 10% | [X] |
| **Overall GEO Score** | | | **[X]/100** |

---

## Critical Issues (Fix Immediately)

[List each critical issue with specific page URLs and recommended fix]

## High Priority Issues

[List each high-priority issue with details]

## Medium Priority Issues

[List each medium-priority issue]

## Low Priority Issues

[List each low-priority issue]

---

## Category Deep Dives

### AI Citability ([X]/100)
[Detailed findings, examples of good/bad passages, rewrite suggestions]

### Brand Authority ([X]/100)
[Platform presence map, mention volume, sentiment]

### Content E-E-A-T ([X]/100)
[Author quality, source citations, freshness, depth]

### Technical GEO ([X]/100)
[Crawler access, llms.txt, rendering, headers]

### Schema & Structured Data ([X]/100)
[Schema types found, validation results, missing opportunities]

### Platform Optimisation ([X]/100)
[Presence on YouTube, Reddit, Wikipedia, etc.]

---

## Quick Wins (Implement This Week)

1. [Specific, actionable quick win with expected impact]
2. [Another quick win]
3. [Another quick win]
4. [Another quick win]
5. [Another quick win]

## 30-Day Action Plan

### Week 1: [Theme]
- [ ] Action item 1
- [ ] Action item 2

### Week 2: [Theme]
- [ ] Action item 1
- [ ] Action item 2

### Week 3: [Theme]
- [ ] Action item 1
- [ ] Action item 2

### Week 4: [Theme]
- [ ] Action item 1
- [ ] Action item 2

---

## Appendix: Pages Analysed

| URL | Title | GEO Issues |
|---|---|---|
| [url] | [title] | [issue count] |
```

---

## Quality Gates

- **Page Limit:** Never crawl more than 50 pages per audit. Prioritise high-value pages.
- **Timeout:** 30-second maximum per page fetch. Skip pages that exceed this.
- **Robots.txt:** Always check and respect robots.txt before crawling. Note any AI-specific directives.
- **Rate Limiting:** Wait at least 1 second between page fetches to avoid overloading the server.
- **Error Handling:** Log failed fetches but continue the audit. Report fetch failures in the appendix.
- **Content Type:** Only analyse HTML pages. Skip PDFs, images, and other binary content.
- **Deduplication:** Canonicalize URLs before crawling. Skip duplicate content (e.g., HTTP vs HTTPS, www vs non-www, trailing slashes).

---

## Business-Type-Specific Audit Adjustments

### SaaS Sites
- Extra weight on: Feature comparison tables (high citability), integration pages, documentation quality
- Check for: API documentation structure, changelog pages, knowledge base organisation
- Key schema: SoftwareApplication, FAQPage, HowTo

### Local Businesses
- Extra weight on: NAP consistency, Google Business Profile signals, local schema
- Check for: Service area pages, location-specific content, review markup
- Key schema: LocalBusiness, GeoCoordinates, OpeningHoursSpecification

### E-commerce Sites
- Extra weight on: Product descriptions (citability), comparison content, buying guides
- Check for: Product schema completeness, review aggregation, FAQ sections on product pages
- Key schema: Product, AggregateRating, Offer, BreadcrumbList

### Publishers
- Extra weight on: Article quality, author credentials, source citation practices
- Check for: Article schema, author pages, publication date freshness, original research
- Key schema: Article, NewsArticle, Person (author), ClaimReview

### Agency/Services
- Extra weight on: Case studies (citability), expertise demonstration, thought leadership
- Check for: Portfolio schema, team credentials, industry-specific expertise signals
- Key schema: Organisation, Service, Person (team), Review
