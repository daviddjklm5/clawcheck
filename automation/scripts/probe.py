#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe iERP page structure for selector discovery")
    parser.add_argument("--url", default="https://hr.onewo.com/ierp/?formId=home_page")
    parser.add_argument("--out-dir", default="automation/logs")
    parser.add_argument("--headless", action="store_true", help="Run headless browser")
    return parser.parse_args()


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = now_slug()
    screenshot_path = out_dir / f"probe_{stamp}.png"
    json_path = out_dir / f"probe_{stamp}.json"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        data = page.evaluate(
            """() => {
                const inputs = [...document.querySelectorAll('input')].map(el => ({
                    type: el.type || '',
                    name: el.name || '',
                    id: el.id || '',
                    placeholder: el.placeholder || '',
                    className: el.className || ''
                }))

                const buttons = [...document.querySelectorAll('button,input[type=button],input[type=submit],a')]
                    .map(el => ({
                        tag: el.tagName.toLowerCase(),
                        text: (el.innerText || el.value || '').trim().slice(0, 80),
                        id: el.id || '',
                        className: el.className || ''
                    }))
                    .filter(item => item.text)

                return {
                    title: document.title,
                    location: window.location.href,
                    bodyTextSnippet: (document.body.innerText || '').slice(0, 800),
                    inputs,
                    buttons,
                }
            }"""
        )

        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved screenshot: {screenshot_path}")
    print(f"Saved probe json: {json_path}")
    print(f"Title: {data.get('title')}")
    print(f"URL: {data.get('location')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
