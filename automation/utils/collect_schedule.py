from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TASK_DAEMON_CONFIG_PATH = REPO_ROOT / "automation" / "config" / "windows_task_daemon.local.json"
DEFAULT_TASK_DAEMON_EXAMPLE_CONFIG_PATH = REPO_ROOT / "automation" / "config" / "windows_task_daemon.example.json"
DEFAULT_TASK_DAEMON_STATE_PATH = REPO_ROOT / "automation" / "state" / "windows_task_daemon_state.json"
DEFAULT_COLLECT_LOCK_PATH = REPO_ROOT / "automation" / "state" / "collect_task.lock"
DEFAULT_TASK_DAEMON_LOG_DIR = REPO_ROOT / "automation" / "logs" / "windows_task_daemon"

COLLECT_TASK_NAME = "collect"
COLLECT_EXECUTION_CONFLICT_EXIT_CODE = 3
COLLECT_TASK_DEFAULT_LIMIT = 100


class CollectExecutionLockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class CollectScheduleSummary:
    enabled: bool
    interval_minutes: int
    poll_seconds: int
    mode: str
    is_running: bool
    last_started_at: str
    last_finished_at: str
    next_planned_at: str
    last_exit_code: int | None
    last_message: str
    last_log_path: str
    config_file: str
    state_file: str
    lock_file: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "intervalMinutes": self.interval_minutes,
            "pollSeconds": self.poll_seconds,
            "mode": self.mode,
            "isRunning": self.is_running,
            "lastStartedAt": self.last_started_at,
            "lastFinishedAt": self.last_finished_at,
            "nextPlannedAt": self.next_planned_at,
            "lastExitCode": self.last_exit_code,
            "lastMessage": self.last_message,
            "lastLogPath": self.last_log_path,
            "configFile": self.config_file,
            "stateFile": self.state_file,
            "lockFile": self.lock_file,
        }


def resolve_repo_path(path_str: str | Path) -> Path:
    raw_path = Path(path_str)
    if raw_path.is_absolute():
        return raw_path
    return REPO_ROOT / raw_path


def to_repo_relative(raw_path: str | Path | None) -> str:
    if raw_path is None:
        return ""
    path = resolve_repo_path(raw_path)
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def load_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            Path(temp_path).unlink(missing_ok=True)
        except OSError:
            pass


def parse_state_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_datetime_text(value: str | datetime | None) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    parsed = parse_state_datetime(value) if isinstance(value, str) else None
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")


def now_iso_text(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _default_collect_task_payload() -> dict[str, Any]:
    return {
        "name": COLLECT_TASK_NAME,
        "enabled": False,
        "script": "automation/scripts/run_windows_task.ps1",
        "args": [
            "-Action",
            COLLECT_TASK_NAME,
            "-Headless",
            "-Limit",
            str(COLLECT_TASK_DEFAULT_LIMIT),
        ],
        "intervalMinutes": 15,
        "dailyTimes": [],
        "runOnStartup": False,
    }


def _ensure_collect_task_headless_args(args: list[str]) -> list[str]:
    normalized = [str(item) for item in args]
    filtered = [item for item in normalized if item not in {"-Headed", "-Headed:$true", "-Headed:$false"}]
    if "-Headless" not in filtered:
        filtered.append("-Headless")
    return filtered


def _ensure_collect_task_payload(raw_task: dict[str, Any]) -> dict[str, Any]:
    task = deepcopy(raw_task)
    task.setdefault("name", COLLECT_TASK_NAME)
    task.setdefault("enabled", False)
    task.setdefault("script", "automation/scripts/run_windows_task.ps1")
    task["args"] = _ensure_collect_task_headless_args([str(item) for item in task.get("args", [])])
    task["intervalMinutes"] = int(task.get("intervalMinutes", 15) or 0)
    task["dailyTimes"] = [str(item) for item in task.get("dailyTimes", [])]
    task["runOnStartup"] = bool(task.get("runOnStartup", False))
    return task


def _normalize_task_daemon_config(payload: dict[str, Any] | None) -> dict[str, Any]:
    normalized = deepcopy(payload) if isinstance(payload, dict) else {}
    normalized["pollSeconds"] = int(normalized.get("pollSeconds", 30) or 30)
    normalized["logDir"] = str(normalized.get("logDir", "automation/logs/windows_task_daemon"))

    tasks: list[dict[str, Any]] = []
    collect_task_found = False
    for raw_task in normalized.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        task = deepcopy(raw_task)
        task_name = str(task.get("name") or "").strip()
        if task_name == COLLECT_TASK_NAME:
            task = _ensure_collect_task_payload(task)
            collect_task_found = True
        tasks.append(task)

    if not collect_task_found:
        tasks.append(_default_collect_task_payload())

    normalized["tasks"] = tasks
    return normalized


def load_task_daemon_config(config_path: Path | None = None) -> dict[str, Any]:
    resolved_path = resolve_repo_path(config_path or DEFAULT_TASK_DAEMON_CONFIG_PATH)
    payload = load_json(resolved_path, fallback=None)
    if payload is None:
        example_payload = load_json(DEFAULT_TASK_DAEMON_EXAMPLE_CONFIG_PATH, fallback=None)
        return _normalize_task_daemon_config(example_payload)
    return _normalize_task_daemon_config(payload)


def save_task_daemon_config(payload: dict[str, Any], config_path: Path | None = None) -> None:
    resolved_path = resolve_repo_path(config_path or DEFAULT_TASK_DAEMON_CONFIG_PATH)
    save_json(resolved_path, _normalize_task_daemon_config(payload))


def load_task_daemon_state(state_path: Path | None = None) -> dict[str, Any]:
    resolved_path = resolve_repo_path(state_path or DEFAULT_TASK_DAEMON_STATE_PATH)
    payload = load_json(resolved_path, fallback={"tasks": {}})
    if not isinstance(payload, dict):
        payload = {"tasks": {}}
    payload.setdefault("tasks", {})
    return payload


def save_task_daemon_state(payload: dict[str, Any], state_path: Path | None = None) -> None:
    resolved_path = resolve_repo_path(state_path or DEFAULT_TASK_DAEMON_STATE_PATH)
    save_json(resolved_path, payload)


def get_collect_task_config(config_payload: dict[str, Any]) -> dict[str, Any]:
    normalized_payload = _normalize_task_daemon_config(config_payload)
    for task in normalized_payload.get("tasks", []):
        if str(task.get("name") or "").strip() == COLLECT_TASK_NAME:
            return task
    return _default_collect_task_payload()


def get_task_state(state_payload: dict[str, Any], task_name: str = COLLECT_TASK_NAME) -> dict[str, Any]:
    tasks = state_payload.setdefault("tasks", {})
    task_state = tasks.get(task_name)
    if not isinstance(task_state, dict):
        task_state = {}
        tasks[task_name] = task_state
    return task_state


def _resolve_collect_reference_time(task_state: dict[str, Any]) -> datetime | None:
    return parse_state_datetime(str(task_state.get("lastFinishedAt") or "")) or parse_state_datetime(
        str(task_state.get("scheduleAnchorAt") or "")
    )


def compute_collect_next_planned_at(
    *,
    enabled: bool,
    interval_minutes: int,
    task_state: dict[str, Any],
    now: datetime | None = None,
    is_running: bool = False,
) -> datetime | None:
    _ = now
    if not enabled or interval_minutes <= 0 or is_running:
        return None
    reference_at = _resolve_collect_reference_time(task_state)
    if reference_at is None:
        return None
    return reference_at + timedelta(minutes=interval_minutes)


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped.lstrip("-").isdigit():
            return int(stripped)
    return None


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        # On Windows, probing a missing PID via os.kill(pid, 0) commonly raises
        # OSError(winerror=87) instead of ProcessLookupError.
        if getattr(exc, "winerror", None) in {87, 1168}:
            return False
        return True
    return True


def get_collect_lock_info(lock_path: Path | None = None, *, cleanup_stale: bool = True) -> dict[str, Any] | None:
    resolved_path = resolve_repo_path(lock_path or DEFAULT_COLLECT_LOCK_PATH)
    if not resolved_path.exists():
        return None

    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        if cleanup_stale:
            resolved_path.unlink(missing_ok=True)
        return None

    if not isinstance(payload, dict):
        if cleanup_stale:
            resolved_path.unlink(missing_ok=True)
        return None

    pid = _coerce_int(payload.get("pid"))
    if pid is not None and not _is_process_running(pid):
        if cleanup_stale:
            resolved_path.unlink(missing_ok=True)
        return None

    payload = deepcopy(payload)
    payload["lockFile"] = to_repo_relative(resolved_path)
    return payload


def is_collect_execution_locked(lock_path: Path | None = None) -> bool:
    return get_collect_lock_info(lock_path) is not None


class CollectExecutionLock(AbstractContextManager["CollectExecutionLock"]):
    def __init__(self, lock_path: Path, payload: dict[str, Any]) -> None:
        self.lock_path = lock_path
        self.payload = payload
        self._acquired = False

    def acquire(self) -> CollectExecutionLock:
        attempts = 0
        while True:
            attempts += 1
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                if attempts == 1 and get_collect_lock_info(self.lock_path, cleanup_stale=True) is None:
                    continue
                lock_info = get_collect_lock_info(self.lock_path, cleanup_stale=False) or {}
                owner_pid = _coerce_int(lock_info.get("pid"))
                owner_text = f"（pid={owner_pid}）" if owner_pid is not None else ""
                raise CollectExecutionLockedError(f"当前已有采集任务在执行{owner_text}。") from exc

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(self.payload, fh, ensure_ascii=False, indent=2)
                    fh.flush()
                    os.fsync(fh.fileno())
            except Exception:
                self.lock_path.unlink(missing_ok=True)
                raise

            self._acquired = True
            return self

    def release(self) -> None:
        if self._acquired:
            self.lock_path.unlink(missing_ok=True)
            self._acquired = False

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
        return None


def acquire_collect_execution_lock(
    *,
    requested_document_no: str = "",
    requested_limit: int = COLLECT_TASK_DEFAULT_LIMIT,
    dry_run: bool = False,
    headed: bool = False,
    lock_path: Path | None = None,
) -> CollectExecutionLock:
    resolved_path = resolve_repo_path(lock_path or DEFAULT_COLLECT_LOCK_PATH)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "createdAt": now_iso_text(),
        "requestedDocumentNo": requested_document_no.strip(),
        "requestedLimit": int(requested_limit),
        "dryRun": bool(dry_run),
        "headed": bool(headed),
        "commandLine": " ".join(str(item) for item in sys.argv),
    }
    return CollectExecutionLock(resolved_path, payload).acquire()


def record_collect_task_started(
    *,
    log_path: str = "",
    state_path: Path | None = None,
    now: datetime | None = None,
) -> None:
    payload = load_task_daemon_state(state_path)
    task_state = get_task_state(payload, COLLECT_TASK_NAME)
    task_state["lastStartedAt"] = now_iso_text(now)
    if log_path:
        task_state["lastLogPath"] = to_repo_relative(log_path)
    task_state["lastMessage"] = "采集任务运行中"
    task_state.pop("scheduleAnchorAt", None)
    save_task_daemon_state(payload, state_path)


def record_collect_task_finished(
    *,
    exit_code: int,
    message: str,
    log_path: str = "",
    state_path: Path | None = None,
    now: datetime | None = None,
) -> None:
    payload = load_task_daemon_state(state_path)
    task_state = get_task_state(payload, COLLECT_TASK_NAME)
    task_state["lastFinishedAt"] = now_iso_text(now)
    task_state["lastExitCode"] = int(exit_code)
    task_state["lastMessage"] = str(message or "")
    if log_path:
        task_state["lastLogPath"] = to_repo_relative(log_path)
    task_state.pop("scheduleAnchorAt", None)
    save_task_daemon_state(payload, state_path)


def update_collect_schedule(
    *,
    enabled: bool,
    interval_minutes: int,
    config_path: Path | None = None,
    state_path: Path | None = None,
    now: datetime | None = None,
) -> CollectScheduleSummary:
    normalized_enabled = bool(enabled)
    normalized_interval = int(interval_minutes or 0)
    if normalized_enabled and normalized_interval <= 0:
        raise ValueError("启用定时采集时，采集频率必须为大于 0 的分钟数。")

    config_payload = load_task_daemon_config(config_path)
    collect_task = get_collect_task_config(config_payload)
    collect_task["enabled"] = normalized_enabled
    collect_task["intervalMinutes"] = normalized_interval
    collect_task["args"] = _ensure_collect_task_headless_args([str(item) for item in collect_task.get("args", [])])

    updated_tasks: list[dict[str, Any]] = []
    collect_updated = False
    for raw_task in config_payload.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        if str(raw_task.get("name") or "").strip() == COLLECT_TASK_NAME:
            updated_tasks.append(collect_task)
            collect_updated = True
        else:
            updated_tasks.append(deepcopy(raw_task))
    if not collect_updated:
        updated_tasks.append(collect_task)
    config_payload["tasks"] = updated_tasks
    save_task_daemon_config(config_payload, config_path)

    state_payload = load_task_daemon_state(state_path)
    task_state = get_task_state(state_payload, COLLECT_TASK_NAME)
    has_history = parse_state_datetime(str(task_state.get("lastStartedAt") or "")) is not None or parse_state_datetime(
        str(task_state.get("lastFinishedAt") or "")
    ) is not None
    if normalized_enabled:
        if not has_history:
            task_state["scheduleAnchorAt"] = now_iso_text(now)
    else:
        if not has_history:
            task_state.pop("scheduleAnchorAt", None)
    save_task_daemon_state(state_payload, state_path)

    return get_collect_schedule_summary(
        now=now,
        config_path=config_path,
        state_path=state_path,
    )


def get_collect_schedule_summary(
    *,
    now: datetime | None = None,
    config_path: Path | None = None,
    state_path: Path | None = None,
    lock_path: Path | None = None,
) -> CollectScheduleSummary:
    resolved_config_path = resolve_repo_path(config_path or DEFAULT_TASK_DAEMON_CONFIG_PATH)
    resolved_state_path = resolve_repo_path(state_path or DEFAULT_TASK_DAEMON_STATE_PATH)
    resolved_lock_path = resolve_repo_path(lock_path or DEFAULT_COLLECT_LOCK_PATH)
    config_payload = load_task_daemon_config(resolved_config_path)
    state_payload = load_task_daemon_state(resolved_state_path)
    collect_task = get_collect_task_config(config_payload)
    task_state = get_task_state(state_payload, COLLECT_TASK_NAME)
    lock_info = get_collect_lock_info(resolved_lock_path)
    next_planned_at = compute_collect_next_planned_at(
        enabled=bool(collect_task.get("enabled")),
        interval_minutes=int(collect_task.get("intervalMinutes") or 0),
        task_state=task_state,
        now=now,
        is_running=lock_info is not None,
    )
    last_exit_code = _coerce_int(task_state.get("lastExitCode"))

    return CollectScheduleSummary(
        enabled=bool(collect_task.get("enabled")),
        interval_minutes=int(collect_task.get("intervalMinutes") or 0),
        poll_seconds=int(config_payload.get("pollSeconds", 30) or 30),
        mode="headless",
        is_running=lock_info is not None,
        last_started_at=format_datetime_text(str(task_state.get("lastStartedAt") or "")),
        last_finished_at=format_datetime_text(str(task_state.get("lastFinishedAt") or "")),
        next_planned_at=format_datetime_text(next_planned_at),
        last_exit_code=last_exit_code,
        last_message=str(task_state.get("lastMessage") or ("采集任务运行中" if lock_info is not None else "")),
        last_log_path=to_repo_relative(str(task_state.get("lastLogPath") or "")),
        config_file=to_repo_relative(resolved_config_path),
        state_file=to_repo_relative(resolved_state_path),
        lock_file=to_repo_relative(resolved_lock_path),
    )
