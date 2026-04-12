---
name: geo-platform-optimizer
description: Platform-specific AI search optimization — audit and optimize for Google AI Overviews, ChatGPT, Perplexity, Gemini, Bing Copilot, Grok, DeepSeek, Meta AI, and Mistral individually
version: 2.0.0
author: antek-automation
tags: [geo, ai-search, platform-optimization, chatgpt, perplexity, gemini, aio, grok, deepseek, meta-ai, mistral]
---

# GEO Platform Optimizer

## Core Insight

Only **11% of domains** are cited by BOTH ChatGPT and Google AI Overviews for the same query. Each AI search platform uses different indexes, ranking logic, and source preferences. A page optimized for Google AI Overviews may be invisible to ChatGPT, and vice versa. Platform-specific optimization is not optional — it is the foundation of any serious GEO strategy.

## How to Use This Skill

1. Collect the target URL and the site's primary topic/industry
2. Run each platform checklist below against the site
3. Score each platform on the 0-100 rubric
4. Generate GEO-PLATFORM-OPTIMIZATION.md with per-platform scores, gaps, and action items

---

## Platform 1: Google AI Overviews (AIO)

### How AIO Selects Sources
- 92% of AIO citations come from pages already ranking in the **top 10 organic results** — traditional SEO is the gateway
- However, 47% of citations come from pages ranking **below position 5** — AIO has its own selection logic favoring clarity and directness over raw rank
- AIO strongly favors pages with **clean structure, direct answers, and scannable formatting**
- Featured snippet optimization has ~70% overlap with AIO optimization
- AIO prefers **concise, factual, unambiguous answers** — hedging and filler reduce citation probability

### Optimization Checklist

1. **Question-Based Headings**: Use H2/H3 headings phrased as questions matching real user queries. Check Google's "People Also Ask" for the target topic and mirror those exact phrasings.
2. **Direct Answer in First Paragraph**: After each question heading, provide a clear 1-2 sentence answer immediately. Then expand with supporting detail. The first sentence should be a standalone citation candidate.
3. **Tables and Structured Comparisons**: AIO heavily cites tables. Convert any comparison, pricing, specification, or feature data into HTML tables. Use clear column headers.
4. **Ordered and Unordered Lists**: Step-by-step processes should use ordered lists. Feature lists should use unordered lists. AIO extracts these directly.
5. **FAQ Sections**: Add a dedicated FAQ section with 5-10 real questions. Use proper H3 headings for each question. While FAQPage schema rich results are restricted to govt/health sites since Aug 2023, the content pattern still helps AIO extraction.
6. **Definitions and Glossary Boxes**: For any industry-specific term, provide a clear definition. Format: "**[Term]** is [concise definition]." AIO frequently cites definitions.
7. **Statistics with Sources**: Include specific numbers with attribution. "According to [Source], [statistic]." AIO prefers citeable, specific claims over vague assertions.
8. **Publication Date**: Include a visible publication date and last-updated date. AIO deprioritizes undated content for time-sensitive queries.
9. **Author Byline**: Display author name with credentials. Link to an author page with bio, credentials, and sameAs links.
10. **Page Depth**: Keep target pages within 3 clicks of homepage. AIO rarely cites deep, orphaned content.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| Ranks in top 10 for target queries | 20 | 20 if yes, 10 if top 20, 0 if beyond |
| Question-based headings present | 10 | 2 points per question heading, max 10 |
| Direct answers after headings | 15 | 3 points per direct answer, max 15 |
| Tables present for comparison data | 10 | 10 if tables used appropriately, 5 if partial, 0 if absent |
| Lists for processes/features | 10 | 10 if present, 5 if partial |
| FAQ section with 5+ questions | 10 | 10 if 5+, 5 if 1-4, 0 if none |
| Statistics with citations | 10 | 2 points per cited stat, max 10 |
| Publication/updated date visible | 5 | 5 if both dates, 3 if one, 0 if none |
| Author byline with credentials | 5 | 5 if full byline, 3 if name only, 0 if none |
| Clean URL + heading hierarchy | 5 | 5 if H1>H2>H3 clean, 3 if minor issues, 0 if broken |

---

## Platform 2: ChatGPT Web Search

### How ChatGPT Selects Sources
- Uses **Bing's search index** as its foundation (not Google)
- Top citation sources by domain share: **Wikipedia (47.9%)**, Reddit (11.3%), YouTube, major news outlets
- ChatGPT heavily weights **entity recognition** — if your brand exists as a structured entity (Wikipedia, Wikidata, Crunchbase), it is far more likely to be cited
- Prefers **authoritative, well-established sources** over new or niche sites
- Longer, more comprehensive articles get cited more often than short pieces
- ChatGPT tends to cite **the most canonical source** for a claim rather than the original

### Optimization Checklist

1. **Wikipedia Presence**: Check if the brand/person/product has a Wikipedia article. If not, assess notability criteria. If notable, create a draft. If an article exists, ensure it is accurate and current.
2. **Wikidata Entity**: Verify the entity exists on Wikidata (wikidata.org). If not, create a Wikidata item with key properties: instance of, official website, social media links, founding date, headquarters location.
3. **Bing Webmaster Tools**: Verify the site is registered in Bing Webmaster Tools. Submit sitemap. Check for crawl errors.
4. **Bing Index Coverage**: Use `site:domain.com` on Bing to verify key pages are indexed. Bing may have different indexed pages than Google.
5. **Reddit Authority**: Check for brand mentions on Reddit. Identify relevant subreddits. Assess whether the brand participates authentically in discussions.
6. **YouTube Presence**: Verify YouTube channel exists with relevant content. Video descriptions should contain full URLs and entity information.
7. **Authoritative Backlinks**: ChatGPT/Bing weight .edu, .gov, and major publication backlinks heavily. Audit backlink profile for these sources.
8. **Entity Consistency**: Brand name, founding date, leadership, and key facts must be consistent across Wikipedia, Crunchbase, LinkedIn, and the official website.
9. **Comprehensive Content**: Pages targeting ChatGPT citation should be **2000+ words** with thorough topic coverage. ChatGPT prefers single authoritative sources over combining multiple thin pages.
10. **Clear Attribution**: Include "About" sections, company descriptions, and founding stories. ChatGPT uses these for entity grounding.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| Wikipedia article exists and is accurate | 20 | 20 if exists, 10 if stub, 0 if none |
| Wikidata entity with 5+ properties | 10 | 10 if complete, 5 if basic, 0 if none |
| Bing index coverage of key pages | 10 | 10 if full, 5 if partial, 0 if poor |
| Reddit brand mentions (positive) | 10 | 10 if active discussions, 5 if mentions, 0 if none |
| YouTube channel with relevant content | 10 | 10 if active, 5 if present but sparse, 0 if none |
| Authoritative backlinks (.edu, .gov, press) | 15 | 3 points per authoritative backlink category, max 15 |
| Entity consistency across platforms | 10 | 10 if consistent, 5 if minor discrepancies, 0 if major |
| Content comprehensiveness (2000+ words) | 10 | 10 if thorough, 5 if adequate, 0 if thin |
| Bing Webmaster Tools configured | 5 | 5 if verified, 0 if not |

---

## Platform 3: Perplexity AI

### How Perplexity Selects Sources
- Top citation sources: **Reddit (46.7%)**, Wikipedia, YouTube, major publications
- Perplexity places the **heaviest emphasis on community validation** of all AI search platforms
- Strongly favors **discussion threads** where claims are debated, validated, or expanded by multiple participants
- Prefers recent content — publication date is a strong ranking signal
- Cites **multiple sources per answer** (typically 5-15), so there is more opportunity for mid-authority sites to appear
- Uses its own crawling infrastructure in addition to search APIs

### Optimization Checklist

1. **Active Reddit Presence**: The brand or its representatives should participate authentically in relevant subreddit discussions. Not promotional — helpful, specific, and community-oriented.
2. **Reddit AMAs and Threads**: Encourage or participate in AMAs, detailed discussion threads, and community Q&As. Perplexity treats these as high-signal content.
3. **Forum and Community Presence**: Beyond Reddit, check Hacker News, Stack Overflow, Quora, and niche industry forums. Perplexity indexes these heavily.
4. **Discussion-Friendly Content**: Publish content that invites discussion — opinion pieces, research findings, contrarian takes, original data. Content that gets shared and debated in communities ranks higher.
5. **Freshness Signals**: Publish content with clear dates. Update content regularly. Perplexity deprioritizes stale content more aggressively than other platforms.
6. **Multiple Source Validation**: Claims in your content should be supported by other sources. Perplexity cross-references and prefers claims it can verify from multiple origins.
7. **YouTube Video Content**: Create video content that Perplexity can reference. Ensure video titles, descriptions, and transcripts contain target information.
8. **Direct, Quotable Passages**: Write paragraphs that can stand alone as citations. Each paragraph should make one clear point with supporting evidence.
9. **Original Data and Research**: Publish original surveys, benchmarks, case studies, or datasets. Perplexity heavily favors primary sources.
10. **Perplexity Pages**: Check if Perplexity has created a "Page" about your topic/brand. These are curated summaries that influence future citations.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| Active Reddit presence in relevant subreddits | 20 | 20 if active contributor, 10 if mentioned, 0 if absent |
| Forum/community mentions (HN, SO, Quora) | 10 | 10 if multiple platforms, 5 if one, 0 if none |
| Content freshness (updated within 6 months) | 10 | 10 if recent, 5 if within year, 0 if older |
| Original research/data published | 15 | 15 if original research, 10 if case studies, 5 if some data, 0 if none |
| YouTube content with transcripts | 10 | 10 if active channel, 5 if some videos, 0 if none |
| Quotable, standalone paragraphs | 10 | 2 points per well-structured quotable paragraph, max 10 |
| Multi-source claim validation | 10 | 10 if claims well-sourced, 5 if some sourcing, 0 if none |
| Discussion-generating content | 10 | 10 if content gets shared/discussed, 5 if some engagement, 0 if none |
| Wikipedia/Wikidata presence | 5 | 5 if present, 0 if absent |

---

## Platform 4: Google Gemini

### How Gemini Selects Sources
- Uses **Google's search index** plus strong weighting toward **Google-owned properties**
- YouTube content is weighted significantly more heavily than in standard Google Search
- Google Business Profile data is directly accessible to Gemini
- Gemini uses Google's Knowledge Graph directly — entity presence in Knowledge Graph is a major advantage
- Structured data (Schema.org) is consumed directly by Gemini for entity understanding
- Gemini multi-modal: can reference images, videos, and text together

### Optimization Checklist

1. **Google Knowledge Panel**: Check if the brand has a Google Knowledge Panel. If not, claim it through Google Business Profile or structured data. Ensure all information is accurate.
2. **Google Business Profile**: Complete and optimize GBP with all fields: hours, services, photos, posts, Q&A. Gemini pulls directly from GBP for local queries.
3. **YouTube Strategy**: Create YouTube content for every key topic. Optimize titles, descriptions, timestamps, and closed captions. Gemini cites YouTube more than any other AI platform.
4. **YouTube Chapters and Timestamps**: Use chapters (timestamps in description) so Gemini can reference specific segments of videos.
5. **Google Merchant Center**: For e-commerce, ensure products are in Google Merchant Center. Gemini references product data directly.
6. **Structured Data (Schema.org)**: Implement comprehensive Schema.org markup. Gemini uses this for entity understanding more aggressively than other platforms.
7. **Google Sites Ecosystem**: Ensure presence across Google ecosystem: Google Scholar (for research), Google News (for publishers), Google Maps (for local).
8. **Image Optimization**: Gemini is multi-modal. Use descriptive alt text, structured image filenames, and high-quality images. Include relevant images with every piece of content.
9. **Google E-E-A-T Signals**: All standard Google E-E-A-T signals apply with extra weight. Author pages, about pages, editorial policies, and expertise demonstrations.
10. **Chrome Web Store / Google Workspace Marketplace**: For software companies, presence on Google platforms adds entity signals.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| Google Knowledge Panel exists | 15 | 15 if complete, 10 if partial, 0 if none |
| Google Business Profile complete | 10 | 10 if fully optimized, 5 if basic, 0 if none |
| YouTube channel with topic-relevant content | 20 | 20 if active with chapters, 10 if present, 0 if none |
| Schema.org structured data implemented | 15 | 15 if comprehensive, 10 if basic, 5 if minimal, 0 if none |
| Google ecosystem presence (Scholar, News, Maps) | 10 | 10 if 3+, 5 if 1-2, 0 if none |
| Image optimization (alt text, filenames) | 10 | 10 if all images optimized, 5 if partial, 0 if none |
| E-E-A-T signals (author pages, about, editorial) | 10 | 10 if strong, 5 if partial, 0 if weak |
| Google Merchant Center (if e-commerce) | 5 | 5 if applicable and active, N/A otherwise |
| Multi-modal content (text + images + video) | 5 | 5 if rich multi-modal, 3 if some, 0 if text-only |

---

## Platform 5: Bing Copilot

### How Copilot Selects Sources
- Uses **Bing's search index** (shared infrastructure with ChatGPT but different ranking/selection)
- Supports **IndexNow protocol** for near-instant indexing of new and updated content
- Copilot tends to cite **fewer sources per answer** (typically 3-5) but gives more prominent attribution
- Microsoft ecosystem integration: LinkedIn, GitHub, Microsoft Learn content is weighted
- Copilot prefers pages with clear, structured markup and fast load times

### Optimization Checklist

1. **Bing Webmaster Tools**: Register and verify site. Submit XML sitemap. Review and fix any crawl issues.
2. **IndexNow Implementation**: Implement the IndexNow protocol to notify Bing of content changes in real-time. Submit a key file at `/.well-known/indexnow-key.txt` and ping the IndexNow API on content publish/update.
3. **LinkedIn Company Page**: Ensure the company LinkedIn page is complete with accurate description, employee connections, and regular posts. Copilot indexes LinkedIn content.
4. **GitHub Presence**: For tech companies, maintain an active GitHub presence. Copilot references GitHub repos, documentation, and README files.
5. **Microsoft Learn / Documentation**: If relevant, contribute to Microsoft Learn or ensure documentation is compatible with Microsoft's documentation standards.
6. **Bing Places for Business**: Equivalent to Google Business Profile. Complete all fields for local search visibility in Copilot.
7. **Clear Meta Descriptions**: Bing/Copilot weights meta descriptions more heavily than Google does. Write compelling, keyword-rich meta descriptions for every page.
8. **Social Signals**: Bing has historically weighted social signals (shares, likes, engagement) more than Google. Maintain active social media presence.
9. **Exact-Match Keywords**: Bing's algorithm is more literal about keyword matching than Google. Include exact target phrases in titles, headings, and body content.
10. **Fast Page Load**: Copilot deprioritizes slow pages. Target sub-2-second load time. Optimize images, enable compression, minimize render-blocking resources.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| Bing Webmaster Tools verified + sitemap | 15 | 15 if verified, 5 if partial, 0 if not |
| IndexNow protocol implemented | 15 | 15 if active, 0 if not |
| Bing index coverage of key pages | 10 | 10 if full, 5 if partial, 0 if poor |
| LinkedIn company page (complete) | 10 | 10 if complete, 5 if basic, 0 if none |
| GitHub presence (if applicable) | 5 | 5 if active, N/A if not applicable |
| Meta descriptions optimized | 10 | 10 if all key pages, 5 if partial, 0 if missing |
| Social media engagement signals | 10 | 10 if active engagement, 5 if present, 0 if none |
| Exact-match keywords in titles/headings | 10 | 10 if well-optimized, 5 if partial, 0 if not |
| Page load speed < 2 seconds | 10 | 10 if < 2s, 5 if < 4s, 0 if > 4s |
| Bing Places configured (if local) | 5 | 5 if complete, N/A if not local |

---

## Platform 6: Grok (xAI)

### How Grok Selects Sources
- Built by xAI (Elon Musk), Grok has **native access to the full X/Twitter firehose** — real-time posts, threads, and engagement data are first-class signals
- Uses web search in addition to X data, but **X/Twitter content is weighted disproportionately** compared to other platforms
- Grok emphasizes **recency and real-time information** — breaking news, trending topics, and live discussions are prioritized
- Prefers **direct, conversational, opinionated content** over hedged corporate language
- Entity recognition relies on X verification status, news coverage, and web presence
- No confirmed dedicated crawler user-agent as of April 2026 — Grok's web search integration uses partnership-based indexing

### Optimization Checklist

1. **Active X/Twitter Presence**: Maintain an active, verified X account with regular posts about your core topics. Grok pulls directly from X conversations, so your X content IS your Grok content.
2. **X Verification (Blue/Gold Checkmark)**: Verified accounts receive higher trust signals. Gold verification (organization) is strongest. Blue verification (individual) is baseline. Unverified accounts have reduced visibility.
3. **X Thread Strategy**: Publish long-form X threads covering key topics. Threads with high engagement (replies, reposts, likes) become citation candidates. Include specific data points and claims in threads.
4. **Real-Time Content Publishing**: Publish timely content responding to industry developments. Grok weights recency more heavily than most platforms. Stale content is deprioritized rapidly.
5. **News and Press Coverage**: Ensure the brand appears in news articles indexed by web search. Grok cross-references X mentions with web sources for verification.
6. **Direct, Opinionated Tone**: Grok favors content with clear positions and direct language. Avoid corporate hedging ("we believe", "it may be the case"). State claims directly with supporting evidence.
7. **Engagement Signals on X**: Content that generates genuine discussion (replies, quote posts) signals relevance. Engage authentically in industry conversations, not just broadcast.
8. **Entity Consistency Across X and Web**: Ensure your X bio, website, and web presence tell the same story. Inconsistencies reduce entity confidence.
9. **Multimedia on X**: Posts with images, videos, and links receive higher engagement and visibility. Create shareable visual content for key claims and data.
10. **Trending Topic Alignment**: Monitor trending topics in your industry on X. Publishing relevant content during trending moments increases Grok citation probability.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| Active X/Twitter account with regular posting | 15 | 15 if daily/weekly posts, 10 if monthly, 5 if dormant, 0 if none |
| X verification status | 10 | 10 if gold (org), 7 if blue, 0 if unverified |
| X threads on core topics with engagement | 15 | 15 if multiple high-engagement threads, 10 if some, 5 if few, 0 if none |
| Content freshness (updated within 30 days) | 10 | 10 if very recent, 5 if within 3 months, 0 if older |
| News/press coverage in web index | 15 | 15 if regular coverage, 10 if occasional, 5 if rare, 0 if none |
| Direct, clear tone in content | 10 | 10 if strong direct voice, 5 if mixed, 0 if corporate/hedged |
| X engagement metrics (replies, reposts) | 10 | 10 if high engagement, 5 if moderate, 0 if minimal |
| Entity consistency (X bio ↔ website ↔ web) | 5 | 5 if consistent, 3 if minor issues, 0 if major discrepancies |
| Multimedia content on X | 5 | 5 if rich media, 3 if some, 0 if text-only |
| Web presence supporting X claims | 5 | 5 if web content backs X claims, 0 if X-only or contradictory |

---

## Platform 7: DeepSeek

### How DeepSeek Selects Sources
- Chinese AI lab with a strong focus on **technical and reasoning tasks** — DeepSeek's models excel at code, math, and technical analysis
- Uses web search through partnerships; **does NOT use Bytespider** (that is ByteDance/TikTok, a separate company)
- Strongly favors **comprehensive, technically detailed content** — documentation-style writing, code examples, and academic references perform well
- DeepSeek's training data skews toward **technical, scientific, and programming content**
- Supports both Chinese and English content, but English-language technical content is heavily represented
- No confirmed dedicated crawler user-agent as of April 2026

### Optimization Checklist

1. **Technical Documentation Quality**: Ensure technical content is thorough, accurate, and well-structured. DeepSeek excels at technical reasoning and favors content that matches its strengths.
2. **Code Examples and Snippets**: Include working code examples with proper syntax highlighting (use fenced code blocks). DeepSeek users frequently ask code-related questions.
3. **Academic and Research Citations**: Reference peer-reviewed research, whitepapers, and technical standards. Include DOIs, paper titles, and author names.
4. **Structured Technical Content**: Use clear section hierarchies, numbered steps for processes, and specification-style formatting. Tables for comparison data, lists for requirements.
5. **Comprehensive Topic Coverage**: DeepSeek favors depth over breadth. A single comprehensive page on a topic outperforms multiple thin pages. Target 2000+ words for technical topics.
6. **API Documentation**: If applicable, provide thorough API documentation with endpoints, parameters, request/response examples, and error codes.
7. **Mathematical and Scientific Notation**: Use proper notation for formulas, equations, and technical specifications. DeepSeek handles technical notation well.
8. **Open-Source Presence**: GitHub repositories, open-source contributions, and technical community participation signal expertise in DeepSeek's technical domain.
9. **Methodology Transparency**: Explain how things work, not just what they do. DeepSeek users tend toward "how" and "why" queries. Show your work.
10. **Benchmark Data and Performance Metrics**: Include specific performance numbers, benchmarks, and measurable outcomes. DeepSeek's reasoning strength makes it effective at comparing quantitative claims.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| Technical documentation depth and accuracy | 20 | 20 if comprehensive, 10 if adequate, 5 if basic, 0 if none |
| Code examples with proper formatting | 15 | 15 if working examples, 10 if snippets, 5 if minimal, 0 if none |
| Academic/research citations present | 10 | 10 if peer-reviewed sources cited, 5 if some references, 0 if none |
| Structured content hierarchy | 10 | 10 if clean H1>H2>H3 with lists/tables, 5 if partial, 0 if unstructured |
| Content comprehensiveness (2000+ words) | 15 | 15 if thorough, 10 if adequate, 5 if thin, 0 if stub |
| API/technical documentation (if applicable) | 10 | 10 if complete, 5 if partial, N/A if not applicable |
| Open-source/GitHub presence | 5 | 5 if active repos, 3 if some presence, 0 if none |
| Methodology explanations ("how" content) | 5 | 5 if explains methods, 3 if some, 0 if outcome-only |
| Quantitative data and benchmarks | 5 | 5 if specific metrics, 3 if some numbers, 0 if qualitative only |
| Schema.org structured data | 5 | 5 if comprehensive, 3 if basic, 0 if none |

---

## Platform 8: Meta AI

### How Meta AI Selects Sources
- Meta AI is integrated across **Facebook, Instagram, WhatsApp, and Messenger** — reaching 3B+ combined users
- Uses **Bing's search index** for web queries (similar to ChatGPT) plus **Meta's own ecosystem data**
- **FacebookBot** crawler (Tier 2) indexes content for Meta AI features — already documented in the crawlers skill
- Strongly weights **social proof signals**: shares, reactions, comments, and community engagement on Meta platforms
- Open Graph tags are consumed directly for rich content previews and entity understanding
- Visual content (images, video, Reels) plays a larger role than on text-first platforms
- Entity recognition draws from Facebook Pages, Instagram business profiles, and the broader web

### Optimization Checklist

1. **FacebookBot Crawler Access**: Verify FacebookBot is allowed in robots.txt. This is the gateway to Meta AI visibility. Block FacebookBot = invisible to Meta AI.
2. **Facebook Business Page**: Complete all fields: about, services, hours, contact info, story, milestones. Meta AI pulls directly from Page data for entity queries.
3. **Instagram Business/Creator Profile**: Active Instagram presence with business account. Bio link, highlights, regular content posting. Meta AI surfaces Instagram content for visual and lifestyle queries.
4. **Open Graph Meta Tags**: Implement `og:title`, `og:description`, `og:image`, `og:type`, `og:url` on every page. Meta AI uses Open Graph for content understanding and rich previews.
5. **Social Engagement Signals**: Content that generates shares, saves, and comments on Facebook and Instagram signals relevance. Community-validated content ranks higher.
6. **Bing Index Optimization**: Since Meta AI uses Bing for web search, all Bing optimization applies: Bing Webmaster Tools, IndexNow, meta descriptions, exact-match keywords.
7. **Visual Content Strategy**: Meta's platforms are visual-first. Include high-quality images with descriptive alt text. Create Reels/short video content covering key topics.
8. **WhatsApp Business Integration**: For businesses with WhatsApp presence, ensure WhatsApp Business profile is complete and linked to the website. Meta AI can reference WhatsApp catalog data.
9. **Community and Group Presence**: Active participation in relevant Facebook Groups signals topical authority. Meta AI considers community engagement as a trust signal.
10. **Entity Consistency Across Meta Properties**: Facebook Page name, Instagram handle, and website brand must be consistent. Meta AI cross-references all Meta properties for entity verification.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| FacebookBot allowed in robots.txt | 15 | 15 if allowed, 0 if blocked |
| Facebook Business Page completeness | 15 | 15 if fully optimized, 10 if basic info, 5 if claimed, 0 if none |
| Instagram business/creator profile | 10 | 10 if active with regular posts, 5 if present but sparse, 0 if none |
| Open Graph meta tags implemented | 10 | 10 if all key OG tags, 5 if partial, 0 if absent |
| Social engagement on Meta platforms | 15 | 15 if high engagement, 10 if moderate, 5 if low, 0 if none |
| Bing index coverage of key pages | 10 | 10 if full coverage, 5 if partial, 0 if poor |
| Visual content (images, video, Reels) | 10 | 10 if rich visual strategy, 5 if some images, 0 if text-only |
| Entity consistency across Meta properties | 5 | 5 if consistent, 3 if minor issues, 0 if major discrepancies |
| Community/Group presence | 5 | 5 if active community, 3 if some presence, 0 if none |
| WhatsApp Business (if applicable) | 5 | 5 if complete, N/A if not applicable |

---

## Platform 9: Mistral (Le Chat)

### How Mistral Selects Sources
- French AI company with a focus on the **European market** — Le Chat is Mistral's consumer-facing AI assistant with web search
- Uses **partnership-based web search** (integrated with Brave Search and other providers) rather than its own crawler
- Favors **authoritative, well-structured content** with clear sourcing — similar to academic standards
- **Multilingual capability** is a strength — Mistral models perform well across European languages (French, German, Spanish, Italian, etc.)
- Content in **structured, professional formats** performs well — documentation, guides, reference material
- Growing presence in **enterprise and professional use cases** in Europe
- No confirmed dedicated crawler user-agent as of April 2026 — relies on partner search indexes

### Optimization Checklist

1. **Brave Search and Partner Index Presence**: Verify your site appears in Brave Search results (search.brave.com). Mistral's Le Chat uses Brave Search as a primary web search provider.
2. **Multilingual Content (hreflang)**: If targeting European audiences, implement hreflang tags and provide content in multiple European languages. Mistral excels at multilingual queries.
3. **Authoritative Sourcing**: Cite authoritative sources for all claims. Mistral's selection methodology weights source credibility heavily. Include references, footnotes, or inline citations.
4. **Schema.org Structured Data**: Implement comprehensive Schema.org markup. Mistral's partner search indexes consume structured data for entity understanding and rich results.
5. **Professional, Formal Tone**: Mistral's training and user base skew professional/enterprise. Content with clear, professional language and expert positioning performs better.
6. **Content Depth and Completeness**: Comprehensive treatment of topics with proper context. Mistral prefers complete answers from authoritative sources over aggregated snippets.
7. **European Regulatory Compliance**: GDPR compliance, EU accessibility standards, and transparent data practices signal trustworthiness to European-focused AI platforms.
8. **Academic and Professional Credentials**: Author pages with credentials, institutional affiliations, and professional backgrounds strengthen authority signals.
9. **Clear Content Hierarchy**: Well-organized content with logical heading structure, table of contents for long pages, and clear section organization.
10. **Publication and Update Dates**: Visible publication dates and update timestamps. Content provenance is a trust signal for citation-focused models.

### Scoring Rubric (0-100)

| Criterion | Points | How to Score |
|---|---|---|
| Presence in Brave Search / partner indexes | 15 | 15 if well-indexed, 10 if partial, 5 if minimal, 0 if absent |
| Multilingual content with hreflang | 10 | 10 if multiple languages, 5 if two languages, 0 if English-only (reduce penalty if English-only market) |
| Authoritative sourcing and citations | 15 | 15 if well-cited, 10 if some citations, 5 if minimal, 0 if none |
| Schema.org structured data | 15 | 15 if comprehensive, 10 if basic, 5 if minimal, 0 if none |
| Professional tone and presentation | 10 | 10 if polished professional, 5 if adequate, 0 if informal/low quality |
| Content depth and comprehensiveness | 10 | 10 if thorough, 5 if adequate, 0 if thin |
| Author credentials and expertise signals | 10 | 10 if full credentials, 5 if name only, 0 if anonymous |
| Content hierarchy and organization | 5 | 5 if clean H1>H2>H3, 3 if some structure, 0 if flat |
| Publication/update dates visible | 5 | 5 if both dates, 3 if one, 0 if none |
| European compliance signals (GDPR, etc.) | 5 | 5 if compliant, 3 if partial, 0 if no signals |

---

## Cross-Platform Summary

### Universal Optimization Actions (help ALL platforms)
1. Wikipedia/Wikidata entity presence
2. YouTube channel with relevant content
3. Comprehensive, well-structured content with clear headings
4. Schema.org structured data (especially Organization + sameAs)
5. Fast page load and clean HTML
6. Author pages with credentials and sameAs links
7. Regular content updates with visible dates
8. Active social presence across X, Facebook, Instagram, LinkedIn
9. Bing index optimization (powers ChatGPT, Copilot, and Meta AI)

### Platform-Specific Priorities
| Priority | Google AIO | ChatGPT | Perplexity | Gemini | Copilot | Grok | DeepSeek | Meta AI | Mistral |
|---|---|---|---|---|---|---|---|---|---|
| #1 | Top-10 ranking | Wikipedia | Reddit presence | YouTube | IndexNow | X/Twitter presence | Technical depth | Facebook Page | Brave Search index |
| #2 | Q&A structure | Entity graph | Original research | Knowledge Panel | Bing WMT | Real-time content | Code examples | Social engagement | Authoritative sourcing |
| #3 | Tables/lists | Bing SEO | Freshness | Schema.org | LinkedIn | News coverage | Comprehensiveness | Open Graph tags | Schema.org markup |
| #4 | Featured snippets | Reddit | Community forums | GBP | Meta descriptions | Engagement signals | Academic citations | Bing index | Multilingual content |

---

## Output Format

Generate **GEO-PLATFORM-OPTIMIZATION.md** with the following structure:

```markdown
# GEO Platform Optimization Report — [Domain]
Date: [Date]

## Overall Platform Readiness
- Combined GEO Score: XX/100 (average of all platform scores)

## Platform Scores
| Platform | Score | Status |
|---|---|---|
| Google AI Overviews | XX/100 | [Strong/Moderate/Weak] |
| ChatGPT Web Search | XX/100 | [Strong/Moderate/Weak] |
| Perplexity AI | XX/100 | [Strong/Moderate/Weak] |
| Google Gemini | XX/100 | [Strong/Moderate/Weak] |
| Bing Copilot | XX/100 | [Strong/Moderate/Weak] |
| Grok (xAI) | XX/100 | [Strong/Moderate/Weak] |
| DeepSeek | XX/100 | [Strong/Moderate/Weak] |
| Meta AI | XX/100 | [Strong/Moderate/Weak] |
| Mistral (Le Chat) | XX/100 | [Strong/Moderate/Weak] |

Status thresholds: Strong = 70+, Moderate = 40-69, Weak = 0-39

## Platform Details
[Per-platform breakdown with score, gaps found, specific actions]

## Prioritized Action Plan
### Quick Wins (this week)
[Actions that improve multiple platform scores with minimal effort]

### Medium-Term (this month)
[Actions requiring content creation or technical changes]

### Strategic (this quarter)
[Actions requiring entity building, community development, or platform presence]
```
