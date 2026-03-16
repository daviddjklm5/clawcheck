from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import unittest
from unittest.mock import patch

from automation.db.postgres import PostgresRiskTrustStore
from automation.utils.config_loader import DatabaseSettings


class _FakeCursor:
    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


class ProcessWorkbenchLatestSnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = PostgresRiskTrustStore(
            DatabaseSettings(
                host="localhost",
                port=5432,
                dbname="clawcheck",
                user="tester",
                password="tester",
                schema="public",
                sslmode="disable",
            )
        )
        self.cursor = _FakeCursor()
        self.connection = _FakeConnection(self.cursor)

    @contextmanager
    def _fake_connect(self):
        yield self.connection

    def test_fetch_process_workbench_uses_latest_rows_per_document(self) -> None:
        latest_rows = [
            {
                "document_no": "RA-TEST-001",
                "applicant_name": "张三",
                "employee_no": "0001",
                "permission_target": "张三",
                "department_name": "人事部",
                "document_status": "已提交",
                "final_score": 1.0,
                "summary_conclusion": "人工干预",
                "suggested_action": "manual_review",
                "low_score_detail_count": 3,
                "assessed_at": datetime(2026, 3, 16, 12, 19, 15),
                "assessment_batch_no": "audit_20260316_121915",
                "assessment_version": "2026-03-15",
            },
            {
                "document_no": "RA-TEST-002",
                "applicant_name": "李四",
                "employee_no": "0002",
                "permission_target": "李四",
                "department_name": "运营部",
                "document_status": "已提交",
                "final_score": 0.0,
                "summary_conclusion": "拒绝",
                "suggested_action": "reject",
                "low_score_detail_count": 8,
                "assessed_at": datetime(2026, 3, 15, 11, 24, 28),
                "assessment_batch_no": "audit_20260315_112428",
                "assessment_version": "2026-03-15",
            },
        ]

        with (
            patch.object(self.store, "ensure_table"),
            patch.object(self.store, "connect", self._fake_connect),
            patch.object(self.store, "_fetch_latest_process_summary_rows", return_value=latest_rows) as mocked_fetch_latest,
            patch.object(
                self.store,
                "_fetch_latest_assessment_batch_no",
                side_effect=AssertionError("process workbench should not fall back to latest batch query"),
            ),
        ):
            result = self.store.fetch_process_workbench()

        mocked_fetch_latest.assert_called_once_with(self.cursor)
        self.assertEqual(result["stats"][0]["value"], "2")
        self.assertEqual(result["stats"][1]["value"], "1")
        self.assertEqual(result["stats"][2]["value"], "1")
        self.assertEqual(result["stats"][3]["value"], "audit_20260316_121915")
        self.assertEqual([row["documentNo"] for row in result["documents"]], ["RA-TEST-001", "RA-TEST-002"])

    def test_fetch_process_document_detail_defaults_to_latest_result_for_document(self) -> None:
        summary_row = {
            "document_no": "RA-TEST-001",
            "applicant_name": "张三",
            "employee_no": "0001",
            "permission_target": "张三",
            "document_status": "已提交",
            "department_name": "人事部",
            "apply_time": None,
            "applicant_identity_label": "属地 HR",
            "applicant_org_unit_name": "人力资源与行政服务中心",
            "latest_approval_time": datetime(2026, 3, 16, 10, 42, 2),
            "applicant_process_level_category": "属地服务站",
            "final_score": 1.0,
            "summary_conclusion": "人工干预",
            "suggested_action": "manual_review",
            "lowest_hit_dimension": "申请的权限",
            "low_score_detail_count": 379,
            "assessment_batch_no": "audit_20260316_121915",
            "assessment_version": "2026-03-15",
            "assessed_at": datetime(2026, 3, 16, 12, 19, 15),
            "assessment_explain": "",
        }

        with (
            patch.object(self.store, "ensure_table"),
            patch.object(self.store, "connect", self._fake_connect),
            patch.object(
                self.store,
                "_fetch_latest_process_summary_rows",
                return_value=[summary_row],
            ) as mocked_fetch_latest,
            patch.object(
                self.store,
                "_fetch_process_summary_rows",
                side_effect=AssertionError("document detail should default to latest per-document result"),
            ),
            patch.object(self.store, "_fetch_process_role_rows", return_value=[]),
            patch.object(self.store, "_fetch_approval_rows", return_value=[]),
            patch.object(self.store, "_fetch_process_org_scope_display_rows", return_value=[]),
            patch.object(self.store, "_fetch_process_low_score_rows", return_value=[]) as mocked_fetch_low_score,
            patch.object(self.store, "_fetch_process_feedback_group_rows", return_value=[]),
            patch(
                "automation.db.postgres.build_low_score_feedback",
                return_value={
                    "summaryConclusionLabel": "加强审核",
                    "feedbackStats": [],
                    "feedbackGroups": [],
                    "feedbackLines": [],
                },
            ),
        ):
            result = self.store.fetch_process_document_detail("RA-TEST-001")

        mocked_fetch_latest.assert_called_once_with(self.cursor, document_no="RA-TEST-001")
        mocked_fetch_low_score.assert_called_once_with(self.cursor, "audit_20260316_121915", ["RA-TEST-001"])
        batch_field = next(field for field in result["overviewFields"] if field["label"] == "评估批次号")
        self.assertEqual(result["documentNo"], "RA-TEST-001")
        self.assertEqual(batch_field["value"], "audit_20260316_121915")
        self.assertEqual(result["feedbackOverview"]["summaryConclusionLabel"], "加强审核")


if __name__ == "__main__":
    unittest.main()
