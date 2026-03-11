from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from automation.utils.config_loader import DatabaseSettings

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover
    psycopg = None


class _PostgresStoreBase:
    def __init__(self, settings: DatabaseSettings) -> None:
        self.settings = settings

    @staticmethod
    def is_configured(settings: DatabaseSettings) -> bool:
        required = [settings.host, settings.dbname, settings.user, settings.password]
        return all(bool(value.strip()) for value in required)

    def ensure_available(self) -> None:
        if psycopg is None:
            raise ModuleNotFoundError(
                "Missing dependency: psycopg. Run `pip install -r automation/requirements.txt`."
            )
        if not self.is_configured(self.settings):
            raise ValueError(
                "PostgreSQL connection is not configured. "
                "Set db.host/db.dbname/db.user/db.password in settings or env IERP_PG_* ."
            )

    @contextmanager
    def connect(self):
        self.ensure_available()
        connection = psycopg.connect(
            host=self.settings.host,
            port=self.settings.port,
            dbname=self.settings.dbname,
            user=self.settings.user,
            password=self.settings.password,
            sslmode=self.settings.sslmode,
            options=f"-c search_path={self.settings.schema}",
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _null_if_blank(value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @classmethod
    def _to_int_or_none(cls, value: Any) -> int | None:
        value = cls._null_if_blank(value)
        if value is None:
            return None
        return int(value)


class PostgresPermissionStore(_PostgresStoreBase):
    def write_documents(self, documents: Iterable[dict[str, Any]]) -> None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                for document in documents:
                    self._write_document(cursor, document)

    def _write_document(self, cursor, document: dict[str, Any]) -> None:
        basic = document["basic_info"]
        document_no = basic["document_no"]

        cursor.execute(
            """
            INSERT INTO basic_info (
                document_no,
                employee_no,
                permission_target,
                apply_reason,
                document_status,
                hr_org,
                company_name,
                department_name,
                position_name,
                apply_time,
                source_system,
                raw_payload,
                created_at,
                updated_at
            ) VALUES (
                %(document_no)s,
                %(employee_no)s,
                %(permission_target)s,
                %(apply_reason)s,
                %(document_status)s,
                %(hr_org)s,
                %(company_name)s,
                %(department_name)s,
                %(position_name)s,
                %(apply_time)s,
                %(source_system)s,
                %(raw_payload)s,
                NOW(),
                NOW()
            )
            ON CONFLICT (document_no) DO UPDATE SET
                employee_no = EXCLUDED.employee_no,
                permission_target = EXCLUDED.permission_target,
                apply_reason = EXCLUDED.apply_reason,
                document_status = EXCLUDED.document_status,
                hr_org = EXCLUDED.hr_org,
                company_name = EXCLUDED.company_name,
                department_name = EXCLUDED.department_name,
                position_name = EXCLUDED.position_name,
                apply_time = EXCLUDED.apply_time,
                source_system = EXCLUDED.source_system,
                raw_payload = EXCLUDED.raw_payload,
                updated_at = NOW()
            """,
            {
                **basic,
                "apply_time": self._null_if_blank(basic.get("apply_time")),
                "raw_payload": json.dumps(document, ensure_ascii=False),
            },
        )

        cursor.execute("DELETE FROM permission_apply_detail WHERE document_no = %s", (document_no,))
        cursor.execute("DELETE FROM approval_record WHERE document_no = %s", (document_no,))
        cursor.execute("DELETE FROM organization_code WHERE document_no = %s", (document_no,))

        detail_rows = document.get("permission_details", [])
        if detail_rows:
            cursor.executemany(
                """
                INSERT INTO permission_apply_detail (
                    document_no,
                    line_no,
                    apply_type,
                    role_name,
                    role_desc,
                    role_code,
                    same_role_multi_dimension_flag,
                    administrative_org_text,
                    administrative_org_detail_text,
                    position_text,
                    social_security_unit,
                    social_security_unit_detail,
                    business_project,
                    tax_unit,
                    salary_change_reason,
                    raw_row,
                    created_at,
                    updated_at
                ) VALUES (
                    %(document_no)s,
                    %(line_no)s,
                    %(apply_type)s,
                    %(role_name)s,
                    %(role_desc)s,
                    %(role_code)s,
                    %(same_role_multi_dimension_flag)s,
                    %(administrative_org_text)s,
                    %(administrative_org_detail_text)s,
                    %(position_text)s,
                    %(social_security_unit)s,
                    %(social_security_unit_detail)s,
                    %(business_project)s,
                    %(tax_unit)s,
                    %(salary_change_reason)s,
                    %(raw_row)s,
                    NOW(),
                    NOW()
                )
                """,
                [
                    {
                        **row,
                        "document_no": document_no,
                        "line_no": self._null_if_blank(row.get("line_no")),
                        "raw_row": json.dumps(row, ensure_ascii=False),
                    }
                    for row in detail_rows
                ],
            )

        approval_rows = document.get("approval_records", [])
        if approval_rows:
            cursor.executemany(
                """
                INSERT INTO approval_record (
                    document_no,
                    record_seq,
                    node_name,
                    approver_name,
                    approver_org_or_position,
                    approval_action,
                    approval_opinion,
                    approval_time,
                    raw_text,
                    created_at
                ) VALUES (
                    %(document_no)s,
                    %(record_seq)s,
                    %(node_name)s,
                    %(approver_name)s,
                    %(approver_org_or_position)s,
                    %(approval_action)s,
                    %(approval_opinion)s,
                    %(approval_time)s,
                    %(raw_text)s,
                    NOW()
                )
                """,
                [
                    {
                        **row,
                        "document_no": document_no,
                        "record_seq": self._to_int_or_none(row.get("record_seq")),
                        "approval_time": self._null_if_blank(row.get("approval_time")),
                    }
                    for row in approval_rows
                ],
            )

        org_codes = sorted({code for code in document.get("organization_codes", []) if code})
        if org_codes:
            cursor.executemany(
                """
                INSERT INTO organization_code (document_no, org_code, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (document_no, org_code) DO NOTHING
                """,
                [(document_no, code) for code in org_codes],
            )


class PostgresActiveRosterStore(_PostgresStoreBase):
    table_name = '"在职花名册表"'
    schema_sql = Path(__file__).resolve().parents[1] / "sql" / "002_active_roster.sql"

    def ensure_table(self) -> None:
        ddl = self.schema_sql.read_text(encoding="utf-8")
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(ddl)

    def write_rows(
        self,
        rows: Iterable[dict[str, Any]],
        query_date: date,
        source_file_name: str,
        import_batch_no: str,
    ) -> int:
        normalized_rows = list(rows)
        if not normalized_rows:
            return 0

        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    f"""
                    INSERT INTO {self.table_name} (
                        query_date,
                        employee_no,
                        employee_name,
                        company_name,
                        company_id,
                        department_name,
                        department_long_text,
                        department_id,
                        department_city,
                        entry_date,
                        level1_function_name,
                        position_code,
                        position_name,
                        specific_post_name,
                        critical_post_flag,
                        post_family,
                        job_title,
                        level2_function_name,
                        standard_position_code,
                        source_file_name,
                        import_batch_no,
                        row_no,
                        raw_row_json,
                        created_at,
                        updated_at
                    ) VALUES (
                        %(query_date)s,
                        %(employee_no)s,
                        %(employee_name)s,
                        %(company_name)s,
                        %(company_id)s,
                        %(department_name)s,
                        %(department_long_text)s,
                        %(department_id)s,
                        %(department_city)s,
                        %(entry_date)s,
                        %(level1_function_name)s,
                        %(position_code)s,
                        %(position_name)s,
                        %(specific_post_name)s,
                        %(critical_post_flag)s,
                        %(post_family)s,
                        %(job_title)s,
                        %(level2_function_name)s,
                        %(standard_position_code)s,
                        %(source_file_name)s,
                        %(import_batch_no)s,
                        %(row_no)s,
                        %(raw_row_json)s,
                        NOW(),
                        NOW()
                    )
                    ON CONFLICT (query_date, employee_no) DO UPDATE SET
                        employee_name = EXCLUDED.employee_name,
                        company_name = EXCLUDED.company_name,
                        company_id = EXCLUDED.company_id,
                        department_name = EXCLUDED.department_name,
                        department_long_text = EXCLUDED.department_long_text,
                        department_id = EXCLUDED.department_id,
                        department_city = EXCLUDED.department_city,
                        entry_date = EXCLUDED.entry_date,
                        level1_function_name = EXCLUDED.level1_function_name,
                        position_code = EXCLUDED.position_code,
                        position_name = EXCLUDED.position_name,
                        specific_post_name = EXCLUDED.specific_post_name,
                        critical_post_flag = EXCLUDED.critical_post_flag,
                        post_family = EXCLUDED.post_family,
                        job_title = EXCLUDED.job_title,
                        level2_function_name = EXCLUDED.level2_function_name,
                        standard_position_code = EXCLUDED.standard_position_code,
                        source_file_name = EXCLUDED.source_file_name,
                        import_batch_no = EXCLUDED.import_batch_no,
                        row_no = EXCLUDED.row_no,
                        raw_row_json = EXCLUDED.raw_row_json,
                        updated_at = NOW()
                    """,
                    [
                        {
                            "query_date": query_date,
                            "employee_no": row.get("employee_no", ""),
                            "employee_name": self._null_if_blank(row.get("employee_name")),
                            "company_name": self._null_if_blank(row.get("company_name")),
                            "company_id": self._null_if_blank(row.get("company_id")),
                            "department_name": self._null_if_blank(row.get("department_name")),
                            "department_long_text": self._null_if_blank(row.get("department_long_text")),
                            "department_id": self._null_if_blank(row.get("department_id")),
                            "department_city": self._null_if_blank(row.get("department_city")),
                            "entry_date": self._parse_date(row.get("entry_date")),
                            "level1_function_name": self._null_if_blank(row.get("level1_function_name")),
                            "position_code": self._null_if_blank(row.get("position_code")),
                            "position_name": self._null_if_blank(row.get("position_name")),
                            "specific_post_name": self._null_if_blank(row.get("specific_post_name")),
                            "critical_post_flag": self._null_if_blank(row.get("critical_post_flag")),
                            "post_family": self._null_if_blank(row.get("post_family")),
                            "job_title": self._null_if_blank(row.get("job_title")),
                            "level2_function_name": self._null_if_blank(row.get("level2_function_name")),
                            "standard_position_code": self._null_if_blank(row.get("standard_position_code")),
                            "source_file_name": source_file_name,
                            "import_batch_no": import_batch_no,
                            "row_no": self._to_int_or_none(row.get("row_no")),
                            "raw_row_json": json.dumps(row.get("raw_row", row), ensure_ascii=False),
                        }
                        for row in normalized_rows
                    ],
                )
        return len(normalized_rows)

    @classmethod
    def _parse_date(cls, value: Any) -> date | None:
        value = cls._null_if_blank(value)
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise ValueError(f"Unsupported date value: {value!r}")
