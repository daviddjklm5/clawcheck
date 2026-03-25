from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from collections.abc import Sequence
from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from automation.utils.approval_record_helpers import derive_latest_approval_time, normalize_approval_records


TODO_HEADERS = ["单据", "单据编号", "发起人", "主题", "状态"]
DETAIL_HEADERS = ["申请类型", "角色名称", "角色编码"]
DETAIL_PREFERRED_HEADERS = ["行政组织详情", "行政组织", "角色描述", "参保单位"]
ORG_HEADERS = ["组织编码", "组织名称", "所属公司", "组织长名称"]
APPROVAL_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
DETAIL_COUNT_RE = re.compile(r"查看详情\((\d+)\)")
APPROVAL_TABPAGE_SELECTOR = "#tabpageap_approvalrecord"
APPROVAL_HEADER_WITH_NODE_RE = re.compile(r"^(?P<node_name>.*?)\s+(?P<approver_info>[^\s]+\|[^\s]+)\s+(?P<approval_action>.*?)$")
APPROVAL_HEADER_WITHOUT_NODE_RE = re.compile(r"^(?P<approver_info>[^\s]+\|[^\s]+)\s+(?P<approval_action>.*?)$")
MANUAL_ADDED_SIGN_NODE_NAME = "加签"


class PermissionCollectFlow:
    def __init__(
        self,
        page: Page,
        logger: logging.Logger,
        timeout_ms: int,
        home_url: str,
        skip_org_scope_role_codes: set[str] | None = None,
    ) -> None:
        self.page = page
        self.logger = logger
        self.timeout_ms = timeout_ms
        self.home_url = home_url
        self.skip_org_scope_role_codes = skip_org_scope_role_codes or set()
        self.current_document_tab_pageid: str | None = None
        self.current_document_tab_text = ""

    def collect(self, document_no: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        self.open_todo_list()
        todo_rows = self.extract_grid_rows(TODO_HEADERS)
        permission_rows = [row for row in todo_rows if row.get("单据") == "权限申请"]
        if document_no:
            permission_rows = [row for row in permission_rows if row.get("单据编号") == document_no]
        if limit > 0:
            permission_rows = permission_rows[:limit]

        documents: list[dict[str, Any]] = []
        document_nos = [row.get("单据编号", "").strip() for row in permission_rows if row.get("单据编号")]
        for index, current_document_no in enumerate(document_nos):
            documents.append(
                self.collect_document_from_todo(
                    document_no=current_document_no,
                    close_document_tab_after=index < len(document_nos) - 1,
                )
            )
        return documents

    def open_todo_list(self, page_size_timeout_ms: int | None = None) -> bool:
        trigger = self.page.locator("div[id^='processflexpanelap_']").filter(has_text="待办任务").first
        trigger.wait_for(state="visible", timeout=self.timeout_ms)
        trigger.click(force=True)
        return self._wait_for_todo_list_ready(page_size_timeout_ms=page_size_timeout_ms)

    def collect_document_from_todo(
        self,
        document_no: str,
        close_document_tab_after: bool = False,
    ) -> dict[str, Any]:
        self.logger.info("Collecting document: %s", document_no)
        started_at = datetime.now()
        started_ts = time.monotonic()
        self.open_document(document_no)
        document = self.collect_current_document()
        elapsed_seconds = round(time.monotonic() - started_ts, 3)
        finished_at = datetime.now()
        document["collection_started_at"] = started_at.isoformat(timespec="seconds")
        document["collection_finished_at"] = finished_at.isoformat(timespec="seconds")
        document["collection_elapsed_seconds"] = elapsed_seconds
        self.logger.info(
            "Collected document %s in %.3f seconds",
            document_no,
            elapsed_seconds,
        )
        if close_document_tab_after:
            self.close_current_document_tab(document_no)
            self.page.wait_for_timeout(200)
            self.return_to_todo_list()
        return document

    def open_document(self, document_no: str, link_timeout_ms: int | None = None) -> None:
        subject_link = self._wait_for_todo_document_link_ready(document_no, timeout_ms=link_timeout_ms)
        subject_link.click(force=True)
        self._wait_for_document_loaded(document_no)
        self._remember_current_document_tab(document_no)

    def return_to_todo_list(self, page_size_timeout_ms: int | None = None) -> bool:
        tab = self.page.locator("li[data-splitscreen-pageid$='hrobs_pc_messagecenter']").first
        tab.wait_for(state="visible", timeout=self.timeout_ms)
        tab.click(force=True)
        return self._wait_for_todo_list_ready(page_size_timeout_ms=page_size_timeout_ms)

    def collect_current_document(self, probe: dict[str, Any] | None = None) -> dict[str, Any]:
        probe = probe or self.collect_current_document_probe()
        basic_info = dict(probe.get("basic_info", {}))
        approval_records = list(probe.get("approval_records", []))
        self._wait_for_permission_detail_grid_ready(basic_info.get("document_no", ""))
        permission_details = self.extract_grid_rows(DETAIL_HEADERS)
        failed_org_scope_rows: list[dict[str, Any]] = []
        role_organization_scopes = self.extract_role_organization_scopes(
            basic_info.get("document_no", ""),
            permission_details,
            failed_rows=failed_org_scope_rows,
        )
        organization_codes = sorted(
            {
                code
                for item in role_organization_scopes
                for code in item.get("organization_codes", [])
                if isinstance(code, str) and code.strip()
            }
        )
        return {
            "basic_info": basic_info,
            "permission_details": permission_details,
            "approval_records": approval_records,
            "role_organization_scopes": role_organization_scopes,
            "organization_codes": organization_codes,
            "failed_org_scope_rows": failed_org_scope_rows,
        }

    def collect_current_document_probe(self) -> dict[str, Any]:
        raw_basic_info = self.extract_basic_info()
        approval_records = normalize_approval_records(self.extract_approval_records())
        latest_approval_time = derive_latest_approval_time(approval_records)
        return {
            "basic_info": self._build_basic_info_payload(
                raw_basic_info,
                latest_approval_time=latest_approval_time,
            ),
            "approval_records": approval_records,
            "latest_approval_time": latest_approval_time,
        }

    @staticmethod
    def _build_basic_info_payload(
        basic_info: dict[str, str],
        latest_approval_time: str,
    ) -> dict[str, str]:
        return {
            "document_no": basic_info.get("单据编号", ""),
            "employee_no": basic_info.get("工号", ""),
            "permission_target": basic_info.get("权限对象", ""),
            "apply_reason": basic_info.get("申请理由", ""),
            "document_status": basic_info.get("单据状态", ""),
            "hr_org": basic_info.get("人事管理组织", ""),
            "company_name": basic_info.get("公司", ""),
            "department_name": basic_info.get("部门", ""),
            "position_name": basic_info.get("职位", ""),
            "apply_time": basic_info.get("申请日期", ""),
            "latest_approval_time": latest_approval_time,
        }

    def extract_basic_info(self) -> dict[str, str]:
        field_map = self.page.evaluate(
            r"""() => {
                const root = document.querySelector('#fs_baseinfo');
                if (!root) return {};
                const items = [...root.querySelectorAll('[data-field-item="true"]')];
                const result = {};
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                };
                for (const item of items) {
                    if (!visible(item)) continue;
                    const label = normalize(item.querySelector('.kd-cq-field-title-wrap span')?.innerText || '');
                    if (!label) continue;
                    let value = '';
                    const input = item.querySelector('input[type="text"], textarea');
                    if (input) {
                        value = normalize(input.value || input.getAttribute('title') || '');
                    }
                    if (!value) {
                        const combo = item.querySelector('.kd-cq-combo-selected');
                        value = normalize(combo?.innerText || '');
                    }
                    if (!value) {
                        const valueWrap = item.querySelector('.kd-cq-field-value-wrap');
                        value = normalize(valueWrap?.innerText || '');
                    }
                    result[label] = value;
                }
                return result;
            }"""
        )
        if not field_map:
            raise RuntimeError("Failed to extract basic info fieldset")
        return field_map

    def extract_grid_rows(self, required_headers: Sequence[str]) -> list[dict[str, str]]:
        grid = self._extract_best_grid(required_headers)
        headers = grid["headers"]
        rows = grid["rows"]
        if tuple(required_headers) == tuple(TODO_HEADERS):
            rows = self._extract_all_todo_grid_rows(grid)
        elif tuple(required_headers) == tuple(DETAIL_HEADERS):
            rows = self._extract_all_detail_grid_rows(grid)
        normalized_rows: list[dict[str, str]] = []
        for row in rows:
            row = self._normalize_row_cells(headers, row)
            mapped = {headers[idx]: row[idx] if idx < len(row) else "" for idx in range(len(headers))}
            if tuple(required_headers) == tuple(TODO_HEADERS):
                normalized_rows.append(mapped)
                continue
            org_scope_count = self._extract_detail_count(mapped.get("行政组织详情", ""))
            normalized_rows.append(
                {
                    "line_no": mapped.get("#", ""),
                    "apply_type": mapped.get("申请类型", ""),
                    "role_name": mapped.get("角色名称", ""),
                    "role_desc": mapped.get("角色描述", ""),
                    "role_code": mapped.get("角色编码", ""),
                    "social_security_unit": mapped.get("参保单位", ""),
                    "org_scope_count": org_scope_count,
                }
            )
            latest_row = normalized_rows[-1]
            if not self._is_detail_row_business_valid(latest_row):
                self.logger.warning(
                    "Discarded invalid permission detail row: line_no=%r, apply_type=%r, role_name=%r, role_code=%r",
                    latest_row.get("line_no", ""),
                    latest_row.get("apply_type", ""),
                    latest_row.get("role_name", ""),
                    latest_row.get("role_code", ""),
                )
                normalized_rows.pop()
        return normalized_rows

    def _extract_all_todo_grid_rows(self, grid: dict[str, Any]) -> list[list[str]]:
        headers = list(grid.get("headers") or [])
        selector = str(grid.get("selector") or "")
        if not headers or not selector:
            return list(grid.get("rows") or [])

        expected_count = self._extract_todo_total_count()
        collected_rows: dict[str, list[str]] = {}
        stagnant_rounds = 0
        last_seen_size = -1

        self._set_grid_vertical_position(selector, 0)
        for _ in range(300):
            snapshot = self._get_grid_virtual_snapshot(selector, headers)
            if not snapshot:
                break

            for row in snapshot.get("rows", []):
                normalized_row = self._normalize_row_cells(headers, row)
                mapped = {
                    headers[idx]: normalized_row[idx] if idx < len(normalized_row) else ""
                    for idx in range(len(headers))
                }
                row_key = (
                    (mapped.get("单据编号") or "").strip()
                    or (mapped.get("#") or "").strip()
                    or "|".join(normalized_row)
                )
                if row_key:
                    collected_rows[row_key] = normalized_row

            if expected_count is not None and len(collected_rows) >= expected_count:
                break

            if len(collected_rows) == last_seen_size:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                last_seen_size = len(collected_rows)

            scroll_height = int(snapshot.get("scrollHeight", 0) or 0)
            client_height = int(snapshot.get("clientHeight", 0) or 0)
            current_top = int(snapshot.get("scrollTop", 0) or 0)
            next_top = min(current_top + max(client_height - 40, 200), max(scroll_height - client_height, 0))
            if next_top <= current_top:
                stagnant_rounds += 1
            else:
                self._set_grid_vertical_position(selector, next_top)

            if stagnant_rounds >= 5:
                break

        if expected_count is not None and len(collected_rows) < expected_count:
            self.logger.warning(
                "Todo grid virtual scroll collection incomplete: expected=%s, collected=%s",
                expected_count,
                len(collected_rows),
            )

        ordered_rows = list(collected_rows.values())
        ordered_rows.sort(key=lambda row: self._todo_row_sort_key(headers, row))
        return ordered_rows

    def _extract_all_detail_grid_rows(self, grid: dict[str, Any]) -> list[list[str]]:
        headers = list(grid.get("headers") or [])
        selector = str(grid.get("selector") or "")
        if not headers or not selector:
            return list(grid.get("rows") or [])

        collected_rows: dict[str, list[str]] = {}
        stagnant_rounds = 0
        last_seen_size = -1

        self._set_grid_vertical_position(selector, 0)
        for _ in range(400):
            snapshot = self._get_grid_virtual_snapshot(selector, headers)
            if not snapshot:
                break

            for row in snapshot.get("rows", []):
                normalized_row = self._normalize_row_cells(headers, row)
                mapped = {
                    headers[idx]: normalized_row[idx] if idx < len(normalized_row) else ""
                    for idx in range(len(headers))
                }
                if self._is_empty_detail_row(mapped):
                    continue
                line_no = (mapped.get("#") or "").strip()
                row_key = line_no or "|".join(normalized_row)
                if row_key:
                    collected_rows[row_key] = normalized_row

            if len(collected_rows) == last_seen_size:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                last_seen_size = len(collected_rows)

            scroll_height = int(snapshot.get("scrollHeight", 0) or 0)
            client_height = int(snapshot.get("clientHeight", 0) or 0)
            current_top = int(snapshot.get("scrollTop", 0) or 0)
            next_top = min(current_top + max(client_height - 40, 200), max(scroll_height - client_height, 0))
            if next_top <= current_top:
                stagnant_rounds += 1
            else:
                self._set_grid_vertical_position(selector, next_top)

            if stagnant_rounds >= 5:
                break

        ordered_rows = list(collected_rows.values())
        ordered_rows.sort(key=lambda row: self._detail_row_sort_key(headers, row))
        return ordered_rows

    def extract_role_organization_scopes(
        self,
        document_no: str,
        detail_rows: Sequence[dict[str, str]],
        failed_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        role_scopes: list[dict[str, Any]] = []
        failed_scope_rows = failed_rows if failed_rows is not None else []
        grid_info = self._wait_for_permission_detail_grid_ready(document_no)
        entry_grid_selector = grid_info["selector"]
        row_count = len(detail_rows)
        for row_idx in range(row_count):
            detail_row = detail_rows[row_idx]
            role_code = (detail_row.get("role_code") or "").strip()
            role_name = (detail_row.get("role_name") or "").strip()
            line_no = (detail_row.get("line_no") or "").strip() or str(row_idx + 1)
            detail_text = ""
            expected_count = self._coerce_expected_count(detail_row.get("org_scope_count"))
            try:
                self._wait_for_grid_row_ready(entry_grid_selector, row_idx, detail_row)
                if role_code and role_code in self.skip_org_scope_role_codes:
                    role_scopes.append(
                        {
                            "line_no": detail_row.get("line_no", ""),
                            "role_code": role_code,
                            "role_name": detail_row.get("role_name", ""),
                            "organization_codes": [],
                        }
                    )
                    self.logger.info(
                        "row_skipped reason=skip_org_scope document_no=%s line_no=%s role_code=%s role_name=%s",
                        document_no,
                        line_no,
                        role_code,
                        role_name,
                    )
                    continue

                cell_link = self._wait_for_detail_link_ready(
                    document_no=document_no,
                    grid_selector=entry_grid_selector,
                    row_idx=row_idx,
                    detail_row=detail_row,
                )
                if cell_link.count() > 0:
                    detail_text = (cell_link.text_content() or "").strip()
                parsed_count = self._extract_detail_count(detail_text) if detail_text else None
                if parsed_count is not None:
                    expected_count = parsed_count
                if expected_count == 0:
                    self.logger.info(
                        "row_skipped reason=expected_count_zero document_no=%s line_no=%s role_code=%s role_name=%s detail_text=%s",
                        document_no,
                        line_no,
                        role_code,
                        role_name,
                        detail_text,
                    )
                    role_scopes.append(
                        {
                            "line_no": detail_row.get("line_no", ""),
                            "role_code": role_code,
                            "role_name": detail_row.get("role_name", ""),
                            "organization_codes": [],
                        }
                    )
                    continue

                collected = self._extract_org_codes_from_detail_link(
                    document_no=document_no,
                    grid_selector=entry_grid_selector,
                    row_idx=row_idx,
                    detail_row=detail_row,
                    expected_count=expected_count,
                    detail_text=detail_text,
                    cell_link=cell_link,
                )
                self.logger.info(
                    "Collected %s organization codes from detail row %s",
                    len(collected),
                    detail_row.get("line_no", row_idx + 1),
                )
                role_scopes.append(
                    {
                        "line_no": detail_row.get("line_no", ""),
                        "role_code": role_code,
                        "role_name": detail_row.get("role_name", ""),
                        "organization_codes": sorted({code for code in collected if code}),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                failure = {
                    "document_no": document_no,
                    "row_idx": row_idx,
                    "line_no": detail_row.get("line_no", ""),
                    "role_code": role_code,
                    "role_name": detail_row.get("role_name", ""),
                    "detail_text": detail_text,
                    "expected_count": expected_count,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                failed_scope_rows.append(failure)
                self.logger.warning(
                    "row_failed_nonblocking document_no=%s row_idx=%s line_no=%s role_code=%s role_name=%s expected_count=%s detail_text=%s error=%s",
                    document_no,
                    row_idx,
                    line_no,
                    role_code,
                    role_name,
                    expected_count,
                    detail_text,
                    exc,
                )
                role_scopes.append(
                    {
                        "line_no": detail_row.get("line_no", ""),
                        "role_code": role_code,
                        "role_name": detail_row.get("role_name", ""),
                        "organization_codes": [],
                    }
                )
        return role_scopes

    def _extract_org_codes_from_detail_link(
        self,
        document_no: str,
        grid_selector: str,
        row_idx: int,
        detail_row: dict[str, str],
        expected_count: int | None,
        detail_text: str,
        cell_link,
    ) -> list[str]:
        def _click_and_extract(link, expected_count_value: int | None) -> set[str]:
            link.scroll_into_view_if_needed(timeout=self.timeout_ms)
            link.click(force=True)
            self.page.wait_for_timeout(1200)
            try:
                return self._extract_codes_from_org_grid(expected_count_value)
            finally:
                self._close_org_detail_with_escape()

        try:
            return sorted(_click_and_extract(cell_link, expected_count))
        except Exception as exc:  # noqa: BLE001
            if not self._is_org_grid_missing_error(exc):
                raise
            line_no = (detail_row.get("line_no") or "").strip() or str(row_idx + 1)
            role_code = (detail_row.get("role_code") or "").strip()
            role_name = (detail_row.get("role_name") or "").strip()
            self.logger.warning(
                "row_retrying reason=org_grid_not_found document_no=%s row_idx=%s line_no=%s role_code=%s role_name=%s expected_count=%s detail_text=%s error=%s",
                document_no,
                row_idx,
                line_no,
                role_code,
                role_name,
                expected_count,
                detail_text,
                exc,
            )
            self._wait_for_grid_row_ready(grid_selector, row_idx, detail_row)
            retry_link = self._wait_for_detail_link_ready(
                document_no=document_no,
                grid_selector=grid_selector,
                row_idx=row_idx,
                detail_row=detail_row,
            )
            retry_detail_text = (retry_link.text_content() or "").strip() if retry_link.count() > 0 else ""
            if expected_count is None and retry_detail_text:
                parsed_count = self._extract_detail_count(retry_detail_text)
                if parsed_count is not None:
                    expected_count = parsed_count
            return sorted(_click_and_extract(retry_link, expected_count))

    def _wait_for_document_loaded(self, document_no: str) -> None:
        self.page.locator("#fs_baseinfo").wait_for(state="visible", timeout=self.timeout_ms)
        self.page.locator("#entryentity").wait_for(state="visible", timeout=self.timeout_ms)

        deadline = time.monotonic() + (self.timeout_ms / 1000)
        current_document_no = ""
        last_headers: list[str] = []
        while time.monotonic() < deadline:
            try:
                basic_info = self.extract_basic_info()
                current_document_no = str(basic_info.get("单据编号", "")).strip()
                grid = self._extract_best_grid(DETAIL_HEADERS)
                last_headers = grid["headers"]
                if current_document_no == document_no:
                    return
            except Exception:
                pass
            self.page.wait_for_timeout(200)
        raise RuntimeError(
            f"Document did not finish loading: {document_no} "
            f"(current_document_no={current_document_no!r}, last_headers={last_headers})"
        )

    def _wait_for_permission_detail_grid_ready(
        self,
        document_no: str,
        row_idx: int | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        last_error = ""
        while time.monotonic() < deadline:
            try:
                grid = self._extract_best_grid(DETAIL_HEADERS)
                return grid
            except Exception as exc:
                last_error = str(exc)
            self.page.wait_for_timeout(200)

        raise PlaywrightTimeoutError(
            f"Permission detail grid not ready. document_no={document_no!r}, last_error={last_error}"
        )

    def _wait_for_grid_row_ready(
        self,
        grid_selector: str,
        row_idx: int,
        detail_row: dict[str, str],
    ) -> None:
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        line_no = detail_row.get("line_no", row_idx + 1)
        while time.monotonic() < deadline:
            matched = self._focus_detail_row(grid_selector, row_idx, line_no)
            if matched:
                return
            self.page.wait_for_timeout(200)
        raise PlaywrightTimeoutError(
            f"Permission detail row not ready. grid_selector={grid_selector!r}, row_idx={row_idx}, line_no={line_no!r}"
        )

    def _wait_for_todo_document_link_ready(self, document_no: str, timeout_ms: int | None = None):
        grid = self._extract_best_grid(TODO_HEADERS)
        grid_selector = str(grid.get("selector") or "")
        headers = list(grid.get("headers") or [])
        if not grid_selector or not headers:
            raise RuntimeError(f"Todo grid not ready for document lookup: {document_no}")
        self._set_grid_vertical_position(grid_selector, 0)
        effective_timeout_ms = max(int(timeout_ms or self.timeout_ms), 1)
        deadline = time.monotonic() + (effective_timeout_ms / 1000)
        stagnant_rounds = 0
        empty_rows_rounds = 0
        refresh_attempted = False
        search_attempted = False
        not_found_rounds = 0
        last_error = ""
        while time.monotonic() < deadline:
            if self._focus_todo_row(grid_selector, document_no):
                not_found_rounds = 0
                row_locator = self._get_target_todo_row_locator(grid_selector)
                try:
                    row_locator.wait_for(state="visible", timeout=1000)
                except PlaywrightTimeoutError:
                    last_error = "target_todo_row_not_visible"
                else:
                    cell_link = row_locator.locator("span.link-cell-content").filter(has_text=document_no).first
                    if cell_link.count() > 0:
                        return cell_link
                    last_error = "target_todo_link_not_rendered"
            else:
                last_error = "target_todo_row_not_found"
                not_found_rounds += 1
                if not search_attempted and not_found_rounds >= 3:
                    search_attempted = self._try_search_todo_document(document_no)
                    if search_attempted:
                        self.logger.info(
                            "Todo document %s not found in current rows, search filter applied and retrying",
                            document_no,
                        )
                        self._set_grid_vertical_position(grid_selector, 0)
                        stagnant_rounds = 0
                        empty_rows_rounds = 0
                        self.page.wait_for_timeout(600)
                        continue
            snapshot = self._get_grid_virtual_snapshot(grid_selector, headers)
            if not snapshot:
                last_error = "todo_grid_snapshot_missing"
                self.page.wait_for_timeout(200)
                continue
            rows = list(snapshot.get("rows") or [])
            if rows:
                empty_rows_rounds = 0
            else:
                empty_rows_rounds += 1
                last_error = "todo_grid_rows_empty"
                if not refresh_attempted and empty_rows_rounds >= 3:
                    refresh_attempted = self._try_refresh_todo_grid()
                    if refresh_attempted:
                        self.logger.info(
                            "Todo grid empty while locating document %s, refresh clicked and retrying",
                            document_no,
                        )
                        self._set_grid_vertical_position(grid_selector, 0)
                        stagnant_rounds = 0
                        self.page.wait_for_timeout(600)
                        continue
            scroll_height = int(snapshot.get("scrollHeight", 0) or 0)
            client_height = int(snapshot.get("clientHeight", 0) or 0)
            current_top = int(snapshot.get("scrollTop", 0) or 0)
            next_top = min(current_top + max(client_height - 40, 200), max(scroll_height - client_height, 0))
            if next_top <= current_top:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                self._set_grid_vertical_position(grid_selector, next_top)
            if stagnant_rounds >= 3:
                # Virtualized rows can keep scrollTop unchanged while still loading.
                # Keep polling until timeout instead of failing fast.
                stagnant_rounds = 0
                self._set_grid_vertical_position(grid_selector, 0)
                if not last_error:
                    last_error = "todo_grid_stagnant_waiting_rows"
                self.page.wait_for_timeout(250)
                continue
            self.page.wait_for_timeout(120)
        todo_total_count = self._extract_todo_total_count()
        todo_tab_count = self._extract_todo_tab_count()
        if todo_tab_count == 0:
            raise PlaywrightTimeoutError(
                f"Todo document not found in current account todo list. document_no={document_no!r}, todo_tab_count=0"
            )
        total_count_text = f", todo_total_count={todo_total_count}" if todo_total_count is not None else ""
        tab_count_text = f", todo_tab_count={todo_tab_count}" if todo_tab_count is not None else ""
        raise PlaywrightTimeoutError(
            f"Todo document link not ready. document_no={document_no!r}, last_error={last_error}{total_count_text}{tab_count_text}"
        )

    def _try_search_todo_document(self, document_no: str) -> bool:
        keyword = str(document_no or "").strip()
        if not keyword:
            return False
        return bool(
            self.page.evaluate(
                r"""(payload) => {
                    const { keyword } = payload;
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    };
                    const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                    const hintPattern = /(\u641c\u7d22|search)/i;
                    const inputs = [...document.querySelectorAll('input[type="text"], input:not([type])')]
                        .filter((el) => visible(el));
                    for (const input of inputs) {
                        const hint = normalize(
                            `${input.getAttribute('placeholder') || ''} ${input.getAttribute('aria-label') || ''} ${input.getAttribute('title') || ''}`
                        );
                        if (!hintPattern.test(hint)) continue;
                        input.focus();
                        input.value = keyword;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true }));
                        input.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', bubbles: true }));
                        return true;
                    }
                    return false;
                }""",
                {"keyword": keyword},
            )
        )

    def _extract_todo_tab_count(self) -> int | None:
        tab_count = self.page.evaluate(
            r"""() => {
                const visible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                };
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const parseCount = (text) => {
                    const match = normalize(text).match(/\((\d+)\)/);
                    return match ? Number(match[1]) : null;
                };
                const tabs = [...document.querySelectorAll('#tabap .kd-cq-tabs-tab, [id^="tabap"] .kd-cq-tabs-tab, div[id^="processflexpanelap_"]')]
                    .filter((el) => visible(el));
                const score = (el) => {
                    let value = 0;
                    if (el.getAttribute('aria-selected') === 'true') value += 100;
                    if ((el.className || '').toLowerCase().includes('active')) value += 50;
                    return value;
                };
                tabs.sort((left, right) => score(right) - score(left));
                for (const tab of tabs) {
                    const count = parseCount(tab.innerText || tab.textContent || '');
                    if (count !== null) return count;
                }
                return null;
            }"""
        )
        if tab_count is None:
            return None
        return int(tab_count)

    def _try_refresh_todo_grid(self) -> bool:
        return bool(
            self.page.evaluate(
                r"""() => {
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    };
                    const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                    const candidates = [...document.querySelectorAll('button, [role=\"button\"], .kd-btn')]
                        .filter((el) => visible(el));
                    const refreshPattern = /(\u5237\u65b0|Refresh)/i;
                    for (const element of candidates) {
                        const text = normalize(element.innerText || element.textContent || '');
                        const title = normalize(element.getAttribute('title') || '');
                        if (!refreshPattern.test(text + ' ' + title)) continue;
                        element.click();
                        return true;
                    }
                    return false;
                }"""
            )
        )

    def _wait_for_detail_link_ready(
        self,
        document_no: str,
        grid_selector: str,
        row_idx: int,
        detail_row: dict[str, str],
    ):
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        line_no = detail_row.get("line_no", row_idx + 1)
        while time.monotonic() < deadline:
            matched = self._focus_detail_row(grid_selector, row_idx, line_no)
            if not matched:
                self.page.wait_for_timeout(200)
                continue
            row_locator = self._get_target_detail_row_locator(grid_selector)
            try:
                row_locator.wait_for(state="visible", timeout=1000)
            except PlaywrightTimeoutError:
                self.page.wait_for_timeout(200)
                continue
            for ratio in self._detail_link_horizontal_ratios():
                if ratio is not None:
                    self._set_grid_horizontal_position(grid_selector, ratio)
                cell_link = self._get_detail_link_locator(row_locator)
                if cell_link.count() > 0:
                    return cell_link
            self.page.wait_for_timeout(200)

        raise PlaywrightTimeoutError(
            f"Organization detail link not ready. document_no={document_no!r}, row_idx={row_idx}, line_no={line_no!r}"
        )

    @staticmethod
    def _get_detail_link_locator(row_locator):
        return row_locator.locator("span.link-cell-content").filter(has_text="查看详情").first

    def _get_target_detail_row_locator(self, grid_selector: str):
        return self.page.locator(f'{grid_selector} tbody tr[data-clawcheck-target-row="true"]').first

    def _get_target_todo_row_locator(self, grid_selector: str):
        return self.page.locator(f'{grid_selector} tbody tr[data-clawcheck-target-todo-row="true"]').first

    def _focus_todo_row(self, grid_selector: str, document_no: str) -> bool:
        focus_result = self.page.evaluate(
            r"""(payload) => {
                const { selector, documentNo } = payload;
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const targetDocumentNo = normalize(documentNo);
                const grid = document.querySelector(selector);
                if (!grid) return false;

                const clearMarkers = () => {
                    grid.querySelectorAll('tbody tr[data-clawcheck-target-todo-row="true"]').forEach((row) => {
                        row.removeAttribute('data-clawcheck-target-todo-row');
                    });
                };
                const getRenderedRows = () => [...grid.querySelectorAll('tbody tr')];
                const matchesDocumentNo = (row) => {
                    const rowText = normalize(row.innerText || '');
                    if (rowText.includes(targetDocumentNo)) return true;
                    const cells = [...row.querySelectorAll('td')]
                        .map((cell) => normalize(cell.innerText))
                        .filter(Boolean);
                    return cells.some((cellText) => cellText === targetDocumentNo || cellText.includes(targetDocumentNo));
                };
                const markTargetRow = () => {
                    const row = getRenderedRows().find(matchesDocumentNo);
                    if (!row) return false;
                    row.setAttribute('data-clawcheck-target-todo-row', 'true');
                    row.scrollIntoView({ block: 'nearest', inline: 'nearest' });
                    return true;
                };

                clearMarkers();
                return markTargetRow();
            }""",
            {
                "selector": grid_selector,
                "documentNo": document_no,
            },
        )
        return bool(focus_result)

    def _focus_detail_row(self, grid_selector: str, row_idx: int, line_no: str | int) -> bool:
        focus_result = self.page.evaluate(
            r"""(payload) => {
                const { selector, rowIndex, lineNo } = payload;
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const targetLineNo = normalize(String(lineNo || ''));
                const fallbackLineNo = String(rowIndex + 1);
                const grid = document.querySelector(selector);
                if (!grid) return false;

                const clearMarkers = () => {
                    grid.querySelectorAll('tbody tr[data-clawcheck-target-row="true"]').forEach((row) => {
                        row.removeAttribute('data-clawcheck-target-row');
                    });
                };
                const getRenderedRows = () => [...grid.querySelectorAll('tbody tr')];
                const matchesLineNo = (row) => {
                    const cells = [...row.querySelectorAll('td')]
                        .map((cell) => normalize(cell.innerText))
                        .filter(Boolean);
                    return cells.slice(0, 3).some((cellText) => cellText === targetLineNo || cellText === fallbackLineNo);
                };
                const markTargetRow = () => {
                    const row = getRenderedRows().find(matchesLineNo);
                    if (!row) return false;
                    row.setAttribute('data-clawcheck-target-row', 'true');
                    row.scrollIntoView({ block: 'nearest', inline: 'nearest' });
                    return true;
                };

                clearMarkers();
                if (markTargetRow()) return true;

                const body = grid.querySelector('.kd-table-body.kd-horizontal-scroll-container')
                    || grid.querySelector('.kd-table-body');
                if (!body) return false;
                const sampleRow = getRenderedRows().find((row) => row.getBoundingClientRect().height > 0);
                const rowHeight = sampleRow ? Math.max(sampleRow.getBoundingClientRect().height, 1) : 40;
                const maxTop = Math.max(body.scrollHeight - body.clientHeight, 0);
                const estimatedTop = Math.min(Math.max((rowIndex * rowHeight) - rowHeight, 0), maxTop);
                if (estimatedTop !== body.scrollTop) {
                    body.scrollTop = estimatedTop;
                }

                clearMarkers();
                return markTargetRow();
            }""",
            {
                "selector": grid_selector,
                "rowIndex": row_idx,
                "lineNo": str(line_no or ""),
            },
        )
        return bool(focus_result)

    @staticmethod
    def _detail_link_horizontal_ratios() -> tuple[float | None, ...]:
        return (None, 0.5, 0.0, 0.75, 0.25, 1.0)

    def _set_grid_horizontal_position(self, grid_selector: str, ratio: float) -> None:
        self.page.evaluate(
            r"""(payload) => {
                const { selector, ratio } = payload;
                const grid = document.querySelector(selector);
                if (!grid) return;
                const targets = [
                    grid.querySelector('.kd-sticky-scroll'),
                    grid.querySelector('.kd-virtual'),
                    grid.querySelector('.kd-table-header'),
                    grid.querySelector('.kd-table-footer.kd-horizontal-scroll-container'),
                    grid.querySelector('.kd-table-body.kd-horizontal-scroll-container'),
                ].filter(Boolean);
                for (const target of targets) {
                    const maxScrollLeft = Math.max(target.scrollWidth - target.clientWidth, 0);
                    if (maxScrollLeft <= 0) continue;
                    target.scrollLeft = Math.round(maxScrollLeft * ratio);
                }
            }""",
            {"selector": grid_selector, "ratio": ratio},
        )
        self.page.wait_for_timeout(150)

    def _get_grid_virtual_snapshot(
        self,
        grid_selector: str,
        headers: Sequence[str],
    ) -> dict[str, Any] | None:
        return self.page.evaluate(
            r"""(payload) => {
                const { selector, headers } = payload;
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const grid = document.querySelector(selector);
                if (!grid) return null;
                const body = grid.querySelector('.kd-table-body.kd-horizontal-scroll-container')
                    || grid.querySelector('.kd-table-body');
                const rows = [...grid.querySelectorAll('tbody tr')].map((tr) =>
                    [...tr.querySelectorAll('td')].map((td) => normalize(td.innerText))
                );
                return {
                    headers,
                    rows,
                    scrollTop: body ? body.scrollTop : 0,
                    scrollHeight: body ? body.scrollHeight : 0,
                    clientHeight: body ? body.clientHeight : 0,
                };
            }""",
            {
                "selector": grid_selector,
                "headers": list(headers),
            },
        )

    def _set_grid_vertical_position(self, grid_selector: str, scroll_top: int) -> None:
        self.page.evaluate(
            r"""(payload) => {
                const { selector, scrollTop } = payload;
                const grid = document.querySelector(selector);
                if (!grid) return;
                const body = grid.querySelector('.kd-table-body.kd-horizontal-scroll-container')
                    || grid.querySelector('.kd-table-body');
                if (body) {
                    body.scrollTop = scrollTop;
                }
            }""",
            {
                "selector": grid_selector,
                "scrollTop": int(scroll_top),
            },
        )
        self.page.wait_for_timeout(150)

    def _extract_todo_total_count(self) -> int | None:
        total_count = self.page.evaluate(
            r"""() => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const candidates = [
                    document.querySelector('#gridview'),
                    document.querySelector('body'),
                ].filter(Boolean);
                for (const candidate of candidates) {
                    const text = normalize(candidate.innerText || '');
                    const match = text.match(/共\s*(\d+)\s*条/);
                    if (match) {
                        return Number(match[1]);
                    }
                }
                return null;
            }"""
        )
        if total_count is None:
            return None
        return int(total_count)

    def extract_approval_records(self) -> list[dict[str, str]]:
        approval_tab = self.page.locator("#tabap .kd-cq-tabs-tab").filter(has_text="审批记录").first
        approval_tab.wait_for(state="visible", timeout=self.timeout_ms)
        approval_tab.click(force=True)
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        while time.monotonic() < deadline:
            visible_blocks = self.page.locator(f"{APPROVAL_TABPAGE_SELECTOR} ._2QHPFSVv")
            if visible_blocks.count() == 0:
                visible_blocks = self.page.locator("li.kd-cq-tabpage:not(.hidden) ._2QHPFSVv")
            if visible_blocks.count() > 0:
                break
            self.page.wait_for_timeout(200)
        else:
            raise PlaywrightTimeoutError("Approval record tab did not become visible")

        records = self._collect_approval_record_cards()
        return self._parse_approval_record_cards(records)

    def _collect_approval_record_cards(self) -> list[dict[str, str]]:
        return self.page.evaluate(
            r"""async (tabSelector) => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
                const waitForPaint = async () => {
                    await new Promise((resolve) => window.requestAnimationFrame(() => resolve(undefined)));
                    await wait(80);
                };
                const root =
                    document.querySelector(tabSelector)
                    || document.querySelector('li.kd-cq-tabpage:not(.hidden)');
                if (!root) return [];

                const cardSelector = '._2QHPFSVv';
                const toRecord = (block) => {
                    const header = block.querySelector('h4');
                    const fullHeader = normalize(header?.innerText || '');
                    const timeText = normalize(block.querySelector('p.zPG-NFNf')?.innerText || '');
                    const opinionNode = block.querySelector('p._3aIXYPkW');
                    const opinionVisible = opinionNode && window.getComputedStyle(opinionNode).display !== 'none';
                    const opinion = opinionVisible ? normalize(opinionNode.innerText || '') : '';
                    return {
                        header_text: fullHeader,
                        approval_time: timeText,
                        approval_opinion: opinion,
                        raw_text: normalize(block.innerText || ''),
                    };
                };
                const findScrollable = () => {
                    const candidates = [root, ...root.querySelectorAll('*')];
                    for (const element of candidates) {
                        if (!(element instanceof HTMLElement)) continue;
                        if (!element.querySelector(cardSelector) && !element.matches(cardSelector)) continue;
                        const style = window.getComputedStyle(element);
                        const overflowY = `${style.overflowY} ${style.overflow}`.toLowerCase();
                        if (!/(auto|scroll|overlay)/.test(overflowY)) continue;
                        if (element.scrollHeight <= element.clientHeight + 4) continue;
                        return element;
                    }
                    return null;
                };

                const collected = [];
                const seen = new Set();
                const collectVisibleCards = () => {
                    const blocks = [...root.querySelectorAll(cardSelector)];
                    for (const block of blocks) {
                        const record = toRecord(block);
                        const uniqueKey = record.raw_text || `${record.header_text}__${record.approval_time}`;
                        if (!uniqueKey || seen.has(uniqueKey)) continue;
                        seen.add(uniqueKey);
                        collected.push(record);
                    }
                };

                const scrollable = findScrollable();
                collectVisibleCards();
                if (!scrollable) {
                    return collected.map((record, index) => ({ ...record, record_seq: String(index + 1) }));
                }

                let lastSeenCount = collected.length;
                let stagnantRounds = 0;
                for (let attempt = 0; attempt < 200; attempt += 1) {
                    const maxScrollTop = Math.max(0, scrollable.scrollHeight - scrollable.clientHeight);
                    if (scrollable.scrollTop >= maxScrollTop - 2) {
                        break;
                    }

                    const nextScrollTop = Math.min(
                        maxScrollTop,
                        scrollable.scrollTop + Math.max(Math.floor(scrollable.clientHeight * 0.8), 160),
                    );
                    if (nextScrollTop <= scrollable.scrollTop) {
                        break;
                    }

                    scrollable.scrollTop = nextScrollTop;
                    scrollable.dispatchEvent(new Event('scroll', { bubbles: true }));
                    await waitForPaint();
                    collectVisibleCards();

                    if (collected.length == lastSeenCount) {
                        stagnantRounds += 1;
                        if (stagnantRounds >= 3) {
                            if (scrollable.scrollTop >= maxScrollTop - 2) {
                                break;
                            }
                            scrollable.scrollTop = Math.min(maxScrollTop, scrollable.scrollTop + 40);
                            scrollable.dispatchEvent(new Event('scroll', { bubbles: true }));
                            await waitForPaint();
                            collectVisibleCards();
                        }
                    } else {
                        stagnantRounds = 0;
                        lastSeenCount = collected.length;
                    }
                }

                return collected.map((record, index) => ({ ...record, record_seq: String(index + 1) }));
            }""",
            APPROVAL_TABPAGE_SELECTOR,
        )

    @staticmethod
    def _parse_approval_record_cards(records: list[dict[str, str]]) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for item in records:
            header_text = item.get("header_text", "")
            node_name, approver_info, approval_action = PermissionCollectFlow._parse_approval_record_header(header_text)
            approver_name = ""
            approver_org_or_position = ""
            if "|" in approver_info:
                approver_name, approver_org_or_position = approver_info.split("|", 1)
            normalized.append(
                {
                    "record_seq": item.get("record_seq", ""),
                    "node_name": node_name,
                    "approver_name": approver_name,
                    "approver_org_or_position": approver_org_or_position,
                    "approval_action": approval_action,
                    "approval_opinion": item.get("approval_opinion", ""),
                    "approval_time": item.get("approval_time", ""),
                    "raw_text": item.get("raw_text", ""),
                }
            )
        return normalized

    @staticmethod
    def _parse_approval_record_header(header_text: str) -> tuple[str, str, str]:
        header_text = str(header_text or "").strip()
        with_node_match = APPROVAL_HEADER_WITH_NODE_RE.match(header_text)
        if with_node_match:
            return (
                with_node_match.group("node_name").strip(),
                with_node_match.group("approver_info").strip(),
                with_node_match.group("approval_action").strip(),
            )

        without_node_match = APPROVAL_HEADER_WITHOUT_NODE_RE.match(header_text)
        if without_node_match:
            return (
                MANUAL_ADDED_SIGN_NODE_NAME,
                without_node_match.group("approver_info").strip(),
                without_node_match.group("approval_action").strip(),
            )

        return "", "", ""

    def _wait_for_grid_headers(self, required_headers: Sequence[str]) -> None:
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        last_headers: list[str] = []
        while time.monotonic() < deadline:
            try:
                grid = self._extract_best_grid(required_headers)
                if grid["rows"] is not None:
                    return
                last_headers = grid["headers"]
            except Exception:
                pass
            self.page.wait_for_timeout(200)
        raise PlaywrightTimeoutError(f"Grid headers not ready: {required_headers}. Last headers={last_headers}")

    def _ensure_todo_page_size(self, page_size: int, timeout_ms: int | None = None) -> None:
        target_text = f"{page_size}条/页"
        effective_timeout_ms = max(int(timeout_ms or self.timeout_ms), 1)
        trigger = self.page.locator(
            "#gridview .kd-pagination-selector button.kd-dropdown-trigger.kd-pagination-selector-size.kd-pagination-options-dropdown"
        ).first
        trigger.wait_for(state="visible", timeout=effective_timeout_ms)

        deadline = time.monotonic() + (effective_timeout_ms / 1000)
        last_text = ""
        while time.monotonic() < deadline:
            last_text = re.sub(r"\s+", "", trigger.inner_text() or "")
            if target_text in last_text:
                return

            trigger.click(force=True)
            option = self.page.locator(
                f'.kd-dropdown.kd-cq-pagination-dropdown li.kd-dropdown-menu-item[title="{target_text}"]'
            ).first
            option.wait_for(state="visible", timeout=3000)
            option.click(force=True)
            self.page.wait_for_timeout(500)

        raise PlaywrightTimeoutError(
            f"Todo page size did not become {target_text}. last_text={last_text}"
        )

    def _wait_for_todo_list_ready(self, page_size_timeout_ms: int | None = None) -> bool:
        self.page.locator("#gridview").first.wait_for(state="visible", timeout=self.timeout_ms)
        page_size_applied = False
        try:
            self._ensure_todo_page_size(1000, timeout_ms=page_size_timeout_ms)
            page_size_applied = True
        except PlaywrightTimeoutError as exc:
            self.logger.warning(
                "Todo page size selector not ready, continue with current pagination: %s",
                exc,
            )
        self._wait_for_grid_headers(TODO_HEADERS)
        return page_size_applied

    def _remember_current_document_tab(self, document_no: str) -> None:
        tab_info = self.page.evaluate(
            r"""(todoPageIdSuffix) => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return (
                        rect.width > 0 &&
                        rect.height > 0 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden'
                    );
                };
                const score = (tab) => {
                    const className = String(tab.className || '').toLowerCase();
                    let value = 0;
                    if (tab.getAttribute('aria-selected') === 'true') value += 100;
                    if (tab.getAttribute('aria-current') === 'page') value += 100;
                    if (/\b(active|selected|focus|focused|current|on)\b/.test(className)) value += 80;
                    return value;
                };
                const tabs = [...document.querySelectorAll('li[data-splitscreen-pageid]')]
                    .filter((tab) => {
                        const pageId = tab.getAttribute('data-splitscreen-pageid') || '';
                        return visible(tab) && pageId && !pageId.endsWith(todoPageIdSuffix);
                    })
                    .map((tab, index) => ({
                        index,
                        pageId: tab.getAttribute('data-splitscreen-pageid') || '',
                        text: normalize(tab.innerText || ''),
                        score: score(tab),
                    }));
                tabs.sort((left, right) => {
                    if (right.score !== left.score) return right.score - left.score;
                    return right.index - left.index;
                });
                return tabs[0] || null;
            }""",
            "hrobs_pc_messagecenter",
        )
        self.current_document_tab_pageid = None
        self.current_document_tab_text = ""
        if not tab_info:
            self.logger.warning("Failed to capture current document tab after opening %s", document_no)
            return
        pageid = str(tab_info.get("pageId", "")).strip()
        self.current_document_tab_pageid = pageid or None
        self.current_document_tab_text = str(tab_info.get("text", "")).strip()
        self.logger.info(
            "Captured document tab for %s: pageid=%s, text=%s",
            document_no,
            self.current_document_tab_pageid,
            self.current_document_tab_text,
        )

    def close_current_document_tab(self, document_no: str = "") -> None:
        close_result = self.page.evaluate(
            r"""(payload) => {
                const { todoPageIdSuffix, trackedPageId } = payload;
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return (
                        rect.width > 0 &&
                        rect.height > 0 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden'
                    );
                };
                const score = (tab) => {
                    const className = String(tab.className || '').toLowerCase();
                    let value = 0;
                    if (tab.getAttribute('aria-selected') === 'true') value += 100;
                    if (tab.getAttribute('aria-current') === 'page') value += 100;
                    if (/\b(active|selected|focus|focused|current|on)\b/.test(className)) value += 80;
                    return value;
                };
                const matchesClose = (el) => {
                    const text = normalize(el.innerText || el.textContent || '');
                    const title = normalize(el.getAttribute('title') || '');
                    const ariaLabel = normalize(el.getAttribute('aria-label') || '');
                    const className = String(el.className || '').toLowerCase();
                    return (
                        el.hasAttribute('drop-close-icon') ||
                        className.includes('kdfont-toubudaohang_guanbi') ||
                        text === '×' ||
                        text === 'x' ||
                        text.includes('关闭') ||
                        title.includes('关闭') ||
                        ariaLabel.includes('关闭') ||
                        className.includes('close') ||
                        className.includes('remove')
                    );
                };
                const findCloseTarget = (tab) => {
                    const directIcon = tab.querySelector('i[drop-close-icon], i.kdfont-toubudaohang_guanbi');
                    if (directIcon) return directIcon;
                    const descendants = [...tab.querySelectorAll('*')];
                    const explicit = descendants.find((el) => matchesClose(el));
                    if (explicit) return explicit;
                    const iconLike = descendants
                        .map((el) => ({
                            el,
                            rect: el.getBoundingClientRect(),
                            className: String(el.className || '').toLowerCase(),
                            text: normalize(el.innerText || el.textContent || ''),
                        }))
                        .filter(({ rect, className, text }) => {
                            const isCompact = rect.width <= 32 && rect.height <= 32;
                            const isLikelyIcon = className.includes('icon') || className.includes('btn') || text === '×';
                            return isCompact && isLikelyIcon;
                        })
                        .sort((left, right) => right.rect.left - left.rect.left);
                    return iconLike[0]?.el || null;
                };
                const tabs = [...document.querySelectorAll('li[data-splitscreen-pageid]')]
                    .filter((tab) => {
                        const pageId = tab.getAttribute('data-splitscreen-pageid') || '';
                        return visible(tab) && pageId && !pageId.endsWith(todoPageIdSuffix);
                    });
                const target =
                    (trackedPageId && tabs.find((tab) => (tab.getAttribute('data-splitscreen-pageid') || '') === trackedPageId)) ||
                    tabs
                        .map((tab, index) => ({
                            index,
                            score: score(tab),
                            tab,
                        }))
                        .sort((left, right) => {
                            if (right.score !== left.score) return right.score - left.score;
                            return right.index - left.index;
                        })[0]?.tab ||
                    null;
                if (!target) {
                    return {
                        clicked: false,
                        reason: 'document_tab_not_found',
                        trackedPageId,
                    };
                }
                target.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                target.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                target.click();
                const closeTarget = findCloseTarget(target);
                if (!closeTarget) {
                    return {
                        clicked: false,
                        reason: 'close_button_not_found',
                        trackedPageId,
                        pageId: target.getAttribute('data-splitscreen-pageid') || '',
                        text: normalize(target.innerText || ''),
                    };
                }
                closeTarget.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                closeTarget.dispatchEvent(new MouseEvent('mouseover', { bubbles: true }));
                closeTarget.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                closeTarget.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
                closeTarget.click();
                return {
                    clicked: true,
                    trackedPageId,
                    pageId: target.getAttribute('data-splitscreen-pageid') || '',
                    text: normalize(target.innerText || ''),
                };
            }""",
            {
                "todoPageIdSuffix": "hrobs_pc_messagecenter",
                "trackedPageId": self.current_document_tab_pageid or "",
            },
        )
        if close_result.get("clicked"):
            self.logger.info(
                "Closed document tab for %s: pageid=%s, text=%s",
                document_no or self.current_document_tab_text or self.current_document_tab_pageid or "<unknown>",
                close_result.get("pageId", ""),
                close_result.get("text", ""),
            )
        else:
            self.logger.warning(
                "Failed to close current document tab for %s: %s",
                document_no or self.current_document_tab_text or self.current_document_tab_pageid or "<unknown>",
                close_result,
            )
        self.current_document_tab_pageid = None
        self.current_document_tab_text = ""

    def _extract_best_grid(self, required_headers: Sequence[str]) -> dict[str, Any]:
        root_selector = None
        preferred_headers: Sequence[str] = ()
        grid_key = "generic"
        if tuple(required_headers) == tuple(TODO_HEADERS):
            root_selector = "#gridview"
            grid_key = "todo"
        elif tuple(required_headers) == tuple(DETAIL_HEADERS):
            root_selector = "#entryentity"
            preferred_headers = DETAIL_PREFERRED_HEADERS
            grid_key = "detail"
        elif tuple(required_headers) == tuple(ORG_HEADERS):
            grid_key = "org"

        grid = self.page.evaluate(
            r"""(payload) => {
                const { requiredHeaders, preferredHeaders, rootSelector, gridKey } = payload;
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const hasRequiredHeaders = (headers, requiredHeaders) =>
                    requiredHeaders.every((requiredHeader) =>
                        headers.some((header) => header.includes(requiredHeader))
                    );
                const countPreferredHeaders = (headers, preferredHeaders) =>
                    preferredHeaders.filter((preferredHeader) =>
                        headers.some((header) => header.includes(preferredHeader))
                    ).length;
                const visible = (el) => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return (
                        rect.width > 0 &&
                        rect.height > 0 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden'
                    );
                };
                const scopes = [];
                if (rootSelector) {
                    const root = document.querySelector(rootSelector);
                    if (root) scopes.push(root);
                }
                scopes.push(document);
                const seen = new Set();
                const grids = scopes.flatMap((scope) =>
                    [...scope.querySelectorAll('.kd-table-container')]
                ).filter((grid) => {
                    if (seen.has(grid)) return false;
                    seen.add(grid);
                    return true;
                }).map((grid, index) => {
                    const headers = [...grid.querySelectorAll('th .kd-table-header-title')]
                        .map((item) => normalize(item.innerText))
                        .filter(Boolean);
                    const rect = grid.getBoundingClientRect();
                    const area = Math.max(rect.width, 0) * Math.max(rect.height, 0);
                    const rows = [...grid.querySelectorAll('tbody tr')].map((tr) =>
                        [...tr.querySelectorAll('td')].map((td) => normalize(td.innerText))
                    );
                    return {
                        index,
                        id: grid.id || '',
                        selector: grid.id ? `#${grid.id}` : `.kd-table-container:nth-of-type(${index + 1})`,
                        headers,
                        rows,
                        area,
                        preferredHeaderScore: countPreferredHeaders(headers, preferredHeaders),
                        visible: visible(grid),
                        element: grid,
                    };
                });
                const matched = grids.filter(
                    (grid) => grid.visible && hasRequiredHeaders(grid.headers, requiredHeaders)
                );
                matched.sort((left, right) => {
                    if (right.preferredHeaderScore !== left.preferredHeaderScore) {
                        return right.preferredHeaderScore - left.preferredHeaderScore;
                    }
                    if (right.rows.length !== left.rows.length) {
                        return right.rows.length - left.rows.length;
                    }
                    return right.area - left.area;
                });
                const selected = matched[0];
                document.querySelectorAll(`.kd-table-container[data-clawcheck-grid-key="${gridKey}"]`).forEach((grid) => {
                    grid.removeAttribute('data-clawcheck-grid-key');
                });
                if (!selected) return null;
                const { element, ...selectedData } = selected;
                if (selected.id) {
                    return selectedData;
                }
                if (!element) return null;
                element.setAttribute('data-clawcheck-grid-key', gridKey);
                return {
                    ...selectedData,
                    selector: `.kd-table-container[data-clawcheck-grid-key="${gridKey}"]`,
                };
            }""",
            {
                "requiredHeaders": list(required_headers),
                "preferredHeaders": list(preferred_headers),
                "rootSelector": root_selector,
                "gridKey": grid_key,
            },
        )
        if not grid:
            raise RuntimeError(f"No grid matched headers: {required_headers}")
        return grid

    def _extract_codes_from_org_grid(self, expected_count: int | None) -> set[str]:
        collected_codes: set[str] = set()
        stagnant_rounds = 0
        last_seen_size = -1

        for _ in range(300):
            snapshot = self._get_org_grid_snapshot(wait_for_present=True, expected_count=expected_count)
            if not snapshot:
                raise RuntimeError("Organization detail grid not found after clicking detail link")

            header_index = {header: idx for idx, header in enumerate(snapshot["headers"])}
            code_idx = header_index.get("组织编码")
            for row in snapshot["rows"]:
                row = self._normalize_row_cells(snapshot["headers"], row)
                if code_idx is None or code_idx >= len(row):
                    continue
                code = row[code_idx].strip()
                if code:
                    collected_codes.add(code)

            if expected_count is not None and len(collected_codes) >= expected_count:
                break

            if len(collected_codes) == last_seen_size:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                last_seen_size = len(collected_codes)

            scroll_height = snapshot.get("scrollHeight", 0)
            client_height = snapshot.get("clientHeight", 0)
            current_top = snapshot.get("scrollTop", 0)
            next_top = min(current_top + max(client_height - 40, 200), max(scroll_height - client_height, 0))
            if next_top <= current_top:
                stagnant_rounds += 1
            else:
                self.page.evaluate(
                    r"""(payload) => {
                        const { requiredHeaders, nextTop } = payload;
                    const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                    const hasRequiredHeaders = (headers, requiredHeaders) =>
                        requiredHeaders.every((requiredHeader) =>
                            headers.some((header) => header.includes(requiredHeader))
                        );
                    const grids = [...document.querySelectorAll('.kd-table-container')].filter((grid) => {
                        const headers = [...grid.querySelectorAll('th .kd-table-header-title')]
                            .map((item) => normalize(item.innerText))
                            .filter(Boolean);
                        return hasRequiredHeaders(headers, requiredHeaders);
                    });
                        grids.sort((left, right) => {
                            const leftRect = left.getBoundingClientRect();
                            const rightRect = right.getBoundingClientRect();
                            return (rightRect.width * rightRect.height) - (leftRect.width * leftRect.height);
                        });
                        const body = grids[0]?.querySelector('.kd-table-body.kd-horizontal-scroll-container');
                        if (body) body.scrollTop = nextTop;
                    }""",
                    {"requiredHeaders": ORG_HEADERS, "nextTop": next_top},
                )
                self.page.wait_for_timeout(150)

            if stagnant_rounds >= 4:
                break
        return collected_codes

    def _get_org_grid_snapshot(
        self,
        wait_for_present: bool = False,
        expected_count: int | None = None,
    ) -> dict[str, Any] | None:
        deadline = time.monotonic() + 5 if wait_for_present else time.monotonic()
        while True:
            snapshot = self.page.evaluate(
                r"""(requiredHeaders) => {
                    const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                    const hasRequiredHeaders = (headers, requiredHeaders) =>
                        requiredHeaders.every((requiredHeader) =>
                            headers.some((header) => header.includes(requiredHeader))
                        );
                    const grids = [...document.querySelectorAll('.kd-table-container')]
                        .map((grid) => {
                            const headers = [...grid.querySelectorAll('th .kd-table-header-title')]
                                .map((item) => normalize(item.innerText))
                                .filter(Boolean);
                            const rect = grid.getBoundingClientRect();
                            const area = Math.max(rect.width, 0) * Math.max(rect.height, 0);
                            const body = grid.querySelector('.kd-table-body.kd-horizontal-scroll-container');
                            const rows = [...grid.querySelectorAll('tbody tr')].map((tr) =>
                                [...tr.querySelectorAll('td')].map((td) => normalize(td.innerText))
                            );
                            return {
                                headers,
                                area,
                                rows,
                                scrollTop: body ? body.scrollTop : 0,
                                scrollHeight: body ? body.scrollHeight : 0,
                                clientHeight: body ? body.clientHeight : 0,
                            };
                        })
                        .filter((grid) => hasRequiredHeaders(grid.headers, requiredHeaders));
                    grids.sort((left, right) => right.area - left.area);
                    return grids[0] || null;
                }""",
                ORG_HEADERS,
            )
            if snapshot and expected_count and expected_count > 1:
                has_scroll = snapshot.get("scrollHeight", 0) > snapshot.get("clientHeight", 0)
                has_multiple_rows = len(snapshot.get("rows", [])) > 1
                if not has_scroll and not has_multiple_rows and time.monotonic() < deadline:
                    self.page.wait_for_timeout(200)
                    continue
            if snapshot or not wait_for_present or time.monotonic() >= deadline:
                return snapshot
            self.page.wait_for_timeout(200)

    def _close_org_detail_with_escape(self) -> None:
        if self._org_detail_closed():
            return
        for _ in range(2):
            self.page.keyboard.press("Escape")
            if self._wait_for_org_detail_closed(1500):
                return

    def _org_detail_closed(self) -> bool:
        snapshot = self._get_org_grid_snapshot(wait_for_present=False)
        return snapshot is None

    def _wait_for_org_detail_closed(self, timeout_ms: int) -> bool:
        deadline = time.monotonic() + (timeout_ms / 1000)
        while time.monotonic() < deadline:
            if self._org_detail_closed():
                return True
            self.page.wait_for_timeout(150)
        return self._org_detail_closed()

    @staticmethod
    def _coerce_expected_count(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        value_text = str(value).strip()
        if not value_text:
            return None
        try:
            parsed = int(value_text)
        except ValueError:
            return None
        if parsed < 0:
            return None
        return parsed

    @staticmethod
    def _normalize_row_cells(headers: Sequence[str], row: Sequence[str]) -> list[str]:
        normalized = list(row)
        while len(normalized) > len(headers) and normalized and not normalized[0]:
            normalized.pop(0)
        if len(normalized) > len(headers):
            normalized = normalized[: len(headers)]
        if len(normalized) < len(headers):
            normalized.extend([""] * (len(headers) - len(normalized)))
        return normalized

    @staticmethod
    def _detail_row_sort_key(headers: Sequence[str], row: Sequence[str]) -> tuple[int, str]:
        normalized_row = PermissionCollectFlow._normalize_row_cells(headers, row)
        mapped = {
            headers[idx]: normalized_row[idx] if idx < len(normalized_row) else ""
            for idx in range(len(headers))
        }
        line_text = (mapped.get("#") or "").strip()
        try:
            line_no = int(line_text)
        except ValueError:
            line_no = 10**9
        fallback = "|".join(normalized_row)
        return (line_no, fallback)

    @staticmethod
    def _is_empty_detail_row(mapped: dict[str, str]) -> bool:
        # Virtualized grids can render a trailing placeholder row that only keeps
        # the row number or org-detail link text but has no real permission detail content.
        detail_row = {
            "apply_type": mapped.get("申请类型", ""),
            "role_name": mapped.get("角色名称", ""),
            "role_code": mapped.get("角色编码", ""),
        }
        return not PermissionCollectFlow._is_detail_row_business_valid(detail_row)

    @staticmethod
    def _is_detail_row_business_valid(detail_row: dict[str, Any]) -> bool:
        business_fields = (
            (detail_row.get("apply_type") or "").strip(),
            (detail_row.get("role_name") or "").strip(),
            (detail_row.get("role_code") or "").strip(),
        )
        return any(business_fields)

    @staticmethod
    def _is_org_grid_missing_error(exc: Exception) -> bool:
        return "Organization detail grid not found after clicking detail link" in str(exc)

    @staticmethod
    def _extract_detail_count(detail_text: str) -> int | None:
        match = DETAIL_COUNT_RE.search(detail_text or "")
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _detail_link_text(expected_count: Any) -> str:
        if expected_count is None or expected_count == "":
            return "查看详情"
        return f"查看详情({int(expected_count)})"

    @staticmethod
    def _todo_row_sort_key(headers: Sequence[str], row: Sequence[str]) -> tuple[int, str]:
        normalized_row = PermissionCollectFlow._normalize_row_cells(headers, row)
        mapped = {
            headers[idx]: normalized_row[idx] if idx < len(normalized_row) else ""
            for idx in range(len(headers))
        }
        line_text = (mapped.get("#") or "").strip()
        try:
            line_no = int(line_text)
        except ValueError:
            line_no = 10**9
        return (line_no, (mapped.get("单据编号") or "").strip())
