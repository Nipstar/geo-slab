# Scoring Methodology

How GEO SLAB computes the composite GEO Score (0–100).

## Composite formula

```
GEO_Score = (Citability  × 0.25)
          + (Brand       × 0.20)
          + (EEAT        × 0.20)
          + (Technical   × 0.15)
          + (Schema      × 0.10)
          + (Platform    × 0.10)
```

Each category itself returns a 0–100 score. Categories are weighted because they correlate differently with AI citation outcomes (brand mentions show ~3× the correlation with AI visibility that backlinks do — Ahrefs Dec 2025).

## Weight table

| Category | Weight | Sub-skill | Source signals |
|----------|--------|-----------|----------------|
| AI Citability & Visibility | 25% | `geo-citability` | Passage word count, fact density, self-containment, structure (headings, lists), AI crawler access |
| Brand Authority Signals | 20% | `geo-brand-mentions` | Mentions on Reddit, YouTube, Wikipedia, LinkedIn, X/Twitter, Quora; Google Business Profile presence; entity SERP features |
| Content Quality & E-E-A-T | 20% | `geo-content` | Author bylines, credentials, original data, freshness, readability, AI-generated content signals |
| Technical Foundations | 15% | `geo-technical` | Core Web Vitals (INP), SSR, robots.txt, sitemap, canonical, mobile responsiveness, HTTPS |
| Structured Data | 10% | `geo-schema` | JSON-LD presence, schema completeness, validation errors, rich-result eligibility |
| Platform Optimization | 10% | `geo-platform-optimizer` | Per-platform readiness across 9 AI platforms |

## Per-category scoring

### AI Citability (25%)

`scripts/citability_scorer.py` scores each content block against a citation-readiness rubric:

- **Passage length**: optimal 134–167 words. Shorter passages lack context; longer passages dilute fact density. Score peaks in this band.
- **Self-containment**: passage answers a discrete question without prior context.
- **Fact density**: ratio of concrete claims (numbers, dates, named entities) to filler.
- **Structure signals**: prefaced by clear heading; uses lists / tables for enumerable info; bolds key terms.
- **Crawler access**: `geo-crawlers` checks robots.txt for 14+ AI bots. Blocked = floor on score.

Final score = mean of top 20 scoring passages, weighted by structural quality.

### Brand Authority (20%)

`scripts/brand_scanner.py` checks for brand mentions across platforms AI models are known to retrieve from:

- Reddit (subreddit mentions, upvote-weighted)
- YouTube (channel + mention count)
- Wikipedia (article presence, citation count)
- LinkedIn (company page activity)
- X/Twitter (verified mentions, recent activity)
- Quora (answers referencing brand)
- Hacker News, Product Hunt, G2, Trustpilot (where relevant)
- Google Business Profile (rating, review count, categories) via Google Places API

Optional SerpAPI integration adds direct SERP feature detection (Knowledge Graph, "people also ask" appearances).

### Content E-E-A-T (20%)

`geo-content` evaluates Experience, Expertise, Authoritativeness, Trustworthiness:

- **Experience**: first-person language, original screenshots, case-study-specific data
- **Expertise**: author credentials in byline, schema `Person.knowsAbout`
- **Authoritativeness**: domain authority signals, inbound citations, "as featured in"
- **Trustworthiness**: HTTPS, privacy policy, contact page, transparent ownership

Plus AI-generated content detection (perplexity / burstiness signals), readability (Flesch-Kincaid), freshness (last-modified vs publication date).

### Technical (15%)

`geo-technical` checks:

- Core Web Vitals: LCP, CLS, INP (replaces FID since March 2024)
- Server-side rendering vs client-side hydration (AI crawlers prefer SSR)
- Crawlability: robots.txt sanity, sitemap.xml validity, canonical tags, hreflang
- Indexability: noindex misuse, redirect chains, 404s
- Security: HTTPS, HSTS, valid certificates
- Mobile: responsive design, viewport meta

### Structured Data (10%)

`geo-schema` detects, validates, and recommends JSON-LD:

- Presence: any schema at all
- Completeness: required + recommended fields populated
- Validation: Schema.org compliance, no syntax errors
- Coverage: appropriate types for business (Organization, LocalBusiness, Product, Article, FAQPage, etc.)
- AI-specific: `sameAs` linking entity profiles, `speakable` for voice answers

Templates in [`schema/`](../schema/) ship as starting points: organization, local-business, article-author, software-saas, product-ecommerce, website-searchaction.

### Platform Optimization (10%)

`geo-platform-optimizer` scores readiness for each of the 9 supported AI platforms separately, then averages:

| Platform | Key signal |
|----------|-----------|
| Google AI Overviews | SSR, FAQ schema, featured-snippet patterns |
| ChatGPT (browse mode) | Bing-crawlable, recent content |
| Perplexity | Citation-friendly URL structure, fact-rich passages |
| Gemini | Google ecosystem signals (GBP, schema) |
| Bing Copilot | Bing index presence, BingBot allowed |
| Grok (xAI) | X/Twitter presence, recent crawl |
| DeepSeek | Open web crawl, multilingual |
| Meta AI | Facebook/Instagram entity presence |
| Mistral (Le Chat) | EU-friendly, multilingual |

## Tier thresholds

GEO Score maps to action tier:

| Tier | Score | What it means |
|------|-------|--------------|
| **Good** | ≥ 80 | Maintain + monitor. Already discoverable to AI; tune for share-of-voice. |
| **Moderate** | 60–79 | Optimization opportunity. Address weakest 1–2 categories first. |
| **Poor** | 40–59 | Significant gaps. Likely missing schema, weak content depth, or partial crawler blocks. |
| **Critical** | < 40 | Foundational issues. Crawler access, indexability, or no structured signals. Quick wins available. |

Tier drives proposal pricing tier in `geo-proposal` and progress framing in `geo-compare`.

## Caveats

- **Brand authority** depends on optional API keys (SerpAPI, Google Places). Without them, the score uses pattern-matching against page content + manual-check URL generation. Less precise but never zero.
- **Live visibility** is opt-in. The composite GEO Score does not include `live-visibility.json` — it would skew month-over-month comparisons because AI model behavior shifts independently of site changes.
- **Platform optimization** uses heuristic checks; absent direct measurement APIs, scores reflect best-known proxies (e.g., FAQPage schema as a Google AI Overviews proxy).
- **Score volatility** is real. Re-running `/geo audit` against the same URL within a week typically lands within ±3 points.
