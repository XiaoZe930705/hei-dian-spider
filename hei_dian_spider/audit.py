from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .parsing import extract_visible_text
from .url_utils import canonicalize_url, normalize_and_filter_links, is_same_site


def extract_page_seo(
    url: str,
    html: str,
    resp,
    parser: str,
    *,
    keep_query: bool,
):
    soup = BeautifulSoup(html, parser)

    title = soup.title.get_text(strip=True) if soup.title else None
    meta_description_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    meta_keywords_tag = soup.find("meta", attrs={"name": re.compile(r"^keywords$", re.I)})
    canonical_tag = soup.find("link", attrs={"rel": re.compile(r"\\bcanonical\\b", re.I)})

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")]
    h3_tags = [h.get_text(strip=True) for h in soup.find_all("h3")]

    hrefs = [a.get("href") for a in soup.find_all("a", href=True)]
    out_links = normalize_and_filter_links(url, hrefs, keep_query=keep_query)

    text_content = extract_visible_text(soup)
    text_preview = text_content[:500] if text_content else None

    robots_meta_tags = soup.find_all("meta", attrs={"name": re.compile(r"^(robots|googlebot)$", re.I)})
    robots_meta = []
    for tag in robots_meta_tags:
        content = (tag.get("content") or "").strip()
        if content:
            robots_meta.append(content)

    page = {
        "url": url,
        "final_url": resp.url,
        "status_code": resp.status_code,
        "content_type": resp.headers.get("Content-Type"),
        "content_encoding": resp.headers.get("Content-Encoding"),
        "x_robots_tag": resp.headers.get("X-Robots-Tag"),
        "title": title,
        "title_length": len(title) if title else 0,
        "content_length": len(html),
        "meta_description": meta_description_tag.get("content") if meta_description_tag else None,
        "meta_description_length": len((meta_description_tag.get("content") or "").strip()) if meta_description_tag else 0,
        "meta_keywords": meta_keywords_tag.get("content") if meta_keywords_tag else None,
        "canonical_url": canonical_tag.get("href") if canonical_tag else None,
        "h1_tags": h1_tags,
        "h2_tags": h2_tags[:20],
        "h3_tags": h3_tags[:20],
        "link_count": len(out_links),
        "links": out_links[:100],
        "text_content_length": len(text_content),
        "text_preview": text_preview,
        "robots_meta": robots_meta,
    }

    return page, out_links


def evaluate_page_issues(page: dict, *, seed_url: str) -> tuple[bool, list[str]]:
    issues: list[str] = []

    status_code = page.get("status_code")
    if status_code and status_code != 200:
        issues.append(f"http_status_{status_code}")

    content_type = (page.get("content_type") or "").lower()
    if content_type and ("text/html" not in content_type) and ("application/xhtml+xml" not in content_type):
        issues.append("non_html_content_type")

    title = (page.get("title") or "").strip()
    if not title:
        issues.append("missing_title")
    else:
        if len(title) < 10:
            issues.append("title_too_short")
        if len(title) > 60:
            issues.append("title_too_long")

    meta_desc = (page.get("meta_description") or "").strip()
    if not meta_desc:
        issues.append("missing_meta_description")
    else:
        if len(meta_desc) < 50:
            issues.append("meta_description_too_short")
        if len(meta_desc) > 160:
            issues.append("meta_description_too_long")

    h1_tags = page.get("h1_tags") or []
    if len(h1_tags) == 0:
        issues.append("missing_h1")
    elif len(h1_tags) > 1:
        issues.append("multiple_h1")

    canonical_url = (page.get("canonical_url") or "").strip()
    if not canonical_url:
        issues.append("missing_canonical")
    else:
        try:
            canonical_abs = canonicalize_url(urljoin(page.get("final_url") or page.get("url") or seed_url, canonical_url))
            if not is_same_site(canonical_abs, seed_url):
                issues.append("canonical_offsite")
        except Exception:
            issues.append("canonical_invalid")

    robots_meta = " ".join((page.get("robots_meta") or [])).lower()
    x_robots = (page.get("x_robots_tag") or "").lower()
    if "noindex" in robots_meta or "noindex" in x_robots:
        issues.append("noindex")

    text_len = int(page.get("text_content_length") or 0)
    if text_len < 200:
        issues.append("thin_or_csr_content")

    indexable = "noindex" not in issues and (status_code == 200)
    return indexable, issues

