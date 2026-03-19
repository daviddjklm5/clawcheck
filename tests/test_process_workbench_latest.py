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
                "todo_process_status": "待处理",
                "todo_status_updated_at": datetime(2026, 3, 16, 12, 30, 0),
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
                "todo_process_status": "已处理",
                "todo_status_updated_at": datetime(2026, 3, 16, 12, 31, 0),
                "final_score": 0.0,
                "summary_conclusion": "拒绝",
                "suggested_action": "reject",
                "low_score_detail_count": 8,
                "assessed_at": datetime(2026, 3, 15, 11, 24, 28),
                "assessment_batch_no": "audit_20260315_112428",
                "assessment_version": "2026-03-15",
            },
        ]
        person_attributes = {
            "0001": {
                "employee_no": "0001",
                "department_id": "ORG-001",
                "position_name": "人力资源经理",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_万物梁行_华东区域公司_人力资源与行政服务中心",
            },
            "0002": {
                "employee_no": "0002",
                "department_id": "ORG-002",
                "position_name": "招商主管",
                "level1_function_name": "招商管理",
                "org_path_name": "万物云_万物梁行_华南区域公司_招商主管理部",
            },
        }
        org_attributes = {
            "ORG-001": {
                "org_unit_name": "人力资源与行政服务中心",
                "war_zone": "华东战区",
                "process_level_category": "业务单元本部",
            },
            "ORG-002": {
                "org_unit_name": "万物梁行",
                "war_zone": "华南战区",
                "process_level_category": "属地组织",
            },
        }

        with (
            patch.object(self.store, "ensure_table"),
            patch.object(self.store, "connect", self._fake_connect),
            patch.object(self.store, "_fetch_latest_process_summary_rows", return_value=latest_rows) as mocked_fetch_latest,
            patch.object(self.store, "_fetch_person_attributes_map", return_value=person_attributes),
            patch.object(self.store, "_fetch_org_attributes_map", return_value=org_attributes),
            patch.object(
                self.store,
                "_fetch_latest_assessment_batch_no",
                side_effect=AssertionError("process workbench should not fall back to latest batch query"),
            ),
        ):
            result = self.store.fetch_process_workbench()

        mocked_fetch_latest.assert_called_once_with(self.cursor)
        self.assertEqual(result["stats"][0]["value"], "1")
        self.assertEqual(result["stats"][1]["value"], "1")
        self.assertEqual(result["stats"][2]["value"], "1")
        self.assertEqual(result["stats"][3]["value"], "1")
        self.assertEqual(result["stats"][4]["value"], "audit_20260316_121915")
        self.assertEqual([row["documentNo"] for row in result["documents"]], ["RA-TEST-001", "RA-TEST-002"])
        self.assertEqual(result["documents"][0]["todoProcessStatus"], "待处理")
        self.assertEqual(result["documents"][1]["todoProcessStatus"], "已处理")
        self.assertEqual(result["documents"][0]["orgUnitName"], "人力资源与行政服务中心")
        self.assertEqual(result["documents"][0]["warZone"], "华东战区")
        self.assertEqual(result["documents"][0]["processLevelCategory"], "业务单元本部")
        self.assertEqual(result["documents"][0]["positionName"], "人力资源经理")
        self.assertEqual(result["documents"][0]["level1FunctionName"], "人力资源")
        self.assertEqual(
            result["documents"][0]["orgPathName"],
            "万物云_万物梁行_华东区域公司_人力资源与行政服务中心",
        )

    def test_fetch_process_document_detail_defaults_to_latest_result_for_document(self) -> None:
        summary_row = {
            "document_no": "RA-TEST-001",
            "applicant_name": "张三",
            "employee_no": "0001",
            "permission_target": "张三",
            "apply_reason": "测试申请原因",
            "document_status": "已提交",
            "todo_process_status": "已处理",
            "todo_status_updated_at": datetime(2026, 3, 16, 12, 31, 0),
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
            patch.object(self.store, "_fetch_person_attributes_map", return_value={}),
            patch.object(self.store, "_fetch_org_attributes_map", return_value={}),
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
        todo_field = next(field for field in result["overviewFields"] if field["label"] == "待办处理状态")
        self.assertEqual(result["documentNo"], "RA-TEST-001")
        self.assertEqual(batch_field["value"], "audit_20260316_121915")
        self.assertEqual(todo_field["value"], "已处理")
        self.assertEqual(result["feedbackOverview"]["summaryConclusionLabel"], "加强审核")
        self.assertEqual(result["approvals"], [])

    def test_fetch_process_document_detail_sorts_roles_by_permission_level_priority(self) -> None:
        summary_row = {
            "document_no": "RA-TEST-001",
            "applicant_name": "张三",
            "employee_no": "0001",
            "permission_target": "张三",
            "apply_reason": "测试申请原因",
            "document_status": "已提交",
            "todo_process_status": "待处理",
            "todo_status_updated_at": datetime(2026, 3, 16, 12, 31, 0),
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
            "low_score_detail_count": 3,
            "assessment_batch_no": "audit_20260316_121915",
            "assessment_version": "2026-03-15",
            "assessed_at": datetime(2026, 3, 16, 12, 19, 15),
            "assessment_explain": "",
        }
        role_rows = [
            {
                "id": "r5",
                "line_no": "5",
                "role_code": "ROLE-C",
                "role_name": "C 类角色",
                "apply_type": "新增",
                "org_scope_count": 1,
                "skip_org_scope_check": False,
                "permission_level": "C类-常规",
            },
            {
                "id": "r3",
                "line_no": "3",
                "role_code": "ROLE-S2",
                "role_name": "S2 类角色",
                "apply_type": "新增",
                "org_scope_count": 1,
                "skip_org_scope_check": False,
                "permission_level": "S2类-限定",
            },
            {
                "id": "r1",
                "line_no": "1",
                "role_code": "ROLE-A",
                "role_name": "A 类角色",
                "apply_type": "新增",
                "org_scope_count": 1,
                "skip_org_scope_check": False,
                "permission_level": "A类-远程",
            },
            {
                "id": "r7",
                "line_no": "7",
                "role_code": "ROLE-UNKNOWN",
                "role_name": "未知级别角色",
                "apply_type": "新增",
                "org_scope_count": 1,
                "skip_org_scope_check": False,
                "permission_level": "",
            },
            {
                "id": "r2",
                "line_no": "2",
                "role_code": "ROLE-S1",
                "role_name": "S1 类角色",
                "apply_type": "新增",
                "org_scope_count": 1,
                "skip_org_scope_check": False,
                "permission_level": "S1类-限定",
            },
            {
                "id": "r4",
                "line_no": "4",
                "role_code": "ROLE-W",
                "role_name": "W 类角色",
                "apply_type": "新增",
                "org_scope_count": 1,
                "skip_org_scope_check": False,
                "permission_level": "W类-取消",
            },
            {
                "id": "r6",
                "line_no": "6",
                "role_code": "ROLE-B1",
                "role_name": "B1 类角色",
                "apply_type": "新增",
                "org_scope_count": 1,
                "skip_org_scope_check": False,
                "permission_level": "B1类-涉薪",
            },
            {
                "id": "r8",
                "line_no": "8",
                "role_code": "ROLE-B2",
                "role_name": "B2 类角色",
                "apply_type": "新增",
                "org_scope_count": 1,
                "skip_org_scope_check": False,
                "permission_level": "B2类-涉档案绩效",
            },
        ]

        with (
            patch.object(self.store, "ensure_table"),
            patch.object(self.store, "connect", self._fake_connect),
            patch.object(self.store, "_fetch_latest_process_summary_rows", return_value=[summary_row]),
            patch.object(self.store, "_fetch_process_role_rows", return_value=role_rows),
            patch.object(self.store, "_fetch_approval_rows", return_value=[]),
            patch.object(self.store, "_fetch_person_attributes_map", return_value={}),
            patch.object(self.store, "_fetch_org_attributes_map", return_value={}),
            patch.object(self.store, "_fetch_process_org_scope_display_rows", return_value=[]),
            patch.object(self.store, "_fetch_process_low_score_rows", return_value=[]),
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

        self.assertEqual(
            [row["permissionLevel"] for row in result["roles"]],
            [
                "S1类-限定",
                "S2类-限定",
                "A类-远程",
                "W类-取消",
                "B1类-涉薪",
                "B2类-涉档案绩效",
                "C类-常规",
                "-",
            ],
        )

    def test_fetch_process_document_detail_enriches_approval_rows_with_person_and_org_attributes(self) -> None:
        summary_row = {
            "document_no": "RA-TEST-001",
            "applicant_name": "张三",
            "employee_no": "0001",
            "permission_target": "张三",
            "apply_reason": "测试申请原因",
            "document_status": "已提交",
            "todo_process_status": "待处理",
            "todo_status_updated_at": datetime(2026, 3, 16, 12, 31, 0),
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
            "low_score_detail_count": 2,
            "assessment_batch_no": "audit_20260316_121915",
            "assessment_version": "2026-03-15",
            "assessed_at": datetime(2026, 3, 16, 12, 19, 15),
            "assessment_explain": "",
        }
        approval_rows = [
            {
                "document_no": "RA-TEST-001",
                "record_seq": 1,
                "node_name": "部门负责人",
                "approver_name": "李四",
                "approver_employee_no": "0099",
                "approval_action": "同意",
                "approval_opinion": "同意申请",
                "approval_time": datetime(2026, 3, 16, 10, 42, 2),
            }
        ]
        person_attributes = {
            "0099": {
                "employee_no": "0099",
                "employee_name": "李四",
                "department_id": "ORG-001",
                "position_name": "战区人力负责人",
                "org_path_name": "万物云_万物梁行_华东区域公司_人力资源与行政服务中心",
            }
        }
        org_attributes = {
            "ORG-001": {
                "org_unit_name": "人力资源与行政服务中心",
                "war_zone": "华东战区",
                "process_level_category": "业务单元本部",
            }
        }

        with (
            patch.object(self.store, "ensure_table"),
            patch.object(self.store, "connect", self._fake_connect),
            patch.object(self.store, "_fetch_latest_process_summary_rows", return_value=[summary_row]),
            patch.object(self.store, "_fetch_process_role_rows", return_value=[]),
            patch.object(self.store, "_fetch_approval_rows", return_value=approval_rows),
            patch.object(self.store, "_fetch_person_attributes_map", return_value=person_attributes),
            patch.object(self.store, "_fetch_org_attributes_map", return_value=org_attributes),
            patch.object(self.store, "_fetch_process_org_scope_display_rows", return_value=[]),
            patch.object(self.store, "_fetch_process_low_score_rows", return_value=[]),
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

        self.assertEqual(
            result["approvals"],
            [
                {
                    "id": "RA-TEST-001:1",
                    "nodeName": "部门负责人",
                    "approver": "李四",
                    "action": "同意",
                    "finishedAt": "2026-03-16 10:42:02",
                    "comment": "同意申请",
                    "positionName": "战区人力负责人",
                    "orgUnitName": "人力资源与行政服务中心",
                    "warZone": "华东战区",
                    "processLevelCategory": "业务单元本部",
                    "orgPathName": "万物云_万物梁行_华东区域公司_人力资源与行政服务中心",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
