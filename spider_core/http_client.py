from __future__ import annotations

import os
import shutil
import subprocess
import logging

import requests

from .config import HEADERS

logger = logging.getLogger(__name__)

try:
    import brotli  # pip install brotli
except Exception:
    brotli = None


def fetch_html(url: str, session: requests.Session, timeout: int = 30) -> tuple[str, requests.Response]:
    resp = session.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)

    content_type = (resp.headers.get("Content-Type") or "").lower()
    content_encoding = (resp.headers.get("Content-Encoding") or "").lower()
    logger.info(f"HTTP {resp.status_code} | Content-Type: {content_type} | Content-Encoding: {content_encoding}")

    if ("text/html" not in content_type) and ("application/xhtml+xml" not in content_type):
        logger.warning(f"Content-Type 看起來不是 HTML：{content_type}（仍嘗試解析）")

    raw = resp.content
    if content_encoding == "br":
        if brotli is None:
            raise RuntimeError(
                "伺服器回傳 br 壓縮，但你的環境未安裝 brotli。請執行：pip install brotli\n"
                "或確保不要主動宣告 Accept-Encoding 包含 br（本程式已移除）。"
            )
        raw = brotli.decompress(raw)

    encoding = resp.encoding
    if not encoding or encoding.lower() in ("iso-8859-1", "latin-1"):
        encoding = resp.apparent_encoding or "utf-8"

    html = raw.decode(encoding, errors="replace")
    return html, resp


def find_chromium_executable() -> tuple[str | None, str | None]:
    candidates: list[tuple[str, str]] = []

    edge = shutil.which("msedge")
    if edge:
        candidates.append(("edge", edge))

    chrome = shutil.which("chrome")
    if chrome:
        candidates.append(("chrome", chrome))

    # Linux 常見（Docker/CI）
    google_chrome = shutil.which("google-chrome")
    if google_chrome:
        candidates.append(("chrome", google_chrome))

    chromium = shutil.which("chromium")
    if chromium:
        candidates.append(("chromium", chromium))

    chromium_browser = shutil.which("chromium-browser")
    if chromium_browser:
        candidates.append(("chromium", chromium_browser))

    program_files = os.environ.get("ProgramFiles") or r"C:\Program Files"
    program_files_x86 = os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)"

    edge_paths = [
        os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    chrome_paths = [
        os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
    ]

    for p in edge_paths:
        if os.path.exists(p):
            candidates.append(("edge", p))
            break
    for p in chrome_paths:
        if os.path.exists(p):
            candidates.append(("chrome", p))
            break

    if not candidates:
        return None, None

    seen = set()
    for name, path in candidates:
        if path not in seen:
            seen.add(path)
            return name, path
    return None, None


def render_pdf_from_html(html_path: str, pdf_path: str) -> bool:
    browser_name, exe = find_chromium_executable()
    if not exe:
        logger.warning("找不到 Edge/Chrome（無法自動輸出 PDF）。")
        return False

    file_url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    cmd = [
        exe,
        "--headless=new",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        f"--print-to-pdf={os.path.abspath(pdf_path)}",
        file_url,
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except Exception as e:
        logger.warning(f"{browser_name} 產 PDF 失敗：{e}")
        return False

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        logger.warning(f"{browser_name} 產 PDF 失敗（exit={proc.returncode}）：{stderr[:500]}")
        return False

    return os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
