#!/usr/bin/env python3
"""Validate local links and assets referenced by AxVigil's static web pages."""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PAGES = sorted(WEB.glob("*.html"))


class HTMLReferences(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[tuple[str, str]] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if "id" in values and values["id"]:
            self.ids.add(values["id"])
        for attr in ("href", "src"):
            value = values.get(attr)
            if value:
                self.references.append((attr, value))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def is_local(url: str) -> bool:
    parsed = urlparse(url)
    return not parsed.scheme and not parsed.netloc and not url.startswith("//")


def check_page(page: Path) -> list[str]:
    parser = HTMLReferences()
    parser.feed(page.read_text(encoding="utf-8"))
    errors: list[str] = []
    for attr, raw in parser.references:
        if raw.startswith(("#", "data:", "javascript:", "mailto:", "tel:")) or not is_local(raw):
            continue
        path_part, fragment = urldefrag(raw)
        path_part = path_part.split("?", 1)[0]
        target = (page.parent / unquote(path_part)).resolve() if path_part else page.resolve()
        try:
            target.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"{page.relative_to(ROOT)}: {attr} escapes repository: {raw}")
            continue
        if not target.exists():
            errors.append(f"{page.relative_to(ROOT)}: missing {attr} target: {raw}")
        if fragment and target.suffix.lower() in {".html", ".htm"} and target.exists():
            target_parser = HTMLReferences()
            target_parser.feed(target.read_text(encoding="utf-8"))
            if fragment not in target_parser.ids:
                errors.append(f"{page.relative_to(ROOT)}: missing fragment target: {raw}")
    return errors


def check_css() -> list[str]:
    errors: list[str] = []
    pattern = re.compile(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)")
    for css in WEB.rglob("*.css"):
        text = css.read_text(encoding="utf-8")
        for raw in pattern.findall(text):
            url = raw[1].strip()
            if url.startswith(("data:", "http:", "https:", "//", "#")):
                continue
            target = (css.parent / unquote(url.split("?", 1)[0].split("#", 1)[0])).resolve()
            if not target.exists():
                errors.append(f"{css.relative_to(ROOT)}: missing CSS asset: {url}")
    return errors


def main() -> int:
    if not PAGES:
        print("No web/*.html pages found", file=sys.stderr)
        return 1
    errors = [error for page in PAGES for error in check_page(page)] + check_css()
    if errors:
        print("Web integrity check failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Web integrity check passed: {len(PAGES)} HTML pages and local CSS assets verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
