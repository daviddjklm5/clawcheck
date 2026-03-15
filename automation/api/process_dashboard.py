from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any

from automation.api.config_summary import REPO_ROOT, _load_runtime_settings
from automation.db.postgres import PostgresRiskTrustStore

_BATCH_NO_PATTERN = re.compile(r'"assessment_batch_no"\s*:\s*"([^"]+)"')
_VERSION_PATTERN = re.compile(r'"assessment_version"\s*:\s*"([^"]+)"')
_DOCUMENT_COUNT_PATTERN = re.compile(r'"document_count"\s*:\s*(\d+)')
_DETAIL_COUNT_PATTERN = re.compile(r'"detail_count"\s*:\s*(\d+)')
_DOCUMENT_NO_PATTERN = re.compile(r'"document_no"\s*:\s*"([^"]+)"')
_AUDIT_LOG_FILENAME_PATTERN = re.compile(r"audit_(\d{8})_(\d{6})$")


def _to_repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _resolve_runtime_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _extract_audit_log_summary(path: Path) -> dict[str, Any] | None:
    with path.open("r", encoding="utf-8") as fh:
        preview_text = fh.read(200000)

    batch_no_match = _BATCH_NO_PATTERN.search(preview_text)
    if not batch_no_match:
        return None

    version_match = _VERSION_PATTERN.search(preview_text)
    document_count_match = _DOCUMENT_COUNT_PATTERN.search(preview_text)
    detail_count_match = _DETAIL_COUNT_PATTERN.search(preview_text)
    sample_document_match = _DOCUMENT_NO_PATTERN.search(preview_text)

    executed_at = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    file_name_match = _AUDIT_LOG_FILENAME_PATTERN.match(path.stem)
    if file_name_match:
        executed_at = datetime.strptime(
            f"{file_name_match.group(1)}{file_name_match.group(2)}",
            "%Y%m%d%H%M%S",
        ).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "batchNo": batch_no_match.group(1),
        "assessmentVersion": version_match.group(1) if version_match else "-",
        "executedAt": executed_at,
        "documentCount": int(document_count_match.group(1)) if document_count_match else 0,
        "detailCount": int(detail_count_match.group(1)) if detail_count_match else 0,
        "sampleDocumentNo": sample_document_match.group(1) if sample_document_match else "-",
        "sourceFile": _to_repo_relative(path),
    }


def _load_execution_logs(store: PostgresRiskTrustStore, logs_dir: Path, limit: int = 6) -> list[dict[str, Any]]:
    audit_log_paths = sorted(logs_dir.glob("audit_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    summaries = [summary for path in audit_log_paths[:limit] if (summary := _extract_audit_log_summary(path)) is not None]
    persisted_batches = store.fetch_existing_assessment_batches(summary["batchNo"] for summary in summaries)

    return [
        {
            "id": summary["batchNo"],
            **summary,
            "persistedToDatabase": summary["batchNo"] in persisted_batches,
        }
        for summary in summaries
    ]


def get_process_dashboard() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresRiskTrustStore(settings.db)
    dashboard = store.fetch_process_dashboard()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    dashboard["executionLogs"] = _load_execution_logs(store, logs_dir)
    return dashboard


def get_process_document_detail(document_no: str, assessment_batch_no: str | None = None) -> dict[str, Any] | None:
    _, settings = _load_runtime_settings()
    store = PostgresRiskTrustStore(settings.db)
    return store.fetch_process_document_detail(
        document_no=document_no,
        assessment_batch_no=assessment_batch_no,
    )
