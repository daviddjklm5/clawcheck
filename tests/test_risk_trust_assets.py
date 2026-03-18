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
        approval_warzone_history_rule = next(rule for rule in approval_rules if rule["id"] == "APPROVAL_LOCAL_WITHOUT_WARZONE_HISTORY")
        missing_catalog_rule = next(rule for rule in permission_rules if rule["id"] == "PERMISSION_CATALOG_MISSING")
        cancel_role_rule = next(rule for rule in permission_rules if rule["id"] == "PERMISSION_CANCEL_ROLE")
        b1_non_hr_rule = next(rule for rule in permission_rules if rule["id"] == "PERMISSION_B1_NON_HR")
        skipped_scope_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_SCOPE_SKIPPED")

        self.assertEqual(cancel_non_hr_skip_rule["score"], 2.5)
        self.assertEqual(
            applicant_non_hr_rule["when"]["all_details_cancel_role_apply_type"],
            False,
        )
        self.assertEqual(
            approval_warzone_history_rule["when"]["all_details_cancel_role_apply_type"],
            False,
        )
        self.assertEqual(missing_catalog_rule["score"], 0.5)
        self.assertEqual(missing_catalog_rule["intervention_action"], "管理员更新权限列表后复核")
        self.assertEqual(cancel_role_rule["score"], 2.5)
        self.assertEqual(
            constants["constants"]["cancel_role_apply_types"],
            ["取消角色"],
        )
        self.assertEqual(
            b1_non_hr_rule["when"]["apply_type_not_in_ref"],
            "cancel_role_apply_types",
        )
        self.assertEqual(skipped_scope_rule["score"], 2.5)

    def test_constants_yaml_contains_summary_conclusion_mapping(self) -> None:
        constants = yaml.safe_load(self.constants_path.read_text(encoding="utf-8"))

        summary_mapping = constants["constants"]["summary_conclusion_mapping"]
        self.assertEqual(summary_mapping["0.0"]["conclusion"], "拒绝")
        self.assertEqual(summary_mapping["0.5"]["action"], "manual_review")
        self.assertEqual(summary_mapping["2.5"]["conclusion"], "可信任")


if __name__ == "__main__":
    unittest.main()
