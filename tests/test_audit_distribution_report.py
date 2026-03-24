from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from automation.reporting import (
    build_approval_node_stats,
    build_audit_distribution_workbook_data,
    build_dimension_stats,
    build_document_feedback_rows,
    build_document_stats,
    build_rule_stats,
    export_audit_distribution_workbook,
    load_audit_distribution_workbook_data,
    render_audit_distribution_workbook,
)


class AuditDistributionReportTest(unittest.TestCase):
    def test_build_stats(self) -> None:
        summary_rows = [
            {
                "document_no": "RA-1",
                "final_score": 0.0,
                "summary_conclusion": "拒绝",
                "hit_manual_review": True,
                "has_low_score_details": True,
            },
            {
                "document_no": "RA-2",
                "final_score": 1.0,
                "summary_conclusion": "人工干预",
                "hit_manual_review": True,
                "has_low_score_details": False,
            },
        ]
        detail_rows = [
            {
                "document_no": "RA-1",
                "dimension_name": "审批人判断",
                "rule_id": "APPROVAL_LOCAL_WITHOUT_WARZONE_HISTORY",
                "rule_summary": "缺少战区人行部门审批",
                "score": 0.0,
                "is_low_score": True,
            },
            {
                "document_no": "RA-2",
                "dimension_name": "申请的权限",
                "rule_id": "PERMISSION_B1_HR_STAFF",
                "rule_summary": "B1 类涉薪权限需要人工关注",
                "score": 1.0,
                "is_low_score": True,
            },
            {
                "document_no": "RA-2",
                "dimension_name": "申请的组织",
                "rule_id": "TARGET_ORG_AUTH_LEVEL_MAP",
                "rule_summary": "按组织授权等级映射评分",
                "score": 2.0,
                "is_low_score": False,
            },
        ]
        approval_rows = [
            {"document_no": "RA-1", "node_name": "权限申请提交", "approval_action": "提交", "approver_employee_no": "001"},
            {"document_no": "RA-1", "node_name": "平台运营组对接人", "approval_action": "待审核", "approver_employee_no": "002"},
            {"document_no": "RA-2", "node_name": "部门负责人", "approval_action": "同意", "approver_employee_no": "003"},
        ]

        document_stats = build_document_stats(summary_rows)
        dimension_stats = build_dimension_stats(detail_rows)
        rule_stats = build_rule_stats(detail_rows)
        approval_stats = build_approval_node_stats(approval_rows, ["平台运营组对接人"])

        self.assertEqual(document_stats["document_count"], 2)
        self.assertEqual(document_stats["summary_conclusion_distribution"][0]["总结论"], "人工干预")
        self.assertEqual(len(dimension_stats), 3)
        self.assertEqual(rule_stats[0]["命中次数"], 1)
        platform_node = next(row for row in approval_stats if row["节点名称"] == "平台运营组对接人")
        self.assertEqual(platform_node["是否排除评分节点"], "是")

    def test_render_workbook(self) -> None:
        summary_rows = [
            {
                "document_no": "RA-1",
                "assessment_version": "2026-03-15",
                "final_score": 0.0,
                "summary_conclusion": "拒绝",
                "suggested_action": "reject",
                "lowest_hit_dimension": "审批人判断",
                "lowest_hit_role_code": None,
                "lowest_hit_org_code": None,
                "hit_manual_review": True,
                "has_low_score_details": True,
                "low_score_detail_count": 1,
                "low_score_detail_conclusion": "缺少战区人行部门审批",
            }
        ]
        detail_rows = [
            {
                "document_no": "RA-1",
                "role_code": None,
                "org_code": None,
                "dimension_name": "审批人判断",
                "rule_id": "APPROVAL_LOCAL_WITHOUT_WARZONE_HISTORY",
                "rule_summary": "缺少战区人行部门审批",
                "score": 0.0,
                "detail_conclusion": "缺少战区人行部门审批，建议拒绝或补齐审批链",
                "is_low_score": True,
                "intervention_action": "补齐战区人行部门审批后复核",
            }
        ]
        approval_rows = [
            {"document_no": "RA-1", "node_name": "权限申请提交", "approval_action": "提交", "approver_employee_no": "001"}
        ]

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "audit_distribution.xlsx"
            render_audit_distribution_workbook(
                batch_no="audit_test",
                assessment_version="2026-03-15",
                summary_rows=summary_rows,
                detail_rows=detail_rows,
                approval_rows=approval_rows,
                ignored_node_names=["平台运营组对接人"],
                output_path=output_path,
            )

            self.assertTrue(output_path.exists())

    def test_build_document_feedback_rows(self) -> None:
        summary_rows = [
            {
                "document_no": "RA-1",
                "assessment_version": "2026-03-15",
                "summary_conclusion": "人工干预",
            }
        ]
        feedback_overviews = {
            "RA-1": {
                "summaryConclusionLabel": "加强审核",
                "feedbackStats": [
                    {"label": "风险类型数", "value": "2"},
                    {"label": "影响组织单位数", "value": "3"},
                ],
                "feedbackGroups": [
                    {"summary": "风险一"},
                    {"summary": "风险二"},
                ],
            }
        }

        rows = build_document_feedback_rows(summary_rows, feedback_overviews)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["document_no"], "RA-1")
        self.assertEqual(rows[0]["summary_conclusion_label"], "加强审核")
        self.assertEqual(rows[0]["risk_type_count"], "2")
        self.assertEqual(rows[0]["feedback_summary"], "风险一\n风险二")

    def test_build_audit_distribution_workbook_data(self) -> None:
        workbook_data = build_audit_distribution_workbook_data(
            batch_no="audit_test",
            ignored_node_names=["平台运营组对接人"],
            summary_rows=[
                {
                    "document_no": "RA-1",
                    "assessment_version": "2026-03-15",
                    "summary_conclusion": "人工干预",
                }
            ],
            detail_rows=[],
            approval_rows=[],
            feedback_overviews={
                "RA-1": {
                    "summaryConclusionLabel": "加强审核",
                    "feedbackStats": [],
                    "feedbackGroups": [],
                }
            },
        )

        self.assertEqual(workbook_data.batch_no, "audit_test")
        self.assertEqual(workbook_data.assessment_version, "2026-03-15")
        self.assertEqual(workbook_data.summary_rows[0]["summary_conclusion_label"], "加强审核")
        self.assertEqual(workbook_data.ignored_node_names, ["平台运营组对接人"])

    def test_load_and_export_workbook_from_store(self) -> None:
        summary_result = [
            (
                "RA-1",
                "2026-03-15",
                0.0,
                "人工干预",
                "review",
                "审批人判断",
                None,
                None,
                True,
                True,
                1,
                "缺少战区人行部门审批",
            )
        ]
        detail_result = [
            (
                "RA-1",
                None,
                None,
                "审批人判断",
                "APPROVAL_LOCAL_WITHOUT_WARZONE_HISTORY",
                "缺少战区人行部门审批",
                0.0,
                "缺少战区人行部门审批，建议拒绝或补齐审批链",
                True,
                "补齐战区人行部门审批后复核",
            )
        ]
        approval_result = [
            ("RA-1", "权限申请提交", "提交", "001"),
        ]

        class FakeCursor:
            def __init__(self) -> None:
                self._step = 0

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def execute(self, query, params=None) -> None:
                self._last_query = query
                self._last_params = params

            def fetchone(self):
                return ("audit_batch_1",)

            def fetchall(self):
                self._step += 1
                if self._step == 1:
                    return summary_result
                if self._step == 2:
                    return detail_result
                if self._step == 3:
                    return approval_result
                return []

        class FakeConnection:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb) -> None:
                return None

            def cursor(self):
                return FakeCursor()

        class FakeStore:
            def connect(self):
                return FakeConnection()

            def fetch_document_feedback_overviews(self, *, assessment_batch_no, document_nos):
                self.assessment_batch_no = assessment_batch_no
                self.document_nos = list(document_nos)
                return {
                    "RA-1": {
                        "summaryConclusionLabel": "加强审核",
                        "feedbackStats": [{"label": "风险类型数", "value": "1"}],
                        "feedbackGroups": [{"summary": "审批链风险"}],
                    }
                }

        store = FakeStore()
        workbook_data = load_audit_distribution_workbook_data(
            store=store,
            batch_no="",
            ignored_node_names=["平台运营组对接人"],
        )

        self.assertEqual(workbook_data.batch_no, "audit_batch_1")
        self.assertEqual(store.assessment_batch_no, "audit_batch_1")
        self.assertEqual(store.document_nos, ["RA-1"])
        self.assertEqual(workbook_data.document_feedback_rows[0]["feedback_summary"], "审批链风险")

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "audit_distribution.xlsx"
            exported_data = export_audit_distribution_workbook(
                store=store,
                batch_no="",
                ignored_node_names=["平台运营组对接人"],
                output_path=output_path,
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(exported_data.batch_no, "audit_batch_1")


if __name__ == "__main__":
    unittest.main()
