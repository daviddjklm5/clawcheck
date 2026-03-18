from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from automation.api import approval_browser_session as session_module


class _FakePage:
    def __init__(self) -> None:
        self.closed = False
        self.bring_to_front_calls = 0
        self.close_calls = 0

    def is_closed(self) -> bool:
        return self.closed

    def close(self) -> None:
        self.closed = True
        self.close_calls += 1

    def bring_to_front(self) -> None:
        self.bring_to_front_calls += 1


class _FakeContext:
    def __init__(self) -> None:
        self.closed = False
        self.close_calls = 0
        self.default_timeout = 0
        self.default_navigation_timeout = 0
        self.new_pages: list[_FakePage] = []

    def set_default_timeout(self, timeout_ms: int) -> None:
        self.default_timeout = timeout_ms

    def set_default_navigation_timeout(self, timeout_ms: int) -> None:
        self.default_navigation_timeout = timeout_ms

    def new_page(self) -> _FakePage:
        page = _FakePage()
        self.new_pages.append(page)
        return page

    def close(self) -> None:
        self.closed = True
        self.close_calls += 1


class _FakeBrowser:
    def __init__(self) -> None:
        self.connected = True
        self.close_calls = 0
        self.contexts: list[_FakeContext] = []

    def is_connected(self) -> bool:
        return self.connected

    def new_context(self, **kwargs) -> _FakeContext:
        _ = kwargs
        context = _FakeContext()
        self.contexts.append(context)
        return context

    def close(self) -> None:
        self.connected = False
        self.close_calls += 1


class _FakeChromium:
    def __init__(self, registry: dict[str, list[object]]) -> None:
        self.registry = registry

    def launch(self, *, headless: bool, slow_mo: int) -> _FakeBrowser:
        _ = (headless, slow_mo)
        browser = _FakeBrowser()
        self.registry["browsers"].append(browser)
        return browser


class _FakePlaywright:
    def __init__(self, registry: dict[str, list[object]]) -> None:
        self.registry = registry
        self.chromium = _FakeChromium(registry)
        self.stop_calls = 0

    def stop(self) -> None:
        self.stop_calls += 1


class _FakePlaywrightStarter:
    def __init__(self, registry: dict[str, list[object]]) -> None:
        self.registry = registry

    def start(self) -> _FakePlaywright:
        playwright = _FakePlaywright(self.registry)
        self.registry["playwrights"].append(playwright)
        return playwright


class _FakeSyncPlaywrightFactory:
    def __init__(self, registry: dict[str, list[object]]) -> None:
        self.registry = registry

    def __call__(self) -> _FakePlaywrightStarter:
        return _FakePlaywrightStarter(self.registry)


class ApprovalBrowserSessionPoolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            browser=SimpleNamespace(
                headed=False,
                slow_mo_ms=0,
                ignore_https_errors=True,
                timeout_ms=2000,
                navigation_timeout_ms=2000,
            )
        )

    def test_reuses_session_on_same_thread(self) -> None:
        registry: dict[str, list[object]] = {"playwrights": [], "browsers": []}
        sync_playwright_factory = _FakeSyncPlaywrightFactory(registry)
        events: list[dict[str, object]] = []

        def collect_event(message: str, **extra) -> None:
            events.append({"message": message, **extra})

        pool = session_module._ApprovalBrowserSessionPool()
        with TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "auth.json"
            with patch("automation.api.approval_browser_session.sync_playwright", new=sync_playwright_factory):
                session_a, meta_a = pool.acquire(self.settings, state_file, event_callback=collect_event)
                pool.release()
                session_b, meta_b = pool.acquire(self.settings, state_file, event_callback=collect_event)
                pool.release()
                pool.close(reason="test_cleanup")

        self.assertIs(session_a, session_b)
        self.assertFalse(meta_a["reused"])
        self.assertTrue(meta_b["reused"])
        self.assertEqual(len(registry["playwrights"]), 1)
        self.assertEqual(
            [event["message"] for event in events].count("browser_session_reused"),
            1,
        )

    def test_recreates_session_when_thread_changes(self) -> None:
        registry: dict[str, list[object]] = {"playwrights": [], "browsers": []}
        sync_playwright_factory = _FakeSyncPlaywrightFactory(registry)
        events: list[dict[str, object]] = []

        def collect_event(message: str, **extra) -> None:
            events.append({"message": message, **extra})

        thread_a = SimpleNamespace(name="worker-a")
        thread_b = SimpleNamespace(name="worker-b")
        current_thread_state = {"thread": thread_a, "ident": 101}

        def fake_current_thread():
            return current_thread_state["thread"]

        def fake_get_ident():
            return current_thread_state["ident"]

        pool = session_module._ApprovalBrowserSessionPool()
        with TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "auth.json"
            with (
                patch("automation.api.approval_browser_session.sync_playwright", new=sync_playwright_factory),
                patch("automation.api.approval_browser_session.threading.current_thread", new=fake_current_thread),
                patch("automation.api.approval_browser_session.threading.get_ident", new=fake_get_ident),
            ):
                session_a, meta_a = pool.acquire(self.settings, state_file, event_callback=collect_event)
                pool.release()
                current_thread_state["thread"] = thread_b
                current_thread_state["ident"] = 202
                session_b, meta_b = pool.acquire(self.settings, state_file, event_callback=collect_event)
                pool.release()
                pool.close(reason="test_cleanup")

        self.assertIsNot(session_a, session_b)
        self.assertFalse(meta_a["reused"])
        self.assertFalse(meta_b["reused"])
        self.assertEqual(len(registry["playwrights"]), 2)
        self.assertTrue(
            any(
                event["message"] == "browser_session_closed"
                and event.get("reason") == "owner_thread_changed"
                for event in events
            )
        )

    def test_release_with_close_session_closes_browser_resources(self) -> None:
        registry: dict[str, list[object]] = {"playwrights": [], "browsers": []}
        sync_playwright_factory = _FakeSyncPlaywrightFactory(registry)
        pool = session_module._ApprovalBrowserSessionPool()

        with TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "auth.json"
            with patch("automation.api.approval_browser_session.sync_playwright", new=sync_playwright_factory):
                session, _ = pool.acquire(self.settings, state_file)
                page = session.page
                context = session.context
                browser = session.browser
                playwright = session.playwright
                pool.release(close_session=True, close_reason="request_finished")

        self.assertTrue(page.closed)
        self.assertTrue(context.closed)
        self.assertFalse(browser.connected)
        self.assertEqual(playwright.stop_calls, 1)


if __name__ == "__main__":
    unittest.main()
