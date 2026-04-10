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
from automation.db.postgres import PostgresPersonnelProfileChangeAuditStore

_LOG_FILE_PATTERN = re.compile(r"Log file:\s*(.+)")
_SUMMARY_PREFIX = "profile_change_audit_summary_"
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
        resolved_path = path.resolve(strict=False)
    except OSError:
        return str(path)
    try:
        return str(resolved_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved_path)


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


def _task_to_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task["taskId"],
        "taskId": task["taskId"],
        "status": task["status"],
        "requestedAt": task["requestedAt"],
        "startedAt": task.get("startedAt", ""),
        "finishedAt": task.get("finishedAt", ""),
        "requestedDocumentNo": str(task.get("requestedDocumentNo") or ""),
        "requestedLimit": int(task.get("requestedLimit") or 0),
        "pageSize": int(task.get("pageSize") or 0),
        "headed": bool(task.get("headed")),
        "dryRun": bool(task.get("dryRun")),
        "downloadAttachments": bool(task.get("downloadAttachments")),
        "successCount": int(task.get("successCount") or 0),
        "failedCount": int(task.get("failedCount") or 0),
        "message": str(task.get("message") or ""),
        "dumpFile": str(task.get("dumpFile") or ""),
        "summaryFile": str(task.get("summaryFile") or ""),
        "logFile": str(task.get("logFile") or ""),
        "outputTail": str(task.get("outputTail") or ""),
    }


def _write_summary_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _persist_task_snapshot(task_id: str) -> None:
    task = _TASK_STATE_BY_ID.get(task_id)
    if task is None:
        return
    summary_file = task.get("summaryFile")
    if not summary_file:
        return
    _write_summary_file(REPO_ROOT / summary_file, _task_to_payload(task))


def _latest_running_task_locked() -> dict[str, Any] | None:
    for task in _TASK_STATE_BY_ID.values():
        if task["status"] in {"queued", "running"}:
            return task
    return None


def _build_message(*, status: str, success_count: int, failed_count: int, dry_run: bool) -> str:
    prefix = {
        "failed": "人员档案修改审核采集执行失败",
        "partial": "人员档案修改审核采集执行完成，但存在失败单据",
        "succeeded": "人员档案修改审核采集执行完成",
    }.get(status, "人员档案修改审核采集任务状态已更新")
    suffix = "（dry-run，未写入 PostgreSQL）" if dry_run else ""
    return f"{prefix}：成功 {success_count} 单，失败 {failed_count} 单{suffix}".strip()


def _reconcile_stale_run(summary_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "")
    if status not in {"queued", "running"}:
        return payload

    dump_path = REPO_ROOT / str(payload.get("dumpFile") or "")
    result_payload = _load_json_file(dump_path)
    if not isinstance(result_payload, dict):
        return payload

    success_count = int(result_payload.get("document_count") or 0)
    failed_count = int(result_payload.get("failed_document_count") or 0)
    recovered_status = "partial" if success_count > 0 and failed_count > 0 else "succeeded" if success_count > 0 else "failed"
    recovered_payload = dict(payload)
    recovered_payload["status"] = recovered_status
    recovered_payload["finishedAt"] = datetime.fromtimestamp(dump_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    recovered_payload["successCount"] = success_count
    recovered_payload["failedCount"] = failed_count
    recovered_payload["message"] = _build_message(
        status=recovered_status,
        success_count=success_count,
        failed_count=failed_count,
        dry_run=bool(payload.get("dryRun")),
    )
    if recovered_payload != payload:
        _write_summary_file(summary_path, recovered_payload)
    return recovered_payload


def _run_task(task_id: str) -> None:
    with _TASK_LOCK:
        task = _TASK_STATE_BY_ID[task_id]
        task["status"] = "running"
        task["startedAt"] = _now_text()
        task["message"] = "人员档案修改审核采集任务已启动，正在调用 runner。"
        _persist_task_snapshot(task_id)

    dump_path = REPO_ROOT / str(task["dumpFile"])
    command = [
        sys.executable,
        "automation/scripts/run.py",
        "profile-change-audit",
        "--limit",
        str(task["requestedLimit"]),
        "--page-size",
        str(task["pageSize"]),
        "--dump-json",
        str(dump_path),
        "--headed" if bool(task.get("headed")) else "--headless",
    ]
    if task.get("requestedDocumentNo"):
        command.extend(["--document-no", str(task["requestedDocumentNo"])])
    if task.get("dryRun"):
        command.append("--dry-run")
    if task.get("downloadAttachments"):
        command.append("--download-attachments")

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
        result_payload = _load_json_file(dump_path)
        success_count = int(result_payload.get("document_count") or 0) if isinstance(result_payload, dict) else 0
        failed_count = int(result_payload.get("failed_document_count") or 0) if isinstance(result_payload, dict) else 0

        if process.returncode != 0:
            status = "failed"
            message = output_tail or "profile-change-audit runner 返回非 0 退出码。"
        elif failed_count > 0:
            status = "partial"
            message = _build_message(
                status=status,
                success_count=success_count,
                failed_count=failed_count,
                dry_run=bool(task.get("dryRun")),
            )
        else:
            status = "succeeded"
            message = _build_message(
                status=status,
                success_count=success_count,
                failed_count=failed_count,
                dry_run=bool(task.get("dryRun")),
            )

        with _TASK_LOCK:
            task = _TASK_STATE_BY_ID[task_id]
            task["status"] = status
            task["finishedAt"] = _now_text()
            task["successCount"] = success_count
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
            task["message"] = f"人员档案修改审核采集任务执行异常：{exc}"
            task["outputTail"] = str(exc)
            _persist_task_snapshot(task_id)


def _load_recent_runs(logs_dir: Path, limit: int = 8, active_task_ids: set[str] | None = None) -> list[dict[str, Any]]:
    summary_paths = sorted(
        logs_dir.glob(f"{_SUMMARY_PREFIX}*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    runs: list[dict[str, Any]] = []
    for path in summary_paths[:limit]:
        payload = _load_json_file(path)
        if isinstance(payload, dict):
            task_id = str(payload.get("taskId") or payload.get("id") or "")
            if task_id and task_id not in (active_task_ids or set()):
                payload = _reconcile_stale_run(path, payload)
            payload.setdefault("id", payload.get("taskId") or path.stem)
            payload.setdefault("summaryFile", _to_repo_relative(path))
            runs.append(payload)
    return runs


def get_profile_change_audit_workbench() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresPersonnelProfileChangeAuditStore(settings.db)
    dashboard = store.fetch_workbench()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)

    with _TASK_LOCK:
        current_task = _latest_running_task_locked()
        active_task_ids = {
            str(task_id)
            for task_id, task in _TASK_STATE_BY_ID.items()
            if task.get("status") in {"queued", "running"}
        }
        dashboard["currentTask"] = _task_to_payload(current_task) if current_task is not None else None

    dashboard["recentRuns"] = _load_recent_runs(logs_dir, active_task_ids=active_task_ids)
    return dashboard


def get_profile_change_audit_document_detail(document_no: str) -> dict[str, Any] | None:
    _, settings = _load_runtime_settings()
    store = PostgresPersonnelProfileChangeAuditStore(settings.db)
    return store.fetch_document_detail(document_no)


def start_profile_change_audit_task(
    *,
    document_no: str | None = None,
    limit: int = 20,
    page_size: int = 100,
    headed: bool | None = None,
    dry_run: bool = False,
    download_attachments: bool = False,
) -> dict[str, Any]:
    normalized_document_no = str(document_no or "").strip()
    normalized_limit = 1 if normalized_document_no else max(int(limit or 0), 1)
    normalized_page_size = max(int(page_size or 0), 1)

    _, settings = _load_runtime_settings()
    resolved_headed = settings.browser.headed if headed is None else bool(headed)
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = uuid4().hex[:12]
    dump_file_path = logs_dir / f"profile_change_audit_{timestamp_slug}_{task_id}.json"
    summary_file_path = logs_dir / f"{_SUMMARY_PREFIX}{timestamp_slug}_{task_id}.json"
    task_state = {
        "taskId": task_id,
        "status": "queued",
        "requestedAt": _now_text(),
        "startedAt": "",
        "finishedAt": "",
        "requestedDocumentNo": normalized_document_no,
        "requestedLimit": normalized_limit,
        "pageSize": normalized_page_size,
        "headed": bool(resolved_headed),
        "dryRun": bool(dry_run),
        "downloadAttachments": bool(download_attachments),
        "successCount": 0,
        "failedCount": 0,
        "message": "人员档案修改审核采集任务已创建，等待执行。",
        "dumpFile": _to_repo_relative(dump_file_path),
        "summaryFile": _to_repo_relative(summary_file_path),
        "logFile": "",
        "outputTail": "",
    }

    with _TASK_LOCK:
        running_task = _latest_running_task_locked()
        if running_task is not None:
            raise RuntimeError(
                f"当前已有人员档案修改审核采集任务在执行：{running_task['taskId']}。请等待其完成后再发起新任务。"
            )
        _TASK_STATE_BY_ID[task_id] = task_state
        _persist_task_snapshot(task_id)

    worker = threading.Thread(target=_run_task, args=(task_id,), daemon=True)
    worker.start()
    return _task_to_payload(task_state)
