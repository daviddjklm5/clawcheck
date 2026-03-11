from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from automation.pages.base_page import BasePage


class LoginPage(BasePage):
    def __init__(self, home_url: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.home_url = home_url

    def open(self) -> None:
        self.page.goto(self.home_url, wait_until="domcontentloaded")

    def is_logged_in(self) -> bool:
        post_markers = self.selectors.get("login", {}).get("post_login_marker", [])
        for selector in post_markers:
            try:
                self.page.locator(selector).first.wait_for(state="visible", timeout=2500)
                return True
            except PlaywrightTimeoutError:
                continue
        return False

    def _fill_username_if_present(self, username: str) -> bool:
        selectors = self.selectors.get("login", {}).get("username", [])
        for selector in selectors:
            locator = self.page.locator(selector)
            try:
                count = locator.count()
            except Exception:  # noqa: BLE001
                continue
            for idx in range(count):
                candidate = locator.nth(idx)
                try:
                    if candidate.is_visible():
                        candidate.fill(username)
                        self.logger.info("Filled username using selector: %s", selector)
                        return True
                except Exception:  # noqa: BLE001
                    continue
        return False

    def _fill_visible_passwords(self, password: str) -> int:
        selectors = self.selectors.get("login", {}).get("password", [])
        filled = 0
        visited: set[tuple[str, int]] = set()
        for selector in selectors:
            locator = self.page.locator(selector)
            try:
                count = locator.count()
            except Exception:  # noqa: BLE001
                continue
            for idx in range(count):
                if (selector, idx) in visited:
                    continue
                candidate = locator.nth(idx)
                try:
                    if candidate.is_visible():
                        candidate.fill(password)
                        filled += 1
                        visited.add((selector, idx))
                except Exception:  # noqa: BLE001
                    continue
        if filled:
            self.logger.info("Filled %s visible password box(es)", filled)
        return filled

    def _click_submit_if_present(self) -> bool:
        selectors = self.selectors.get("login", {}).get("submit", [])
        for selector in selectors:
            locator = self.page.locator(selector)
            try:
                count = locator.count()
            except Exception:  # noqa: BLE001
                continue
            for idx in range(count):
                candidate = locator.nth(idx)
                try:
                    if candidate.is_visible():
                        candidate.click()
                        self.logger.info("Clicked login submit using selector: %s", selector)
                        return True
                except Exception:  # noqa: BLE001
                    continue
        return False

    def login(self, username: str, password: str, require_manual_captcha: bool) -> None:
        self.open()

        if self.is_logged_in():
            self.logger.info("Session already authenticated, skip login")
            return

        for round_idx in range(1, 5):
            self.logger.info("Login round %s started. Current URL: %s", round_idx, self.page.url)

            if self.is_logged_in():
                self.logger.info("Login already completed before input stage")
                return

            self._fill_username_if_present(username)
            filled_password_count = self._fill_visible_passwords(password)
            if filled_password_count == 0:
                self.logger.warning("No visible password field detected in login round %s", round_idx)

            if require_manual_captcha and self.is_present("login", "captcha_hint"):
                input("Captcha detected. Complete it in browser, then press Enter to continue...")

            clicked = self._click_submit_if_present()
            if not clicked and not self.is_logged_in():
                raise RuntimeError("Login submit button not found on current page")

            self.page.wait_for_timeout(3000)
            if self.is_logged_in():
                self.logger.info("Login succeeded")
                return

        raise RuntimeError(f"Login did not reach post-login marker. Last URL: {self.page.url}")
