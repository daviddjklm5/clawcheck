from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from automation.utils.retry import retry_call

T = TypeVar("T")


def ensure_login_with_retry(
    *,
    login_page: Any,
    username: str,
    password: str,
    require_manual_captcha: bool,
    retries: int,
    wait_sec: float,
    bound_pages: list[object] | None = None,
    retry_fn: Callable[[Callable[[], T], int, float], T] = retry_call,
    event_callback: Callable[..., None] | None = None,
) -> Any:
    managed_pages = bound_pages or [login_page]

    def emit_event(message: str, **extra: Any) -> None:
        if event_callback is None:
            return
        event_callback(message, **extra)

    def refresh_closed_page() -> None:
        page = login_page.page
        try:
            is_closed = bool(page.is_closed())
        except Exception:  # noqa: BLE001
            is_closed = False
        if not is_closed:
            return

        new_page = page.context.new_page()
        for candidate in managed_pages:
            if hasattr(candidate, "set_page"):
                candidate.set_page(new_page)
        login_page.logger.warning(
            "Detected closed Playwright page during login retry; created a fresh page in the same context"
        )
        emit_event("login_retry_page_recreated")

    total_attempts = max(retries, 0) + 1
    attempt = 0

    def do_login() -> Any:
        nonlocal attempt
        attempt += 1
        try:
            emit_event("login_attempt_started", attempt=attempt, totalAttempts=total_attempts)
            login_page.login(
                username=username,
                password=password,
                require_manual_captcha=require_manual_captcha,
            )
            emit_event("login_attempt_succeeded", attempt=attempt, totalAttempts=total_attempts)
            return login_page.page
        except Exception as exc:  # noqa: BLE001
            emit_event("login_attempt_failed", attempt=attempt, totalAttempts=total_attempts, error=str(exc))
            refresh_closed_page()
            raise

    return retry_fn(do_login, retries=max(retries, 0), wait_sec=max(wait_sec, 0.0))
