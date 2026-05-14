#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.flows.personnel_profile_change_audit_flow import PersonnelProfileChangeAuditFlow  # noqa: E402
from automation.pages.home_page import HomePage  # noqa: E402
from automation.pages.login_page import LoginPage  # noqa: E402
from automation.utils.config_loader import load_local_auth, load_selectors, load_settings  # noqa: E402
from automation.utils.logger import setup_logger  # noqa: E402
from automation.utils.login_resilience import ensure_login_with_retry  # noqa: E402
from automation.utils.playwright_helpers import timestamp_slug  # noqa: E402


DEFAULT_CONFIG_PATH = "automation/config/settings.prod.yaml"
DEFAULT_CREDENTIALS_PATH = "automation/config/credentials.prod.local.yaml"
DEFAULT_SELECTORS_PATH = "automation/config/selectors.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample personnel profile change audit documents")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Settings YAML path")
    parser.add_argument("--credentials", default=DEFAULT_CREDENTIALS_PATH, help="Credentials YAML path")
    parser.add_argument("--selectors", default=DEFAULT_SELECTORS_PATH, help="Selectors YAML path")
    parser.add_argument("--limit", type=int, default=20, help="How many documents to sample from the top of the list")
    parser.add_argument("--page-size", type=int, default=100, help="Target list pagination size")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    return parser.parse_args()


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def build_context(playwright, settings, state_file: Path):
    browser = playwright.chromium.launch(
        headless=not settings.browser.headed,
        slow_mo=settings.browser.slow_mo_ms,
    )
    context_kwargs: dict[str, Any] = {
        "ignore_https_errors": settings.browser.ignore_https_errors,
        "viewport": {"width": 1440, "height": 900},
        "accept_downloads": True,
    }
    if state_file.exists():
        context_kwargs["storage_state"] = str(state_file)
    context = browser.new_context(**context_kwargs)
    context.set_default_timeout(settings.browser.timeout_ms)
    context.set_default_navigation_timeout(settings.browser.navigation_timeout_ms)
    return browser, context


def apply_local_credentials(settings, credentials_path: Path) -> None:
    try:
        credentials = load_local_auth(credentials_path)
    except FileNotFoundError:
        return
    if not settings.auth.username.strip():
        settings.auth.username = credentials.get("username", "").strip()
    if not settings.auth.password.strip():
        settings.auth.password = credentials.get("password", "").strip()


def ensure_session(context, settings, selectors, logger, state_file: Path) -> None:
    page = context.new_page()
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
    home_page.open()
    if not login_page.is_logged_in():
        page = ensure_login_with_retry(
            login_page=login_page,
            username=settings.auth.username.strip(),
            password=settings.auth.password.strip(),
            require_manual_captcha=settings.auth.require_manual_captcha,
            retries=max(settings.runtime.retries, 0),
            wait_sec=max(settings.runtime.retry_wait_sec, 0.0),
            bound_pages=[login_page, home_page],
            retry_fn=lambda fn, retries, wait_sec: _retry_call(fn, retries=retries, wait_sec=wait_sec),
        )
        login_page.set_page(page)
        home_page.set_page(page)
        context.storage_state(path=str(state_file))
        logger.info("Auth state refreshed: %s", state_file)
    else:
        logger.info("Reused existing auth state: %s", state_file)
    page.close()


def _retry_call(fn, retries: int, wait_sec: float):
    attempt = 0
    while True:
        try:
            return fn()
        except Exception:  # noqa: BLE001
            if attempt >= retries:
                raise
            attempt += 1
            import time

            time.sleep(wait_sec)


def summarize_samples(payload: dict[str, Any]) -> str:
    list_rows = payload.get("list_rows", [])
    documents = [doc for doc in payload.get("documents", []) if not doc.get("error")]
    failed_documents = [doc for doc in payload.get("documents", []) if doc.get("error")]

    status_counter: Counter[str] = Counter()
    document_order_lines: list[str] = []
    section_counter: Counter[str] = Counter()
    section_prefix_counter: Counter[str] = Counter()
    table_header_counter: Counter[str] = Counter()
    table_title_counter: Counter[str] = Counter()
    attachment_docs: list[tuple[str, int, list[str]]] = []

    for row in list_rows:
        document_no = str(row.get("单据编号") or "").strip()
        status = _extract_status_from_row(row)
        applicant = _extract_applicant_from_row(row)
        if status:
            status_counter[status] += 1
        document_order_lines.append(f"- `{document_no}` {applicant} / {status}".rstrip(" /"))

    for doc in documents:
        document_no = str(doc.get("document_no") or "")
        for title in doc.get("section_titles", []):
            normalized = str(title).strip()
            if not normalized:
                continue
            section_counter[normalized] += 1
            section_prefix_counter[_strip_trailing_digits(normalized)] += 1
        for table in doc.get("tables", []):
            headers = [str(item).strip() for item in table.get("headers", []) if str(item).strip()]
            if headers:
                table_header_counter[" | ".join(headers)] += 1
            title = str(table.get("title") or "").strip()
            if title:
                table_title_counter[title] += 1
        attachment_names = [str(item).strip() for item in doc.get("attachment_names", []) if str(item).strip()]
        if attachment_names:
            attachment_docs.append((document_no, len(attachment_names), attachment_names[:5]))

    lines: list[str] = []
    lines.append("# 310 采样汇总")
    lines.append("")
    lines.append(f"- 采样时间: {payload.get('sampled_at', '')}")
    lines.append(f"- 入口路径: {payload.get('entry_path', '')}")
    lines.append(f"- 列表分页: {payload.get('page_size', '')}条/页")
    lines.append(f"- 列表目标样本数: {payload.get('limit', '')}")
    lines.append(f"- 成功采样: {len(documents)}")
    lines.append(f"- 失败采样: {len(failed_documents)}")
    lines.append("")
    lines.append("## 列表前 20 单")
    lines.extend(document_order_lines[:20] or ["- 无"])
    lines.append("")
    lines.append("## 列表状态分布")
    if status_counter:
        for status, count in status_counter.most_common():
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- 未识别")
    lines.append("")
    lines.append("## 页面结构规律")
    if section_prefix_counter:
        for title, count in section_prefix_counter.most_common(12):
            lines.append(f"- 区段前缀 `{title}` 出现 {count} 次")
    else:
        lines.append("- 未识别到稳定区段标题")
    lines.append("")
    lines.append("## 表格头规律")
    if table_header_counter:
        for header_line, count in table_header_counter.most_common(10):
            lines.append(f"- `{header_line}` 出现 {count} 次")
    else:
        lines.append("- 未识别到表格头")
    lines.append("")
    lines.append("## 附件规律")
    if attachment_docs:
        lines.append(f"- 含可见附件文件名的单据数: {len(attachment_docs)}")
        for document_no, count, names in attachment_docs[:10]:
            lines.append(f"- `{document_no}` 可见附件 {count} 个: {', '.join(names)}")
    else:
        lines.append("- 本轮采样未识别到可见附件文件名")
    lines.append("")
    lines.append("## 失败样本")
    if failed_documents:
        for doc in failed_documents:
            lines.append(f"- `{doc.get('document_no', '')}`: {doc.get('error', '')}")
    else:
        lines.append("- 无")
    lines.append("")
    lines.append("## 采集方案建议")
    lines.append("- 入口固定为左上角九宫格菜单 -> 最近使用 -> 人员档案信息变更申请。")
    lines.append("- 列表先统一切换到 100 条/页，再按当前排序自上而下读取前 N 单。")
    lines.append("- 详情页采用区段级采集，不把字段写死成单一固定表头。")
    lines.append("- 区段下如识别到附件文件名或下载控件，按 `automation/downloads/personnel_profile_change_audit/<单据编号>/` 落盘。")
    lines.append("- 首版落库建议先用主表 + 区段表 + 附件表，等样本稳定后再考虑业务宽表。")
    return "\n".join(lines) + "\n"


def _extract_status_from_row(row: dict[str, Any]) -> str:
    for value in row.values():
        normalized = str(value or "").strip()
        if normalized in {"已提交", "审批中", "已废弃", "已完成", "已驳回"}:
            return normalized
    return ""


def _extract_applicant_from_row(row: dict[str, Any]) -> str:
    for key, value in row.items():
        key_text = str(key or "").strip()
        value_text = str(value or "").strip()
        if not value_text:
            continue
        if any(marker in key_text for marker in ("变更人", "申请人", "发起人", "创建人")):
            return value_text
    for value in row.values():
        value_text = str(value or "").strip()
        if value_text and not value_text.isdigit() and not value_text.startswith("AM-") and not re_search_status(value_text):
            return value_text
    return ""


def re_search_status(value: str) -> bool:
    return value in {"已提交", "审批中", "已废弃", "已完成", "已驳回"}


def _strip_trailing_digits(value: str) -> str:
    return value.rstrip("0123456789").strip() or value


def main() -> int:
    args = parse_args()
    config_path = resolve_path(args.config)
    credentials_path = resolve_path(args.credentials)
    selectors_path = resolve_path(args.selectors)

    settings = load_settings(config_path)
    apply_local_credentials(settings, credentials_path)
    selectors = load_selectors(selectors_path)

    if args.headed:
        settings.browser.headed = True
    if args.headless:
        settings.browser.headed = False

    logs_dir = resolve_path(settings.runtime.logs_dir)
    shots_dir = resolve_path(settings.runtime.screenshots_dir)
    state_file = resolve_path(settings.runtime.state_file)
    logger = setup_logger(logs_dir)

    logger.info("Sampling config=%s credentials=%s selectors=%s", config_path, credentials_path, selectors_path)
    logger.info("Sampling limit=%s page_size=%s headed=%s", args.limit, args.page_size, settings.browser.headed)

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        logger.error("Missing dependency: playwright")
        return 2

    sampled_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sample_id = timestamp_slug()
    payload: dict[str, Any] = {
        "sampled_at": sampled_at,
        "sample_id": sample_id,
        "entry_path": "左上角九宫格菜单 -> 最近使用 -> 人员档案信息变更申请",
        "page_size": args.page_size,
        "limit": args.limit,
        "list_headers": [],
        "list_rows": [],
        "documents": [],
    }

    with sync_playwright() as playwright:
        browser, context = build_context(playwright, settings, state_file)
        try:
            ensure_session(context, settings, selectors, logger, state_file)

            list_page = context.new_page()
            list_flow = PersonnelProfileChangeAuditFlow(
                page=list_page,
                logger=logger,
                timeout_ms=settings.browser.timeout_ms,
                home_url=settings.app.home_url,
            )
            list_flow.open_module_page(page_size=args.page_size)
            list_snapshot = list_flow.collect_list_rows(limit=args.limit)
            payload["list_headers"] = list_snapshot.get("headers", [])
            payload["list_rows"] = list_snapshot.get("rows", [])
            logger.info("Collected list rows: %s", len(payload['list_rows']))
            list_page.close()

            for index, row in enumerate(payload["list_rows"], start=1):
                document_no = str(row.get("单据编号") or "").strip()
                if not document_no:
                    continue
                logger.info("Sampling document %s/%s: %s", index, len(payload["list_rows"]), document_no)
                page = context.new_page()
                flow = PersonnelProfileChangeAuditFlow(
                    page=page,
                    logger=logger,
                    timeout_ms=settings.browser.timeout_ms,
                    home_url=settings.app.home_url,
                )
                try:
                    flow.open_module_page(page_size=args.page_size)
                    flow.open_document(document_no)
                    doc_sample = flow.collect_document_sample(document_no=document_no, screenshots_dir=shots_dir)
                    payload["documents"].append(doc_sample)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Failed to sample document %s: %s", document_no, exc)
                    payload["documents"].append(
                        {
                            "document_no": document_no,
                            "error": str(exc),
                        }
                    )
                finally:
                    page.close()
        finally:
            context.close()
            browser.close()

    json_path = logs_dir / f"personnel_profile_change_audit_samples_{sample_id}.json"
    summary_path = logs_dir / f"personnel_profile_change_audit_summary_{sample_id}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_text = summarize_samples(payload)
    summary_path.write_text(summary_text, encoding="utf-8")
    logger.info("Sample JSON: %s", json_path)
    logger.info("Sample summary: %s", summary_path)
    print(str(json_path))
    print(str(summary_path))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
