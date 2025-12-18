from __future__ import annotations

import re

from bs4 import BeautifulSoup


def pick_parser() -> str:
    try:
        import lxml  # noqa: F401

        return "lxml"
    except Exception:
        return "html.parser"


def extract_visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    body = soup.body
    if body:
        text = body.get_text(separator=" ", strip=True)
    else:
        text = soup.get_text(separator=" ", strip=True)

    return re.sub(r"\s+", " ", text).strip()

