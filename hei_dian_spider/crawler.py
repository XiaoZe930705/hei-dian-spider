from __future__ import annotations

import os
import time
import json
import logging
from collections import deque, defaultdict
from datetime import datetime

import requests

from .audit import extract_page_seo, evaluate_page_issues
from .config import DATA_DIR, HTML_DIR, DEFAULT_KEEP_QUERY
from .http_client import fetch_html, render_pdf_from_html
from .parsing import pick_parser
from .reporting import build_html_report
from .security import analyze_security
from .url_utils import canonicalize_url, is_same_site, safe_filename_from_url

logger = logging.getLogger(__name__)


def _ensure_dirs(save_html: bool) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    if save_html:
        os.makedirs(HTML_DIR, exist_ok=True)


def _dupes(pages: list[dict], field: str) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    for p in pages:
        value = (p.get(field) or "").strip()
        if not value:
            continue
        buckets[value].append(p.get("final_url") or p.get("url") or "")
    return {k: v for k, v in buckets.items() if len(v) > 1}


def crawl_site_and_audit(
    seed_url: str,
    *,
    max_pages: int,
    max_depth: int,
    delay_seconds: float,
    timeout_seconds: int,
    keep_query: bool = DEFAULT_KEEP_QUERY,
    save_html: bool = True,
    save_html_limit: int = 60,
) -> dict | None:
    try:
        seed_url = canonicalize_url(seed_url, keep_query=keep_query)
        logger.info(f"開始多頁爬取: {seed_url} | max_pages={max_pages}, max_depth={max_depth}")

        _ensure_dirs(save_html=save_html)
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")

        html_run_dir = os.path.join(HTML_DIR, timestamp_str)
        if save_html:
            os.makedirs(html_run_dir, exist_ok=True)

        parser = pick_parser()
        queue = deque([(seed_url, 0)])
        seen: set[str] = set()
        pages: list[dict] = []
        inbound_counts: dict[str, int] = defaultdict(int)

        with requests.Session() as session:
            while queue and len(pages) < max_pages:
                url, depth = queue.popleft()
                url = canonicalize_url(url, keep_query=keep_query)
                if url in seen:
                    continue
                seen.add(url)

                if not is_same_site(url, seed_url):
                    continue

                logger.info(f"[{len(pages)+1}/{max_pages}] depth={depth} GET {url}")
                started = time.time()
                try:
                    html, resp = fetch_html(url, session=session, timeout=timeout_seconds)
                except Exception as e:
                    elapsed_ms = int((time.time() - started) * 1000)
                    page = {
                        "url": url,
                        "final_url": url,
                        "depth": depth,
                        "status_code": None,
                        "error": str(e),
                        "elapsed_ms": elapsed_ms,
                        "indexable": False,
                        "issues": ["request_failed"],
                    }
                    pages.append(page)
                    continue

                elapsed_ms = int((time.time() - started) * 1000)
                page, out_links = extract_page_seo(url, html, resp, parser, keep_query=keep_query)
                page["depth"] = depth
                page["elapsed_ms"] = elapsed_ms

                indexable, issues = evaluate_page_issues(page, seed_url=seed_url)
                page["indexable"] = indexable
                page["issues"] = issues

                security = analyze_security(seed_url, page.get("final_url") or url, html, resp)
                page["security"] = security
                page["security_score"] = security.get("score")
                page["security_grade"] = security.get("grade")
                pages.append(page)

                if save_html and len(pages) <= save_html_limit:
                    html_path = os.path.join(html_run_dir, safe_filename_from_url(page.get("final_url") or url))
                    try:
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(html)
                    except Exception as e:
                        logger.warning(f"HTML 儲存失敗: {html_path} | {e}")

                for link in out_links:
                    if is_same_site(link, seed_url):
                        inbound_counts[canonicalize_url(link, keep_query=keep_query)] += 1

                if depth < max_depth:
                    for link in out_links:
                        if not is_same_site(link, seed_url):
                            continue
                        link = canonicalize_url(link, keep_query=keep_query)
                        if link not in seen:
                            queue.append((link, depth + 1))

                if delay_seconds > 0:
                    time.sleep(delay_seconds)

        for p in pages:
            p_url = canonicalize_url(p.get("final_url") or p.get("url") or "", keep_query=keep_query)
            p["inbound_link_count"] = int(inbound_counts.get(p_url, 0))

        security_scores = [int(p.get("security_score")) for p in pages if p.get("security_score") is not None]
        avg_security_score = int(sum(security_scores) / len(security_scores)) if security_scores else None
        min_security_score = min(security_scores) if security_scores else None

        owasp_hits_total: dict[str, int] = defaultdict(int)
        security_finding_counts: dict[str, int] = defaultdict(int)
        for p in pages:
            sec = p.get("security") or {}
            for f in sec.get("findings") or []:
                security_finding_counts[str(f)] += 1
            for k, v in (sec.get("owasp_top10_hits") or {}).items():
                owasp_hits_total[str(k)] += int(v or 0)

        summary = {
            "pages_crawled": len(pages),
            "seed_url": seed_url,
            "max_pages": max_pages,
            "max_depth": max_depth,
            "keep_query": keep_query,
            "missing_title": sum(1 for p in pages if "missing_title" in (p.get("issues") or [])),
            "missing_meta_description": sum(
                1 for p in pages if "missing_meta_description" in (p.get("issues") or [])
            ),
            "missing_h1": sum(1 for p in pages if "missing_h1" in (p.get("issues") or [])),
            "noindex": sum(1 for p in pages if "noindex" in (p.get("issues") or [])),
            "non_200": sum(1 for p in pages if (p.get("status_code") not in (None, 200))),
            "duplicate_titles": _dupes(pages, "title"),
            "duplicate_meta_descriptions": _dupes(pages, "meta_description"),
        }

        report = {
            "timestamp": now.isoformat(),
            "timestamp_id": timestamp_str,
            "seed_url": seed_url,
            "pages": pages,
            "summary": summary,
            "security": {
                "avg_score": avg_security_score,
                "min_score": min_security_score,
                "owasp_top10_hits_total": dict(owasp_hits_total),
                "finding_counts": dict(security_finding_counts),
            },
        }

        json_path = os.path.join(DATA_DIR, f"seo_audit_{timestamp_str}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        html_report_path = os.path.join(DATA_DIR, f"seo_audit_{timestamp_str}.html")
        with open(html_report_path, "w", encoding="utf-8") as f:
            f.write(build_html_report(report))

        pdf_path = os.path.join(DATA_DIR, f"seo_audit_{timestamp_str}.pdf")
        pdf_ok = render_pdf_from_html(html_report_path, pdf_path)

        logger.info(f"SEO 稽核完成！JSON: {json_path}")
        if pdf_ok:
            logger.info(f"SEO 稽核完成！PDF: {pdf_path}")
        else:
            logger.warning(f"PDF 產生失敗（仍可手動用瀏覽器列印 HTML）：{html_report_path}")
        if save_html:
            logger.info(f"HTML（前 {min(save_html_limit, len(pages))} 頁）保存於: {html_run_dir}")

        return report
    except Exception:
        logger.exception("爬取過程發生錯誤")
        return None
