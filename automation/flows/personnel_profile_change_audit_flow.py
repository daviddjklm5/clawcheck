from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Download, Locator, Page, Response, TimeoutError as PlaywrightTimeoutError

from automation.utils.playwright_helpers import save_screenshot


class PersonnelProfileChangeAuditFlow:
    MODULE_NAME = "人员档案信息变更申请"
    MODULE_READY_TEXT = "我的审批进度"
    RECENT_MENU_TEXT = "最近使用"
    DETAIL_READY_TEXT = "变更申请单"
    LIST_FORM_ID = "hspm_infoapproval"
    HEAD_FORM_ID = "hspm_approvalhead"
    GROUP_FORM_ID = "hspm_groupfieldapproval"
    ATTACHMENT_FORM_ID = "hspm_attachmentapproval"
    PAGINATION_TRIGGER_SELECTOR = (
        "#gridview .kd-pagination-selector button.kd-dropdown-trigger."
        "kd-pagination-selector-size.kd-pagination-options-dropdown"
    )
    PAGINATION_OPTION_SELECTOR = ".kd-dropdown.kd-cq-pagination-dropdown li.kd-dropdown-menu-item"
    GRID_SELECTOR = "#gridview"
    SECTION_TITLE_RE = re.compile(r"(?:附件信息|[^\s]{1,24}信息)\d*$")
    NOTE_PREFIX = "注："
    CHANGE_TYPE_LABELS = {
        "0": "修改",
        "1": "新增",
        "2": "删除",
    }
    PAGE_SIZE_OPTION_INDEX = {
        5: 0,
        10: 1,
        20: 2,
        50: 3,
        100: 4,
        500: 5,
        1000: 6,
    }
    ATTACHMENT_FILE_RE = re.compile(
        r"[^,，、\s]+\.(?:pdf|jpg|jpeg|png|gif|bmp|doc|docx|xls|xlsx|ppt|pptx|zip|rar|7z|txt)",
        re.IGNORECASE,
    )

    def __init__(self, page: Page, logger: logging.Logger, timeout_ms: int, home_url: str) -> None:
        self.page = page
        self.logger = logger
        self.timeout_ms = timeout_ms
        self.home_url = home_url
        self._captured_network_payloads: list[dict[str, Any]] = []
        self.page.on("response", self._handle_response)

    def reset_network_capture(self) -> None:
        self._captured_network_payloads.clear()

    def open_module_page(self, page_size: int = 100) -> None:
        self.page.goto(self.home_url, wait_until="domcontentloaded")
        self._wait_for_home_ready()
        if not self._is_module_ready():
            self._ensure_recent_menu_opened()
            self._click_recent_module_entry()
            self._wait_for_module_ready()
        self.ensure_page_size(page_size)

    def ensure_page_size(self, page_size: int) -> None:
        if page_size not in self.PAGE_SIZE_OPTION_INDEX:
            raise ValueError(f"Unsupported page size: {page_size}")

        trigger = self.page.locator(self.PAGINATION_TRIGGER_SELECTOR).first
        trigger.wait_for(state="visible", timeout=self.timeout_ms)
        current_selected_key = self.page.evaluate(
            r"""() => {
                const selected = document.querySelector('.kd-dropdown.kd-cq-pagination-dropdown li.kd-dropdown-menu-item.selected');
                return selected ? String(selected.getAttribute('data-key') || '') : '';
            }"""
        )
        if current_selected_key == str(page_size):
            return

        deadline = time.monotonic() + (self.timeout_ms / 1000)
        last_text = ""
        while time.monotonic() < deadline:
            last_text = self._normalize_text(trigger.inner_text())
            if self._extract_first_number(last_text) == str(page_size):
                return
            trigger.click(force=True)
            option = self.page.locator(self.PAGINATION_OPTION_SELECTOR).nth(self.PAGE_SIZE_OPTION_INDEX[page_size])
            option.wait_for(state="visible", timeout=3000)
            option.click(force=True)
            self.page.wait_for_timeout(500)

        raise PlaywrightTimeoutError(f"Pagination size did not become {page_size}. last_text={last_text}")

    def collect_list_rows(self, limit: int) -> dict[str, Any]:
        self.page.locator(self.GRID_SELECTOR).first.wait_for(state="visible", timeout=self.timeout_ms)
        body_rows = self._parse_list_rows_from_body(limit=limit)
        if body_rows:
            return {
                "headers": ["#", "单据编号", "单据名称", "单据状态", "提交时间", "创建人姓名", "创建人工号"],
                "rows": body_rows,
            }
        payload_rows = self._latest_list_payload_ordered_rows(limit=limit)
        if payload_rows:
            return {
                "headers": ["#", "单据编号", "单据名称", "单据状态", "提交时间", "创建人姓名", "创建人工号"],
                "rows": payload_rows,
            }
        return self._collect_grid_rows(limit=limit)

    def collect_documents(
        self,
        *,
        limit: int,
        page_size: int = 100,
        screenshots_dir: Path | None = None,
        downloads_dir: Path | None = None,
        download_attachments: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        self.open_module_page(page_size=page_size)
        list_snapshot = self.collect_list_rows(limit=limit)
        documents: list[dict[str, Any]] = []
        failed_documents: list[dict[str, str]] = []

        for index, row in enumerate(list_snapshot.get("rows", []), start=1):
            row = self._normalize_list_row_payload(row)
            document_no = str(row.get("单据编号") or "").strip()
            if not document_no:
                continue
            try:
                if index > 1:
                    self.open_module_page(page_size=page_size)
                documents.append(
                    self.collect_document(
                        document_row=row,
                        screenshots_dir=screenshots_dir,
                        downloads_dir=downloads_dir,
                        download_attachments=download_attachments,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                failed_documents.append(
                    {
                        "document_no": document_no,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        return documents, failed_documents

    def open_document(self, document_no: str) -> None:
        link = self._find_list_document_link(document_no)
        if link is None:
            raise RuntimeError(f"Document not found in list grid: {document_no}")
        link.click(force=True)
        self._wait_for_document_ready(document_no)

    def collect_document(
        self,
        *,
        document_row: dict[str, str],
        screenshots_dir: Path | None = None,
        downloads_dir: Path | None = None,
        download_attachments: bool = False,
    ) -> dict[str, Any]:
        document_row = self._normalize_list_row_payload(document_row)
        document_no = str(document_row.get("单据编号") or "").strip()
        if not document_no:
            raise ValueError("Missing document number in list row")

        self.reset_network_capture()
        self.open_document(document_no)
        outline = self.collect_document_sample(document_no=document_no, screenshots_dir=screenshots_dir)
        network_bundle_ready = True
        try:
            self._wait_for_detail_network_bundle()
        except PlaywrightTimeoutError:
            network_bundle_ready = False
            self.logger.warning("Detail network bundle missing for %s, fallback to DOM tables", document_no)

        detail_payload = self._latest_infoapproval_detail_payload()
        head_payload = self._latest_captured_form_payload(self.HEAD_FORM_ID)
        group_payloads = self._captured_form_payloads(self.GROUP_FORM_ID)
        attachment_payloads = self._captured_form_payloads(self.ATTACHMENT_FORM_ID)
        head_fields = self._parse_head_fields(head_payload) if head_payload is not None else {}
        section_titles = [str(item).strip() for item in outline.get("section_titles", []) if str(item).strip()]
        visible_section_titles = [
            title
            for title in section_titles
            if title != self.NOTE_PREFIX and self.NOTE_PREFIX not in title
        ]
        section_index_lookup = {
            title: index
            for index, title in enumerate(visible_section_titles, start=1)
        }
        group_section_names = [title for title in visible_section_titles if "附件信息" not in title]
        attachment_section_names = [title for title in visible_section_titles if "附件信息" in title]

        summary_section = self._build_summary_section(
            document_row=document_row,
            outline=outline,
            head_fields=head_fields,
            detail_payload=detail_payload or {},
            section_index_lookup=section_index_lookup,
        )
        if network_bundle_ready and detail_payload is not None and head_payload is not None:
            group_sections = self._build_group_sections(
                group_payloads=group_payloads,
                group_section_names=group_section_names,
                section_index_lookup=section_index_lookup,
            )
            attachment_sections, attachment_records = self._build_attachment_sections(
                attachment_payloads=attachment_payloads,
                attachment_section_names=attachment_section_names,
                section_index_lookup=section_index_lookup,
                document_no=document_no,
                downloads_dir=downloads_dir,
                download_attachments=download_attachments,
            )
        else:
            group_sections, attachment_sections, attachment_records = self._build_dom_fallback_sections(
                document_no=document_no,
                outline=outline,
                visible_section_titles=visible_section_titles,
                section_index_lookup=section_index_lookup,
                downloads_dir=downloads_dir,
                download_attachments=download_attachments,
            )
        all_sections = [summary_section, *group_sections, *attachment_sections]
        all_sections = [section for section in all_sections if section]
        all_sections.sort(key=lambda item: (int(item.get("section_seq", 0) or 0), str(item.get("section_type") or "")))

        basic_info = {
            "document_no": document_no,
            "document_name": str(document_row.get("单据名称") or "").strip(),
            "document_status": str(document_row.get("单据状态") or "").strip() or str(head_fields.get("billstatusshow") or "").strip(),
            "submit_time": str(document_row.get("提交时间") or "").strip(),
            "creator_name": str(document_row.get("创建人姓名") or "").strip(),
            "creator_employee_no": str(document_row.get("创建人工号") or "").strip(),
            "change_person": str(head_fields.get("modifyman") or "").strip(),
            "change_submit_time": str(head_fields.get("sumbittime") or head_fields.get("modifytime") or "").strip(),
            "applicant_summary_line": str(outline.get("applicant_summary_line") or "").strip(),
            "header_fields": head_fields,
            "section_count": len(all_sections),
            "attachment_count": len(attachment_records),
        }

        return {
            "basic_info": basic_info,
            "sections": all_sections,
            "attachments": attachment_records,
            "outline": outline,
            "raw_snapshot": {
                "list_row": document_row,
                "head_fields": head_fields,
                "section_titles": section_titles,
                "group_payload_count": len(group_payloads),
                "attachment_payload_count": len(attachment_payloads),
                "detail_payload": detail_payload,
            },
        }

    def collect_document_sample(
        self,
        *,
        document_no: str,
        screenshots_dir: Path | None = None,
    ) -> dict[str, Any]:
        if screenshots_dir is not None:
            save_screenshot(self.page, screenshots_dir, f"sample310_{document_no}")

        body_text = self._get_body_text()
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        section_titles: list[str] = []
        applicant_summary_line = ""
        for line in lines:
            if not applicant_summary_line and "工号" in line and document_no not in line:
                applicant_summary_line = line
            if line.startswith(self.NOTE_PREFIX):
                if line not in section_titles:
                    section_titles.append(line)
                continue
            if self.SECTION_TITLE_RE.fullmatch(line) and line not in section_titles:
                section_titles.append(line)

        tables = self.page.evaluate(
            r"""() => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                };
                const tables = [...document.querySelectorAll('table')].filter(visible);
                return tables.map((table) => {
                    const headers = [...table.querySelectorAll('thead th, tr:first-child th, tr:first-child td')]
                        .map((cell) => normalize(cell.innerText))
                        .filter(Boolean);
                    const rows = [...table.querySelectorAll('tbody tr')]
                        .map((tr) => [...tr.querySelectorAll('td')].map((cell) => normalize(cell.innerText)))
                        .filter((row) => row.some(Boolean));
                    let title = '';
                    let current = table.previousElementSibling;
                    for (let step = 0; current && step < 4; step += 1) {
                        const text = normalize(current.innerText || '');
                        if (text) {
                            title = text;
                            break;
                        }
                        current = current.previousElementSibling;
                    }
                    return { title, headers, rows };
                });
            }"""
        )
        attachment_names = self._extract_attachment_names(body_text)
        return {
            "document_no": document_no,
            "section_titles": section_titles,
            "tables": tables,
            "attachment_names": attachment_names,
            "applicant_summary_line": applicant_summary_line,
        }

    def _handle_response(self, response: Response) -> None:
        try:
            form_id, action = self._parse_form_request(response.url)
            if form_id not in {self.LIST_FORM_ID, self.HEAD_FORM_ID, self.GROUP_FORM_ID, self.ATTACHMENT_FORM_ID}:
                return
            if action.lower() != "loaddata":
                return
            payload: Any
            try:
                payload = response.json()
            except Exception:
                response_text = response.text()
                stripped_text = str(response_text or "").strip()
                if not stripped_text or stripped_text[0] not in "{[":
                    return
                payload = json.loads(stripped_text)
        except Exception:  # noqa: BLE001
            return

        if not isinstance(payload, dict):
            return

        self._captured_network_payloads.append(
            {
                "form_id": form_id,
                "action": action,
                "url": response.url,
                "payload": payload,
                "captured_at": time.monotonic(),
            }
        )

    def _parse_form_request(self, url: str) -> tuple[str, str]:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        form_id = str((query.get("f") or [""])[0] or "").strip()
        action = str((query.get("ac") or [""])[0] or "").strip()
        return form_id, action

    def _wait_for_home_ready(self) -> None:
        self.page.locator("body").first.wait_for(state="visible", timeout=self.timeout_ms)
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        while time.monotonic() < deadline:
            if self._has_text(self.RECENT_MENU_TEXT) or self._is_module_ready():
                return
            self.page.wait_for_timeout(200)
        self.page.wait_for_timeout(1000)

    def _is_module_ready(self) -> bool:
        try:
            if not self._has_text(self.MODULE_READY_TEXT):
                return False
            grid = self.page.locator(self.GRID_SELECTOR).first
            return grid.count() > 0 and grid.is_visible(timeout=1000)
        except Exception:  # noqa: BLE001
            return False

    def _wait_for_module_ready(self) -> None:
        self.page.get_by_text(self.MODULE_READY_TEXT, exact=False).first.wait_for(state="visible", timeout=self.timeout_ms)
        self.page.locator(self.GRID_SELECTOR).first.wait_for(state="visible", timeout=self.timeout_ms)

    def _ensure_recent_menu_opened(self) -> None:
        if self._has_text(self.RECENT_MENU_TEXT):
            return
        self.page.mouse.click(24, 24)
        self.page.get_by_text(self.RECENT_MENU_TEXT, exact=False).first.wait_for(state="visible", timeout=self.timeout_ms)
        self.logger.info("Opened left-top recent menu")

    def _click_recent_module_entry(self) -> None:
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        while time.monotonic() < deadline:
            if self._is_module_ready():
                return
            if self._try_click_text(self.MODULE_NAME, exact=False, force=True, scope=None):
                return
            self.page.wait_for_timeout(300)
            if not self._has_text(self.RECENT_MENU_TEXT):
                self.page.mouse.click(24, 24)
        raise RuntimeError(f"Recent menu entry not found: {self.MODULE_NAME}")

    def _collect_grid_rows(self, limit: int) -> dict[str, Any]:
        if limit <= 0:
            return {"headers": [], "rows": []}

        headers: list[str] = []
        collected_rows: list[dict[str, str]] = []
        seen_keys: set[tuple[str, ...]] = set()
        self._set_grid_vertical_position(0)

        deadline = time.monotonic() + (self.timeout_ms / 1000)
        while time.monotonic() < deadline:
            snapshot = self._get_grid_snapshot()
            headers = [self._normalize_cell_text(item) for item in snapshot.get("headers", []) if self._normalize_cell_text(item)]
            for row in snapshot.get("rows", []):
                normalized_row = self._normalize_row_cells(headers, row)
                if (
                    headers
                    and headers[0] == "#"
                    and normalized_row
                    and normalized_row[0].startswith("AM-")
                ):
                    normalized_row = self._normalize_row_cells(headers, [str(len(collected_rows) + 1), *normalized_row])
                row_key = tuple(normalized_row)
                if not row_key or row_key in seen_keys:
                    continue
                seen_keys.add(row_key)
                collected_rows.append(self._build_list_row_payload(headers, normalized_row))
                if len(collected_rows) >= limit:
                    break
            if len(collected_rows) >= limit:
                break

            next_top = int(snapshot.get("scroll_top") or 0) + max(int(snapshot.get("client_height") or 0), 320)
            max_top = max(int(snapshot.get("scroll_height") or 0) - int(snapshot.get("client_height") or 0), 0)
            if next_top <= int(snapshot.get("scroll_top") or 0) or next_top > max_top:
                if int(snapshot.get("scroll_top") or 0) >= max_top:
                    break
                next_top = max_top
            self._set_grid_vertical_position(next_top)

        collected_rows.sort(key=self._list_row_sort_key)
        return {"headers": headers, "rows": collected_rows[:limit]}

    def _get_grid_snapshot(self) -> dict[str, Any]:
        snapshot = self.page.evaluate(
            r"""(selector) => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const grid = document.querySelector(selector);
                if (!grid) {
                    return { headers: [], rows: [], scroll_top: 0, scroll_height: 0, client_height: 0 };
                }
                const body = grid.querySelector('.kd-table-body.kd-horizontal-scroll-container')
                    || grid.querySelector('.kd-table-body');
                const headers = [...grid.querySelectorAll('th .kd-table-header-title, th')]
                    .map((item) => normalize(item.innerText))
                    .filter(Boolean);
                const rows = [...grid.querySelectorAll('tbody tr')]
                    .map((tr) => [...tr.querySelectorAll('td')].map((td) => normalize(td.innerText)))
                    .filter((row) => row.some(Boolean));
                return {
                    headers,
                    rows,
                    scroll_top: body ? body.scrollTop : 0,
                    scroll_height: body ? body.scrollHeight : 0,
                    client_height: body ? body.clientHeight : 0,
                };
            }""",
            self.GRID_SELECTOR,
        )
        return dict(snapshot or {})

    def _set_grid_vertical_position(self, scroll_top: int) -> None:
        self.page.evaluate(
            r"""(payload) => {
                const { selector, scrollTop } = payload;
                const grid = document.querySelector(selector);
                if (!grid) return;
                const body = grid.querySelector('.kd-table-body.kd-horizontal-scroll-container')
                    || grid.querySelector('.kd-table-body');
                if (body) {
                    body.scrollTop = scrollTop;
                    body.dispatchEvent(new Event('scroll', { bubbles: true }));
                }
            }""",
            {"selector": self.GRID_SELECTOR, "scrollTop": int(scroll_top)},
        )
        self.page.wait_for_timeout(200)

    def _build_list_row_payload(self, headers: list[str], row: list[str]) -> dict[str, str]:
        payload = {headers[index]: row[index] if index < len(row) else "" for index in range(len(headers))}
        if "单据编号" not in payload:
            payload["单据编号"] = ""
        alias_map = self._latest_list_payload_rows()
        document_no = str(payload.get("单据编号") or "").strip()
        if document_no and document_no in alias_map:
            merged = dict(alias_map[document_no])
            merged.update(payload)
            return merged
        return payload

    def _parse_list_rows_from_body(self, limit: int) -> list[dict[str, str]]:
        lines = [line.strip() for line in self._get_body_text().splitlines() if line.strip()]
        headers = ["#", "单据编号", "单据名称", "单据状态", "提交时间", "创建人姓名", "创建人工号"]
        rows: list[dict[str, str]] = []
        cursor = 0
        while cursor + len(headers) - 1 < len(lines) and len(rows) < limit:
            chunk = lines[cursor : cursor + len(headers)]
            if (
                chunk[0].isdigit()
                and re.fullmatch(r"AM-\d+", chunk[1])
                and "人员档案信息变更申请" in chunk[2]
                and re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", chunk[4])
                and re.fullmatch(r"\d{6,12}", chunk[6])
            ):
                rows.append({header: chunk[idx] for idx, header in enumerate(headers)})
                cursor += len(headers)
                continue
            cursor += 1
        return rows

    def _normalize_list_row_payload(self, row: dict[str, str]) -> dict[str, str]:
        normalized = {str(key): str(value or "").strip() for key, value in row.items()}
        values = [value for value in normalized.values() if value]
        document_no = normalized.get("单据编号", "")
        if not document_no or not re.fullmatch(r"AM-\d+", document_no):
            for value in values:
                matched = re.search(r"AM-\d+", value)
                if matched:
                    document_no = matched.group(0)
                    normalized["单据编号"] = document_no
                    break
        alias = self._latest_list_payload_rows().get(document_no or "")
        if alias:
            merged = dict(normalized)
            merged.update(alias)
            return merged
        if "单据名称" not in normalized or "人员档案信息变更申请" not in normalized.get("单据名称", ""):
            for value in values:
                if "人员档案信息变更申请" in value:
                    normalized["单据名称"] = value
                    break
        if "单据状态" not in normalized or normalized.get("单据状态") not in {"已提交", "审批中", "已废弃", "已完成", "已驳回"}:
            for value in values:
                if value in {"已提交", "审批中", "已废弃", "已完成", "已驳回"}:
                    normalized["单据状态"] = value
                    break
        if not normalized.get("提交时间"):
            for value in values:
                if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value):
                    normalized["提交时间"] = value
                    break
        return normalized

    def _latest_list_payload_ordered_rows(self, limit: int | None = None) -> list[dict[str, str]]:
        payload = self._latest_captured_form_payload(self.LIST_FORM_ID)
        if payload is None:
            return []
        rows = self._extract_rows_from_payload(payload)
        normalized_rows: list[dict[str, str]] = []
        for index, row in enumerate(rows, start=1):
            document_no = str(row.get("billno") or row.get("单据编号") or "").strip()
            if not document_no:
                continue
            normalized_rows.append(
                {
                    "#": str(index),
                    "单据编号": document_no,
                    "单据名称": str(row.get("billname") or row.get("单据名称") or "").strip(),
                    "单据状态": str(row.get("billstatusshow") or row.get("billstatus") or row.get("单据状态") or "").strip(),
                    "提交时间": str(row.get("createtime") or row.get("sumbittime") or row.get("提交时间") or "").strip(),
                    "创建人姓名": str(row.get("creator_name") or row.get("创建人姓名") or "").strip(),
                    "创建人工号": str(row.get("creator_number") or row.get("创建人工号") or "").strip(),
                }
            )
        if limit is not None and limit > 0:
            return normalized_rows[:limit]
        return normalized_rows

    def _latest_list_payload_rows(self) -> dict[str, dict[str, str]]:
        alias_map: dict[str, dict[str, str]] = {}
        for row in self._latest_list_payload_ordered_rows():
            document_no = str(row.get("单据编号") or "").strip()
            if not document_no:
                continue
            alias_map[document_no] = {
                "单据编号": document_no,
                "单据名称": str(row.get("单据名称") or "").strip(),
                "单据状态": str(row.get("单据状态") or "").strip(),
                "提交时间": str(row.get("提交时间") or "").strip(),
                "创建人姓名": str(row.get("创建人姓名") or "").strip(),
                "创建人工号": str(row.get("创建人工号") or "").strip(),
            }
        return alias_map

    def _find_list_document_link(self, document_no: str) -> Locator | None:
        self._set_grid_vertical_position(0)
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        while time.monotonic() < deadline:
            locator = self.page.locator(self.GRID_SELECTOR).get_by_text(document_no, exact=True).first
            try:
                if locator.count() > 0 and locator.is_visible(timeout=500):
                    return locator
            except Exception:  # noqa: BLE001
                pass
            snapshot = self._get_grid_snapshot()
            next_top = int(snapshot.get("scroll_top") or 0) + max(int(snapshot.get("client_height") or 0), 320)
            max_top = max(int(snapshot.get("scroll_height") or 0) - int(snapshot.get("client_height") or 0), 0)
            if int(snapshot.get("scroll_top") or 0) >= max_top:
                break
            self._set_grid_vertical_position(min(next_top, max_top))
        return None

    def _wait_for_document_ready(self, document_no: str) -> None:
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        last_body = ""
        while time.monotonic() < deadline:
            last_body = self._get_body_text()
            if self.DETAIL_READY_TEXT in last_body and document_no in last_body:
                return
            self.page.wait_for_timeout(200)
        raise PlaywrightTimeoutError(
            f"Document detail did not become ready for {document_no}. body={last_body[:500]}"
        )

    def _wait_for_detail_network_bundle(self) -> None:
        deadline = time.monotonic() + (self.timeout_ms / 1000)
        stable_rounds = 0
        last_count = -1
        while time.monotonic() < deadline:
            has_detail = self._latest_infoapproval_detail_payload() is not None
            has_head = self._latest_captured_form_payload(self.HEAD_FORM_ID) is not None
            if has_detail and has_head:
                count = len(self._captured_network_payloads)
                if count == last_count:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                    last_count = count
                if stable_rounds >= 3:
                    return
            self.page.wait_for_timeout(250)
        raise PlaywrightTimeoutError("Detail network bundle did not complete in time")

    def _latest_infoapproval_detail_payload(self) -> dict[str, Any] | None:
        payloads = self._captured_form_payloads(self.LIST_FORM_ID)
        for payload in reversed(payloads):
            if self._payload_contains_key(payload, "showForm"):
                return payload
        return payloads[-1] if payloads else None

    def _captured_form_payloads(self, form_id: str) -> list[dict[str, Any]]:
        return [
            item["payload"]
            for item in self._captured_network_payloads
            if item.get("form_id") == form_id and isinstance(item.get("payload"), dict)
        ]

    def _latest_captured_form_payload(self, form_id: str) -> dict[str, Any] | None:
        payloads = self._captured_form_payloads(form_id)
        return payloads[-1] if payloads else None

    def _parse_head_fields(self, payload: dict[str, Any]) -> dict[str, Any]:
        decoded_rows = self._extract_rows_from_payload(payload)
        fields: dict[str, Any] = {}
        if decoded_rows:
            fields.update(decoded_rows[0])
        for item in self._iter_dicts(payload):
            for key, value in item.items():
                if key in {"rows", "dataindex", "showForm", "metadata", "result"}:
                    continue
                if isinstance(value, (str, int, float, bool)) or value is None:
                    fields.setdefault(str(key), value)
        return fields

    def _build_summary_section(
        self,
        *,
        document_row: dict[str, str],
        outline: dict[str, Any],
        head_fields: dict[str, Any],
        detail_payload: dict[str, Any],
        section_index_lookup: dict[str, int],
    ) -> dict[str, Any]:
        section_name = "人员信息"
        section_seq = int(section_index_lookup.get(section_name) or 1)
        summary_fields = [
            ("单据编号", str(document_row.get("单据编号") or "").strip()),
            ("单据名称", str(document_row.get("单据名称") or "").strip()),
            ("单据状态", str(document_row.get("单据状态") or head_fields.get("billstatusshow") or "").strip()),
            ("提交时间", str(document_row.get("提交时间") or "").strip()),
            ("创建人姓名", str(document_row.get("创建人姓名") or "").strip()),
            ("创建人工号", str(document_row.get("创建人工号") or "").strip()),
            ("变更人", str(head_fields.get("modifyman") or "").strip()),
            ("提交变更时间", str(head_fields.get("sumbittime") or head_fields.get("modifytime") or "").strip()),
            ("申请人摘要信息", str(outline.get("applicant_summary_line") or "").strip()),
        ]
        rows = [
            {
                "row_seq": row_index,
                "fields": [
                    {"field_seq": 1, "field_name": "字段名称", "field_value": field_name, "field_type": "summary_key"},
                    {"field_seq": 2, "field_name": "字段值", "field_value": field_value, "field_type": "summary_value"},
                ],
            }
            for row_index, (field_name, field_value) in enumerate(summary_fields, start=1)
            if field_value
        ]
        return {
            "section_seq": section_seq,
            "section_name": section_name,
            "subsection_seq": 1,
            "subsection_name": section_name,
            "section_type": "summary",
            "headers": ["字段名称", "字段值"],
            "rows": rows,
            "raw_payload": detail_payload,
        }

    def _build_group_sections(
        self,
        *,
        group_payloads: list[dict[str, Any]],
        group_section_names: list[str],
        section_index_lookup: dict[str, int],
    ) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        for index, payload in enumerate(group_payloads, start=1):
            decoded_rows = self._extract_rows_from_payload(payload)
            if not decoded_rows:
                continue
            section_name = group_section_names[index - 1] if index - 1 < len(group_section_names) else f"业务区段{index}"
            section_seq = int(section_index_lookup.get(section_name) or index + 1)
            rows = []
            for row_seq, row in enumerate(decoded_rows, start=1):
                normalized_row = self._normalize_change_row(row)
                row_fields = [
                    {
                        "field_seq": field_index,
                        "field_name": field_name,
                        "field_value": value,
                        "field_type": "table_cell",
                    }
                    for field_index, (field_name, value) in enumerate(normalized_row, start=1)
                    if value
                ]
                rows.append({"row_seq": row_seq, "fields": row_fields})
            sections.append(
                {
                    "section_seq": section_seq,
                    "section_name": section_name,
                    "subsection_seq": index,
                    "subsection_name": section_name,
                    "section_type": "change_table",
                    "headers": ["序号", "操作类型", "变更项", "变更前", "变更后", "不通过", "理由", "数据引用ID"],
                    "rows": rows,
                    "raw_payload": payload,
                }
            )
        return sections

    def _build_attachment_sections(
        self,
        *,
        attachment_payloads: list[dict[str, Any]],
        attachment_section_names: list[str],
        section_index_lookup: dict[str, int],
        document_no: str,
        downloads_dir: Path | None,
        download_attachments: bool,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        sections: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        for index, payload in enumerate(attachment_payloads, start=1):
            decoded_rows = self._extract_rows_from_payload(payload)
            if not decoded_rows:
                continue
            section_name = attachment_section_names[index - 1] if index - 1 < len(attachment_section_names) else f"附件信息{index}"
            section_seq = int(section_index_lookup.get(section_name) or index + 1)
            rows = []
            for row_seq, row in enumerate(decoded_rows, start=1):
                normalized_row = self._normalize_attachment_row(row)
                row_fields = [
                    {
                        "field_seq": field_index,
                        "field_name": field_name,
                        "field_value": value,
                        "field_type": "table_cell",
                    }
                    for field_index, (field_name, value) in enumerate(normalized_row, start=1)
                    if value
                ]
                rows.append({"row_seq": row_seq, "fields": row_fields})
                attachments.extend(
                    self._build_attachment_records(
                        document_no=document_no,
                        section_seq=section_seq,
                        section_name=section_name,
                        subsection_seq=index,
                        subsection_name=section_name,
                        row_seq=row_seq,
                        row=row,
                        downloads_dir=downloads_dir,
                        download_attachments=download_attachments,
                    )
                )
            sections.append(
                {
                    "section_seq": section_seq,
                    "section_name": section_name,
                    "subsection_seq": index,
                    "subsection_name": section_name,
                    "section_type": "attachment_table",
                    "headers": ["序号", "变更项", "变更前", "变更后", "不通过", "理由", "数据引用ID"],
                    "rows": rows,
                    "raw_payload": payload,
                }
            )
        return sections, attachments

    def _build_dom_fallback_sections(
        self,
        *,
        document_no: str,
        outline: dict[str, Any],
        visible_section_titles: list[str],
        section_index_lookup: dict[str, int],
        downloads_dir: Path | None,
        download_attachments: bool,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        group_sections: list[dict[str, Any]] = []
        attachment_sections: list[dict[str, Any]] = []
        attachments: list[dict[str, Any]] = []
        tables = [table for table in outline.get("tables", []) if isinstance(table, dict)]
        for index, table in enumerate(tables, start=1):
            title = str(table.get("title") or "").strip()
            headers = [str(item).strip() for item in table.get("headers", []) if str(item).strip()]
            table_rows = [row for row in table.get("rows", []) if isinstance(row, list)]
            if headers and headers[0].isdigit():
                table_rows = [headers, *table_rows]
                headers = self._guess_dom_table_headers(max(len(row) for row in table_rows))
            if not title:
                if index - 1 < len(visible_section_titles):
                    title = visible_section_titles[index - 1]
                else:
                    title = f"区段{index}"
            section_seq = int(section_index_lookup.get(title) or index + 1)
            rows = []
            for row_seq, row in enumerate(table_rows, start=1):
                row_fields = []
                for field_index, cell_value in enumerate(row, start=1):
                    field_name = headers[field_index - 1] if field_index - 1 < len(headers) else f"列{field_index}"
                    row_fields.append(
                        {
                            "field_seq": field_index,
                            "field_name": field_name,
                            "field_value": str(cell_value or "").strip(),
                            "field_type": "table_cell",
                        }
                    )
                rows.append({"row_seq": row_seq, "fields": row_fields})
                if "附件信息" in title:
                    attachments.extend(
                        self._build_dom_attachment_records(
                            document_no=document_no,
                            section_seq=section_seq,
                            section_name=title,
                            subsection_seq=index,
                            subsection_name=title,
                            row_seq=row_seq,
                            headers=headers,
                            row=row,
                            downloads_dir=downloads_dir,
                            download_attachments=download_attachments,
                        )
                    )
            if not rows:
                continue
            section_payload = {
                "section_seq": section_seq,
                "section_name": title,
                "subsection_seq": index,
                "subsection_name": title,
                "section_type": "attachment_table" if "附件信息" in title else "change_table",
                "headers": headers,
                "rows": rows,
                "raw_payload": table,
            }
            if "附件信息" in title:
                attachment_sections.append(section_payload)
            else:
                group_sections.append(section_payload)

        if not attachments:
            attachment_names = [str(item).strip() for item in outline.get("attachment_names", []) if str(item).strip()]
            for attachment_seq, attachment_name in enumerate(attachment_names, start=1):
                download_result = self._resolve_attachment_download(
                    file_name=attachment_name,
                    target_dir=(downloads_dir / "personnel_profile_change_audit" / document_no) if downloads_dir is not None else None,
                    download_attachments=download_attachments,
                )
                attachments.append(
                    {
                        "document_no": document_no,
                        "section_seq": int(section_index_lookup.get("附件信息") or (len(group_sections) + 2)),
                        "section_name": "附件信息",
                        "subsection_seq": 1,
                        "subsection_name": "附件信息",
                        "row_seq": 1,
                        "change_item": "",
                        "attachment_seq": attachment_seq,
                        "attachment_name": attachment_name,
                        "attachment_old_value": "",
                        "attachment_new_value": attachment_name,
                        "relative_path": download_result.get("relative_path") or "",
                        "download_status": download_result.get("download_status") or "",
                        "download_time": download_result.get("download_time") or "",
                        "file_size": download_result.get("file_size"),
                        "file_hash": download_result.get("file_hash") or "",
                        "datarefid": "",
                        "raw_payload": {"source": "dom_outline"},
                    }
                )

        return group_sections, attachment_sections, attachments

    @staticmethod
    def _guess_dom_table_headers(column_count: int) -> list[str]:
        base_headers = ["#", "操作类型", "变更项", "变更前", "变更后", "不通过", "理由"]
        if column_count <= len(base_headers):
            return base_headers[:column_count]
        headers = list(base_headers)
        for index in range(len(base_headers) + 1, column_count + 1):
            headers.append(f"扩展列{index}")
        return headers

    def _build_dom_attachment_records(
        self,
        *,
        document_no: str,
        section_seq: int,
        section_name: str,
        subsection_seq: int,
        subsection_name: str,
        row_seq: int,
        headers: list[str],
        row: list[Any],
        downloads_dir: Path | None,
        download_attachments: bool,
    ) -> list[dict[str, Any]]:
        joined_text = "\n".join(str(item or "").strip() for item in row)
        names = self._extract_attachment_names(joined_text)
        if not names:
            return []
        change_item = ""
        if headers:
            for index, header in enumerate(headers):
                if header == "变更项" and index < len(row):
                    change_item = str(row[index] or "").strip()
                    break
        records: list[dict[str, Any]] = []
        for attachment_seq, attachment_name in enumerate(names, start=1):
            download_result = self._resolve_attachment_download(
                file_name=attachment_name,
                target_dir=(downloads_dir / "personnel_profile_change_audit" / document_no) if downloads_dir is not None else None,
                download_attachments=download_attachments,
            )
            records.append(
                {
                    "document_no": document_no,
                    "section_seq": section_seq,
                    "section_name": section_name,
                    "subsection_seq": subsection_seq,
                    "subsection_name": subsection_name,
                    "row_seq": row_seq,
                    "change_item": change_item,
                    "attachment_seq": attachment_seq,
                    "attachment_name": attachment_name,
                    "attachment_old_value": "",
                    "attachment_new_value": joined_text,
                    "relative_path": download_result.get("relative_path") or "",
                    "download_status": download_result.get("download_status") or "",
                    "download_time": download_result.get("download_time") or "",
                    "file_size": download_result.get("file_size"),
                    "file_hash": download_result.get("file_hash") or "",
                    "datarefid": "",
                    "raw_payload": {"headers": headers, "row": row},
                }
            )
        return records

    def _build_attachment_records(
        self,
        *,
        document_no: str,
        section_seq: int,
        section_name: str,
        subsection_seq: int,
        subsection_name: str,
        row_seq: int,
        row: dict[str, Any],
        downloads_dir: Path | None,
        download_attachments: bool,
    ) -> list[dict[str, Any]]:
        old_value = str(row.get("oldvalue") or "").strip()
        new_value = str(row.get("newvalue") or "").strip()
        change_item = str(row.get("fieldname") or "").strip()
        datarefid = str(row.get("datarefid") or "").strip()
        file_names = self._extract_attachment_names("\n".join(item for item in [old_value, new_value] if item))
        if not file_names:
            return []

        attachment_dir = None
        if downloads_dir is not None:
            attachment_dir = downloads_dir / "personnel_profile_change_audit" / document_no
            attachment_dir.mkdir(parents=True, exist_ok=True)

        records: list[dict[str, Any]] = []
        for attachment_seq, file_name in enumerate(file_names, start=1):
            download_result = self._resolve_attachment_download(
                file_name=file_name,
                target_dir=attachment_dir,
                download_attachments=download_attachments,
            )
            records.append(
                {
                    "document_no": document_no,
                    "section_seq": section_seq,
                    "section_name": section_name,
                    "subsection_seq": subsection_seq,
                    "subsection_name": subsection_name,
                    "row_seq": row_seq,
                    "change_item": change_item,
                    "attachment_seq": attachment_seq,
                    "attachment_name": file_name,
                    "attachment_old_value": old_value,
                    "attachment_new_value": new_value,
                    "relative_path": download_result.get("relative_path") or "",
                    "download_status": download_result.get("download_status") or "",
                    "download_time": download_result.get("download_time") or "",
                    "file_size": download_result.get("file_size"),
                    "file_hash": download_result.get("file_hash") or "",
                    "datarefid": datarefid,
                    "raw_payload": row,
                }
            )
        return records

    def _resolve_attachment_download(
        self,
        *,
        file_name: str,
        target_dir: Path | None,
        download_attachments: bool,
    ) -> dict[str, Any]:
        if target_dir is None:
            return {
                "download_status": "downloads_dir_missing",
                "download_time": "",
                "relative_path": "",
                "file_size": None,
                "file_hash": "",
            }
        if not download_attachments:
            return {
                "download_status": "not_requested",
                "download_time": "",
                "relative_path": "",
                "file_size": None,
                "file_hash": "",
            }

        download = self._try_download_attachment_from_page(file_name=file_name, target_dir=target_dir)
        if download is None:
            return {
                "download_status": "unresolved",
                "download_time": "",
                "relative_path": "",
                "file_size": None,
                "file_hash": "",
            }
        return download

    def _try_download_attachment_from_page(self, *, file_name: str, target_dir: Path) -> dict[str, Any] | None:
        candidates: list[Locator] = []
        exact_text = self.page.get_by_text(file_name, exact=True).first
        if exact_text.count() > 0:
            candidates.append(exact_text)
        fuzzy_text = self.page.get_by_text(file_name, exact=False).first
        if fuzzy_text.count() > 0:
            candidates.append(fuzzy_text)
        for selector in (
            f'a[title="{file_name}"]',
            f'[title="{file_name}"]',
            f'[download="{file_name}"]',
        ):
            locator = self.page.locator(selector).first
            if locator.count() > 0:
                candidates.append(locator)

        for locator in candidates:
            try:
                with self.page.expect_download(timeout=2000) as download_info:
                    locator.click(force=True)
                download = download_info.value
                return self._save_download(download, target_dir)
            except Exception:  # noqa: BLE001
                continue
        return None

    def _save_download(self, download: Download, target_dir: Path) -> dict[str, Any]:
        target_dir.mkdir(parents=True, exist_ok=True)
        suggested = download.suggested_filename or "attachment.bin"
        safe_name = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", suggested)
        target_path = target_dir / safe_name
        download.save_as(str(target_path))
        file_bytes = target_path.read_bytes()
        relative_path = ""
        try:
            relative_path = str(target_path.relative_to(Path(__file__).resolve().parents[2])).replace("\\", "/")
        except Exception:  # noqa: BLE001
            relative_path = str(target_path)
        return {
            "download_status": "downloaded",
            "download_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "relative_path": relative_path,
            "file_size": target_path.stat().st_size,
            "file_hash": hashlib.sha256(file_bytes).hexdigest(),
        }

    @classmethod
    def _extract_rows_from_payload(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        for item in cls._iter_dicts(payload):
            dataindex = item.get("dataindex")
            rows = item.get("rows")
            if isinstance(dataindex, list) and isinstance(rows, list):
                decoded = cls._decode_indexed_rows(dataindex, rows)
                if decoded:
                    return decoded
        return []

    @classmethod
    def _decode_indexed_rows(cls, dataindex: list[Any], rows: list[Any]) -> list[dict[str, Any]]:
        keys = [cls._decode_dataindex_key(item, index) for index, item in enumerate(dataindex)]
        decoded_rows: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict):
                decoded_rows.append(dict(row))
                continue
            if not isinstance(row, list):
                continue
            decoded_row: dict[str, Any] = {}
            for index, key in enumerate(keys):
                decoded_row[key] = row[index] if index < len(row) else None
            decoded_rows.append(decoded_row)
        return decoded_rows

    @staticmethod
    def _decode_dataindex_key(item: Any, index: int) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("field", "name", "dataIndex", "key", "id"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return f"col_{index + 1}"

    @classmethod
    def _iter_dicts(cls, payload: Any) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                collected.append(node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        return collected

    @classmethod
    def _payload_contains_key(cls, payload: Any, key_name: str) -> bool:
        if isinstance(payload, dict):
            if key_name in payload:
                return True
            return any(cls._payload_contains_key(value, key_name) for value in payload.values())
        if isinstance(payload, list):
            return any(cls._payload_contains_key(item, key_name) for item in payload)
        return False

    @classmethod
    def _normalize_change_row(cls, row: dict[str, Any]) -> list[tuple[str, str]]:
        operate_type = str(row.get("operatetype") or "").strip()
        return [
            ("序号", str(row.get("seq") or "").strip()),
            ("操作类型", cls.CHANGE_TYPE_LABELS.get(operate_type, operate_type)),
            ("变更项", str(row.get("fieldname") or "").strip()),
            ("变更前", str(row.get("oldvalue") or "").strip()),
            ("变更后", str(row.get("newvalue") or "").strip()),
            ("不通过", cls._bool_to_label(row.get("status"))),
            ("理由", str(row.get("reason") or "").strip()),
            ("数据引用ID", str(row.get("datarefid") or "").strip()),
        ]

    @classmethod
    def _normalize_attachment_row(cls, row: dict[str, Any]) -> list[tuple[str, str]]:
        return [
            ("序号", str(row.get("seq") or "").strip()),
            ("变更项", str(row.get("fieldname") or "").strip()),
            ("变更前", str(row.get("oldvalue") or "").strip()),
            ("变更后", str(row.get("newvalue") or "").strip()),
            ("不通过", cls._bool_to_label(row.get("status"))),
            ("理由", str(row.get("reason") or "").strip()),
            ("数据引用ID", str(row.get("datarefid") or "").strip()),
        ]

    @staticmethod
    def _bool_to_label(value: Any) -> str:
        if value is True:
            return "是"
        if value is False:
            return "否"
        return str(value or "").strip()

    @classmethod
    def _extract_attachment_names(cls, value: str) -> list[str]:
        names = []
        seen: set[str] = set()
        for matched in cls.ATTACHMENT_FILE_RE.findall(value or ""):
            normalized = str(matched or "").strip().strip(",，、")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            names.append(normalized)
        return names

    @staticmethod
    def _normalize_row_cells(headers: list[str], row: list[str]) -> list[str]:
        normalized = [str(cell or "").strip() for cell in row]
        if len(normalized) < len(headers):
            normalized.extend([""] * (len(headers) - len(normalized)))
        return normalized[: len(headers)]

    @classmethod
    def _list_row_sort_key(cls, row: dict[str, str]) -> tuple[int, str]:
        index_value = str(row.get("#") or row.get("序号") or "").strip()
        if index_value.isdigit():
            return (int(index_value), str(row.get("单据编号") or ""))
        return (10**9, str(row.get("单据编号") or ""))

    def _get_body_text(self) -> str:
        return self._normalize_text(self.page.locator("body").inner_text(timeout=self.timeout_ms))

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return "\n".join(
            line.strip()
            for line in str(value or "").replace("\r", "\n").split("\n")
            if line.strip()
        )

    @staticmethod
    def _normalize_cell_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip()

    @staticmethod
    def _extract_first_number(value: str) -> str:
        matched = re.search(r"(\d+)", value or "")
        return matched.group(1) if matched else ""

    def _has_text(self, text: str) -> bool:
        try:
            return self.page.get_by_text(text, exact=False).first.is_visible(timeout=1000)
        except Exception:  # noqa: BLE001
            return False

    def _try_click_text(self, text: str, exact: bool, force: bool, scope: str | None) -> bool:
        locator_scope = self.page.locator(scope) if scope else None
        try:
            locator = locator_scope.get_by_text(text, exact=exact).first if locator_scope else self.page.get_by_text(text, exact=exact).first
            if locator.is_visible(timeout=1000):
                locator.click(timeout=self.timeout_ms, force=force)
                return True
        except Exception:  # noqa: BLE001
            pass
        try:
            selector = f"text={text}"
            locator = self.page.locator(selector).first if scope is None else self.page.locator(f"{scope} >> {selector}").first
            if locator.count() and locator.is_visible():
                locator.click(timeout=self.timeout_ms, force=force)
                return True
        except Exception:  # noqa: BLE001
            pass
        return False
