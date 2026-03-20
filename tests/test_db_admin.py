from __future__ import annotations

import argparse
import os
import unittest
from unittest.mock import patch

from automation.scripts.db_admin import (
    REPO_ROOT,
    build_acceptance_status,
    build_connection_payload,
    format_env_output,
    load_database_settings,
)


class _FakeDbSettings:
    def __init__(self) -> None:
        self.host = "127.0.0.1"
        self.port = 5432
        self.dbname = "clawcheck"
        self.user = "tester"
        self.password = "secret"
        self.schema = "public"
        self.sslmode = "prefer"


class _FakeSettings:
    def __init__(self) -> None:
        self.db = _FakeDbSettings()


class DbAdminHelpersTest(unittest.TestCase):
    def test_build_acceptance_status_reports_missing_objects(self) -> None:
        result = build_acceptance_status(
            required_tables=[
                {"tableName": "申请单基本信息", "exists": True},
                {"tableName": "组织列表", "exists": False},
            ],
            required_functions=[
                {"functionName": "refresh_组织属性查询", "exists": False},
            ],
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["missingTables"], ["组织列表"])
        self.assertEqual(result["missingFunctions"], ["refresh_组织属性查询"])

    def test_format_env_output_includes_pg_variables(self) -> None:
        rendered = format_env_output(
            {
                "host": "127.0.0.1",
                "port": 5440,
                "dbname": "clawcheck",
                "user": "tester",
                "password": "secret",
                "sslmode": "prefer",
            }
        )

        self.assertIn("PGHOST=127.0.0.1", rendered)
        self.assertIn("PGPORT=5440", rendered)
        self.assertIn("PGPASSWORD=secret", rendered)

    def test_load_database_settings_applies_env_and_cli_overrides(self) -> None:
        args = argparse.Namespace(
            config="",
            host="db-host",
            port=6543,
            dbname="target_db",
            user="target_user",
            password="target_password",
            schema="custom_schema",
            sslmode="require",
        )

        with (
            patch("automation.scripts.db_admin.resolve_default_config_path", return_value=REPO_ROOT / "automation/config/settings.yaml"),
            patch("automation.scripts.db_admin.load_settings", return_value=_FakeSettings()),
            patch.dict(os.environ, {"IERP_PG_HOST": "env-host", "IERP_PG_PORT": "6000"}, clear=False),
        ):
            settings_path, db_settings = load_database_settings(args)

        self.assertTrue(settings_path.as_posix().endswith("automation/config/settings.yaml"))
        self.assertEqual(db_settings.host, "db-host")
        self.assertEqual(db_settings.port, 6543)
        self.assertEqual(db_settings.dbname, "target_db")
        self.assertEqual(db_settings.user, "target_user")
        self.assertEqual(db_settings.password, "target_password")
        self.assertEqual(db_settings.schema, "custom_schema")
        self.assertEqual(db_settings.sslmode, "require")

    def test_build_connection_payload_hides_password_by_default(self) -> None:
        payload = build_connection_payload(
            settings_path=REPO_ROOT / "automation/config/settings.yaml",
            db_settings=_FakeDbSettings(),
            include_password=False,
        )

        self.assertNotIn("password", payload)
        self.assertEqual(payload["configPath"], "automation/config/settings.yaml")


if __name__ == "__main__":
    unittest.main()
