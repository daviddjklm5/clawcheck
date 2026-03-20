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

    def test_xiangying_org_unit_skips_warzone_history_check(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-20260318-00020160", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "祥盈企服"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-18 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "部门负责人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-18 11:00:00",
                    "approver_org_attributes": {"process_level_category": "万物云本部"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-20260318-00020160",
                    "role_code": "C001",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": None, "org_auth_level": None, "org_unit_name": None}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_20160")

        approval_detail = next(row for row in detail_rows if row["dimension_name"] == "审批人判断")
        self.assertEqual(approval_detail["rule_id"], "APPROVAL_CHAIN_DEFAULT")
        self.assertEqual(approval_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)

    def test_xiangying_org_unit_skips_warzone_current_round_check(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-12", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "祥盈企服"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-19 09:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "部门负责人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-19 09:30:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-19 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "部门负责人",
                    "approver_employee_no": "009",
                    "approval_action": "同意",
                    "approval_time": "2026-03-19 10:30:00",
                    "approver_org_attributes": {"process_level_category": "万物云本部"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-12",
                    "role_code": "C001",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": True,
                    "targets": [{"org_code": None, "org_auth_level": None, "org_unit_name": None}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_12")

        approval_detail = next(row for row in detail_rows if row["dimension_name"] == "审批人判断")
        self.assertEqual(approval_detail["rule_id"], "APPROVAL_CHAIN_DEFAULT")
        self.assertEqual(approval_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)

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

    def test_b_and_below_permission_is_skipped_in_permission_dimension(self) -> None:
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
        self.assertEqual(permission_detail["rule_id"], "PERMISSION_B_AND_BELOW_SKIPPED")
        self.assertEqual(permission_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)

    def test_b_and_below_permission_skip_does_not_affect_target_org_dimension(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-10", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-19 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-19 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-10",
                    "role_code": "B200",
                    "role_name": "涉薪权限",
                    "catalog_matched": True,
                    "permission_level": "B1类-涉薪",
                    "skip_org_scope_check": False,
                    "targets": [{"org_code": "ORG10", "org_auth_level": None, "org_unit_name": "组织A"}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_10")

        permission_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的权限")
        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(permission_detail["rule_id"], "PERMISSION_B_AND_BELOW_SKIPPED")
        self.assertEqual(permission_detail["score"], 2.5)
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_AUTH_LEVEL_MAP")
        self.assertEqual(target_org_detail["score"], 2.0)
        self.assertEqual(summary_rows[0]["final_score"], 2.0)

    def test_cross_org_rule_has_priority_over_l4_skip_when_cross_unit(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-11", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-19 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-19 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-11",
                    "role_code": "C011",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": [{"org_code": "ORG11", "org_auth_level": "四级授权", "org_unit_name": "组织B"}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_11")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_CROSS_UNIT_LOW")
        self.assertEqual(target_org_detail["score"], 0.5)
        self.assertEqual(summary_rows[0]["final_score"], 0.5)

    def test_l4_skip_still_works_when_not_cross_unit(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-11-SAME-UNIT", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "组织A"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-19 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-19 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-11-SAME-UNIT",
                    "role_code": "C011",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": [{"org_code": "ORG11", "org_auth_level": "四级授权", "org_unit_name": "组织A"}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_11_same_unit")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_L4_SKIPPED")
        self.assertEqual(target_org_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)

    def test_l2_representative_office_is_downgraded_to_l3_for_scoring(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-13", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "广州战区代表处"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-19 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-19 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-13",
                    "role_code": "C013",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": [{"org_code": "ORG13", "org_auth_level": "二级授权", "org_unit_name": "广州战区代表处"}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_13")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_L2_REPRESENTATIVE_OFFICE_AS_L3")
        self.assertEqual(target_org_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)

    def test_representative_office_non_l2_auth_still_uses_auth_level_map(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-13B", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地服务站", "org_unit_name": "人力资源与行政服务中心"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-19 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地服务站"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-19 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-13B",
                    "role_code": "C013B",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": [
                        {
                            "org_code": "ORG13B",
                            "org_auth_level": "三级授权",
                            "org_unit_name": "琼桂战区代表处",
                            "org_company_name": "琼桂战区代表处",
                        }
                    ],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_13b")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_REPRESENTATIVE_OFFICE_AUTH_LEVEL_MAP")
        self.assertEqual(target_org_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)

    def test_warzone_hr_cross_company_l2_normal_org_uses_auth_level_map(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-L2-CROSS-1", "employee_no": "001", "company_name": "公司A"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "战区人行部门", "org_unit_name": "人力资源与行政服务中心"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-20 10:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
                {
                    "node_name": "审批",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-20 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-L2-CROSS-1",
                    "role_code": "ZZ001",
                    "role_name": "组织/岗位查看",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": [
                        {
                            "org_code": "ORG-L2-CROSS-1",
                            "org_auth_level": "二级授权",
                            "org_unit_name": "普通组织",
                            "org_company_name": "公司B",
                        }
                    ],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_l2_cross")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_L2_LOCAL_SERVICE_WARZONE_CROSS_COMPANY")
        self.assertEqual(target_org_detail["score"], 1.5)
        self.assertEqual(summary_rows[0]["final_score"], 1.5)

    def test_local_service_station_same_company_l2_normal_org_uses_updated_l2_override_score(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-L2-SAME-1", "employee_no": "001", "company_name": "公司A"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地服务站", "org_unit_name": "人力资源与行政服务中心"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-20 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地服务站"},
                },
                {
                    "node_name": "审批",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-20 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-L2-SAME-1",
                    "role_code": "ZZ002",
                    "role_name": "组织/岗位查看",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": [
                        {
                            "org_code": "ORG-L2-SAME-1",
                            "org_auth_level": "二级授权",
                            "org_unit_name": "普通组织",
                            "org_company_name": "公司A",
                        }
                    ],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_l2_same")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_L2_LOCAL_SERVICE_WARZONE_OVERRIDE")
        self.assertEqual(target_org_detail["score"], 1.5)
        self.assertEqual(summary_rows[0]["final_score"], 1.5)

    def test_local_org_same_company_sets_target_org_to_high_trust(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-LOCAL-1", "employee_no": "001", "company_name": "东莞滨海湾城资"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "万物云城"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-20 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-20 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-LOCAL-1",
                    "role_code": "C001",
                    "role_name": "常规权限",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": [
                        {
                            "org_code": "ORG-LOCAL-1",
                            "org_auth_level": "一级授权",
                            "org_unit_name": "万物云城",
                            "org_company_name": "东莞滨海湾城资",
                        }
                    ],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_local_same_company")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_LOCAL_SAME_COMPANY_TRUSTED")
        self.assertEqual(target_org_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)
        self.assertEqual(summary_rows[0]["summary_conclusion"], "可信任")

    def test_same_company_non_local_category_uses_auth_level_map(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-SAME-1", "employee_no": "001", "company_name": "万物云本部"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地服务站", "org_unit_name": "人力资源与行政服务中心"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-20 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地服务站"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-20 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-SAME-1",
                    "role_code": "ZZ001",
                    "role_name": "组织/岗位查看",
                    "catalog_matched": True,
                    "permission_level": "C类-常规",
                    "skip_org_scope_check": False,
                    "targets": [
                        {
                            "org_code": "ORG-SAME-1",
                            "org_auth_level": None,
                            "org_unit_name": "财务与资金管理中心",
                            "org_company_name": "万物云本部",
                        }
                    ],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_same_company")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_SAME_COMPANY_AUTH_LEVEL_MAP")
        self.assertEqual(target_org_detail["score"], 2.0)
        self.assertEqual(summary_rows[0]["final_score"], 2.0)

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

    def test_cancel_role_skips_target_org_auth_level_and_cross_unit_risks(self) -> None:
        bundle = {
            "basic_info": {"document_no": "RA-12", "employee_no": "001"},
            "applicant_person_attributes": {"hr_type": "H1"},
            "applicant_org_attributes": {"process_level_category": "属地组织", "org_unit_name": "为家-朴邻"},
            "approval_records": [
                {
                    "node_name": "权限申请提交",
                    "approver_employee_no": "001",
                    "approval_action": "提交",
                    "approval_time": "2026-03-20 10:00:00",
                    "approver_org_attributes": {"process_level_category": "属地组织"},
                },
                {
                    "node_name": "战区权限对接人",
                    "approver_employee_no": "008",
                    "approval_action": "同意",
                    "approval_time": "2026-03-20 11:00:00",
                    "approver_org_attributes": {"process_level_category": "战区人行部门"},
                },
            ],
            "permission_details": [
                {
                    "document_no": "RA-12",
                    "role_code": "YG003",
                    "role_name": "人员档案-可查看引出-无定薪无绩效",
                    "apply_type": "取消角色",
                    "catalog_matched": True,
                    "permission_level": "B1类-涉薪",
                    "skip_org_scope_check": False,
                    "targets": [{"org_code": "ORG12", "org_auth_level": "二级授权", "org_unit_name": "蝶城发展中心"}],
                }
            ],
        }

        summary_rows, detail_rows = self.evaluator.evaluate_documents([bundle], assessment_batch_no="audit_batch_12")

        target_org_detail = next(row for row in detail_rows if row["dimension_name"] == "申请的组织")
        self.assertEqual(target_org_detail["rule_id"], "TARGET_ORG_CANCEL_ROLE_SKIPPED")
        self.assertEqual(target_org_detail["score"], 2.5)
        self.assertEqual(summary_rows[0]["final_score"], 2.5)
        self.assertFalse(summary_rows[0]["has_low_score_details"])

    def test_cross_org_unit_rules_do_not_match_for_exempt_process_categories(self) -> None:
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
                    "skip_org_scope_check": False,
                    "targets": [{"org_code": "ORG9", "org_auth_level": "三级授权", "org_unit_name": "组织B"}],
                }
            ],
        }

        facts = self.evaluator._build_facts(bundle)
        role_row = facts["details"][0]
        target_row = role_row["targets"][0]
        context = self.evaluator._build_rule_context(facts, role_row, target_row)
        target_org_rules = self.evaluator.matrix["dimensions"]["target_organization"]["rules"]

        cross_unit_low_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_CROSS_UNIT_LOW")
        cross_unit_high_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_CROSS_UNIT_HIGH")
        cross_unit_other_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_CROSS_UNIT_OTHER")
        auth_level_map_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_AUTH_LEVEL_MAP")

        self.assertFalse(self.evaluator._rule_matches(cross_unit_low_rule["when"], context))
        self.assertFalse(self.evaluator._rule_matches(cross_unit_high_rule["when"], context))
        self.assertFalse(self.evaluator._rule_matches(cross_unit_other_rule["when"], context))
        self.assertTrue(self.evaluator._rule_matches(auth_level_map_rule["when"], context))

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
