from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from collections.abc import Sequence
from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


TODO_HEADERS = ["单据", "单据编号", "发起人", "主题", "状态"]
DETAIL_HEADERS = ["申请类型", "角色名称", "角色编码"]
DETAIL_PREFERRED_HEADERS = ["行政组织详情", "行政组织", "角色描述", "参保单位"]
ORG_HEADERS = ["组织编码", "组织名称", "所属公司", "组织长名称"]
APPROVAL_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")
DETAIL_COUNT_RE = re.compile(r"查看详情\((\d+)\)")


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
            started_at = datetime.now()
            started_ts = time.monotonic()
            if index > 0:
                self.return_to_todo_list()
            self.open_document(current_document_no)
            document = self.collect_current_document()
            elapsed_seconds = round(time.monotonic() - started_ts, 3)
            finished_at = datetime.now()
            document["collection_started_at"] = started_at.isoformat(timespec="seconds")
            document["collection_finished_at"] = finished_at.isoformat(timespec="seconds")
            document["collection_elapsed_seconds"] = elapsed_seconds
            self.logger.info(
                "Collected document %s in %.3f seconds",
                current_document_no,
                elapsed_seconds,
            )
            documents.append(document)
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
        self._wait_for_document_loaded(document_no)

    def return_to_todo_list(self) -> None:
        tab = self.page.locator("li[data-splitscreen-pageid$='hrobs_pc_messagecenter']").first
        tab.wait_for(state="visible", timeout=self.timeout_ms)
        tab.click(force=True)
        self._wait_for_grid_headers(TODO_HEADERS)

    def collect_current_document(self) -> dict[str, Any]:
        basic_info = self.extract_basic_info()
        self._wait_for_permission_detail_grid_ready(basic_info.get("单据编号", ""))
        permission_details = self.extract_grid_rows(DETAIL_HEADERS)
        role_organization_scopes = self.extract_role_organization_scopes(
            basic_info.get("单据编号", ""),
            permission_details,
        )
        approval_records = self.extract_approval_records()
        organization_codes = sorted(
            {
                code
                for item in role_organization_scopes
                for code in item.get("organization_codes", [])
                if isinstance(code, str) and code.strip()
            }
        )
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
            "role_organization_scopes": role_organization_scopes,
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

    def extract_role_organization_scopes(
        self,
        document_no: str,
        detail_rows: Sequence[dict[str, str]],
    ) -> list[dict[str, Any]]:
        role_scopes: list[dict[str, Any]] = []
        grid_info = self._wait_for_permission_detail_grid_ready(document_no)
        entry_grid_selector = grid_info["selector"]
        row_count = len(detail_rows)
        for row_idx in range(row_count):
            self._wait_for_grid_row_ready(entry_grid_selector, row_idx)
            detail_row = detail_rows[row_idx]
            role_code = (detail_row.get("role_code") or "").strip()
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
                    "Skipped organization detail collection for skip-org-scope role %s on row %s",
                    role_code,
                    detail_row.get("line_no", row_idx + 1),
                )
                continue
            self._scroll_grid_horizontal_to_end(entry_grid_selector)

            cell_link = self._wait_for_detail_link_ready(
                document_no=document_no,
                grid_selector=entry_grid_selector,
                row_idx=row_idx,
                detail_row=detail_row,
            )
            detail_text = cell_link.text_content() if cell_link.count() > 0 else ""
            expected_count = self._extract_detail_count(detail_text) if detail_text else detail_row.get("org_scope_count")
            collected: list[str] = []
            if cell_link.count() > 0:
                cell_link.scroll_into_view_if_needed(timeout=self.timeout_ms)
                cell_link.click(force=True)
                self.page.wait_for_timeout(1200)
                collected = self._extract_codes_from_org_grid(expected_count)
                self.logger.info(
                    "Collected %s organization codes from detail row %s",
                    len(collected),
                    detail_row.get("line_no", row_idx + 1),
                )
                self._close_org_detail_with_escape()

            role_scopes.append(
                {
                    "line_no": detail_row.get("line_no", ""),
                    "role_code": role_code,
                    "role_name": detail_row.get("role_name", ""),
                    "organization_codes": sorted({code for code in collected if code}),
                }
            )
        return role_scopes

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
                rows = grid.get("rows") or []
                if row_idx is not None and len(rows) <= row_idx:
                    raise RuntimeError(f"detail row index {row_idx} out of range, row_count={len(rows)}")
                return grid
            except Exception as exc:
                last_error = str(exc)
            self.page.wait_for_timeout(200)

        raise PlaywrightTimeoutError(
            f"Permission detail grid not ready. document_no={document_no!r}, last_error={last_error}"
        )

    def _wait_for_grid_row_ready(self, grid_selector: str, row_idx: int) -> None:
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        row_locator = self.page.locator(f"{grid_selector} tbody tr").nth(row_idx)
        while time.monotonic() < deadline:
            try:
                row_locator.wait_for(state="visible", timeout=1000)
                return
            except PlaywrightTimeoutError:
                self.page.wait_for_timeout(200)
        raise PlaywrightTimeoutError(
            f"Permission detail row not ready. grid_selector={grid_selector!r}, row_idx={row_idx}"
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
            self._scroll_grid_horizontal_to_end(grid_selector)
            row_locator = self.page.locator(f"{grid_selector} tbody tr").nth(row_idx)
            try:
                row_locator.wait_for(state="visible", timeout=1000)
            except PlaywrightTimeoutError:
                self.page.wait_for_timeout(200)
                continue
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

    def _scroll_grid_horizontal_to_end(self, grid_selector: str) -> None:
        self.page.evaluate(
            r"""(selector) => {
                const grid = document.querySelector(selector);
                if (!grid) return;
                const body = grid.querySelector('.kd-table-body.kd-horizontal-scroll-container');
                if (!body) return;
                body.scrollLeft = body.scrollWidth;
            }""",
            grid_selector,
        )
        self.page.wait_for_timeout(150)

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
