from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml

from automation.db.postgres import PostgresRiskTrustStore
from automation.utils.config_loader import DatabaseSettings


class _FakeCursor:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []

    def execute(self, sql: str) -> None:
        self.executed_sql.append(sql)

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


class RiskTrustStoreEnsureTableTest(unittest.TestCase):
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

    def test_runs_ddl(self) -> None:
        with (
            patch.object(self.store, "connect", self._fake_connect),
            patch("pathlib.Path.read_text", side_effect=["DDL SQL 022", "DDL SQL 023", "DDL SQL 024"]),
        ):
            self.store.ensure_table()

        self.assertEqual(self.cursor.executed_sql, ["DDL SQL 022", "DDL SQL 023", "DDL SQL 024"])


class RiskTrustYamlAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.matrix_path = self.repo_root / "automation" / "config" / "rules" / "risk_trust_matrix.yaml"
        self.constants_path = self.repo_root / "automation" / "config" / "rules" / "risk_trust_constants.yaml"

    def test_matrix_yaml_contains_summary_and_low_score_output_contract(self) -> None:
        matrix = yaml.safe_load(self.matrix_path.read_text(encoding="utf-8"))

        self.assertEqual(matrix["defaults"]["low_score_threshold"], 1.0)
        self.assertIn("总结论", matrix["output_contract"]["summary_required_fields"])
        self.assertIn("低分明细结论", matrix["output_contract"]["summary_required_fields"])
        self.assertIn("明细结论", matrix["output_contract"]["detail_required_fields"])

    def test_matrix_yaml_contains_confirmed_manual_review_rules(self) -> None:
        matrix = yaml.safe_load(self.matrix_path.read_text(encoding="utf-8"))
        constants = yaml.safe_load(self.constants_path.read_text(encoding="utf-8"))

        applicant_rules = matrix["dimensions"]["applicant_role"]["rules"]
        approval_rules = matrix["dimensions"]["approval_chain"]["rules"]
        permission_rules = matrix["dimensions"]["permission_level"]["rules"]
        target_org_rules = matrix["dimensions"]["target_organization"]["rules"]

        cancel_non_hr_skip_rule = next(rule for rule in applicant_rules if rule["id"] == "APPLICANT_CANCEL_ROLE_NON_HR_SKIPPED")
        applicant_non_hr_rule = next(rule for rule in applicant_rules if rule["id"] == "APPLICANT_HR_NON_HR")
        applicant_hr_type_missing_rule = next(rule for rule in applicant_rules if rule["id"] == "APPLICANT_HR_TYPE_MISSING")
        approval_warzone_history_rule = next(rule for rule in approval_rules if rule["id"] == "APPROVAL_LOCAL_WITHOUT_WARZONE_HISTORY")
        approval_warzone_current_round_rule = next(
            rule for rule in approval_rules if rule["id"] == "APPROVAL_LOCAL_WITHOUT_WARZONE_CURRENT_ROUND"
        )
        missing_catalog_rule = next(rule for rule in permission_rules if rule["id"] == "PERMISSION_CATALOG_MISSING")
        cancel_role_rule = next(rule for rule in permission_rules if rule["id"] == "PERMISSION_CANCEL_ROLE")
        d_non_hr_rule = next(rule for rule in permission_rules if rule["id"] == "PERMISSION_D_NON_HR_OR_UNKNOWN")
        b_and_below_skip_rule = next(rule for rule in permission_rules if rule["id"] == "PERMISSION_B_AND_BELOW_SKIPPED")
        cancel_role_target_org_skip_rule = next(
            rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_CANCEL_ROLE_SKIPPED"
        )
        skipped_scope_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_SCOPE_SKIPPED")
        ss001_wyw_override_rule = next(
            rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_SS001_50702609_OVERRIDE"
        )
        l4_skip_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_L4_SKIPPED")
        local_same_company_trusted_rule = next(
            rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_LOCAL_SAME_COMPANY_TRUSTED"
        )
        same_company_auth_map_rule = next(
            rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_SAME_COMPANY_AUTH_LEVEL_MAP"
        )
        l1_not_allowed_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_L1_NOT_ALLOWED")
        l2_not_allowed_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_L2_NOT_ALLOWED")
        l2_local_service_warzone_override_rule = next(
            rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_L2_LOCAL_SERVICE_WARZONE_OVERRIDE"
        )
        l2_local_service_warzone_cross_company_rule = next(
            rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_L2_LOCAL_SERVICE_WARZONE_CROSS_COMPANY"
        )
        l2_representative_office_as_l3_rule = next(
            rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_L2_REPRESENTATIVE_OFFICE_AS_L3"
        )
        representative_office_auth_map_rule = next(
            rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_REPRESENTATIVE_OFFICE_AUTH_LEVEL_MAP"
        )
        cross_unit_low_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_CROSS_UNIT_LOW")
        cross_unit_high_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_CROSS_UNIT_HIGH")
        cross_unit_other_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_CROSS_UNIT_OTHER")
        auth_level_map_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_AUTH_LEVEL_MAP")

        self.assertEqual(cancel_non_hr_skip_rule["score"], 2.5)
        self.assertEqual(applicant_hr_type_missing_rule["score"], 1.0)
        self.assertEqual(
            applicant_non_hr_rule["when"]["all_details_cancel_role_apply_type"],
            False,
        )
        self.assertEqual(
            approval_warzone_history_rule["when"]["all_details_cancel_role_apply_type"],
            False,
        )
        self.assertEqual(
            approval_warzone_history_rule["when"]["applicant_org_unit_name_not_in_ref"],
            "approval_warzone_check_exempt_org_units",
        )
        self.assertEqual(
            approval_warzone_current_round_rule["when"]["applicant_org_unit_name_not_in_ref"],
            "approval_warzone_check_exempt_org_units",
        )
        self.assertEqual(
            constants["constants"]["approval_warzone_check_exempt_org_units"],
            ["祥盈企服"],
        )
        self.assertEqual(missing_catalog_rule["score"], 0.5)
        self.assertEqual(missing_catalog_rule["intervention_action"], "管理员更新权限列表后复核")
        self.assertEqual(cancel_role_rule["score"], 2.5)
        self.assertEqual(d_non_hr_rule["score"], 2.0)
        self.assertEqual(d_non_hr_rule["when"]["permission_level_equals"], "D类-普通")
        self.assertEqual(d_non_hr_rule["when"]["applicant_hr_type_not_in_ref"], "applicant_hr_staff_types")
        self.assertEqual(
            constants["constants"]["cancel_role_apply_types"],
            ["取消角色"],
        )
        self.assertEqual(
            constants["constants"]["permission_level_skip_assessment_levels"],
            ["B1类-涉薪", "B2类-涉档案绩效", "C类-常规", "D类-普通"],
        )
        self.assertEqual(
            constants["constants"]["target_org_auth_level_skip_assessment_levels"],
            ["4级授权"],
        )
        self.assertEqual(
            b_and_below_skip_rule["when"]["apply_type_not_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertEqual(
            b_and_below_skip_rule["when"]["permission_level_in_ref"],
            "permission_level_skip_assessment_levels",
        )
        self.assertEqual(b_and_below_skip_rule["score"], 2.5)
        self.assertEqual(cancel_role_target_org_skip_rule["score"], 2.5)
        self.assertEqual(
            cancel_role_target_org_skip_rule["when"]["apply_type_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertEqual(skipped_scope_rule["score"], 2.5)
        self.assertEqual(ss001_wyw_override_rule["priority"], 100)
        self.assertEqual(ss001_wyw_override_rule["score"], 2.5)
        self.assertEqual(ss001_wyw_override_rule["when"]["role_code_equals"], "SS001")
        self.assertEqual(ss001_wyw_override_rule["when"]["target_org_code_equals"], "50702609")
        self.assertEqual(l4_skip_rule["score"], 2.5)
        self.assertEqual(
            l4_skip_rule["when"]["target_org_auth_level_in_ref"],
            "target_org_auth_level_skip_assessment_levels",
        )
        self.assertEqual(
            l4_skip_rule["when"]["applicant_org_unit_not_equal_target_org_unit"],
            False,
        )
        self.assertEqual(local_same_company_trusted_rule["score"], 2.5)
        self.assertEqual(
            local_same_company_trusted_rule["when"]["applicant_process_level_category_equals"],
            "属地组织",
        )
        self.assertEqual(
            local_same_company_trusted_rule["when"]["permission_target_company_equal_target_org_company"],
            True,
        )
        self.assertEqual(
            same_company_auth_map_rule["when"]["permission_target_company_equal_target_org_company"],
            True,
        )
        self.assertEqual(
            same_company_auth_map_rule["when"]["applicant_process_level_category_not_in_ref"],
            "target_org_same_company_trusted_process_categories",
        )
        self.assertEqual(
            same_company_auth_map_rule["when"]["target_org_unit_name_not_in_ref"],
            "target_org_l2_representative_office_org_units",
        )
        self.assertEqual(
            same_company_auth_map_rule["score_map_ref"],
            "organization_auth_level_scores",
        )
        self.assertEqual(
            constants["constants"]["target_org_same_company_trusted_process_categories"],
            ["属地组织"],
        )
        self.assertEqual(
            l1_not_allowed_rule["when"]["apply_type_not_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertEqual(
            l1_not_allowed_rule["when"]["permission_target_company_equal_target_org_company"],
            False,
        )
        self.assertEqual(
            l2_not_allowed_rule["when"]["apply_type_not_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertEqual(
            l2_not_allowed_rule["when"]["target_org_unit_name_not_in_ref"],
            "target_org_l2_representative_office_org_units",
        )
        self.assertEqual(
            l2_not_allowed_rule["when"]["applicant_process_level_category_not_in_ref"],
            "l2_not_allowed_exempt_process_categories",
        )
        self.assertEqual(
            l2_not_allowed_rule["when"]["permission_target_company_equal_target_org_company"],
            False,
        )
        self.assertEqual(
            l2_local_service_warzone_override_rule["when"]["applicant_process_level_category_in_ref"],
            "l2_auth_level_map_process_categories",
        )
        self.assertEqual(
            l2_local_service_warzone_override_rule["score"],
            1.5,
        )
        self.assertEqual(
            l2_local_service_warzone_cross_company_rule["when"]["applicant_process_level_category_in_ref"],
            "l2_auth_level_map_process_categories",
        )
        self.assertEqual(
            l2_local_service_warzone_cross_company_rule["when"]["permission_target_company_equal_target_org_company"],
            False,
        )
        self.assertEqual(
            l2_local_service_warzone_cross_company_rule["score"],
            1.5,
        )
        self.assertEqual(
            l2_representative_office_as_l3_rule["when"]["target_org_unit_name_in_ref"],
            "target_org_l2_representative_office_org_units",
        )
        self.assertEqual(l2_representative_office_as_l3_rule["score"], 2.5)
        self.assertEqual(
            representative_office_auth_map_rule["when"]["target_org_unit_name_in_ref"],
            "target_org_l2_representative_office_org_units",
        )
        self.assertEqual(
            representative_office_auth_map_rule["when"]["target_org_auth_level_in_ref"],
            "target_org_representative_office_auth_level_map_levels",
        )
        self.assertEqual(
            constants["constants"]["l2_auth_level_map_process_categories"],
            ["属地服务站", "战区人行部门"],
        )
        self.assertEqual(
            constants["constants"]["l2_not_allowed_exempt_process_categories"],
            ["BG人行中心与学社", "人事远程交付中心", "蝶发人行部", "业务单元本部", "属地服务站", "战区人行部门"],
        )
        self.assertEqual(
            constants["constants"]["organization_auth_level_scores"]["2级授权"],
            2.0,
        )
        self.assertEqual(
            constants["constants"]["organization_auth_level_scores"]["3级授权"],
            2.5,
        )
        self.assertEqual(
            constants["constants"]["target_org_representative_office_auth_level_map_levels"],
            ["1级授权", "3级授权", "<NULL>"],
        )
        self.assertEqual(
            constants["constants"]["cross_org_assessment_exempt_process_categories"],
            ["人事远程交付中心", "BG人行中心与学社", "蝶发人行部", "战区人行部门", "属地服务站"],
        )
        self.assertEqual(
            constants["constants"]["target_org_l2_representative_office_org_units"],
            [
                "安徽战区代表处",
                "福州战区代表处",
                "厦门战区代表处",
                "山东战区代表处",
                "杭州战区代表处",
                "东北战区代表处",
                "鄂豫战区代表处",
                "湘赣战区代表处",
                "南京战区代表处",
                "西北战区代表处",
                "深圳战区代表处",
                "津晋战区代表处",
                "京冀战区代表处",
                "福建战区代表处",
                "川云战区代表处",
                "广州战区代表处",
                "琼桂战区代表处",
                "佛山战区代表处",
                "苏州战区代表处",
                "上海战区代表处",
                "渝贵战区代表处",
            ],
        )
        self.assertEqual(
            constants["constants"]["cross_org_high_trust_process_categories"],
            ["万物云本部"],
        )
        self.assertEqual(
            cross_unit_low_rule["when"]["applicant_process_level_category_not_in_ref"],
            "cross_org_assessment_exempt_process_categories",
        )
        self.assertEqual(
            cross_unit_low_rule["when"]["apply_type_not_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertNotIn("target_org_auth_level_not_in_ref", cross_unit_low_rule["when"])
        self.assertEqual(
            cross_unit_low_rule["when"]["permission_target_company_equal_target_org_company"],
            False,
        )
        self.assertEqual(
            cross_unit_high_rule["when"]["applicant_process_level_category_not_in_ref"],
            "cross_org_assessment_exempt_process_categories",
        )
        self.assertEqual(
            cross_unit_high_rule["when"]["apply_type_not_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertNotIn("target_org_auth_level_not_in_ref", cross_unit_high_rule["when"])
        self.assertEqual(
            cross_unit_high_rule["when"]["permission_target_company_equal_target_org_company"],
            False,
        )
        self.assertEqual(
            cross_unit_other_rule["when"]["applicant_process_level_category_not_in_ref"],
            "cross_org_assessment_exempt_process_categories",
        )
        self.assertEqual(
            cross_unit_other_rule["when"]["apply_type_not_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertNotIn("target_org_auth_level_not_in_ref", cross_unit_other_rule["when"])
        self.assertEqual(
            cross_unit_other_rule["when"]["permission_target_company_equal_target_org_company"],
            False,
        )
        self.assertEqual(
            auth_level_map_rule["when"]["apply_type_not_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertEqual(
            auth_level_map_rule["when"]["target_org_unit_name_not_in_ref"],
            "target_org_l2_representative_office_org_units",
        )
        self.assertEqual(
            auth_level_map_rule["when"]["permission_target_company_equal_target_org_company"],
            False,
        )

    def test_constants_yaml_contains_summary_conclusion_mapping(self) -> None:
        constants = yaml.safe_load(self.constants_path.read_text(encoding="utf-8"))

        summary_mapping = constants["constants"]["summary_conclusion_mapping"]
        self.assertEqual(summary_mapping["0.0"]["conclusion"], "拒绝")
        self.assertEqual(summary_mapping["0.5"]["action"], "manual_review")
        self.assertEqual(summary_mapping["2.5"]["conclusion"], "可信任")


if __name__ == "__main__":
    unittest.main()
