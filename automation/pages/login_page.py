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

    def login(self, username: str, password: str, require_manual_captcha: bool) -> None:
        self.open()

        if self.is_logged_in():
            self.logger.info("Session already authenticated, skip login")
            return

        self.fill("login", "username", username)
        self.fill("login", "password", password)

        if require_manual_captcha and self.is_present("login", "captcha_hint"):
            input("Captcha detected. Complete it in browser, then press Enter to continue...")

        self.click("login", "submit")

        # Wait for a post-login marker to ensure login succeeded.
        self.wait_and_get("login", "post_login_marker")
        self.logger.info("Login succeeded")
