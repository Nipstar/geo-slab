#!/usr/bin/env python3
"""
GEO SLAB — Brand Mention Scanner
Checks brand presence across AI-cited platforms.

Brand mentions correlate 3x more strongly with AI visibility than backlinks.
(Ahrefs December 2025 study of 75,000 brands)

Platform importance for AI citations:
1. YouTube mentions (~0.737 correlation - STRONGEST)
2. Reddit mentions (high)
3. Wikipedia presence (high)
4. LinkedIn presence (moderate)
5. Domain Rating/backlinks (~0.266 - weak)

When SERPAPI_API_KEY is set, performs live Google searches for each platform.
Without it, falls back to generating search URLs for manual checking.

When GOOGLE_PLACES_API_KEY is set, queries Google Places API for business
profile data (rating, reviews, categories, photos). Critical for local
business audits and Gemini optimisation.
"""

import sys
import os
import json
import re
from urllib.parse import quote_plus

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Required packages not installed. Run: pip install requests beautifulsoup4")
    sys.exit(1)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_BASE_URL = "https://serpapi.com/search"
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


# ── SerpAPI Helpers ──────────────────────────────────────────────────────────


def serpapi_search(query: str, num: int = 10, gl: str = "us") -> dict:
    """
    Perform a Google search via SerpAPI.

    Returns dict with:
        - "success": bool
        - "total_results": int or None
        - "organic_results": list of {position, title, link, snippet, displayed_link, date}
        - "knowledge_graph": dict or None (if KG panel present)
        - "error": str or None
    """
    result = {
        "success": False,
        "total_results": None,
        "organic_results": [],
        "knowledge_graph": None,
        "error": None,
    }

    if not SERPAPI_API_KEY:
        result["error"] = "No API key configured"
        return result

    try:
        params = {
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "engine": "google",
            "num": num,
            "gl": gl,
        }

        response = requests.get(SERPAPI_BASE_URL, params=params, timeout=20)

        if response.status_code == 401:
            result["error"] = "Invalid SerpAPI API key (401)"
            return result
        elif response.status_code == 429:
            result["error"] = "SerpAPI rate limit exceeded (429)"
            return result
        elif response.status_code != 200:
            result["error"] = f"SerpAPI returned status {response.status_code}"
            return result

        data = response.json()

        result["total_results"] = data.get("search_information", {}).get("total_results", None)

        for r in data.get("organic_results", []):
            result["organic_results"].append({
                "position": r.get("position"),
                "title": r.get("title", ""),
                "link": r.get("link", ""),
                "snippet": r.get("snippet", ""),
                "displayed_link": r.get("displayed_link", ""),
                "date": r.get("date"),
            })

        # Extract Knowledge Graph if present
        kg = data.get("knowledge_graph")
        if kg:
            result["knowledge_graph"] = {
                "title": kg.get("title"),
                "type": kg.get("type"),
                "description": kg.get("description"),
                "website": kg.get("website"),
                "source": kg.get("source", {}).get("name"),
                "rating": kg.get("rating"),
                "review_count": kg.get("review_count"),
                "profiles": kg.get("profiles", []),
                "people_also_search_for": [
                    p.get("name") for p in kg.get("people_also_search_for", [])
                ],
            }

        result["success"] = True

    except requests.exceptions.Timeout:
        result["error"] = "SerpAPI request timed out (20s)"
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"Connection error reaching SerpAPI: {str(e)}"
    except json.JSONDecodeError:
        result["error"] = "Failed to parse SerpAPI JSON response"
    except Exception as e:
        result["error"] = f"Unexpected SerpAPI error: {str(e)}"

    return result


def serpapi_platform_search(brand_name: str, site_domain: str, num: int = 10, gl: str = "us") -> dict:
    """
    Search for a brand on a specific platform using both exact and broad queries.

    Runs two searches:
        1. '"brand_name" site:domain' (exact match)
        2. 'brand_name site:domain' (broad match)

    Returns dict with:
        - "exact_results": list from exact search
        - "broad_results": list from broad search
        - "all_results": deduplicated union by URL
        - "total_exact": total result count from exact search
        - "total_broad": total result count from broad search
        - "errors": list of any error strings
    """
    output = {
        "exact_results": [],
        "broad_results": [],
        "all_results": [],
        "total_exact": None,
        "total_broad": None,
        "errors": [],
    }

    # Exact match search
    exact = serpapi_search(f'"{brand_name}" site:{site_domain}', num=num, gl=gl)
    if exact["success"]:
        output["exact_results"] = exact["organic_results"]
        output["total_exact"] = exact["total_results"]
    elif exact["error"]:
        output["errors"].append(f"Exact search: {exact['error']}")

    # Broad match search
    broad = serpapi_search(f'{brand_name} site:{site_domain}', num=num, gl=gl)
    if broad["success"]:
        output["broad_results"] = broad["organic_results"]
        output["total_broad"] = broad["total_results"]
    elif broad["error"]:
        output["errors"].append(f"Broad search: {broad['error']}")

    # Deduplicate by URL
    seen_urls = set()
    for r in output["exact_results"] + output["broad_results"]:
        url = r.get("link", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            output["all_results"].append(r)

    return output


# ── Google Places API ────────────────────────────────────────────────────────


def check_google_business_profile(brand_name: str, location: str = "") -> dict:
    """
    Check Google Business Profile via Google Places API (New).

    Returns GBP data: rating, review count, categories, photos, hours, place_id.
    Falls back gracefully when GOOGLE_PLACES_API_KEY is not set.
    """
    result = {
        "platform": "Google Business Profile",
        "has_gbp": False,
        "place_id": None,
        "rating": None,
        "review_count": None,
        "categories": [],
        "address": None,
        "phone": None,
        "website": None,
        "photos_count": None,
        "has_hours": False,
        "business_status": None,
        "search_url": f"https://www.google.com/maps/search/{quote_plus(brand_name)}",
        "recommendations": [],
    }

    if GOOGLE_PLACES_API_KEY:
        try:
            search_query = f"{brand_name} {location}".strip()
            response = requests.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
                    "X-Goog-FieldMask": (
                        "places.id,places.displayName,places.formattedAddress,"
                        "places.rating,places.userRatingCount,places.types,"
                        "places.nationalPhoneNumber,places.websiteUri,"
                        "places.photos,places.currentOpeningHours,"
                        "places.businessStatus,places.primaryType"
                    ),
                },
                json={"textQuery": search_query},
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()
                places = data.get("places", [])

                if places:
                    place = places[0]
                    result["has_gbp"] = True
                    result["place_id"] = place.get("id")
                    result["rating"] = place.get("rating")
                    result["review_count"] = place.get("userRatingCount")
                    result["address"] = place.get("formattedAddress")
                    result["phone"] = place.get("nationalPhoneNumber")
                    result["website"] = place.get("websiteUri")
                    result["business_status"] = place.get("businessStatus")

                    # Categories
                    primary_type = place.get("primaryType", "")
                    types = place.get("types", [])
                    result["categories"] = [primary_type] + [t for t in types if t != primary_type][:5]

                    # Photos
                    photos = place.get("photos", [])
                    result["photos_count"] = len(photos)

                    # Hours
                    hours = place.get("currentOpeningHours")
                    result["has_hours"] = hours is not None

            elif response.status_code == 400:
                result["error"] = "Google Places API: Bad request (check API key permissions)"
            elif response.status_code == 403:
                result["error"] = "Google Places API: Forbidden (enable Places API in Google Cloud Console)"
            else:
                result["error"] = f"Google Places API returned status {response.status_code}"

        except Exception as e:
            result["error"] = f"Google Places API error: {str(e)}"
    else:
        result["check_instructions"] = [
            f"Search Google Maps for '{brand_name}' and check:",
            "1. Does the business have a Google Business Profile?",
            "2. Is the profile complete (hours, photos, services, description)?",
            "3. What's the star rating and how many reviews?",
            "4. Are there recent reviews (within 3 months)?",
            "5. Is the business verified?",
        ]

    result["recommendations"] = [
        "Claim and verify Google Business Profile if not done",
        "Complete all GBP fields: hours, services, description, photos, Q&A",
        "Post regularly to GBP (Google Posts)",
        "Respond to all reviews (positive and negative)",
        "Add products/services with descriptions",
        "Upload 10+ high-quality photos",
        "GBP feeds directly into Google Gemini — this is critical for local AI visibility",
    ]

    return result


# ── Knowledge Graph Check ────────────────────────────────────────────────────


def check_knowledge_graph(brand_name: str) -> dict:
    """
    Check if the brand has a Google Knowledge Graph panel.
    Uses SerpAPI's knowledge_graph extraction from a direct brand search.
    """
    result = {
        "has_knowledge_panel": False,
        "kg_title": None,
        "kg_type": None,
        "kg_description": None,
        "kg_website": None,
        "kg_source": None,
        "kg_rating": None,
        "kg_review_count": None,
        "kg_profiles": [],
        "kg_related_entities": [],
    }

    if not SERPAPI_API_KEY:
        return result

    search = serpapi_search(brand_name, num=5)
    if search["success"] and search["knowledge_graph"]:
        kg = search["knowledge_graph"]
        result["has_knowledge_panel"] = True
        result["kg_title"] = kg.get("title")
        result["kg_type"] = kg.get("type")
        result["kg_description"] = kg.get("description")
        result["kg_website"] = kg.get("website")
        result["kg_source"] = kg.get("source")
        result["kg_rating"] = kg.get("rating")
        result["kg_review_count"] = kg.get("review_count")
        result["kg_profiles"] = kg.get("profiles", [])
        result["kg_related_entities"] = kg.get("people_also_search_for", [])

    return result


# ── Platform Check Functions ─────────────────────────────────────────────────


def check_youtube_presence(brand_name: str) -> dict:
    """Check brand presence on YouTube."""
    result = {
        "platform": "YouTube",
        "correlation": 0.737,
        "weight": "25%",
        "has_channel": False,
        "channel_url": None,
        "subscriber_count_approx": None,
        "video_count_approx": None,
        "mentioned_in_videos": False,
        "search_result_count": 0,
        "total_google_results_exact": None,
        "total_google_results_broad": None,
        "search_url": f"https://www.youtube.com/results?search_query={quote_plus(brand_name)}",
        "video_results": [],
        "recommendations": [],
    }

    if SERPAPI_API_KEY:
        search_data = serpapi_platform_search(brand_name, "youtube.com")
        result["search_result_count"] = len(search_data["all_results"])
        result["total_google_results_exact"] = search_data["total_exact"]
        result["total_google_results_broad"] = search_data["total_broad"]

        for r in search_data["all_results"]:
            link = r.get("link", "")
            snippet = r.get("snippet", "")
            title = r.get("title", "")

            # Detect channel pages
            if "/@" in link or "/c/" in link or "/channel/" in link:
                result["has_channel"] = True
                result["channel_url"] = link
                sub_match = re.search(r'([\d,.]+[KMB]?)\s*subscribers?', snippet, re.I)
                if sub_match:
                    result["subscriber_count_approx"] = sub_match.group(1)
                vid_match = re.search(r'([\d,.]+)\s*videos?', snippet, re.I)
                if vid_match:
                    result["video_count_approx"] = vid_match.group(1)

            # Detect video pages
            if "/watch?" in link or "/shorts/" in link:
                result["mentioned_in_videos"] = True
                result["video_results"].append({
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                })

        if search_data["errors"]:
            result["serpapi_errors"] = search_data["errors"]
    else:
        result["check_instructions"] = [
            f"Search YouTube for '{brand_name}' and check:",
            "1. Does the brand have an official YouTube channel?",
            "2. Are there videos FROM the brand (tutorials, demos, thought leadership)?",
            "3. Are there videos ABOUT the brand from other creators?",
            "4. What's the view count on brand-related videos?",
            "5. Are there positive reviews or demonstrations?",
        ]

    result["recommendations"] = [
        "Create a YouTube channel if none exists",
        "Publish educational/tutorial content related to your niche",
        "Encourage customers to create review/demo videos",
        "Optimise video titles and descriptions with brand name",
        "Add timestamps and chapters to improve AI parseability",
        "Include transcripts (YouTube auto-generates, but review for accuracy)",
    ]

    return result


def check_reddit_presence(brand_name: str) -> dict:
    """Check brand presence on Reddit."""
    result = {
        "platform": "Reddit",
        "correlation": "High",
        "weight": "25%",
        "has_subreddit": False,
        "mentioned_in_discussions": False,
        "search_result_count": 0,
        "total_google_results_exact": None,
        "total_google_results_broad": None,
        "subreddits_found": [],
        "discussion_results": [],
        "search_url": f"https://www.reddit.com/search/?q={quote_plus(brand_name)}",
        "recommendations": [],
    }

    if SERPAPI_API_KEY:
        search_data = serpapi_platform_search(brand_name, "reddit.com")
        result["search_result_count"] = len(search_data["all_results"])
        result["total_google_results_exact"] = search_data["total_exact"]
        result["total_google_results_broad"] = search_data["total_broad"]

        subreddits_found = set()
        brand_slug = re.sub(r'\s+', '', brand_name.lower())

        for r in search_data["all_results"]:
            link = r.get("link", "")
            snippet = r.get("snippet", "")
            title = r.get("title", "")

            # Extract subreddit names
            sub_match = re.search(r'reddit\.com/r/([A-Za-z0-9_]+)', link)
            if sub_match:
                subreddit = sub_match.group(1)
                subreddits_found.add(subreddit)
                if subreddit.lower() == brand_slug:
                    result["has_subreddit"] = True

            result["mentioned_in_discussions"] = True
            result["discussion_results"].append({
                "title": title,
                "url": link,
                "snippet": snippet,
                "subreddit": sub_match.group(1) if sub_match else None,
            })

        result["subreddits_found"] = list(subreddits_found)

        if search_data["errors"]:
            result["serpapi_errors"] = search_data["errors"]
    else:
        result["check_instructions"] = [
            f"Search Reddit for '{brand_name}' and check:",
            "1. Does the brand have its own subreddit (r/brandname)?",
            "2. Is the brand discussed in relevant industry subreddits?",
            "3. What's the sentiment (positive, negative, neutral)?",
            "4. Are there recommendation threads mentioning the brand?",
            "5. Does the brand have an official Reddit presence?",
            "6. Are mentions recent (within last 6 months)?",
        ]

    result["recommendations"] = [
        "Monitor relevant subreddits for brand mentions",
        "Participate authentically in industry discussions (no spam)",
        "Create an official Reddit account for customer support",
        "Share valuable content (not just self-promotion)",
        "Respond to questions about your product/service category",
        "Reddit authenticity matters — don't use marketing speak",
    ]

    return result


def check_wikipedia_presence(brand_name: str) -> dict:
    """Check brand/entity presence on Wikipedia and Wikidata."""
    result = {
        "platform": "Wikipedia",
        "correlation": "High",
        "weight": "20%",
        "has_wikipedia_page": False,
        "has_wikidata_entry": False,
        "cited_in_articles": False,
        "search_url": f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(brand_name)}",
        "wikidata_url": f"https://www.wikidata.org/w/index.php?search={quote_plus(brand_name)}",
        "recommendations": [],
    }

    # Check Wikipedia API
    try:
        api_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote_plus(brand_name)}&format=json"
        response = requests.get(api_url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            search_results = data.get("query", {}).get("search", [])
            if search_results:
                top_title = search_results[0].get("title", "").lower()
                if brand_name.lower() in top_title:
                    result["has_wikipedia_page"] = True
                result["wikipedia_search_results"] = len(search_results)
    except Exception:
        pass

    # Check Wikidata
    try:
        wikidata_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={quote_plus(brand_name)}&language=en&format=json"
        response = requests.get(wikidata_url, headers=DEFAULT_HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            entities = data.get("search", [])
            if entities:
                result["has_wikidata_entry"] = True
                result["wikidata_id"] = entities[0].get("id", "")
                result["wikidata_description"] = entities[0].get("description", "")
    except Exception:
        pass

    result["recommendations"] = [
        "If eligible, create a Wikipedia article (requires notability criteria)",
        "Ensure Wikidata entry exists with complete structured data",
        "Add sameAs links in schema markup pointing to Wikipedia/Wikidata",
        "Get cited in existing Wikipedia articles as a source",
        "Build notability through press coverage and independent reviews",
        "Note: Wikipedia has strict notability guidelines — PR coverage helps establish this",
    ]

    return result


def check_linkedin_presence(brand_name: str) -> dict:
    """Check brand presence on LinkedIn."""
    result = {
        "platform": "LinkedIn",
        "correlation": "Moderate",
        "weight": "15%",
        "has_company_page": False,
        "company_page_url": None,
        "follower_count_approx": None,
        "employee_count_approx": None,
        "employee_thought_leadership": False,
        "search_result_count": 0,
        "total_google_results_exact": None,
        "total_google_results_broad": None,
        "linkedin_results": [],
        "search_url": f"https://www.linkedin.com/search/results/companies/?keywords={quote_plus(brand_name)}",
        "recommendations": [],
    }

    if SERPAPI_API_KEY:
        search_data = serpapi_platform_search(brand_name, "linkedin.com")
        result["search_result_count"] = len(search_data["all_results"])
        result["total_google_results_exact"] = search_data["total_exact"]
        result["total_google_results_broad"] = search_data["total_broad"]

        for r in search_data["all_results"]:
            link = r.get("link", "")
            snippet = r.get("snippet", "")
            title = r.get("title", "")

            # Detect company page
            if "/company/" in link:
                result["has_company_page"] = True
                result["company_page_url"] = link
                follower_match = re.search(r'([\d,.]+[KMB]?)\s*followers?', snippet, re.I)
                if follower_match:
                    result["follower_count_approx"] = follower_match.group(1)
                employee_match = re.search(r'([\d,.]+[KMB]?)\s*employees?', snippet, re.I)
                if employee_match:
                    result["employee_count_approx"] = employee_match.group(1)

            # Detect thought leadership posts
            if "/pulse/" in link or "/posts/" in link:
                result["employee_thought_leadership"] = True

            result["linkedin_results"].append({
                "title": title,
                "url": link,
                "snippet": snippet,
            })

        if search_data["errors"]:
            result["serpapi_errors"] = search_data["errors"]
    else:
        result["check_instructions"] = [
            f"Search LinkedIn for '{brand_name}' and check:",
            "1. Does the company have a LinkedIn page?",
            "2. How many followers?",
            "3. Is the page active with recent posts?",
            "4. Do employees post thought leadership content?",
            "5. Are there LinkedIn articles about the brand?",
            "6. Is there engagement on posts (likes, comments, shares)?",
        ]

    result["recommendations"] = [
        "Create/optimise LinkedIn company page",
        "Post regular thought leadership content",
        "Encourage employees to share company content",
        "Publish long-form LinkedIn articles",
        "Engage with industry discussions and comments",
        "Add company LinkedIn URL to schema sameAs property",
    ]

    return result


def check_other_platforms(brand_name: str) -> dict:
    """Check brand presence on additional platforms."""
    result = {
        "platform": "Other Platforms",
        "weight": "15%",
        "platforms_checked": {},
        "recommendations": [],
    }

    platforms = {
        "Quora": {"search_url": f"https://www.quora.com/search?q={quote_plus(brand_name)}", "domain": "quora.com"},
        "Stack Overflow": {"search_url": f"https://stackoverflow.com/search?q={quote_plus(brand_name)}", "domain": "stackoverflow.com"},
        "GitHub": {"search_url": f"https://github.com/search?q={quote_plus(brand_name)}", "domain": "github.com"},
        "Crunchbase": {"search_url": f"https://www.crunchbase.com/textsearch?q={quote_plus(brand_name)}", "domain": "crunchbase.com"},
        "Product Hunt": {"search_url": f"https://www.producthunt.com/search?q={quote_plus(brand_name)}", "domain": "producthunt.com"},
        "G2": {"search_url": f"https://www.g2.com/search?utf8=&query={quote_plus(brand_name)}", "domain": "g2.com"},
        "Trustpilot": {"search_url": f"https://www.trustpilot.com/search?query={quote_plus(brand_name)}", "domain": "trustpilot.com"},
    }

    for name, info in platforms.items():
        platform_data = {
            "search_url": info["search_url"],
            "found": False,
            "result_count": 0,
            "results": [],
        }

        if SERPAPI_API_KEY:
            serp_result = serpapi_search(f'"{brand_name}" site:{info["domain"]}', num=5)
            if serp_result["success"]:
                platform_data["found"] = len(serp_result["organic_results"]) > 0
                platform_data["result_count"] = len(serp_result["organic_results"])
                platform_data["total_google_results"] = serp_result["total_results"]
                platform_data["results"] = [
                    {"title": r["title"], "url": r["link"], "snippet": r["snippet"]}
                    for r in serp_result["organic_results"]
                ]
            if serp_result["error"]:
                platform_data["serpapi_error"] = serp_result["error"]
        else:
            platform_data["check_instruction"] = f"Search for '{brand_name}' on {name}"

        result["platforms_checked"][name] = platform_data

    result["recommendations"] = [
        "Maintain profiles on industry-relevant platforms",
        "Respond to questions on Quora and Stack Overflow",
        "Encourage customer reviews on G2 and Trustpilot",
        "Keep Crunchbase profile updated (important for B2B)",
        "Open-source contributions on GitHub boost developer brand authority",
        "Product Hunt launch can generate significant initial buzz",
    ]

    return result


# ── Main Report ──────────────────────────────────────────────────────────────


def generate_brand_report(brand_name: str, domain: str = None, location: str = "") -> dict:
    """Generate a comprehensive brand mention report."""
    apis_enabled = []
    if SERPAPI_API_KEY:
        apis_enabled.append("SerpAPI")
    if GOOGLE_PLACES_API_KEY:
        apis_enabled.append("Google Places API")

    report = {
        "brand_name": brand_name,
        "domain": domain,
        "analysis_date": "Generated by GEO SLAB — antekautomation.com",
        "serpapi_enabled": bool(SERPAPI_API_KEY),
        "google_places_enabled": bool(GOOGLE_PLACES_API_KEY),
        "apis_active": apis_enabled if apis_enabled else ["None — manual check mode"],
        "data_source": (
            f"Live data via {', '.join(apis_enabled)} + direct platform APIs"
            if apis_enabled
            else "URL generation only (set SERPAPI_API_KEY and/or GOOGLE_PLACES_API_KEY for live data)"
        ),
        "key_insight": "Brand mentions correlate 3x more strongly with AI visibility than backlinks (Ahrefs Dec 2025, 75K brands)",
        "platforms": {},
        "knowledge_graph": {},
        "overall_recommendations": [],
    }

    # Check all platforms
    report["platforms"]["youtube"] = check_youtube_presence(brand_name)
    report["platforms"]["reddit"] = check_reddit_presence(brand_name)
    report["platforms"]["wikipedia"] = check_wikipedia_presence(brand_name)
    report["platforms"]["linkedin"] = check_linkedin_presence(brand_name)
    report["platforms"]["google_business_profile"] = check_google_business_profile(brand_name, location)
    report["platforms"]["other"] = check_other_platforms(brand_name)

    # Knowledge Graph check
    report["knowledge_graph"] = check_knowledge_graph(brand_name)

    # Overall recommendations
    report["overall_recommendations"] = [
        "Priority 1: YouTube — highest correlation (0.737) with AI citations. Create educational content.",
        "Priority 2: Reddit — build authentic presence in industry subreddits. No marketing speak.",
        "Priority 3: Wikipedia — establish notability through press coverage, then create/improve entry.",
        "Priority 4: Google Business Profile — complete all fields, respond to reviews. Feeds directly into Gemini.",
        "Priority 5: LinkedIn — thought leadership content from founders and employees.",
        "Priority 6: Review platforms — G2, Trustpilot, Capterra for social proof signals.",
        "Cross-platform: Ensure consistent NAP (Name, Address, Phone) across all platforms.",
        "Schema markup: Add sameAs property linking to ALL platform profiles.",
        "Monitor: Set up brand mention alerts across all platforms.",
    ]

    return report


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python brand_scanner.py <brand_name> [domain] [--location 'City, Country']")
        print("Example: python brand_scanner.py 'Acme Corp' acmecorp.com --location 'Hampshire, UK'")
        print("\nOptional API keys for live data:")
        print("  SERPAPI_API_KEY          — Google search results for all platforms")
        print("  GOOGLE_PLACES_API_KEY    — Google Business Profile data")
        sys.exit(1)

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    args = [a for a in sys.argv[1:] if a not in ("--verbose", "-v") and not a.startswith("--location")]

    # Extract location flag
    location = ""
    for i, a in enumerate(sys.argv):
        if a == "--location" and i + 1 < len(sys.argv):
            location = sys.argv[i + 1]
            break

    brand = args[0]
    domain = args[1] if len(args) > 1 else None

    if verbose:
        if SERPAPI_API_KEY:
            print(f"SerpAPI: Enabled (key: ...{SERPAPI_API_KEY[-4:]})", file=sys.stderr)
        else:
            print("SerpAPI: Disabled (no SERPAPI_API_KEY found)", file=sys.stderr)
        if GOOGLE_PLACES_API_KEY:
            print(f"Google Places: Enabled (key: ...{GOOGLE_PLACES_API_KEY[-4:]})", file=sys.stderr)
        else:
            print("Google Places: Disabled (no GOOGLE_PLACES_API_KEY found)", file=sys.stderr)
        print(f"Scanning brand: {brand}", file=sys.stderr)
        if domain:
            print(f"Domain: {domain}", file=sys.stderr)
        if location:
            print(f"Location: {location}", file=sys.stderr)

    result = generate_brand_report(brand, domain, location)
    print(json.dumps(result, indent=2, default=str))
