from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import unittest
from unittest.mock import patch

from automation.db.postgres import PostgresActiveRosterStore
from automation.utils.config_loader import DatabaseSettings


class _FakeCursor:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self.executemany_calls: list[tuple[str, list[dict[str, object]]]] = []

    def execute(self, sql: str, params=None) -> None:
        self.executed_sql.append(sql)

    def executemany(self, sql: str, payloads) -> None:
        self.executemany_calls.append((sql, list(payloads)))

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


class ActiveRosterStoreWriteRowsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = PostgresActiveRosterStore(
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

    def test_write_rows_truncates_roster_and_refreshes_person_attributes(self) -> None:
        rows = [{"employee_no": "05026859", "employee_name": "张三", "row_no": 2}]

        with (
            patch.object(self.store, "ensure_table"),
            patch.object(self.store, "connect", self._fake_connect),
            patch("automation.db.postgres.PostgresPersonAttributesStore._refresh_from_roster", return_value=1) as refresh_mock,
        ):
            inserted_count = self.store.write_rows(
                rows=rows,
                query_date=date(2026, 3, 15),
                source_file_name="roster.xlsx",
                import_batch_no="roster_20260315_120000",
            )

        self.assertEqual(inserted_count, 1)
        self.assertTrue(any("TRUNCATE TABLE \"在职花名册表\"" in sql for sql in self.cursor.executed_sql))
        self.assertEqual(len(self.cursor.executemany_calls), 1)
        refresh_mock.assert_called_once_with(self.cursor)


if __name__ == "__main__":
    unittest.main()
