from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from automation.flows.active_roster_flow import ActiveRosterFlow


class ActiveRosterFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.logger = MagicMock()
        self.flow = ActiveRosterFlow(
            page=self.page,
            logger=self.logger,
            timeout_ms=2000,
            home_url="https://example.com",
        )
        hidden_locator = MagicMock()
        hidden_locator.count.return_value = 0
        self.page.locator.return_value.first = hidden_locator

    def test_click_background_export_button_falls_back_to_partial_text_match(self) -> None:
        with patch.object(
            self.flow,
            "_try_click_text",
            side_effect=[False, True],
        ) as try_click_text:
            clicked = self.flow._click_background_export_button()

        self.assertTrue(clicked)
        self.assertEqual(
            [call.kwargs for call in try_click_text.call_args_list],
            [
                {
                    "text": "转后台执行",
                    "exact": True,
                    "force": True,
                    "scope": "#dialogShow",
                },
                {
                    "text": "转后台执行",
                    "exact": False,
                    "force": True,
                    "scope": "#dialogShow",
                },
            ],
        )
        self.logger.info.assert_called_with(
            "Clicked background export button: %s%s",
            "转后台执行",
            " (partial match)",
        )

    def test_click_background_export_button_falls_back_to_dom_evaluation(self) -> None:
        self.page.evaluate.return_value = "转后台执行 50"

        with patch.object(self.flow, "_try_click_text", return_value=False):
            clicked = self.flow._click_background_export_button()

        self.assertTrue(clicked)
        self.logger.info.assert_called_with(
            "Clicked background export button by DOM evaluation: %s",
            "转后台执行 50",
        )

    def test_click_background_export_button_retries_until_dom_evaluation_succeeds(self) -> None:
        self.page.evaluate.side_effect = ["", "", "转后台执行 49"]

        with patch.object(self.flow, "_try_click_text", return_value=False):
            clicked = self.flow._click_background_export_button()

        self.assertTrue(clicked)
        self.assertEqual(self.page.wait_for_timeout.call_count, 2)
