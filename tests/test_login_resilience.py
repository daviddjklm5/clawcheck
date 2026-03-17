from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from automation.scripts.run import ensure_login
from automation.utils.playwright_helpers import save_screenshot
from automation.utils.retry import retry_call


class _FakeLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, message: str, *args) -> None:
        self.warnings.append(message % args if args else message)


class _FakePage:
    def __init__(self, *, closed: bool = False, context=None) -> None:
        self._closed = closed
        self.context = context

    def is_closed(self) -> bool:
        return self._closed

    def close_for_test(self) -> None:
        self._closed = True

    def screenshot(self, *, path: str, full_page: bool) -> None:
        _ = (path, full_page)
        raise RuntimeError("page already closed")


class _FakeContext:
    def __init__(self) -> None:
        self.new_pages: list[_FakePage] = []

    def new_page(self) -> _FakePage:
        page = _FakePage(context=self)
        self.new_pages.append(page)
        return page


class _FakePageHolder:
    def __init__(self, page: _FakePage) -> None:
        self.page = page

    def set_page(self, page: _FakePage) -> None:
        self.page = page


class _FakeLoginPage(_FakePageHolder):
    def __init__(self, page: _FakePage) -> None:
        super().__init__(page)
        self.logger = _FakeLogger()
        self.login_calls = 0

    def login(self, username: str, password: str, require_manual_captcha: bool) -> None:
        _ = (username, password, require_manual_captcha)
        self.login_calls += 1
        if self.login_calls == 1:
            self.page.close_for_test()
            raise RuntimeError("first login attempt closed page")


class EnsureLoginResilienceTest(unittest.TestCase):
    def test_ensure_login_recreates_closed_page_before_retry(self) -> None:
        context = _FakeContext()
        initial_page = _FakePage(context=context)
        login_page = _FakeLoginPage(initial_page)
        home_page = _FakePageHolder(initial_page)
        settings = type(
            "Settings",
            (),
            {
                "auth": type(
                    "Auth",
                    (),
                    {
                        "username": "tester",
                        "password": "tester",
                        "require_manual_captcha": False,
                    },
                )(),
            },
        )()

        final_page = ensure_login(
            login_page,
            settings,
            retries=1,
            wait_sec=0,
            retry_call=retry_call,
            bound_pages=[login_page, home_page],
        )

        self.assertEqual(login_page.login_calls, 2)
        self.assertIs(final_page, context.new_pages[0])
        self.assertIs(login_page.page, final_page)
        self.assertIs(home_page.page, final_page)
        self.assertTrue(any("created a fresh page" in message for message in login_page.logger.warnings))


class SaveScreenshotResilienceTest(unittest.TestCase):
    def test_save_screenshot_returns_none_when_page_closed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = save_screenshot(
                _FakePage(closed=True),
                Path(temp_dir),
                "error",
            )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
