from __future__ import annotations

from contextlib import contextmanager
import unittest
from unittest.mock import MagicMock, patch

from automation.db.postgres import PostgresPermissionCatalogStore
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


class PermissionCatalogStoreEnsureTableTest(unittest.TestCase):
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

    def _column_exists_side_effect(self, present_columns: set[str]):
        def _side_effect(cursor, table_name: str, column_name: str) -> bool:
            self.assertEqual(table_name, "权限列表")
            return column_name in present_columns

        return _side_effect

    def test_runs_ddl_when_table_is_missing(self) -> None:
        with (
            patch.object(self.store, "connect", self._fake_connect),
            patch("pathlib.Path.read_text", return_value="DDL SQL"),
            patch.object(self.store, "_column_exists", side_effect=self._column_exists_side_effect(set())),
        ):
            self.store.ensure_table()

        self.assertEqual(self.cursor.executed_sql, ["DDL SQL"])

    def test_raises_for_legacy_english_schema(self) -> None:
        with (
            patch.object(self.store, "connect", self._fake_connect),
            patch("pathlib.Path.read_text", return_value="DDL SQL"),
            patch.object(self.store, "_column_exists", side_effect=self._column_exists_side_effect({"role_code"})),
        ):
            with self.assertRaises(RuntimeError):
                self.store.ensure_table()

        self.assertEqual(self.cursor.executed_sql, [])

    def test_runs_ddl_for_legacy_chinese_schema(self) -> None:
        present_columns = {
            "角色编码",
            "角色名称",
            "原始权限级别",
            "归一化分组",
            "是否远程角色",
            "不检查组织范围",
            "是否已取消角色",
            "是否有效",
            "数据来源",
            "原始快照",
            "记录创建时间",
            "记录更新时间",
        }
        with (
            patch.object(self.store, "connect", self._fake_connect),
            patch("pathlib.Path.read_text", return_value="DDL SQL"),
            patch.object(self.store, "_column_exists", side_effect=self._column_exists_side_effect(present_columns)),
        ):
            self.store.ensure_table()

        self.assertEqual(self.cursor.executed_sql, ["DDL SQL"])

    def test_skips_ddl_when_new_schema_is_already_ready(self) -> None:
        present_columns = {
            "角色编码",
            "角色名称",
            "权限级别",
            "不检查组织范围",
            "数据来源",
            "原始快照",
            "记录创建时间",
            "记录更新时间",
        }
        with (
            patch.object(self.store, "connect", self._fake_connect),
            patch("pathlib.Path.read_text", return_value="DDL SQL"),
            patch.object(self.store, "_column_exists", side_effect=self._column_exists_side_effect(present_columns)),
        ):
            self.store.ensure_table()

        self.assertEqual(self.cursor.executed_sql, [])


if __name__ == "__main__":
    unittest.main()
