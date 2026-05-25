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
        "title": "AI crawlers blocked",
        "body": (
            "Your robots.txt disallows GPTBot, ClaudeBot, PerplexityBot, or Google-Extended — "
            "the bots that feed AI search answers. As long as this stays in place, ChatGPT "
            "and Perplexity literally cannot read your pages, no matter how good your "
            "content is. Roughly 12% of UK firms in your sector accidentally do this. The "
            "fix is a one-line robots.txt change, under 10 minutes."
        ),
    },
    "no_llmstxt": {
        "title": "No llms.txt published",
        "body": (
            "llms.txt is the file that tells AI engines which of your pages matter most. "
            "Without it, ChatGPT and Perplexity guess — and they often guess wrong, citing "
            "a competitor's clearer page instead. Roughly 8% of UK firms in your sector "
            "have published one. The fix takes under an hour."
        ),
    },
    "no_schema": {
        "title": "No structured data",
        "body": (
            "There's no JSON-LD schema on your homepage. Schema is how you tell AI what "
            "your business is — a law firm, what services, which locations, who the "
            "partners are. Without it, AI engines guess from page text alone and "
            "frequently confuse you with another firm. The fix is a single block of code "
            "in the page head, typically under two hours."
        ),
    },
    "low_citability": {
        "title": "Content not citable by AI",
        "body": (
            "AI engines prefer paragraphs they can lift whole and quote — 130-170 words, "
            "self-contained, fact-rich, directly answering a question. Your pages are "
            "written for human skim-reading, which is fine for Google but invisible to AI "
            "citation. Competitors who've restructured for citability are being quoted in "
            "answers about your specialism."
        ),
    },
    "no_mobile_viewport": {
        "title": "No mobile viewport",
        "body": (
            "Your site is missing the mobile viewport meta tag. Most prospects search from "
            "a phone, and AI engines treat mobile-broken sites as a quality signal that "
            "downgrades you. This is a one-line fix in the page head."
        ),
    },
    "missing_gbp": {
        "title": "Google Business Profile gaps",
        "body": (
            "Your Google Business Profile is missing fields AI search engines lean on for "
            "local recommendations — opening hours, services, photos, or reviews. AI "
            "answers about 'best [service] in [town]' pull straight from GBP. A complete "
            "profile usually takes under an hour to fix."
        ),
    },
    "nap_inconsistent": {
        "title": "Name, address, phone inconsistent",
        "body": (
            "Your firm name, address, or phone number is different across your website, "
            "Google Business Profile, and the major UK directories. AI engines treat "
            "inconsistency as a confidence-killer and demote you in local answers. The fix "
            "is a one-pass directory audit — usually under a day."
        ),
    },
    "thin_eeat": {
        "title": "Thin trust signals",
        "body": (
            "Your content shows little of who you are — no author bios, no case histories, "
            "no specific credentials. AI engines weight Experience, Expertise, "
            "Authoritativeness, and Trust signals heavily when picking who to cite. "
            "Without them you read as generic, even if your work is excellent."
        ),
    },
    "no_wikipedia": {
        "title": "Not on Wikipedia or Wikidata",
        "body": (
            "AI engines use Wikipedia and Wikidata as a primary trust anchor for entity "
            "verification — does this firm actually exist as a real, notable thing? "
            "Without an entry, you start every AI query at zero. A Wikidata entry is "
            "cheap (under a day) and surprisingly underused in UK SMB sectors."
        ),
    },
    "no_press_clutch": {
        "title": "No press or third-party validation",
        "body": (
            "AI engines look for third-party signals — press mentions, Clutch profiles, "
            "Reddit threads, industry awards — to decide whether to cite a firm. With "
            "none of these, you depend entirely on your own pages, which AI weights less. "
            "A targeted three-month outreach plan typically lands enough signals to shift "
            "this category."
        ),
    },
}


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

