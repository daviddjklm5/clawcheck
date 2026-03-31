from __future__ import annotations

from datetime import date
from pathlib import Path
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
        self.page.locator.return_value.last = hidden_locator

    def test_click_background_export_button_falls_back_to_partial_text_match(self) -> None:
        with patch.object(
            self.flow,
            "_try_click_text",
            side_effect=[False, True],
        ) as try_click_text:
            clicked = self.flow._click_background_export_button()

        self.assertTrue(clicked)
        self.assertEqual(
            [(call.args, call.kwargs) for call in try_click_text.call_args_list],
            [
                (
                    ("转后台执行",),
                    {
                        "exact": True,
                        "force": True,
                        "scope": "#dialogShow",
                    },
                ),
                (
                    ("转后台执行",),
                    {
                        "exact": False,
                        "force": True,
                        "scope": "#dialogShow",
                    },
                ),
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

    def test_run_sets_query_date_before_query(self) -> None:
        with (
            patch.object(self.flow, "open_roster_page"),
            patch.object(self.flow, "set_query_date") as set_query_date_mock,
            patch.object(self.flow, "select_report_scheme"),
            patch.object(self.flow, "select_employment_type"),
            patch.object(
                self.flow,
                "query_report",
                return_value={"row_count": 12, "query_date": "2026-03-29"},
            ) as query_report_mock,
        ):
            result = self.flow.run(
                downloads_dir=Path("automation/downloads"),
                query_date="2026-03-29",
                report_scheme="scheme",
                employment_type="employment",
                query_timeout_sec=60,
                download_timeout_sec=120,
                skip_export=True,
            )

        set_query_date_mock.assert_called_once_with("2026-03-29")
        query_report_mock.assert_called_once_with(timeout_sec=60, expected_query_date="2026-03-29")
        self.assertEqual(result["requested_query_date"], "2026-03-29")

    def test_set_query_date_uses_calendar_navigation_and_confirm(self) -> None:
        input_locator = MagicMock()

        with (
            patch.object(self.flow, "_get_query_date_input_locator", return_value=input_locator),
            patch.object(
                self.flow,
                "_get_query_date_input_value",
                side_effect=["2026-03-30", "2026-03-29"],
            ),
            patch.object(self.flow, "_navigate_query_calendar_to_date") as navigate_mock,
        ):
            self.flow.set_query_date("2026-03-29")

        input_locator.click.assert_called_once_with(timeout=self.flow.timeout_ms)
        navigate_mock.assert_called_once_with(
            input_locator=input_locator,
            current_date=date(2026, 3, 30),
            target_date=date(2026, 3, 29),
        )
        input_locator.press.assert_called_once_with("Enter", timeout=self.flow.timeout_ms)

    def test_navigate_query_calendar_to_date_uses_month_then_day_keys(self) -> None:
        input_locator = MagicMock()

        with patch.object(
            self.flow,
            "_get_query_date_input_value",
            side_effect=[
                "2026-02-28",
                "2026-01-28",
                "2025-12-28",
                "2025-12-29",
                "2025-12-30",
                "2025-12-31",
            ],
        ):
            self.flow._navigate_query_calendar_to_date(
                input_locator=input_locator,
                current_date=date(2026, 3, 30),
                target_date=date(2025, 12, 31),
            )

        self.assertEqual(
            [call.args[0] for call in input_locator.press.call_args_list],
            ["PageUp", "PageUp", "PageUp", "ArrowRight", "ArrowRight", "ArrowRight"],
        )
