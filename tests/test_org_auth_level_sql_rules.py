from __future__ import annotations

from pathlib import Path
import unittest


class OrgAuthLevelSqlRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]
        self.base_sql = (self.repo_root / "automation/sql/006_organization_attribute_query.sql").read_text(
            encoding="utf-8"
        )
        self.latest_migration_sql = (
            self.repo_root / "automation/sql/028_business_unit_l4_to_l3_auth_level.sql"
        ).read_text(encoding="utf-8")

    def test_base_sql_contains_wanrui_exception_before_generic_l2_rule(self) -> None:
        exception_snippet = (
            "IF normalized_process_level_category = '业务单元本部'\n"
            "       AND normalized_org_unit_name = '万睿科技'\n"
            "       AND physical_level_num <= 4 THEN\n"
            "        RETURN '三级授权';"
        )
        generic_snippet = (
            "IF normalized_process_level_category = '业务单元本部'\n"
            "       AND physical_level_num <= 3 THEN\n"
            "        RETURN '二级授权';"
        )

        self.assertIn(exception_snippet, self.base_sql)
        self.assertIn(generic_snippet, self.base_sql)
        self.assertLess(self.base_sql.index(exception_snippet), self.base_sql.index(generic_snippet))

    def test_base_sql_contains_updated_generic_buben_thresholds(self) -> None:
        self.assertIn(
            "RETURN 'process_level_category:业务单元本部_and_physical_level:lte_3';",
            self.base_sql,
        )
        self.assertIn(
            "RETURN 'process_level_category:业务单元本部_and_physical_level:gte_4';",
            self.base_sql,
        )

    def test_base_sql_contains_traceable_rule_code_for_wanrui_exception(self) -> None:
        self.assertIn(
            "RETURN 'process_level_category:业务单元本部_and_org_unit_name:万睿科技_and_physical_level:lte_4';",
            self.base_sql,
        )

    def test_latest_migration_redefines_both_auth_level_functions(self) -> None:
        self.assertIn("CREATE OR REPLACE FUNCTION fn_map_org_auth_level(", self.latest_migration_sql)
        self.assertIn("CREATE OR REPLACE FUNCTION fn_map_org_auth_level_rule(", self.latest_migration_sql)
        self.assertIn("normalized_org_unit_name = '万睿科技'", self.latest_migration_sql)
        self.assertIn("physical_level_num <= 3", self.latest_migration_sql)
        self.assertIn("physical_level_num >= 4", self.latest_migration_sql)


if __name__ == "__main__":
    unittest.main()
