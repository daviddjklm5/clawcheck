from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Download, Page, TimeoutError as PlaywrightTimeoutError


class ActiveRosterFlow:
    def __init__(self, page: Page, logger, timeout_ms: int, home_url: str) -> None:
        self.page = page
        self.logger = logger
        self.timeout_ms = timeout_ms
        self.home_url = home_url
        self._known_completed_task_ids: set[str] = set()
        self._current_export_task_id: str | None = None
        self._background_panel_initialized = False

    def run(
        self,
        downloads_dir: Path,
        report_scheme: str,
        employment_type: str,
        query_timeout_sec: int,
        download_timeout_sec: int,
        skip_export: bool,
    ) -> dict[str, Any]:
        self.open_roster_page()
        self.select_report_scheme(report_scheme)
        self.select_employment_type(employment_type)
        query_summary = self.query_report(timeout_sec=query_timeout_sec)

        result: dict[str, Any] = {
            "report_scheme": report_scheme,
            "employment_type": employment_type,
            "query_summary": query_summary,
        }
        if skip_export:
            return result

        downloaded_file = self.export_report(downloads_dir=downloads_dir, timeout_sec=download_timeout_sec)
        result["downloaded_file"] = str(downloaded_file)
        return result

    def open_roster_page(self) -> None:
        self.page.goto(self.home_url, wait_until="domcontentloaded")
        self._wait_for_text("员工自助服务中心", timeout_ms=self.timeout_ms)
        self._ensure_recent_menu_opened()
        clicked = False
        for exact in (True, False):
            if self._try_click_text("在职人员花名册", exact=exact, force=False, scope=None):
                clicked = True
                break
        if not clicked:
            try:
                self.page.locator("text=在职人员花名册").first.click(timeout=self.timeout_ms)
                clicked = True
            except Exception:  # noqa: BLE001
                pass
        if not clicked:
            raise RuntimeError("Failed to click text: 在职人员花名册")
        self.page.locator("#report").first.wait_for(state="visible", timeout=self.timeout_ms)
        self.page.locator("#postype").first.wait_for(state="visible", timeout=self.timeout_ms)
        self.logger.info("Opened active roster page")

    def select_report_scheme(self, value: str) -> None:
        self._select_f7_value(field_id="report", row_text=value, expected_value=value)
        self.logger.info("Selected report scheme: %s", value)

    def select_employment_type(self, value: str) -> None:
        self._select_f7_value(field_id="postype", row_text=value, expected_value=value)
        self.logger.info("Selected employment type: %s", value)

    def query_report(self, timeout_sec: int) -> dict[str, Any]:
        self.page.locator('#reportfilterap .kd-cq-reportpanel-bottom-item:has-text("查询")').first.click(force=True)
        self.logger.info("Clicked query button")

        deadline = time.monotonic() + timeout_sec
        last_body = ""
        while time.monotonic() < deadline:
            self.page.wait_for_timeout(1000)
            if not self._is_visible("#toolbarap") or not self._is_visible("#exportexcel"):
                continue
            last_body = self.page.locator("body").inner_text()
            if "正在加载..." in last_body or "（加载中）" in last_body:
                continue
            if "在职人员花名册" not in last_body:
                continue
            row_count = self._extract_row_count(last_body)
            query_date = self._extract_query_date(last_body)
            self.logger.info("Roster query completed. row_count=%s query_date=%s", row_count, query_date)
            return {
                "row_count": row_count,
                "query_date": query_date,
            }

        raise PlaywrightTimeoutError(f"Roster query did not finish within {timeout_sec} seconds. body={last_body[:500]}")

    def export_report(self, downloads_dir: Path, timeout_sec: int) -> Path:
        downloads_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("Waiting for roster download. timeout=%ss dir=%s", timeout_sec, downloads_dir)
        self._known_completed_task_ids.clear()
        self._current_export_task_id = None
        self._background_panel_initialized = False

        downloads: list[Download] = []

        def _on_download(download: Download) -> None:
            downloads.append(download)
            self.logger.info("Download event received: %s", download.suggested_filename)

        self.page.on("download", _on_download)

        self.page.locator("#exportexcel").first.click(force=True)
        self._wait_for_text("引出中", timeout_ms=self.timeout_ms)
        if not self._click_background_export_button():
            raise RuntimeError("Failed to find background export button in export dialog")

        return self._wait_for_download_after_background(downloads_dir=downloads_dir, downloads=downloads, timeout_sec=timeout_sec)

    def _click_background_export_button(self) -> bool:
        deadline = time.monotonic() + min(max(self.timeout_ms / 1000, 2), 8)
        while time.monotonic() < deadline:
            selector = '#dialogShow [data-btn-key="btnok"]'
            try:
                locator = self.page.locator(selector).last
                if locator.count() and locator.is_visible():
                    locator.click(timeout=self.timeout_ms, force=True)
                    self.logger.info("Clicked background export button by selector: %s", selector)
                    return True
            except Exception:  # noqa: BLE001
                pass

            for text in ["转后台执行", "转后台运行"]:
                for exact in (True, False):
                    if self._try_click_text(text, exact=exact, force=True, scope="#dialogShow"):
                        self.logger.info(
                            "Clicked background export button: %s%s",
                            text,
                            "" if exact else " (partial match)",
                        )
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
            clicked_text = str(clicked or "").strip()
            if clicked_text:
                self.logger.info("Clicked background export button by DOM evaluation: %s", clicked_text)
                return True
            self.page.wait_for_timeout(300)

        try:
            candidate_texts = self.page.evaluate(
                """() => Array.from(document.querySelectorAll('*'))
                    .map((el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
                    .filter((text) => text.includes('后台执行') || text.includes('后台运行') || text.includes('转入后台'))
                    .slice(0, 10)"""
            )
            if candidate_texts:
                self.logger.warning("Background export button candidates: %s", candidate_texts)
        except Exception:  # noqa: BLE001
            pass
        return False

    def _wait_for_download_after_background(self, downloads_dir: Path, downloads: list[Download], timeout_sec: int) -> Path:
        deadline = time.monotonic() + timeout_sec
        last_progress = ""
        while time.monotonic() < deadline:
            if downloads:
                return self._save_download(downloads_dir, downloads[0])

            body = self.page.locator("body").inner_text()
            progress = self._extract_progress_text(body)
            if progress and progress != last_progress:
                last_progress = progress
                self.logger.info("Background export progress: %s", progress)

            if self._ensure_background_task_panel_opened():
                self._update_background_task_tracking()
                if self._open_completed_roster_task_detail():
                    self.page.wait_for_timeout(800)

            if self._click_task_download_button():
                self.page.wait_for_timeout(2000)
                if downloads:
                    return self._save_download(downloads_dir, downloads[0])

            self.page.wait_for_timeout(2000)

        raise PlaywrightTimeoutError(f"Roster download did not complete within {timeout_sec} seconds")

    def _ensure_background_task_panel_opened(self) -> bool:
        if self._is_background_task_panel_open():
            return True
        clicked_text = self.page.evaluate(
            """() => {
                const items = Array.from(document.querySelectorAll('*'))
                    .map((el) => ({
                        el,
                        rect: el.getBoundingClientRect(),
                        text: (el.innerText || el.textContent || '').trim(),
                    }))
                    .filter((item) => item.rect.width > 0 && item.rect.height > 0)
                    .filter((item) => item.rect.x > window.innerWidth - 80)
                    .filter((item) => /^\\d+\\/\\d+$/.test(item.text))
                    .filter((item) => item.rect.width <= 60 && item.rect.height <= 60);
                if (!items.length) {
                    return '';
                }
                const target = items[items.length - 1];
                target.el.click();
                return target.text;
            }"""
        )
        if clicked_text:
            self.logger.info("Clicked background task bubble: %s", clicked_text)
            self.page.wait_for_timeout(500)
        return self._is_background_task_panel_open()

    def _is_background_task_panel_open(self) -> bool:
        return bool(
            self.page.evaluate(
                """() => Array.from(document.querySelectorAll('*')).some((el) => {
                    const text = (el.innerText || el.textContent || '').trim();
                    const rect = el.getBoundingClientRect();
                    return text.includes('后台运行') && rect.width >= 250 && rect.height >= 150;
                })"""
            )
        )

    def _collect_background_task_state(self) -> dict[str, Any] | None:
        state = self.page.evaluate(
            """() => {
                const panel = Array.from(document.querySelectorAll('*')).find((el) => {
                    const text = (el.innerText || el.textContent || '').trim();
                    const rect = el.getBoundingClientRect();
                    return text.includes('后台运行') && rect.width >= 250 && rect.height >= 150;
                });
                if (!panel) {
                    return null;
                }
                const items = Array.from(panel.querySelectorAll('li'))
                    .map((el) => ({
                        id: el.id || '',
                        text: (el.innerText || el.textContent || '').trim(),
                    }))
                    .filter((item) => item.text.includes('报表导出 - 在职人员花名册'));
                return {
                    items,
                    completed_ids: items.filter((item) => item.text.includes('已完成')).map((item) => item.id).filter(Boolean),
                    active_ids: items.filter((item) => !item.text.includes('已完成')).map((item) => item.id).filter(Boolean),
                };
            }"""
        )
        return state if isinstance(state, dict) else None

    def _update_background_task_tracking(self) -> None:
        state = self._collect_background_task_state()
        if not state:
            return

        completed_ids = {task_id for task_id in state.get("completed_ids", []) if task_id}
        active_ids = [task_id for task_id in state.get("active_ids", []) if task_id]

        if not self._background_panel_initialized:
            self._known_completed_task_ids = set(completed_ids)
            self._background_panel_initialized = True
            if completed_ids:
                self.logger.info("Remembered historical completed task ids: %s", sorted(completed_ids))

        if active_ids:
            latest_active = active_ids[-1]
            if latest_active != self._current_export_task_id:
                self._current_export_task_id = latest_active
                self.logger.info("Tracked current export task id: %s", latest_active)

    def _open_completed_roster_task_detail(self) -> bool:
        if self._is_task_download_dialog_open():
            return True

        state = self._collect_background_task_state()
        if not state:
            return False

        target_task_id = None
        items = state.get("items", [])
        if self._current_export_task_id:
            for item in items:
                if item.get("id") == self._current_export_task_id and "已完成" in item.get("text", ""):
                    target_task_id = self._current_export_task_id
                    break

        if target_task_id is None:
            for item in items:
                item_id = item.get("id", "")
                if item_id and "已完成" in item.get("text", "") and item_id not in self._known_completed_task_ids:
                    target_task_id = item_id
                    break

        if target_task_id is None:
            return False

        clicked = self.page.evaluate(
            """(taskId) => {
                const item = document.getElementById(taskId);
                if (!item) {
                    return false;
                }
                const icon = item.querySelector('i.kdfont.kdfont-f') || item.querySelector('i[class*="kdfont-f"]');
                (icon || item).click();
                return true;
            }""",
            target_task_id,
        )
        if clicked:
            self.logger.info("Opened completed roster task detail: %s", target_task_id)
            self._known_completed_task_ids.add(target_task_id)
        return bool(clicked)

    def _is_task_download_dialog_open(self) -> bool:
        return bool(
            self.page.evaluate(
                """() => Array.from(document.querySelectorAll('*')).some((el) => {
                    const text = (el.innerText || el.textContent || '').trim();
                    const rect = el.getBoundingClientRect();
                    return text.includes('报表导出文件下载') && rect.width >= 300 && rect.height >= 200;
                })"""
            )
        )

    def _click_task_download_button(self) -> bool:
        selector = '#dialogShow [data-page-id$="_btnexport"]'
        try:
            locator = self.page.locator(selector).first
            if locator.count() and locator.is_visible():
                locator.click(timeout=self.timeout_ms, force=True)
                self.logger.info("Clicked task download button by selector: %s", selector)
                return True
        except Exception:  # noqa: BLE001
            pass

        clicked = self.page.evaluate(
            """() => {
                const dialog = Array.from(document.querySelectorAll('*')).find((el) => {
                    const text = (el.innerText || el.textContent || '').trim();
                    const rect = el.getBoundingClientRect();
                    return text.includes('报表导出文件下载') && rect.width >= 300 && rect.height >= 200;
                });
                if (!dialog) {
                    return false;
                }
                const candidates = Array.from(dialog.querySelectorAll('*'))
                    .map((el) => ({
                        el,
                        rect: el.getBoundingClientRect(),
                        text: (el.innerText || el.textContent || '').trim(),
                        color: getComputedStyle(el).color,
                        cursor: getComputedStyle(el).cursor,
                    }))
                    .filter((item) => item.rect.width > 0 && item.rect.height > 0)
                    .filter((item) => item.text.includes('下载文件'))
                    .filter((item) => item.cursor === 'pointer' || item.color.includes('85, 130, 243'));
                if (!candidates.length) {
                    return false;
                }
                candidates[0].el.click();
                return true;
            }"""
        )
        if clicked:
            self.logger.info("Clicked task download button by DOM evaluation")
        return bool(clicked)

    def _save_download(self, downloads_dir: Path, download: Download) -> Path:
        target_path = downloads_dir / self._build_download_name(download)
        download.save_as(str(target_path))
        self.logger.info("Roster download saved: %s", target_path)
        return target_path

    def _build_download_name(self, download: Download) -> str:
        suggested = download.suggested_filename or "active_roster.xlsx"
        safe_name = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", suggested)
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}"

    def _select_f7_value(self, field_id: str, row_text: str, expected_value: str) -> None:
        self.page.locator(f"#{field_id} .sesB9_9m").first.click(timeout=self.timeout_ms)
        self.page.locator("#dialogShow").first.wait_for(state="visible", timeout=self.timeout_ms)
        self.page.locator(f'#dialogShow tbody tr:has-text("{row_text}")').first.click(timeout=self.timeout_ms)
        self.page.locator('#dialogShow a:has-text("确定")').first.click(timeout=self.timeout_ms, force=True)
        self.page.locator("#dialogShow").first.wait_for(state="hidden", timeout=self.timeout_ms)

        input_value = self.page.locator(f"#{field_id} input").first.input_value().strip()
        if expected_value not in input_value:
            raise RuntimeError(f"Field {field_id} value mismatch. expected contains={expected_value}, actual={input_value}")

    def _ensure_recent_menu_opened(self) -> None:
        if self._has_text("最近使用"):
            return
        self.page.mouse.click(24, 24)
        self._wait_for_text("最近使用", timeout_ms=self.timeout_ms)
        self.logger.info("Opened left-top recent menu")

    def _extract_row_count(self, body_text: str) -> int | None:
        matched = re.search(r"在职人员花名册\s*[（(]共\s*([\d,]+)\s*条[）)]", body_text)
        if not matched:
            return None
        return int(matched.group(1).replace(",", ""))

    def _extract_query_date(self, body_text: str) -> str | None:
        matched = re.search(r"查询日期[:：]\s*(\d{4}-\d{2}-\d{2})", body_text)
        if not matched:
            return None
        return matched.group(1)

    def _extract_progress_text(self, body_text: str) -> str:
        for pattern in [r"已处理\s*\d+(?:\s*/\s*\d+)?\s*张(?:单据)?", r"后台运行.*", r"引出中.*"]:
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
