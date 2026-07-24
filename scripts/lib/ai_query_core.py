#!/usr/bin/env python3
"""
GEO SLAB — shared AI-query core, now an adapter over antek-geo-core.

Brand detection, competitor extraction, models and the OpenRouter call live in
the shared Geo-core library (github.com/Nipstar/Geo-core) so GEO SLAB (paid
audit) and geo-prospecting (free tease) can never drift on how they score
visibility. This module preserves SLAB's existing public surface exactly —
including the historic (prompt, api_key, model) arg order and the extra provider
wrappers — so live_ai_query.py and visibility_check.py need no changes.

Pure stdlib + `requests`. Safe to run headless.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from antek_geo_core import brand as _brand
from antek_geo_core import providers as _providers
from antek_geo_core import settings as _core_settings
from antek_geo_core.models import CHECK_MODELS  # canonical 5 engines (shared)

# Web-search grounding ON by default (GEO_WEB_SEARCH, default on) — the audit
# must reflect how ChatGPT/Gemini actually answer today (live search), not stale
# training data. Set GEO_WEB_SEARCH=0 to disable.
_core_settings.X_TITLE = "GEO SLAB"

OPENROUTER_URL = _providers.OPENROUTER_URL


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


# ── Brand detection (shared) ───────────────────────────────────────────────
normalize_brand_name = _brand.normalize_brand_name
detect_brand_mention = _brand.detect_brand_mention
extract_competitors = _brand.extract_competitors


# ── OpenRouter (SLAB-compat signatures over the shared impl) ────────────────

def query_openrouter_full(prompt: str, api_key: str, model: str) -> Optional[dict]:
    """SLAB arg order (prompt, api_key, model). Delegates to the shared core
    (which uses the canonical prompt, model, api_key order)."""
    return _providers.query_openrouter_full(prompt, model, api_key)


def query_openrouter(prompt: str, api_key: str, model: str = "openai/gpt-4o-mini") -> Optional[str]:
    """Text-only call. Kept signature-compatible with live_ai_query wrappers."""
    result = query_openrouter_full(prompt, api_key, model)
    return result.get("text") if result else None


# Per-platform wrappers (unchanged slugs — used by live_ai_query).
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
    assert detect_brand_mention("visit acme.com today", "Acme", "https://acme.com")["mentioned"]
    comps = extract_competitors("1. Beta Corp\n2. Gamma Ltd\n3. Acme", "Acme")
    assert "Beta Corp" in comps and "Gamma Ltd" in comps and "Acme" not in comps, comps
    print("ai_query_core self-check passed (via antek-geo-core)")


if __name__ == "__main__":
    _demo()
