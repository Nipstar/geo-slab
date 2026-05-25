#!/usr/bin/env python3
"""
GEO SLAB — voice gate for the CLIENT PDF.

Greps a generated GEO-REPORT-*.pdf (or .html) for raw technical terms that
must never appear in client-facing copy. The developer PDF (GEO-DEV-REPORT-*)
is allowed all of these — don't run voice_check.py against it.

Usage:
    python voice_check.py reports/<domain>/GEO-REPORT-<domain>.pdf
    python voice_check.py reports/<domain>/GEO-REPORT-<domain>.html

Exit code 0 = clean. Exit code 1 = banned terms found (prints them).
Exit code 2 = file not found / cannot read.

Source: /STYLE.md "BANNED IN CLIENT PDF" + scripts/style.py:US_TO_UK_SPELLINGS.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Terms allowed in the developer PDF but BANNED in the client PDF.
# Case-sensitive matches use \b word boundaries below. Multi-word phrases are
# matched as literal substrings (case-insensitive on the phrase).
BANNED_TERMS = [
    "JSON-LD", "Organization schema", "LegalService", "LocalBusiness",
    "Person schema", "Attorney schema", "FAQPage", "NewsArticle",
    "Article schema", "AggregateRating", "sameAs", "Yoast", "WordPress",
    "fetchpriority", "preconnect", "defer ", "HSTS", "CSP",
    "X-Frame-Options", "Referrer-Policy", "WebP", "AVIF",
    "LCP", "INP", "CLS", "PageSpeed", "taxonomy", "Open Graph",
    "NAP", "GBP", "E-E-A-T", "schema.org", "llms.txt", "robots.txt",
]

# OG appears in normal English ("logging"); match as a standalone token only.
BANNED_TOKENS = {"OG"}

# US spellings (lowercase). Mirrors scripts/style.py:US_TO_UK_SPELLINGS.
US_SPELLINGS = [
    "optimize", "optimized", "optimizing", "optimization",
    "organize", "organized", "organizing", "organization",
    "analyze", "analyzed", "analyzing",
    "color", "colored", "behavior", "favor", "favorite",
    "center", "centered", "defense", "offense",
    "prioritize", "prioritized", "recognize", "customize", "summarize",
    "specialize", "specialized", "specializing",
]


def extract_text(path: Path) -> str:
    """Extract plain text from .html or .pdf. PDF requires pdfminer.six or pypdf.

    For HTML, strip the <head>...</head> block — link rel=preconnect and other
    head-only tags would otherwise generate false positives even though no
    reader ever sees that text.
    """
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm", ".md", ".txt"):
        raw = path.read_text(encoding="utf-8", errors="replace")
        if suffix in (".html", ".htm"):
            raw = re.sub(r"<head>.*?</head>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        return raw
    if suffix == ".pdf":
        try:
            from pdfminer.high_level import extract_text as _et  # type: ignore
            return _et(str(path))
        except Exception:
            pass
        try:
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(str(path))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            print(f"ERROR: install pdfminer.six or pypdf to grep PDFs ({e})", file=sys.stderr)
            sys.exit(2)
    print(f"ERROR: unsupported file type: {suffix}", file=sys.stderr)
    sys.exit(2)


def find_hits(text: str) -> list:
    hits = []
    for term in BANNED_TERMS:
        # Phrase match — case-insensitive substring is strict enough for our terms.
        if term.lower() in text.lower():
            hits.append(("banned-term", term))
    for tok in BANNED_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", text):
            hits.append(("banned-token", tok))
    for sp in US_SPELLINGS:
        if re.search(rf"\b{re.escape(sp)}\b", text, flags=re.IGNORECASE):
            hits.append(("us-spelling", sp))
    return hits


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(2)

    text = extract_text(path)
    hits = find_hits(text)

    if not hits:
        print(f"OK: {path.name} — no banned technical terms or US spellings.")
        sys.exit(0)

    print(f"FAIL: {path.name} — voice check found {len(hits)} issue(s):")
    seen = set()
    for kind, term in hits:
        key = (kind, term.lower())
        if key in seen:
            continue
        seen.add(key)
        print(f"  [{kind}] {term}")
    print("\nFix in the agent client_summary fields, then re-render.")
    sys.exit(1)


if __name__ == "__main__":
    main()
