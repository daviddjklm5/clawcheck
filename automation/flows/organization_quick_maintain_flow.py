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
        query_summary = self.ensure_include_children_enabled(timeout_sec=query_timeout_sec)

        result: dict[str, Any] = {
            "root_org_name": root_org_name,
            "include_all_children": True,
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
        self._ensure_recent_menu_opened()
        if not self._try_click_text("组织快速维护", exact=True, force=False, scope=None):
            if not self._try_click_text("组织快速维护", exact=False, force=False, scope=None):
                raise RuntimeError("Failed to click text: 组织快速维护")

        deadline = time.monotonic() + max(self.timeout_ms / 1000, 20)
        while time.monotonic() < deadline:
            body = self.page.locator("body").inner_text()
            if "组织快速维护列表" in body and "行政组织维护" in body and self._is_visible("#baritemap1"):
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
        )

    def wait_org_list_ready(
        self,
        timeout_sec: int,
        before_count: int | None,
        before_page_count: int | None,
        require_count_change: bool,
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

            if (
                self._is_include_children_enabled()
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
                    "include_all_children": True,
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
        for text in ["转入后台", "转后台执行", "转后台运行"]:
            if self._try_click_text(text, exact=True, force=True, scope="#dialogShow"):
                return True
        return False

    def _is_include_children_enabled(self) -> bool:
        return bool(self.page.locator('#chkincludechild input[type="checkbox"]').first.evaluate("(el) => el.checked"))

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
