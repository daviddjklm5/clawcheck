#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from automation.utils.collect_schedule import (
    COLLECT_TASK_NAME,
    DEFAULT_COLLECT_LOCK_PATH,
    DEFAULT_TASK_DAEMON_CONFIG_PATH,
    DEFAULT_TASK_DAEMON_EXAMPLE_CONFIG_PATH,
    DEFAULT_TASK_DAEMON_LOG_DIR,
    DEFAULT_TASK_DAEMON_STATE_PATH,
    is_collect_execution_locked,
    load_json as _load_json,
    reconcile_incomplete_collect_state,
    save_json as _save_json,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = DEFAULT_TASK_DAEMON_CONFIG_PATH
DEFAULT_EXAMPLE_CONFIG_PATH = DEFAULT_TASK_DAEMON_EXAMPLE_CONFIG_PATH
DEFAULT_STATE_PATH = DEFAULT_TASK_DAEMON_STATE_PATH
DEFAULT_LOG_DIR = DEFAULT_TASK_DAEMON_LOG_DIR


@dataclass(frozen=True)
class TaskConfig:
    name: str
    script: str
    args: list[str]
    enabled: bool
    interval_minutes: int
    daily_times: list[str]
    run_on_startup: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="User-mode task daemon for Windows native clawcheck tasks")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to local daemon config JSON")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_PATH), help="Path to daemon state JSON")
    parser.add_argument("--once", action="store_true", help="Run one scheduling cycle and exit")
    return parser.parse_args()


def resolve_repo_path(path_str: str) -> Path:
    raw_path = Path(path_str)
    if raw_path.is_absolute():
        return raw_path
    return REPO_ROOT / raw_path


def parse_time_token(token: str) -> tuple[int, int]:
    hour_str, minute_str = token.split(":", 1)
    hour = int(hour_str)
    minute = int(minute_str)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid daily time token: {token}")
    return hour, minute


def load_json(path: Path, fallback: Any) -> Any:
    return _load_json(path, fallback)


def save_json(path: Path, payload: Any) -> None:
    _save_json(path, payload)


def load_config(config_path: Path) -> tuple[int, Path, list[TaskConfig]]:
    config_payload = load_json(config_path, fallback=None)
    if config_payload is None:
        raise FileNotFoundError(
            f"Daemon config not found: {config_path}. Copy {DEFAULT_EXAMPLE_CONFIG_PATH.name} to create a local config."
        )

    poll_seconds = int(config_payload.get("pollSeconds", 30))
    log_dir_value = config_payload.get("logDir", "automation/logs/windows_task_daemon")
    log_dir = resolve_repo_path(log_dir_value)

    tasks: list[TaskConfig] = []
    for raw_task in config_payload.get("tasks", []):
        tasks.append(
            TaskConfig(
                name=str(raw_task["name"]),
                script=str(raw_task["script"]),
                args=[str(item) for item in raw_task.get("args", [])],
                enabled=bool(raw_task.get("enabled", False)),
                interval_minutes=int(raw_task.get("intervalMinutes", 0) or 0),
                daily_times=[str(item) for item in raw_task.get("dailyTimes", [])],
                run_on_startup=bool(raw_task.get("runOnStartup", False)),
            )
        )
    return poll_seconds, log_dir, tasks


def get_task_state(state_payload: dict[str, Any], task_name: str) -> dict[str, Any]:
    tasks = state_payload.setdefault("tasks", {})
    task_state = tasks.get(task_name)
    if not isinstance(task_state, dict):
        task_state = {}
        tasks[task_name] = task_state
    return task_state


def parse_state_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def bootstrap_interval_state(task: TaskConfig, task_state: dict[str, Any], now: datetime) -> bool:
    if not task.enabled:
        return False
    if task.interval_minutes <= 0 or task.run_on_startup:
        return False
    if task.name == COLLECT_TASK_NAME:
        if task_state.get("lastFinishedAt") or task_state.get("lastStartedAt") or task_state.get("scheduleAnchorAt"):
            return False
        task_state["scheduleAnchorAt"] = now.isoformat(timespec="seconds")
        return True
    if task_state.get("lastStartedAt"):
        return False
    task_state["lastStartedAt"] = now.isoformat(timespec="seconds")
    return True


def get_due_daily_key(task_state: dict[str, Any], now: datetime, daily_times: list[str]) -> str | None:
    current_token = now.strftime("%H:%M")
    if current_token not in daily_times:
        return None
    trigger_key = now.strftime("%Y-%m-%dT%H:%M")
    if task_state.get("lastDailyTriggerKey") == trigger_key:
        return None
    return trigger_key


def is_task_due(task: TaskConfig, task_state: dict[str, Any], now: datetime) -> tuple[bool, str | None]:
    if not task.enabled:
        return False, None

    if task.daily_times:
        daily_key = get_due_daily_key(task_state, now, task.daily_times)
        if daily_key:
            return True, daily_key

    if task.interval_minutes > 0:
        if task.name == COLLECT_TASK_NAME:
            reference_at = parse_state_datetime(task_state.get("lastFinishedAt")) or parse_state_datetime(
                task_state.get("scheduleAnchorAt")
            )
            if reference_at is None:
                if task.run_on_startup:
                    return True, None
                return False, None
            if now >= reference_at + timedelta(minutes=task.interval_minutes):
                return True, None
        else:
            if not task_state.get("lastStartedAt"):
                if task.run_on_startup:
                    return True, None
                return False, None

            last_started_at = parse_state_datetime(task_state.get("lastStartedAt"))
            if last_started_at is None:
                return False, None

            if now >= last_started_at + timedelta(minutes=task.interval_minutes):
                return True, None

    return False, None


def _should_skip_collect_due_to_running_lock(task: TaskConfig) -> bool:
    if task.name != COLLECT_TASK_NAME:
        return False
    return is_collect_execution_locked(DEFAULT_COLLECT_LOCK_PATH)


def is_collect_task_name(task_name: str) -> bool:
    return task_name == COLLECT_TASK_NAME


def _record_non_collect_start(task_name: str, task_state: dict[str, Any], now: datetime, log_path: Path) -> None:
    if is_collect_task_name(task_name):
        return
    task_state["lastStartedAt"] = now.isoformat(timespec="seconds")
    task_state["lastLogPath"] = str(log_path)


def _record_non_collect_completion(task_name: str, task_state: dict[str, Any], now_text: str, return_code: int) -> None:
    if is_collect_task_name(task_name):
        return
    task_state["lastFinishedAt"] = now_text
    task_state["lastExitCode"] = int(return_code)


def process_completed_tasks(
    running_tasks: dict[str, subprocess.Popen[str]],
    state_payload: dict[str, Any],
    log_dir: Path,
) -> bool:
    completed_names: list[str] = []
    now = datetime.now()
    now_text = now.isoformat(timespec="seconds")
    changed = False

    for task_name, process in running_tasks.items():
        return_code = process.poll()
        if return_code is None:
            continue
        task_state = get_task_state(state_payload, task_name)
        _record_non_collect_completion(task_name, task_state, now_text, return_code)
        if is_collect_task_name(task_name):
            reconcile_incomplete_collect_state(task_state, is_running=False, exit_code=return_code, now=now)
        close_process_log(process)
        completed_names.append(task_name)
        changed = True

    for task_name in completed_names:
        running_tasks.pop(task_name, None)
    return changed


def run_cycle(
    tasks: list[TaskConfig],
    state_payload: dict[str, Any],
    running_tasks: dict[str, subprocess.Popen[str]],
    log_dir: Path,
    now: datetime,
) -> bool:
    changed = False
    if process_completed_tasks(running_tasks, state_payload, log_dir):
        changed = True

    for task in tasks:
        task_state = get_task_state(state_payload, task.name)
        if bootstrap_interval_state(task, task_state, now):
            changed = True

        if task.name in running_tasks:
            continue

        due, daily_key = is_task_due(task, task_state, now)
        if not due:
            continue
        if _should_skip_collect_due_to_running_lock(task):
            continue

        process, log_path = start_task(task, log_dir=log_dir, now=now)
        running_tasks[task.name] = process
        _record_non_collect_start(task.name, task_state, now, log_path)
        if daily_key:
            task_state["lastDailyTriggerKey"] = daily_key
        changed = True

    return changed


def main() -> int:
    args = parse_args()
    config_path = resolve_repo_path(args.config)
    state_path = resolve_repo_path(args.state_file)

    if not config_path.exists() and DEFAULT_EXAMPLE_CONFIG_PATH.exists():
        print(
            f"Daemon config is missing: {config_path}. "
            f"Copy {DEFAULT_EXAMPLE_CONFIG_PATH} to {config_path} and enable tasks explicitly.",
            file=sys.stderr,
        )
        return 1

    state_payload = load_json(state_path, fallback={"tasks": {}})
    running_tasks: dict[str, subprocess.Popen[str]] = {}
    poll_seconds = 30
    log_dir = DEFAULT_LOG_DIR
    tasks: list[TaskConfig] = []

    while True:
        try:
            poll_seconds, log_dir, tasks = load_config(config_path)
        except Exception as exc:  # noqa: BLE001
            print(f"Failed to load daemon config: {exc}", file=sys.stderr)

        now = datetime.now()
        changed = run_cycle(tasks=tasks, state_payload=state_payload, running_tasks=running_tasks, log_dir=log_dir, now=now)
        if changed:
            save_json(state_path, state_payload)

        if args.once:
            process_completed_tasks(running_tasks, state_payload, log_dir)
            save_json(state_path, state_payload)
            return 0

        time.sleep(max(5, poll_seconds))


def start_task(task: TaskConfig, log_dir: Path, now: datetime) -> tuple[subprocess.Popen[str], Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{task.name}_{now.strftime('%Y%m%d_%H%M%S')}.log"
    script_path = resolve_repo_path(task.script)
    command = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *task.args,
    ]
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(REPO_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    setattr(process, "_clawcheck_log_file", log_file)
    return process, log_path


def close_process_log(process: subprocess.Popen[str]) -> None:
    log_file = getattr(process, "_clawcheck_log_file", None)
    if log_file is not None:
        log_file.close()


if __name__ == "__main__":
    raise SystemExit(main())
