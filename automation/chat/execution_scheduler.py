from __future__ import annotations

from dataclasses import dataclass
import threading
import time


@dataclass
class SchedulerAcquireResult:
    acquired: bool
    queued: bool
    queue_position: int
    reason: str = ""


class ExecutionScheduler:
    """Global run scheduler with bounded queue and FIFO fairness."""

    def __init__(
        self,
        *,
        max_concurrent_runs: int,
        queue_size: int,
        wait_interval_seconds: float = 0.1,
    ) -> None:
        self._max_concurrent_runs = max(1, max_concurrent_runs)
        self._queue_size = max(1, queue_size)
        self._wait_interval_seconds = max(0.05, wait_interval_seconds)
        self._lock = threading.Lock()
        self._queued_run_ids: list[str] = []
        self._running_run_ids: set[str] = set()

    def acquire(
        self,
        *,
        run_id: str,
        cancel_event: threading.Event,
    ) -> SchedulerAcquireResult:
        with self._lock:
            if run_id in self._running_run_ids:
                return SchedulerAcquireResult(acquired=True, queued=False, queue_position=0)
            if run_id in self._queued_run_ids:
                # Duplicate acquire from the same run should not happen; keep safe.
                return SchedulerAcquireResult(
                    acquired=False,
                    queued=True,
                    queue_position=self._queued_run_ids.index(run_id) + 1,
                    reason="duplicate_acquire",
                )
            if len(self._running_run_ids) < self._max_concurrent_runs and not self._queued_run_ids:
                self._running_run_ids.add(run_id)
                return SchedulerAcquireResult(acquired=True, queued=False, queue_position=0)
            if len(self._queued_run_ids) >= self._queue_size:
                return SchedulerAcquireResult(
                    acquired=False,
                    queued=False,
                    queue_position=0,
                    reason="queue_full",
                )
            self._queued_run_ids.append(run_id)
            current_position = len(self._queued_run_ids)

        while True:
            if cancel_event.is_set():
                with self._lock:
                    if run_id in self._queued_run_ids:
                        self._queued_run_ids.remove(run_id)
                return SchedulerAcquireResult(
                    acquired=False,
                    queued=True,
                    queue_position=current_position,
                    reason="canceled",
                )

            with self._lock:
                if (
                    self._queued_run_ids
                    and self._queued_run_ids[0] == run_id
                    and len(self._running_run_ids) < self._max_concurrent_runs
                ):
                    self._queued_run_ids.pop(0)
                    self._running_run_ids.add(run_id)
                    return SchedulerAcquireResult(acquired=True, queued=True, queue_position=0)
                if run_id in self._queued_run_ids:
                    current_position = self._queued_run_ids.index(run_id) + 1

            time.sleep(self._wait_interval_seconds)

    def release(self, *, run_id: str) -> None:
        with self._lock:
            self._running_run_ids.discard(run_id)
            if run_id in self._queued_run_ids:
                self._queued_run_ids.remove(run_id)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "running": len(self._running_run_ids),
                "queued": len(self._queued_run_ids),
                "maxConcurrentRuns": self._max_concurrent_runs,
                "queueSize": self._queue_size,
            }

