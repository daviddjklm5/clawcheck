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

    def test_wait_for_submission_confirmation_returns_todo_disappeared_success(self) -> None:
        with (
            patch("automation.flows.document_approval_flow.time.monotonic", side_effect=[0.0, 1.0, 9.0, 10.0, 26.0]),
            patch.object(self.flow, "visible_feedback_message", return_value=""),
            patch.object(self.flow, "capture_approval_records", side_effect=RuntimeError("approval tab hidden")),
            patch.object(
                self.flow,
                "_inspect_submission_state",
                return_value={
                    "submitButtonVisible": False,
                    "taskTabVisible": False,
                    "approvalTabVisible": False,
                    "todoListVisible": False,
                    "documentDetailVisible": False,
                },
            ),
            patch.object(
                self.flow,
                "_probe_todo_document_presence",
                return_value={
                    "todoListVisible": True,
                    "documentStillInTodo": False,
                    "probeError": "",
                },
            ),
        ):
            result = self.flow.wait_for_submission_confirmation(
                document_no="RA-TEST-001",
                expected_opinion="同意",
                approval_count_before=1,
                wait_timeout_ms=30_000,
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["confirmationType"], "todo_disappeared")

    def test_wait_for_submission_confirmation_returns_pending_when_structure_changed_but_todo_probe_is_uncertain(self) -> None:
        with (
            patch("automation.flows.document_approval_flow.time.monotonic", side_effect=[0.0, 1.0, 9.0, 10.0, 26.0]),
            patch.object(self.flow, "visible_feedback_message", return_value=""),
            patch.object(self.flow, "capture_approval_records", side_effect=RuntimeError("approval tab hidden")),
            patch.object(
                self.flow,
                "_inspect_submission_state",
                return_value={
                    "submitButtonVisible": False,
                    "taskTabVisible": False,
                    "approvalTabVisible": False,
                    "todoListVisible": True,
                    "documentDetailVisible": False,
                },
            ),
            patch.object(
                self.flow,
                "_probe_todo_document_presence",
                return_value={
                    "todoListVisible": True,
                    "documentStillInTodo": None,
                    "probeError": "todo_grid_snapshot_missing",
                },
            ),
        ):
            result = self.flow.wait_for_submission_confirmation(
                document_no="RA-TEST-001",
                expected_opinion="同意",
                approval_count_before=1,
                wait_timeout_ms=30_000,
            )

        self.assertEqual(result["status"], "submitted_pending_confirmation")
        self.assertEqual(result["confirmationType"], "submitted_pending_confirmation")

    def test_wait_for_submission_confirmation_raises_when_document_still_in_todo(self) -> None:
        with (
            patch("automation.flows.document_approval_flow.time.monotonic", side_effect=[0.0, 1.0, 9.0, 10.0, 26.0, 27.0]),
            patch.object(self.flow, "visible_feedback_message", return_value=""),
            patch.object(self.flow, "capture_approval_records", side_effect=RuntimeError("approval tab hidden")),
            patch.object(
                self.flow,
                "_inspect_submission_state",
                return_value={
                    "submitButtonVisible": True,
                    "taskTabVisible": True,
                    "approvalTabVisible": True,
                    "todoListVisible": False,
                    "documentDetailVisible": True,
                },
            ),
            patch.object(
                self.flow,
                "_probe_todo_document_presence",
                side_effect=[
                    {
                        "todoListVisible": True,
                        "documentStillInTodo": True,
                        "probeError": "",
                    },
                    {
                        "todoListVisible": True,
                        "documentStillInTodo": True,
                        "probeError": "",
                    },
                    {
                        "todoListVisible": True,
                        "documentStillInTodo": True,
                        "probeError": "",
                    },
                ],
            ),
        ):
            with self.assertRaises(RuntimeError) as context:
                self.flow.wait_for_submission_confirmation(
                    document_no="RA-TEST-001",
                    expected_opinion="同意",
                    approval_count_before=1,
                    wait_timeout_ms=30_000,
                )

        self.assertIn("仍在当前账号待办中", str(context.exception))

    def test_probe_todo_document_presence_uses_existing_grid_without_trigger_click(self) -> None:
        grid_locator = MagicMock()
        grid_locator.count.return_value = 1
        grid_locator.is_visible.return_value = True
        self.page.locator.return_value.first = grid_locator

        self.flow.collector._wait_for_todo_list_ready = MagicMock()
        self.flow.collector._extract_best_grid = MagicMock(
            return_value={"selector": "#gridview", "headers": ["单据", "单据编号"]},
        )
        self.flow.collector._set_grid_vertical_position = MagicMock()
        self.flow.collector._focus_todo_row = MagicMock(return_value=False)
        self.flow.collector._get_grid_virtual_snapshot = MagicMock(
            return_value={
                "scrollHeight": 1000,
                "clientHeight": 500,
                "scrollTop": 500,
            },
        )

        result = self.flow._probe_todo_document_presence("RA-TEST-001", timeout_ms=500)

        self.flow.collector._wait_for_todo_list_ready.assert_called_once_with()
        self.assertEqual(result["todoListVisible"], True)
        self.assertEqual(result["documentStillInTodo"], False)


if __name__ == "__main__":
    unittest.main()
