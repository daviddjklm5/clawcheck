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
            patch("pathlib.Path.read_text", side_effect=["DDL SQL 022", "DDL SQL 023"]),
        ):
            self.store.ensure_table()

        self.assertEqual(self.cursor.executed_sql, ["DDL SQL 022", "DDL SQL 023"])


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

        permission_rules = matrix["dimensions"]["permission_level"]["rules"]
        target_org_rules = matrix["dimensions"]["target_organization"]["rules"]

        missing_catalog_rule = next(rule for rule in permission_rules if rule["id"] == "PERMISSION_CATALOG_MISSING")
        skipped_scope_rule = next(rule for rule in target_org_rules if rule["id"] == "TARGET_ORG_SCOPE_SKIPPED")

        self.assertEqual(missing_catalog_rule["score"], 0.5)
        self.assertEqual(missing_catalog_rule["intervention_action"], "管理员更新权限列表后复核")
        self.assertEqual(skipped_scope_rule["score"], 2.5)

    def test_constants_yaml_contains_summary_conclusion_mapping(self) -> None:
        constants = yaml.safe_load(self.constants_path.read_text(encoding="utf-8"))

        summary_mapping = constants["constants"]["summary_conclusion_mapping"]
        self.assertEqual(summary_mapping["0.0"]["conclusion"], "拒绝")
        self.assertEqual(summary_mapping["0.5"]["action"], "manual_review")
        self.assertEqual(summary_mapping["2.5"]["conclusion"], "可信任")


if __name__ == "__main__":
    unittest.main()
