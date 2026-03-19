from __future__ import annotations

import unittest

from automation.db.postgres import _PostgresStoreBase


class OrgScopeSummaryRowsTest(unittest.TestCase):
    def test_build_org_scope_summary_rows_groups_by_org_and_sorts_by_physical_level_desc(self) -> None:
        org_scope_rows = [
            {"document_no": "RA-TEST-001", "role_code": "ROLE-A", "org_code": "ORG-1", "skip_org_scope_check": False},
            {"document_no": "RA-TEST-001", "role_code": "ROLE-B", "org_code": "ORG-1", "skip_org_scope_check": False},
            {"document_no": "RA-TEST-001", "role_code": "ROLE-C", "org_code": "ORG-2", "skip_org_scope_check": False},
            {"document_no": "RA-TEST-001", "role_code": "ROLE-D", "org_code": None, "skip_org_scope_check": True},
        ]
        org_attributes_by_code = {
            "ORG-1": {
                "org_name": "上海财务共享中心",
                "org_unit_name": "财务共享",
                "physical_level": "2",
                "process_level_category": "属地组织",
                "org_auth_level": "二级授权",
            },
            "ORG-2": {
                "org_name": "集团总部",
                "org_unit_name": "总部",
                "physical_level": "3",
                "process_level_category": "业务单元本部",
                "org_auth_level": "三级授权",
            },
        }

        result = _PostgresStoreBase._build_org_scope_summary_rows(org_scope_rows, org_attributes_by_code)

        self.assertEqual([row["org_code"] for row in result], ["ORG-2", "ORG-1", None])
        self.assertEqual(result[0]["aggregated_row_count"], 1)
        self.assertEqual(result[0]["process_level_category"], "业务单元本部")
        self.assertEqual(result[1]["aggregated_row_count"], 2)
        self.assertEqual(result[1]["org_auth_level"], "二级授权")
        self.assertEqual(result[2]["organization_name"], "不检查组织范围")
        self.assertTrue(result[2]["skip_org_scope_check"])


if __name__ == "__main__":
    unittest.main()
