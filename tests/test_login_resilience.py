from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from automation.pages.login_page import LoginPage
from automation.scripts.run import ensure_login
from automation.utils.login_resilience import ensure_login_with_retry
from automation.utils.playwright_helpers import save_screenshot
from automation.utils.retry import retry_call


class _FakeLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def info(self, message: str, *args) -> None:
        self.infos.append(message % args if args else message)

    def warning(self, message: str, *args) -> None:
        self.warnings.append(message % args if args else message)


class _FakePage:
    def __init__(self, *, closed: bool = False, context=None, url: str = "about:blank", goto_results: list[object] | None = None) -> None:
        self._closed = closed
        self.context = context
        self.url = url
        self.goto_calls: list[tuple[str, str]] = []
        self.goto_results = list(goto_results or [])
        self.wait_for_timeout_calls: list[int] = []

    def is_closed(self) -> bool:
        return self._closed

    def close_for_test(self) -> None:
        self._closed = True

    def goto(self, url: str, *, wait_until: str) -> None:
        self.goto_calls.append((url, wait_until))
        if self.goto_results:
            result = self.goto_results.pop(0)
            if isinstance(result, Exception):
                raise result
            self.url = str(result)
            return
        self.url = url

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_for_timeout_calls.append(timeout_ms)

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


class LoginPageNavigationResilienceTest(unittest.TestCase):
    def test_open_retries_when_navigation_lands_on_browser_error_page(self) -> None:
        logger = _FakeLogger()
        page = _FakePage(
            url="about:blank",
            goto_results=[
                "chrome-error://chromewebdata/",
                "https://siam.vankeservice.com/login",
            ],
        )
        login_page = LoginPage(
            home_url="https://hr.onewo.com/ierp/?formId=home_page",
            page=page,
            selectors={},
            logger=logger,
            timeout_ms=1000,
        )

        login_page.open()

        self.assertEqual(
            page.goto_calls,
            [
                ("https://hr.onewo.com/ierp/?formId=home_page", "domcontentloaded"),
                ("https://thr.onewo.com:8443/ierp/?formId=home_page", "domcontentloaded"),
            ],
        )
        self.assertEqual(page.wait_for_timeout_calls, [LoginPage._OPEN_RETRY_WAIT_MS])
        self.assertEqual(page.url, "https://siam.vankeservice.com/login")
        self.assertTrue(any("Chromium error page" in message for message in logger.warnings))
        self.assertTrue(any("recovered on attempt 2" in message for message in logger.infos))

    def test_open_raises_clear_error_after_navigation_retries_are_exhausted(self) -> None:
        logger = _FakeLogger()
        page = _FakePage(
            url="about:blank",
            goto_results=["chrome-error://chromewebdata/"] * LoginPage._OPEN_RETRY_COUNT,
        )
        login_page = LoginPage(
            home_url="https://hr.onewo.com/ierp/?formId=home_page",
            page=page,
            selectors={},
            logger=logger,
            timeout_ms=1000,
        )

        with self.assertRaises(RuntimeError) as ctx:
            login_page.open()

        self.assertIn("Unable to open login entry page after navigation retries", str(ctx.exception))
        self.assertIn("Target URL: https://hr.onewo.com/ierp/?formId=home_page", str(ctx.exception))
        self.assertIn("attempted URLs:", str(ctx.exception))
        self.assertIn("current URL: chrome-error://chromewebdata/", str(ctx.exception))
        self.assertEqual(len(page.goto_calls), LoginPage._OPEN_RETRY_COUNT)
        self.assertEqual(page.wait_for_timeout_calls, [LoginPage._OPEN_RETRY_WAIT_MS] * (LoginPage._OPEN_RETRY_COUNT - 1))
        self.assertEqual(len(logger.warnings), LoginPage._OPEN_RETRY_COUNT)


class SharedLoginResilienceHelperTest(unittest.TestCase):
    def test_ensure_login_with_retry_recreates_closed_page(self) -> None:
        context = _FakeContext()
        initial_page = _FakePage(context=context)
        login_page = _FakeLoginPage(initial_page)
        home_page = _FakePageHolder(initial_page)
        events: list[str] = []

        final_page = ensure_login_with_retry(
            login_page=login_page,
            username="tester",
            password="tester",
            require_manual_captcha=False,
            retries=1,
            wait_sec=0,
            bound_pages=[login_page, home_page],
            event_callback=lambda message, **_: events.append(message),
        )

        self.assertEqual(login_page.login_calls, 2)
        self.assertIs(final_page, context.new_pages[0])
        self.assertIs(login_page.page, final_page)
        self.assertIs(home_page.page, final_page)
        self.assertIn("login_attempt_failed", events)
        self.assertIn("login_retry_page_recreated", events)
        self.assertIn("login_attempt_succeeded", events)


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
