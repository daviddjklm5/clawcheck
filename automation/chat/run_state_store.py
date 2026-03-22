from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Any


TERMINAL_RUN_STATUSES = {"succeeded", "failed", "timeout", "canceled", "interrupted", "tool_failed"}
NON_TERMINAL_RUN_STATUSES = {"queued", "running", "cancel_requested"}


@dataclass
class RunStateRecord:
    run_id: str
    session_id: str
    status: str
    backend_mode: str
    worker_id: str
    started_at: str
    updated_at: str
    finished_at: str
    error_code: str
    error_message: str


class RunStateStore:
    """
    Persist run lifecycle when DB support exists.
    Falls back to in-memory storage for tests or non-DB stores.
    """

    def __init__(self, store: Any) -> None:
        self._store = store
        self._lock = threading.Lock()
        self._memory: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _now_text() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _upsert_memory(
        self,
        *,
        run_id: str,
        session_id: str,
        status: str,
        backend_mode: str,
        worker_id: str = "",
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        now_text = self._now_text()
        with self._lock:
            existing = self._memory.get(run_id) or {
                "runId": run_id,
                "sessionId": session_id,
                "status": status,
                "backendMode": backend_mode,
                "workerId": worker_id,
                "startedAt": "",
                "updatedAt": now_text,
                "finishedAt": "",
                "errorCode": "",
                "errorMessage": "",
            }
            existing["sessionId"] = session_id
            existing["status"] = status
            existing["backendMode"] = backend_mode
            if worker_id:
                existing["workerId"] = worker_id
            existing["updatedAt"] = now_text
            if status == "running" and not existing.get("startedAt"):
                existing["startedAt"] = now_text
            if status in TERMINAL_RUN_STATUSES:
                existing["finishedAt"] = now_text
            if error_code:
                existing["errorCode"] = error_code
            if error_message:
                existing["errorMessage"] = error_message
            self._memory[run_id] = existing

    def upsert(
        self,
        *,
        run_id: str,
        session_id: str,
        status: str,
        backend_mode: str,
        worker_id: str = "",
        error_code: str = "",
        error_message: str = "",
    ) -> None:
        if hasattr(self._store, "upsert_run_state"):
            self._store.upsert_run_state(
                run_id=run_id,
                session_id=session_id,
                status=status,
                backend_mode=backend_mode,
                worker_id=worker_id,
                error_code=error_code,
                error_message=error_message,
            )
            return
        self._upsert_memory(
            run_id=run_id,
            session_id=session_id,
            status=status,
            backend_mode=backend_mode,
            worker_id=worker_id,
            error_code=error_code,
            error_message=error_message,
        )

    def mark_inflight_as_interrupted(self) -> list[RunStateRecord]:
        if hasattr(self._store, "mark_non_terminal_run_states_interrupted"):
            rows = self._store.mark_non_terminal_run_states_interrupted(
                statuses=sorted(NON_TERMINAL_RUN_STATUSES),
                error_code="interrupted_by_restart",
                error_message="API restarted during run.",
            )
            return [
                RunStateRecord(
                    run_id=str(row.get("runId") or ""),
                    session_id=str(row.get("sessionId") or ""),
                    status=str(row.get("status") or "interrupted"),
                    backend_mode=str(row.get("backendMode") or ""),
                    worker_id=str(row.get("workerId") or ""),
                    started_at=str(row.get("startedAt") or ""),
                    updated_at=str(row.get("updatedAt") or ""),
                    finished_at=str(row.get("finishedAt") or ""),
                    error_code=str(row.get("errorCode") or ""),
                    error_message=str(row.get("errorMessage") or ""),
                )
                for row in rows
                if row.get("runId")
            ]

        interrupted: list[RunStateRecord] = []
        now_text = self._now_text()
        with self._lock:
            for run in self._memory.values():
                if str(run.get("status") or "") not in NON_TERMINAL_RUN_STATUSES:
                    continue
                run["status"] = "interrupted"
                run["updatedAt"] = now_text
                run["finishedAt"] = now_text
                run["errorCode"] = "interrupted_by_restart"
                run["errorMessage"] = "API restarted during run."
                interrupted.append(
                    RunStateRecord(
                        run_id=str(run.get("runId") or ""),
                        session_id=str(run.get("sessionId") or ""),
                        status="interrupted",
                        backend_mode=str(run.get("backendMode") or ""),
                        worker_id=str(run.get("workerId") or ""),
                        started_at=str(run.get("startedAt") or ""),
                        updated_at=now_text,
                        finished_at=now_text,
                        error_code="interrupted_by_restart",
                        error_message="API restarted during run.",
                    )
                )
        return interrupted

