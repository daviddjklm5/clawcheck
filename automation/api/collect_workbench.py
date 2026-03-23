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
from automation.api.audit_workbench import run_audit_now
from automation.db.postgres import PostgresPermissionStore
from automation.utils.collect_schedule import (
    COLLECT_EXECUTION_CONFLICT_EXIT_CODE,
    is_collect_execution_locked,
)

_LOG_FILE_PATTERN = re.compile(r"Log file:\s*(.+)")
_SUMMARY_PREFIX = "collect_summary_"
_TASK_LOCK = threading.Lock()
_TASK_STATE_BY_ID: dict[str, dict[str, Any]] = {}
_COLLECT_TIMESTAMP_PATTERN = re.compile(r"collect_(\d{8}_\d{6})_[^.]+\.json$")


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
        "headed": bool(task.get("headed")),
        "dryRun": bool(task.get("dryRun")),
        "autoAudit": bool(task.get("autoAudit")),
        "forceRecollect": bool(task.get("forceRecollect")),
        "requestedCount": int(task.get("requestedCount") or 0),
        "successCount": int(task.get("successCount") or 0),
        "skippedCount": int(task.get("skippedCount") or 0),
        "failedCount": int(task.get("failedCount") or 0),
        "message": str(task.get("message") or ""),
        "auditStatus": str(task.get("auditStatus") or ""),
        "auditBatchNo": str(task.get("auditBatchNo") or ""),
        "auditMessage": str(task.get("auditMessage") or ""),
        "auditLogFile": str(task.get("auditLogFile") or ""),
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


def _extract_collected_document_nos(payload: Any) -> list[str]:
    if not isinstance(payload, list):
        return []
    ordered: list[str] = []
    seen: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            continue
        basic_info = row.get("basic_info")
        if not isinstance(basic_info, dict):
            continue
        document_no = str(basic_info.get("document_no") or "").strip()
        if not document_no or document_no in seen:
            continue
        seen.add(document_no)
        ordered.append(document_no)
    return ordered


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


def _build_no_pending_message(*, dry_run: bool) -> str:
    suffix = "（dry-run，未写入 PostgreSQL）" if dry_run else ""
    return f"本轮无待办，已快速结束{suffix}".strip()


def _build_lock_conflict_message() -> str:
    return "当前已有其他采集任务在执行，本次未重复启动。"


def _write_summary_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_collect_timestamp_slug(path_text: str) -> str:
    match = _COLLECT_TIMESTAMP_PATTERN.search(Path(path_text).name)
    if not match:
        return ""
    return match.group(1)


def _tail_text_file(path: Path, max_chars: int = 4000) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")[-max_chars:]
    except Exception:  # noqa: BLE001
        return ""


def _reconcile_stale_collect_run(summary_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "")
    if status not in {"queued", "running"}:
        return payload

    dump_path = REPO_ROOT / str(payload.get("dumpFile") or "")
    skipped_dump_path = REPO_ROOT / str(payload.get("skippedDumpFile") or "")
    failed_dump_path = REPO_ROOT / str(payload.get("failedDumpFile") or "")

    success_payload = _load_json_file(dump_path)
    success_count = len(success_payload) if isinstance(success_payload, list) else 0
    skipped_count = _count_from_sidecar(skipped_dump_path, "skipped_count")
    failed_count = _count_from_sidecar(failed_dump_path, "failed_count")

    timestamp_slug = _extract_collect_timestamp_slug(str(payload.get("dumpFile") or ""))
    log_path = REPO_ROOT / f"automation/logs/run_{timestamp_slug}.log" if timestamp_slug else Path()
    log_tail = _tail_text_file(log_path) if timestamp_slug else ""

    has_terminal_artifact = any(
        (
            dump_path.exists(),
            skipped_dump_path.exists(),
            failed_dump_path.exists(),
            bool(log_tail),
        )
    )
    if not has_terminal_artifact:
        return payload

    finished_candidates = [
        path.stat().st_mtime
        for path in (dump_path, skipped_dump_path, failed_dump_path, log_path)
        if path.exists()
    ]
    finished_at = (
        datetime.fromtimestamp(max(finished_candidates)).strftime("%Y-%m-%d %H:%M:%S")
        if finished_candidates
        else ""
    )
    requested_document_no = str(payload.get("requestedDocumentNo") or "").strip()
    requested_limit = int(payload.get("requestedLimit") or 0)
    requested_count = max(success_count + skipped_count + failed_count, 1 if requested_document_no else requested_limit)

    if failed_count > 0:
        recovered_status = "partial"
    elif success_count > 0 or "Automation finished successfully" in log_tail:
        recovered_status = "succeeded"
    else:
        recovered_status = "failed"

    recovered_payload = dict(payload)
    recovered_payload["status"] = recovered_status
    recovered_payload["finishedAt"] = finished_at
    recovered_payload["requestedCount"] = requested_count
    recovered_payload["successCount"] = success_count
    recovered_payload["skippedCount"] = skipped_count
    recovered_payload["failedCount"] = failed_count
    recovered_payload["message"] = _build_task_message(
        status=recovered_status,
        success_count=success_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        dry_run=bool(payload.get("dryRun")),
    )
    recovered_payload["logFile"] = _to_repo_relative(log_path) if timestamp_slug and log_path.exists() else str(
        payload.get("logFile") or ""
    )
    recovered_payload["outputTail"] = log_tail or str(payload.get("outputTail") or "")

    if recovered_payload != payload:
        _write_summary_file(summary_path, recovered_payload)
    return recovered_payload


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
        "--headed" if bool(task.get("headed")) else "--headless",
        "--limit",
        str(task["requestedLimit"]),
        "--dump-json",
        str(dump_path),
    ]
    if task["requestedDocumentNo"]:
        command.extend(["--document-no", str(task["requestedDocumentNo"])])
    if task["dryRun"]:
        command.append("--dry-run")
    if task.get("forceRecollect"):
        command.append("--force-recollect")

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
        success_document_nos = _extract_collected_document_nos(success_payload)
        skipped_count = _count_from_sidecar(skipped_dump_path, "skipped_count")
        failed_count = _count_from_sidecar(failed_dump_path, "failed_count")
        requested_count = max(
            success_count + skipped_count + failed_count,
            1 if task["requestedDocumentNo"] else int(task["requestedLimit"]),
        )
        audit_result: dict[str, Any] | None = None
        no_pending_detected = "No permission application documents found in todo list" in combined_output

        if process.returncode == COLLECT_EXECUTION_CONFLICT_EXIT_CODE:
            status = "succeeded"
            requested_count = 0
            message = _build_lock_conflict_message()
        elif process.returncode != 0:
            status = "failed"
            message = output_tail or "collect runner 返回非 0 退出码。"
        elif no_pending_detected and success_count == 0 and skipped_count == 0 and failed_count == 0:
            status = "succeeded"
            requested_count = 0
            message = _build_no_pending_message(dry_run=bool(task["dryRun"]))
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

        if (
            process.returncode == 0
            and success_document_nos
            and bool(task.get("autoAudit"))
            and not bool(task["dryRun"])
        ):
            audit_result = run_audit_now(
                document_nos=success_document_nos,
                limit=len(success_document_nos),
                dry_run=False,
            )
            if audit_result["status"] == "partial":
                status = "partial"
                message = f"{message}；增量评估部分失败：{audit_result['message']}"
            elif audit_result["status"] != "succeeded":
                status = "partial"
                message = f"{message}；增量评估失败：{audit_result['message']}"
            else:
                message = f"{message}；已完成增量评估，批次 {audit_result['assessmentBatchNo']}"

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
            task["auditStatus"] = str(audit_result.get("status") or "") if audit_result is not None else ""
            task["auditBatchNo"] = str(audit_result.get("assessmentBatchNo") or "") if audit_result is not None else ""
            task["auditMessage"] = str(audit_result.get("message") or "") if audit_result is not None else ""
            task["auditLogFile"] = str(audit_result.get("logFile") or "") if audit_result is not None else ""
            _persist_task_snapshot(task_id)
    except Exception as exc:  # noqa: BLE001
        with _TASK_LOCK:
            task = _TASK_STATE_BY_ID[task_id]
            task["status"] = "failed"
            task["finishedAt"] = _now_text()
            task["message"] = f"采集任务执行异常：{exc}"
            task["outputTail"] = str(exc)
            _persist_task_snapshot(task_id)


def _load_recent_collect_runs(logs_dir: Path, limit: int = 8, active_task_ids: set[str] | None = None) -> list[dict[str, Any]]:
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
                payload = _reconcile_stale_collect_run(path, payload)
            payload.setdefault("id", payload.get("taskId") or path.stem)
            payload.setdefault("summaryFile", _to_repo_relative(path))
            payload.setdefault("headed", False)
            payload.setdefault("forceRecollect", False)
            runs.append(payload)
    return runs


def get_collect_workbench() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresPermissionStore(settings.db)
    dashboard = store.fetch_collect_workbench()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)

    with _TASK_LOCK:
        current_task = _latest_running_task_locked()
        active_task_ids = {str(task_id) for task_id, task in _TASK_STATE_BY_ID.items() if task.get("status") in {"queued", "running"}}
        dashboard["currentTask"] = _task_to_payload(current_task) if current_task is not None else None

    dashboard["recentRuns"] = _load_recent_collect_runs(logs_dir, active_task_ids=active_task_ids)
    return dashboard


def get_collect_document_detail(document_no: str) -> dict[str, Any] | None:
    _, settings = _load_runtime_settings()
    store = PostgresPermissionStore(settings.db)
    return store.fetch_collect_document_detail(document_no)


def start_collect_task(
    *,
    document_no: str | None = None,
    limit: int = 100,
    headed: bool | None = None,
    dry_run: bool = False,
    auto_audit: bool = True,
    force_recollect: bool = False,
) -> dict[str, Any]:
    normalized_document_no = (document_no or "").strip()
    normalized_limit = 1 if normalized_document_no else max(int(limit or 0), 1)

    _, settings = _load_runtime_settings()
    resolved_headed = settings.browser.headed if headed is None else bool(headed)
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
        "headed": bool(resolved_headed),
        "dryRun": bool(dry_run),
        "autoAudit": bool(auto_audit),
        "forceRecollect": bool(force_recollect),
        "requestedCount": 0,
        "successCount": 0,
        "skippedCount": 0,
        "failedCount": 0,
        "message": "采集任务已创建，等待执行。",
        "auditStatus": "",
        "auditBatchNo": "",
        "auditMessage": "",
        "auditLogFile": "",
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
        if is_collect_execution_locked():
            raise RuntimeError("当前已有采集任务在执行。请等待当前批次完成后再发起新的采集。")
        _TASK_STATE_BY_ID[task_id] = task_state
        _persist_task_snapshot(task_id)

    worker = threading.Thread(target=_run_collect_task, args=(task_id,), daemon=True)
    worker.start()

    return _task_to_payload(task_state)
