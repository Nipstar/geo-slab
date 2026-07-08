#!/usr/bin/env python3
"""
GEO SLAB — shared AI-query core.

Single source of truth for the provider-call + brand-detection logic used by
both live_ai_query.py (full audit) and visibility_check.py (free lead-magnet
check). Refactored out so the two do not diverge (spec §7).

Pure stdlib + `requests`. No Claude/LLM orchestration — safe to run headless
from cron / n8n / a Flask endpoint.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


# ── Env ──────────────────────────────────────────────────────────────────

def load_env() -> None:
    """Load .env.local (repo root / cwd / home) into os.environ if present.
    Prefers python-dotenv when installed, else a minimal parser."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    for p in (
        Path(__file__).resolve().parent.parent.parent / ".env.local",
        Path.cwd() / ".env.local",
        Path.home() / ".env.local",
    ):
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):]
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'").strip('"'))
        break


# ── OpenRouter model IDs for the free check (cheap tier) ───────────────────

# Model IDs verified live against GET /api/v1/models (2026-07-03). OpenRouter
# slugs drift — re-check here if a platform starts returning 404.
# Consumer-facing flagships — what a real person actually gets on chatgpt.com /
# claude.ai, so the check reflects the answers a prospect's customers see (not a
# cheaper mini/haiku tier). Verify slugs against the OpenRouter models list
# before changing.
CHECK_MODELS = {
    "ChatGPT":    "openai/gpt-5.2-chat",
    "Claude":     "anthropic/claude-sonnet-5",
    "Gemini":     "google/gemini-2.5-flash",
    "Perplexity": "perplexity/sonar",
}


# ── Brand detection (identical logic shared with live_ai_query) ────────────

def normalize_brand_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower().strip())


def detect_brand_mention(text: str, brand_name: str, url: str = "") -> dict:
    """Regex brand detection. Returns mentioned/count/positions/sentiment."""
    if not text or not brand_name:
        return {"mentioned": False, "count": 0, "positions": [], "sentiment": "neutral"}

    brand_normalized = normalize_brand_name(brand_name)
    domain = ""
    if url:
        domain = urlparse(url if "//" in url else f"//{url}").netloc.replace("www.", "")

    patterns = [re.compile(r"\b" + re.escape(brand_name) + r"\b", re.IGNORECASE)]
    if domain:
        patterns.append(re.compile(re.escape(domain), re.IGNORECASE))
    if len(brand_name.split()) > 1:
        patterns.append(re.compile(r"\b" + re.escape(brand_normalized) + r"\b", re.IGNORECASE))

    count = 0
    positions = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            count += 1
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            positions.append(text[start:end].strip())

    sentiment = "neutral"
    if count > 0:
        text_lower = text.lower()
        positive = ["recommend", "best", "great", "excellent", "top", "leading",
                    "trusted", "reliable", "popular", "preferred", "outstanding"]
        negative = ["avoid", "poor", "worst", "bad", "terrible", "unreliable",
                    "scam", "complaint", "issue", "problem"]
        pos = sum(1 for w in positive if w in text_lower)
        neg = sum(1 for w in negative if w in text_lower)
        if pos > neg:
            sentiment = "positive"
        elif neg > pos:
            sentiment = "negative"

    return {"mentioned": count > 0, "count": count, "positions": positions[:5], "sentiment": sentiment}


def extract_competitors(text: str, brand_name: str) -> list:
    """Pull competitor-like names from list items and bold text."""
    competitors = set()
    brand_norm = normalize_brand_name(brand_name)

    list_pattern = re.compile(
        r"(?:^|\n)\s*(?:\d+[\.\)]\s*\**|[-*]\s*\**)"
        r"([A-Z][A-Za-z0-9\s&'-]{2,40}?)(?:\**\s*[-–—:]|\**\s*\n|\**$)",
        re.MULTILINE,
    )
    bold_pattern = re.compile(r"\*\*([A-Z][A-Za-z0-9\s&'-]{2,40}?)\*\*")

    for pat in (list_pattern, bold_pattern):
        for match in pat.finditer(text):
            name = match.group(1).strip().rstrip("*").strip()
            if normalize_brand_name(name) != brand_norm and len(name) > 2:
                competitors.add(name)

    noise = {
        "the best", "the top", "the most", "in conclusion", "for example",
        "in summary", "key features", "main benefits", "important factors",
        "here are", "some options", "final thoughts", "pros and cons",
        # Generic discovery-advice phrases AI lists that are NOT businesses —
        # keep the competitor list to real named firms + directories.
        "word of mouth", "online search", "local directories", "local directory",
        "online reviews", "google reviews", "google search", "google maps",
        "social media", "personal recommendations", "recommendations",
        "check reviews", "ask friends", "search online", "review sites",
        "review platforms", "local search", "trade associations", "gas safe register",
        # Selection-CRITERIA the AI lists when it can't name a real firm — these
        # are how-to-choose advice, not rival businesses. Without these the
        # "a competitor was recommended instead" hook fires on junk like
        # "Location" / "Fees" / "Professional Associations".
        "location", "fees", "pricing", "cost", "costs", "experience",
        "qualifications", "professional qualifications", "credentials",
        "accreditation", "accreditations", "services offered", "services",
        "professional associations", "professional bodies", "professional body",
        "value for money", "specialization", "specialisation", "reputation",
        "availability", "communication", "references", "reviews and ratings",
        "local business directories", "local recommendations", "recommendations",
        "ask for recommendations", "range of services", "client reviews",
        "industry experience", "areas of expertise", "expertise", "self",
    }
    # Directories / review sites / the AI engines themselves are NOT competitor
    # firms — an AI listing "Trustpilot" as where to look is not a rival business.
    directories = {
        "trustpilot", "yell", "yelp", "checkatrade", "bark", "bark.com",
        "google", "google business", "google my business", "bing", "facebook",
        "linkedin", "thomson local", "yellow pages", "yellowpages", "192.com",
        "freeindex", "cylex", "scoot", "houzz", "which", "which?", "tripadvisor",
        "chatgpt", "openai", "perplexity", "gemini", "claude", "reddit", "quora",
    }
    # Bare postcode / outcode fragments ("SO16", "RG21 7QW") aren't firms.
    postcode_frag = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?(\s*\d[A-Z]{2})?$", re.I)
    # Company signals — if present, it's a firm regardless of shape.
    signals = ("ltd", "llp", "& co", "accountant", "accountancy", "associates",
               "partners", "group", "chartered", "bookkeep", "advisor", "advisory",
               "solutions", "consultancy", "consulting", "financial", "plc", "limited")
    # Generic advice/criteria words. An LLM listing how to CHOOSE an accountant
    # emits Title-Case headings ("Online Directories", "Initial Consultation")
    # that pass a naive multi-word test — any of these words = not a firm.
    generic = {
        "experience", "qualifications", "qualification", "directories", "directory",
        "consultation", "consultations", "referrals", "referral", "reviews", "review",
        "testimonials", "testimonial", "fees", "fee", "pricing", "price", "cost", "costs",
        "networks", "network", "communication", "style", "expertise", "specialisation",
        "specialization", "availability", "reputation", "consideration", "considerations",
        "formation", "services", "service", "contact", "details", "recommendations",
        "recommendation", "referral", "friends", "family", "structure", "initial",
        "online", "local", "other", "businesses", "business", "clear", "consider",
        "what", "ask", "and", "for", "with", "your", "type", "value", "money",
    }

    def is_firm(name: str) -> bool:
        s = name.strip()
        low = s.lower()
        if low in noise or low in directories or len(s) <= 3 or postcode_frag.match(s):
            return False
        if any(sig in low for sig in signals):
            return True
        toks = [t for t in s.split() if t != "&"]
        if len(toks) < 2 or len(toks) > 4:
            return False  # firm names here are 2-4 proper-noun tokens
        # every token Title-Case AND none is a generic advice word → proper noun
        if any(t.lower() in generic for t in toks):
            return False
        return all(t[:1].isupper() for t in toks)

    return sorted(c for c in competitors if is_firm(c))


# ── OpenRouter ─────────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_HEADERS_EXTRA = {
    "HTTP-Referer": "https://antekautomation.com",
    "X-Title": "GEO SLAB",
}


def query_openrouter(prompt: str, api_key: str, model: str = "openai/gpt-4o-mini") -> Optional[str]:
    """Text-only call. Kept signature-compatible with live_ai_query wrappers."""
    result = query_openrouter_full(prompt, api_key, model)
    return result.get("text") if result else None


def query_openrouter_full(prompt: str, api_key: str, model: str) -> Optional[dict]:
    """Call OpenRouter and return {text, cost_usd, tokens}. Requests usage
    accounting so cost is logged per check (spec §7). Returns None on error."""
    import requests
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", **_HEADERS_EXTRA},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7,
                "usage": {"include": True},
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage") or {}
        return {
            "text": data["choices"][0]["message"]["content"],
            "cost_usd": float(usage.get("cost", 0.0) or 0.0),
            "tokens": usage.get("total_tokens", 0),
        }
    except Exception as e:
        import sys
        print(f"[OpenRouter/{model}] Error: {e}", file=sys.stderr)
        return None


# Per-platform wrappers (used by live_ai_query — re-exported there for compat).
def query_openrouter_chatgpt(prompt: str, api_key: str) -> Optional[str]:
    return query_openrouter(prompt, api_key, "openai/gpt-4o-mini")


def query_openrouter_gemini(prompt: str, api_key: str) -> Optional[str]:
    return query_openrouter(prompt, api_key, "google/gemini-2.5-flash")


def query_openrouter_claude(prompt: str, api_key: str) -> Optional[str]:
    return query_openrouter(prompt, api_key, "anthropic/claude-haiku-4.5")


def query_openrouter_grok(prompt: str, api_key: str) -> Optional[str]:
    return query_openrouter(prompt, api_key, "x-ai/grok-3-mini-beta")


def query_openrouter_deepseek(prompt: str, api_key: str) -> Optional[str]:
    return query_openrouter(prompt, api_key, "deepseek/deepseek-chat-v3-0324")


def query_openrouter_meta(prompt: str, api_key: str) -> Optional[str]:
    return query_openrouter(prompt, api_key, "meta-llama/llama-4-maverick")


def query_openrouter_mistral(prompt: str, api_key: str) -> Optional[str]:
    return query_openrouter(prompt, api_key, "mistralai/mistral-small-3.1-24b-instruct")


# ── Self-check (offline — no network) ──────────────────────────────────────

def _demo() -> None:
    assert normalize_brand_name("Acme Ltd!") == "acmeltd"
    d = detect_brand_mention("We recommend Acme Plumbing, the best in town.", "Acme Plumbing")
    assert d["mentioned"] and d["count"] == 1 and d["sentiment"] == "positive"
    assert not detect_brand_mention("nobody here", "Acme Plumbing")["mentioned"]
    # domain match
    assert detect_brand_mention("visit acme.com today", "Acme", "https://acme.com")["mentioned"]
    comps = extract_competitors("1. Beta Corp\n2. Gamma Ltd\n3. Acme", "Acme")
    assert "Beta Corp" in comps and "Gamma Ltd" in comps and "Acme" not in comps, comps
    print("ai_query_core self-check passed")


if __name__ == "__main__":
    _demo()
