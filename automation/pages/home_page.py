from __future__ import annotations

from automation.pages.base_page import BasePage


class HomePage(BasePage):
    def __init__(self, home_url: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.home_url = home_url

    def open(self) -> None:
        self.page.goto(self.home_url, wait_until="domcontentloaded")

    def wait_ready(self) -> None:
        self.wait_and_get("home", "main_ready")
