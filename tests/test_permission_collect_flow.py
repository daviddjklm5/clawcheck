from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from automation.flows.permission_collect_flow import PermissionCollectFlow


class PermissionCollectFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.logger = MagicMock()
        self.flow = PermissionCollectFlow(
            page=self.page,
            logger=self.logger,
            timeout_ms=2000,
            home_url="https://example.com",
        )

    def test_set_grid_horizontal_position_targets_sticky_scroll(self) -> None:
        self.flow._set_grid_horizontal_position("#entryentity", 0.5)

        script, payload = self.page.evaluate.call_args.args
        self.assertIn("kd-sticky-scroll", script)
        self.assertEqual(payload, {"selector": "#entryentity", "ratio": 0.5})
        self.page.wait_for_timeout.assert_called_once_with(150)

    def test_detail_link_horizontal_ratios_start_from_middle(self) -> None:
        self.assertEqual(
            self.flow._detail_link_horizontal_ratios(),
            (None, 0.5, 0.0, 0.75, 0.25, 1.0),
        )

    def test_focus_detail_row_passes_line_no_and_row_index(self) -> None:
        self.page.evaluate.return_value = True

        matched = self.flow._focus_detail_row("#entryentity", 3, "14")

        self.assertTrue(matched)
        script, payload = self.page.evaluate.call_args.args
        self.assertIn('data-clawcheck-target-row', script)
        self.assertEqual(
            payload,
            {
                "selector": "#entryentity",
                "rowIndex": 3,
                "lineNo": "14",
            },
        )

    def test_wait_for_detail_link_ready_uses_marked_target_row(self) -> None:
        row_collection = MagicMock()
        row_locator = MagicMock()
        row_collection.first = row_locator

        cell_link = MagicMock()
        cell_link.count.return_value = 1
        row_locator.locator.return_value.filter.return_value.first = cell_link

        self.page.locator.return_value = row_collection

        with (
            patch.object(self.flow, "_focus_detail_row", return_value=True),
            patch.object(self.flow, "_set_grid_horizontal_position"),
        ):
            result = self.flow._wait_for_detail_link_ready(
                document_no="RA-20260311-00019907",
                grid_selector="#entryentity",
                row_idx=0,
                detail_row={"line_no": "1"},
            )

        self.assertIs(result, cell_link)
        self.page.locator.assert_called_once_with(
            '#entryentity tbody tr[data-clawcheck-target-row="true"]'
        )
        row_locator.wait_for.assert_called_once_with(state="visible", timeout=1000)

    def test_wait_for_detail_link_ready_scans_middle_before_other_positions(self) -> None:
        row_collection = MagicMock()
        row_locator = MagicMock()
        row_collection.first = row_locator

        cell_link = MagicMock()
        cell_link.count.side_effect = [0, 0, 1]
        row_locator.locator.return_value.filter.return_value.first = cell_link

        self.page.locator.return_value = row_collection

        with (
            patch.object(self.flow, "_focus_detail_row", return_value=True),
            patch.object(self.flow, "_set_grid_horizontal_position") as set_position,
        ):
            result = self.flow._wait_for_detail_link_ready(
                document_no="RA-20260313-00019984",
                grid_selector="#entryentity",
                row_idx=0,
                detail_row={"line_no": "1"},
            )

        self.assertIs(result, cell_link)
        self.assertEqual(
            [call.args for call in set_position.call_args_list],
            [
                ("#entryentity", 0.5),
                ("#entryentity", 0.0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
