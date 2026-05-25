---
name: geo-compare
description: >
  Monthly delta tracking and progress reporting for GEO clients. Compares two
  GEO audits (baseline vs. current), calculates score improvements across all
  categories, tracks action item completion, and generates a client-ready
  progress report. Use when user says "compare", "delta", "monthly report",
  "progress", or when running a monthly client check-in.
version: 1.0.0
tags: [geo, business, delta, monthly, reporting, client, progress]
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - Grep
---

# GEO Monthly Delta Report Generator

> **MANDATORY: Read `/STYLE.md` before generating any prose in this report.**
>
> The compare report is client-facing — plain English only. Pull issue text from the audit's `client_summary` field, not `technical_findings`. Section labels use the client-facing names — `DOES AI TRUST YOU`, `EXPERTISE SIGNALS`, `AI CRAWLER ACCESS`, `HOW AI READS YOUR SITE`, `VISIBILITY ACROSS AI ENGINES`.
>
> Banned-in-body list: `llms.txt`, `JSON-LD`, `robots.txt`, `E-E-A-T`, `schema.org`, `LCP`, `HSTS`, `sameAs`, `FAQPage`, `Yoast`, `WordPress`, `fetchpriority`, `Organisation schema`, `LocalBusiness`, `LegalService`, `Person schema`. Use plain-English wrappers from `scripts/style.py:ISSUE_COPY`.
>
> UK English. No exclamation marks. No words from `style.py:BANNED_WORDS`.

## Purpose

Track GEO optimisation progress over time by comparing two audit snapshots. This skill extracts scores from both audits, calculates deltas, identifies what improved and what declined, and generates a client-ready progress report.

## Command

```
/geo compare <domain>                       — Auto-find latest two audits in reports/<domain>/
/geo compare <baseline.md> <current.md>     — Compare two specific audit files
```

---

## Execution Steps

### Step 1: Locate Audit Files

**If given a domain:**
1. Use Glob to find all audit files in `reports/<domain>/`:
   - Pattern: `reports/<domain>/GEO-AUDIT-REPORT*.md`
   - Also check: `reports/<domain>/GEO-REPORT-*.md`
2. Sort by filename or date embedded in file (most recent = current, second-most-recent = baseline)
3. If only one audit exists, inform the user they need at least two audits to compare. Suggest running `/geo audit <url>` first.

**If given two file paths:**
1. Read both files directly
2. Determine which is baseline (older) and which is current (newer) by parsing the audit date

### Step 2: Extract Scores

Parse both audit files for these score markers using regex patterns:

```
Score markers to extract:
- "GEO Score: XX/100" or "Overall GEO Score: XX/100" or "GEO Score:**XX**/100"
- "AI Citability: XX/100" or "Citability: XX" or "AI Citability & Visibility.*XX/100"
- "Brand Authority: XX/100" or "Brand Authority Signals.*XX/100"
- "Content.*E-E-A-T: XX/100" or "Content Quality: XX/100"
- "Technical: XX/100" or "Technical Foundations: XX/100" or "Technical GEO: XX/100"
- "Schema: XX/100" or "Schema & Structured Data: XX/100" or "Structured Data: XX/100"
- "Platform: XX/100" or "Platform Optimisation: XX/100"
```

Also extract:
- **Crawler access:** Look for GPTBot, ClaudeBot, PerplexityBot status (Allowed/Blocked)
- **Platform scores:** Individual platform readiness scores (Google AIO, ChatGPT, Perplexity, Gemini, Copilot, Grok, DeepSeek, Meta AI, Mistral)
- **Finding counts:** Count items marked CRITICAL, HIGH, MEDIUM, LOW
- **Audit date:** Parse from "Audit Date:", "Date:", or file modification time

If exact numeric scores are not found in the audit text, use contextual analysis:
- Look for phrases like "improved", "declined", "unchanged" in findings
- Estimate from severity descriptions (e.g., "Critical" → ~20, "Fair" → ~50, "Good" → ~70)
- Flag estimated scores with "(est.)" in output

### Step 3: Calculate Deltas

For each score category:

```
delta = current_score - baseline_score
```

Assign trend indicators:
- `▲` if delta > 0 (improved)
- `▼` if delta < 0 (declined)
- `──` if delta == 0 (unchanged)

Calculate overall trend:
- **Improving:** GEO Score delta > 0 AND majority of categories improved
- **Declining:** GEO Score delta < 0 AND majority of categories declined
- **Mixed:** Some improved, some declined
- **Stable:** All deltas within +/- 2 points

### Step 4: Analyse Changes

**What Improved:**
- List each category that improved with specific evidence from the current audit
- Note specific actions that were taken (e.g., "Schema score rose from 4 to 52 — Organisation and LocalBusiness schema were deployed")
- Highlight cross-category impacts (e.g., "Adding Wikipedia entry improved both Brand Authority (+15) and ChatGPT readiness (+12)")

**What Declined:**
- List each category that declined with explanation
- Distinguish between real declines (something broke) vs. measurement variance
- Flag any newly discovered issues not present in baseline

**Unchanged Issues:**
- List critical/high items from baseline that remain unaddressed
- This is important for client accountability — shows what was recommended but not acted on

### Step 5: Generate Recommended Actions

Based on the delta analysis:
1. Prioritise actions that address declining categories first
2. Then address unchanged critical issues
3. Then suggest next-level improvements for categories already improving
4. Include estimated score impact for each action

### Step 6: Write Report

Generate the report file to `reports/<domain>/GEO-COMPARE-<domain>-<YYYY-MM>.md`.

---

## Output Format

```markdown
# GEO Monthly Progress Report — [Domain]

**Period:** [Baseline Date] → [Current Date]
**Overall Trend:** [Improving / Declining / Mixed / Stable]
**GEO Score Change:** [baseline]/100 → [current]/100 ([+/-X] points)

---

## Score Summary

| Category | Baseline | Current | Delta | Trend |
|---|---|---|---|---|
| **GEO Score** | **XX/100** | **XX/100** | **+X** | **▲** |
| AI Citability | XX/100 | XX/100 | +X | ▲ |
| Brand Authority | XX/100 | XX/100 | -X | ▼ |
| Content E-E-A-T | XX/100 | XX/100 | +X | ▲ |
| Technical | XX/100 | XX/100 | +X | ▲ |
| Schema | XX/100 | XX/100 | +X | ▲ |
| Platform Optimisation | XX/100 | XX/100 | +X | ▲ |

## Platform Readiness Changes

| Platform | Baseline | Current | Delta | Trend |
|---|---|---|---|---|
| Google AI Overviews | XX | XX | +X | ▲ |
| ChatGPT Web Search | XX | XX | +X | ▲ |
| Perplexity AI | XX | XX | +X | ▲ |
| Google Gemini | XX | XX | +X | ▲ |
| Bing Copilot | XX | XX | +X | ▲ |
| Grok (xAI) | XX | XX | +X | ▲ |
| DeepSeek | XX | XX | +X | ▲ |
| Meta AI | XX | XX | +X | ▲ |
| Mistral (Le Chat) | XX | XX | +X | ▲ |

## Crawler Access Changes

| Crawler | Baseline | Current | Change |
|---|---|---|---|
| GPTBot | [Status] | [Status] | [Changed/Unchanged] |
| ClaudeBot | [Status] | [Status] | [Changed/Unchanged] |
| PerplexityBot | [Status] | [Status] | [Changed/Unchanged] |

---

## What Improved

[Bulleted list with specific evidence]

## What Declined

[Bulleted list with explanation and recommended fixes]

## Unchanged Issues (Still Outstanding)

[Items from baseline recommendations that were not addressed]

---

## Recommended Next Actions

### High Priority (Address This Month)
1. **[Action]** — Expected impact: +X to [Category] — Effort: [Low/Medium/High]
2. **[Action]** — Expected impact: +X to [Category] — Effort: [Level]

### Medium Priority (Next Quarter)
1. **[Action]** — Expected impact: +X to [Category]
2. **[Action]** — Expected impact: +X to [Category]

---

*Generated by GEO SLAB — Antek Automation — antekautomation.com*
*Baseline: [file path or date]*
*Current: [file path or date]*
```

---

## Important Notes

- Always show the actual score numbers, not just trends. Clients want to see "42 → 58" not just "improved."
- If scores are estimated (not directly parseable from audit files), flag them clearly with "(est.)"
- Platform readiness changes are optional — only include if both audits contain platform scores.
- Crawler access changes are always important to highlight, especially if a previously allowed crawler is now blocked.
- Keep the tone professional and client-friendly. This report often goes directly to stakeholders.
- The delta report does NOT re-run the audit. It only compares existing audit files.
