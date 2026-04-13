from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from automation.api.report_center import (
    _TARGET_HR_SUBDOMAINS,
    open_report_output_folder,
    resolve_service_station_flow_export_path,
)
from automation.db.postgres import (
    APPLICANT_HR_SUBDOMAIN_STATION_HR_OPS,
    APPLICANT_HR_SUBDOMAIN_STATION_RECRUITING,
)


class ReportCenterHelpersTest(unittest.TestCase):
    def test_service_station_flow_targets_match_person_attribute_subdomain_constants(self) -> None:
        self.assertEqual(
            _TARGET_HR_SUBDOMAINS,
            (
                APPLICANT_HR_SUBDOMAIN_STATION_HR_OPS,
                APPLICANT_HR_SUBDOMAIN_STATION_RECRUITING,
            ),
        )

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


if __name__ == "__main__":
    unittest.main()
