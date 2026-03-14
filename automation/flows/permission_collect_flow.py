from __future__ import annotations

import logging
import re
import time
from collections.abc import Sequence
from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


TODO_HEADERS = ["单据", "单据编号", "发起人", "主题", "状态"]
DETAIL_HEADERS = ["申请类型", "角色名称", "角色编码", "行政组织", "行政组织详情"]
ORG_HEADERS = ["组织编码", "组织名称", "所属公司", "组织长名称"]
APPROVAL_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
DETAIL_COUNT_RE = re.compile(r"查看详情\((\d+)\)")


class PermissionCollectFlow:
    def __init__(self, page: Page, logger: logging.Logger, timeout_ms: int, home_url: str) -> None:
        self.page = page
        self.logger = logger
        self.timeout_ms = timeout_ms
        self.home_url = home_url

    def collect(self, document_no: str | None = None, limit: int = 1) -> list[dict[str, Any]]:
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
            self.logger.info("Collecting document: %s", current_document_no)
            if index > 0:
                self.return_to_todo_list()
            self.open_document(current_document_no)
            documents.append(self.collect_current_document())
        return documents

    def open_todo_list(self) -> None:
        trigger = self.page.locator("div[id^='processflexpanelap_']").filter(has_text="待办任务").first
        trigger.wait_for(state="visible", timeout=self.timeout_ms)
        trigger.click(force=True)
        self.page.locator("#gridview").first.wait_for(state="visible", timeout=self.timeout_ms)
        self._wait_for_grid_headers(TODO_HEADERS)

    def open_document(self, document_no: str) -> None:
        subject_text = f"单据编号：{document_no}"
        subject_link = self.page.locator("span.link-cell-content").filter(has_text=subject_text).first
        subject_link.wait_for(state="visible", timeout=self.timeout_ms)
        subject_link.click(force=True)
        self.page.locator("#fs_baseinfo").wait_for(state="visible", timeout=self.timeout_ms)
        self.page.locator("#entryentity").wait_for(state="visible", timeout=self.timeout_ms)

    def return_to_todo_list(self) -> None:
        tab = self.page.locator("li[data-splitscreen-pageid$='hrobs_pc_messagecenter']").first
        tab.wait_for(state="visible", timeout=self.timeout_ms)
        tab.click(force=True)
        self._wait_for_grid_headers(TODO_HEADERS)

    def collect_current_document(self) -> dict[str, Any]:
        basic_info = self.extract_basic_info()
        permission_details = self.extract_grid_rows(DETAIL_HEADERS)
        approval_records = self.extract_approval_records()
        organization_codes = self.extract_all_organization_codes(basic_info.get("单据编号", ""), permission_details)
        return {
            "basic_info": {
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
            },
            "permission_details": permission_details,
            "approval_records": approval_records,
            "organization_codes": organization_codes,
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
        return normalized_rows

    def extract_all_organization_codes(self, document_no: str, detail_rows: Sequence[dict[str, str]]) -> list[str]:
        codes: set[str] = set()
        row_count = len(detail_rows)
        for row_idx in range(row_count):
            if row_idx > 0 and not self._org_detail_closed():
                self.page.goto(self.home_url, wait_until="domcontentloaded")
                self.page.wait_for_timeout(1500)
                self.open_todo_list()
                self.open_document(document_no)

            grid_info = self._extract_best_grid(DETAIL_HEADERS)
            entry_grid_selector = grid_info["selector"]
            expected_count = detail_rows[row_idx].get("org_scope_count")
            detail_text = self._detail_link_text(expected_count)
            row_locator = self.page.locator(f"{entry_grid_selector} tbody tr").nth(row_idx)
            cell_link = row_locator.locator("span.link-cell-content").filter(has_text=detail_text).first
            if cell_link.count() == 0 and detail_text:
                cell_link = row_locator.locator(f"text={detail_text}").first
            if cell_link.count() == 0:
                cell_link = row_locator.locator("span.link-cell-content").filter(has_text="查看详情").first
            if cell_link.count() == 0:
                continue
            cell_link.scroll_into_view_if_needed(timeout=self.timeout_ms)
            cell_link.click(force=True)
            self.page.wait_for_timeout(1200)
            collected = self._extract_codes_from_org_grid(expected_count)
            codes.update(collected)
            self.logger.info(
                "Collected %s organization codes from detail row %s",
                len(collected),
                detail_rows[row_idx].get("line_no", row_idx + 1),
            )
            self._close_org_detail_with_escape()
        return sorted(codes)

    def extract_approval_records(self) -> list[dict[str, str]]:
        approval_tab = self.page.locator("#tabap .kd-cq-tabs-tab").filter(has_text="审批记录").first
        approval_tab.wait_for(state="visible", timeout=self.timeout_ms)
        approval_tab.click(force=True)
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        while time.monotonic() < deadline:
            visible_blocks = self.page.locator("li.kd-cq-tabpage:not(.hidden) ._2QHPFSVv")
            if visible_blocks.count() > 0:
                break
            self.page.wait_for_timeout(200)
        else:
            raise PlaywrightTimeoutError("Approval record tab did not become visible")
        records = self.page.evaluate(
            r"""() => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const blocks = [...document.querySelectorAll('li.kd-cq-tabpage:not(.hidden) ._2QHPFSVv')];
                return blocks.map((block, index) => {
                    const header = block.querySelector('h4');
                    const fullHeader = normalize(header?.innerText || '');
                    const timeText = normalize(block.querySelector('p.zPG-NFNf')?.innerText || '');
                    const opinionNode = block.querySelector('p._3aIXYPkW');
                    const opinionVisible = opinionNode && window.getComputedStyle(opinionNode).display !== 'none';
                    const opinion = opinionVisible ? normalize(opinionNode.innerText) : '';
                    return {
                        record_seq: String(index + 1),
                        header_text: fullHeader,
                        approval_time: timeText,
                        approval_opinion: opinion,
                        raw_text: normalize(block.innerText || ''),
                    };
                });
            }"""
        )
        normalized: list[dict[str, str]] = []
        for item in records:
            header_text = item.get("header_text", "")
            match = re.match(r"^(.*?)\s+([^\s]+\|[^\s]+)\s+(.*?)$", header_text)
            node_name = ""
            approver_info = ""
            approval_action = ""
            approver_name = ""
            approver_org_or_position = ""
            if match:
                node_name = match.group(1).strip()
                approver_info = match.group(2).strip()
                approval_action = match.group(3).strip()
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

    def _extract_best_grid(self, required_headers: Sequence[str]) -> dict[str, Any]:
        grid = self.page.evaluate(
            r"""(requiredHeaders) => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const grids = [...document.querySelectorAll('.kd-table-container')].map((grid, index) => {
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
                    };
                });
                const matched = grids.filter((grid) => requiredHeaders.every((header) => grid.headers.includes(header)));
                matched.sort((left, right) => right.area - left.area);
                return matched[0] || null;
            }""",
            list(required_headers),
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
                        const grids = [...document.querySelectorAll('.kd-table-container')].filter((grid) => {
                            const headers = [...grid.querySelectorAll('th .kd-table-header-title')]
                                .map((item) => normalize(item.innerText))
                                .filter(Boolean);
                            return requiredHeaders.every((header) => headers.includes(header));
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
                        .filter((grid) => requiredHeaders.every((header) => grid.headers.includes(header)));
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
        for _ in range(3):
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(400)
            if self._org_detail_closed():
                return

    def _org_detail_closed(self) -> bool:
        snapshot = self._get_org_grid_snapshot(wait_for_present=False)
        return snapshot is None

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
