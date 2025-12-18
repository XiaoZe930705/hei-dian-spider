from __future__ import annotations

import re
import hashlib
from urllib.parse import urljoin, urlparse

from .config import DEFAULT_KEEP_QUERY


def strip_www(host: str) -> str:
    host = (host or "").strip().lower()
    if host.startswith("www."):
        return host[4:]
    return host


def canonicalize_url(url: str, *, keep_query: bool = DEFAULT_KEEP_QUERY) -> str:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "http").lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port

    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    query = parsed.query if keep_query else ""
    normalized = parsed._replace(
        scheme=scheme,
        netloc=netloc,
        path=path,
        params="",
        query=query,
        fragment="",
    )
    return normalized.geturl()


def looks_like_asset(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    asset_exts = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".css",
        ".js",
        ".map",
        ".json",
        ".xml",
        ".pdf",
        ".zip",
        ".rar",
        ".7z",
        ".mp4",
        ".mp3",
        ".mov",
        ".avi",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
    )
    return any(path.endswith(ext) for ext in asset_exts)


def is_same_site(url: str, seed_url: str) -> bool:
    seed_host = strip_www(urlparse(seed_url).hostname or "")
    host = strip_www(urlparse(url).hostname or "")
    return bool(host) and host == seed_host


def normalize_and_filter_links(base_url: str, hrefs: list[str], *, keep_query: bool = DEFAULT_KEEP_QUERY) -> list[str]:
    out: list[str] = []
    for href in hrefs:
        if not href:
            continue
        href = href.strip()

        if href.startswith("#"):
            continue
        if href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue

        abs_url = urljoin(base_url, href)
        abs_url = canonicalize_url(abs_url, keep_query=keep_query)
        parsed = urlparse(abs_url)

        if parsed.scheme not in ("http", "https"):
            continue
        if looks_like_asset(abs_url):
            continue

        out.append(abs_url)

    seen: set[str] = set()
    uniq: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def safe_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "site"
    path = parsed.path or "/"
    if path in ("", "/"):
        base = "home"
    else:
        base = path.strip("/").replace("/", "_")

    base = re.sub(r'[<>:"/\\\\|?*\\x00-\\x1f]', "_", base)
    base = base.strip(" .") or "page"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{host}_{base}_{digest}.html"

