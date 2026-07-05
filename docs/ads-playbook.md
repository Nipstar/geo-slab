# GEO SLAB — Ads Playbook (spec §7)

Paid traffic → **antekautomation.com/services/geo-audit** → free check → Brevo
sequence → walkthrough. This is copy + config, not code. UTMs here match what the
`landing/geo-audit-embed.html` snippet captures and `funnel_report.py --campaign`
filters on.

## UTM taxonomy

Every ad URL: `https://antekautomation.com/services/geo-audit?utm_source=…&utm_medium=…&utm_campaign=…`

| Param | Values |
|-------|--------|
| `utm_source` | `google`, `meta` |
| `utm_medium` | `cpc` (search), `paid_social` (Meta) |
| `utm_campaign` | `geo-<vertical>-<geo>` e.g. `geo-plumber-hampshire` |

Keep `utm_campaign` identical to the DB `campaign` value so the funnel report ties spend to conversions.

## Google Search (high intent)

- **Match**: phrase/exact. Keywords: `is my business on chatgpt`, `ai search visibility`, `does chatgpt recommend my business`, `geo optimisation <town>`, `<trade> marketing <town>`.
- **Negative**: `jobs`, `course`, `free tool`, `login`.
- **Headlines** (30 char): `Invisible to ChatGPT?` · `Free AI Visibility Check` · `Does AI Recommend You?` · `See Your AI Score Free`
- **Descriptions** (90 char): `Find out in 60 seconds if ChatGPT, Gemini & Perplexity recommend your business. Free.` · `Your customers ask AI for recommendations. Are you the answer? Free check, no card.`
- **Budget**: start £15–20/day, one campaign per vertical, manual CPC cap.

## Meta (interruption / awareness)

- **Objective**: Leads (or Traffic to the page if pixel-light at launch).
- **Audience**: local business owners, radius on target towns, interests = small business / marketing; age 30–60.
- **Primary text**: "When someone asks ChatGPT or Google's AI to recommend a {trade} near them, does your name come up — or a competitor's? Find out free in 60 seconds."
- **Headline**: "Is your business invisible to AI search?"
- **Creative**: neo-brutalist score card (coral/cream), big "23/100" style number. One static + one 6s video showing the check running.
- **Budget**: £10–15/day per ad set, 2–3 creatives, kill losers at £30 spend / 0 leads.

## Tracking

- Landing page fires `gtag('generate_lead')` + `fbq('Lead')` on a returned score (guarded — only if the pixels are pasted into the deployed page `<head>`).
- Server-side truth = `funnel_report.py --campaign geo-plumber-hampshire` (spend ÷ leads ÷ walkthroughs ÷ paid conversions). Trust this over pixel counts.

## Weekly review

1. `python3 scripts/funnel_report.py --campaign <c>` per active campaign.
2. Cost per free check = ad spend ÷ `checks.runs`. Cost per walkthrough = spend ÷ `walkthrough_booked`.
3. Pause any campaign over target CPL with no walkthrough after 2 weeks.
