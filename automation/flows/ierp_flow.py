from __future__ import annotations

import logging
from datetime import datetime

from playwright.sync_api import Page

from automation.pages.base_page import BasePage


class IerpFlow:
    def __init__(
        self,
        page: Page,
        selectors: dict[str, dict[str, list[str]]],
        logger: logging.Logger,
        timeout_ms: int,
        auto_reason: str | None = None,
        enable_create: bool = False,
        enable_submit: bool = False,
    ) -> None:
        self.base = BasePage(page=page, selectors=selectors, logger=logger, timeout_ms=timeout_ms)
        self.logger = logger
        self.auto_reason = auto_reason or f"AUTO-PLAN001-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.enable_create = enable_create
        self.enable_submit = enable_submit

    def run_example(self) -> None:
        workflow = self.base.selectors.get("workflow", {})
        entry_key = "app_entry" if "app_entry" in workflow else "menu_entry"
        required_keys = [entry_key]
        missing = [k for k in required_keys if k not in workflow]
        if missing:
            raise KeyError(
                "Missing workflow selectors: "
                + ", ".join(f"workflow.{key}" for key in missing)
                + ". Please update automation/config/selectors.yaml"
            )

        self.base.click("workflow", entry_key)
        if "page_ready" in workflow:
            self.base.wait_and_get("workflow", "page_ready")
            self.logger.info("Workflow page is ready")

        if not self.enable_create:
            self.logger.info("Create/save is disabled, navigation-only run completed")
            return

        if "form_create" not in workflow:
            raise KeyError("Missing workflow selector: workflow.form_create")
        self.base.click("workflow", "form_create")

        if "reason_input" in workflow:
            self.base.fill("workflow", "reason_input", self.auto_reason)
            self.logger.info("Filled reason field: %s", self.auto_reason)

        if "save" in workflow:
            self.base.click("workflow", "save")
            self.logger.info("Clicked save")
            if "save_success_toast" in workflow:
                try:
                    self.base.wait_and_get("workflow", "save_success_toast")
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning("Save success toast not detected: %s", exc)

        if self.enable_submit and "submit" in workflow:
            self.base.click("workflow", "submit")
            if "submit_success_toast" in workflow:
                self.base.wait_and_get("workflow", "submit_success_toast")
            elif "success_toast" in workflow:
                self.base.wait_and_get("workflow", "success_toast")
            self.logger.info("Workflow submit completed")
