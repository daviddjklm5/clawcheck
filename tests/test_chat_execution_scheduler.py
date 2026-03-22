from __future__ import annotations

import threading
import time

from automation.chat.execution_scheduler import ExecutionScheduler


def test_scheduler_rejects_when_queue_full() -> None:
    scheduler = ExecutionScheduler(max_concurrent_runs=1, queue_size=1, wait_interval_seconds=0.02)

    run1_cancel = threading.Event()
    run1_result = scheduler.acquire(run_id="run-1", cancel_event=run1_cancel)
    assert run1_result.acquired

    run2_cancel = threading.Event()
    run2_result_holder: dict[str, object] = {}

    def acquire_run2() -> None:
        run2_result_holder["result"] = scheduler.acquire(run_id="run-2", cancel_event=run2_cancel)

    run2_thread = threading.Thread(target=acquire_run2, daemon=True)
    run2_thread.start()
    time.sleep(0.05)

    run3_result = scheduler.acquire(run_id="run-3", cancel_event=threading.Event())
    assert run3_result.acquired is False
    assert run3_result.reason == "queue_full"

    scheduler.release(run_id="run-1")
    run2_thread.join(timeout=1.0)
    run2_result = run2_result_holder.get("result")
    assert run2_result is not None
    assert run2_result.acquired is True  # type: ignore[union-attr]
    scheduler.release(run_id="run-2")


def test_scheduler_returns_canceled_for_queued_run() -> None:
    scheduler = ExecutionScheduler(max_concurrent_runs=1, queue_size=1, wait_interval_seconds=0.02)
    scheduler.acquire(run_id="run-1", cancel_event=threading.Event())

    run2_cancel = threading.Event()
    run2_result_holder: dict[str, object] = {}

    def acquire_run2() -> None:
        run2_result_holder["result"] = scheduler.acquire(run_id="run-2", cancel_event=run2_cancel)

    run2_thread = threading.Thread(target=acquire_run2, daemon=True)
    run2_thread.start()
    time.sleep(0.05)
    run2_cancel.set()
    run2_thread.join(timeout=1.0)

    run2_result = run2_result_holder.get("result")
    assert run2_result is not None
    assert run2_result.acquired is False  # type: ignore[union-attr]
    assert run2_result.reason == "canceled"  # type: ignore[union-attr]
    scheduler.release(run_id="run-1")

