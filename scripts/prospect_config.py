#!/usr/bin/env python3
"""
GEO SLAB — prospecting outreach config + gates.

Single maintained home for the copy-critical lists that keep a prospecting
letter or email from looking broken:

  * VERTICAL_NOUN_PHRASES — the noun phrase used after "recommend ..." so a
    letter reads "recommend an accountancy firm", never "recommend a accountant".
    Used in BOTH the opening line and the problem bullets so one vocabulary runs
    through the whole letter.
  * AGGREGATOR_DENYLIST / PAGE_LABEL_DENYLIST — review sites, directories and
    website furniture that the competitor extractor sometimes captures. These
    must never reach a letter as "a competitor recommended in your place".
  * is_valid_competitor() / first_valid_competitor() — the gate the letter and
    email call before naming a competitor. Denylist + firm-signal validation.

Why not "validate against the local Google Places / Companies House universe":
the only cohort pulled per campaign is the prospect list itself (rival firms of
each other). Genuinely cited competitors are usually national/regional (James
Cowper Kreston, BDO, Baker Tilly) and are NOT in that small set, so treating
absence-from-cohort as grounds to suppress would strip every valid competitor
and leave every letter identical. Cohort membership is therefore a positive
booster (see is_in_universe), never a suppressor.

ponytail: plain module of literals + two small functions. No YAML/JSON to parse,
importable everywhere the copy is built. Run `python3 prospect_config.py` for the
self-check that pins the real regression strings.
"""
from __future__ import annotations

import re


# ── Per-vertical noun phrase ────────────────────────────────────────────────
# Matched by substring against the raw industry string, first hit wins, so
# "accountants southampton" -> "an accountancy firm".
VERTICAL_NOUN_PHRASES = {
    "accountanc": "an accountancy firm",
    "accountant": "an accountancy firm",
    "accounting": "an accountancy firm",
    "bookkeep": "an accountancy firm",
    "dental": "a dental practice",
    "dentist": "a dental practice",
    "orthodont": "a dental practice",
    "family law": "a law firm",
    "solicitor": "a law firm",
    "conveyanc": "a law firm",
    "legal": "a law firm",
    "law": "a law firm",
    "plumb": "a firm like yours",
    "electric": "a firm like yours",
    "roof": "a firm like yours",
    "builder": "a firm like yours",
    "trade": "a firm like yours",
}
DEFAULT_NOUN_PHRASE = "a firm like yours"


def noun_phrase(industry: str) -> str:
    """The noun phrase to follow 'recommend ...' for this vertical."""
    s = (industry or "").lower()
    for key, phrase in VERTICAL_NOUN_PHRASES.items():
        if key in s:
            return phrase
    return DEFAULT_NOUN_PHRASE


# ── Competitor validation gate ──────────────────────────────────────────────
# Exact matches (lower-cased, trimmed). Review sites, directories, and the AI
# engines themselves — never a rival firm.
AGGREGATOR_DENYLIST = {
    "trustpilot", "yell", "yell.com", "yelp", "checkatrade", "reviews.io",
    "clutch", "bark", "bark.com", "google", "google business",
    "google my business", "google maps", "google maps search", "bing",
    "facebook", "linkedin", "instagram", "twitter", "thomson local",
    "yellow pages", "yellowpages", "192.com", "freeindex", "cylex", "scoot",
    "houzz", "which", "which?", "tripadvisor", "reddit", "quora", "nextdoor",
    "citizens advice", "accountantsup", "unbiased", "comparison sites",
    "get quotes", "get a quote", "local facebook groups",
    "social media and community groups",
    "chatgpt", "openai", "perplexity", "gemini", "claude", "copilot",
}
# Substrings — catch composed junk like "Google Maps Search" or "Comparison Site".
AGGREGATOR_SUBSTRINGS = (
    "google", "facebook", "linkedin", "trustpilot", "yell.com", "yelp",
    "comparison site", "review site", "review platform", "maps search",
    "get quotes", "social media", "yellow pages",
)

# Website furniture / scraped page headings — never a business name.
PAGE_LABEL_DENYLIST = {
    "services offered", "about us", "about", "contact", "contact us", "home",
    "our team", "our services", "services", "testimonials", "menu",
    "opening hours", "privacy policy", "terms", "blog", "news", "faq", "faqs",
    "hourly rates", "regulatory compliance", "accounting firms", "technology use",
    "personal rapport", "client base", "why recommended", "proactive advice",
    "bookkeeping", "client reviews", "range of services", "initial consultation",
}

# Any token equal to one of these = advice/criteria heading, not a firm.
GENERIC_WORDS = {
    "rates", "compliance", "regulatory", "firms", "firm", "use", "technology",
    "personal", "rapport", "client", "base", "advice", "reviews", "review",
    "ratings", "rating", "tips", "tip", "general", "services", "service",
    "fees", "fee", "pricing", "price", "cost", "costs", "quotes", "quote",
    "experience", "qualifications", "qualification", "communication",
    "availability", "reputation", "expertise", "associations", "association",
    "directories", "directory", "recommendations", "recommendation",
    "considerations", "consideration", "credentials", "accreditation",
    "specialisation", "specialization", "referrals", "referral",
}
# A candidate starting with one of these is a question / advice heading.
QUESTION_WORDS = {
    "how", "why", "what", "when", "where", "who", "which", "some", "general",
    "other", "ask", "find", "finding", "choosing", "choose", "top", "best",
    "consider", "considering", "check", "look",
}
# Strong firm signals — presence + a real name shape means keep it.
FIRM_SIGNALS = (
    "ltd", "llp", "limited", "plc", "& co", "accountancy", "accountant",
    "chartered", "associates", "partners", "solicitors", "surgery", "practice",
    "consultancy", "advisory",
)


def is_valid_competitor(name: str) -> bool:
    """True only when `name` looks like a real rival firm, not a directory,
    review site, or a scraped page heading."""
    s = (name or "").strip().rstrip(".").strip()
    low = s.lower()
    if len(s) <= 3:
        return False
    if low in AGGREGATOR_DENYLIST or low in PAGE_LABEL_DENYLIST:
        return False
    if any(sub in low for sub in AGGREGATOR_SUBSTRINGS):
        return False
    toks = [t for t in re.split(r"\s+", s) if t and t != "&"]
    if not toks:
        return False
    if toks[0].lower() in QUESTION_WORDS:
        return False
    # Firm signal + a real multi-token shape → keep (blocks single-word
    # service labels like "Bookkeeping" that happen to contain a signal).
    if any(sig in low for sig in FIRM_SIGNALS) and len(toks) >= 2:
        return True
    # Otherwise: 2-4 proper-noun tokens, none an advice/criteria word.
    if not (2 <= len(toks) <= 4):
        return False
    if any(t.lower() in GENERIC_WORDS for t in toks):
        return False
    return all(t[:1].isupper() for t in toks)


def first_valid_competitor(names: list[str]) -> str | None:
    """First name in priority order that passes the gate, else None."""
    for n in names:
        if is_valid_competitor(n):
            return n.strip().rstrip(".").strip()
    return None


def is_in_universe(name: str, cohort_names: list[str]) -> bool:
    """Positive booster: is this competitor one of the real firms already
    pulled for the campaign? Case-insensitive substring either direction."""
    low = (name or "").strip().lower()
    if not low:
        return False
    for c in cohort_names:
        cl = (c or "").strip().lower()
        if cl and (cl in low or low in cl):
            return True
    return False


def _demo() -> None:
    # noun phrase: no "a accountant", one vocabulary
    assert noun_phrase("accountants southampton") == "an accountancy firm"
    assert noun_phrase("Accountant") == "an accountancy firm"
    assert noun_phrase("plumbers") == "a firm like yours"
    assert noun_phrase("family law") == "a law firm"
    assert noun_phrase("dentists") == "a dental practice"
    assert noun_phrase("") == DEFAULT_NOUN_PHRASE

    # real firms from the Southampton DB must survive
    keep = ["James Cowper Kreston", "HWB Accountants", "BDO LLP", "Baker Tilly",
            "Smith & Williamson", "Basra & Basra", "MHA Carpenter Box",
            "Pearl Chartered Accountants", "Cone Accounting",
            "Poolemead Accountants Ltd", "Hendy & Co Chartered Accountants",
            "Prentice & Co", "James & Uzzell", "PKF Francis Clark",
            "Rothmans Accountants", "Lubbock Fine", "HJS Accountants"]
    for n in keep:
        assert is_valid_competitor(n), f"should keep real firm: {n}"

    # junk actually stored in the DB as "competitors" must be rejected
    junk = ["Google Maps Search", "Get Quotes", "AccountantsUp",
            "General tips for finding good accountants", "Some Highly",
            "How to Find Accountants in SO19", "How to Find Accountants in SO40",
            "How to Find Accountants Near SO40", "Local Facebook Groups",
            "Hourly Rates", "Regulatory Compliance", "Accounting Firms",
            "Technology Use", "Personal Rapport", "Client Base",
            "Why Recommended", "Comparison Sites", "Proactive Advice",
            "Bookkeeping", "Citizens Advice",
            "Social Media and Community Groups", "Trustpilot", "Services Offered",
            "Client Reviews"]
    for n in junk:
        assert not is_valid_competitor(n), f"should reject junk: {n}"

    # the three regression targets pick a real firm or nothing (never junk)
    assert first_valid_competitor(
        ["Google Maps Search", "Get Quotes", "AccountantsUp",
         "Poolemead Accountants Ltd", "General tips for finding good accountants"]
    ) == "Poolemead Accountants Ltd"  # The Accounting Studio
    assert first_valid_competitor(
        ["James Cowper Kreston", "HWB Accountants"]) == "James Cowper Kreston"  # Troy/Switch
    assert first_valid_competitor(
        ["Hourly Rates", "Regulatory Compliance", "Accounting Firms",
         "How to Find Accountants in SO40"]) is None  # Diamond -> truthful fallback

    assert is_in_universe("HWB Accountants", ["HWB Accountants Ltd", "Troy"])
    assert not is_in_universe("BDO LLP", ["Troy", "Switch"])
    print("prospect_config self-check passed")


if __name__ == "__main__":
    _demo()
