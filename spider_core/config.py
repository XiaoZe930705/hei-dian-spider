from __future__ import annotations

import os

TARGET_URL = "https://hei-dian.com.tw/"

DEFAULT_MAX_PAGES = 60
DEFAULT_MAX_DEPTH = 3
DEFAULT_DELAY_SECONDS = 0.5
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_KEEP_QUERY = False
DEFAULT_SAVE_HTML = True
DEFAULT_SAVE_HTML_LIMIT = 60

DATA_DIR = "data"
HTML_DIR = os.path.join(DATA_DIR, "html")

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
