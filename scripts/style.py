"""
GEO SLAB report voice — structured data.

Human-readable companion: /STYLE.md at repo root.
Edit both together. If they drift, STYLE.md is the spec and this file
must catch up.

All client-facing copy (prospect lite, full PDF, proposal, compare,
audit summaries) imports its score bands, sub-score descriptions,
issue translations, working-list copy, and £-impact numbers from
here. No skill or script should hard-code these strings.
"""

from __future__ import annotations


# ── Score band copy ─────────────────────────────────────────────────────────
# Verdict = the headline that sits next to the big score.
# Summary = the supporting paragraph immediately below.
# Bands match: 80+, 60-79, 40-59, 0-39.

SCORE_BANDS = [
    {
        "min": 80,
        "verdict": "Top 20% on the basics. The next move is worth real money.",
        "summary": "You've done the technical groundwork most haven't. What's missing is the authority signals that turn 'found' into 'cited'.",
    },
    {
        "min": 60,
        "verdict": "You're showing up sometimes. Your competitors are showing up more often.",
        "summary": "Your foundations are functional but AI engines can't confirm who you are. Brand signals and citable content are the missing pieces.",
    },
    {
        "min": 40,
        "verdict": "AI engines see your site but skip past it. The fixes are specific.",
        "summary": "Multiple gaps. Competitors with better GEO are taking the AI-driven enquiries that should be yours.",
    },
    {
        "min": 0,
        "verdict": "AI search is happening without you. Every week this continues, instructions go elsewhere.",
        "summary": "Critical gaps across the basics. AI engines can't reliably find, understand, or cite your firm.",
    },
]


def score_band(score: int) -> dict:
    """Return the band dict whose minimum the score meets or exceeds."""
    for band in SCORE_BANDS:
        if score >= band["min"]:
            return band
    return SCORE_BANDS[-1]


# ── Score labels (compact, for badges + tables) ─────────────────────────────
# Bands match SCORE_BANDS. Used for "62/100 — Fair" style call-outs.

SCORE_LABELS = [
    (80, "Good"),
    (60, "Fair"),
    (40, "Poor"),
    (0,  "Critical"),
]


def score_label(score: int) -> str:
    for floor, label in SCORE_LABELS:
        if score >= floor:
            return label
    return SCORE_LABELS[-1][1]


# ── Sub-score card descriptions ─────────────────────────────────────────────
# One line under each category card. Plain English, no jargon.

SCORE_CARD_DESCRIPTIONS = {
    "ai_citability":         "Whether AI engines can lift a paragraph from your site and quote it back to a prospect. Below 60 means they mostly can't.",
    "brand_authority":       "Whether AI engines can confirm you're a real, reputable firm via Wikipedia, Wikidata, trusted directories, and press. Below 60 means you look unverified.",
    "content_eeat":          "Whether your content shows real Experience, Expertise, Authoritativeness, and Trust signals. Below 60 means it reads as generic to AI.",
    "technical":             "Whether AI crawlers can reach your pages and understand the structure. Below 60 usually means crawl access or rendering issues.",
    "schema":                "Whether you've told search engines what each page IS (a service, a person, a location) in machine-readable form.",
    "platform_optimization": "Aggregate visibility across the 9 major AI search engines (ChatGPT, Perplexity, Gemini, Bing Copilot, Google AI Overviews, Grok, DeepSeek, Meta AI, Mistral).",
}


# ── Issue translation table ─────────────────────────────────────────────────
# Internal slug → client-facing title + body. Every issue surfaced in a
# client report must come through here. If you find an internal slug not
# in this table, add it before the report ships.
#
# Bodies follow the pattern: what it is (1 sentence), what it costs in
# plain terms (1-2 sentences), how common the fix is + how hard (1
# sentence with a benchmark + time estimate).

ISSUE_COPY = {
    "blocks_ai_crawlers": {
        "title": "AI engines locked out at the front door",
        "body": (
            "Your site is telling the bots that feed ChatGPT, Claude, and Perplexity that "
            "they're not allowed in. As long as this stays in place, those AI engines "
            "literally cannot read your pages, no matter how good your content is. Roughly "
            "12% of UK firms in your sector do this by accident. Under 10 minutes to fix."
        ),
    },
    "no_llmstxt": {
        "title": "No AI guidance file published",
        "body": (
            "AI engines look for a small file that tells them which of your pages matter "
            "most. Without it, ChatGPT and Perplexity guess — and they often guess wrong, "
            "citing a competitor's clearer page instead. Roughly 8% of UK firms in your "
            "sector have one. Under an hour to fix."
        ),
    },
    "no_schema": {
        "title": "AI engines can't tell what your site is",
        "body": (
            "AI engines can't tell what your site is. Your platform adds basic tagging but "
            "no machine-readable description of the firm, your services, or your offices. "
            "AI has to guess from page text alone, which is unreliable. Fix is a single "
            "block of code in the page head, typically under two hours."
        ),
    },
    "no_entity_schema": {
        "title": "AI can't confirm what your firm is",
        "body": (
            "AI engines don't have a machine-readable file confirming you're a law firm, "
            "what you do, or where your offices are. They guess from page text, which is "
            "unreliable. The fix is a single block of code in the page head, typically "
            "under two hours of developer time."
        ),
    },
    "no_person_schema": {
        "title": "Solicitor profiles aren't tagged",
        "body": (
            "Your solicitor profiles aren't tagged in a way AI engines can read. AI can't "
            "connect the named solicitor to your firm or to the specialism without this. "
            "Standard template work, half a day to roll out across every bio."
        ),
    },
    "no_faq_schema": {
        "title": "FAQs aren't tagged for AI quoting",
        "body": (
            "FAQ blocks on your service pages aren't tagged in a way AI can quote. "
            "Question-and-answer style is one of the most heavily cited formats in Google "
            "AI Overviews and Perplexity. Tag the blocks you already have — under two hours."
        ),
    },
    "no_sameas": {
        "title": "Authority links not connected to your site",
        "body": (
            "Your reviews, professional listings, accreditations and Companies House "
            "record aren't linked to your site in a way AI engines verify. The "
            "credentials exist but AI can't confirm they're yours. One config block "
            "sitewide."
        ),
    },
    "low_citability": {
        "title": "Pages not written for AI to quote",
        "body": (
            "AI engines prefer paragraphs they can lift whole and quote — 130–170 words, "
            "self-contained, fact-rich, directly answering a question. Your pages are "
            "written for human skim-reading, which is fine for Google but invisible to AI "
            "citation. Competitors who've restructured for citability are being quoted in "
            "answers about your specialism."
        ),
    },
    "no_mobile_viewport": {
        "title": "Site not configured for mobile screens",
        "body": (
            "Your site is missing the setting that tells phones how to display the page. "
            "Most prospects search from a phone, and AI engines treat mobile-broken sites "
            "as a quality signal that downgrades you. One-line fix in the page head."
        ),
    },
    "missing_gbp": {
        "title": "Google Business Profile gaps",
        "body": (
            "Your Google Business Profile is missing fields AI search engines lean on for "
            "local recommendations — opening hours, services, photos, or reviews. AI "
            "answers about 'best [service] in [town]' pull straight from this profile. A "
            "complete profile usually takes under an hour to fix."
        ),
    },
    "multi_gbp_unclaimed": {
        "title": "Office Google profiles need claim, verify, and consistency audit",
        "body": (
            "Each office needs its Google profile claimed and verified. Name, address, "
            "and phone must match exactly across your site, Google, and major directories. "
            "AI engines pull these for 'best solicitor in [town]' answers — any mismatch "
            "makes AI skip you. One-pass audit, typically a week across a multi-office firm."
        ),
    },
    "nap_inconsistent": {
        "title": "Name, address, phone inconsistent",
        "body": (
            "Your firm name, address, or phone number is different across your website, "
            "Google Business Profile, and the major UK directories. AI engines treat "
            "inconsistency as a confidence-killer and demote you in local answers. "
            "One-pass directory audit — usually under a day."
        ),
    },
    "thin_eeat": {
        "title": "Thin trust signals",
        "body": (
            "Your content shows little of who you are — no author bios, no case histories, "
            "no specific credentials. AI engines look hard for evidence of real experience, "
            "expertise, and trust when picking who to cite. Without it you read as generic, "
            "even if your work is excellent."
        ),
    },
    "no_wikipedia": {
        "title": "Not on Wikipedia or Wikidata",
        "body": (
            "AI engines use Wikipedia and Wikidata as the primary trust anchor for entity "
            "verification — does this firm actually exist as a real, notable thing? "
            "Without an entry, your AI confidence score starts at zero even with a century "
            "of trading behind you. A Wikidata entry is cheap (under a day) and "
            "surprisingly underused in UK SMB sectors."
        ),
    },
    "no_press_clutch": {
        "title": "No press or third-party validation",
        "body": (
            "AI engines look for third-party signals — press mentions, listings on "
            "industry review sites, forum discussions, industry awards — to decide whether "
            "to cite a firm. With none of these, you depend entirely on your own pages, "
            "which AI weights less. A targeted three-month outreach plan typically lands "
            "enough signals to shift this category."
        ),
    },
    "slow_mobile": {
        "title": "Homepage too slow on mobile",
        "body": (
            "Your homepage takes several seconds to render its largest element on mobile. "
            "AI engines that use real-user speed signals (Google AI Overviews especially) "
            "will rank faster competitors above you. Desktop is usually fine — the gap is "
            "mobile only. Image format and loading-hint changes, typically one engineering "
            "day."
        ),
    },
    "outdated_image_formats": {
        "title": "Outdated image format on the homepage hero",
        "body": (
            "Image format and loading hints on your homepage hero are out of date. Modern "
            "formats load 30–50% faster. Configuration change only — no design work."
        ),
    },
    "no_author_byline": {
        "title": "Articles don't show who wrote them",
        "body": (
            "Your articles don't show who wrote them. AI engines treat unsigned content as "
            "less trustworthy. The author data exists in your CMS — the page template just "
            "isn't displaying it. 30 minutes of work."
        ),
    },
    "no_article_schema": {
        "title": "Articles not tagged as journalism",
        "body": (
            "Your news and insight articles aren't tagged as authored journalism. AI "
            "engines treat them as generic web pages instead of editorial content from an "
            "established firm. Template change, two hours."
        ),
    },
    "weak_og_tags": {
        "title": "Social preview images fall back to defaults",
        "body": (
            "When someone shares your pages on social media, the preview image and "
            "description fall back to generic banners. Worth fixing for share-quality but "
            "not blocking AI search visibility."
        ),
    },
    "missing_security_headers": {
        "title": "Standard security hardening missing",
        "body": (
            "Standard security hardening is missing. Not blocking AI search visibility but "
            "worth fixing during the same engineering window — typically a single config "
            "file change."
        ),
    },
    "no_x_account": {
        "title": "No X/Twitter presence — costs you Grok",
        "body": (
            "Grok (Elon Musk's AI) relies heavily on real-time X/Twitter content. With no "
            "active account, Grok cannot cite you on topics where you'd otherwise be a "
            "credible source. This is the cheapest single way to lift your Grok score."
        ),
    },
    "service_intros_marketing_prose": {
        "title": "Service pages open with marketing prose",
        "body": (
            "AI engines prefer paragraphs they can lift whole — 130–170 words, "
            "self-contained, fact-rich, directly answering a question. Your service pages "
            "open with marketing prose AI engines skip. Restructure the top five around "
            "question headings with answer blocks."
        ),
    },
    "js_only_schema": {
        "title": "Machine-readable tagging only appears after JavaScript runs",
        "body": (
            "Your tagging is added by the page's JavaScript instead of the page itself. AI "
            "crawlers don't run JavaScript and miss it entirely. Switch the relevant "
            "plugin to render the tags on the server — typically half a day."
        ),
    },
    "no_ssr_content": {
        "title": "Page is empty until JavaScript runs",
        "body": (
            "Most of the page only appears once a browser runs your JavaScript. AI crawlers "
            "don't run JavaScript and see a near-empty page. This is the biggest single "
            "barrier to AI citation a site can have. Requires switching to server-side "
            "rendering — typically multi-week, but unavoidable."
        ),
    },
    "cookie_wall_blocks_bots": {
        "title": "Cookie banner hides content from AI crawlers",
        "body": (
            "Your cookie banner covers the page content and AI crawlers can't dismiss it. "
            "They see the banner instead of the real page. One-line change to allow content "
            "behind the banner."
        ),
    },
}


# ── Section labels (used by every renderer) ─────────────────────────────────
# Plain-English category headings — consistent across prospect, client full
# audit, proposal, and compare reports. Don't mix terminology between
# deliverables. The developer report keeps technical labels — see DEV_LABELS.

DISPLAY_LABELS = {
    "AI Citability":             "AI CITABILITY",
    "Brand Authority":           "DOES AI TRUST YOU",
    "Content E-E-A-T":           "EXPERTISE SIGNALS",
    "Technical GEO":             "AI CRAWLER ACCESS",
    "Schema & Structured Data":  "HOW AI READS YOUR SITE",
    "Schema":                    "HOW AI READS YOUR SITE",
    "Platform Optimization":     "VISIBILITY ACROSS AI ENGINES",
    "Platform Optimisation":     "VISIBILITY ACROSS AI ENGINES",
}

# Subtitles render under each category card in the client report.
SECTION_SUBTITLES = {
    "AI CITABILITY":               "Whether AI engines can lift a paragraph from your site and quote it back.",
    "DOES AI TRUST YOU":           "Whether AI engines treat your firm as a real, reputable entity.",
    "EXPERTISE SIGNALS":           "Whether your content shows real experience, expertise, and trust.",
    "AI CRAWLER ACCESS":           "Whether AI crawlers can reach your pages and read the content.",
    "HOW AI READS YOUR SITE":      "Whether AI engines have a machine-readable description of your business.",
    "VISIBILITY ACROSS AI ENGINES":"How visible you are across the nine AI engines that now compete with Google.",
}

# Developer report keeps technical category names — that audience wants them.
DEV_LABELS = {
    "AI Citability":             "AI CITABILITY",
    "Brand Authority":           "BRAND AUTHORITY",
    "Content E-E-A-T":           "CONTENT E-E-A-T",
    "Technical GEO":             "TECHNICAL GEO",
    "Schema & Structured Data":  "SCHEMA & STRUCTURED DATA",
    "Schema":                    "SCHEMA & STRUCTURED DATA",
    "Platform Optimization":     "PLATFORM OPTIMISATION",
    "Platform Optimisation":     "PLATFORM OPTIMISATION",
}


# ── Agent voice prompt (every analysis agent imports this) ──────────────────
# Every analysis agent emits two layers. The technical_findings field feeds
# the developer PDF. The client_summary field is the only thing the partner
# sees — every sentence rewritten per /STYLE.md. The orchestrator passes this
# string into every subagent prompt and reminds the agent before output time.

AGENT_VOICE_RULES = """
TWO-LAYER OUTPUT — MANDATORY.

Your findings are rendered into TWO separate PDFs:
  - GEO-REPORT-<domain>.pdf       (client; partner reads this; plain English only)
  - GEO-DEV-REPORT-<domain>.pdf   (developer/agency; technical instructions)

You must output BOTH of these top-level fields in your structured response:

technical_findings: list of objects, each {
    "slug":     "<internal_slug>",        # matches ISSUE_COPY where possible
    "severity": "CRITICAL|HIGH|MEDIUM|LOW",
    "title":    "<short technical name>", # raw spec language OK here
    "detail":   "<specifics: LCP ms, schema types, headers, file paths, code>",
    "fix":      "<technical instruction for the developer/agency>"
}

client_summary: list of objects, each {
    "slug":        "<same slug as the matching technical_findings entry>",
    "severity":    "CRITICAL|HIGH|MEDIUM|LOW",
    "title":       "<plain-English headline a partner understands>",
    "description": "<3–4 plain-English sentences: what this means for me, what it costs me, how hard the fix is>"
}

Pair entries by slug. Every technical finding must have a matching client_summary entry.

CLIENT_SUMMARY RULES — read /STYLE.md before writing this field.
The managing partner does NOT know what any of these mean and they must NEVER
appear in client_summary text:
JSON-LD, FAQPage, LCP, INP, CLS, HSTS, CSP, X-Frame-Options, Referrer-Policy,
sameAs, OG, Open Graph, Yoast, WordPress, fetchpriority, preconnect, defer,
WebP, AVIF, PageSpeed, taxonomy, NAP, GBP, E-E-A-T, schema.org, llms.txt,
robots.txt, NewsArticle, Article schema, LegalService, LocalBusiness, Person
schema, Attorney schema, AggregateRating, Organization schema.

Translate every technical concept through the issue map in
scripts/style.py:ISSUE_COPY. Re-use existing slugs where they fit. If you add
a new slug, add the entry to ISSUE_COPY in the same change.

UK English only — never optimize, organize, analyze, color, center, behavior.
No exclamation marks. No words in style.py:BANNED_WORDS. Sentences over 25
words are drafts. No corporate filler.

TECHNICAL_FINDINGS RULES — accuracy first.
Raw spec names allowed and encouraged. Cite exact thresholds, schema type
names, header names, file paths, screenshot paths. The agency reading this
needs enough to act without a second pass.
""".strip()



# ── Good-news translation table ─────────────────────────────────────────────
# Each working-state checkbox is framed as relative positioning, never a
# binary tick. Pattern: "[what's there] — [how rare or valuable that is]."

WORKING_COPY = {
    "has_llmstxt":   "llms.txt published — you're in the ~8% of firms in your sector that have done this.",
    "has_schema":    "Structured data in place — AI engines can parse what your homepage is about.",
    "allows_ai":     "AI crawlers welcomed — you haven't accidentally blocked ChatGPT, Claude, or Perplexity from indexing you.",
    "mobile_ok":     "Mobile-ready — your site renders correctly on the devices most prospects use to search.",
    "https_ok":      "HTTPS in place — AI engines won't down-rank you for an insecure connection.",
    "fast_response": "Fast response — your homepage loads quickly enough that crawlers don't time out.",
    "fallback":      "Site responds and serves content to crawlers.",
}


# ── £-impact templates by sector ────────────────────────────────────────────
# Used in the Why section of the prospect lite report and elsewhere.
# (singular_unit, deal_low_£, deal_high_£). If a sector slug isn't in the
# table, omit the £-line — wrong is worse than absent.

INDUSTRY_VALUES = {
    "family_law":         ("instruction",       4000,  20000),
    "criminal_defence":   ("case",              3000,  15000),
    "conveyancing":       ("transaction",       1500,   4000),
    "personal_injury":    ("case",              5000,  25000),
    "immigration":        ("matter",            2000,   8000),
    "commercial_law":     ("matter",           10000, 100000),
    "private_client":     ("matter",            3000,  15000),
    "dentist":            ("treatment plan",    2000,   8000),
    "plastic_surgery":    ("procedure",         5000,  15000),
    "fertility":          ("cycle",             6000,  12000),
    "rehab":              ("admission",         8000,  30000),
    "tradespeople":       ("job",                500,   5000),
    "saas_b2b":           ("annual contract",   5000,  50000),
}

INDUSTRY_DISPLAY_NAMES = {
    "family_law":       "family law",
    "criminal_defence": "criminal defence",
    "conveyancing":     "conveyancing",
    "personal_injury":  "personal injury",
    "immigration":      "immigration",
    "commercial_law":   "commercial law",
    "private_client":   "private client",
    "dentist":          "dental",
    "plastic_surgery":  "plastic surgery",
    "fertility":        "fertility",
    "rehab":            "addiction treatment",
    "tradespeople":     "trades",
    "saas_b2b":         "B2B SaaS",
}


# ── Banned filler words ─────────────────────────────────────────────────────
# Anything in this list signals a draft that hasn't been edited.
# Grep target for static voice audits.

BANNED_WORDS = [
    "leverage", "unlock", "synergy", "synergies", "ecosystem",
    "journey", "robust", "holistic", "best-in-class", "best in class",
    "world-class", "world class", "cutting-edge", "cutting edge",
    "seamless", "seamlessly", "next-generation", "next generation",
    "thought leader", "thought leadership", "deep dive",
    "value-add", "value add", "circle back", "level up", "move the needle",
    "win-win", "low-hanging fruit", "synergistic",
]


# ── American → British spelling pairs ───────────────────────────────────────
# Grep target. Any of the left-side spellings in client-facing copy is a bug.

US_TO_UK_SPELLINGS = {
    "optimize":   "optimise",
    "optimized":  "optimised",
    "optimizing": "optimising",
    "organize":   "organise",
    "organized":  "organised",
    "organizing": "organising",
    "analyze":    "analyse",
    "analyzed":   "analysed",
    "analyzing":  "analysing",
    "color":      "colour",
    "colors":     "colours",
    "center":     "centre",
    "centers":    "centres",
    "favor":      "favour",
    "favorite":   "favourite",
    "behavior":   "behaviour",
    "license":    "licence",  # noun form; "license" as verb is fine in UK
    "defense":    "defence",
    "offense":    "offence",
    "specialize": "specialise",
    "specialized":"specialised",
    "specializes":"specialises",
    "specializing":"specialising",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def revenue_impact_line(industry: str, deal_low: int = 0, deal_high: int = 0) -> str:
    """Compose the £-impact line. Returns empty string if no sector data."""
    unit = None
    low = deal_low or 0
    high = deal_high or 0
    if industry and industry in INDUSTRY_VALUES:
        unit, preset_low, preset_high = INDUSTRY_VALUES[industry]
        if not low:
            low = preset_low
        if not high:
            high = preset_high
    if not (unit and low and high):
        return (
            "If AI search is sending even one prospect a month to a cited competitor, "
            "that's months of revenue walking past you every year."
        )
    annual_low = (low * 12) // 1000
    annual_high = (high * 12) // 1000
    return (
        f"For a UK firm in this sector, one {unit} is worth £{low:,}–£{high:,}. "
        f"If AI search is sending even one prospect a month to a cited competitor, "
        f"that's £{annual_low}k–£{annual_high}k a year walking past you."
    )


def sector_display(slug: str) -> str:
    """Return the human-facing sector label, e.g. 'family law'."""
    return INDUSTRY_DISPLAY_NAMES.get(slug, slug.replace("_", " ").lower())


# ── Proposal tier copy ──────────────────────────────────────────────────────
# Used by render_proposal.py. Tier copy is the most prose-heavy place
# jargon leaks into client deliverables — keep canonical here.

PROPOSAL_TIERS = {
    "basic": {
        "title": "Basic — Monthly AI-search monitoring",
        "subtitle": "Right for firms in maintenance mode after the heavy lifting is done.",
        "desc": (
            "Fixed-scope monthly audit, ongoing checks on the files AI engines read first, "
            "month-on-month delta tracking, and email support. Suited to the steady-state phase "
            "once the foundations are in place — not the right shape for closing a wide gap "
            "from a Poor score."
        ),
        "bullets": [
            "Monthly AI-visibility audit with month-on-month scorecard",
            "Ongoing checks on the indexing files AI engines look for first",
            "Schema and structured-data health monitoring",
            "Email support inside one working day",
        ],
    },
    "standard": {
        "title": "Standard — Full AI-search optimisation programme",
        "subtitle": "The right shape for firms scoring 40–70 who want to be cited, not just found.",
        "desc": (
            "End-to-end work on the foundations AI engines rely on: clearing crawler blocks, "
            "publishing the discovery file that points AI at your strongest pages, fixing the "
            "machine-readable signals that tell AI what your business is, and rewriting "
            "page passages so AI can quote them whole. Monthly audit + delta tracking + "
            "priority support."
        ),
        "focus": (
            "Critical fixes — open the door for ChatGPT, Claude, and Perplexity (currently "
            "blocked at the front door), fix the cookie banner so AI crawlers see the real "
            "page, address the speed issues holding back search ranking, fix the sitemap, "
            "tidy LinkedIn, and claim every Google Business Profile listed in your name."
        ),
        "bullets": [
            "Robots and crawler access — unblock the bots that feed AI answers",
            "Publish and maintain the discovery file AI engines look for",
            "Schema + structured-data rewrites across the key pages",
            "Citability rewrites — restructure paragraphs so AI can quote them",
            "Monthly audit + month-on-month delta tracking",
            "Priority support, same-day response",
        ],
    },
    "premium": {
        "title": "Premium — Complete AI-search transformation",
        "subtitle": "For firms who need to move from invisible to authoritative across every AI engine.",
        "desc": (
            "Everything in Standard plus a full brand-authority programme: Wikipedia / Wikidata "
            "entity work, press and third-party validation outreach, and proactive citation "
            "tracking across all nine AI search engines. Dedicated account lead. Weekly "
            "stand-up. Quarterly business review."
        ),
        "bullets": [
            "Everything in Standard",
            "Wikipedia / Wikidata entity work",
            "Press + third-party validation outreach (three-month plan)",
            "Citation tracking across all nine AI engines, monthly",
            "Dedicated account lead, weekly stand-up, quarterly review",
        ],
    },
}


# ── Market-context stats (proposal hero block) ──────────────────────────────
# Used by render_proposal.py "Why AI search matters now" panel. Sourced from
# public industry reports — update yearly. Keep numbers, drop jargon.

MARKET_STATS = [
    {"num": "58%",   "text": "Of UK searches now end without a click — AI answers the question on the results page"},
    {"num": "1–3",   "text": "Firms typically cited in any given AI answer"},
    {"num": "9",     "text": "Major AI search engines now competing with Google for the same intent"},
    {"num": "23%",   "text": "Share of UK marketers actively investing in AI-search visibility — early-mover window is open"},
]

