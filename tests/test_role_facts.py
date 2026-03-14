from __future__ import annotations

import unittest

from automation.rules.role_facts import (
    build_detail_role_facts,
    build_detail_role_facts_list,
    is_deprecated_permission_level,
    is_remote_permission_level,
)


class RoleFactsTest(unittest.TestCase):
    def test_build_detail_role_facts_prefers_detail_name_and_uses_catalog_fields(self) -> None:
        detail_row = {
            "role_code": "QF24",
            "role_name": "远程薪酬主管-申请单快照",
        }
        catalog_row = {
            "role_code": "QF24",
            "role_name": "远程薪酬主管",
            "permission_level": "A类-远程",
            "skip_org_scope_check": False,
        }

        facts = build_detail_role_facts(detail_row, catalog_row)

        self.assertEqual(
            facts,
            {
                "code": "QF24",
                "name": "远程薪酬主管-申请单快照",
                "permission_level": "A类-远程",
                "skip_org_scope_check": False,
                "catalog_matched": True,
            },
        )

    def test_build_detail_role_facts_handles_missing_catalog(self) -> None:
        facts = build_detail_role_facts({"role_code": "UNKNOWN", "role_name": "未知角色"}, None)

        self.assertEqual(
            facts,
            {
                "code": "UNKNOWN",
                "name": "未知角色",
                "permission_level": "",
                "skip_org_scope_check": False,
                "catalog_matched": False,
            },
        )

    def test_build_detail_role_facts_list_joins_by_role_code(self) -> None:
        detail_rows = [
            {"role_code": "QF24", "role_name": "远程薪酬主管"},
            {"role_code": "DTX009", "role_name": "业务数据提报"},
        ]
        catalog_by_role_code = {
            "QF24": {
                "role_code": "QF24",
                "role_name": "远程薪酬主管",
                "permission_level": "A类-远程",
                "skip_org_scope_check": False,
            },
            "DTX009": {
                "role_code": "DTX009",
                "role_name": "业务数据提报",
                "permission_level": "C类-常规",
                "skip_org_scope_check": True,
            },
        }

        facts_list = build_detail_role_facts_list(detail_rows, catalog_by_role_code)

        self.assertEqual(facts_list[0]["permission_level"], "A类-远程")
        self.assertTrue(facts_list[1]["skip_org_scope_check"])

    def test_permission_level_helpers(self) -> None:
        self.assertTrue(is_remote_permission_level("A类-远程"))
        self.assertTrue(is_remote_permission_level(" A类-远程 "))
        self.assertFalse(is_remote_permission_level("C类-常规"))
        self.assertTrue(is_deprecated_permission_level("W类-取消"))
        self.assertFalse(is_deprecated_permission_level(""))


if __name__ == "__main__":
    unittest.main()
