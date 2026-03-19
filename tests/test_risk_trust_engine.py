from __future__ import annotations

from pathlib import Path
import unittest

from automation.rules import RiskTrustEvaluator, load_risk_trust_package


class RiskTrustEvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        package = load_risk_trust_package(repo_root / "automation" / "config" / "rules")
        self.evaluator = RiskTrustEvaluator(package)

    def test_permission_catalog_missing_causes_manual_review(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-1", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "人事远程交付中心", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-15 10:00:00",
                    "approver_org_attributes": {"process_level_category": "人事远程交付中心"},
                },
                {
                    "node_name": "部门负责人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-15 11:00:00",
                    "approver_org_attributes": {"process_level_category": "万物云本部"},
                }
            ],
            "permission_details": [
                {
                    "document_no": "RA-1",
                    "role_code": "UNKNOWN",
                    "role_name": "未知权限",
                    "catalog_matched": False,
                    "permission_level": None,
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": None, "org_auth_level": None, "org_unit_name": None}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_1")

        self.assertEqual(summary_rows[0]["summary_conclusion"], "人工干预")
        self.assertEqual(summary_rows[0]["suggested_action"], "manual_review")
        self.assertEqual(summary_rows[0]["final_score"], 0.5)

        permission_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的权限")
        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(permission_detail["rule_id"], "PERMISSION_CATALOG_MISSING")
        self.assertEqual(permission_detail["score"], 0.5)
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_SCOPE_SKIPPED")
        self.assertEqual(target_org_detail["score"], 2.5)

    def test_platform_ops_node_is_excluded_from_approval_chain(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-2", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "HX"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-15 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "平台运营组对接人",
                    "approver_employee_no": "009",
                    "approval_action": "同意",
                    "approval_time": "2026-03-15 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
                {
                    "node_name": "部门负责人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-15 12:00:00",
                    "approver_org_attributes": {"process_level_category": "万物云本部"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-2",
                    "role_code": "C001",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": None, "org_auth_level": None, "org_unit_name": None}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_2")

        self.assertEqual(summary_rows[0]["summary_conclusion"], "拒绝")
        approval_detail = next(row for row in detail_rows if row["dimension_name"] == "审批人判断")
        self.assertEqual(approval_detail["rule_id"], "APPROVAL_LOCAL_WITHOUT_WARZONE_HISTORY")
        self.assertEqual(approval_detail["score"], 0.0)

    def test_low_score_details_are_aggregated(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-3", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "HX"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-15 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                }
            ],
            "permission_details": [
                {
                    "document_no": "RA-3",
                    "role_code": "B100",
                    "role_name": "涉薪权限",
                    "catalog_matched": True,
                    "permission_level": "B1类-涉薪",
                    "skip_org_scope_check": False,
                    "targets": [{"org_code": "ORG1", "org_auth_level": "一级授权", "org_unit_name": "组织B"}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_3")

        self.assertTrue(summary_rows[0]["has_low_score_details"])
        self.assertGreaterEqual(summary_rows[0]["low_score_detail_count"], 3)
        self.assertIn("维度=", summary_rows[0]["low_score_detail_conclusion"])
        low_score_details = [row for row in detail_rows if row["is_low_score"]]
        self.assertTrue(low_score_details)

    def test_warzone_node_name_without_warzone_org_does_not_count(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-4", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-15 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-15 11:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-4",
                    "role_code": "C001",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": None, "org_auth_level": None, "org_unit_name": None}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_4")

        approval_detail = next(row for row in detail_rows if row["dimension_name"] == "审批人判断")
        self.assertEqual(approval_detail["rule_id"], "APPROVAL_LOCAL_WITHOUT_WARZONE_HISTORY")
        self.assertEqual(approval_detail["score"], 0.0)
        self.assertEqual(summary_rows[0]["final_score"], 0.0)

    def test_hr_b1_permission_does_not_fall_into_non_hr_rule(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-5", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-15 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-15 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-5",
                    "role_code": "B100",
                    "role_name": "涉薪权限",
                    "catalog_matched": True,
                    "permission_level": "B1类-涉薪",
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": None, "org_auth_level": None, "org_unit_name": None}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_5")

        permission_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的权限")
        self.assertEqual(permission_detail["rule_id"], "PERMISSION_B1_HR_STAFF")
        self.assertEqual(permission_detail["score"], 1.0)
        self.assertEqual(summary_rows[0]["final_score"], 1.0)

    def test_cancel_role_apply_type_uses_revoke_permission_rule(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-7", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "人事远程交付中心", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-15 10:00:00",
                    "approver_org_attributes": {"process_level_category": "人事远程交付中心"},
                },
                {
                    "node_name": "部门负责人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-15 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-7",
                    "role_code": "B100",
                    "role_name": "涉薪权限",
                    "apply_type": "取消角色",
                    "catalog_matched": True,
                    "permission_level": "B1类-涉薪",
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": None, "org_auth_level": None, "org_unit_name": None}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_7")

        permission_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的权限")
        self.assertEqual(permission_detail["rule_id"], "PERMISSION_CANCEL_ROLE")
        self.assertEqual(permission_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)
        self.assertEqual(summary_rows[0]["summary_conclusion"], "可信任")

    def test_cancel_role_non_hr_skips_non_hr_and_warzone_checks(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-8", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "HX"},
            "applicant_org_attributes": {"process_level_category": "人事远程交付中心", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-15 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "部门负责人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-15 11:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-8",
                    "role_code": "B100",
                    "role_name": "涉薪权限",
                    "apply_type": "取消角色",
                    "catalog_matched": True,
                    "permission_level": "B1类-涉薪",
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": None, "org_auth_level": None, "org_unit_name": None}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_8")

        applicant_detail = next(row for row in detail_rows if row["dimension_name"] == "申请人的角色判断")
        approval_detail = next(row for row in detail_rows if row["dimension_name"] == "审批人判断")
        permission_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的权限")

        self.assertEqual(applicant_detail["rule_id"], "APPLICANT_CANCEL_ROLE_NON_HR_SKIPPED")
        self.assertEqual(approval_detail["rule_id"], "APPROVAL_CHAIN_DEFAULT")
        self.assertEqual(permission_detail["rule_id"], "PERMISSION_CANCEL_ROLE")
        self.assertEqual(summary_rows[0]["final_score"], 2.5)
        self.assertEqual(summary_rows[0]["summary_conclusion"], "可信任")
        self.assertFalse(summary_rows[0]["has_low_score_details"])

    def test_cross_org_unit_risk_is_skipped_for_exempt_process_categories(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-9", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "战区人行部门", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-19 10:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
                {
                    "node_name": "部门负责人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-19 11:00:00",
                    "approver_org_attributes": {"process_level_category": "万物云本部"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-9",
                    "role_code": "C001",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": "ORG9", "org_auth_level": None, "org_unit_name": "组织B"}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_9")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_SCOPE_SKIPPED")
        self.assertEqual(target_org_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["summary_conclusion"], "可信任")
        self.assertFalse(summary_rows[0]["has_low_score_details"])

    def test_none_payload_sections_do_not_break_evaluation(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-6", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "HX"},
            "applicant_org_attributes": None,
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-15 10:00:00",
                    "approver_org_attributes": None,
                }
            ],
            "permission_details": [
                {
                    "document_no": "RA-6",
                    "role_code": "C001",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": None,
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_6")

        self.assertEqual(len(summary_rows), 1)
        self.assertEqual(summary_rows[0]["document_no"], "RA-6")
        self.assertGreater(len(detail_rows), 0)
        self.assertTrue(any(row["dimension_name"] == "审批人判断" for row in detail_rows))


if __name__ == "__main__":
    unittest.main()
