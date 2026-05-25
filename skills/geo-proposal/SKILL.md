---
name: geo-proposal
description: >
  Auto-generate professional GEO service proposals from audit data. Extracts
  scores, findings, and quick wins from existing audits to produce a client-ready
  proposal with tiered pricing recommendations based on GEO score severity.
  Use when user says "proposal", "quote", "pitch", or "generate proposal".
version: 1.0.0
tags: [geo, business, proposal, sales, client, pricing]
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

# GEO Proposal Generator

> **MANDATORY: Read `/STYLE.md` before generating any prose in this proposal.**
> Every client-facing sentence — executive summary, current-state snapshot, recommendations, pricing rationale, timeline, CTA — must be translated through the mappings defined in `/STYLE.md` and `scripts/style.py`. Do NOT output raw technical terms (`llms.txt`, `JSON-LD`, `robots.txt`, `E-E-A-T`, `schema.org`, `GEO`) without the plain-English wrapper. The banned-words list in `style.py:BANNED_WORDS` is non-negotiable. UK English throughout.

## Purpose

Transform GEO audit data into a professional client-facing service proposal. The proposal includes an executive summary, current performance snapshot, recommended service tier with pricing logic, timeline, and next steps. Designed to go from audit to proposal in under 2 minutes.

## Command

```
/geo proposal <domain>                                    — Load latest audit from reports/<domain>/
/geo proposal <domain> --tier standard                    — Force a specific tier
/geo proposal <domain> --client-name "Acme Corp"          — Override client name
/geo proposal <audit-file.md>                             — Use a specific audit file
```

---

## Execution Steps

### Step 1: Load Audit Data

1. If given a domain, use Glob to find the latest audit in `reports/<domain>/`:
   - Look for `GEO-AUDIT-REPORT.md`, `GEO-AUDIT-REPORT*.md`, or `GEO-REPORT-*.md`
   - Pick the most recent by filename date or modification time
2. If given a file path, read that file directly
3. If no audit exists, tell the user to run `/geo audit <url>` first

### Step 2: Extract Key Data

Parse the audit file for:

**Scores (required):**
- Overall GEO Score (0-100)
- Category scores: AI Citability, Brand Authority, Content E-E-A-T, Technical, Schema, Platform Optimization
- Platform readiness scores (if available)

**Findings (required):**
- All findings with severity (CRITICAL, HIGH, MEDIUM, LOW)
- Count of each severity level
- Top 3-5 critical/high findings for the proposal

**Quick Wins (optional):**
- Actions labeled as "quick wins", "this week", or low-effort/high-impact items
- These demonstrate immediate value in the proposal

**Business Context:**
- Domain and brand name
- Business type detected (SaaS, Local, E-commerce, Publisher, Agency)
- Audit date
- Pages analyzed

### Step 3: Determine Recommended Tier

**Pricing recommendation based on GEO score:**

| GEO Score | Recommended Tier | Rationale |
|---|---|---|
| 0-40 | **Premium** | Critical issues across multiple categories require intensive, hands-on work |
| 41-60 | **Standard** | Significant gaps but foundations exist; structured monthly optimization will close them |
| 61-75 | **Basic** | Solid foundations with specific improvement areas; maintenance + targeted fixes |
| 76-100 | **Basic** or Retainer | Strong performance; quarterly check-in and monitoring sufficient |

**Override:** If `--tier` is specified, use that tier regardless of score.

**Tier definitions:**

#### Basic — Monthly GEO Monitoring
- Monthly GEO audit and score tracking
- llms.txt maintenance and updates
- Schema.org monitoring and fixes
- Monthly progress report (`/geo compare`)
- Email support for GEO questions

#### Standard — Full GEO Optimization Program
- Everything in Basic, plus:
- Weekly content recommendations for AI citability
- Platform-specific optimization (all 9 platforms)
- Brand mention strategy and tracking
- Bi-weekly strategy calls
- Competitor visibility monitoring

#### Premium — Complete GEO Transformation
- Everything in Standard, plus:
- Daily AI visibility monitoring
- Content creation and optimization (X articles/month)
- Wikipedia/Wikidata entity building
- Community presence strategy (Reddit, forums)
- Priority support and dedicated Slack channel
- Quarterly executive report

### Step 4: Generate Proposal

Write the proposal to `reports/<domain>/GEO-PROPOSAL-<domain>.md`.

If `--client-name` is not provided, derive the client name from the audit file's brand name or domain.

---

## Output Format

```markdown
# GEO Optimization Proposal

**Prepared for:** [Client Name]
**Website:** [Domain]
**Date:** [Today's Date]
**Prepared by:** [Your Agency Name]

---

## Executive Summary

[2-3 paragraphs that tell a story:]
[Paragraph 1: Current state — "We audited [domain] across [X] pages and scored it [X]/100 on our GEO readiness scale. This means [interpretation]."]
[Paragraph 2: The opportunity — "AI-powered search engines now drive [X]% of discovery traffic with 4.4x higher conversion rates. Your competitors who score higher are capturing this traffic today."]
[Paragraph 3: The solution — "We've identified [X] critical issues and [X] quick wins. Our [Tier] program addresses these systematically over [timeline]."]

---

## Your Current GEO Performance

**Overall GEO Score: [X]/100 — [Critical/Poor/Fair/Good/Excellent]**

| Category | Score | Status |
|---|---|---|
| AI Citability & Visibility | [X]/100 | [Status] |
| Brand Authority Signals | [X]/100 | [Status] |
| Content Quality & E-E-A-T | [X]/100 | [Status] |
| Technical Foundations | [X]/100 | [Status] |
| Schema & Structured Data | [X]/100 | [Status] |
| Platform Optimization | [X]/100 | [Status] |

Status: Critical (0-29), Poor (30-49), Fair (50-69), Good (70-84), Excellent (85-100)

### What We Found

**[X] Critical Issues:**
1. **[Finding title]** — [One-sentence description and business impact]
2. **[Finding title]** — [Description]
3. **[Finding title]** — [Description]

**[X] Quick Wins Available:**
- [Quick win 1 — estimated time]
- [Quick win 2 — estimated time]
- [Quick win 3 — estimated time]

---

## Recommended Service: [Tier Name]

Based on your GEO score of [X]/100, we recommend our **[Tier]** program. [1-2 sentence justification].

### What's Included

[Bulleted list of deliverables for the recommended tier]

### Implementation Timeline

| Phase | Duration | Focus | Expected Score Impact |
|---|---|---|---|
| **Phase 1: Foundation** | Weeks 1-2 | Critical fixes, schema deployment, crawler access | +10-15 points |
| **Phase 2: Optimization** | Weeks 3-8 | Platform optimization, content improvements, entity building | +15-25 points |
| **Phase 3: Growth** | Months 3-6 | Brand authority, community presence, ongoing monitoring | +10-15 points |

**Projected GEO Score After 6 Months:** [Current + estimated improvement]/100

---

## Alternative Service Options

### [Other Tier 1]
[Brief 2-3 line description of what this tier includes and who it's for]

### [Other Tier 2]
[Brief 2-3 line description]

---

## Why GEO Matters Now

The AI search landscape is shifting rapidly:

- **$850M+ GEO market** in 2025, projected to reach **$7.3B by 2031** (34% CAGR)
- **AI-referred traffic converts 4.4x higher** than traditional organic search
- **Google AI Overviews** now reach 1.5B users/month across 200+ countries
- **ChatGPT** has 900M+ weekly active users searching with AI
- **Gartner predicts** traditional search traffic will drop 50% by 2028
- **Only 23% of marketers** are investing in GEO — early movers have a significant advantage

Companies that optimize for AI search now will dominate their industries in AI-generated recommendations. Those that don't will become invisible as AI search becomes the default.

---

## Next Steps

1. **Review this proposal** and reach out with any questions
2. **Schedule a 30-minute review call** to discuss findings and priorities
3. **Confirm scope and timeline** — we can begin within [X] days of agreement
4. **Phase 1 kickoff** — immediate action on critical fixes and quick wins

---

*This proposal was generated from a comprehensive GEO audit conducted on [Audit Date].*
*Audit covered [X] pages across [X] analysis categories.*
```

---

## Important Notes

- The proposal should feel like it was written by a consultant, not generated by a tool. Use natural language, not bullet-point dumps.
- Do NOT include exact pricing numbers unless the user specifies them with `--monthly`. The proposal shows tiers and scope — pricing is discussed in the review call.
- Always include the "Why GEO Matters Now" section with current market data. This educates the client and creates urgency.
- The projected score improvement should be realistic. Don't promise 100/100. A jump from 35 to 65 over 6 months is aggressive but achievable.
- If the audit found very few issues (score 80+), adjust the tone. Don't oversell — acknowledge strong performance and focus on maintaining competitive advantage.
- Output goes to `reports/<domain>/GEO-PROPOSAL-<domain>.md` following the project's output convention.
