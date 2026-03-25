from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import traceback
import re
import time
from typing import Any

from automation.api.approval_browser_session import (
    acquire_approval_browser_session,
    release_approval_browser_session,
)
from automation.api.config_summary import REPO_ROOT, _load_runtime_settings
from automation.api.process_todo_sync import run_process_todo_sync_now
from automation.api.audit_workbench import get_audit_task_overview
from automation.db.postgres import PostgresPermissionStore, PostgresRiskTrustStore
from automation.flows.document_approval_flow import DocumentApprovalFlow
from automation.pages.home_page import HomePage
from automation.pages.login_page import LoginPage
from automation.utils.config_loader import load_local_auth, load_selectors
from automation.utils.login_resilience import ensure_login_with_retry

_BATCH_NO_PATTERN = re.compile(r'"assessment_batch_no"\s*:\s*"([^"]+)"')
_VERSION_PATTERN = re.compile(r'"assessment_version"\s*:\s*"([^"]+)"')
_DOCUMENT_COUNT_PATTERN = re.compile(r'"document_count"\s*:\s*(\d+)')
_DETAIL_COUNT_PATTERN = re.compile(r'"detail_count"\s*:\s*(\d+)')
_DOCUMENT_NO_PATTERN = re.compile(r'"document_no"\s*:\s*"([^"]+)"')
_AUDIT_LOG_FILENAME_PATTERN = re.compile(r"audit_(\d{8})_(\d{6})$")
DEFAULT_CREDENTIALS_PATH = REPO_ROOT / "automation/config/credentials.local.yaml"
PROD_CREDENTIALS_PATH = REPO_ROOT / "automation/config/credentials.prod.local.yaml"
SELECTORS_PATH = REPO_ROOT / "automation/config/selectors.yaml"
_APPROVAL_ACTION_CONFIG: dict[str, dict[str, str]] = {
    "approve": {
        "ehrDecision": "同意",
        "submitActionLabel": "批准",
        "successMessage": "EHR 已完成同意并提交。",
        "todoProcessStatusOnSucceeded": "已处理",
    },
    "reject": {
        "ehrDecision": "驳回至已选节点",
        "submitActionLabel": "驳回",
        "successMessage": "EHR 已完成驳回并提交。",
        "todoProcessStatusOnSucceeded": "已驳回",
    },
}


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


def _resolve_credentials_path(settings_path: Path) -> Path:
    if settings_path.name.endswith(".prod.yaml"):
        return PROD_CREDENTIALS_PATH
    return DEFAULT_CREDENTIALS_PATH


def _apply_runtime_auth(settings_path: Path, settings) -> Path:
    credentials_path = _resolve_credentials_path(settings_path)
    if credentials_path.exists():
        local_auth = load_local_auth(credentials_path)
        if local_auth.get("username"):
            settings.auth.username = local_auth["username"]
        if local_auth.get("password"):
            settings.auth.password = local_auth["password"]

    settings.auth.username = os.getenv("IERP_USERNAME", settings.auth.username)
    settings.auth.password = os.getenv("IERP_PASSWORD", settings.auth.password)
    return credentials_path


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


def get_process_workbench() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresRiskTrustStore(settings.db)
    dashboard = store.fetch_process_workbench()
    dashboard.update(get_audit_task_overview())
    return dashboard


def get_process_analysis_dashboard() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresRiskTrustStore(settings.db)
    dashboard = store.fetch_process_analysis_dashboard()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    dashboard["executionLogs"] = _load_execution_logs(store, logs_dir)
    dashboard.update(get_audit_task_overview())
    return dashboard


def get_process_dashboard() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresRiskTrustStore(settings.db)
    dashboard = store.fetch_process_dashboard()
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    dashboard["executionLogs"] = _load_execution_logs(store, logs_dir)
    dashboard.update(get_audit_task_overview())
    return dashboard


def get_process_document_detail(document_no: str, assessment_batch_no: str | None = None) -> dict[str, Any] | None:
    _, settings = _load_runtime_settings()
    store = PostgresRiskTrustStore(settings.db)
    return store.fetch_process_document_detail(
        document_no=document_no,
        assessment_batch_no=assessment_batch_no,
    )


def _capture_failure_screenshot(
    page: Any,
    screenshot_path: Path,
    response_payload: dict[str, Any],
    add_event: Callable[..., None],
) -> None:
    if page is None:
        return

    try:
        if hasattr(page, "is_closed") and page.is_closed():
            add_event("page_already_closed_before_screenshot")
            return
    except Exception as exc:  # noqa: BLE001
        add_event("page_closed_probe_failed", error=str(exc))

    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        response_payload["screenshotFile"] = _to_repo_relative(screenshot_path)
        add_event("error_screenshot_saved", screenshotFile=response_payload["screenshotFile"])
    except Exception as exc:  # noqa: BLE001
        add_event("screenshot_failed", error=str(exc))


def _prepare_approval_runtime(headed: bool | None = None) -> tuple[Path, Any, Path, dict[str, Any], Path, Path, Path]:
    settings_path, settings = _load_runtime_settings()
    if headed is not None:
        settings.browser.headed = bool(headed)
    credentials_path = _apply_runtime_auth(settings_path, settings)
    selectors = load_selectors(SELECTORS_PATH)
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    screenshots_dir = _resolve_runtime_path(settings.runtime.screenshots_dir)
    state_file = _resolve_runtime_path(settings.runtime.state_file)

    logs_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    return settings_path, settings, credentials_path, selectors, logs_dir, screenshots_dir, state_file


def _build_approval_artifact_paths(
    *,
    logs_dir: Path,
    screenshots_dir: Path,
    started_at: datetime,
    document_no: str,
) -> tuple[Path, Path]:
    timestamp_slug = started_at.strftime("%Y%m%d_%H%M%S")
    safe_document_no = re.sub(r"[^A-Za-z0-9._-]+", "_", document_no).strip("_") or "document"
    log_path = logs_dir / f"approval_{timestamp_slug}_{safe_document_no}.json"
    screenshot_path = screenshots_dir / f"approval_error_{timestamp_slug}_{safe_document_no}.png"
    return log_path, screenshot_path


def _normalize_document_nos(document_nos: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_document_no in document_nos:
        document_no = str(raw_document_no or "").strip()
        if not document_no or document_no in seen:
            continue
        normalized.append(document_no)
        seen.add(document_no)
    return normalized


def _extract_generated_reject_opinion_lines(detail_payload: dict[str, Any] | None) -> list[str]:
    if not detail_payload:
        return []
    feedback_overview = detail_payload.get("feedbackOverview")
    if not isinstance(feedback_overview, dict):
        return []
    feedback_groups = feedback_overview.get("feedbackGroups")
    if not isinstance(feedback_groups, list):
        return []

    lines: list[str] = []
    for group in feedback_groups:
        if not isinstance(group, dict):
            continue
        raw_lines = group.get("summaryLines")
        if not isinstance(raw_lines, list) or not raw_lines:
            raw_lines = [group.get("summary")]
        for raw_line in raw_lines:
            normalized_line = str(raw_line or "").strip()
            if normalized_line and normalized_line not in lines:
                lines.append(normalized_line)
    return lines


def _resolve_batch_approval_opinion(
    *,
    store: PostgresRiskTrustStore,
    document_no: str,
    action: str,
) -> str:
    if action == "approve":
        return "通过"

    detail_payload = store.fetch_process_document_detail(document_no=document_no)
    generated_lines = _extract_generated_reject_opinion_lines(detail_payload)
    if not generated_lines:
        raise ValueError(
            f"单据 {document_no} 未命中可用的“生成驳回意见”摘要，请先检查风险总览是否已产出内容。"
        )
    return "\n".join(generated_lines)


def _ensure_approval_page(
    *,
    page: Any,
    context: Any,
    add_event: Callable[..., None],
) -> Any:
    try:
        if page is not None and not page.is_closed():
            return page
    except Exception as exc:  # noqa: BLE001
        add_event("approval_page_probe_failed", error=str(exc))

    recreated_page = context.new_page()
    add_event("approval_page_recreated")
    return recreated_page


def _build_failed_approval_response(
    *,
    document_no: str,
    normalized_action: str,
    action_config: dict[str, str],
    approval_opinion: str,
    dry_run: bool,
    message: str,
    started_at: datetime | None = None,
    log_file: str = "",
    screenshot_file: str = "",
) -> dict[str, Any]:
    finished_at = datetime.now()
    effective_started_at = started_at or finished_at
    return {
        "documentNo": document_no,
        "action": normalized_action,
        "ehrDecision": action_config["ehrDecision"],
        "ehrSubmitLabel": "提交",
        "approvalOpinion": approval_opinion,
        "dryRun": dry_run,
        "status": "failed",
        "startedAt": effective_started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "finishedAt": finished_at.strftime("%Y-%m-%d %H:%M:%S"),
        "durationMs": round(max((finished_at - effective_started_at).total_seconds(), 0.0) * 1000, 1),
        "logFile": log_file,
        "screenshotFile": screenshot_file,
        "confirmationType": "",
        "confirmationMessage": "",
        "message": message,
    }


def _execute_document_approval_in_active_session(
    *,
    page: Any,
    context: Any,
    settings: Any,
    selectors: dict[str, Any],
    logger: logging.Logger,
    state_file: Path,
    permission_store: PostgresPermissionStore,
    document_no: str,
    normalized_action: str,
    approval_opinion: str,
    dry_run: bool,
    action_config: dict[str, str],
    add_event: Callable[..., None],
    response_payload: dict[str, Any],
    started_perf: float,
) -> tuple[dict[str, Any], Any]:
    try:
        sync_state = permission_store.fetch_document_sync_states([document_no]).get(document_no, {})
    except Exception as exc:  # noqa: BLE001
        sync_state = {}
        add_event("todo_process_status_probe_failed", error=str(exc))
    else:
        todo_process_status = str(sync_state.get("todo_process_status") or "").strip()
        todo_status_updated_at = str(sync_state.get("todo_status_updated_at") or "").strip()
        if todo_process_status:
            add_event(
                "todo_process_status_probed",
                documentNo=document_no,
                todoProcessStatus=todo_process_status,
                todoStatusUpdatedAt=todo_status_updated_at,
            )
        if todo_process_status in {"已处理", "已驳回"}:
            response_payload["status"] = "failed"
            response_payload["finishedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            response_payload["durationMs"] = round((time.perf_counter() - started_perf) * 1000, 1)
            response_payload["message"] = (
                f"该单据最近一次待办同步结果为“{todo_process_status}”，当前账号待办列表中未找到。"
                "如怀疑单据已驳回后重新提交，请先点击“同步待办状态”后再重试。"
            )
            raise ValueError(response_payload["message"])

    page = _ensure_approval_page(page=page, context=context, add_event=add_event)
    home_page = HomePage(
        home_url=settings.app.home_url,
        page=page,
        selectors=selectors,
        logger=logger,
        timeout_ms=settings.browser.timeout_ms,
    )
    login_page = LoginPage(
        home_url=settings.app.home_url,
        page=page,
        selectors=selectors,
        logger=logger,
        timeout_ms=settings.browser.timeout_ms,
    )
    approval_flow = DocumentApprovalFlow(
        page=page,
        logger=logger,
        timeout_ms=settings.browser.timeout_ms,
        home_url=settings.app.home_url,
        event_callback=add_event,
    )

    add_event("open_home_page", homeUrl=settings.app.home_url)
    home_page.open()
    try:
        home_page.wait_ready()
        add_event("home_ready")
    except Exception as exc:  # noqa: BLE001
        add_event("home_ready_probe_failed", error=str(exc))

    if not login_page.is_logged_in():
        if not settings.auth.username.strip() or not settings.auth.password.strip():
            raise RuntimeError("当前登录态失效，且未配置可用账号密码，无法执行审批。")
        add_event("login_required")
        page = ensure_login_with_retry(
            login_page=login_page,
            username=settings.auth.username.strip(),
            password=settings.auth.password.strip(),
            require_manual_captcha=False,
            retries=settings.runtime.retries,
            wait_sec=settings.runtime.retry_wait_sec,
            bound_pages=[login_page, home_page, approval_flow],
            event_callback=add_event,
        )
        context = page.context
        home_page.set_page(page)
        login_page.set_page(page)
        approval_flow.set_page(page)
        context.storage_state(path=str(state_file))
        add_event("login_refreshed", stateFile=_to_repo_relative(state_file))
    else:
        add_event("reuse_existing_login_state")

    add_event(
        "approval_flow_started",
        documentNo=document_no,
        action=normalized_action,
        dryRun=dry_run,
    )
    flow_result = approval_flow.execute_action(
        action=normalized_action,
        document_no=document_no,
        approval_opinion=approval_opinion,
        dry_run=dry_run,
    )
    add_event("approval_flow_finished", result=flow_result)

    flow_status = str(flow_result.get("status") or "succeeded")
    response_payload["ehrSubmitLabel"] = str(flow_result.get("submitLabel") or "提交")
    response_payload["confirmationType"] = str(flow_result.get("confirmationType") or "")
    response_payload["confirmationMessage"] = str(flow_result.get("confirmationMessage") or "")
    response_payload["status"] = flow_status
    response_payload["finishedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response_payload["durationMs"] = round((time.perf_counter() - started_perf) * 1000, 1)
    response_payload["message"] = (
        "已完成 EHR 写入验证，未点击提交。"
        if dry_run
        else (
            response_payload["confirmationMessage"]
            or (
                "提交动作已发出，但当前未拿到强成功回执。"
                f"请先不要重复点击{action_config['submitActionLabel']}。"
            )
        )
        if flow_status == "submitted_pending_confirmation"
        else action_config["successMessage"]
    )
    if not dry_run and flow_status == "succeeded":
        try:
            final_todo_process_status = action_config["todoProcessStatusOnSucceeded"]
            permission_store.update_single_todo_process_status(document_no, final_todo_process_status)
            add_event(
                "todo_process_status_updated",
                documentNo=document_no,
                todoProcessStatus=final_todo_process_status,
            )
        except Exception as exc:  # noqa: BLE001
            add_event("todo_process_status_update_failed", error=str(exc), documentNo=document_no)
    return flow_result, page


def _run_logged_document_approval_in_active_session(
    *,
    page: Any,
    context: Any,
    settings: Any,
    selectors: dict[str, Any],
    state_file: Path,
    logs_dir: Path,
    screenshots_dir: Path,
    permission_store: PostgresPermissionStore,
    logger: logging.Logger,
    document_no: str,
    normalized_action: str,
    approval_opinion: str,
    dry_run: bool,
    action_config: dict[str, str],
    raise_on_failed: bool,
    browser_session_meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Any]:
    started_at = datetime.now()
    log_path, screenshot_path = _build_approval_artifact_paths(
        logs_dir=logs_dir,
        screenshots_dir=screenshots_dir,
        started_at=started_at,
        document_no=document_no,
    )
    execution_log: dict[str, Any] = {
        "request": {
            "documentNo": document_no,
            "action": normalized_action,
            "approvalOpinion": approval_opinion,
            "dryRun": dry_run,
            "headed": bool(settings.browser.headed),
        },
        "runtime": {
            "selectorsFile": _to_repo_relative(SELECTORS_PATH),
            "stateFile": _to_repo_relative(state_file),
        },
        "events": [],
    }
    response_payload: dict[str, Any] = {
        "documentNo": document_no,
        "action": normalized_action,
        "ehrDecision": action_config["ehrDecision"],
        "ehrSubmitLabel": "提交",
        "approvalOpinion": approval_opinion,
        "dryRun": dry_run,
        "status": "running",
        "startedAt": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "finishedAt": "",
        "durationMs": 0.0,
        "logFile": _to_repo_relative(log_path),
        "screenshotFile": "",
        "confirmationType": "",
        "confirmationMessage": "",
        "message": "",
    }
    started_perf = time.perf_counter()
    last_event_perf = started_perf

    def flush_execution_log() -> None:
        execution_log["response"] = response_payload
        log_path.write_text(
            json.dumps(execution_log, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_event(message: str, **extra: Any) -> None:
        nonlocal last_event_perf
        now_dt = datetime.now()
        now_perf = time.perf_counter()
        event = {
            "timestamp": now_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "elapsedMs": round((now_perf - started_perf) * 1000, 1),
            "deltaMs": round((now_perf - last_event_perf) * 1000, 1),
            "message": message,
        }
        last_event_perf = now_perf
        if extra:
            event.update(extra)
        execution_log["events"].append(event)
        flush_execution_log()

    flush_execution_log()
    if browser_session_meta is not None:
        add_event(
            "browser_context_ready",
            stateFile=_to_repo_relative(state_file),
            sessionReused=bool(browser_session_meta.get("reused", False)),
            sessionAgeMs=browser_session_meta.get("sessionAgeMs", 0.0),
            sessionIdleMs=browser_session_meta.get("sessionIdleMs", 0.0),
            pageRecreated=bool(browser_session_meta.get("pageRecreated", False)),
        )

    try:
        flow_result, page = _execute_document_approval_in_active_session(
            page=page,
            context=context,
            settings=settings,
            selectors=selectors,
            logger=logger,
            state_file=state_file,
            permission_store=permission_store,
            document_no=document_no,
            normalized_action=normalized_action,
            approval_opinion=approval_opinion,
            dry_run=dry_run,
            action_config=action_config,
            add_event=add_event,
            response_payload=response_payload,
            started_perf=started_perf,
        )
        execution_log["result"] = flow_result
        flush_execution_log()
        return response_payload, page
    except Exception as exc:  # noqa: BLE001
        _capture_failure_screenshot(
            page=page,
            screenshot_path=screenshot_path,
            response_payload=response_payload,
            add_event=add_event,
        )
        response_payload["status"] = "failed"
        response_payload["finishedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response_payload["durationMs"] = round((time.perf_counter() - started_perf) * 1000, 1)
        response_payload["message"] = f"审批执行失败：{exc}。详见 {response_payload['logFile']}"
        execution_log["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        flush_execution_log()
        if raise_on_failed:
            raise RuntimeError(response_payload["message"]) from exc
        return response_payload, page


def approve_process_document(
    document_no: str,
    action: str,
    approval_opinion: str,
    dry_run: bool = False,
    headed: bool | None = None,
) -> dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    action_config = _APPROVAL_ACTION_CONFIG.get(normalized_action)
    if action_config is None:
        raise ValueError(
            f"暂不支持审批动作 {action!r}，当前仅支持 {sorted(_APPROVAL_ACTION_CONFIG)}"
        )

    _, settings, _, selectors, logs_dir, screenshots_dir, state_file = _prepare_approval_runtime(headed=headed)
    logger = logging.getLogger("approval_api")
    permission_store = PostgresPermissionStore(settings.db)

    page = None
    context = None
    browser_session_acquired = False
    response_payload: dict[str, Any] | None = None

    try:
        _, context, page, browser_session_meta = acquire_approval_browser_session(
            settings=settings,
            state_file=state_file,
            event_callback=None,
        )
        browser_session_acquired = True
        response_payload, page = _run_logged_document_approval_in_active_session(
            page=page,
            context=context,
            settings=settings,
            selectors=selectors,
            state_file=state_file,
            logs_dir=logs_dir,
            screenshots_dir=screenshots_dir,
            permission_store=permission_store,
            logger=logger,
            document_no=document_no,
            normalized_action=normalized_action,
            approval_opinion=approval_opinion,
            dry_run=dry_run,
            action_config=action_config,
            raise_on_failed=True,
            browser_session_meta=browser_session_meta,
        )
    except Exception as exc:  # noqa: BLE001
        if response_payload is not None:
            raise RuntimeError(response_payload["message"]) from exc
        message = str(exc)
        if message.startswith(("Approval execution failed:", "审批执行失败：")):
            raise RuntimeError(message) from exc
        raise RuntimeError(f"Approval execution failed: {message}") from exc
    finally:
        if browser_session_acquired:
            release_approval_browser_session(
                close_session=True,
                close_reason="approval_request_finished",
            )

    return response_payload


def approve_process_documents_batch(
    document_nos: list[str],
    action: str,
    dry_run: bool = False,
    headed: bool | None = None,
) -> dict[str, Any]:
    normalized_action = str(action or "").strip().lower()
    action_config = _APPROVAL_ACTION_CONFIG.get(normalized_action)
    if action_config is None:
        raise ValueError(
            f"暂不支持审批动作 {action!r}，当前仅支持 {sorted(_APPROVAL_ACTION_CONFIG)}"
        )

    normalized_document_nos = _normalize_document_nos(document_nos)
    if not normalized_document_nos:
        raise ValueError("批量审批至少需要 1 个单据编号。")

    settings_path, settings, credentials_path, selectors, logs_dir, screenshots_dir, state_file = _prepare_approval_runtime(
        headed=headed
    )
    logger = logging.getLogger("approval_api")
    permission_store = PostgresPermissionStore(settings.db)
    store = PostgresRiskTrustStore(settings.db)

    started_at = datetime.now()
    batch_log_path = logs_dir / (
        f"approval_batch_{started_at.strftime('%Y%m%d_%H%M%S')}_{normalized_action}_{len(normalized_document_nos)}.json"
    )
    execution_log: dict[str, Any] = {
        "request": {
            "documentNos": normalized_document_nos,
            "action": normalized_action,
            "dryRun": dry_run,
            "headed": bool(settings.browser.headed),
        },
        "runtime": {
            "settingsFile": _to_repo_relative(settings_path),
            "credentialsFile": _to_repo_relative(credentials_path),
            "selectorsFile": _to_repo_relative(SELECTORS_PATH),
            "stateFile": _to_repo_relative(state_file),
        },
        "events": [],
        "results": [],
    }
    response_payload: dict[str, Any] = {
        "action": normalized_action,
        "dryRun": dry_run,
        "documentNos": normalized_document_nos,
        "totalCount": len(normalized_document_nos),
        "succeededCount": 0,
        "pendingConfirmationCount": 0,
        "failedCount": 0,
        "results": [],
        "status": "running",
        "startedAt": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "finishedAt": "",
        "durationMs": 0.0,
        "logFile": _to_repo_relative(batch_log_path),
        "message": "",
    }
    started_perf = time.perf_counter()
    last_event_perf = started_perf
    batch_results: list[dict[str, Any]] = []

    def flush_execution_log() -> None:
        execution_log["results"] = batch_results
        execution_log["response"] = response_payload
        batch_log_path.write_text(
            json.dumps(execution_log, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_event(message: str, **extra: Any) -> None:
        nonlocal last_event_perf
        now_dt = datetime.now()
        now_perf = time.perf_counter()
        event = {
            "timestamp": now_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "elapsedMs": round((now_perf - started_perf) * 1000, 1),
            "deltaMs": round((now_perf - last_event_perf) * 1000, 1),
            "message": message,
        }
        last_event_perf = now_perf
        if extra:
            event.update(extra)
        execution_log["events"].append(event)
        flush_execution_log()

    flush_execution_log()
    browser_session_acquired = False
    page = None
    context = None
    try:
        add_event(
            "batch_todo_sync_started",
            dryRun=dry_run,
            headed=bool(settings.browser.headed),
        )
        try:
            todo_sync_result = run_process_todo_sync_now(
                dry_run=dry_run,
                headed=bool(settings.browser.headed),
            )
        except Exception as exc:  # noqa: BLE001
            add_event("batch_todo_sync_failed", error=str(exc))
            raise RuntimeError(f"批量审批前同步待办状态失败：{exc}") from exc
        add_event(
            "batch_todo_sync_finished",
            status=todo_sync_result.get("status", ""),
            pendingCount=todo_sync_result.get("pendingCount", 0),
            processedCount=todo_sync_result.get("processedCount", 0),
            changedCount=todo_sync_result.get("changedCount", 0),
            dumpFile=todo_sync_result.get("dumpFile", ""),
            logFile=todo_sync_result.get("logFile", ""),
            resultMessage=todo_sync_result.get("message", ""),
        )

        _, context, page, browser_session_meta = acquire_approval_browser_session(
            settings=settings,
            state_file=state_file,
            event_callback=None,
        )
        browser_session_acquired = True
        add_event(
            "browser_context_ready",
            stateFile=_to_repo_relative(state_file),
            sessionReused=bool(browser_session_meta.get("reused", False)),
            sessionAgeMs=browser_session_meta.get("sessionAgeMs", 0.0),
            sessionIdleMs=browser_session_meta.get("sessionIdleMs", 0.0),
            pageRecreated=bool(browser_session_meta.get("pageRecreated", False)),
        )

        for index, document_no in enumerate(normalized_document_nos, start=1):
            try:
                approval_opinion = _resolve_batch_approval_opinion(
                    store=store,
                    document_no=document_no,
                    action=normalized_action,
                )
                add_event(
                    "batch_document_started",
                    index=index,
                    total=len(normalized_document_nos),
                    documentNo=document_no,
                    approvalOpinionSource="fixed_pass" if normalized_action == "approve" else "generated_reject_opinion",
                    approvalOpinionLength=len(approval_opinion),
                )
                result, page = _run_logged_document_approval_in_active_session(
                    page=page,
                    context=context,
                    settings=settings,
                    selectors=selectors,
                    state_file=state_file,
                    logs_dir=logs_dir,
                    screenshots_dir=screenshots_dir,
                    permission_store=permission_store,
                    logger=logger,
                    document_no=document_no,
                    normalized_action=normalized_action,
                    approval_opinion=approval_opinion,
                    dry_run=dry_run,
                    action_config=action_config,
                    raise_on_failed=False,
                    browser_session_meta=None,
                )
            except Exception as exc:  # noqa: BLE001
                result = _build_failed_approval_response(
                    document_no=document_no,
                    normalized_action=normalized_action,
                    action_config=action_config,
                    approval_opinion="",
                    dry_run=dry_run,
                    message=f"批量{action_config['submitActionLabel']}前置处理失败：{exc}",
                )
                add_event(
                    "batch_document_failed_before_execution",
                    index=index,
                    total=len(normalized_document_nos),
                    documentNo=document_no,
                    error=str(exc),
                )

            batch_results.append(result)
            add_event(
                "batch_document_finished",
                index=index,
                total=len(normalized_document_nos),
                documentNo=document_no,
                status=result.get("status", ""),
                logFile=result.get("logFile", ""),
                resultMessage=result.get("message", ""),
            )
    except Exception as exc:  # noqa: BLE001
        add_event("batch_request_failed", error=str(exc))
        processed_document_nos = {str(item.get("documentNo") or "").strip() for item in batch_results}
        for document_no in normalized_document_nos:
            if document_no in processed_document_nos:
                continue
            batch_results.append(
                _build_failed_approval_response(
                    document_no=document_no,
                    normalized_action=normalized_action,
                    action_config=action_config,
                    approval_opinion="",
                    dry_run=dry_run,
                    message=f"批量{action_config['submitActionLabel']}未执行：{exc}",
                )
            )
    finally:
        if browser_session_acquired:
            release_approval_browser_session(
                close_session=True,
                close_reason="batch_approval_request_finished",
            )

    succeeded_count = sum(1 for item in batch_results if item.get("status") == "succeeded")
    pending_confirmation_count = sum(
        1 for item in batch_results if item.get("status") == "submitted_pending_confirmation"
    )
    failed_count = len(batch_results) - succeeded_count - pending_confirmation_count
    response_payload["results"] = batch_results
    response_payload["succeededCount"] = succeeded_count
    response_payload["pendingConfirmationCount"] = pending_confirmation_count
    response_payload["failedCount"] = failed_count
    response_payload["finishedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response_payload["durationMs"] = round((time.perf_counter() - started_perf) * 1000, 1)

    if failed_count == 0 and pending_confirmation_count == 0:
        response_payload["status"] = "succeeded"
    elif succeeded_count == 0 and pending_confirmation_count == 0:
        response_payload["status"] = "failed"
    else:
        response_payload["status"] = "partial"

    action_label = "批量批准" if normalized_action == "approve" else "批量驳回"
    if dry_run:
        action_label = f"{action_label}连通性验证"
    status_summary_parts = [f"成功 {succeeded_count}"]
    if pending_confirmation_count > 0:
        status_summary_parts.append(f"待确认 {pending_confirmation_count}")
    status_summary_parts.append(f"失败 {failed_count}")
    response_payload["message"] = f"{action_label}完成：{'，'.join(status_summary_parts)}，共 {len(batch_results)} 条。"
    flush_execution_log()
    return response_payload
