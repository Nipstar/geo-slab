#!/usr/bin/env python3
"""
GEO Report PDF Generator (Playwright)

Renders the neo brutalist HTML via render_geo_report.py, then prints to PDF
using Playwright's headless Chromium — preserving fonts, colours, and layout.

Usage:
    python generate_pdf_report.py data.json [output.pdf]
    cat data.json | python generate_pdf_report.py - output.pdf

Output defaults to GEO-REPORT-<domain>.pdf in the current directory.

Requirements:
    pip install playwright
    playwright install chromium
"""

import sys
import json
import re
import tempfile
import os
from pathlib import Path
from datetime import datetime

# ── Locate render_geo_report.py relative to this script ──────────────────────
_SCRIPTS_DIR = Path(__file__).parent
_RENDER_SCRIPT = _SCRIPTS_DIR / "render_geo_report.py"

if not _RENDER_SCRIPT.exists():
    print(f"ERROR: render_geo_report.py not found at {_RENDER_SCRIPT}", file=sys.stderr)
    sys.exit(1)

# Import build_html from sibling script
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("render_geo_report", _RENDER_SCRIPT)
_render_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_render_mod)
build_html = _render_mod.build_html


def domain_from_url(url: str) -> str:
    return re.sub(r"https?://(www\.)?", "", url).rstrip("/").split("/")[0]


def html_to_pdf(html_content: str, output_path: str) -> str:
    """Write HTML to a temp file and print to PDF via Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "ERROR: Playwright is required.\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr,
        )
        sys.exit(1)

    # Write HTML to a named temp file so Playwright can load it as file://
    with tempfile.NamedTemporaryFile(
        suffix=".html", delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(html_content)
        tmp_path = tmp.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{tmp_path}", wait_until="networkidle")
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            browser.close()
    finally:
        os.unlink(tmp_path)

    return output_path


def generate(data: dict, output_path: str) -> str:
    html = build_html(data)
    return html_to_pdf(html, output_path)


def default_output_name(data: dict) -> str:
    url = data.get("url", "site")
    domain = domain_from_url(url)
    safe = re.sub(r"[^\w.-]", "-", domain)
    return f"GEO-REPORT-{safe}.pdf"


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    input_arg = sys.argv[1]

    if input_arg == "-":
        data = json.load(sys.stdin)
    else:
        with open(input_arg, encoding="utf-8") as f:
            data = json.load(f)

    output_arg = sys.argv[2] if len(sys.argv) > 2 else default_output_name(data)

    out = generate(data, output_arg)
    size_kb = round(Path(out).stat().st_size / 1024)
    print(f"PDF report generated: {out} ({size_kb} KB)")
