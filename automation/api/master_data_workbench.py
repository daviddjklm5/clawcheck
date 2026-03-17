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
from automation.db.postgres import PostgresMasterDataStore

_LOG_FILE_PATTERN = re.compile(r"Log file:\s*(.+)")
_SUMMARY_PREFIX = "master_data_summary_"
_VALID_TASK_TYPES = {"roster", "orglist", "rolecatalog"}
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


def _normalize_task_type(task_type: str) -> str:
    normalized = task_type.strip().lower()
    if normalized not in _VALID_TASK_TYPES:
        raise ValueError(f"不支持的主数据任务类型：{task_type}")
    return normalized


def _extract_log_file(output_text: str) -> str:
    matches = _LOG_FILE_PATTERN.findall(output_text)
    if not matches:
        return ""
    return _to_repo_relative(Path(matches[-1].strip()))


def _load_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _translate_status(status: str) -> tuple[str, str]:
    mapping = {
        "queued": ("排队中", "info"),
        "running": ("运行中", "warning"),
        "succeeded": ("已完成", "success"),
        "failed": ("执行失败", "danger"),
    }
    return mapping.get(status, (status, "default"))


def _normalize_permission_level_counts(raw_rows: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_rows, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in raw_rows:
        if not isinstance(item, dict):
            continue
        level = str(item.get("permission_level") or item.get("permissionLevel") or "").strip()
        if not level:
            continue
        count_raw = item.get("count")
        try:
            count = int(count_raw or 0)
        except (TypeError, ValueError):
            count = 0
        rows.append({"permissionLevel": level, "count": count})
    return rows


def _task_to_payload(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task["taskId"],
        "taskId": task["taskId"],
        "taskType": task["taskType"],
        "status": task["status"],
        "requestedAt": task["requestedAt"],
        "startedAt": task.get("startedAt", ""),
        "finishedAt": task.get("finishedAt", ""),
        "headed": bool(task.get("headed")),
        "dryRun": bool(task.get("dryRun")),
        "inputFile": str(task.get("inputFile") or ""),
        "skipExport": bool(task.get("skipExport")),
        "skipImport": bool(task.get("skipImport")),
        "queryTimeoutSeconds": int(task.get("queryTimeoutSeconds") or 0),
        "downloadTimeoutMinutes": int(task.get("downloadTimeoutMinutes") or 0),
        "scheme": str(task.get("scheme") or ""),
        "employmentType": str(task.get("employmentType") or ""),
        "forceRefresh": bool(task.get("forceRefresh")),
        "tableName": str(task.get("tableName") or ""),
        "importBatchNo": str(task.get("importBatchNo") or ""),
        "sourceFileName": str(task.get("sourceFileName") or ""),
        "insertedCount": int(task.get("insertedCount") or 0),
        "totalRows": int(task.get("totalRows") or 0),
        "countsByPermissionLevel": list(task.get("countsByPermissionLevel") or []),
        "message": str(task.get("message") or ""),
        "dumpFile": str(task.get("dumpFile") or ""),
        "summaryFile": str(task.get("summaryFile") or ""),
        "logFile": str(task.get("logFile") or ""),
        "outputTail": str(task.get("outputTail") or ""),
    }


def _build_master_data_stats(
    summary: dict[str, Any],
    *,
    recent_runs: list[dict[str, Any]],
    current_task: dict[str, Any] | None,
    db_error: str = "",
) -> list[dict[str, str]]:
    roster = summary.get("roster", {})
    orglist = summary.get("orglist", {})
    rolecatalog = summary.get("rolecatalog", {})

    latest_task_status = ""
    latest_task_time = ""
    if current_task is not None:
        latest_task_status = current_task.get("status") or ""
        latest_task_time = current_task.get("startedAt") or current_task.get("requestedAt") or ""
    elif recent_runs:
        latest_task_status = str(recent_runs[0].get("status") or "")
        latest_task_time = str(recent_runs[0].get("finishedAt") or recent_runs[0].get("requestedAt") or "")

    latest_task_label, latest_task_tone = _translate_status(latest_task_status) if latest_task_status else ("无任务", "default")

    stats = [
        {
            "label": "在职花名册",
            "value": str(roster.get("latestImportedAt") or "-"),
            "hint": (
                f"批次 {roster.get('latestImportBatchNo') or '-'}，行数 {int(roster.get('totalRows') or 0)}，"
                f"人员属性 {int(roster.get('personAttributeRows') or 0)} 行。"
            ),
            "tone": "success" if int(roster.get("totalRows") or 0) > 0 else "default",
        },
        {
            "label": "组织列表",
            "value": str(orglist.get("latestUpdatedAt") or "-"),
            "hint": (
                f"批次 {orglist.get('latestImportBatchNo') or '-'}，行数 {int(orglist.get('totalRows') or 0)}，"
                f"组织属性 {int(orglist.get('orgAttributeRows') or 0)} 行。"
            ),
            "tone": "success" if int(orglist.get("totalRows") or 0) > 0 else "default",
        },
        {
            "label": "权限列表",
            "value": f"{int(rolecatalog.get('totalRows') or 0)} 条",
            "hint": f"最新更新时间 {rolecatalog.get('latestUpdatedAt') or '-'}，按权限级别分组可在下方任务摘要查看。",
            "tone": "info" if int(rolecatalog.get("totalRows") or 0) > 0 else "default",
        },
        {
            "label": "最近主数据任务",
            "value": latest_task_label,
            "hint": f"{latest_task_time or '暂无执行时间'}",
            "tone": latest_task_tone,
        },
    ]
    if db_error:
        stats.append(
            {
                "label": "数据库连接状态",
                "value": "异常",
                "hint": db_error[:180],
                "tone": "danger",
            }
        )
    return stats


def _build_actions() -> list[dict[str, Any]]:
    return [
        {
            "id": "roster",
            "taskType": "roster",
            "title": "同步在职花名册",
            "description": "下载最新在职花名册并刷新人员属性查询。",
            "buttonLabel": "启动同步",
            "status": "建议保留可见浏览器模式，便于观察导出流程。",
        },
        {
            "id": "orglist",
            "taskType": "orglist",
            "title": "同步组织列表",
            "description": "下载组织快速维护清单并刷新组织属性查询。",
            "buttonLabel": "启动同步",
            "status": "组织数据量较大，建议单任务串行执行。",
        },
        {
            "id": "rolecatalog",
            "taskType": "rolecatalog",
            "title": "刷新权限主数据",
            "description": "执行权限列表 seed/upsert，刷新权限级别口径。",
            "buttonLabel": "执行刷新",
            "status": "每次点击都会执行 seed upsert 并返回最新统计。",
        },
    ]


def _latest_running_task_locked() -> dict[str, Any] | None:
    for task in _TASK_STATE_BY_ID.values():
        if task["status"] in {"queued", "running"}:
            return task
    return None


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


def _build_task_message(task_type: str, status: str) -> str:
    if status == "failed":
        return f"{task_type} 任务执行失败。"
    return f"{task_type} 任务执行完成。"


def _run_master_data_task(task_id: str) -> None:
    with _TASK_LOCK:
        task = _TASK_STATE_BY_ID[task_id]
        task["status"] = "running"
        task["startedAt"] = _now_text()
        task["message"] = f"{task['taskType']} 任务已启动。"
        _persist_task_snapshot(task_id)

    settings_path, settings = _load_runtime_settings()
    _ = settings_path
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "automation/scripts/run.py",
        task["taskType"],
        "--dump-json",
        str(REPO_ROOT / task["dumpFile"]),
        "--headed" if task["headed"] else "--headless",
    ]
    if task["taskType"] in {"roster", "orglist"} and task["dryRun"]:
        command.append("--dry-run")
    if task.get("inputFile"):
        command.extend(["--input-file", str(task["inputFile"])])
    if task["taskType"] in {"roster", "orglist"} and task.get("skipExport"):
        command.append("--skip-export")
    if task["taskType"] in {"roster", "orglist"} and task.get("skipImport"):
        command.append("--skip-import")
    if task.get("queryTimeoutSeconds"):
        command.extend(["--query-timeout-seconds", str(task["queryTimeoutSeconds"])])
    if task.get("downloadTimeoutMinutes"):
        command.extend(["--download-timeout-minutes", str(task["downloadTimeoutMinutes"])])
    if task["taskType"] == "roster" and task.get("scheme"):
        command.extend(["--scheme", str(task["scheme"])])
    if task["taskType"] == "roster" and task.get("employmentType"):
        command.extend(["--employment-type", str(task["employmentType"])])

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
        dump_payload = _load_json_file(REPO_ROOT / task["dumpFile"])
        store = PostgresMasterDataStore(settings.db)
        summary = store.fetch_master_data_workbench()
        task_type = str(task["taskType"])
        sub_summary = summary.get(task_type, {})

        status = "succeeded" if process.returncode == 0 else "failed"
        message = output_tail or _build_task_message(task_type, status)

        source_file_name = ""
        if isinstance(dump_payload, dict):
            source_file_name = str(dump_payload.get("file_name") or dump_payload.get("source_file_name") or "")
        if not source_file_name:
            source_file_name = str(sub_summary.get("sourceFileName") or "")

        if task_type == "rolecatalog":
            counts = _normalize_permission_level_counts(
                dump_payload.get("counts_by_permission_level") if isinstance(dump_payload, dict) else []
            )
            if not counts:
                counts = list(sub_summary.get("countsByPermissionLevel") or [])
            inserted_count = int(dump_payload.get("total_rows") or 0) if isinstance(dump_payload, dict) else 0
            total_rows = int(sub_summary.get("totalRows") or inserted_count or 0)
            import_batch_no = ""
            table_name = "权限列表"
        elif task_type == "roster":
            inserted_count = int(sub_summary.get("totalRows") or 0) if status == "succeeded" and not task["dryRun"] and not task.get("skipImport") else 0
            total_rows = int(sub_summary.get("totalRows") or 0)
            import_batch_no = str(sub_summary.get("latestImportBatchNo") or "")
            table_name = "在职花名册表"
            counts = []
        else:
            inserted_count = int(sub_summary.get("totalRows") or 0) if status == "succeeded" and not task["dryRun"] and not task.get("skipImport") else 0
            total_rows = int(sub_summary.get("totalRows") or 0)
            import_batch_no = str(sub_summary.get("latestImportBatchNo") or "")
            table_name = "组织列表"
            counts = []

        with _TASK_LOCK:
            current = _TASK_STATE_BY_ID[task_id]
            current["status"] = status
            current["finishedAt"] = _now_text()
            current["message"] = message if status == "failed" else _build_task_message(task_type, status)
            current["sourceFileName"] = source_file_name
            current["importBatchNo"] = import_batch_no
            current["insertedCount"] = inserted_count
            current["totalRows"] = total_rows
            current["tableName"] = table_name
            current["countsByPermissionLevel"] = counts
            current["logFile"] = _extract_log_file(combined_output)
            current["outputTail"] = output_tail
            _persist_task_snapshot(task_id)
    except Exception as exc:  # noqa: BLE001
        with _TASK_LOCK:
            current = _TASK_STATE_BY_ID[task_id]
            current["status"] = "failed"
            current["finishedAt"] = _now_text()
            current["message"] = f"主数据任务执行异常：{exc}"
            current["outputTail"] = str(exc)
            _persist_task_snapshot(task_id)


def _load_recent_runs(logs_dir: Path, limit: int = 10) -> list[dict[str, Any]]:
    summary_paths = sorted(
        logs_dir.glob(f"{_SUMMARY_PREFIX}*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    runs: list[dict[str, Any]] = []
    for path in summary_paths[:limit]:
        payload = _load_json_file(path)
        if not isinstance(payload, dict):
            continue
        payload.setdefault("id", payload.get("taskId") or path.stem)
        payload.setdefault("summaryFile", _to_repo_relative(path))
        runs.append(payload)
    return runs


def get_master_data_workbench() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    db_error = ""
    try:
        store = PostgresMasterDataStore(settings.db)
        summary = store.fetch_master_data_workbench()
    except Exception as exc:  # noqa: BLE001
        db_error = f"主数据摘要查询失败：{exc}"
        summary = {
            "roster": {},
            "orglist": {},
            "rolecatalog": {},
        }
    recent_runs = _load_recent_runs(logs_dir)
    with _TASK_LOCK:
        current_task = _latest_running_task_locked()
        current_payload = _task_to_payload(current_task) if current_task is not None else None
    return {
        "stats": _build_master_data_stats(
            summary,
            recent_runs=recent_runs,
            current_task=current_payload,
            db_error=db_error,
        ),
        "actions": _build_actions(),
        "currentTask": current_payload,
        "recentRuns": recent_runs,
    }


def start_master_data_task(
    *,
    task_type: str,
    headed: bool,
    dry_run: bool = False,
    input_file: str = "",
    skip_export: bool = False,
    skip_import: bool = False,
    query_timeout_seconds: int = 0,
    download_timeout_minutes: int = 0,
    scheme: str = "",
    employment_type: str = "",
    force_refresh: bool = True,
) -> dict[str, Any]:
    normalized_task_type = _normalize_task_type(task_type)
    if normalized_task_type == "rolecatalog":
        dry_run = False
        skip_export = False
        skip_import = False

    _, settings = _load_runtime_settings()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    task_id = uuid4().hex[:12]
    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_path = logs_dir / f"{normalized_task_type}_{timestamp_slug}_{task_id}.json"
    summary_path = logs_dir / f"{_SUMMARY_PREFIX}{timestamp_slug}_{task_id}.json"

    task_state = {
        "taskId": task_id,
        "taskType": normalized_task_type,
        "status": "queued",
        "requestedAt": _now_text(),
        "startedAt": "",
        "finishedAt": "",
        "headed": bool(headed),
        "dryRun": bool(dry_run),
        "inputFile": (input_file or "").strip(),
        "skipExport": bool(skip_export),
        "skipImport": bool(skip_import),
        "queryTimeoutSeconds": max(int(query_timeout_seconds or 0), 0),
        "downloadTimeoutMinutes": max(int(download_timeout_minutes or 0), 0),
        "scheme": (scheme or "").strip(),
        "employmentType": (employment_type or "").strip(),
        "forceRefresh": bool(force_refresh),
        "tableName": "",
        "importBatchNo": "",
        "sourceFileName": "",
        "insertedCount": 0,
        "totalRows": 0,
        "countsByPermissionLevel": [],
        "message": "主数据任务已创建，等待执行。",
        "dumpFile": _to_repo_relative(dump_path),
        "summaryFile": _to_repo_relative(summary_path),
        "logFile": "",
        "outputTail": "",
    }

    with _TASK_LOCK:
        running_task = _latest_running_task_locked()
        if running_task is not None:
            raise RuntimeError(
                f"当前已有主数据任务在执行：{running_task['taskId']}。请等待该任务完成后再发起新的任务。"
            )
        _TASK_STATE_BY_ID[task_id] = task_state
        _persist_task_snapshot(task_id)

    worker = threading.Thread(target=_run_master_data_task, args=(task_id,), daemon=True)
    worker.start()
    return _task_to_payload(task_state)
