from __future__ import annotations

import unittest

from automation.db.postgres import PostgresPersonAttributesStore
from automation.utils.config_loader import DatabaseSettings


class PersonAttributesStoreApplicantHrTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = PostgresPersonAttributesStore(
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

    def test_unmatched_employee_returns_unmatched_tags(self) -> None:
        tags = self.store._build_applicant_hr_tags({"employee_no": "05026859"})

        self.assertEqual(tags["roster_match_status"], "UNMATCHED")
        self.assertIsNone(tags["hr_type"])
        self.assertFalse(tags["is_hr_staff"])
        self.assertFalse(tags["is_suspected_hr_staff"])
        self.assertEqual(tags["hr_judgement_reason"], "roster_not_found")

    def test_level1_hr_is_classified_as_h1(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "人事运营",
                "position_name": "运营支持经理",
            }
        )

        self.assertEqual(tags["roster_match_status"], "MATCHED")
        self.assertEqual(tags["hr_type"], "H1")
        self.assertTrue(tags["is_hr_staff"])
        self.assertEqual(tags["hr_primary_evidence"], "level1_function_name")
        self.assertEqual(tags["hr_subdomain"], "hr_operations")
        self.assertEqual(tags["hr_judgement_reason"], "level1_is_hr")

    def test_special_perf_position_requires_hr_org_path(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "目标与绩效管理专业总监",
                "org_path_name": "万物云_万科物业_财务及运营管理部",
            }
        )

        self.assertEqual(tags["hr_type"], "HX")
        self.assertEqual(tags["hr_judgement_reason"], "no_hr_signal")

    def test_management_position_in_hr_path_is_h2(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "平台与运营资深总监",
                "org_path_name": "万物云_万科物业_人力资源与行政服务中心",
            }
        )

        self.assertEqual(tags["hr_type"], "H2")
        self.assertTrue(tags["is_hr_staff"])
        self.assertEqual(tags["hr_primary_evidence"], "position_name")
        self.assertEqual(tags["hr_subdomain"], "other_hr_domain")
        self.assertEqual(tags["hr_judgement_reason"], "weak_signal_management_position_promoted_to_h2")

    def test_responsible_hr_without_other_signal_is_h3(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "运营管理中心经理",
                "is_responsible_hr": True,
            }
        )

        self.assertEqual(tags["hr_type"], "H3")
        self.assertTrue(tags["is_hr_staff"])
        self.assertEqual(tags["hr_primary_evidence"], "responsible_hr_employee_no")
        self.assertEqual(tags["hr_primary_value"], "05026859")
        self.assertIsNone(tags["hr_subdomain"])

    def test_hr_org_path_only_is_hy(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "法务专家",
                "org_path_name": "万物云_祥盈企服_组织发展中心",
            }
        )

        self.assertEqual(tags["hr_type"], "HY")
        self.assertFalse(tags["is_hr_staff"])
        self.assertTrue(tags["is_suspected_hr_staff"])
        self.assertEqual(tags["hr_primary_evidence"], "org_path_name")
        self.assertEqual(tags["hr_judgement_reason"], "org_path_keyword_hit_only")

    def test_wanyu_city_sales_department_rule_is_h1(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "认证中心负责人",
                "wanyu_city_sales_department": "深圳城市营业部",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_primary_evidence"], "wanyu_city_sales_department")
        self.assertEqual(tags["hr_primary_value"], "深圳城市营业部")
        self.assertEqual(tags["hr_judgement_reason"], "wanyu_city_sales_department_position_hit")


if __name__ == "__main__":
    unittest.main()
