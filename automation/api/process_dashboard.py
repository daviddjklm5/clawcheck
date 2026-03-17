from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import traceback
import re
from typing import Any

from playwright.sync_api import sync_playwright

from automation.api.config_summary import REPO_ROOT, _load_runtime_settings
from automation.api.audit_workbench import get_audit_task_overview
from automation.db.postgres import PostgresPermissionStore, PostgresRiskTrustStore
from automation.flows.document_approval_flow import DocumentApprovalFlow
from automation.pages.home_page import HomePage
from automation.pages.login_page import LoginPage
from automation.utils.config_loader import load_local_auth, load_selectors

_BATCH_NO_PATTERN = re.compile(r'"assessment_batch_no"\s*:\s*"([^"]+)"')
_VERSION_PATTERN = re.compile(r'"assessment_version"\s*:\s*"([^"]+)"')
_DOCUMENT_COUNT_PATTERN = re.compile(r'"document_count"\s*:\s*(\d+)')
_DETAIL_COUNT_PATTERN = re.compile(r'"detail_count"\s*:\s*(\d+)')
_DOCUMENT_NO_PATTERN = re.compile(r'"document_no"\s*:\s*"([^"]+)"')
_AUDIT_LOG_FILENAME_PATTERN = re.compile(r"audit_(\d{8})_(\d{6})$")
DEFAULT_CREDENTIALS_PATH = REPO_ROOT / "automation/config/credentials.local.yaml"
PROD_CREDENTIALS_PATH = REPO_ROOT / "automation/config/credentials.prod.local.yaml"
SELECTORS_PATH = REPO_ROOT / "automation/config/selectors.yaml"


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


def approve_process_document(
    document_no: str,
    action: str,
    approval_opinion: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    if action != "approve":
        raise ValueError(f"暂不支持审批动作 {action!r}，当前仅支持 'approve'")

    settings_path, settings = _load_runtime_settings()
    credentials_path = _apply_runtime_auth(settings_path, settings)
    selectors = load_selectors(SELECTORS_PATH)
    logs_dir = _resolve_runtime_path(settings.runtime.logs_dir)
    screenshots_dir = _resolve_runtime_path(settings.runtime.screenshots_dir)
    state_file = _resolve_runtime_path(settings.runtime.state_file)

    logs_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now()
    timestamp_slug = started_at.strftime("%Y%m%d_%H%M%S")
    safe_document_no = re.sub(r"[^A-Za-z0-9._-]+", "_", document_no).strip("_") or "document"
    log_path = logs_dir / f"approval_{timestamp_slug}_{safe_document_no}.json"
    screenshot_path = screenshots_dir / f"approval_error_{timestamp_slug}_{safe_document_no}.png"

    execution_log: dict[str, Any] = {
        "request": {
            "documentNo": document_no,
            "action": action,
            "approvalOpinion": approval_opinion,
            "dryRun": dry_run,
        },
        "runtime": {
            "settingsFile": _to_repo_relative(settings_path),
            "credentialsFile": _to_repo_relative(credentials_path),
            "selectorsFile": _to_repo_relative(SELECTORS_PATH),
            "stateFile": _to_repo_relative(state_file),
        },
        "events": [],
    }

    response_payload: dict[str, Any] | None = None

    def flush_execution_log() -> None:
        if response_payload is not None:
            execution_log["response"] = response_payload
        log_path.write_text(
            json.dumps(execution_log, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_event(message: str, **extra: Any) -> None:
        event = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": message,
        }
        if extra:
            event.update(extra)
        execution_log["events"].append(event)
        flush_execution_log()

    page = None
    browser = None
    context = None
    response_payload = {
        "documentNo": document_no,
        "action": action,
        "ehrDecision": "同意",
        "ehrSubmitLabel": "提交",
        "approvalOpinion": approval_opinion,
        "dryRun": dry_run,
        "status": "running",
        "startedAt": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "finishedAt": "",
        "logFile": _to_repo_relative(log_path),
        "screenshotFile": "",
        "confirmationType": "",
        "confirmationMessage": "",
        "message": "",
    }
    flush_execution_log()
    logger = logging.getLogger("approval_api")

    permission_store = PostgresPermissionStore(settings.db)
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
        if todo_process_status == "已处理":
            response_payload["status"] = "failed"
            response_payload["finishedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            response_payload["message"] = (
                "该单据最近一次待办同步结果为“已处理”，当前账号待办列表中未找到。"
                "若怀疑单据已驳回后重新提交，请先点击“同步待办状态”后再重试。"
            )
            flush_execution_log()
            raise ValueError(response_payload["message"])

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=not settings.browser.headed,
                slow_mo=settings.browser.slow_mo_ms,
            )
            context_kwargs: dict[str, Any] = {
                "ignore_https_errors": settings.browser.ignore_https_errors,
                "viewport": {"width": 1600, "height": 960},
                "accept_downloads": False,
            }
            if state_file.exists():
                context_kwargs["storage_state"] = str(state_file)

            context = browser.new_context(**context_kwargs)
            context.set_default_timeout(settings.browser.timeout_ms)
            context.set_default_navigation_timeout(settings.browser.navigation_timeout_ms)
            page = context.new_page()
            add_event("browser_context_ready", stateFile=_to_repo_relative(state_file))

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
            try:
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
                    login_page.login(
                        username=settings.auth.username.strip(),
                        password=settings.auth.password.strip(),
                        require_manual_captcha=False,
                    )
                    context.storage_state(path=str(state_file))
                    add_event("login_refreshed", stateFile=_to_repo_relative(state_file))
                else:
                    add_event("reuse_existing_login_state")

                add_event("approval_flow_started", documentNo=document_no, dryRun=dry_run)
                flow_result = approval_flow.execute_approve(
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
                response_payload["message"] = (
                    "已完成 EHR 写入验证，未点击提交。"
                    if dry_run
                    else (
                        response_payload["confirmationMessage"]
                        or "提交动作已发出，但当前未拿到强成功回执。请先不要重复点击批准。"
                    )
                    if flow_status == "submitted_pending_confirmation"
                    else "EHR 已完成同意并提交。"
                )
                if not dry_run and flow_status == "succeeded":
                    try:
                        permission_store.update_single_todo_process_status(document_no, "已处理")
                        add_event("todo_process_status_updated", documentNo=document_no, todoProcessStatus="已处理")
                    except Exception as exc:  # noqa: BLE001
                        add_event("todo_process_status_update_failed", error=str(exc), documentNo=document_no)
                execution_log["result"] = flow_result
                execution_log["response"] = response_payload
            except Exception:
                _capture_failure_screenshot(
                    page=page,
                    screenshot_path=screenshot_path,
                    response_payload=response_payload,
                    add_event=add_event,
                )
                raise
    except Exception as exc:  # noqa: BLE001
        response_payload["status"] = "failed"
        response_payload["finishedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        response_payload["message"] = (
            f"审批执行失败：{exc}。详见 {response_payload['logFile']}"
        )

        execution_log["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        execution_log["response"] = response_payload
        log_path.write_text(
            json.dumps(execution_log, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise RuntimeError(response_payload["message"]) from exc
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:  # noqa: BLE001
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:  # noqa: BLE001
                pass

    flush_execution_log()
    return response_payload
