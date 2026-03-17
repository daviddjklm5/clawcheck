from __future__ import annotations

from contextlib import contextmanager
import unittest
from unittest.mock import patch

from automation.db.postgres import PostgresPermissionCatalogStore
from automation.utils.config_loader import DatabaseSettings


class _FakeCursor:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []

    def execute(self, sql: str, params=None) -> None:
        _ = params
        self.executed_sql.append(sql)

    def fetchone(self):
        return (7,)

    def fetchall(self):
        return [("A类-远程", 3), ("C类-常规", 4)]

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


class PermissionCatalogStoreSeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = PostgresPermissionCatalogStore(
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

    def test_seed_catalog_always_executes_schema_sql(self) -> None:
        seed_sql = "SELECT 'seed-catalog';"
        with (
            patch.object(self.store, "_needs_schema_update", return_value=False) as schema_check_mock,
            patch("pathlib.Path.read_text", return_value=seed_sql),
            patch.object(self.store, "connect", self._fake_connect),
        ):
            summary = self.store.seed_catalog()

        self.assertTrue(self.cursor.executed_sql)
        self.assertEqual(self.cursor.executed_sql[0], seed_sql)
        schema_check_mock.assert_called_once()
        self.assertEqual(summary["table_name"], "权限列表")
        self.assertEqual(summary["total_rows"], 7)
        self.assertEqual(
            summary["counts_by_permission_level"],
            [
                {"permission_level": "A类-远程", "count": 3},
                {"permission_level": "C类-常规", "count": 4},
            ],
        )


if __name__ == "__main__":
    unittest.main()
