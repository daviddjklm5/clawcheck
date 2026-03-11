from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

from automation.utils.config_loader import DatabaseSettings

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover
    psycopg = None


class PostgresPermissionStore:
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
