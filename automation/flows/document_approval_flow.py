from __future__ import annotations

import logging
import time
from collections.abc import Callable
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
        "[role='option']",
        "li[role='option']",
        ".ant-select-item-option",
        ".ant-select-dropdown .ant-select-item",
    )
    _SUCCESS_KEYWORDS = ("成功", "提交成功", "处理成功", "审批成功", "操作成功")
    _ERROR_KEYWORDS = ("失败", "错误", "异常", "不能为空", "请填写", "请先填写", "必填", "校验")
    _ACTION_CONFIG: dict[str, dict[str, Any]] = {
        "approve": {
            "decisionValue": "同意",
            "approvalRecordActions": ("同意",),
            "submitActionLabel": "批准",
            "recordSuccessMessage": "审批记录已追加最新同意动作。",
        },
        "reject": {
            "decisionValue": "驳回至已选节点",
            "approvalRecordActions": ("驳回", "拒绝"),
            "submitActionLabel": "驳回",
            "recordSuccessMessage": "审批记录已追加最新驳回动作。",
        },
    }

    def __init__(
        self,
        page: Page,
        logger: logging.Logger,
        timeout_ms: int,
        home_url: str,
        event_callback: Callable[..., None] | None = None,
    ) -> None:
        self.page = page
        self.logger = logger
        self.timeout_ms = timeout_ms
        self.home_url = home_url
        self.event_callback = event_callback
        self.collector = PermissionCollectFlow(
            page=page,
            logger=logger,
            timeout_ms=timeout_ms,
            home_url=home_url,
        )
        self._todo_page_size_applied = False

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").split()).strip()

    def set_page(self, page: Page) -> None:
        self.page = page
        self.collector.page = page

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

    def _emit_event(self, message: str, **extra: Any) -> None:
        if self.event_callback is None:
            return
        try:
            self.event_callback(message, **extra)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Failed to emit approval event %s: %s", message, exc)

    def _remember_todo_page_size_state(self, page_size_applied: bool) -> bool:
        self._todo_page_size_applied = self._todo_page_size_applied or bool(page_size_applied)
        return self._todo_page_size_applied

    def _todo_grid_is_visible(self) -> bool:
        try:
            todo_grid = self.page.locator("#gridview").first
            return todo_grid.count() > 0 and todo_grid.is_visible()
        except Exception:
            return False

    def _find_visible_todo_trigger(self, timeout_ms: int | None = None) -> Locator | None:
        todo_triggers = self.page.locator("div[id^='processflexpanelap_']").filter(has_text="待办任务")
        deadline = time.monotonic() + ((timeout_ms or self.timeout_ms) / 1000)
        last_error = ""

        while time.monotonic() < deadline:
            try:
                trigger_count = todo_triggers.count()
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                trigger_count = 0

            for index in range(trigger_count):
                trigger = todo_triggers.nth(index)
                try:
                    if trigger.is_visible():
                        return trigger
                except Exception as exc:  # noqa: BLE001
                    last_error = f"trigger[{index}]: {exc}"

            if self._todo_grid_is_visible():
                return None

            self.page.wait_for_timeout(200)

        if self._todo_grid_is_visible():
            return None

        raise PlaywrightTimeoutError(
            "Todo trigger did not become visible."
            f" selectors=div[id^='processflexpanelap_'][text*='待办任务'] last_error={last_error}"
        )

    def _open_todo_list_ready(self, page_size_timeout_ms: int | None = None) -> bool:
        started_at = time.monotonic()
        self._emit_event("approval_open_todo_started")
        todo_trigger = self._find_visible_todo_trigger()
        if todo_trigger is not None:
            todo_trigger.click(force=True)
        # Reuse the collect path's todo-list readiness flow so approval can see
        # the full pending set instead of only the current 10-row page.
        page_size_applied = self.collector._wait_for_todo_list_ready(page_size_timeout_ms=page_size_timeout_ms)
        page_size_applied = self._remember_todo_page_size_state(page_size_applied)
        self._emit_event(
            "approval_open_todo_finished",
            pageSizeApplied=page_size_applied,
            durationMs=round((time.monotonic() - started_at) * 1000, 1),
        )
        return page_size_applied

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

    def _task_tab_locator(self) -> Locator:
        task_tab = self.page.locator("#tabap .kd-cq-tabs-tab").filter(has_text="任务处理").first
        if task_tab.count() == 0:
            task_tab = self.page.locator("text=任务处理").first
        return task_tab

    def _open_task_tab(self) -> None:
        task_tab = self._task_tab_locator()
        task_tab.wait_for(state="visible", timeout=self.timeout_ms)
        task_tab.click(force=True)
        self.page.wait_for_timeout(600)

    def _approval_record_tab_locator(self) -> Locator:
        approval_tab = self.page.locator("#tabap .kd-cq-tabs-tab").filter(has_text="审批记录").first
        if approval_tab.count() == 0:
            approval_tab = self.page.locator("text=审批记录").first
        return approval_tab

    def _open_approval_record_tab(self) -> None:
        approval_tab = self._approval_record_tab_locator()
        approval_tab.wait_for(state="visible", timeout=self.timeout_ms)
        approval_tab.click(force=True)
        self.page.wait_for_timeout(600)

    @classmethod
    def _resolve_action_config(cls, action: str) -> dict[str, Any]:
        normalized_action = cls._normalize_text(action)
        config = cls._ACTION_CONFIG.get(normalized_action)
        if config is None:
            raise ValueError(f"暂不支持审批动作 {action!r}")
        return {
            "action": normalized_action,
            **config,
        }

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
        if deduplicated:
            return deduplicated

        fallback_texts = self.page.evaluate(
            r"""() => {
                const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                const visible = (el) => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                };
                const containerSelectors = [
                    '.kd-cq-dropdown',
                    '.kd-dropdown-menu',
                    '.kd-cq-select-dropdown',
                    '.kd-cq-combo-dropdown',
                    '.ant-select-dropdown',
                    '[role=\"listbox\"]',
                ];
                const containers = containerSelectors.flatMap((selector) =>
                    [...document.querySelectorAll(selector)].filter(visible)
                );
                const roots = containers.length > 0 ? containers : [];
                const result = [];
                for (const root of roots) {
                    for (const element of root.querySelectorAll('li, div, span, a')) {
                        if (!visible(element)) continue;
                        const text = normalize(element.innerText || element.textContent || '');
                        if (!text) continue;
                        result.push(text);
                    }
                }
                return result;
            }"""
        )
        for text in fallback_texts or []:
            normalized = self._normalize_text(text)
            if normalized and normalized not in deduplicated:
                deduplicated.append(normalized)
        return deduplicated

    def _open_decision_dropdown(self) -> None:
        trigger = self._decision_trigger()
        trigger.click(force=True)
        self.page.wait_for_timeout(250)
        if self._visible_option_texts():
            return

        field = self._task_field_item("审批决策")
        field.evaluate(
            r"""(item) => {
                const candidates = [
                    ".kd-cq-select-arrow",
                    ".kd-cq-combo-arrow",
                    ".kd-select-arrow",
                    "[role='combobox']",
                    "svg",
                    "input",
                    ".kd-cq-combo-selected",
                    ".kd-cq-select-selection-item",
                    ".kd-cq-select",
                    ".kd-cq-combo",
                ];
                for (const selector of candidates) {
                    const target = item.querySelector(selector);
                    if (!target) continue;
                    target.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
                    target.dispatchEvent(new MouseEvent("click", { bubbles: true }));
                    return;
                }
                item.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
                item.dispatchEvent(new MouseEvent("click", { bubbles: true }));
            }"""
        )
        self.page.wait_for_timeout(250)
        if self._visible_option_texts():
            return

        trigger.click(force=True)
        self.page.keyboard.press("ArrowDown")
        self.page.wait_for_timeout(250)

    def list_decision_options(self) -> list[str]:
        self._open_decision_dropdown()
        options = self._visible_option_texts()
        self.page.keyboard.press("Escape")
        return options

    def read_decision_value(self) -> str:
        return self._read_field_display_value("审批决策")

    def set_decision_value(self, target_value: str) -> str:
        current_value = self.read_decision_value()
        if current_value == target_value:
            return current_value

        self._open_decision_dropdown()
        option_selector = ",".join(self._OPTION_SELECTORS)
        option_candidates = [target_value]
        if "驳回" in target_value:
            option_candidates.extend(["驳回至已选", "驳回"])
        selected = False
        for option_text in option_candidates:
            option_locator = self.page.locator(option_selector).filter(has_text=option_text).first
            try:
                option_locator.wait_for(state="visible", timeout=min(self.timeout_ms, 2500))
                option_locator.click(force=True)
                selected = True
                break
            except Exception:  # noqa: BLE001
                continue
        if not selected:
            click_result = self.page.evaluate(
                r"""(payload) => {
                    const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                    };
                    const containerSelectors = [
                        '.kd-cq-dropdown',
                        '.kd-dropdown-menu',
                        '.kd-cq-select-dropdown',
                        '.kd-cq-combo-dropdown',
                        '.ant-select-dropdown',
                        '[role=\"listbox\"]',
                    ];
                    const containers = containerSelectors.flatMap((selector) =>
                        [...document.querySelectorAll(selector)].filter(visible)
                    );
                    const collectBestCandidate = (elements) => {
                        const matches = [];
                        for (const element of elements) {
                            if (!visible(element)) continue;
                            const text = normalize(element.innerText || element.textContent || '');
                            if (!text) continue;
                            if (!payload.candidates.some((candidate) => text.includes(candidate))) continue;
                            const hasSameTextChild = [...element.querySelectorAll('*')].some((child) => {
                                if (!visible(child)) return false;
                                return normalize(child.innerText || child.textContent || '') === text;
                            });
                            if (hasSameTextChild) continue;
                            const exact = payload.candidates.some((candidate) => text === candidate);
                            matches.push({ element, text, exact, length: text.length });
                        }
                        if (matches.length === 0) return null;
                        matches.sort((left, right) => {
                            if (left.exact !== right.exact) return left.exact ? -1 : 1;
                            return left.length - right.length;
                        });
                        return matches[0];
                    };
                    for (const container of containers) {
                        const best = collectBestCandidate(container.querySelectorAll('li, div, span, a'));
                        if (!best) continue;
                        best.element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        best.element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                        return { clicked: true, text: best.text };
                    }
                    return { clicked: false, text: '' };
                }""",
                {"candidates": option_candidates},
            )
            selected = bool((click_result or {}).get("clicked"))
        if not selected:
            click_result = self.page.evaluate(
                r"""(payload) => {
                    const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                    const visible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
                    };
                    const allElements = [...document.querySelectorAll('body *')].filter(visible);
                    const matches = [];
                    for (const candidate of payload.candidates) {
                        for (const element of allElements) {
                            const text = normalize(element.innerText || element.textContent || '');
                            if (!text || !text.includes(candidate)) continue;
                            const hasSameTextChild = [...element.querySelectorAll('*')].some((child) => {
                                if (!visible(child)) return false;
                                return normalize(child.innerText || child.textContent || '') === text;
                            });
                            if (hasSameTextChild) continue;
                            const exact = payload.candidates.some((item) => text === item);
                            matches.push({ element, text, exact, length: text.length });
                        }
                    }
                    if (matches.length > 0) {
                        matches.sort((left, right) => {
                            if (left.exact !== right.exact) return left.exact ? -1 : 1;
                            return left.length - right.length;
                        });
                        const best = matches[0];
                        best.element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                        best.element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                        return { clicked: true, text: best.text };
                    }
                    return { clicked: false, text: '' };
                }""",
                {"candidates": option_candidates},
            )
            selected = bool((click_result or {}).get("clicked"))
        if not selected:
            raise RuntimeError(f"审批决策下拉未找到目标选项：{target_value!r}")
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
                    '.kd-cq-dialog .kd-cq-dialog-body',
                    '.kd-cq-dialog .kd-cq-dialog-content',
                    '.kd-modal .kd-modal-body',
                    '.kd-dialog .kd-dialog-body',
                    '.kd-cq-form-item-explain-error',
                    '.kd-cq-form-item-help',
                    '.kd-cq-field-item-error',
                    '.ant-form-item-explain-error',
                    '.ant-form-item-extra',
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
        started_at = time.monotonic()
        self._emit_event("approval_record_capture_started")
        self._open_approval_record_tab()
        records = self.collector.extract_approval_records()
        self._open_task_tab()
        self._emit_event(
            "approval_record_capture_finished",
            approvalRecordCount=len(records),
            durationMs=round((time.monotonic() - started_at) * 1000, 1),
        )
        return records

    def _inspect_submission_state(self) -> dict[str, Any]:
        try:
            state = self.page.evaluate(
                r"""(payload) => {
                    const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
                    const visible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return (
                            style.display !== 'none' &&
                            style.visibility !== 'hidden' &&
                            rect.width > 0 &&
                            rect.height > 0
                        );
                    };
                    const anyVisible = (selectors, expectedText = '') => {
                        for (const selector of selectors) {
                            for (const element of document.querySelectorAll(selector)) {
                                if (!visible(element)) continue;
                                if (!expectedText) return true;
                                const text = normalize(element.innerText || element.textContent || '');
                                if (text.includes(expectedText)) return true;
                            }
                        }
                        return false;
                    };

                    const tabs = [...document.querySelectorAll('#tabap .kd-cq-tabs-tab, [id^="tabap"] .kd-cq-tabs-tab')]
                        .filter(visible)
                        .map((el) => normalize(el.innerText || ''))
                        .filter(Boolean);

                    return {
                        submitButtonVisible: anyVisible(payload.submitSelectors, payload.submitText),
                        taskTabVisible: tabs.some((text) => text.includes('任务处理')),
                        approvalTabVisible: tabs.some((text) => text.includes('审批记录')),
                        todoListVisible: visible(document.querySelector('#gridview')),
                        documentDetailVisible: visible(document.querySelector('#fs_baseinfo')) || visible(document.querySelector('#entryentity')),
                        visibleTabs: tabs,
                    };
                }""",
                {
                    "submitSelectors": [
                        "a.kd-cq-btn",
                        "button",
                        "a",
                    ],
                    "submitText": "提交",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "submitButtonVisible": False,
                "taskTabVisible": False,
                "approvalTabVisible": False,
                "todoListVisible": False,
                "documentDetailVisible": False,
                "visibleTabs": [],
                "probeError": str(exc),
            }

        normalized = {
            "submitButtonVisible": bool(state.get("submitButtonVisible")),
            "taskTabVisible": bool(state.get("taskTabVisible")),
            "approvalTabVisible": bool(state.get("approvalTabVisible")),
            "todoListVisible": bool(state.get("todoListVisible")),
            "documentDetailVisible": bool(state.get("documentDetailVisible")),
            "visibleTabs": [self._normalize_text(item) for item in state.get("visibleTabs") or [] if item],
        }
        probe_error = self._normalize_text(state.get("probeError"))
        if probe_error:
            normalized["probeError"] = probe_error
        return normalized

    def _probe_todo_document_presence(
        self,
        document_no: str,
        timeout_ms: int = 8000,
        todo_ready_timeout_ms: int | None = None,
    ) -> dict[str, Any]:
        probe: dict[str, Any] = {
            "todoListVisible": False,
            "documentStillInTodo": None,
            "probeError": "",
            "pageSizeApplied": False,
            "todoTotalCount": None,
            "scannedUniqueRowCount": 0,
            "coveredAllTodoRows": False,
        }
        grid_visible = False
        try:
            todo_grid = self.page.locator("#gridview").first
            if todo_grid.count() > 0 and todo_grid.is_visible():
                grid_visible = True
        except Exception:
            grid_visible = False

        try:
            if grid_visible:
                # When submit brings us back to todo grid directly, avoid relying on
                # the left-panel "待办任务" trigger visibility.
                page_size_applied = self.collector._wait_for_todo_list_ready(page_size_timeout_ms=todo_ready_timeout_ms)
            else:
                try:
                    page_size_applied = self.collector.return_to_todo_list(page_size_timeout_ms=todo_ready_timeout_ms)
                except Exception:
                    page_size_applied = self._open_todo_list_ready(page_size_timeout_ms=todo_ready_timeout_ms)
        except Exception as exc:  # noqa: BLE001
            probe["probeError"] = f"open_todo_list_failed: {exc}"
            return probe

        probe["todoListVisible"] = True
        probe["pageSizeApplied"] = self._remember_todo_page_size_state(page_size_applied)
        try:
            grid = self.collector._extract_best_grid(TODO_HEADERS)
        except Exception as exc:  # noqa: BLE001
            probe["probeError"] = f"todo_grid_not_ready: {exc}"
            return probe

        grid_selector = str(grid.get("selector") or "")
        headers = list(grid.get("headers") or [])
        if not grid_selector or not headers:
            probe["probeError"] = "todo_grid_selector_missing"
            return probe

        self.collector._set_grid_vertical_position(grid_selector, 0)
        try:
            todo_total_count = self.collector._extract_todo_total_count()
        except Exception as exc:  # noqa: BLE001
            todo_total_count = None
            probe["probeError"] = f"todo_total_count_probe_failed: {exc}"
        probe["todoTotalCount"] = todo_total_count

        deadline = time.monotonic() + (timeout_ms / 1000)
        stagnant_rounds = 0
        saw_snapshot = False
        last_error = ""
        collected_row_keys: set[str] = set()

        while time.monotonic() < deadline:
            if self.collector._focus_todo_row(grid_selector, document_no):
                probe["documentStillInTodo"] = True
                probe["probeError"] = ""
                return probe

            snapshot = self.collector._get_grid_virtual_snapshot(grid_selector, headers)
            if not snapshot:
                last_error = "todo_grid_snapshot_missing"
                self.page.wait_for_timeout(200)
                continue

            saw_snapshot = True
            for row in snapshot.get("rows", []):
                normalized_row = self.collector._normalize_row_cells(headers, row)
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
                    collected_row_keys.add(row_key)

            probe["scannedUniqueRowCount"] = len(collected_row_keys)
            if todo_total_count is not None and len(collected_row_keys) >= todo_total_count:
                probe["documentStillInTodo"] = False
                probe["coveredAllTodoRows"] = True
                probe["probeError"] = ""
                return probe

            scroll_height = int(snapshot.get("scrollHeight", 0) or 0)
            client_height = int(snapshot.get("clientHeight", 0) or 0)
            current_top = int(snapshot.get("scrollTop", 0) or 0)
            next_top = min(current_top + max(client_height - 40, 200), max(scroll_height - client_height, 0))
            if next_top <= current_top:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
                self.collector._set_grid_vertical_position(grid_selector, next_top)

            if stagnant_rounds >= 3:
                break

        if saw_snapshot and todo_total_count is not None and len(collected_row_keys) >= todo_total_count:
            probe["documentStillInTodo"] = False
            probe["coveredAllTodoRows"] = True
        else:
            probe["documentStillInTodo"] = False if saw_snapshot else None
        probe["probeError"] = last_error
        return probe

    @staticmethod
    def _is_todo_probe_strong_success(todo_probe: dict[str, Any]) -> bool:
        if todo_probe.get("documentStillInTodo") is not False:
            return False
        if todo_probe.get("pageSizeApplied", False):
            return True
        return bool(todo_probe.get("coveredAllTodoRows", False))

    @staticmethod
    def _should_return_pending_confirmation(
        state_before_todo_probe: dict[str, Any],
        todo_probe: dict[str, Any],
    ) -> bool:
        if todo_probe.get("documentStillInTodo") is not None:
            return False
        return (
            not state_before_todo_probe.get("submitButtonVisible", False)
            and (
                state_before_todo_probe.get("todoListVisible", False)
                or not state_before_todo_probe.get("documentDetailVisible", True)
                or (
                    not state_before_todo_probe.get("taskTabVisible", False)
                    and not state_before_todo_probe.get("approvalTabVisible", False)
                )
            )
        )

    @staticmethod
    def _should_prioritize_todo_probe(state: dict[str, Any]) -> bool:
        if state.get("todoListVisible", False):
            return True
        return (
            not state.get("submitButtonVisible", False)
            and not state.get("documentDetailVisible", True)
            and not state.get("taskTabVisible", False)
            and not state.get("approvalTabVisible", False)
        )

    def _build_pending_confirmation_result(
        self,
        document_no: str,
        state_before_todo_probe: dict[str, Any],
        todo_probe: dict[str, Any],
        submit_action_label: str,
    ) -> dict[str, Any]:
        self._emit_event(
            "approval_confirmation_uncertain",
            documentNo=document_no,
            submitButtonVisible=state_before_todo_probe.get("submitButtonVisible", False),
            taskTabVisible=state_before_todo_probe.get("taskTabVisible", False),
            approvalTabVisible=state_before_todo_probe.get("approvalTabVisible", False),
            todoListVisible=state_before_todo_probe.get("todoListVisible", False),
            documentDetailVisible=state_before_todo_probe.get("documentDetailVisible", False),
            probeError=todo_probe.get("probeError", ""),
        )
        return {
            "status": "submitted_pending_confirmation",
            "confirmationType": "submitted_pending_confirmation",
            "confirmationMessage": (
                "提交动作已发出，但当前未拿到强成功回执。"
                f"请先不要重复点击{submit_action_label}，可先查看最新审批日志或执行一次“同步待办状态”确认。"
            ),
        }

    def wait_for_submission_confirmation(
        self,
        document_no: str,
        expected_opinion: str,
        approval_count_before: int,
        wait_timeout_ms: int | None = None,
        *,
        expected_approval_actions: tuple[str, ...] = ("同意",),
        record_success_message: str = "审批记录已追加最新同意动作。",
        submit_action_label: str = "批准",
    ) -> dict[str, Any]:
        total_timeout_ms = wait_timeout_ms or max(self.timeout_ms, 45000)
        started_at = time.monotonic()
        feedback_deadline = started_at + (min(total_timeout_ms, 8000) / 1000)
        approval_record_deadline = started_at + (min(total_timeout_ms, 25000) / 1000)
        final_deadline = started_at + (total_timeout_ms / 1000)
        last_error_message = ""
        last_approval_record_error = ""
        last_todo_probe: dict[str, Any] | None = None

        self._emit_event(
            "approval_confirmation_probe_started",
            documentNo=document_no,
            approvalRecordCountBefore=approval_count_before,
            waitTimeoutMs=total_timeout_ms,
        )

        should_run_todo_probe = False
        while time.monotonic() < feedback_deadline:
            error_message = self.visible_feedback_message(self._ERROR_KEYWORDS)
            if error_message:
                self._emit_event(
                    "approval_confirmation_feedback_detected",
                    documentNo=document_no,
                    outcome="error",
                    feedbackMessage=error_message,
                )
                raise RuntimeError(f"EHR 提交失败：{error_message}")

            success_message = self.visible_feedback_message(self._SUCCESS_KEYWORDS)
            if success_message:
                self._emit_event(
                    "approval_confirmation_feedback_detected",
                    documentNo=document_no,
                    outcome="success",
                    feedbackMessage=success_message,
                )
                return {
                    "status": "succeeded",
                    "confirmationType": "toast",
                    "confirmationMessage": success_message,
                }

            state = self._inspect_submission_state()
            if self._should_prioritize_todo_probe(state):
                should_run_todo_probe = True
                break

            self.page.wait_for_timeout(500)

        state_before_todo_probe = self._inspect_submission_state()
        self._emit_event(
            "approval_todo_reprobe_started",
            documentNo=document_no,
            submitButtonVisible=state_before_todo_probe.get("submitButtonVisible", False),
            taskTabVisible=state_before_todo_probe.get("taskTabVisible", False),
            approvalTabVisible=state_before_todo_probe.get("approvalTabVisible", False),
            todoListVisible=state_before_todo_probe.get("todoListVisible", False),
            documentDetailVisible=state_before_todo_probe.get("documentDetailVisible", False),
            earlyTriggered=should_run_todo_probe,
        )
        todo_probe = self._probe_todo_document_presence(
            document_no=document_no,
            timeout_ms=8000,
            todo_ready_timeout_ms=min(self.timeout_ms, 2000),
        )
        last_todo_probe = todo_probe
        self._emit_event(
            "approval_todo_reprobe_result",
            documentNo=document_no,
            todoListVisible=todo_probe.get("todoListVisible", False),
            documentStillInTodo=todo_probe.get("documentStillInTodo"),
            pageSizeApplied=todo_probe.get("pageSizeApplied", False),
            todoTotalCount=todo_probe.get("todoTotalCount"),
            scannedUniqueRowCount=todo_probe.get("scannedUniqueRowCount", 0),
            coveredAllTodoRows=todo_probe.get("coveredAllTodoRows", False),
            submitButtonVisible=state_before_todo_probe.get("submitButtonVisible", False),
            taskTabVisible=state_before_todo_probe.get("taskTabVisible", False),
            approvalTabVisible=state_before_todo_probe.get("approvalTabVisible", False),
            probeError=todo_probe.get("probeError", ""),
        )
        if todo_probe.get("documentStillInTodo") is False:
            if self._is_todo_probe_strong_success(todo_probe):
                return {
                    "status": "succeeded",
                    "confirmationType": "todo_disappeared",
                    "confirmationMessage": "提交后目标单据已不在当前账号待办中。",
                }
            self._emit_event(
                "approval_todo_reprobe_retry_full_scan_started",
                documentNo=document_no,
                reason="page_size_not_confirmed",
            )
            todo_probe = self._probe_todo_document_presence(
                document_no=document_no,
                timeout_ms=8000,
                todo_ready_timeout_ms=min(self.timeout_ms, 5000),
            )
            last_todo_probe = todo_probe
            self._emit_event(
                "approval_todo_reprobe_result",
                documentNo=document_no,
                todoListVisible=todo_probe.get("todoListVisible", False),
                documentStillInTodo=todo_probe.get("documentStillInTodo"),
                pageSizeApplied=todo_probe.get("pageSizeApplied", False),
                todoTotalCount=todo_probe.get("todoTotalCount"),
                scannedUniqueRowCount=todo_probe.get("scannedUniqueRowCount", 0),
                coveredAllTodoRows=todo_probe.get("coveredAllTodoRows", False),
                submitButtonVisible=state_before_todo_probe.get("submitButtonVisible", False),
                taskTabVisible=state_before_todo_probe.get("taskTabVisible", False),
                approvalTabVisible=state_before_todo_probe.get("approvalTabVisible", False),
                probeError=todo_probe.get("probeError", ""),
            )
            if self._is_todo_probe_strong_success(todo_probe):
                return {
                    "status": "succeeded",
                    "confirmationType": "todo_disappeared",
                    "confirmationMessage": "提交后目标单据已不在当前账号待办中。",
                }
            if todo_probe.get("documentStillInTodo") is False:
                return self._build_pending_confirmation_result(
                    document_no,
                    state_before_todo_probe,
                    todo_probe,
                    submit_action_label=submit_action_label,
                )

        while time.monotonic() < approval_record_deadline:
            error_message = self.visible_feedback_message(self._ERROR_KEYWORDS)
            if error_message:
                self._emit_event(
                    "approval_confirmation_feedback_detected",
                    documentNo=document_no,
                    outcome="error",
                    feedbackMessage=error_message,
                )
                raise RuntimeError(f"EHR 提交失败：{error_message}")

            success_message = self.visible_feedback_message(self._SUCCESS_KEYWORDS)
            if success_message:
                self._emit_event(
                    "approval_confirmation_feedback_detected",
                    documentNo=document_no,
                    outcome="success",
                    feedbackMessage=success_message,
                )
                return {
                    "status": "succeeded",
                    "confirmationType": "toast",
                    "confirmationMessage": success_message,
                }

            state = self._inspect_submission_state()
            if not state.get("approvalTabVisible", False):
                self.page.wait_for_timeout(800)
                continue

            try:
                records = self.capture_approval_records()
            except Exception as exc:  # noqa: BLE001
                last_error_message = str(exc)
                if last_error_message != last_approval_record_error:
                    last_approval_record_error = last_error_message
                    self._emit_event(
                        "approval_record_probe_failed",
                        documentNo=document_no,
                        error=last_error_message,
                    )
                self.page.wait_for_timeout(800)
                continue

            if len(records) > approval_count_before:
                latest_record = records[-1]
                latest_action = self._normalize_text(latest_record.get("approval_action"))
                latest_opinion = self._normalize_text(latest_record.get("approval_opinion"))
                normalized_expected_actions = {
                    self._normalize_text(action)
                    for action in expected_approval_actions
                    if self._normalize_text(action)
                }
                if latest_action in normalized_expected_actions or latest_opinion == self._normalize_text(expected_opinion):
                    self._emit_event(
                        "approval_record_probe_hit",
                        documentNo=document_no,
                        latestApprovalAction=latest_action,
                        latestApprovalOpinion=latest_opinion,
                    )
                    return {
                        "status": "succeeded",
                        "confirmationType": "approval_record",
                        "confirmationMessage": record_success_message,
                        "latestApprovalAction": latest_action,
                        "latestApprovalOpinion": latest_opinion,
                    }

            self.page.wait_for_timeout(800)

        state_before_todo_probe = self._inspect_submission_state()
        self._emit_event(
            "approval_todo_reprobe_started",
            documentNo=document_no,
            submitButtonVisible=state_before_todo_probe.get("submitButtonVisible", False),
            taskTabVisible=state_before_todo_probe.get("taskTabVisible", False),
            approvalTabVisible=state_before_todo_probe.get("approvalTabVisible", False),
            todoListVisible=state_before_todo_probe.get("todoListVisible", False),
            documentDetailVisible=state_before_todo_probe.get("documentDetailVisible", False),
        )

        todo_probe = self._probe_todo_document_presence(
            document_no=document_no,
            timeout_ms=8000,
            todo_ready_timeout_ms=min(self.timeout_ms, 2000),
        )
        last_todo_probe = todo_probe
        self._emit_event(
            "approval_todo_reprobe_result",
            documentNo=document_no,
            todoListVisible=todo_probe.get("todoListVisible", False),
            documentStillInTodo=todo_probe.get("documentStillInTodo"),
            pageSizeApplied=todo_probe.get("pageSizeApplied", False),
            todoTotalCount=todo_probe.get("todoTotalCount"),
            scannedUniqueRowCount=todo_probe.get("scannedUniqueRowCount", 0),
            coveredAllTodoRows=todo_probe.get("coveredAllTodoRows", False),
            submitButtonVisible=state_before_todo_probe.get("submitButtonVisible", False),
            taskTabVisible=state_before_todo_probe.get("taskTabVisible", False),
            approvalTabVisible=state_before_todo_probe.get("approvalTabVisible", False),
            probeError=todo_probe.get("probeError", ""),
        )
        if todo_probe.get("documentStillInTodo") is False:
            if self._is_todo_probe_strong_success(todo_probe):
                return {
                    "status": "succeeded",
                    "confirmationType": "todo_disappeared",
                    "confirmationMessage": "提交后目标单据已不在当前账号待办中。",
                }
            self._emit_event(
                "approval_todo_reprobe_retry_full_scan_started",
                documentNo=document_no,
                reason="page_size_not_confirmed",
            )
            todo_probe = self._probe_todo_document_presence(
                document_no=document_no,
                timeout_ms=8000,
                todo_ready_timeout_ms=min(self.timeout_ms, 5000),
            )
            last_todo_probe = todo_probe
            self._emit_event(
                "approval_todo_reprobe_result",
                documentNo=document_no,
                todoListVisible=todo_probe.get("todoListVisible", False),
                documentStillInTodo=todo_probe.get("documentStillInTodo"),
                pageSizeApplied=todo_probe.get("pageSizeApplied", False),
                todoTotalCount=todo_probe.get("todoTotalCount"),
                scannedUniqueRowCount=todo_probe.get("scannedUniqueRowCount", 0),
                coveredAllTodoRows=todo_probe.get("coveredAllTodoRows", False),
                submitButtonVisible=state_before_todo_probe.get("submitButtonVisible", False),
                taskTabVisible=state_before_todo_probe.get("taskTabVisible", False),
                approvalTabVisible=state_before_todo_probe.get("approvalTabVisible", False),
                probeError=todo_probe.get("probeError", ""),
            )
            if self._is_todo_probe_strong_success(todo_probe):
                return {
                    "status": "succeeded",
                    "confirmationType": "todo_disappeared",
                    "confirmationMessage": "提交后目标单据已不在当前账号待办中。",
                }
            if todo_probe.get("documentStillInTodo") is False:
                return self._build_pending_confirmation_result(
                    document_no,
                    state_before_todo_probe,
                    todo_probe,
                    submit_action_label=submit_action_label,
                )

        if todo_probe.get("documentStillInTodo") is True and time.monotonic() < final_deadline:
            self.page.wait_for_timeout(3000)
            todo_probe = self._probe_todo_document_presence(
                document_no=document_no,
                timeout_ms=6000,
                todo_ready_timeout_ms=min(self.timeout_ms, 2000),
            )
            last_todo_probe = todo_probe
            self._emit_event(
                "approval_todo_reprobe_result",
                documentNo=document_no,
                todoListVisible=todo_probe.get("todoListVisible", False),
                documentStillInTodo=todo_probe.get("documentStillInTodo"),
                pageSizeApplied=todo_probe.get("pageSizeApplied", False),
                todoTotalCount=todo_probe.get("todoTotalCount"),
                scannedUniqueRowCount=todo_probe.get("scannedUniqueRowCount", 0),
                coveredAllTodoRows=todo_probe.get("coveredAllTodoRows", False),
                submitButtonVisible=state_before_todo_probe.get("submitButtonVisible", False),
                taskTabVisible=state_before_todo_probe.get("taskTabVisible", False),
                approvalTabVisible=state_before_todo_probe.get("approvalTabVisible", False),
                probeError=todo_probe.get("probeError", ""),
            )
            if self._is_todo_probe_strong_success(todo_probe):
                return {
                    "status": "succeeded",
                    "confirmationType": "todo_disappeared",
                    "confirmationMessage": "提交后目标单据已不在当前账号待办中。",
                }

        if todo_probe.get("documentStillInTodo") is True:
            raise RuntimeError(
                "点击提交后目标单据仍在当前账号待办中，且未观察到成功反馈。"
                + (f" last_error={last_error_message}" if last_error_message else "")
            )

        if self._should_return_pending_confirmation(state_before_todo_probe, todo_probe):
            return self._build_pending_confirmation_result(
                document_no,
                state_before_todo_probe,
                todo_probe,
                submit_action_label=submit_action_label,
            )

        raise RuntimeError(
            "点击提交后未在预期时间内观察到成功反馈。"
            + (
                f" todo_probe={last_todo_probe}"
                if last_todo_probe is not None
                else ""
            )
            + (f" last_error={last_error_message}" if last_error_message else "")
        )

    def prepare_document_for_approval(self, document_no: str) -> dict[str, Any]:
        started_at = time.monotonic()
        self._emit_event("approval_prepare_started", documentNo=document_no)
        self._open_todo_list_ready(page_size_timeout_ms=min(self.timeout_ms, 2000))
        open_started_at = time.monotonic()
        try:
            self.collector.open_document(document_no, link_timeout_ms=min(self.timeout_ms, 2000))
        except PlaywrightTimeoutError as exc:
            if self._todo_page_size_applied:
                raise
            self._emit_event(
                "approval_document_open_retry_full_scan_started",
                documentNo=document_no,
                error=str(exc),
            )
            self._open_todo_list_ready(page_size_timeout_ms=self.timeout_ms)
            self.collector.open_document(document_no)
        self._emit_event(
            "approval_document_opened",
            documentNo=document_no,
            durationMs=round((time.monotonic() - open_started_at) * 1000, 1),
        )
        basic_info_started_at = time.monotonic()
        basic_info = self.collector.extract_basic_info()
        self._emit_event(
            "approval_basic_info_loaded",
            documentNo=document_no,
            loadedDocumentNo=self._normalize_text(basic_info.get("单据编号")),
            durationMs=round((time.monotonic() - basic_info_started_at) * 1000, 1),
        )
        current_document_no = self._normalize_text(basic_info.get("单据编号"))
        if current_document_no != document_no:
            raise RuntimeError(
                f"打开单据校验失败，期望={document_no!r}，实际={current_document_no!r}"
            )

        detail_tabs = self._list_visible_tabs()
        self._open_task_tab()
        self._emit_event(
            "approval_prepare_finished",
            documentNo=document_no,
            detailTabCount=len(detail_tabs),
            durationMs=round((time.monotonic() - started_at) * 1000, 1),
        )
        return {
            "basicInfo": basic_info,
            "detailTabs": detail_tabs,
        }

    def execute_action(
        self,
        *,
        action: str,
        document_no: str,
        approval_opinion: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        action_config = self._resolve_action_config(action)
        decision_target = str(action_config["decisionValue"])
        expected_approval_actions = tuple(action_config["approvalRecordActions"])
        submit_action_label = str(action_config["submitActionLabel"])
        record_success_message = str(action_config["recordSuccessMessage"])

        preparation = self.prepare_document_for_approval(document_no)
        baseline_records = self.capture_approval_records()

        decision_probe_started_at = time.monotonic()
        decision_before = self.read_decision_value()
        decision_options = self.list_decision_options()
        self._emit_event(
            "approval_decision_state_loaded",
            documentNo=document_no,
            decisionBefore=decision_before,
            decisionOptionCount=len(decision_options),
            durationMs=round((time.monotonic() - decision_probe_started_at) * 1000, 1),
        )

        opinion_probe_started_at = time.monotonic()
        opinion_before = self.read_approval_opinion()
        try:
            decision_after = self.set_decision_value(decision_target)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"当前审批决策不支持“{decision_target}”，可用选项={decision_options}"
            ) from exc
        opinion_after = self.write_approval_opinion(approval_opinion)
        self._emit_event(
            "approval_form_filled",
            documentNo=document_no,
            action=action_config["action"],
            decisionAfter=decision_after,
            approvalOpinionBefore=opinion_before,
            approvalOpinionAfter=opinion_after,
            durationMs=round((time.monotonic() - opinion_probe_started_at) * 1000, 1),
        )
        submit_button = self.submit_button_locator()
        submit_label = self._normalize_text(submit_button.inner_text())
        self._emit_event(
            "approval_submit_button_ready",
            documentNo=document_no,
            submitLabel=submit_label,
        )

        response = {
            "action": action_config["action"],
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
            restore_warnings: list[str] = []
            if opinion_before != approval_opinion:
                try:
                    self.write_approval_opinion(opinion_before)
                except Exception as exc:  # noqa: BLE001
                    restore_warnings.append(f"restore_approval_opinion_failed: {exc}")
            if decision_before and decision_before != decision_target:
                try:
                    self.set_decision_value(decision_before)
                except Exception as exc:  # noqa: BLE001
                    restore_warnings.append(f"restore_decision_failed: {exc}")
            response["approvalOpinionRestored"] = self.read_approval_opinion()
            response["decisionRestored"] = self.read_decision_value()
            if restore_warnings:
                response["dryRunRestoreWarnings"] = restore_warnings
            response["status"] = "succeeded"
            response["confirmationType"] = "dry_run"
            response["confirmationMessage"] = (
                "已完成页面连通与写入验证，未点击提交。"
                if not restore_warnings
                else "已完成页面连通与写入验证，未点击提交；但页面回滚存在告警，请查看 dryRunRestoreWarnings。"
            )
            return response

        submit_button.click(force=True)
        self._emit_event(
            "approval_submit_clicked",
            documentNo=document_no,
            action=action_config["action"],
            submitLabel=submit_label,
        )
        self.page.wait_for_timeout(600)
        confirmation = self.wait_for_submission_confirmation(
            document_no=document_no,
            expected_opinion=approval_opinion,
            approval_count_before=len(baseline_records),
            wait_timeout_ms=max(self.timeout_ms, 45000),
            expected_approval_actions=expected_approval_actions,
            record_success_message=record_success_message,
            submit_action_label=submit_action_label,
        )
        response.update(confirmation)
        return response

    def execute_approve(self, document_no: str, approval_opinion: str, dry_run: bool = False) -> dict[str, Any]:
        return self.execute_action(
            action="approve",
            document_no=document_no,
            approval_opinion=approval_opinion,
            dry_run=dry_run,
        )

    def execute_reject(self, document_no: str, approval_opinion: str, dry_run: bool = False) -> dict[str, Any]:
        return self.execute_action(
            action="reject",
            document_no=document_no,
            approval_opinion=approval_opinion,
            dry_run=dry_run,
        )
