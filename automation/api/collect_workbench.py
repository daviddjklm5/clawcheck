from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Any
from uuid import uuid4

from automation.api.config_summary import REPO_ROOT, _load_runtime_settings
from automation.db.postgres import PostgresPermissionStore

_LOG_FILE_PATTERN = re.compile(r"Log file:\s*(.+)")
_SUMMARY_PREFIX = "collect_summary_"
_TASK_LOCK = threading.Lock()
_TASK_STATE_BY_ID: dict[str, dict[str, Any]] = {}


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


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _task_to_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task["taskId"],
        "taskId": task["taskId"],
        "status": task["status"],
        "requestedAt": task["requestedAt"],
        "startedAt": task.get("startedAt", ""),
        "finishedAt": task.get("finishedAt", ""),
        "requestedDocumentNo": task.get("requestedDocumentNo", ""),
        "requestedLimit": int(task.get("requestedLimit") or 0),
        "dryRun": bool(task.get("dryRun")),
        "requestedCount": int(task.get("requestedCount") or 0),
        "successCount": int(task.get("successCount") or 0),
        "skippedCount": int(task.get("skippedCount") or 0),
        "failedCount": int(task.get("failedCount") or 0),
        "message": str(task.get("message") or ""),
        "dumpFile": str(task.get("dumpFile") or ""),
        "skippedDumpFile": str(task.get("skippedDumpFile") or ""),
        "failedDumpFile": str(task.get("failedDumpFile") or ""),
        "summaryFile": str(task.get("summaryFile") or ""),
        "logFile": str(task.get("logFile") or ""),
        "outputTail": str(task.get("outputTail") or ""),
    }


def _load_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _count_from_sidecar(path: Path, key: str) -> int:
    payload = _load_json_file(path)
    if not isinstance(payload, dict):
        return 0
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return 0
    value = summary.get(key)
    return int(value) if isinstance(value, int) else 0


def _extract_log_file(output_text: str) -> str:
    matches = _LOG_FILE_PATTERN.findall(output_text)
    if not matches:
        return ""
    log_path = Path(matches[-1].strip())
    return _to_repo_relative(log_path)


def _build_task_message(
    *,
    status: str,
    success_count: int,
    skipped_count: int,
    failed_count: int,
    dry_run: bool,
) -> str:
    prefix = {
        "failed": "采集执行失败",
        "partial": "采集执行完成，但存在失败单据",
        "succeeded": "采集执行完成",
    }.get(status, "采集任务状态已更新")
    suffix = "（dry-run，未写入 PostgreSQL）" if dry_run else ""
    return (
        f"{prefix}：成功 {success_count} 张，跳过 {skipped_count} 张，失败 {failed_count} 张{suffix}".strip()
    )


def _write_summary_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_running_task_locked() -> dict[str, Any] | None:
    for task in _TASK_STATE_BY_ID.values():
        if task["status"] in {"queued", "running"}:
            return task
    return None


def _persist_task_snapshot(task_id: str) -> None:
    task = _TASK_STATE_BY_ID.get(task_id)
    if task is None:
        return
    summary_file = task.get("summaryFile")
    if not summary_file:
        return
    summary_path = REPO_ROOT / summary_file
    _write_summary_file(summary_path, _task_to_payload(task))


def _run_collect_task(task_id: str) -> None:
    with _TASK_LOCK:
        task = _TASK_STATE_BY_ID[task_id]
        task["status"] = "running"
        task["startedAt"] = _now_text()
        task["message"] = "采集任务已启动，正在调用 collect runner。"
        _persist_task_snapshot(task_id)

    _, settings = _load_runtime_settings()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    dump_path = REPO_ROOT / task["dumpFile"]
    skipped_dump_path = REPO_ROOT / task["skippedDumpFile"]
    failed_dump_path = REPO_ROOT / task["failedDumpFile"]

    command = [
        sys.executable,
        "automation/scripts/run.py",
        "collect",
        "--limit",
        str(task["requestedLimit"]),
        "--dump-json",
        str(dump_path),
    ]
    if task["requestedDocumentNo"]:
        command.extend(["--document-no", str(task["requestedDocumentNo"])])
    if task["dryRun"]:
        command.append("--dry-run")

    try:
        process = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        combined_output = "\n".join(part for part in [process.stdout, process.stderr] if part).strip()
        output_tail = combined_output[-4000:] if combined_output else ""
        success_payload = _load_json_file(dump_path)
        success_count = len(success_payload) if isinstance(success_payload, list) else 0
        skipped_count = _count_from_sidecar(skipped_dump_path, "skipped_count")
        failed_count = _count_from_sidecar(failed_dump_path, "failed_count")
        requested_count = max(
            success_count + skipped_count + failed_count,
            1 if task["requestedDocumentNo"] else int(task["requestedLimit"]),
        )

        if process.returncode != 0:
            status = "failed"
            message = output_tail or "collect runner 返回非 0 退出码。"
        elif failed_count > 0:
            status = "partial"
            message = _build_task_message(
                status=status,
                success_count=success_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                dry_run=bool(task["dryRun"]),
            )
        else:
            status = "succeeded"
            message = _build_task_message(
                status=status,
                success_count=success_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                dry_run=bool(task["dryRun"]),
            )

        with _TASK_LOCK:
            task = _TASK_STATE_BY_ID[task_id]
            task["status"] = status
            task["finishedAt"] = _now_text()
            task["requestedCount"] = requested_count
            task["successCount"] = success_count
            task["skippedCount"] = skipped_count
            task["failedCount"] = failed_count
            task["message"] = message
            task["logFile"] = _extract_log_file(combined_output)
            task["outputTail"] = output_tail
            _persist_task_snapshot(task_id)
    except Exception as exc:  # noqa: BLE001
        with _TASK_LOCK:
            task = _TASK_STATE_BY_ID[task_id]
            task["status"] = "failed"
            task["finishedAt"] = _now_text()
            task["message"] = f"采集任务执行异常：{exc}"
            task["outputTail"] = str(exc)
            _persist_task_snapshot(task_id)


def _load_recent_collect_runs(logs_dir: Path, limit: int = 8) -> list[dict[str, Any]]:
    summary_paths = sorted(
        logs_dir.glob(f"{_SUMMARY_PREFIX}*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    runs: list[dict[str, Any]] = []
    for path in summary_paths[:limit]:
        payload = _load_json_file(path)
        if isinstance(payload, dict):
            payload.setdefault("id", payload.get("taskId") or path.stem)
            payload.setdefault("summaryFile", _to_repo_relative(path))
            runs.append(payload)
    return runs


def get_collect_workbench() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresPermissionStore(settings.db)
    dashboard = store.fetch_collect_workbench()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)

    with _TASK_LOCK:
        current_task = _latest_running_task_locked()
        dashboard["currentTask"] = _task_to_payload(current_task) if current_task is not None else None

    dashboard["recentRuns"] = _load_recent_collect_runs(logs_dir)
    return dashboard


def get_collect_document_detail(document_no: str) -> dict[str, Any] | None:
    _, settings = _load_runtime_settings()
    store = PostgresPermissionStore(settings.db)
    return store.fetch_collect_document_detail(document_no)


def start_collect_task(
    *,
    document_no: str | None = None,
    limit: int = 10,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized_document_no = (document_no or "").strip()
    normalized_limit = 1 if normalized_document_no else max(int(limit or 0), 1)

    _, settings = _load_runtime_settings()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = uuid4().hex[:12]
    dump_file_path = logs_dir / f"collect_{timestamp_slug}_{task_id}.json"
    summary_file_path = logs_dir / f"{_SUMMARY_PREFIX}{timestamp_slug}_{task_id}.json"
    task_state = {
        "taskId": task_id,
        "status": "queued",
        "requestedAt": _now_text(),
        "startedAt": "",
        "finishedAt": "",
        "requestedDocumentNo": normalized_document_no,
        "requestedLimit": normalized_limit,
        "dryRun": bool(dry_run),
        "requestedCount": 0,
        "successCount": 0,
        "skippedCount": 0,
        "failedCount": 0,
        "message": "采集任务已创建，等待执行。",
        "dumpFile": _to_repo_relative(dump_file_path),
        "skippedDumpFile": _to_repo_relative(
            dump_file_path.with_name(f"{dump_file_path.stem}_skipped{dump_file_path.suffix}")
        ),
        "failedDumpFile": _to_repo_relative(
            dump_file_path.with_name(f"{dump_file_path.stem}_failed{dump_file_path.suffix}")
        ),
        "summaryFile": _to_repo_relative(summary_file_path),
        "logFile": "",
        "outputTail": "",
    }

    with _TASK_LOCK:
        running_task = _latest_running_task_locked()
        if running_task is not None:
            raise RuntimeError(
                f"当前已有采集任务在执行：{running_task['taskId']}。请等待该任务完成后再发起新的采集。"
            )
        _TASK_STATE_BY_ID[task_id] = task_state
        _persist_task_snapshot(task_id)

    worker = threading.Thread(target=_run_collect_task, args=(task_id,), daemon=True)
    worker.start()

    return _task_to_payload(task_state)
