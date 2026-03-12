from __future__ import annotations

import json
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date, datetime
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
        downloaded_at: datetime | None = None,
    ) -> int:
        from automation.utils.roster_excel import ROSTER_DATE_FIELDS, ROSTER_FIELD_SPECS

        normalized_rows = list(rows)
        if not normalized_rows:
            return 0

        self.ensure_table()
        roster_columns = [field_name for _, field_name, _ in ROSTER_FIELD_SPECS]
        metadata_columns = [
            "query_date",
            "source_file_name",
            "import_batch_no",
            "row_no",
            "downloaded_at",
            "imported_at",
            "extra_columns_json",
        ]
        insert_columns = roster_columns + metadata_columns + ["created_at", "updated_at"]
        value_placeholders = [f"%({column})s" for column in roster_columns + metadata_columns]
        value_placeholders.extend(["NOW()", "NOW()"])
        update_columns = [column for column in roster_columns + metadata_columns if column != "employee_no"]

        insert_sql = f"""
            INSERT INTO {self.table_name} (
                {', '.join(insert_columns)}
            ) VALUES (
                {', '.join(value_placeholders)}
            )
            ON CONFLICT (employee_no) DO UPDATE SET
                {', '.join(f'{column} = EXCLUDED.{column}' for column in update_columns)},
                updated_at = NOW()
        """

        payloads: list[dict[str, Any]] = []
        for row in normalized_rows:
            payload: dict[str, Any] = {
                "employee_no": row.get("employee_no", ""),
                "query_date": query_date,
                "source_file_name": source_file_name,
                "import_batch_no": import_batch_no,
                "row_no": self._to_int_or_none(row.get("row_no")),
                "downloaded_at": downloaded_at,
                "imported_at": datetime.now(),
                "extra_columns_json": json.dumps(row.get("extra_columns", {}), ensure_ascii=False),
            }
            for column in roster_columns:
                if column == "employee_no":
                    continue
                value = row.get(column)
                if column in ROSTER_DATE_FIELDS:
                    payload[column] = self._parse_date(value)
                else:
                    payload[column] = self._null_if_blank(value)
            payloads.append(payload)

        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(insert_sql, payloads)
        return len(normalized_rows)

    @classmethod
    def _parse_date(cls, value: Any) -> date | None:
        value = cls._null_if_blank(value)
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            text = value.strip()
            for candidate in (text[:10], text.replace('/', '-')[:10]):
                try:
                    return date.fromisoformat(candidate)
                except ValueError:
                    continue
            return None
        raise ValueError(f"Unsupported date value: {value!r}")


class PostgresOrganizationListStore(_PostgresStoreBase):
    table_name = '"组织列表"'
    schema_sql = Path(__file__).resolve().parents[1] / "sql" / "003_organization_list.sql"
    migration_sql_files = [
        Path(__file__).resolve().parents[1] / "sql" / "005_organization_list_drop_extra_columns_json.sql",
        Path(__file__).resolve().parents[1] / "sql" / "007_organization_list_add_process_level_name.sql",
        Path(__file__).resolve().parents[1] / "sql" / "008_organization_list_standardize_latest_columns.sql",
    ]
    derived_schema_sql_files = [
        Path(__file__).resolve().parents[1] / "sql" / "004_city_warzone.sql",
        Path(__file__).resolve().parents[1] / "sql" / "006_organization_attribute_query.sql",
    ]
    base_columns = [
        "org_code",
        "row_no",
        "org_name",
        "org_type",
        "parent_org_name",
        "parent_org_code",
        "established_date",
        "company_name",
        "business_status",
        "org_level",
        "org_function",
        "city_name",
        "work_location",
        "physical_level",
        "pending_disable_date",
        "department_type",
        "process_level_name",
        "dept_subcategory_code",
        "dept_subcategory_name",
        "dept_category_code",
        "dept_category_name",
        "org_created_time",
        "org_full_name",
        "org_manager_name",
        "hr_owner_employee_no",
        "hr_owner_name",
        "hr_owner_include_children_flag",
        "hr_owner_exposed_flag",
        "source_root_org",
        "include_all_children",
        "source_file_name",
        "import_batch_no",
    ]

    def ensure_table(self) -> None:
        ddl = self.schema_sql.read_text(encoding="utf-8")
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(ddl)
                for migration_sql_file in self.migration_sql_files:
                    cursor.execute(migration_sql_file.read_text(encoding="utf-8"))
                for derived_schema_sql_file in self.derived_schema_sql_files:
                    cursor.execute(derived_schema_sql_file.read_text(encoding="utf-8"))

    def write_rows(
        self,
        rows: Iterable[dict[str, Any]],
        source_file_name: str,
        import_batch_no: str,
        source_root_org: str,
        include_all_children: bool,
        extra_headers: Iterable[str] | None = None,
    ) -> int:
        normalized_rows = list(rows)
        if not normalized_rows:
            return 0

        normalized_extra_headers = self._normalize_extra_headers(extra_headers, normalized_rows)

        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                self._ensure_extra_columns(cursor, normalized_extra_headers)
                cursor.execute(f"TRUNCATE TABLE {self.table_name}")
                insert_columns = self.base_columns + normalized_extra_headers + ["created_at", "updated_at"]
                value_placeholders = [f"%({column})s" for column in self.base_columns]
                extra_header_placeholders = {
                    header: f"dynamic_column_{index}"
                    for index, header in enumerate(normalized_extra_headers)
                }
                value_placeholders.extend(
                    f"%({extra_header_placeholders[header]})s" for header in normalized_extra_headers
                )
                value_placeholders.extend(["NOW()", "NOW()"])
                cursor.executemany(
                    f"""
                    INSERT INTO {self.table_name} (
                        {', '.join(self._quote_identifier(column) for column in insert_columns)}
                    ) VALUES (
                        {', '.join(value_placeholders)}
                    )
                    """,
                    [
                        self._build_orglist_payload(
                            row=row,
                            source_file_name=source_file_name,
                            import_batch_no=import_batch_no,
                            source_root_org=source_root_org,
                            include_all_children=include_all_children,
                            extra_headers=normalized_extra_headers,
                            extra_header_placeholders=extra_header_placeholders,
                        )
                        for row in normalized_rows
                    ],
                )
                cursor.execute('SELECT refresh_组织属性查询()')
        return len(normalized_rows)

    @classmethod
    def _build_orglist_payload(
        cls,
        row: dict[str, Any],
        source_file_name: str,
        import_batch_no: str,
        source_root_org: str,
        include_all_children: bool,
        extra_headers: list[str],
        extra_header_placeholders: dict[str, str],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "org_code": row.get("org_code", ""),
            "row_no": cls._to_int_or_none(row.get("row_no")),
            "org_name": cls._null_if_blank(row.get("org_name")),
            "org_type": cls._null_if_blank(row.get("org_type")),
            "parent_org_name": cls._null_if_blank(row.get("parent_org_name")),
            "parent_org_code": cls._null_if_blank(row.get("parent_org_code")),
            "established_date": cls._null_if_blank(row.get("established_date")),
            "company_name": cls._null_if_blank(row.get("company_name")),
            "business_status": cls._null_if_blank(row.get("business_status")),
            "org_level": cls._null_if_blank(row.get("org_level")),
            "org_function": cls._null_if_blank(row.get("org_function")),
            "city_name": cls._null_if_blank(row.get("city_name")),
            "work_location": cls._null_if_blank(row.get("work_location")),
            "physical_level": cls._null_if_blank(row.get("physical_level")),
            "pending_disable_date": cls._null_if_blank(row.get("pending_disable_date")),
            "department_type": cls._null_if_blank(row.get("department_type")),
            "process_level_name": cls._null_if_blank(row.get("process_level_name")),
            "dept_subcategory_code": cls._null_if_blank(row.get("dept_subcategory_code")),
            "dept_subcategory_name": cls._null_if_blank(row.get("dept_subcategory_name")),
            "dept_category_code": cls._null_if_blank(row.get("dept_category_code")),
            "dept_category_name": cls._null_if_blank(row.get("dept_category_name")),
            "org_created_time": cls._null_if_blank(row.get("org_created_time")),
            "org_full_name": cls._null_if_blank(row.get("org_full_name")),
            "org_manager_name": cls._null_if_blank(row.get("org_manager_name")),
            "hr_owner_employee_no": cls._null_if_blank(row.get("hr_owner_employee_no")),
            "hr_owner_name": cls._null_if_blank(row.get("hr_owner_name")),
            "hr_owner_include_children_flag": cls._null_if_blank(row.get("hr_owner_include_children_flag")),
            "hr_owner_exposed_flag": cls._null_if_blank(row.get("hr_owner_exposed_flag")),
            "source_root_org": source_root_org,
            "include_all_children": include_all_children,
            "source_file_name": source_file_name,
            "import_batch_no": import_batch_no,
        }
        extra_columns = row.get("extra_columns", {})
        for header in extra_headers:
            payload[extra_header_placeholders[header]] = cls._null_if_blank(extra_columns.get(header))
        return payload

    def _ensure_extra_columns(self, cursor, extra_headers: Iterable[str]) -> None:
        for header in extra_headers:
            cursor.execute(
                f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS {self._quote_identifier(header)} TEXT"
            )

    @classmethod
    def _normalize_extra_headers(cls, extra_headers: Iterable[str] | None, rows: Iterable[dict[str, Any]]) -> list[str]:
        ordered_headers: list[str] = []
        seen: set[str] = set()

        def append_header(header: Any) -> None:
            if not isinstance(header, str):
                return
            normalized_header = header.strip()
            if not normalized_header or normalized_header in seen:
                return
            seen.add(normalized_header)
            ordered_headers.append(normalized_header)

        for header in extra_headers or []:
            append_header(header)
        for row in rows:
            for header in row.get("extra_columns", {}).keys():
                append_header(header)
        return ordered_headers

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'
