from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Any, Iterable
from uuid import uuid4

from automation.api.config_summary import REPO_ROOT, _load_runtime_settings

_LOG_FILE_PATTERN = re.compile(r"Log file:\s*(.+)")
_SUMMARY_PREFIX = "audit_summary_"
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


def _normalize_document_nos(document_nos: Iterable[str] | None = None, *, document_no: str = "") -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    candidates: list[str] = []
    if document_no.strip():
        candidates.append(document_no)
    if document_nos is not None:
        candidates.extend(document_nos)

    for value in candidates:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _audit_task_to_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task["taskId"],
        "taskId": task["taskId"],
        "status": task["status"],
        "requestedAt": task["requestedAt"],
        "startedAt": task.get("startedAt", ""),
        "finishedAt": task.get("finishedAt", ""),
        "requestedDocumentNos": list(task.get("requestedDocumentNos") or []),
        "requestedLimit": int(task.get("requestedLimit") or 0),
        "dryRun": bool(task.get("dryRun")),
        "documentCount": int(task.get("documentCount") or 0),
        "detailCount": int(task.get("detailCount") or 0),
        "assessmentBatchNo": str(task.get("assessmentBatchNo") or ""),
        "assessmentVersion": str(task.get("assessmentVersion") or ""),
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
    _write_summary_file(REPO_ROOT / summary_file, _audit_task_to_payload(task))


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


def _latest_running_task_locked() -> dict[str, Any] | None:
    for task in _TASK_STATE_BY_ID.values():
        if task["status"] in {"queued", "running"}:
            return task
    return None


def _build_success_message(*, document_count: int, detail_count: int, dry_run: bool, batch_no: str) -> str:
    suffix = "（dry-run，未写入 PostgreSQL）" if dry_run else ""
    batch_text = f"，批次 {batch_no}" if batch_no else ""
    return f"评估执行完成：单据 {document_count} 张，明细 {detail_count} 条{batch_text}{suffix}".strip()


def _execute_audit_subprocess(
    *,
    requested_document_nos: list[str],
    requested_limit: int,
    dry_run: bool,
    dump_path: Path,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "automation/scripts/run.py",
        "audit",
        "--limit",
        str(requested_limit),
        "--dump-json",
        str(dump_path),
    ]
    if len(requested_document_nos) == 1:
        command.extend(["--document-no", requested_document_nos[0]])
    elif requested_document_nos:
        command.extend(["--document-nos", ",".join(requested_document_nos)])
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
    document_count = 0
    detail_count = 0
    assessment_batch_no = ""
    assessment_version = ""
    if isinstance(payload, dict):
        document_count = int(payload.get("document_count") or 0)
        detail_count = int(payload.get("detail_count") or 0)
        assessment_batch_no = str(payload.get("assessment_batch_no") or "")
        assessment_version = str(payload.get("assessment_version") or "")

    if process.returncode != 0:
        status = "failed"
        message = output_tail or "audit runner 返回非 0 退出码。"
    else:
        status = "succeeded"
        message = _build_success_message(
            document_count=document_count,
            detail_count=detail_count,
            dry_run=dry_run,
            batch_no=assessment_batch_no,
        )

    return {
        "status": status,
        "message": message,
        "documentCount": document_count,
        "detailCount": detail_count,
        "assessmentBatchNo": assessment_batch_no,
        "assessmentVersion": assessment_version,
        "logFile": _extract_log_file(combined_output),
        "outputTail": output_tail,
        "dumpFile": _to_repo_relative(dump_path),
    }


def _run_audit_task(task_id: str) -> None:
    with _TASK_LOCK:
        task = _TASK_STATE_BY_ID[task_id]
        task["status"] = "running"
        task["startedAt"] = _now_text()
        task["message"] = "评估任务已启动，正在调用 audit runner。"
        _persist_task_snapshot(task_id)

    dump_path = REPO_ROOT / str(task["dumpFile"])
    try:
        result = _execute_audit_subprocess(
            requested_document_nos=list(task.get("requestedDocumentNos") or []),
            requested_limit=int(task.get("requestedLimit") or 0),
            dry_run=bool(task.get("dryRun")),
            dump_path=dump_path,
        )
        with _TASK_LOCK:
            task = _TASK_STATE_BY_ID[task_id]
            task["status"] = result["status"]
            task["finishedAt"] = _now_text()
            task["documentCount"] = result["documentCount"]
            task["detailCount"] = result["detailCount"]
            task["assessmentBatchNo"] = result["assessmentBatchNo"]
            task["assessmentVersion"] = result["assessmentVersion"]
            task["message"] = result["message"]
            task["logFile"] = result["logFile"]
            task["outputTail"] = result["outputTail"]
            _persist_task_snapshot(task_id)
    except Exception as exc:  # noqa: BLE001
        with _TASK_LOCK:
            task = _TASK_STATE_BY_ID[task_id]
            task["status"] = "failed"
            task["finishedAt"] = _now_text()
            task["message"] = f"评估任务执行异常：{exc}"
            task["outputTail"] = str(exc)
            _persist_task_snapshot(task_id)


def run_audit_now(
    *,
    document_no: str | None = None,
    document_nos: Iterable[str] | None = None,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized_document_nos = _normalize_document_nos(document_nos, document_no=document_no or "")
    requested_limit = len(normalized_document_nos) if normalized_document_nos else max(int(limit or 0), 0)

    _, settings = _load_runtime_settings()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = uuid4().hex[:12]
    dump_path = logs_dir / f"audit_{timestamp_slug}_{task_id}.json"
    result = _execute_audit_subprocess(
        requested_document_nos=normalized_document_nos,
        requested_limit=requested_limit,
        dry_run=dry_run,
        dump_path=dump_path,
    )
    return {
        "taskId": task_id,
        "requestedDocumentNos": normalized_document_nos,
        "requestedLimit": requested_limit,
        "dryRun": bool(dry_run),
        **result,
    }


def start_audit_task(
    *,
    document_no: str | None = None,
    document_nos: Iterable[str] | None = None,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    normalized_document_nos = _normalize_document_nos(document_nos, document_no=document_no or "")
    normalized_limit = len(normalized_document_nos) if normalized_document_nos else max(int(limit or 0), 0)

    _, settings = _load_runtime_settings()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_id = uuid4().hex[:12]
    dump_file_path = logs_dir / f"audit_{timestamp_slug}_{task_id}.json"
    summary_file_path = logs_dir / f"{_SUMMARY_PREFIX}{timestamp_slug}_{task_id}.json"
    task_state = {
        "taskId": task_id,
        "status": "queued",
        "requestedAt": _now_text(),
        "startedAt": "",
        "finishedAt": "",
        "requestedDocumentNos": normalized_document_nos,
        "requestedLimit": normalized_limit,
        "dryRun": bool(dry_run),
        "documentCount": 0,
        "detailCount": 0,
        "assessmentBatchNo": "",
        "assessmentVersion": "",
        "message": "评估任务已创建，等待执行。",
        "dumpFile": _to_repo_relative(dump_file_path),
        "summaryFile": _to_repo_relative(summary_file_path),
        "logFile": "",
        "outputTail": "",
    }

    with _TASK_LOCK:
        running_task = _latest_running_task_locked()
        if running_task is not None:
            raise RuntimeError(
                f"当前已有评估任务在执行：{running_task['taskId']}。请等待该任务完成后再发起新的评估。"
            )
        _TASK_STATE_BY_ID[task_id] = task_state
        _persist_task_snapshot(task_id)

    worker = threading.Thread(target=_run_audit_task, args=(task_id,), daemon=True)
    worker.start()
    return _audit_task_to_payload(task_state)


def _load_recent_audit_runs(logs_dir: Path, limit: int = 8) -> list[dict[str, Any]]:
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


def get_audit_task_overview() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    with _TASK_LOCK:
        current_task = _latest_running_task_locked()
        payload = {
            "currentTask": _audit_task_to_payload(current_task) if current_task is not None else None,
            "recentRuns": _load_recent_audit_runs(logs_dir),
        }
    return payload
