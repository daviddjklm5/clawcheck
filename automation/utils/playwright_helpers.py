from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError


def wait_for_first_visible(page: Page, selectors: list[str], timeout_ms: int) -> tuple[str, Locator]:
    deadline = time.monotonic() + (timeout_ms / 1000)
    last_counts: dict[str, int] = {}

    while time.monotonic() < deadline:
        for selector in selectors:
            locator = page.locator(selector)
            try:
                count = locator.count()
            except Exception:  # noqa: BLE001
                continue

            last_counts[selector] = count
            for idx in range(count):
                candidate = locator.nth(idx)
                try:
                    if candidate.is_visible():
                        return selector, candidate
                except Exception:  # noqa: BLE001
                    continue
        time.sleep(0.2)

    details = " | ".join(f"{selector}: count={last_counts.get(selector, 0)}" for selector in selectors)
    raise PlaywrightTimeoutError(f"No visible element matched within {timeout_ms}ms. {details}")


def has_any_selector(page: Page, selectors: list[str]) -> bool:
    for selector in selectors:
        try:
            if page.locator(selector).first.count() > 0:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_screenshot(page: Page, screenshots_dir: Path, prefix: str) -> Path:
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    file_path = screenshots_dir / f"{prefix}_{timestamp_slug()}.png"
    page.screenshot(path=str(file_path), full_page=True)
    return file_path
