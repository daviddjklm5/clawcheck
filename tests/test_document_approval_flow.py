from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from automation.flows.document_approval_flow import DocumentApprovalFlow


class DocumentApprovalFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.page.keyboard = MagicMock()
        self.logger = MagicMock()
        self.flow = DocumentApprovalFlow(
            page=self.page,
            logger=self.logger,
            timeout_ms=2000,
            home_url="https://example.com",
        )

    def test_write_approval_opinion_prefers_keyboard_path(self) -> None:
        locator = MagicMock()
        locator.input_value.side_effect = ["同意通过"]

        with patch.object(self.flow, "approval_opinion_locator", return_value=locator):
            result = self.flow.write_approval_opinion("同意通过")

        self.assertEqual(result, "同意通过")
        locator.click.assert_called_once_with(force=True)
        self.page.keyboard.press.assert_any_call("Control+A")
        self.page.keyboard.insert_text.assert_called_once_with("同意通过")
        locator.evaluate.assert_called_once_with("(el) => el.blur()")

    def test_write_approval_opinion_falls_back_to_dom_events(self) -> None:
        locator = MagicMock()
        locator.input_value.side_effect = ["同意", "OK，通过"]

        with patch.object(self.flow, "approval_opinion_locator", return_value=locator):
            result = self.flow.write_approval_opinion("OK，通过")

        self.assertEqual(result, "OK，通过")
        locator.evaluate.assert_any_call(
            """(el, value) => {
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
            "OK，通过",
        )
        locator.evaluate.assert_any_call("(el) => el.blur()")

    def test_open_todo_list_ready_reuses_collect_wait_flow(self) -> None:
        todo_trigger = MagicMock()
        self.page.locator.return_value.filter.return_value.first = todo_trigger
        self.flow.collector._wait_for_todo_list_ready = MagicMock()

        self.flow._open_todo_list_ready()

        self.page.locator.assert_called_once_with("div[id^='processflexpanelap_']")
        self.page.locator.return_value.filter.assert_called_once_with(has_text="待办任务")
        todo_trigger.wait_for.assert_called_once_with(state="visible", timeout=2000)
        todo_trigger.click.assert_called_once_with(force=True)
        self.flow.collector._wait_for_todo_list_ready.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
