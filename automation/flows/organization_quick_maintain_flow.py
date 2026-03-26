from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Download, Page, TimeoutError as PlaywrightTimeoutError


class OrganizationQuickMaintainFlow:
    def __init__(self, page: Page, logger, timeout_ms: int, home_url: str) -> None:
        self.page = page
        self.logger = logger
        self.timeout_ms = timeout_ms
        self.home_url = home_url
        self.required_business_statuses = ["已启用", "已停用"]
        self.org_quick_maintain_menu_selector = 'li[data-menu-id-info*="217WYC/L9U7E"]'
        self.business_status_field_selector = (
            '.kd-cq-querypanel-compact-item:has(.kd-cq-querypanel-compact-item-text[title="业务状态"])'
        )

    def run(
        self,
        downloads_dir: Path,
        query_timeout_sec: int,
        download_timeout_sec: int,
        skip_export: bool,
        root_org_name: str = "万物云",
    ) -> dict[str, Any]:
        self.open_org_quick_maintain_page()
        self.select_top_org_node(root_org_name)
        business_status_summary = self.ensure_business_status_selected(
            statuses=self.required_business_statuses,
            timeout_sec=query_timeout_sec,
        )
        query_summary = self.ensure_include_children_enabled(timeout_sec=query_timeout_sec)
        query_summary["business_statuses"] = business_status_summary["selected_statuses"]
        query_summary["business_status_display"] = business_status_summary["selected_display"]

        result: dict[str, Any] = {
            "root_org_name": root_org_name,
            "include_all_children": True,
            "business_statuses": business_status_summary["selected_statuses"],
            "query_summary": query_summary,
        }
        if skip_export:
            return result

        downloaded_file = self.export_report(downloads_dir=downloads_dir, timeout_sec=download_timeout_sec)
        result["downloaded_file"] = str(downloaded_file)
        return result

    def open_org_quick_maintain_page(self) -> None:
        self.page.goto(self.home_url, wait_until="domcontentloaded")
        self._wait_for_text("员工自助服务中心", timeout_ms=self.timeout_ms)
        if self._is_org_quick_maintain_page_ready():
            self.logger.info("Organization quick maintain page already opened")
            return

        self._ensure_recent_menu_opened()
        if self._is_visible(self.org_quick_maintain_menu_selector):
            self.page.locator(self.org_quick_maintain_menu_selector).first.click(timeout=self.timeout_ms)
        elif not self._try_click_text("组织快速维护", exact=True, force=False, scope=None):
            if not self._try_click_text("组织快速维护", exact=False, force=False, scope=None):
                raise RuntimeError("Failed to click text: 组织快速维护")

        deadline = time.monotonic() + max(self.timeout_ms / 1000, 20)
        while time.monotonic() < deadline:
            if self._is_org_quick_maintain_page_ready():
                self.logger.info("Opened organization quick maintain page")
                return
            self.page.wait_for_timeout(1000)

        raise PlaywrightTimeoutError("Organization quick maintain page did not finish opening")

    def select_top_org_node(self, node_name: str) -> None:
        locator = self.page.locator(f'li.kd-cq-tree-treenode:has(a.kd-cq-tree-treenode-text:text-is("{node_name}"))').first
        if locator.count() == 0:
            locator = self.page.locator(f'li.kd-cq-tree-treenode:has-text("{node_name}")').first
        locator.wait_for(state="visible", timeout=self.timeout_ms)
        locator.click(timeout=self.timeout_ms, force=True)
        self.page.wait_for_timeout(800)

        selected = locator.evaluate("(el) => (el.className || '').includes('kd-cq-tree-treenode-selected')")
        if not selected:
            raise RuntimeError(f"Failed to select top org node: {node_name}")
        self.logger.info("Selected top org node: %s", node_name)

    def ensure_include_children_enabled(self, timeout_sec: int) -> dict[str, Any]:
        before_body = self.page.locator("body").inner_text()
        before_count = self._extract_list_row_count(before_body)
        before_page_count = self._extract_page_count(before_body)
        already_enabled = self._is_include_children_enabled()

        if not already_enabled:
            self.page.locator('#chkincludechild ._1HdIQduJ').first.click(timeout=self.timeout_ms, force=True)
            self.logger.info("Enabled include-children switch")
        else:
            self.logger.info("Include-children switch already enabled")

        return self.wait_org_list_ready(
            timeout_sec=timeout_sec,
            before_count=before_count,
            before_page_count=before_page_count,
            require_count_change=not already_enabled,
            require_include_children_enabled=True,
        )

    def ensure_business_status_selected(self, statuses: list[str], timeout_sec: int) -> dict[str, Any]:
        expected_statuses = [status.strip() for status in statuses if status.strip()]
        if not expected_statuses:
            raise ValueError("Business statuses must not be empty")

        before_body = self.page.locator("body").inner_text()
        before_count = self._extract_list_row_count(before_body)
        before_page_count = self._extract_page_count(before_body)

        if not self._set_business_status_values(expected_statuses):
            raise RuntimeError("Failed to set business status dropdown to 已启用 + 已停用")

        selected_display = self._wait_for_business_status_values(
            expected_values=expected_statuses,
            timeout_sec=min(max(timeout_sec, 10), 30),
        )

        self.wait_org_list_ready(
            timeout_sec=timeout_sec,
            before_count=before_count,
            before_page_count=before_page_count,
            require_count_change=False,
            require_include_children_enabled=False,
        )
        self.logger.info("Selected business statuses: %s display=%s", expected_statuses, selected_display)
        return {
            "selected_statuses": expected_statuses,
            "selected_display": selected_display,
        }

    def wait_org_list_ready(
        self,
        timeout_sec: int,
        before_count: int | None,
        before_page_count: int | None,
        require_count_change: bool,
        require_include_children_enabled: bool,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_sec
        last_count: int | None = None
        stable_rounds = 0
        last_page_count: int | None = None

        while time.monotonic() < deadline:
            body = self.page.locator("body").inner_text()
            loading = ("正在加载..." in body) or ("（加载中）" in body)
            current_count = self._extract_list_row_count(body)
            current_page_count = self._extract_page_count(body)

            if current_count == last_count and current_page_count == last_page_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                last_count = current_count
                last_page_count = current_page_count

            count_ready = current_count is not None
            if require_count_change:
                count_ready = count_ready and current_count != before_count

            include_children_ready = True
            if require_include_children_enabled:
                include_children_ready = self._is_include_children_enabled()

            if (
                include_children_ready
                and not loading
                and count_ready
                and stable_rounds >= 2
            ):
                self.logger.info(
                    "Organization list ready. before_count=%s after_count=%s before_page_count=%s after_page_count=%s",
                    before_count,
                    current_count,
                    before_page_count,
                    current_page_count,
                )
                return {
                    "row_count": current_count,
                    "page_count": current_page_count,
                    "before_row_count": before_count,
                    "before_page_count": before_page_count,
                    "include_all_children": self._is_include_children_enabled(),
                }

            self.page.wait_for_timeout(1000)

        raise PlaywrightTimeoutError(
            "Organization list did not finish loading "
            f"within {timeout_sec} seconds. before_count={before_count} last_count={last_count}"
        )

    def export_report(self, downloads_dir: Path, timeout_sec: int) -> Path:
        downloads_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("Waiting for organization list download. timeout=%ss dir=%s", timeout_sec, downloads_dir)
        downloads: list[Download] = []

        def _on_download(download: Download) -> None:
            downloads.append(download)
            self.logger.info("Download event received: %s", download.suggested_filename)

        self.page.on("download", _on_download)

        self.page.locator("#baritemap1").first.click(timeout=self.timeout_ms, force=True)
        self._wait_for_text("引出数据（按列表）", timeout_ms=self.timeout_ms)
        if not self._try_click_text("引出数据（按列表）", exact=True, force=True, scope=None):
            raise RuntimeError("Failed to click text: 引出数据（按列表）")

        self._wait_for_text("操作确认", timeout_ms=self.timeout_ms)
        if not self._click_dialog_confirm():
            raise RuntimeError("Failed to click confirm button in export confirm dialog")

        return self._wait_for_download(downloads_dir=downloads_dir, downloads=downloads, timeout_sec=timeout_sec)

    def _wait_for_download(self, downloads_dir: Path, downloads: list[Download], timeout_sec: int) -> Path:
        deadline = time.monotonic() + timeout_sec
        last_progress = ""
        background_clicked = False
        background_confirm_clicked = False

        while time.monotonic() < deadline:
            if downloads:
                return self._save_download(downloads_dir, downloads[0])

            body = self.page.locator("body").inner_text()
            progress = self._extract_progress_text(body)
            if progress and progress != last_progress:
                last_progress = progress
                self.logger.info("Organization export progress: %s", progress)

            elapsed = timeout_sec - max(deadline - time.monotonic(), 0)
            if (not background_clicked) and elapsed >= 10 and self._is_background_button_visible():
                if self._click_background_button():
                    background_clicked = True
                    self.logger.info("Clicked export background button")
                    self.page.wait_for_timeout(1000)
                    continue

            if background_clicked and (not background_confirm_clicked) and "您确认要把引出转为后台执行" in body:
                if self._click_dialog_confirm():
                    background_confirm_clicked = True
                    self.logger.info("Confirmed background export dialog")
                    self.page.wait_for_timeout(1000)
                    continue

            self.page.wait_for_timeout(1000)

        raise PlaywrightTimeoutError(f"Organization list download did not complete within {timeout_sec} seconds")

    def _click_dialog_confirm(self) -> bool:
        selectors = [
            '#dialogShow [data-btn-key="btnok"]',
            '#dialogShow ._3qE72Z2_.theme.btn-follow-theme',
        ]
        for selector in selectors:
            try:
                locator = self.page.locator(selector).last
                if locator.count() and locator.is_visible():
                    locator.click(timeout=self.timeout_ms, force=True)
                    return True
            except Exception:  # noqa: BLE001
                continue

        return self._try_click_text("确定", exact=True, force=True, scope="#dialogShow")

    def _is_background_button_visible(self) -> bool:
        try:
            return self.page.get_by_text("转入后台", exact=True).first.is_visible(timeout=500)
        except Exception:  # noqa: BLE001
            return False

    def _click_background_button(self) -> bool:
        deadline = time.monotonic() + min(max(self.timeout_ms / 1000, 2), 8)
        while time.monotonic() < deadline:
            for text in ["转入后台", "转后台执行", "转后台运行"]:
                for exact in (True, False):
                    if self._try_click_text(text, exact=exact, force=True, scope="#dialogShow"):
                        return True
            clicked = self.page.evaluate(
                """() => {
                    const candidates = Array.from(document.querySelectorAll('*'))
                        .map((el) => {
                            const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                            const rect = el.getBoundingClientRect();
                            return {
                                el,
                                text,
                                tag: el.tagName || '',
                                width: rect.width,
                                height: rect.height,
                                top: rect.top,
                                left: rect.left,
                            };
                        })
                        .filter((item) => item.text.includes('后台执行') || item.text.includes('后台运行') || item.text.includes('转入后台'))
                        .filter((item) => item.width > 0 && item.height > 0);
                    if (!candidates.length) {
                        return '';
                    }
                    candidates.sort((a, b) => {
                        const aButton = /^(BUTTON|A)$/.test(a.tag) ? 1 : 0;
                        const bButton = /^(BUTTON|A)$/.test(b.tag) ? 1 : 0;
                        if (aButton !== bButton) {
                            return bButton - aButton;
                        }
                        const areaDelta = (b.width * b.height) - (a.width * a.height);
                        if (areaDelta !== 0) {
                            return areaDelta;
                        }
                        return b.top - a.top || b.left - a.left;
                    });
                    const winner = candidates[0];
                    const clickable = winner.el.closest('button, a, [role="button"], [data-btn-key]') || winner.el;
                    clickable.click();
                    return winner.text;
                }"""
            )
            if str(clicked or "").strip():
                return True
            self.page.wait_for_timeout(300)
        return False

    def _is_include_children_enabled(self) -> bool:
        return bool(self.page.locator('#chkincludechild input[type="checkbox"]').first.evaluate("(el) => el.checked"))

    def _get_business_status_display_value(self) -> str:
        locator = self.page.locator(f'{self.business_status_field_selector} .kd-cq-select').first
        if locator.count() == 0:
            return ""

        for candidate in [
            locator.get_attribute("title"),
            locator.locator('.kd-cq-combo-selected').first.text_content() if locator.locator('.kd-cq-combo-selected').count() else None,
            locator.text_content(),
        ]:
            value = re.sub(r"\s+", " ", str(candidate or "")).strip(" ；;")
            if value:
                return value
        return ""

    def _wait_for_business_status_values(self, expected_values: list[str], timeout_sec: int) -> str:
        deadline = time.monotonic() + timeout_sec
        last_display = ""
        while time.monotonic() < deadline:
            display = self._get_business_status_display_value()
            if display:
                last_display = display
            if self._field_display_contains_values(display, expected_values):
                return display
            self.page.wait_for_timeout(500)
        raise PlaywrightTimeoutError(
            f"Business status field did not reflect expected values within {timeout_sec} seconds. last_display={last_display}"
        )

    def _field_display_contains_values(self, display_text: str, expected_values: list[str]) -> bool:
        normalized = re.sub(r"\s+", "", display_text or "")
        if not normalized:
            return False
        return all(re.sub(r"\s+", "", value) in normalized for value in expected_values)

    def _set_business_status_values(self, expected_values: list[str]) -> bool:
        for _ in range(3):
            if not self._open_business_status_dropdown():
                self.page.wait_for_timeout(500)
                continue

            all_matched = True
            for expected_value in expected_values:
                if not self._set_business_status_option(expected_value, selected=True):
                    all_matched = False
                    break

            self._close_business_status_dropdown()
            if all_matched:
                return True
        return False

    def _open_business_status_dropdown(self) -> bool:
        arrow = self.page.locator(f'{self.business_status_field_selector} .kdfont-xiala').first
        if arrow.count() == 0:
            return False
        arrow.click(timeout=self.timeout_ms, force=True)
        self.page.wait_for_timeout(300)
        return self.page.locator('li.kd-cq-dropdown-menu-item:has(> span[title="已停用"])').first.count() > 0

    def _set_business_status_option(self, option_text: str, selected: bool) -> bool:
        option = self.page.locator(f'li.kd-cq-dropdown-menu-item:has(> span[title="{option_text}"])').first
        if option.count() == 0:
            return False

        checkbox = option.locator('input[type="checkbox"]').first
        checked = checkbox.is_checked() if checkbox.count() else False
        if checked != selected:
            option.click(timeout=self.timeout_ms, force=True)
            self.page.wait_for_timeout(200)
            checked = checkbox.is_checked() if checkbox.count() else checked
        return checked == selected

    def _close_business_status_dropdown(self) -> None:
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

    def _is_org_quick_maintain_page_ready(self) -> bool:
        try:
            body = self.page.locator("body").inner_text()
        except Exception:  # noqa: BLE001
            return False
        return "组织快速维护列表" in body and "行政组织维护" in body and self._is_visible("#baritemap1")

    def _save_download(self, downloads_dir: Path, download: Download) -> Path:
        target_path = downloads_dir / self._build_download_name(download)
        download.save_as(str(target_path))
        self.logger.info("Organization list download saved: %s", target_path)
        return target_path

    def _build_download_name(self, download: Download) -> str:
        suggested = download.suggested_filename or "organization_list.xlsx"
        safe_name = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", suggested)
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"

    def _ensure_recent_menu_opened(self) -> None:
        if self._has_text("最近使用"):
            return
        self.page.mouse.click(24, 24)
        self._wait_for_text("最近使用", timeout_ms=self.timeout_ms)
        self.logger.info("Opened left-top recent menu")

    def _extract_list_row_count(self, body_text: str) -> int | None:
        matched = re.search(r"列表包含所有下级\s*共\s*([\d,]+)\s*条", body_text)
        if not matched:
            matched = re.search(r"共\s*([\d,]+)\s*条", body_text)
        if not matched:
            return None
        return int(matched.group(1).replace(",", ""))

    def _extract_page_count(self, body_text: str) -> int | None:
        matched = re.search(r"选择全部\s*共\s*([\d,]+)\s*页", body_text)
        if not matched:
            matched = re.search(r"共\s*([\d,]+)\s*页", body_text)
        if not matched:
            return None
        return int(matched.group(1).replace(",", ""))

    def _extract_progress_text(self, body_text: str) -> str:
        for pattern in [r"正在引出组织快速维护.*", r"引出中.*", r"您确认要把引出转为后台执行\?"]:
            matched = re.search(pattern, body_text)
            if matched:
                return matched.group(0)
        return ""

    def _wait_for_text(self, text: str, timeout_ms: int) -> None:
        self.page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout_ms)

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

    def _is_visible(self, selector: str) -> bool:
        try:
            locator = self.page.locator(selector).first
            return locator.count() > 0 and locator.is_visible()
        except Exception:  # noqa: BLE001
            return False
