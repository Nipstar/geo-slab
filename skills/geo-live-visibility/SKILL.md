---
name: geo-live-visibility
description: >
  Live AI brand visibility testing. Queries ChatGPT, Claude, Gemini, and Perplexity
  with contextual prompts to measure real-time brand visibility in AI-generated
  responses. Discovers competitors and calculates visibility, sentiment, and share
  of voice scores. Requires at least one AI provider API key.
  Use when user says "live visibility", "live test", "AI visibility test", "brand test",
  or "query AI models".
version: 1.0.0
tags: [geo, ai-visibility, live-testing, brand, competitors]
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

# Live AI Brand Visibility Testing

## Purpose

This skill measures real brand visibility by actually querying AI providers and checking whether the brand appears in their responses. Unlike the static audit (which infers visibility from signals like crawler access and content structure), live visibility testing provides ground-truth measurement of how AI models respond to brand-related queries.

## Key Insight

A brand can score well on technical GEO signals (good schema, crawler access, quality content) but still not appear in AI-generated responses if it lacks entity recognition in the models' training data. Live testing bridges this gap by measuring actual visibility.

## Prerequisites

At least one AI provider API key must be configured as an environment variable:

| Provider | Environment Variable | Cost (approx.) |
|---|---|---|
| OpenAI (ChatGPT) | `OPENAI_API_KEY` | ~$0.05/audit |
| Anthropic (Claude) | `ANTHROPIC_API_KEY` | ~$0.03/audit |
| Google (Gemini) | `GOOGLE_GENERATIVE_AI_API_KEY` | ~$0.02/audit |
| Perplexity | `PERPLEXITY_API_KEY` | ~$0.04/audit |

If no API keys are configured, this skill will report which keys are missing and skip the live test.

## Command

```
/geo live <url>
/geo live <url> --industry "legal services" --location "Hampshire, UK"
```

## Execution Steps

### Step 1: Gather Context

Before running the live query script, collect:
1. **Company name** — from the page title, og:site_name, or Organisation schema
2. **URL** — the target URL
3. **Industry** — from business type detection or user input
4. **Location** — if local business, from address/schema or user input
5. **Keywords** — from meta keywords, H1 tags, or page content analysis
6. **Products/Services** — from service pages, product schema, or navigation

### Step 2: Run Live Query Script

Execute via Bash:
```bash
python3 ~/.claude/skills/geo/scripts/live_ai_query.py \
  --company-name "Brand Name" \
  --url "https://example.com" \
  --industry "industry" \
  --location "City, Country" \
  --keywords "kw1,kw2,kw3" \
  --products "service1,service2" \
  --output "reports/<domain>/live-visibility.json"
```

The script takes 30-90 seconds depending on how many providers are configured.

### Step 3: Parse Results

Read the JSON output and extract:
- `visibility_score` — Composite 0-100 score
- `brand_mentioned_pct` — % of unbranded queries where brand appeared
- `sentiment` — Overall sentiment (positive/neutral/negative/mixed)
- `share_of_voice` — Brand mentions vs competitor mentions
- `competitor_rankings` — Top competitors found in AI responses
- `provider_results` — Per-provider breakdown

### Step 4: Generate Report Section

Write a markdown report section suitable for inclusion in audit reports.

## Scoring Methodology

The Live Visibility Score (0-100) is calculated as:

| Component | Weight | Description |
|---|---|---|
| Discovery Rate | 40% | % of unbranded queries where brand appeared |
| Sentiment Quality | 20% | Positive=100, Neutral=50, Negative=0 |
| Share of Voice | 25% | Brand mentions / (brand + competitor mentions) |
| Provider Coverage | 15% | How many of the 4 providers were queried |

**Important:** Only unbranded prompts (those that don't include the brand name) count toward the discovery rate. Branded prompts test entity recognition, not organic discovery.

## Output Format

```markdown
## Live AI Brand Visibility

**Visibility Score: [X]/100**
**Providers Queried:** [list]
**Total Prompts Sent:** [N] across [N] providers

### Sub-Scores

| Metric | Score | Details |
|---|---|---|
| Discovery Rate | [X]% | Brand found in [X]/[Y] unbranded queries |
| Sentiment | [positive/neutral/negative] | Based on [N] branded responses |
| Share of Voice | [X]% | vs [N] competitors identified |
| Provider Coverage | [N]/4 | [list of queried providers] |

### Provider Comparison

| Provider | Queries | Brand Mentioned | Mention Rate | Sentiment |
|---|---|---|---|---|
| ChatGPT (OpenAI) | [N] | [N] | [X]% | [sentiment] |
| Claude (Anthropic) | [N] | [N] | [X]% | [sentiment] |
| Gemini (Google) | [N] | [N] | [X]% | [sentiment] |
| Perplexity AI | [N] | [N] | [X]% | [sentiment] |

### Top Competitors in AI Responses

| Company | Mentions | Providers |
|---|---|---|
| [competitor 1] | [N] | [N]/[total] |
| [competitor 2] | [N] | [N]/[total] |
| [competitor 3] | [N] | [N]/[total] |

### Interpretation

[2-3 sentences interpreting the results. E.g., "Your brand appears in X% of unbranded AI queries, indicating [strong/moderate/weak] organic discovery. The primary competitors appearing instead are [names]. To improve visibility, focus on [specific actions]."]

**Data file:** `reports/<domain>/live-visibility.json`
```

## Integration with Full Audit

When run as part of `/geo audit`, the live visibility section appears as a **supplementary appendix** in the audit report. It does NOT affect the composite GEO Score (0-100) because:

1. It requires API keys that not all users will have
2. AI model responses change frequently — the score would be non-reproducible
3. It measures current model state, not optimisation readiness

The GEO Score measures **how well-optimised** the site is. The Live Visibility Score measures **actual current visibility**. Both are valuable but serve different purposes.

## Important Notes

- The script uses cost-efficient models (gpt-4o-mini, claude-haiku, gemini-2.0-flash, sonar) to minimize API costs
- Rate limiting is built in (0.5s between queries per provider) to avoid API throttling
- If a provider fails mid-query, the audit continues with the remaining providers
- Results are saved to JSON for future comparison via `/geo compare`
- **Never fabricate results.** If the script fails or no keys are available, report that clearly — don't estimate or infer live visibility scores from other data
