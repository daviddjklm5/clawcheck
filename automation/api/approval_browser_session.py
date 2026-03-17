from __future__ import annotations

import atexit
from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Any

from playwright.sync_api import sync_playwright

_APPROVAL_SESSION_IDLE_TTL_SECONDS = 300.0
_DEFAULT_VIEWPORT = {"width": 1600, "height": 960}


@dataclass
class _ApprovalBrowserSession:
    playwright: Any
    browser: Any
    context: Any
    page: Any
    settings_signature: tuple[Any, ...]
    created_at_monotonic: float
    last_used_at_monotonic: float


class _ApprovalBrowserSessionPool:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: _ApprovalBrowserSession | None = None

    @staticmethod
    def _emit_event(event_callback, message: str, **extra: Any) -> None:
        if event_callback is None:
            return
        event_callback(message, **extra)

    @staticmethod
    def _build_settings_signature(settings, state_file: Path) -> tuple[Any, ...]:
        return (
            bool(settings.browser.headed),
            int(settings.browser.slow_mo_ms),
            bool(settings.browser.ignore_https_errors),
            int(settings.browser.timeout_ms),
            int(settings.browser.navigation_timeout_ms),
            str(state_file.resolve()),
        )

    @staticmethod
    def _is_browser_connected(browser: Any) -> bool:
        try:
            return bool(browser.is_connected())
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _is_page_closed(page: Any) -> bool:
        try:
            return bool(page.is_closed())
        except Exception:  # noqa: BLE001
            return True

    def _close_session_locked(self, reason: str, event_callback=None) -> None:
        session = self._session
        if session is None:
            return

        self._session = None
        now = time.monotonic()
        self._emit_event(
            event_callback,
            "browser_session_closed",
            reason=reason,
            sessionAgeMs=round((now - session.created_at_monotonic) * 1000, 1),
            sessionIdleMs=round((now - session.last_used_at_monotonic) * 1000, 1),
        )

        try:
            if not self._is_page_closed(session.page):
                session.page.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            session.context.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            session.browser.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            session.playwright.stop()
        except Exception:  # noqa: BLE001
            pass

    def _create_session_locked(self, settings, state_file: Path, event_callback=None) -> tuple[_ApprovalBrowserSession, dict[str, Any]]:
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=not settings.browser.headed,
            slow_mo=settings.browser.slow_mo_ms,
        )
        context_kwargs: dict[str, Any] = {
            "ignore_https_errors": settings.browser.ignore_https_errors,
            "viewport": dict(_DEFAULT_VIEWPORT),
            "accept_downloads": False,
        }
        if state_file.exists():
            context_kwargs["storage_state"] = str(state_file)

        context = browser.new_context(**context_kwargs)
        context.set_default_timeout(settings.browser.timeout_ms)
        context.set_default_navigation_timeout(settings.browser.navigation_timeout_ms)
        page = context.new_page()
        now = time.monotonic()
        session = _ApprovalBrowserSession(
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
            settings_signature=self._build_settings_signature(settings, state_file),
            created_at_monotonic=now,
            last_used_at_monotonic=now,
        )
        self._session = session
        self._emit_event(
            event_callback,
            "browser_session_created",
            stateFile=str(state_file),
            idleTtlSec=_APPROVAL_SESSION_IDLE_TTL_SECONDS,
            headed=bool(settings.browser.headed),
        )
        return session, {
            "reused": False,
            "pageRecreated": False,
            "sessionAgeMs": 0.0,
            "sessionIdleMs": 0.0,
        }

    def _ensure_session_locked(self, settings, state_file: Path, event_callback=None) -> tuple[_ApprovalBrowserSession, dict[str, Any]]:
        signature = self._build_settings_signature(settings, state_file)
        now = time.monotonic()
        session = self._session

        if session is not None:
            close_reason = ""
            if session.settings_signature != signature:
                close_reason = "settings_changed"
            elif not self._is_browser_connected(session.browser):
                close_reason = "browser_disconnected"
            else:
                idle_seconds = now - session.last_used_at_monotonic
                if idle_seconds > _APPROVAL_SESSION_IDLE_TTL_SECONDS:
                    close_reason = "idle_expired"
            if close_reason:
                self._close_session_locked(close_reason, event_callback=event_callback)
                session = None

        if session is None:
            return self._create_session_locked(settings, state_file, event_callback=event_callback)

        page_recreated = False
        if self._is_page_closed(session.page):
            try:
                session.page = session.context.new_page()
                page_recreated = True
            except Exception:  # noqa: BLE001
                self._close_session_locked("page_recreate_failed", event_callback=event_callback)
                return self._create_session_locked(settings, state_file, event_callback=event_callback)

        try:
            session.page.bring_to_front()
        except Exception:  # noqa: BLE001
            pass

        idle_ms = round((now - session.last_used_at_monotonic) * 1000, 1)
        age_ms = round((now - session.created_at_monotonic) * 1000, 1)
        session.last_used_at_monotonic = now
        self._emit_event(
            event_callback,
            "browser_session_reused",
            sessionAgeMs=age_ms,
            sessionIdleMs=idle_ms,
            pageRecreated=page_recreated,
        )
        return session, {
            "reused": True,
            "pageRecreated": page_recreated,
            "sessionAgeMs": age_ms,
            "sessionIdleMs": idle_ms,
        }

    def acquire(self, settings, state_file: Path, event_callback=None) -> tuple[_ApprovalBrowserSession, dict[str, Any]]:
        wait_started_at = time.monotonic()
        self._lock.acquire()
        wait_ms = round((time.monotonic() - wait_started_at) * 1000, 1)
        self._emit_event(
            event_callback,
            "browser_session_lock_acquired",
            waitMs=wait_ms,
            queued=wait_ms >= 1.0,
        )
        try:
            return self._ensure_session_locked(settings, state_file, event_callback=event_callback)
        except Exception:
            self._lock.release()
            raise

    def release(self) -> None:
        if self._lock.locked():
            self._lock.release()

    def close(self, reason: str = "manual") -> None:
        with self._lock:
            self._close_session_locked(reason)


_APPROVAL_BROWSER_SESSION_POOL = _ApprovalBrowserSessionPool()


def acquire_approval_browser_session(settings, state_file: Path, event_callback=None) -> tuple[Any, Any, Any, dict[str, Any]]:
    session, metadata = _APPROVAL_BROWSER_SESSION_POOL.acquire(
        settings=settings,
        state_file=state_file,
        event_callback=event_callback,
    )
    return session.browser, session.context, session.page, metadata


def release_approval_browser_session() -> None:
    _APPROVAL_BROWSER_SESSION_POOL.release()


def close_approval_browser_session(reason: str = "process_exit") -> None:
    _APPROVAL_BROWSER_SESSION_POOL.close(reason=reason)


atexit.register(close_approval_browser_session)
