from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from automation.api.routers.reports import (
    OpenReportFolderRequest,
    ServiceStationFlowRequest,
    get_report_catalog,
    get_service_station_flow_report_options,
    post_open_report_folder,
    post_service_station_flow_report_export,
    post_service_station_flow_report_query,
)


class ReportsRouterTest(unittest.TestCase):
    def test_get_report_catalog_returns_payload(self) -> None:
        payload = {"modules": []}
        with patch("automation.api.routers.reports.get_report_center_catalog", return_value=payload):
            result = get_report_catalog()
        self.assertEqual(result, payload)

    def test_get_service_station_flow_report_options_returns_payload(self) -> None:
        payload = {"availableSnapshotDates": [], "canRun": False, "hint": "x"}
        with patch("automation.api.routers.reports.get_service_station_flow_options", return_value=payload):
            result = get_service_station_flow_report_options()
        self.assertEqual(result, payload)

    def test_post_service_station_flow_report_query_maps_value_error_to_400(self) -> None:
        request = ServiceStationFlowRequest(
            startDate=date(2025, 12, 31),
            endDate=date(2026, 3, 30),
            saveAsPath="",
        )
        with patch(
            "automation.api.routers.reports.build_service_station_flow_report_result",
            side_effect=ValueError("开始日期不存在"),
        ):
            with self.assertRaises(HTTPException) as context:
                post_service_station_flow_report_query(request)
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "开始日期不存在")

    def test_post_service_station_flow_report_export_forwards_payload(self) -> None:
        request = ServiceStationFlowRequest(
            startDate=date(2025, 12, 31),
            endDate=date(2026, 3, 30),
            saveAsPath="automation\\logs\\report_exports",
        )
        payload = {"summary": {}, "exportInfo": {}}
        with patch("automation.api.routers.reports.export_service_station_flow_report", return_value=payload) as mocked_export:
            result = post_service_station_flow_report_export(request)
        self.assertEqual(result, payload)
        mocked_export.assert_called_once_with(
            start_date=date(2025, 12, 31),
            end_date=date(2026, 3, 30),
            save_as_path="automation\\logs\\report_exports",
        )

    def test_post_open_report_folder_forwards_payload(self) -> None:
        request = OpenReportFolderRequest(path="C:\\reports\\service_station_flow.xlsx")
        payload = {"directory": "C:\\reports"}
        with patch("automation.api.routers.reports.open_report_output_folder", return_value=payload) as mocked_open:
            result = post_open_report_folder(request)
        self.assertEqual(result, payload)
        mocked_open.assert_called_once_with("C:\\reports\\service_station_flow.xlsx")


if __name__ == "__main__":
    unittest.main()
