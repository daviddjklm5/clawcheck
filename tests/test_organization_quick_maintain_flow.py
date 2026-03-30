from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from automation.flows.organization_quick_maintain_flow import OrganizationQuickMaintainFlow


class OrganizationQuickMaintainFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.logger = MagicMock()
        self.flow = OrganizationQuickMaintainFlow(
            page=self.page,
            logger=self.logger,
            timeout_ms=2000,
            home_url="https://example.com",
        )

    def test_click_background_button_falls_back_to_partial_text_match(self) -> None:
        side_effect = [False, False, True]
        with patch.object(self.flow, "_try_click_text", side_effect=side_effect) as try_click_text:
            clicked = self.flow._click_background_button()

        self.assertTrue(clicked)
        self.assertEqual(
            [(call.args, call.kwargs) for call in try_click_text.call_args_list],
            [
                (
                    ("转入后台",),
                    {
                        "exact": True,
                        "force": True,
                        "scope": "#dialogShow",
                    },
                ),
                (
                    ("转入后台",),
                    {
                        "exact": False,
                        "force": True,
                        "scope": "#dialogShow",
                    },
                ),
                (
                    ("转后台执行",),
                    {
                        "exact": True,
                        "force": True,
                        "scope": "#dialogShow",
                    },
                ),
            ],
        )

    def test_click_background_button_falls_back_to_dom_evaluation(self) -> None:
        self.page.evaluate.return_value = "转后台执行 50"

        with patch.object(self.flow, "_try_click_text", return_value=False):
            clicked = self.flow._click_background_button()

        self.assertTrue(clicked)

    def test_click_background_button_retries_until_dom_evaluation_succeeds(self) -> None:
        self.page.evaluate.side_effect = ["", "", "转后台执行 49"]

        with patch.object(self.flow, "_try_click_text", return_value=False):
            clicked = self.flow._click_background_button()

        self.assertTrue(clicked)
        self.assertEqual(self.page.wait_for_timeout.call_count, 2)
