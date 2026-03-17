from __future__ import annotations

import logging

from playwright.sync_api import Locator, Page

from automation.utils.playwright_helpers import wait_for_first_visible


class BasePage:
    def __init__(
        self,
        page: Page,
        selectors: dict[str, dict[str, list[str]]],
        logger: logging.Logger,
        timeout_ms: int,
    ) -> None:
        self.page = page
        self.selectors = selectors
        self.logger = logger
        self.timeout_ms = timeout_ms

    def _candidate_selectors(self, section: str, key: str) -> list[str]:
        section_data = self.selectors.get(section, {})
        values = section_data.get(key, [])
        if not values:
            raise KeyError(f"Missing selectors for '{section}.{key}'")
        return values

    def set_page(self, page: Page) -> None:
        self.page = page

    def wait_and_get(self, section: str, key: str) -> tuple[str, Locator]:
        candidates = self._candidate_selectors(section, key)
        selector, locator = wait_for_first_visible(self.page, candidates, self.timeout_ms)
        self.logger.info("Matched selector %s.%s -> %s", section, key, selector)
        return selector, locator

    def click(self, section: str, key: str) -> None:
        _, locator = self.wait_and_get(section, key)
        locator.click()

    def fill(self, section: str, key: str, value: str) -> None:
        _, locator = self.wait_and_get(section, key)
        locator.fill(value)

    def is_present(self, section: str, key: str) -> bool:
        selectors = self.selectors.get(section, {}).get(key, [])
        if not selectors:
            return False
        for selector in selectors:
            try:
                if self.page.locator(selector).first.count() > 0:
                    return True
            except Exception:  # noqa: BLE001
                continue
        return False
