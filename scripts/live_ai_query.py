#!/usr/bin/env python3
"""
Live AI Brand Visibility Querying Module

Queries AI providers (OpenAI, Anthropic, Google Gemini, Perplexity) with
contextual prompts to measure how visible a brand is in AI-generated responses.
Uses regex-based brand detection (no second AI call) and discovers competitors
from response content.

Usage as CLI:
    python live_ai_query.py --company-name "Brand" --url "https://..." --industry "tech"
    python live_ai_query.py --company-name "Brand" --url "https://..." --industry "legal" --location "Hampshire, UK"

Usage as library:
    from live_ai_query import run_brand_visibility_audit
    results = run_brand_visibility_audit("Brand", "https://example.com", industry="tech")

Environment variables (set whichever providers you want to query):
    OPENAI_API_KEY          — For ChatGPT queries
    ANTHROPIC_API_KEY       — For Claude queries
    GOOGLE_GENERATIVE_AI_API_KEY — For Gemini queries
    PERPLEXITY_API_KEY      — For Perplexity queries
"""

import os
import re
import sys
import json
import time
import argparse
from datetime import datetime
import concurrent.futures
from typing import Optional
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ── Brand Detection ──────────────────────────────────────────────────────────

def normalize_brand_name(name: str) -> str:
    """Normalize a brand name for comparison."""
    return re.sub(r'[^a-z0-9]', '', name.lower().strip())


def detect_brand_mention(text: str, brand_name: str, url: str = "") -> dict:
    """
    Check if a brand is mentioned in text using regex.
    Returns dict with 'mentioned' (bool), 'count' (int), 'positions' (list),
    and 'sentiment' (str).
    """
    if not text or not brand_name:
        return {"mentioned": False, "count": 0, "positions": [], "sentiment": "neutral"}

    # Build patterns for the brand name
    brand_lower = brand_name.lower()
    brand_normalized = normalize_brand_name(brand_name)

    # Also check for domain mention
    domain = ""
    if url:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")

    patterns = [
        re.compile(r'\b' + re.escape(brand_name) + r'\b', re.IGNORECASE),
    ]

    # Add domain pattern if available
    if domain:
        patterns.append(re.compile(re.escape(domain), re.IGNORECASE))

    # Add normalized version if different
    if len(brand_name.split()) > 1:
        # Multi-word brand: also check without spaces
        patterns.append(re.compile(r'\b' + re.escape(brand_normalized) + r'\b', re.IGNORECASE))

    count = 0
    positions = []
    text_lower = text.lower()

    for pattern in patterns:
        for match in pattern.finditer(text):
            count += 1
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            positions.append(text[start:end].strip())

    # Simple sentiment analysis based on surrounding context
    sentiment = "neutral"
    if count > 0:
        positive_words = ["recommend", "best", "great", "excellent", "top", "leading",
                          "trusted", "reliable", "popular", "preferred", "outstanding"]
        negative_words = ["avoid", "poor", "worst", "bad", "terrible", "unreliable",
                          "scam", "complaint", "issue", "problem"]

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        if pos_count > neg_count:
            sentiment = "positive"
        elif neg_count > pos_count:
            sentiment = "negative"

    return {
        "mentioned": count > 0,
        "count": count,
        "positions": positions[:5],  # Limit context snippets
        "sentiment": sentiment,
    }


def extract_competitors(text: str, brand_name: str) -> list:
    """
    Extract potential competitor names from AI response text.
    Looks for company-like patterns: capitalized multi-word names, names with
    common suffixes (Inc, Ltd, LLC), and items in numbered/bulleted lists.
    """
    competitors = set()
    brand_norm = normalize_brand_name(brand_name)

    # Pattern 1: Numbered list items (common in AI responses)
    # Matches "1. Company Name" or "- Company Name" patterns
    list_pattern = re.compile(
        r'(?:^|\n)\s*(?:\d+[\.\)]\s*\**|[-*]\s*\**)'
        r'([A-Z][A-Za-z0-9\s&\'-]{2,40}?)(?:\**\s*[-–—:]|\**\s*\n|\**$)',
        re.MULTILINE
    )
    for match in list_pattern.finditer(text):
        name = match.group(1).strip().rstrip('*').strip()
        if normalize_brand_name(name) != brand_norm and len(name) > 2:
            competitors.add(name)

    # Pattern 2: Bold names (common in AI formatting)
    bold_pattern = re.compile(r'\*\*([A-Z][A-Za-z0-9\s&\'-]{2,40}?)\*\*')
    for match in bold_pattern.finditer(text):
        name = match.group(1).strip()
        if normalize_brand_name(name) != brand_norm and len(name) > 2:
            competitors.add(name)

    # Filter out common non-company phrases
    noise_words = {
        "the best", "the top", "the most", "in conclusion", "for example",
        "in summary", "key features", "main benefits", "important factors",
        "here are", "some options", "final thoughts", "pros and cons",
    }

    filtered = []
    for comp in competitors:
        comp_lower = comp.lower().strip()
        if comp_lower not in noise_words and len(comp_lower) > 3:
            filtered.append(comp)

    return sorted(filtered)


# ── Provider Queries ─────────────────────────────────────────────────────────

def build_prompts(company_name: str, industry: str, location: str = "",
                  keywords: list = None, products: list = None) -> list:
    """Build contextual prompts for AI providers."""
    prompts = []
    loc_str = f" in {location}" if location else ""
    kw_str = ", ".join(keywords[:3]) if keywords else industry

    # Discovery prompts (unbranded — most important for real visibility)
    prompts.extend([
        f"What are the best {industry} companies{loc_str}?",
        f"Can you recommend a good {industry} provider{loc_str}?",
        f"Who are the top {industry} companies I should consider{loc_str}?",
        f"What {industry} services would you recommend for a business{loc_str}?",
        f"I'm looking for {kw_str} services. What companies should I look at?",
        f"Compare the leading {industry} companies{loc_str}. Which is best?",
        f"What are the most trusted {industry} brands{loc_str}?",
    ])

    # Product/service specific prompts
    if products:
        for product in products[:3]:
            prompts.append(f"What is the best {product} available{loc_str}?")
            prompts.append(f"Can you recommend a {product} provider?")

    # Brand-specific prompts (these test entity recognition, not discovery)
    prompts.extend([
        f"What is {company_name}?",
        f"Tell me about {company_name} and what they do.",
        f"Is {company_name} a good choice for {industry} services?",
        f"What do people say about {company_name}?",
    ])

    return prompts


def query_openai(prompt: str, api_key: str) -> Optional[str]:
    """Query OpenAI ChatGPT."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[OpenAI] Error: {e}", file=sys.stderr)
        return None


def query_anthropic(prompt: str, api_key: str) -> Optional[str]:
    """Query Anthropic Claude."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        print(f"[Anthropic] Error: {e}", file=sys.stderr)
        return None


def query_gemini(prompt: str, api_key: str) -> Optional[str]:
    """Query Google Gemini."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"[Gemini] Error: {e}", file=sys.stderr)
        return None


def query_perplexity(prompt: str, api_key: str) -> Optional[str]:
    """Query Perplexity AI."""
    try:
        import requests
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Perplexity] Error: {e}", file=sys.stderr)
        return None


def query_openrouter(prompt: str, api_key: str, model: str = "openai/gpt-4o-mini") -> Optional[str]:
    """Query any model via OpenRouter (OpenAI-compatible API)."""
    try:
        import requests
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://antekautomation.com",
                "X-Title": "GEO SLAB",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[OpenRouter/{model}] Error: {e}", file=sys.stderr)
        return None


def query_openrouter_chatgpt(prompt: str, api_key: str) -> Optional[str]:
    """Query ChatGPT via OpenRouter."""
    return query_openrouter(prompt, api_key, model="openai/gpt-4o-mini")


def query_openrouter_gemini(prompt: str, api_key: str) -> Optional[str]:
    """Query Gemini via OpenRouter."""
    return query_openrouter(prompt, api_key, model="google/gemini-2.0-flash-001")


def query_openrouter_grok(prompt: str, api_key: str) -> Optional[str]:
    """Query Grok via OpenRouter."""
    return query_openrouter(prompt, api_key, model="x-ai/grok-3-mini-beta")


def query_openrouter_deepseek(prompt: str, api_key: str) -> Optional[str]:
    """Query DeepSeek via OpenRouter."""
    return query_openrouter(prompt, api_key, model="deepseek/deepseek-chat-v3-0324")


def query_openrouter_meta(prompt: str, api_key: str) -> Optional[str]:
    """Query Meta Llama via OpenRouter."""
    return query_openrouter(prompt, api_key, model="meta-llama/llama-4-maverick")


def query_openrouter_mistral(prompt: str, api_key: str) -> Optional[str]:
    """Query Mistral via OpenRouter."""
    return query_openrouter(prompt, api_key, model="mistralai/mistral-small-3.1-24b-instruct")


def query_openrouter_claude(prompt: str, api_key: str) -> Optional[str]:
    """Query Claude via OpenRouter."""
    return query_openrouter(prompt, api_key, model="anthropic/claude-haiku-4-5-20251001")


# ── Provider Resolution ──────────────────────────────────────────────────────
# Priority: native API keys first, then OpenRouter as fallback for missing ones

def _build_providers() -> dict:
    """
    Build the active provider map. Uses native API keys when available,
    falls back to OpenRouter for ChatGPT and Gemini if OPENROUTER_API_KEY is set.
    """
    providers = {}
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")

    # ChatGPT: native OpenAI key > OpenRouter
    if os.environ.get("OPENAI_API_KEY"):
        providers["openai"] = {
            "name": "ChatGPT (OpenAI)",
            "env_key": "OPENAI_API_KEY",
            "query_fn": query_openai,
        }
    elif openrouter_key:
        providers["openai_or"] = {
            "name": "ChatGPT (via OpenRouter)",
            "env_key": "OPENROUTER_API_KEY",
            "query_fn": query_openrouter_chatgpt,
        }

    # Claude: native Anthropic key > OpenRouter
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers["anthropic"] = {
            "name": "Claude (Anthropic)",
            "env_key": "ANTHROPIC_API_KEY",
            "query_fn": query_anthropic,
        }
    elif openrouter_key:
        providers["anthropic_or"] = {
            "name": "Claude (via OpenRouter)",
            "env_key": "OPENROUTER_API_KEY",
            "query_fn": query_openrouter_claude,
        }

    # Gemini: native Google key > OpenRouter
    if os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY"):
        providers["gemini"] = {
            "name": "Gemini (Google)",
            "env_key": "GOOGLE_GENERATIVE_AI_API_KEY",
            "query_fn": query_gemini,
        }
    elif openrouter_key:
        providers["gemini_or"] = {
            "name": "Gemini (via OpenRouter)",
            "env_key": "OPENROUTER_API_KEY",
            "query_fn": query_openrouter_gemini,
        }

    # Perplexity: native key only (not on OpenRouter)
    if os.environ.get("PERPLEXITY_API_KEY"):
        providers["perplexity"] = {
            "name": "Perplexity AI",
            "env_key": "PERPLEXITY_API_KEY",
            "query_fn": query_perplexity,
        }

    # Grok, DeepSeek, Meta AI, Mistral: OpenRouter only
    if openrouter_key:
        providers["grok"] = {
            "name": "Grok (xAI)",
            "env_key": "OPENROUTER_API_KEY",
            "query_fn": query_openrouter_grok,
        }
        providers["deepseek"] = {
            "name": "DeepSeek",
            "env_key": "OPENROUTER_API_KEY",
            "query_fn": query_openrouter_deepseek,
        }
        providers["meta"] = {
            "name": "Meta AI (Llama)",
            "env_key": "OPENROUTER_API_KEY",
            "query_fn": query_openrouter_meta,
        }
        providers["mistral"] = {
            "name": "Mistral (Le Chat)",
            "env_key": "OPENROUTER_API_KEY",
            "query_fn": query_openrouter_mistral,
        }

    return providers


PROVIDERS = _build_providers()


# ── Main Audit Logic ─────────────────────────────────────────────────────────

def run_brand_visibility_audit(
    company_name: str,
    url: str,
    industry: str = "",
    location: str = "",
    keywords: list = None,
    products: list = None,
) -> dict:
    """
    Run a complete brand visibility audit across available AI providers.

    Returns a dict with:
    - providers_queried: list of provider names
    - providers_skipped: list of providers without API keys
    - total_prompts: total prompts sent
    - total_responses: total successful responses
    - visibility_score: 0-100 composite score
    - brand_mentioned_pct: % of responses mentioning the brand
    - sentiment: overall sentiment
    - competitor_rankings: list of competitors found
    - provider_results: per-provider breakdown
    - raw_responses: all prompt/response pairs (for debugging)
    """
    # Determine available providers
    available = {}
    skipped = []
    for key, config in PROVIDERS.items():
        api_key = os.environ.get(config["env_key"])
        if api_key:
            available[key] = {**config, "api_key": api_key}
        else:
            skipped.append(config["name"])

    if not available:
        return {
            "error": "No AI provider API keys found. Set at least one of: "
                     "OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_GENERATIVE_AI_API_KEY, PERPLEXITY_API_KEY",
            "providers_queried": [],
            "providers_skipped": [c["name"] for c in PROVIDERS.values()],
            "visibility_score": 0,
        }

    prompts = build_prompts(company_name, industry, location, keywords, products)

    # Separate branded vs unbranded prompts
    brand_lower = company_name.lower()
    unbranded_prompts = [p for p in prompts if brand_lower not in p.lower()]
    branded_prompts = [p for p in prompts if brand_lower in p.lower()]

    all_responses = []
    provider_results = {}

    # Query each provider with all prompts (using thread pool for parallelism)
    for provider_key, config in available.items():
        provider_name = config["name"]
        query_fn = config["query_fn"]
        api_key = config["api_key"]

        print(f"[live_ai_query] Querying {provider_name}...", file=sys.stderr)
        provider_responses = []

        def query_single(prompt):
            time.sleep(0.5)  # Rate limiting
            response = query_fn(prompt, api_key)
            return prompt, response

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(query_single, p) for p in prompts]
            for future in concurrent.futures.as_completed(futures):
                prompt, response = future.result()
                if response:
                    detection = detect_brand_mention(response, company_name, url)
                    competitors = extract_competitors(response, company_name)
                    is_branded = brand_lower in prompt.lower()

                    entry = {
                        "provider": provider_name,
                        "prompt": prompt,
                        "response_length": len(response),
                        "brand_mentioned": detection["mentioned"],
                        "mention_count": detection["count"],
                        "sentiment": detection["sentiment"],
                        "competitors_found": competitors,
                        "is_branded_prompt": is_branded,
                    }
                    provider_responses.append(entry)
                    all_responses.append(entry)

        # Calculate provider-level stats
        total = len(provider_responses)
        mentioned = sum(1 for r in provider_responses if r["brand_mentioned"])
        unbranded_responses = [r for r in provider_responses if not r["is_branded_prompt"]]
        unbranded_mentioned = sum(1 for r in unbranded_responses if r["brand_mentioned"])

        provider_results[provider_name] = {
            "total_queries": total,
            "brand_mentioned": mentioned,
            "mention_rate": round(mentioned / total * 100, 1) if total > 0 else 0,
            "unbranded_mention_rate": round(
                unbranded_mentioned / len(unbranded_responses) * 100, 1
            ) if unbranded_responses else 0,
            "sentiment": _aggregate_sentiment(provider_responses),
        }

        print(f"[live_ai_query] {provider_name}: {mentioned}/{total} mentions "
              f"({provider_results[provider_name]['mention_rate']}%)", file=sys.stderr)

    # Aggregate competitor rankings
    competitor_counts = {}
    for resp in all_responses:
        for comp in resp.get("competitors_found", []):
            norm = normalize_brand_name(comp)
            if norm not in competitor_counts:
                competitor_counts[norm] = {"name": comp, "mentions": 0, "providers": set()}
            competitor_counts[norm]["mentions"] += 1
            competitor_counts[norm]["providers"].add(resp["provider"])

    # Filter: keep competitors mentioned 2+ times
    competitor_rankings = sorted(
        [
            {
                "name": v["name"],
                "mentions": v["mentions"],
                "providers": len(v["providers"]),
            }
            for v in competitor_counts.values()
            if v["mentions"] >= 2
        ],
        key=lambda x: x["mentions"],
        reverse=True,
    )[:15]  # Top 15

    # Calculate composite visibility score
    # Only use unbranded prompts for the visibility score (branded prompts inflate it)
    unbranded_all = [r for r in all_responses if not r["is_branded_prompt"]]
    unbranded_mentioned_count = sum(1 for r in unbranded_all if r["brand_mentioned"])
    unbranded_total = len(unbranded_all)

    visibility_pct = (unbranded_mentioned_count / unbranded_total * 100) if unbranded_total > 0 else 0

    # Sentiment score: positive=100, neutral=50, negative=0
    overall_sentiment = _aggregate_sentiment(all_responses)
    sentiment_score = {"positive": 100, "neutral": 50, "negative": 0, "mixed": 50}.get(overall_sentiment, 50)

    # Share of voice: brand mentions vs total competitor mentions
    total_competitor_mentions = sum(c["mentions"] for c in competitor_rankings)
    brand_total_mentions = sum(r["mention_count"] for r in all_responses if r["brand_mentioned"])
    sov = (brand_total_mentions / (brand_total_mentions + total_competitor_mentions) * 100) \
        if (brand_total_mentions + total_competitor_mentions) > 0 else 0

    # Composite score: weighted average
    visibility_score = round(
        (visibility_pct * 0.40) +     # 40% — organic discovery rate
        (sentiment_score * 0.20) +     # 20% — sentiment quality
        (min(sov, 100) * 0.25) +       # 25% — share of voice
        (min(len(available) / 8 * 100, 100) * 0.15)  # 15% — provider coverage (up to 8 providers)
    )
    visibility_score = max(0, min(100, visibility_score))

    return {
        "company_name": company_name,
        "url": url,
        "industry": industry,
        "timestamp": datetime.now().isoformat(),
        "providers_queried": [c["name"] for c in available.values()],
        "providers_skipped": skipped,
        "total_prompts": len(prompts) * len(available),
        "total_responses": len(all_responses),
        "visibility_score": visibility_score,
        "brand_mentioned_pct": round(visibility_pct, 1),
        "sentiment": overall_sentiment,
        "share_of_voice": round(sov, 1),
        "competitor_rankings": competitor_rankings,
        "provider_results": provider_results,
    }


def _aggregate_sentiment(responses: list) -> str:
    """Aggregate sentiment across responses."""
    sentiments = [r["sentiment"] for r in responses if r.get("brand_mentioned")]
    if not sentiments:
        return "neutral"
    pos = sentiments.count("positive")
    neg = sentiments.count("negative")
    if pos > neg and pos > len(sentiments) * 0.3:
        return "positive"
    elif neg > pos and neg > len(sentiments) * 0.3:
        return "negative"
    elif pos > 0 and neg > 0:
        return "mixed"
    return "neutral"


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Live AI Brand Visibility Querying — "
                    "Measures brand visibility across AI search providers"
    )
    parser.add_argument("--company-name", required=True, help="Brand/company name to check")
    parser.add_argument("--url", required=True, help="Company website URL")
    parser.add_argument("--industry", default="", help="Industry/sector (e.g., 'legal', 'SaaS', 'e-commerce')")
    parser.add_argument("--location", default="", help="Location for local queries (e.g., 'Hampshire, UK')")
    parser.add_argument("--keywords", default="", help="Comma-separated keywords")
    parser.add_argument("--products", default="", help="Comma-separated product/service names")
    parser.add_argument("--output", default=None, help="Output JSON file path")

    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else None
    products = [p.strip() for p in args.products.split(",") if p.strip()] if args.products else None

    results = run_brand_visibility_audit(
        company_name=args.company_name,
        url=args.url,
        industry=args.industry,
        location=args.location,
        keywords=keywords,
        products=products,
    )

    output = json.dumps(results, indent=2, default=str)

    if args.output:
        from pathlib import Path
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Results written to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
