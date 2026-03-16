from __future__ import annotations

import logging
import time
from typing import Any

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from automation.flows.permission_collect_flow import PermissionCollectFlow, TODO_HEADERS


class DocumentApprovalFlow:
    _OPTION_SELECTORS = (
        ".kd-dropdown-menu-item",
        ".kd-cq-select-item",
        ".kd-cq-dropdown-item",
        ".kd-cq-menu-item",
        ".kd-cq-list-item",
    )
    _SUCCESS_KEYWORDS = ("成功", "提交成功", "处理成功", "审批成功", "操作成功")
    _ERROR_KEYWORDS = ("失败", "错误", "异常", "不能为空", "请填写", "请先填写")

    def __init__(
        self,
        page: Page,
        logger: logging.Logger,
        timeout_ms: int,
        home_url: str,
    ) -> None:
        self.page = page
        self.logger = logger
        self.timeout_ms = timeout_ms
        self.home_url = home_url
        self.collector = PermissionCollectFlow(
            page=page,
            logger=logger,
            timeout_ms=timeout_ms,
            home_url=home_url,
        )

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip()

    def _wait_for_first_visible(
        self,
        selectors: tuple[str, ...],
        root: Locator | None = None,
        timeout_ms: int | None = None,
    ) -> Locator:
        container = root or self.page.locator(":root")
        deadline = time.monotonic() + ((timeout_ms or self.timeout_ms) / 1000)
        last_error = ""

        while time.monotonic() < deadline:
            for selector in selectors:
                locator = container.locator(selector).first
                try:
                    if locator.count() > 0 and locator.is_visible():
                        return locator
                except Exception as exc:  # noqa: BLE001
                    last_error = f"{selector}: {exc}"
                    continue
            self.page.wait_for_timeout(200)

        raise PlaywrightTimeoutError(
            f"No visible locator matched selectors={selectors}. last_error={last_error}"
        )

    def _open_todo_list_ready(self) -> None:
        todo_trigger = self.page.locator("div[id^='processflexpanelap_']").filter(has_text="待办任务").first
        todo_trigger.wait_for(state="visible", timeout=self.timeout_ms)
        todo_trigger.click(force=True)
        self.page.locator("#gridview").first.wait_for(state="visible", timeout=self.timeout_ms)
        self.collector._wait_for_grid_headers(TODO_HEADERS)

    def _list_visible_tabs(self) -> list[str]:
        tabs = self.page.evaluate(
            r"""() => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null;
                };
                return [...document.querySelectorAll('#tabap .kd-cq-tabs-tab, [id^="tabap"] .kd-cq-tabs-tab')]
                    .filter(visible)
                    .map((el) => normalize(el.innerText || ''))
                    .filter(Boolean);
            }"""
        )
        return [self._normalize_text(item) for item in tabs]

    def _open_task_tab(self) -> None:
        task_tab = self.page.locator("#tabap .kd-cq-tabs-tab").filter(has_text="任务处理").first
        if task_tab.count() == 0:
            task_tab = self.page.locator("text=任务处理").first
        task_tab.wait_for(state="visible", timeout=self.timeout_ms)
        task_tab.click(force=True)
        self.page.wait_for_timeout(600)

    def _open_approval_record_tab(self) -> None:
        approval_tab = self.page.locator("#tabap .kd-cq-tabs-tab").filter(has_text="审批记录").first
        if approval_tab.count() == 0:
            approval_tab = self.page.locator("text=审批记录").first
        approval_tab.wait_for(state="visible", timeout=self.timeout_ms)
        approval_tab.click(force=True)
        self.page.wait_for_timeout(600)

    def _task_field_item(self, label: str) -> Locator:
        field = self.page.locator('[data-field-item="true"]').filter(has_text=label).first
        field.wait_for(state="visible", timeout=self.timeout_ms)
        return field

    def _read_field_display_value(self, label: str) -> str:
        field = self._task_field_item(label)
        value = field.evaluate(
            r"""(item) => {
                const normalize = (input) => (input || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null;
                };

                const readCandidate = (candidate) => {
                    if (!candidate || !visible(candidate)) return '';
                    if ('value' in candidate && candidate.value) return normalize(candidate.value);
                    return normalize(candidate.innerText || candidate.textContent || '');
                };

                const candidates = [
                    ...item.querySelectorAll('input, textarea, .kd-cq-combo-selected, .kd-cq-select-selection-item, .kd-cq-select-selected-value, .kd-cq-field-value-wrap'),
                ];
                for (const candidate of candidates) {
                    const value = readCandidate(candidate);
                    if (value) return value;
                }
                return normalize(item.innerText || '');
            }"""
        )
        normalized = self._normalize_text(value)
        if normalized.startswith(label):
            normalized = self._normalize_text(normalized[len(label) :])
        normalized = normalized.lstrip("*").strip()
        return normalized

    def _decision_trigger(self) -> Locator:
        field = self._task_field_item("审批决策")
        return self._wait_for_first_visible(
            (
                ".kd-cq-combo-selected",
                ".kd-cq-select-selection-item",
                ".kd-cq-select",
                ".kd-cq-combo",
                "input",
            ),
            root=field,
        )

    def _visible_option_texts(self) -> list[str]:
        option_texts = self.page.evaluate(
            r"""(selectors) => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null;
                };
                const result = [];
                for (const selector of selectors) {
                    for (const element of document.querySelectorAll(selector)) {
                        if (!visible(element)) continue;
                        const text = normalize(element.innerText || element.textContent || '');
                        if (text) result.push(text);
                    }
                }
                return result;
            }""",
            list(self._OPTION_SELECTORS),
        )
        deduplicated: list[str] = []
        for text in option_texts:
            normalized = self._normalize_text(text)
            if normalized and normalized not in deduplicated:
                deduplicated.append(normalized)
        return deduplicated

    def list_decision_options(self) -> list[str]:
        self._decision_trigger().click(force=True)
        self.page.wait_for_timeout(300)
        options = self._visible_option_texts()
        self.page.keyboard.press("Escape")
        return options

    def read_decision_value(self) -> str:
        return self._read_field_display_value("审批决策")

    def set_decision_value(self, target_value: str) -> str:
        current_value = self.read_decision_value()
        if current_value == target_value:
            return current_value

        self._decision_trigger().click(force=True)
        option_locator = self.page.locator(",".join(self._OPTION_SELECTORS)).filter(has_text=target_value).first
        option_locator.wait_for(state="visible", timeout=self.timeout_ms)
        option_locator.click(force=True)
        self.page.wait_for_timeout(500)

        current_value = self.read_decision_value()
        if current_value != target_value:
            raise RuntimeError(
                f"审批决策切换失败，期望={target_value!r}，实际={current_value!r}"
            )
        return current_value

    def approval_opinion_locator(self) -> Locator:
        try:
            locator = self.page.locator('textarea[placeholder="请输入审批意见。"]').first
            locator.wait_for(state="visible", timeout=1500)
            return locator
        except PlaywrightTimeoutError:
            field = self._task_field_item("审批意见")
            return self._wait_for_first_visible(("textarea",), root=field)

    def read_approval_opinion(self) -> str:
        return self._normalize_text(self.approval_opinion_locator().input_value())

    def write_approval_opinion(self, opinion: str) -> str:
        locator = self.approval_opinion_locator()
        locator.click(force=True)
        self.page.keyboard.press("Control+A")
        if opinion:
            self.page.keyboard.insert_text(opinion)
        else:
            self.page.keyboard.press("Backspace")
        self.page.wait_for_timeout(300)

        current_value = self._normalize_text(locator.input_value())
        if current_value != self._normalize_text(opinion):
            locator.evaluate(
                """(el, value) => {
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                opinion,
            )
            self.page.wait_for_timeout(300)
            current_value = self._normalize_text(locator.input_value())

        locator.evaluate("(el) => el.blur()")
        self.page.wait_for_timeout(200)

        if current_value != self._normalize_text(opinion):
            raise RuntimeError(
                f"审批意见写入失败，期望={opinion!r}，实际={current_value!r}"
            )
        return current_value

    def submit_button_locator(self) -> Locator:
        return self._wait_for_first_visible(
            (
                "a.kd-cq-btn:has-text('提交')",
                "button:has-text('提交')",
                "a:has-text('提交')",
            )
        )

    def visible_feedback_message(self, keywords: tuple[str, ...]) -> str:
        message = self.page.evaluate(
            r"""(keywords) => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null;
                };
                const selectors = [
                    '[role="alert"]',
                    '.kd-message',
                    '.kd-message-notice',
                    '.kd-notification',
                    '.kd-cq-message',
                    '.ant-message',
                    '.ant-notification',
                ];
                for (const selector of selectors) {
                    for (const element of document.querySelectorAll(selector)) {
                        if (!visible(element)) continue;
                        const text = normalize(element.innerText || element.textContent || '');
                        if (!text) continue;
                        if (keywords.some((keyword) => text.includes(keyword))) return text;
                    }
                }
                return '';
            }""",
            list(keywords),
        )
        return self._normalize_text(message)

    def capture_approval_records(self) -> list[dict[str, Any]]:
        self._open_approval_record_tab()
        records = self.collector.extract_approval_records()
        self._open_task_tab()
        return records

    def wait_for_submission_confirmation(
        self,
        expected_opinion: str,
        approval_count_before: int,
        wait_timeout_ms: int | None = None,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + ((wait_timeout_ms or self.timeout_ms) / 1000)
        last_error_message = ""

        while time.monotonic() < deadline:
            error_message = self.visible_feedback_message(self._ERROR_KEYWORDS)
            if error_message:
                raise RuntimeError(f"EHR 提交失败：{error_message}")

            success_message = self.visible_feedback_message(self._SUCCESS_KEYWORDS)
            if success_message:
                return {
                    "confirmationType": "toast",
                    "confirmationMessage": success_message,
                }

            try:
                records = self.capture_approval_records()
            except Exception as exc:  # noqa: BLE001
                last_error_message = str(exc)
                self.page.wait_for_timeout(800)
                continue

            if len(records) > approval_count_before:
                latest_record = records[-1]
                latest_action = self._normalize_text(latest_record.get("approval_action"))
                latest_opinion = self._normalize_text(latest_record.get("approval_opinion"))
                if latest_action == "同意" or latest_opinion == self._normalize_text(expected_opinion):
                    return {
                        "confirmationType": "approval_record",
                        "confirmationMessage": "审批记录已追加最新同意动作。",
                        "latestApprovalAction": latest_action,
                        "latestApprovalOpinion": latest_opinion,
                    }

            self.page.wait_for_timeout(800)

        raise RuntimeError(
            "点击提交后未在预期时间内观察到成功反馈。"
            + (f" last_error={last_error_message}" if last_error_message else "")
        )

    def prepare_document_for_approval(self, document_no: str) -> dict[str, Any]:
        self._open_todo_list_ready()
        self.collector.open_document(document_no)
        basic_info = self.collector.extract_basic_info()
        current_document_no = self._normalize_text(basic_info.get("单据编号"))
        if current_document_no != document_no:
            raise RuntimeError(
                f"打开单据校验失败，期望={document_no!r}，实际={current_document_no!r}"
            )

        detail_tabs = self._list_visible_tabs()
        self._open_task_tab()
        return {
            "basicInfo": basic_info,
            "detailTabs": detail_tabs,
        }

    def execute_approve(self, document_no: str, approval_opinion: str, dry_run: bool = False) -> dict[str, Any]:
        preparation = self.prepare_document_for_approval(document_no)
        baseline_records = self.capture_approval_records()

        decision_before = self.read_decision_value()
        decision_options = self.list_decision_options()
        if "同意" not in decision_options and decision_before != "同意":
            raise RuntimeError(f"当前审批决策不支持“同意”，可用选项={decision_options}")

        opinion_before = self.read_approval_opinion()
        decision_after = self.set_decision_value("同意")
        opinion_after = self.write_approval_opinion(approval_opinion)
        submit_button = self.submit_button_locator()
        submit_label = self._normalize_text(submit_button.inner_text())

        response = {
            "basicInfo": preparation["basicInfo"],
            "detailTabs": preparation["detailTabs"],
            "decisionBefore": decision_before,
            "decisionAfter": decision_after,
            "decisionOptions": decision_options,
            "approvalOpinionBefore": opinion_before,
            "approvalOpinionAfter": opinion_after,
            "submitLabel": submit_label,
            "approvalRecordCountBefore": len(baseline_records),
            "dryRun": dry_run,
        }

        if dry_run:
            if opinion_before != approval_opinion:
                self.write_approval_opinion(opinion_before)
            if decision_before and decision_before != "同意":
                self.set_decision_value(decision_before)
            response["approvalOpinionRestored"] = self.read_approval_opinion()
            response["decisionRestored"] = self.read_decision_value()
            response["confirmationType"] = "dry_run"
            response["confirmationMessage"] = "已完成页面连通与写入验证，未点击提交。"
            return response

        submit_button.click(force=True)
        self.page.wait_for_timeout(600)
        confirmation = self.wait_for_submission_confirmation(
            expected_opinion=approval_opinion,
            approval_count_before=len(baseline_records),
            wait_timeout_ms=max(self.timeout_ms, 20000),
        )
        response.update(confirmation)
        return response
