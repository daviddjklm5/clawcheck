from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any
from uuid import uuid4

from automation.api.config_summary import REPO_ROOT, _load_runtime_settings

_LOG_FILE_PATTERN = re.compile(r"Log file:\s*(.+)")


def _resolve_runtime_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _to_repo_relative(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _load_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _extract_log_file(output_text: str) -> str:
    matches = _LOG_FILE_PATTERN.findall(output_text)
    if not matches:
        return ""
    return _to_repo_relative(Path(matches[-1].strip()))


def run_process_todo_sync_now(*, dry_run: bool = False, headed: bool | None = None) -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    resolved_headed = settings.browser.headed if headed is None else bool(headed)
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = uuid4().hex[:12]
    dump_path = logs_dir / f"todo_sync_{timestamp_slug}_{task_id}.json"

    command = [
        sys.executable,
        "automation/scripts/run.py",
        "sync-todo-status",
        "--headed" if resolved_headed else "--headless",
        "--dump-json",
        str(dump_path),
    ]
    if dry_run:
        command.append("--dry-run")

    process = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    combined_output = "\n".join(part for part in [process.stdout, process.stderr] if part).strip()
    output_tail = combined_output[-4000:] if combined_output else ""
    payload = _load_json_file(dump_path)
    if not isinstance(payload, dict):
        payload = {}

    result = {
        "taskId": task_id,
        "status": "succeeded" if process.returncode == 0 else "failed",
        "dryRun": bool(dry_run),
        "startedAt": str(payload.get("started_at") or ""),
        "finishedAt": str(payload.get("finished_at") or ""),
        "projectDocumentCount": int(payload.get("project_document_count") or 0),
        "ehrTodoCount": int(payload.get("ehr_todo_count") or 0),
        "pendingCount": int(payload.get("pending_count") or 0),
        "processedCount": int(payload.get("processed_count") or 0),
        "changedCount": int(payload.get("changed_count") or 0),
        "unchangedCount": int(payload.get("unchanged_count") or 0),
        "extraEhrTodoCount": int(payload.get("extra_ehr_todo_count") or 0),
        "message": str(payload.get("message") or output_tail or "待办状态同步执行失败"),
        "dumpFile": _to_repo_relative(dump_path),
        "logFile": _extract_log_file(combined_output),
        "outputTail": output_tail,
    }
    if process.returncode != 0:
        raise RuntimeError(result["message"])
    return result
