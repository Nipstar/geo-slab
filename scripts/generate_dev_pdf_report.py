#!/usr/bin/env python3
"""
GEO Developer Hand-off PDF Generator (Playwright).

Sibling of generate_pdf_report.py. Renders the technical hand-off HTML via
render_dev_report.py, then prints to PDF using Playwright headless Chromium.

Usage:
    python generate_dev_pdf_report.py data.json [output.pdf]
    cat data.json | python generate_dev_pdf_report.py - output.pdf

Default output filename: GEO-DEV-REPORT-<domain>.pdf.

Requirements:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import os
import re
import sys
import tempfile
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent
_RENDER_SCRIPT = _SCRIPTS_DIR / "render_dev_report.py"

if not _RENDER_SCRIPT.exists():
    print(f"ERROR: render_dev_report.py not found at {_RENDER_SCRIPT}", file=sys.stderr)
    sys.exit(1)

_spec = _ilu.spec_from_file_location("render_dev_report", _RENDER_SCRIPT)
_render_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_render_mod)
build_html = _render_mod.build_html


def domain_from_url(url: str) -> str:
    return re.sub(r"https?://(www\.)?", "", url).rstrip("/").split("/")[0]


def html_to_pdf(html_content: str, output_path: str) -> str:
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
                margin={"top": "16mm", "right": "12mm", "bottom": "16mm", "left": "12mm"},
            )
            browser.close()
    finally:
        os.unlink(tmp_path)
    return output_path


def generate(data: dict, output_path: str) -> str:
    return html_to_pdf(build_html(data), output_path)


def default_output_name(data: dict) -> str:
    url = data.get("url", "site")
    domain = domain_from_url(url)
    safe = re.sub(r"[^\w.-]", "-", domain)
    return f"GEO-DEV-REPORT-{safe}.pdf"


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    input_arg = sys.argv[1]
    data = json.load(sys.stdin) if input_arg == "-" else json.load(open(input_arg, encoding="utf-8"))
    output_arg = sys.argv[2] if len(sys.argv) > 2 else default_output_name(data)

    out = generate(data, output_arg)
    size_kb = round(Path(out).stat().st_size / 1024)
    print(f"Dev PDF report generated: {out} ({size_kb} KB)")
