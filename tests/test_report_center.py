from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from automation.api.report_center import (
    _TARGET_HR_SUBDOMAINS,
    _fetch_snapshot_rows,
    build_service_station_flow_report_result,
    open_report_output_folder,
    resolve_service_station_flow_export_path,
)


class ReportCenterHelpersTest(unittest.TestCase):
    def test_resolve_service_station_flow_export_path_uses_default_report_exports_dir(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runtime_settings = SimpleNamespace(
                runtime=SimpleNamespace(logs_dir=tmpdir),
            )
            with patch("automation.api.report_center._load_runtime_settings", return_value=(Path("settings.yaml"), runtime_settings)):
                output_path, default_dir = resolve_service_station_flow_export_path(
                    start_date=date(2025, 12, 31),
                    end_date=date(2026, 3, 30),
                    save_as_path="",
                )

        self.assertEqual(default_dir, Path(tmpdir).resolve() / "report_exports")
        self.assertEqual(output_path.parent, default_dir)
        self.assertTrue(output_path.name.endswith(".xlsx"))

    def test_resolve_service_station_flow_export_path_supports_repo_relative_directory(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runtime_settings = SimpleNamespace(
                runtime=SimpleNamespace(logs_dir=tmpdir),
            )
            with patch("automation.api.report_center._load_runtime_settings", return_value=(Path("settings.yaml"), runtime_settings)):
                output_path, _ = resolve_service_station_flow_export_path(
                    start_date=date(2025, 12, 31),
                    end_date=date(2026, 3, 30),
                    save_as_path="automation\\output\\service_station_reports",
                )

        self.assertTrue(str(output_path).endswith(".xlsx"))
        self.assertIn(str(Path("automation") / "output" / "service_station_reports"), str(output_path))

    def test_resolve_service_station_flow_export_path_rejects_non_xlsx_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            runtime_settings = SimpleNamespace(
                runtime=SimpleNamespace(logs_dir=tmpdir),
            )
            with patch("automation.api.report_center._load_runtime_settings", return_value=(Path("settings.yaml"), runtime_settings)):
                with self.assertRaises(ValueError):
                    resolve_service_station_flow_export_path(
                        start_date=date(2025, 12, 31),
                        end_date=date(2026, 3, 30),
                        save_as_path="D:\\reports\\service_station_flow.csv",
                    )

    def test_open_report_output_folder_opens_parent_directory(self) -> None:
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "report.xlsx"
            file_path.write_text("demo", encoding="utf-8")
            with patch("automation.api.report_center.os.startfile", create=True) as mocked_startfile:
                result = open_report_output_folder(str(file_path))

        self.assertEqual(result["directory"], str(Path(tmpdir).resolve()))
        mocked_startfile.assert_called_once_with(str(Path(tmpdir).resolve()))

    def test_fetch_snapshot_rows_applies_excluded_department_ids_filter(self) -> None:
        captured: dict[str, object] = {}

        class FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute(self, sql, params):
                captured["sql"] = sql
                captured["params"] = params

            def fetchall(self):
                return []

        class FakeConnection:
            def __init__(self):
                self._cursor = FakeCursor()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def cursor(self):
                return self._cursor

        class FakeStore:
            table_name = '"人员属性查询历史"'

            def _quote_identifier(self, identifier: str) -> str:
                return f'"{identifier}"'

            def connect(self):
                return FakeConnection()

        result = _fetch_snapshot_rows(
            FakeStore(),
            effective_date=date(2026, 4, 13),
            target_only=True,
            excluded_department_ids=["55005710"],
        )

        self.assertEqual(result, [])
        self.assertIn('COALESCE("部门ID", \'\') <> ALL(%s)', str(captured["sql"]))
        self.assertEqual(captured["params"], [date(2026, 4, 13), list(_TARGET_HR_SUBDOMAINS), ["55005710"]])

    def test_build_service_station_flow_report_result_forwards_excluded_department_ids(self) -> None:
        runtime_settings = SimpleNamespace(
            db=SimpleNamespace(),
        )
        store = MagicMock()
        mocked_report = {"summary": {"startTargetCount": 1}}

        with patch("automation.api.report_center._load_runtime_settings", return_value=(Path("settings.yaml"), runtime_settings)):
            with patch("automation.api.report_center.PostgresPersonAttributesHistoryStore", return_value=store):
                with patch(
                    "automation.api.report_center._fetch_available_snapshot_dates",
                    return_value=[date(2025, 12, 31), date(2026, 3, 30)],
                ):
                    with patch(
                        "automation.api.report_center._fetch_snapshot_rows",
                        side_effect=[
                            [{"employee_no": "1001"}],
                            [{"employee_no": "1001"}],
                            [{"employee_no": "1001", "department_id": "D-1"}],
                            [{"employee_no": "1001", "department_id": "D-1"}],
                        ],
                    ) as mocked_fetch_rows:
                        with patch(
                            "automation.api.report_center.build_service_station_flow_report",
                            return_value=mocked_report,
                        ) as mocked_build_report:
                            result = build_service_station_flow_report_result(
                                start_date=date(2025, 12, 31),
                                end_date=date(2026, 3, 30),
                            )

        self.assertEqual(result, mocked_report)
        self.assertEqual(mocked_fetch_rows.call_count, 4)
        for call in mocked_fetch_rows.call_args_list:
            self.assertEqual(call.kwargs["excluded_department_ids"], ["55005710"])
        mocked_build_report.assert_called_once()


if __name__ == "__main__":
    unittest.main()
