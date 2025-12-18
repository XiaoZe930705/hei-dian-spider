#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
黑點網站爬蟲（模組化）

站內多頁爬取 + SEO 稽核報表輸出（JSON + PDF）。
"""

from __future__ import annotations

import argparse
import logging
import time

import schedule

from hei_dian_spider.config import (
    TARGET_URL,
    DEFAULT_MAX_PAGES,
    DEFAULT_MAX_DEPTH,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_SAVE_HTML_LIMIT,
)
from hei_dian_spider.crawler import crawl_site_and_audit


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("spider.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="站內多頁爬取 + SEO 稽核報表輸出")
    parser.add_argument("--url", default=TARGET_URL, help="起始網址（預設為 TARGET_URL）")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help="最多爬取頁數")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH, help="最多跟隨深度（BFS）")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="每次請求間隔秒數")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="requests timeout 秒數")
    parser.add_argument("--keep-query", action="store_true", help="是否保留 URL query（預設移除）")
    parser.add_argument("--no-save-html", action="store_true", help="不保存原始 HTML")
    parser.add_argument("--save-html-limit", type=int, default=DEFAULT_SAVE_HTML_LIMIT, help="最多保存幾頁 HTML")
    parser.add_argument("--once", action="store_true", help="只執行一次後結束（不進入排程）")
    parser.add_argument("--interval-days", type=int, default=1, help="排程間隔天數（預設 1）")
    parser.add_argument("--daily-at", default="03:00", help="每日執行時間（HH:MM，預設 03:00）")
    return parser


def run_once(args: argparse.Namespace) -> None:
    crawl_site_and_audit(
        args.url,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay_seconds=args.delay,
        timeout_seconds=args.timeout,
        keep_query=args.keep_query,
        save_html=not args.no_save_html,
        save_html_limit=args.save_html_limit,
    )


def main() -> None:
    args = build_arg_parser().parse_args()

    logger.info("黑點網站爬蟲啟動（多頁 + SEO 稽核）")
    logger.info(f"起始網址: {args.url}")
    logger.info(f"max_pages={args.max_pages}, max_depth={args.max_depth}, delay={args.delay}s")

    run_once(args)
    if args.once:
        return

    # 啟動時已先跑一次；之後改為每日跑一次（或每 N 天）
    try:
        schedule.every(args.interval_days).days.at(args.daily_at).do(lambda: run_once(args))
        logger.info(f"定時任務已設定：每 {args.interval_days} 天於 {args.daily_at} 執行（Ctrl+C 停止）")
    except Exception:
        schedule.every(args.interval_days).days.do(lambda: run_once(args))
        logger.warning("daily-at 格式錯誤，改用每 N 天執行（不指定時間）。")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("爬蟲已停止")


if __name__ == "__main__":
    main()
