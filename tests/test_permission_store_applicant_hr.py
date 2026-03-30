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
        self.assertEqual(tags["hr_subdomain"], "人事运营")
        self.assertEqual(tags["hr_judgement_reason"], "level1_is_hr")

    def test_comp_perf_maps_to_comp_perf_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "薪酬绩效",
                "position_name": "薪酬绩效经理",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "薪酬绩效岗")

    def test_hr_business_support_is_merged_into_ren_shi_yun_ying_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "人力业务支持",
                "position_name": "人力业务支持高级专业经理",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人事运营")

    def test_employee_relations_maps_to_chinese_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "员工关系",
                "position_name": "员工关系专员",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "员工关系")

    def test_org_development_maps_to_chinese_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "组织发展",
                "position_name": "组织发展经理",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "组织发展岗")

    def test_management_position_maps_to_chinese_management_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "position_name": "总经理",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人行负责人(管理岗)")

    def test_position_contains_fuzeren_maps_to_management_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "position_name": "人力资源负责人",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人行负责人(管理岗)")

    def test_standard_position_contains_fuzeren_maps_to_management_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "position_name": "人力资源经理",
                "standard_position_name": "军种本部二级部门负责人",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人行负责人(管理岗)")

    def test_position_contains_zongjian_maps_to_management_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "position_name": "人力资源总监",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人行负责人(管理岗)")

    def test_level2_hr_without_admin_keyword_maps_to_hr_resource_post(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "人力资源",
                "position_name": "人力资源经理",
                "standard_position_name": "人力资源岗",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人力资源岗")

    def test_level2_hr_with_admin_keyword_maps_to_hr_admin_post(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "人力资源",
                "position_name": "人力行政经理",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人事行政岗")

    def test_hrbp_keyword_in_position_maps_to_hrbp_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "position_name": "HRBP副经理",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "HRBP/业务支持")

    def test_personnel_keyword_fallback_maps_to_hr_resource_post(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "综合行政",
                "level2_function_name": "综合行政",
                "position_name": "人事专员",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人力资源岗")

    def test_operations_keyword_fallback_maps_to_hr_ops(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "数据分析",
                "org_path_name": "万物云_万科物业_人力资源与行政服务中心",
            }
        )

        self.assertEqual(tags["hr_type"], "H2")
        self.assertEqual(tags["hr_subdomain"], "人事运营")

    def test_excluded_position_overrides_h1_signals(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "position_name": "残疾人",
            }
        )

        self.assertEqual(tags["hr_type"], "HX")
        self.assertFalse(tags["is_hr_staff"])
        self.assertEqual(tags["hr_primary_evidence"], "position_name")
        self.assertEqual(tags["hr_primary_value"], "残疾人")
        self.assertEqual(tags["hr_judgement_reason"], "position_excluded_from_hr")

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
        self.assertEqual(tags["hr_subdomain"], "人行负责人(管理岗)")
        self.assertEqual(tags["hr_judgement_reason"], "weak_signal_management_position_promoted_to_h2")

    def test_employee_experience_position_in_special_org_unit_is_h2(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "员工体验与行政专业经理",
                "org_unit_name": "人力资源与行政服务中心",
                "level2_function_name": "综合行政",
                "is_responsible_hr": True,
            }
        )

        self.assertEqual(tags["hr_type"], "H2")
        self.assertTrue(tags["is_hr_staff"])
        self.assertFalse(tags["is_suspected_hr_staff"])
        self.assertEqual(tags["hr_primary_evidence"], "org_unit_name+position_name")
        self.assertEqual(tags["hr_primary_value"], "人力资源与行政服务中心|员工体验与行政专业经理")
        self.assertEqual(tags["hr_subdomain"], "人事行政岗")
        self.assertEqual(tags["hr_judgement_reason"], "org_unit_employee_experience_position_promoted_to_h2")

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

    def test_excluded_position_overrides_responsible_hr(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "外场采集人员",
                "org_path_name": "万物云_祥盈企服_组织发展中心",
                "is_responsible_hr": True,
            }
        )

        self.assertEqual(tags["hr_type"], "HX")
        self.assertFalse(tags["is_hr_staff"])
        self.assertFalse(tags["is_suspected_hr_staff"])
        self.assertEqual(tags["hr_primary_evidence"], "position_name")
        self.assertEqual(tags["hr_primary_value"], "外场采集人员")
        self.assertEqual(tags["hr_judgement_reason"], "position_excluded_from_hr")

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

    def test_public_service_center_org_path_maps_to_qifu_local_public_service(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_祥盈企服_公共服务中心_深圳片区_深圳公共服务中心_A万科集团HR-SSC",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "企服属地公服")

    def test_remote_bp_org_path_maps_to_qifu_remote_bp(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_祥盈企服_远程交付中心_人事远程交付中心_BP_华南区",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "企服远程外服")

    def test_remote_delivery_org_path_maps_to_qifu_remote_delivery_center(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_祥盈企服_远程交付中心_人事远程交付中心_数据服务组",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "企服人事远程交付中心")

    def test_standard_position_hrbp_maps_to_hrbp_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "standard_position_name": "HRBP",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "HRBP/业务支持")

    def test_position_name_hrbp_maps_to_hrbp_subdomain_before_hr_general(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "人力资源",
                "position_name": "HRBP",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "HRBP/业务支持")

    def test_hr_admin_center_local_service_station_maps_to_local_station(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_人事交付服务组_深圳",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "服务站-人事运营")

    def test_hr_admin_center_without_bg_falls_back_when_warzone_rule_removed(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_战区人力行政服务组",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "other_hr_domain")

    def test_recruiting_keyword_maps_to_recruiting_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "招聘运营",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "招聘配置岗")

    def test_talent_development_maps_to_training_cert_talent_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "人才发展",
                "position_name": "人才发展专家",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人才发展（含培训认证）")

    def test_hr_level2_station_positions_map_to_training_cert_talent_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "人力资源",
                "position_name": "服务站站长",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人才发展（含培训认证）")

    def test_hr_level2_training_cert_keyword_maps_to_training_cert_talent_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "人力资源",
                "position_name": "认证培训经理",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人才发展（含培训认证）")

    def test_perf_expert_with_hrbp_standard_position_maps_to_comp_perf_post(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "position_name": "绩效专家",
                "standard_position_name": "HRBP",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "薪酬绩效岗")

    def test_project_responsible_position_is_not_management_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "position_name": "项目人力资源及行政副经理(负责人)",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人力资源岗")

    def test_weak_signal_ops_manager_without_hr_level1_is_demoted_to_hx(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "项目管理",
                "position_name": "运营经理",
                "org_path_name": "万物云_万物云城_高投城资_C人力资源与行政服务部",
            }
        )

        self.assertEqual(tags["hr_type"], "HX")
        self.assertEqual(tags["hr_judgement_reason"], "weak_signal_position_demoted_to_hx")
        self.assertIsNone(tags["hr_subdomain"])

    def test_station_recruiting_level2_maps_to_station_recruiting_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "招聘",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_人事交付服务组_深圳",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "服务站-招聘")

    def test_bg_local_support_group_maps_to_hrbp_support(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_本部人力行政支持组",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "HRBP/业务支持")

    def test_bg_platform_ops_group_maps_to_hr_ops(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_平台与运营组",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人事运营")

    def test_bg_talent_leadership_group_maps_to_talent_subdomain(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_人才与领导力组",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人才发展（含培训认证）")

    def test_bg_org_effectiveness_group_maps_to_comp_perf_when_standard_position_is_comp_perf(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "standard_position_name": "薪酬绩效岗",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_组织与效能组",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "薪酬绩效岗")

    def test_bg_org_effectiveness_group_maps_to_org_development_otherwise(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "standard_position_name": "人力资源岗",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_组织与效能组",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "组织发展岗")

    def test_bg_employee_experience_group_maps_to_personnel_admin_post(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "position_name": "员工体验与行政",
                "org_unit_name": "人力资源与行政服务中心",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_员工体验与行政组",
            }
        )

        self.assertEqual(tags["hr_type"], "H2")
        self.assertEqual(tags["hr_subdomain"], "人事行政岗")

    def test_bg_platform_ops_group_takes_priority_over_comp_perf_keyword(self) -> None:
        tags = self.store._build_applicant_hr_tags(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "level1_function_name": "人力资源",
                "level2_function_name": "薪酬绩效",
                "position_name": "薪酬与绩效管理",
                "standard_position_name": "薪酬绩效岗",
                "org_path_name": "万物云_万物云本部_人力资源与行政服务中心_BG人力资源行政服务中心_平台与运营组",
            }
        )

        self.assertEqual(tags["hr_type"], "H1")
        self.assertEqual(tags["hr_subdomain"], "人事运营")

    def test_build_person_attribute_payload_carries_employee_group_fields(self) -> None:
        payload = self.store._build_person_attribute_payload(
            {
                "employee_no": "05026859",
                "employee_name": "张三",
                "department_id": "50900001",
                "org_unit_name": "人力资源与行政服务中心",
                "employee_group": "正式员工",
                "employee_subgroup": "管理岗",
                "level1_function_name": "人力资源",
                "level2_function_name": "人事运营",
                "position_name": "运营支持经理",
            }
        )

        self.assertEqual(payload["org_unit_name"], "人力资源与行政服务中心")
        self.assertEqual(payload["employee_group"], "正式员工")
        self.assertEqual(payload["employee_subgroup"], "管理岗")
        self.assertEqual(payload["employee_name"], "张三")
        self.assertEqual(payload["hr_type"], "H1")


if __name__ == "__main__":
    unittest.main()

