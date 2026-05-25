---
name: geo-prospect
description: Generate a lite GEO prospect report from full audit data. Shows top problems (no fixes), category scores, and a full-audit CTA. Use after running /geo-audit. Outputs a branded HTML + PDF for cold outreach or as an entry-level product.
version: 1.0.0
author: antek-automation
tags: [geo, prospect, report, sales, outreach, lite]
---

# GEO Prospect Report Generator

## Purpose

This skill takes the output of a full GEO audit and produces a condensed prospect report:
- **Top 3 problems** — identified clearly, no fix instructions
- **Category scores** — all six, with the weakest highlighted
- **What's working** — 2–3 genuine positives to build credibility
- **Full audit teaser** — what the prospect doesn't see in this scan
- **CTA** — soft lead-magnet ask: book a 15-minute walkthrough where Andy opens ChatGPT/Claude/Perplexity live and shows the firm where they appear (and don't). No pricing on the report — it's a teaser.

Use it as a top-of-funnel lead magnet:
1. **Cold outreach attachment**: Send the PDF to show the firm their AI-visibility gaps. CTA invites a 15-minute live walkthrough call — not a paid audit.
2. **Booking-driver**: The report's only job is to get a meeting booked. Pricing conversation happens on the call.

---

## Workflow

### Step 1 — Collect audit data

You need the following from the completed audit. If you just ran `/geo-audit`, this is all in memory. If not, ask the user to provide the URL and run the audit first.

**Required:**
- Overall GEO score (0–100)
- Category scores: AI Citability, Brand Authority, Content E-E-A-T, Technical GEO, Schema, Platform Optimisation
- Full findings list with severity levels (critical / high / medium / low)
- Positive signals identified during the audit

**Optional:**
- Platform scores (ChatGPT, Perplexity, Gemini, Bing Copilot, Google AI Overviews) — not shown in prospect report but informs your framing
- Specific page data — useful for writing problem bodies

---

### Step 2 — Select the top 3 problems

From the full findings list, select exactly **3 problems** using this priority order:
1. Critical severity first
2. Then high severity
3. If tied, pick the one with the broadest business impact (affects multiple categories)

**Write each problem as:**
- **Title** — short, direct, no jargon. "No Wikipedia entry." Not "Insufficient Wikidata entity representation."
- **Body** — 2–3 sentences. State what's missing, why it matters to AI visibility, and the consequence. No fix instructions. No hedging. Antek voice.

**Antek voice rules for problem bodies:**
- Short sentences. 
- No corporate language.
- No hedging ("may", "could potentially", "consider").
- State consequences plainly: "AI models don't know you exist." Not "This may limit AI discoverability."
- UK English: optimise, authoritative, recognise.

**Example:**
```
title: "No Wikipedia entry"
body: "AI models don't know you exist. Wikipedia and Wikidata are the primary trust anchors for entity verification. Without them, your business won't appear in AI-generated recommendations regardless of how good your site is."
```

---

### Step 3 — Select 2–3 working signals

Pick genuine positives from the audit — things that are actually above average or correctly implemented. Don't pad this with mediocre signals.

**Format:** Short, factual, specific. "All major AI crawlers explicitly allowed in robots.txt." Not "Good technical foundation."

Aim for 2–3 items. If there are fewer genuine positives, use fewer. Don't invent them.

---

### Step 4 — Build the JSON data structure

Assemble this exact JSON structure:

```json
{
    "url": "https://example.com",
    "brand_name": "Company Name",
    "date": "6 April 2026",
    "geo_score": 59,
    "scores": {
        "ai_citability": 72,
        "brand_authority": 31,
        "content_eeat": 55,
        "technical": 72,
        "schema": 74,
        "platform_optimization": 52
    },
    "top_problems": [
        {
            "title": "No Wikipedia entry",
            "body": "AI models don't know you exist. Wikipedia and Wikidata are the primary trust anchors for entity verification. Without them, your business won't appear in AI-generated recommendations regardless of how good your site is."
        },
        {
            "title": "Zero editorial content",
            "body": "29 pages, no blog, no case studies, no guides. AI models have nothing to cite. FAQ schema blocks are not enough — they need long-form evidence to surface your business in competitive queries."
        },
        {
            "title": "Address mismatch across sources",
            "body": "Your Google Business Profile and schema show different building names and street names. AI models cross-reference these when resolving local entities. Conflicting signals suppress citation frequency."
        }
    ],
    "working": [
        "All major AI crawlers explicitly allowed in robots.txt",
        "Schema sameAs links across 9 platforms — above average for a UK SMB",
        "llms.txt implemented with pricing, services, and contact information"
    ],
    "cta_url": "https://antekautomation.com/contact",
    "cta_price": "",
    "cta_label": "Book a 15-minute walkthrough"
}
```

**Notes:**
- `date`: Write it out — "6 April 2026", not "2026-04-06"
- `scores`: Use the exact category keys above (snake_case)
- `top_problems`: Exactly 3 items (2 minimum if genuinely only 2 critical issues exist)
- `working`: 2–3 items, genuine positives only
- `cta_url`: Booking link (Cal.com / Calendly / native scheduler). Default `antekautomation.com/book`.
- `cta_price`: Leave empty by default — the report is a lead-magnet teaser, not a price list. Pricing is discussed on the call.
- `cta_label`: Default "Book a 15-minute walkthrough". The CTA must invite a meeting, never a purchase decision.

---

### Step 5 — Generate the HTML report

Save the JSON to a temporary file and run the script:

```bash
# Save JSON to temp file
cat > /tmp/prospect_data.json << 'EOF'
{ ... your JSON ... }
EOF

# Generate HTML
python3 "/path/to/scripts/generate_prospect_report.py" \
    --data /tmp/prospect_data.json \
    --output "/path/to/output/directory/"
```

The script outputs: `GEO-PROSPECT-{domain}.html`

---

### Step 6 — Generate the PDF

Use Chrome headless to PDF the HTML:

```bash
HTML_FILE="/path/to/GEO-PROSPECT-{domain}.html"
PDF_FILE="/path/to/GEO-PROSPECT-{domain}.pdf"

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
    --headless=new \
    --disable-gpu \
    --no-pdf-header-footer \
    --print-to-pdf="$PDF_FILE" \
    "file://$HTML_FILE"
```

On Linux or if Chrome is in PATH:
```bash
google-chrome --headless=new --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$PDF_FILE" "file://$HTML_FILE"
```

---

### Step 7 — Report to the user

Tell the user:
1. The output file paths (HTML + PDF)
2. The 3 problems you selected and why (brief)
3. Suggested outreach framing (one sentence hook for an email subject line or DM opener)

**Suggested outreach framing format:**
> "Your GEO score is {score}/100. The biggest issue: {top problem title in plain language}. I've put together a short scan — worth 5 minutes of your time."

---

## File Naming Convention

```
GEO-PROSPECT-{domain}.html
GEO-PROSPECT-{domain}.pdf
```

Examples:
- `GEO-PROSPECT-antekautomation.com.html`
- `GEO-PROSPECT-localplumber.co.uk.pdf`

---

## CTA Configuration by Use Case

The report is positioned as a **free lead-magnet teaser**. The CTA always invites a meeting, never a purchase. Pricing is held back for the call.

| Use case | `cta_price` | `cta_label` |
|---|---|---|
| Cold outreach (default) | `""` | `"Book a 15-minute walkthrough"` |
| Post-connection LinkedIn follow-up | `""` | `"Grab a 15-min slot"` |
| Warm referral | `""` | `"Book a quick call"` |

---

## Quality Checks Before Sending

- [ ] Score matches the audit data exactly
- [ ] Problem titles are in plain English — no jargon
- [ ] Problem bodies have no fix instructions
- [ ] Working items are genuinely positive, not filler
- [ ] CTA URL is correct and live
- [ ] PDF renders cleanly (check fonts loaded, borders visible)
- [ ] Domain name in filename matches the audited site

---

## Dependencies

- Python 3.8+
- Script: `scripts/generate_prospect_report.py` (no external dependencies beyond stdlib)
- Google Chrome (for PDF generation)
- Internet connection (Google Fonts load at render time — or pre-cache if sending offline)
