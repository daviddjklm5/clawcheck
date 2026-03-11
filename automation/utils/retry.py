from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_call(fn: Callable[[], T], retries: int, wait_sec: float) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt > retries:
                break
            time.sleep(wait_sec)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("retry_call failed without exception")
