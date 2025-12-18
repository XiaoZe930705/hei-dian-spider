#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
黑點網站爬蟲（修正版）
每30分鐘自動爬取 https://hei-dian.com.tw/ 網站
- 修正：避免 br 壓縮導致 requests 解析出亂碼 / soup 解析失敗
- 支援：若仍收到 br，嘗試使用 brotli 解壓（可選套件）
- 追加：保存 raw HTML 供除錯（判斷是否 CSR/JS 渲染）
"""

import os
import json
import time
import re
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import schedule

# ====== 可選：支援 brotli（若伺服器硬回 br）======
try:
    import brotli  # pip install brotli
except Exception:
    brotli = None

# ====== 日誌設定 ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("spider.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ====== 目標網站 ======
TARGET_URL = "https://hei-dian.com.tw/"

# ====== 請求標頭（重點：不要手動宣告 Accept-Encoding，讓 requests/urllib3 自己談判）======
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ====== 輸出資料夾 ======
DATA_DIR = "data"
HTML_DIR = os.path.join(DATA_DIR, "html")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)


def _pick_parser():
    """
    優先使用 lxml（若已安裝），否則退回 html.parser
    """
    try:
        import lxml  # noqa: F401
        return "lxml"
    except Exception:
        return "html.parser"


def fetch_html(url: str, session: requests.Session, timeout: int = 30) -> tuple[str, requests.Response]:
    """
    抓取並回傳「已解壓 + 已解碼」的 HTML 字串
    - 若遇到 Content-Encoding: br，嘗試用 brotli 解壓（需安裝 brotli）
    """
    resp = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()

    content_type = (resp.headers.get("Content-Type") or "").lower()
    content_encoding = (resp.headers.get("Content-Encoding") or "").lower()

    logger.info(f"HTTP {resp.status_code} | Content-Type: {content_type} | Content-Encoding: {content_encoding}")

    # 基本檢查：避免抓到非 HTML（例如圖片、檔案）
    if ("text/html" not in content_type) and ("application/xhtml+xml" not in content_type):
        # 有些站 Content-Type 可能沒寫標準，但仍是 HTML；這裡不直接擋死，改用保守判斷
        logger.warning(f"Content-Type 看起來不是 HTML：{content_type}（仍嘗試解析）")

    # requests 對 gzip/deflate 通常會自動處理；但 br 視環境而定
    raw = resp.content

    if content_encoding == "br":
        if brotli is None:
            raise RuntimeError(
                "伺服器回傳 br 壓縮，但你的環境未安裝 brotli。請執行：pip install brotli\n"
                "或確保不要主動宣告 Accept-Encoding 包含 br（本程式已移除）。"
            )
        raw = brotli.decompress(raw)

    # 決定解碼
    encoding = resp.encoding
    if not encoding or encoding.lower() in ("iso-8859-1", "latin-1"):
        encoding = resp.apparent_encoding or "utf-8"

    html = raw.decode(encoding, errors="replace")
    return html, resp


def normalize_and_filter_links(base_url: str, hrefs: list[str]) -> list[str]:
    """
    轉為絕對連結、移除 javascript/mailto/tel/hash 等
    """
    out = []
    for href in hrefs:
        if not href:
            continue
        href = href.strip()

        # 過濾無效 / 非 http(s)
        if href.startswith("#"):
            continue
        if href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue

        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)

        # 只保留 http/https
        if parsed.scheme not in ("http", "https"):
            continue

        out.append(abs_url)

    # 去重但保序
    seen = set()
    uniq = []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def extract_visible_text(soup: BeautifulSoup) -> str:
    """
    抽取可讀文字（較保守、較不會抓到亂碼）
    """
    # 移除不應出現在正文的 tag
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    body = soup.body
    if body:
        text = body.get_text(separator=" ", strip=True)
    else:
        text = soup.get_text(separator=" ", strip=True)

    # 清理多餘空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def crawl_website():
    """
    爬取目標網站並輸出 JSON + 原始 HTML
    """
    try:
        logger.info(f"開始爬取網站: {TARGET_URL}")

        with requests.Session() as session:
            html, resp = fetch_html(TARGET_URL, session=session, timeout=30)

        parser = _pick_parser()
        soup = BeautifulSoup(html, parser)

        # --- SEO / 結構資料 ---
        title = soup.title.get_text(strip=True) if soup.title else None

        meta_description = soup.find("meta", attrs={"name": "description"})
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        canonical = soup.find("link", attrs={"rel": "canonical"})

        h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
        h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")]
        h3_tags = [h.get_text(strip=True) for h in soup.find_all("h3")]

        hrefs = [a.get("href") for a in soup.find_all("a", href=True)]
        links = normalize_and_filter_links(TARGET_URL, hrefs)

        # --- 文字 ---
        text_content = extract_visible_text(soup)
        text_preview = text_content[:500] if text_content else None

        # --- 結果資料 ---
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")

        data = {
            "timestamp": now.isoformat(),
            "url": TARGET_URL,
            "final_url": resp.url,
            "status_code": resp.status_code,
            "content_type": resp.headers.get("Content-Type"),
            "content_encoding": resp.headers.get("Content-Encoding"),
            "title": title,
            "content_length": len(html),
            "meta_description": meta_description.get("content") if meta_description else None,
            "meta_keywords": meta_keywords.get("content") if meta_keywords else None,
            "canonical_url": canonical.get("href") if canonical else None,
            "h1_tags": h1_tags,
            "h2_tags": h2_tags[:20],
            "h3_tags": h3_tags[:20],
            "links": links[:100],
            "link_count": len(links),
            "text_content_length": len(text_content),
            "text_preview": text_preview,
        }

        # --- 保存 JSON ---
        json_path = os.path.join(DATA_DIR, f"hei_dian_{timestamp_str}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # --- 保存 HTML（除錯用）---
        html_path = os.path.join(HTML_DIR, f"hei_dian_{timestamp_str}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"爬取成功！JSON: {json_path}")
        logger.info(f"原始 HTML 已保存: {html_path}")
        logger.info(f"標題: {data['title']}")
        logger.info(f"H1: {len(data['h1_tags'])}, H2: {len(data['h2_tags'])}, links: {data['link_count']}")
        logger.info(f"文字長度: {data['text_content_length']}")

        # 若仍幾乎抓不到任何東西，提示可能是 CSR/JS 渲染
        if (data["title"] is None) and (data["link_count"] == 0) and (data["text_content_length"] < 200):
            logger.warning(
                "解析結果仍偏少：可能是前端 CSR/JS 渲染（requests 抓不到渲染後內容）。"
                "請打開 data/html/ 裡的 html 檔確認內容是否本來就很少。"
            )

        return data

    except requests.exceptions.RequestException as e:
        logger.error(f"請求錯誤: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"爬取過程發生錯誤: {str(e)}", exc_info=True)
        return None


def run_scheduled_crawl():
    logger.info("=" * 60)
    logger.info("執行定時爬取任務")
    crawl_website()
    logger.info("=" * 60)


def main():
    logger.info("黑點網站爬蟲啟動（修正版）")
    logger.info(f"目標網站: {TARGET_URL}")
    logger.info("爬取頻率: 每30分鐘")
    logger.info("首次爬取...")

    crawl_website()

    schedule.every(30).minutes.do(run_scheduled_crawl)
    logger.info("定時任務已設定，等待執行...（Ctrl+C 停止）")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("爬蟲已停止")


if __name__ == "__main__":
    main()
