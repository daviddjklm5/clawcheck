from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from automation.pages.base_page import BasePage


class LoginPage(BasePage):
    _BROWSER_ERROR_PAGE_PREFIXES = ("chrome-error://", "edge-error://")
    _OPEN_RETRY_COUNT = 2
    _OPEN_RETRY_WAIT_MS = 1000

    def __init__(self, home_url: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.home_url = home_url

    def _is_browser_error_page(self) -> bool:
        try:
            current_url = str(self.page.url or "")
        except Exception:  # noqa: BLE001
            return False
        return current_url.startswith(self._BROWSER_ERROR_PAGE_PREFIXES)

    def open(self) -> None:
        last_exc: Exception | None = None

        for attempt in range(1, self._OPEN_RETRY_COUNT + 1):
            try:
                self.page.goto(self.home_url, wait_until="domcontentloaded")
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                self.logger.warning(
                    "Login navigation attempt %s/%s failed for %s: %s",
                    attempt,
                    self._OPEN_RETRY_COUNT,
                    self.home_url,
                    exc,
                )
            else:
                if not self._is_browser_error_page():
                    if attempt > 1:
                        self.logger.info(
                            "Login navigation recovered on attempt %s. Current URL: %s",
                            attempt,
                            self.page.url,
                        )
                    return

                last_exc = RuntimeError(f"Browser landed on Chromium error page: {self.page.url}")
                self.logger.warning(
                    "Login navigation attempt %s/%s landed on Chromium error page. "
                    "Target URL: %s; current URL: %s",
                    attempt,
                    self._OPEN_RETRY_COUNT,
                    self.home_url,
                    self.page.url,
                )

            if attempt < self._OPEN_RETRY_COUNT:
                self.page.wait_for_timeout(self._OPEN_RETRY_WAIT_MS)

        current_url = ""
        try:
            current_url = str(self.page.url or "")
        except Exception:  # noqa: BLE001
            current_url = ""
        message = (
            "Unable to open login entry page after navigation retries. "
            f"Target URL: {self.home_url}; current URL: {current_url or 'unknown'}"
        )
        raise RuntimeError(message) from last_exc

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

            if self._is_browser_error_page():
                self.logger.warning(
                    "Login round %s detected Chromium error page before input stage. Reopening %s",
                    round_idx,
                    self.home_url,
                )
                self.open()

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
                if self._is_browser_error_page():
                    raise RuntimeError(
                        "Login page became a Chromium error page before submit. "
                        f"Target URL: {self.home_url}; current URL: {self.page.url}"
                    )
                raise RuntimeError(f"Login submit button not found on current page. Current URL: {self.page.url}")

            self.page.wait_for_timeout(3000)
            if self.is_logged_in():
                self.logger.info("Login succeeded")
                return

        raise RuntimeError(f"Login did not reach post-login marker. Last URL: {self.page.url}")
