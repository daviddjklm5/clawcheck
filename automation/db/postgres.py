from __future__ import annotations
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from automation.utils.approval_record_helpers import (
    collect_unresolved_approver_names,
    derive_latest_approval_time,
    normalize_approval_records,
)
from automation.utils.config_loader import DatabaseSettings

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover
    psycopg = None


BASIC_INFO_TABLE = '"申请单基本信息"'
PERMISSION_APPLY_DETAIL_TABLE = '"申请单权限列表"'
APPROVAL_RECORD_TABLE = '"申请单审批记录"'
APPLY_FORM_ORG_SCOPE_TABLE = '"申请表组织范围"'

BASIC_INFO_COLUMNS = {
    "document_no": "单据编号",
    "employee_no": "工号",
    "permission_target": "权限对象",
    "apply_reason": "申请理由",
    "document_status": "单据状态",
    "hr_org": "人事管理组织",
    "company_name": "公司",
    "department_name": "部门",
    "position_name": "职位",
    "apply_time": "申请日期",
    "latest_approval_time": "最新审批时间",
    "collection_count": "采集次数",
    "created_at": "记录创建时间",
    "updated_at": "记录更新时间",
}

PERMISSION_DETAIL_COLUMNS = {
    "id": "权限明细ID",
    "document_no": "单据编号",
    "line_no": "明细行号",
    "apply_type": "申请类型",
    "role_name": "角色名称",
    "role_desc": "角色描述",
    "role_code": "角色编码",
    "social_security_unit": "参保单位",
    "org_scope_count": "组织范围数量",
    "created_at": "记录创建时间",
    "updated_at": "记录更新时间",
}

APPROVAL_RECORD_COLUMNS = {
    "id": "审批记录ID",
    "document_no": "单据编号",
    "record_seq": "审批记录顺序号",
    "node_name": "节点名称",
    "approver_name": "审批人",
    "approver_employee_no": "工号",
    "approver_org_or_position": "审批人组织或职位",
    "approval_action": "审批动作",
    "approval_opinion": "审批意见",
    "approval_time": "审批时间",
    "raw_text": "原始展示文本",
    "created_at": "记录创建时间",
}

APPLY_FORM_ORG_SCOPE_COLUMNS = {
    "id": "组织范围ID",
    "document_no": "单据编号",
    "role_code": "角色编码",
    "role_name": "角色名称",
    "org_code": "组织编码",
    "created_at": "记录创建时间",
}

PERMISSION_CATALOG_COLUMNS = {
    "role_code": "角色编码",
    "role_name": "角色名称",
    "permission_level": "权限级别",
    "skip_org_scope_check": "不检查组织范围",
    "source_system": "数据来源",
    "raw_payload": "原始快照",
    "created_at": "记录创建时间",
    "updated_at": "记录更新时间",
}


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

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'

    @classmethod
    def _quoted_columns(cls, columns: Iterable[str]) -> str:
        return ", ".join(cls._quote_identifier(column) for column in columns)

    @classmethod
    def _normalize_physical_column_name(cls, name: str) -> str:
        normalized = name.strip()
        for old, new in (
            (" ", "_"),
            (".", "_"),
            ("/", "_"),
            ("-", "_"),
            ("(", "_"),
            (")", "_"),
            ("（", "_"),
            ("）", "_"),
        ):
            normalized = normalized.replace(old, new)
        while "__" in normalized:
            normalized = normalized.replace("__", "_")
        return normalized.strip("_")

    @classmethod
    def _build_physical_mapping(cls, specs: Iterable[tuple[str, str, str]] | Iterable[tuple[str, str]]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for spec in specs:
            header = spec[0]
            field_name = spec[1]
            mapping[field_name] = cls._normalize_physical_column_name(header)
        return mapping

    @staticmethod
    def _column_exists(cursor, table_name: str, column_name: str) -> bool:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        return cursor.fetchone() is not None


class PostgresPermissionStore(_PostgresStoreBase):
    schema_sql = Path(__file__).resolve().parents[1] / "sql" / "001_permission_apply_collect.sql"
    bootstrap_migration_sql_files = [
        Path(__file__).resolve().parents[1] / "sql" / "010_permission_apply_collect_migrate_basic_info.sql",
        Path(__file__).resolve().parents[1] / "sql" / "011_permission_apply_collect_trim_columns.sql",
    ]
    schema_upgrade_sql_files = [
        Path(__file__).resolve().parents[1] / "sql" / "016_permission_apply_collect_approval_record_latest_time.sql",
        Path(__file__).resolve().parents[1] / "sql" / "017_permission_apply_collect_recollect_strategy.sql",
    ]
    role_org_scope_migration_sql = (
        Path(__file__).resolve().parents[1] / "sql" / "014_apply_form_org_scope_role_org_refactor.sql"
    )

    @classmethod
    def _index_exists(cls, cursor, index_name: str) -> bool:
        cursor.execute(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND indexname = %s
            LIMIT 1
            """,
            (index_name,),
        )
        return cursor.fetchone() is not None

    @classmethod
    def _column_is_nullable(cls, cursor, table_name: str, column_name: str) -> bool | None:
        cursor.execute(
            """
            SELECT is_nullable = 'YES'
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        row = cursor.fetchone()
        return None if row is None else bool(row[0])

    def _apply_form_org_scope_needs_role_refactor(self, cursor) -> bool:
        required_columns = (
            APPLY_FORM_ORG_SCOPE_COLUMNS["role_code"],
            APPLY_FORM_ORG_SCOPE_COLUMNS["role_name"],
        )
        if any(not self._column_exists(cursor, "申请表组织范围", column_name) for column_name in required_columns):
            return True
        if self._column_is_nullable(cursor, "申请表组织范围", APPLY_FORM_ORG_SCOPE_COLUMNS["org_code"]) is False:
            return True
        if not self._index_exists(cursor, "uq_apply_form_org_scope_doc_role_org"):
            return True
        if not self._index_exists(cursor, "uq_apply_form_org_scope_doc_role_null_org"):
            return True
        return False

    def ensure_table(self) -> None:
        ddl = self.schema_sql.read_text(encoding="utf-8")
        with self.connect() as connection:
            with connection.cursor() as cursor:
                if self._column_exists(cursor, "申请单基本信息", "document_no"):
                    raise RuntimeError('Detected legacy English schema for "申请单基本信息". Run automation/sql/012_rename_columns_to_cn_fixed_schema.sql first.')
                needs_bootstrap = not self._column_exists(cursor, "申请单基本信息", BASIC_INFO_COLUMNS["document_no"])
                cursor.execute(ddl)
                if needs_bootstrap:
                    for migration_sql_file in self.bootstrap_migration_sql_files:
                        cursor.execute(migration_sql_file.read_text(encoding="utf-8"))
                if self._apply_form_org_scope_needs_role_refactor(cursor):
                    cursor.execute(self.role_org_scope_migration_sql.read_text(encoding="utf-8"))
                for migration_sql_file in self.schema_upgrade_sql_files:
                    cursor.execute(migration_sql_file.read_text(encoding="utf-8"))

    @classmethod
    def _normalize_document_locally(cls, document: dict[str, Any]) -> dict[str, Any]:
        normalized_document = dict(document)
        basic_info = dict(document.get("basic_info", {}))
        approval_records = normalize_approval_records(list(document.get("approval_records", [])))
        basic_info["latest_approval_time"] = derive_latest_approval_time(approval_records)
        normalized_document["basic_info"] = basic_info
        normalized_document["approval_records"] = approval_records
        return normalized_document

    @classmethod
    def _normalize_documents_locally(cls, documents: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [cls._normalize_document_locally(document) for document in documents]

    @classmethod
    def _collect_unresolved_approver_names(cls, documents: Iterable[dict[str, Any]]) -> set[str]:
        unresolved_names: set[str] = set()
        for document in documents:
            unresolved_names.update(collect_unresolved_approver_names(list(document.get("approval_records", []))))
        return unresolved_names

    @classmethod
    def _apply_approver_employee_no_map(
        cls,
        documents: Iterable[dict[str, Any]],
        approver_employee_no_by_name: dict[str, str],
    ) -> list[dict[str, Any]]:
        normalized_documents: list[dict[str, Any]] = []
        for document in documents:
            normalized_document = dict(document)
            basic_info = dict(document.get("basic_info", {}))
            approval_records = normalize_approval_records(
                list(document.get("approval_records", [])),
                approver_employee_no_by_name=approver_employee_no_by_name,
            )
            basic_info["latest_approval_time"] = derive_latest_approval_time(approval_records)
            normalized_document["basic_info"] = basic_info
            normalized_document["approval_records"] = approval_records
            normalized_documents.append(normalized_document)
        return normalized_documents

    def prepare_documents(
        self,
        documents: Iterable[dict[str, Any]],
        resolve_roster_approver_employee_no: bool = True,
    ) -> list[dict[str, Any]]:
        normalized_documents = self._normalize_documents_locally(documents)
        if not normalized_documents or not resolve_roster_approver_employee_no:
            return normalized_documents
        if psycopg is None or not self.is_configured(self.settings):
            return normalized_documents

        unresolved_names = self._collect_unresolved_approver_names(normalized_documents)
        if not unresolved_names:
            return normalized_documents

        try:
            with self.connect() as connection:
                with connection.cursor() as cursor:
                    approver_employee_no_by_name = self._fetch_unique_roster_employee_no_by_names(cursor, unresolved_names)
        except Exception:
            return normalized_documents

        return self._apply_approver_employee_no_map(normalized_documents, approver_employee_no_by_name)

    def write_documents(self, documents: Iterable[dict[str, Any]]) -> None:
        normalized_documents = self._normalize_documents_locally(documents)
        if not normalized_documents:
            return

        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                unresolved_names = self._collect_unresolved_approver_names(normalized_documents)
                approver_employee_no_by_name = self._fetch_unique_roster_employee_no_by_names(cursor, unresolved_names)
                normalized_documents = self._apply_approver_employee_no_map(
                    normalized_documents,
                    approver_employee_no_by_name,
                )
                for document in normalized_documents:
                    self._write_document(cursor, document)

    @staticmethod
    def _normalize_timestamp_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.isoformat()
        return str(value).strip()

    def fetch_document_sync_states(self, document_nos: Iterable[str]) -> dict[str, dict[str, Any]]:
        normalized_document_nos = sorted(
            {
                str(document_no).strip()
                for document_no in document_nos
                if isinstance(document_no, str) and document_no.strip()
            }
        )
        if not normalized_document_nos:
            return {}

        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    WITH approval_counts AS (
                        SELECT
                            {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])} AS document_no,
                            COUNT(*)::INTEGER AS approval_record_count
                        FROM {APPROVAL_RECORD_TABLE}
                        WHERE {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])} = ANY(%s)
                        GROUP BY {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])}
                    )
                    SELECT
                        bi.{self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])},
                        bi.{self._quote_identifier(BASIC_INFO_COLUMNS["latest_approval_time"])},
                        COALESCE(bi.{self._quote_identifier(BASIC_INFO_COLUMNS["collection_count"])}, 1),
                        COALESCE(ac.approval_record_count, 0)
                    FROM {BASIC_INFO_TABLE} bi
                    LEFT JOIN approval_counts ac
                      ON ac.document_no = bi.{self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])}
                    WHERE bi.{self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])} = ANY(%s)
                    """,
                    (normalized_document_nos, normalized_document_nos),
                )
                rows = cursor.fetchall()

        return {
            str(row[0]).strip(): {
                "document_no": str(row[0]).strip(),
                "latest_approval_time": self._normalize_timestamp_text(row[1]),
                "collection_count": int(row[2]) if row[2] is not None else 1,
                "approval_record_count": int(row[3]) if row[3] is not None else 0,
            }
            for row in rows
            if row and isinstance(row[0], str) and row[0].strip()
        }

    def _fetch_unique_roster_employee_no_by_names(self, cursor, approver_names: Iterable[str]) -> dict[str, str]:
        name_list = sorted(
            {
                str(name).strip()
                for name in approver_names
                if isinstance(name, str) and name.strip()
            }
        )
        if not name_list:
            return {}
        if (
            not self._column_exists(cursor, "在职花名册表", "姓名")
            or not self._column_exists(cursor, "在职花名册表", "人员编号")
        ):
            return {}

        cursor.execute(
            """
            WITH matched AS (
                SELECT "姓名", "人员编号"
                FROM "在职花名册表"
                WHERE "姓名" = ANY(%s)
                  AND "姓名" IS NOT NULL
                  AND "人员编号" IS NOT NULL
            )
            SELECT "姓名", MIN("人员编号") AS "人员编号"
            FROM matched
            GROUP BY "姓名"
            HAVING COUNT(DISTINCT "人员编号") = 1
            """,
            (name_list,),
        )
        rows = cursor.fetchall()
        return {
            str(row[0]).strip(): str(row[1]).strip()
            for row in rows
            if row
            and isinstance(row[0], str)
            and row[0].strip()
            and isinstance(row[1], str)
            and row[1].strip()
        }

    def _write_document(self, cursor, document: dict[str, Any]) -> None:
        basic = document["basic_info"]
        document_no = basic["document_no"]
        collection_count = self._to_int_or_none(basic.get("collection_count")) or 1
        write_mode = str(document.get("_write_mode") or "").strip()

        if write_mode == "recollect":
            cursor.execute(
                f'DELETE FROM {BASIC_INFO_TABLE} WHERE {self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])} = %s',
                (document_no,),
            )

        basic_insert_columns = [
            BASIC_INFO_COLUMNS["document_no"],
            BASIC_INFO_COLUMNS["employee_no"],
            BASIC_INFO_COLUMNS["permission_target"],
            BASIC_INFO_COLUMNS["apply_reason"],
            BASIC_INFO_COLUMNS["document_status"],
            BASIC_INFO_COLUMNS["hr_org"],
            BASIC_INFO_COLUMNS["company_name"],
            BASIC_INFO_COLUMNS["department_name"],
            BASIC_INFO_COLUMNS["position_name"],
            BASIC_INFO_COLUMNS["apply_time"],
            BASIC_INFO_COLUMNS["latest_approval_time"],
            BASIC_INFO_COLUMNS["collection_count"],
            BASIC_INFO_COLUMNS["created_at"],
            BASIC_INFO_COLUMNS["updated_at"],
        ]

        cursor.execute(
            f"""
            INSERT INTO {BASIC_INFO_TABLE} (
                {self._quoted_columns(basic_insert_columns)}
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
                %(latest_approval_time)s,
                %(collection_count)s,
                NOW(),
                NOW()
            )
            ON CONFLICT ({self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])}) DO UPDATE SET
                {self._quote_identifier(BASIC_INFO_COLUMNS["employee_no"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["employee_no"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["permission_target"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["permission_target"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["apply_reason"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["apply_reason"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["document_status"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["document_status"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["hr_org"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["hr_org"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["company_name"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["company_name"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["department_name"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["department_name"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["position_name"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["position_name"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["apply_time"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["apply_time"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["latest_approval_time"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["latest_approval_time"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["collection_count"])} = EXCLUDED.{self._quote_identifier(BASIC_INFO_COLUMNS["collection_count"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["updated_at"])} = NOW()
            """,
            {
                **basic,
                "apply_time": self._null_if_blank(basic.get("apply_time")),
                "latest_approval_time": self._null_if_blank(basic.get("latest_approval_time")),
                "collection_count": collection_count,
            },
        )

        cursor.execute(
            f'DELETE FROM {PERMISSION_APPLY_DETAIL_TABLE} WHERE {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])} = %s',
            (document_no,),
        )
        cursor.execute(
            f'DELETE FROM {APPROVAL_RECORD_TABLE} WHERE {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])} = %s',
            (document_no,),
        )
        cursor.execute(
            f'DELETE FROM {APPLY_FORM_ORG_SCOPE_TABLE} WHERE {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])} = %s',
            (document_no,),
        )

        detail_rows = document.get("permission_details", [])
        if detail_rows:
            detail_insert_columns = [
                PERMISSION_DETAIL_COLUMNS["document_no"],
                PERMISSION_DETAIL_COLUMNS["line_no"],
                PERMISSION_DETAIL_COLUMNS["apply_type"],
                PERMISSION_DETAIL_COLUMNS["role_name"],
                PERMISSION_DETAIL_COLUMNS["role_desc"],
                PERMISSION_DETAIL_COLUMNS["role_code"],
                PERMISSION_DETAIL_COLUMNS["social_security_unit"],
                PERMISSION_DETAIL_COLUMNS["org_scope_count"],
                PERMISSION_DETAIL_COLUMNS["created_at"],
                PERMISSION_DETAIL_COLUMNS["updated_at"],
            ]
            cursor.executemany(
                f"""
                INSERT INTO {PERMISSION_APPLY_DETAIL_TABLE} (
                    {self._quoted_columns(detail_insert_columns)}
                ) VALUES (
                    %(document_no)s,
                    %(line_no)s,
                    %(apply_type)s,
                    %(role_name)s,
                    %(role_desc)s,
                    %(role_code)s,
                    %(social_security_unit)s,
                    %(org_scope_count)s,
                    NOW(),
                    NOW()
                )
                """,
                [
                    {
                        **row,
                        "document_no": document_no,
                        "line_no": self._null_if_blank(row.get("line_no")),
                        "org_scope_count": self._to_int_or_none(row.get("org_scope_count")),
                    }
                    for row in detail_rows
                ],
            )

        approval_rows = document.get("approval_records", [])
        if approval_rows:
            approval_insert_columns = [
                APPROVAL_RECORD_COLUMNS["document_no"],
                APPROVAL_RECORD_COLUMNS["record_seq"],
                APPROVAL_RECORD_COLUMNS["node_name"],
                APPROVAL_RECORD_COLUMNS["approver_name"],
                APPROVAL_RECORD_COLUMNS["approver_employee_no"],
                APPROVAL_RECORD_COLUMNS["approver_org_or_position"],
                APPROVAL_RECORD_COLUMNS["approval_action"],
                APPROVAL_RECORD_COLUMNS["approval_opinion"],
                APPROVAL_RECORD_COLUMNS["approval_time"],
                APPROVAL_RECORD_COLUMNS["raw_text"],
                APPROVAL_RECORD_COLUMNS["created_at"],
            ]
            cursor.executemany(
                f"""
                INSERT INTO {APPROVAL_RECORD_TABLE} (
                    {self._quoted_columns(approval_insert_columns)}
                ) VALUES (
                    %(document_no)s,
                    %(record_seq)s,
                    %(node_name)s,
                    %(approver_name)s,
                    %(approver_employee_no)s,
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
                        "approver_employee_no": self._null_if_blank(row.get("approver_employee_no")),
                        "approval_time": self._null_if_blank(row.get("approval_time")),
                    }
                    for row in approval_rows
                ],
            )

        org_scope_rows = self._build_apply_form_org_scope_rows(cursor, document_no, document)
        if org_scope_rows:
            cursor.executemany(
                f"""
                INSERT INTO {APPLY_FORM_ORG_SCOPE_TABLE} (
                    {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])},
                    {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_code"])},
                    {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_name"])},
                    {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["org_code"])},
                    {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["created_at"])}
                )
                VALUES (%s, %s, %s, %s, NOW())
                """,
                org_scope_rows,
            )

    def _build_apply_form_org_scope_rows(
        self,
        cursor,
        document_no: str,
        document: dict[str, Any],
    ) -> list[tuple[str, str, str, str | None]]:
        detail_rows = document.get("permission_details", [])
        role_codes = {
            role_code.strip()
            for row in detail_rows
            if isinstance((role_code := row.get("role_code")), str) and role_code.strip()
        }
        role_catalog = self._fetch_permission_catalog_map(cursor, role_codes)

        role_scope_map: dict[str, dict[str, Any]] = {}
        for row in detail_rows:
            role_code = self._null_if_blank(row.get("role_code"))
            if role_code is None:
                continue
            role_entry = role_scope_map.setdefault(
                role_code,
                {
                    "role_name": self._null_if_blank(row.get("role_name")),
                    "organization_codes": set(),
                },
            )
            if role_entry["role_name"] is None:
                role_entry["role_name"] = self._null_if_blank(row.get("role_name"))

        for scope in document.get("role_organization_scopes", []):
            role_code = self._null_if_blank(scope.get("role_code"))
            if role_code is None:
                continue
            role_entry = role_scope_map.setdefault(
                role_code,
                {
                    "role_name": self._null_if_blank(scope.get("role_name")),
                    "organization_codes": set(),
                },
            )
            if role_entry["role_name"] is None:
                role_entry["role_name"] = self._null_if_blank(scope.get("role_name"))
            for org_code in scope.get("organization_codes", []):
                normalized_org_code = self._null_if_blank(org_code)
                if normalized_org_code is not None:
                    role_entry["organization_codes"].add(normalized_org_code)

        normalized_rows: set[tuple[str, str, str, str | None]] = set()
        for role_code, role_entry in role_scope_map.items():
            catalog_row = role_catalog.get(role_code, {})
            role_name = (
                role_entry.get("role_name")
                or self._null_if_blank(catalog_row.get("role_name"))
                or role_code
            )
            if bool(catalog_row.get("skip_org_scope_check")):
                normalized_rows.add((document_no, role_code, role_name, None))
                continue
            organization_codes = sorted(role_entry["organization_codes"])
            for org_code in organization_codes:
                normalized_rows.add((document_no, role_code, role_name, org_code))
        return sorted(normalized_rows, key=lambda row: (row[1], row[3] is not None, row[3] or ""))

    def _fetch_permission_catalog_map(self, cursor, role_codes: Iterable[str]) -> dict[str, dict[str, Any]]:
        normalized_codes = sorted({code.strip() for code in role_codes if isinstance(code, str) and code.strip()})
        if not normalized_codes:
            return {}
        if not self._column_exists(cursor, "权限列表", PERMISSION_CATALOG_COLUMNS["role_code"]):
            return {}

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])},
                {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_name"])},
                {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["skip_org_scope_check"])}
            FROM "权限列表"
            WHERE {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])} = ANY(%s)
            """,
            (normalized_codes,),
        )
        rows = cursor.fetchall()
        return {
            str(row[0]): {
                "role_code": str(row[0]),
                "role_name": str(row[1]),
                "skip_org_scope_check": bool(row[2]),
            }
            for row in rows
        }


class PostgresPermissionCatalogStore(_PostgresStoreBase):
    table_name = '"权限列表"'
    schema_sql = Path(__file__).resolve().parents[1] / "sql" / "009_permission_catalog.sql"

    def _needs_schema_update(self, cursor) -> bool:
        if self._column_exists(cursor, "权限列表", "role_code"):
            raise RuntimeError('Detected legacy English schema for "权限列表". Run automation/sql/012_rename_columns_to_cn_fixed_schema.sql first.')

        if not self._column_exists(cursor, "权限列表", PERMISSION_CATALOG_COLUMNS["role_code"]):
            return True

        required_columns = [
            PERMISSION_CATALOG_COLUMNS["role_name"],
            PERMISSION_CATALOG_COLUMNS["permission_level"],
            PERMISSION_CATALOG_COLUMNS["skip_org_scope_check"],
            PERMISSION_CATALOG_COLUMNS["source_system"],
            PERMISSION_CATALOG_COLUMNS["raw_payload"],
            PERMISSION_CATALOG_COLUMNS["created_at"],
            PERMISSION_CATALOG_COLUMNS["updated_at"],
        ]
        legacy_columns = [
            "原始权限级别",
            "归一化分组",
            "是否远程角色",
            "是否已取消角色",
            "是否有效",
        ]

        missing_required_columns = any(
            not self._column_exists(cursor, "权限列表", column_name)
            for column_name in required_columns
        )
        has_legacy_columns = any(
            self._column_exists(cursor, "权限列表", column_name)
            for column_name in legacy_columns
        )
        return missing_required_columns or has_legacy_columns

    def ensure_table(self) -> None:
        ddl = self.schema_sql.read_text(encoding="utf-8")
        with self.connect() as connection:
            with connection.cursor() as cursor:
                if not self._needs_schema_update(cursor):
                    return
                cursor.execute(ddl)

    def seed_catalog(self) -> dict[str, Any]:
        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                total_rows = int(cursor.fetchone()[0])
                cursor.execute(
                    f"""
                    SELECT {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["permission_level"])}, COUNT(*)
                    FROM {self.table_name}
                    GROUP BY {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["permission_level"])}
                    ORDER BY {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["permission_level"])}
                    """
                )
                counts_by_permission_level = [
                    {"permission_level": row[0], "count": int(row[1])}
                    for row in cursor.fetchall()
                ]
        return {
            "table_name": self.table_name.strip('"'),
            "total_rows": total_rows,
            "counts_by_permission_level": counts_by_permission_level,
        }

    def fetch_by_role_codes(self, role_codes: Iterable[str]) -> dict[str, dict[str, Any]]:
        normalized_codes = sorted({code.strip() for code in role_codes if isinstance(code, str) and code.strip()})
        if not normalized_codes:
            return {}

        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])},
                        {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_name"])},
                        {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["permission_level"])},
                        {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["skip_org_scope_check"])}
                    FROM {self.table_name}
                    WHERE {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])} = ANY(%s)
                    """,
                    (normalized_codes,),
                )
                rows = cursor.fetchall()

        return {
            str(row[0]): {
                "role_code": str(row[0]),
                "role_name": str(row[1]),
                "permission_level": str(row[2]),
                "skip_org_scope_check": bool(row[3]),
            }
            for row in rows
        }

    def fetch_skip_org_scope_role_codes(self) -> set[str]:
        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])}
                    FROM {self.table_name}
                    WHERE {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["skip_org_scope_check"])} = TRUE
                    """
                )
                rows = cursor.fetchall()
        return {
            str(row[0]).strip()
            for row in rows
            if row and isinstance(row[0], str) and row[0].strip()
        }


class PostgresActiveRosterStore(_PostgresStoreBase):
    table_name = '"在职花名册表"'
    schema_sql = Path(__file__).resolve().parents[1] / "sql" / "002_active_roster.sql"

    def ensure_table(self) -> None:
        ddl = self.schema_sql.read_text(encoding="utf-8")
        with self.connect() as connection:
            with connection.cursor() as cursor:
                if self._column_exists(cursor, "在职花名册表", "人员编号"):
                    return
                if self._column_exists(cursor, "在职花名册表", "employee_no"):
                    raise RuntimeError('Detected legacy English schema for "在职花名册表". Run automation/sql/012_rename_columns_to_cn_fixed_schema.sql first.')
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
        roster_column_mapping = self._build_physical_mapping(ROSTER_FIELD_SPECS)
        roster_column_mapping["query_date"] = "查询日期"
        roster_column_mapping["source_file_name"] = "来源文件名"
        roster_column_mapping["import_batch_no"] = "导入批次号"
        roster_column_mapping["row_no"] = "导入行号"
        roster_column_mapping["downloaded_at"] = "下载时间"
        roster_column_mapping["imported_at"] = "导入时间"
        roster_column_mapping["extra_columns_json"] = "扩展字段JSON"
        roster_column_mapping["created_at"] = "记录创建时间"
        roster_column_mapping["updated_at"] = "记录更新时间"
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
        insert_columns = [roster_column_mapping[column] for column in roster_columns + metadata_columns + ["created_at", "updated_at"]]
        value_placeholders = [f"%({column})s" for column in roster_columns + metadata_columns]
        value_placeholders.extend(["NOW()", "NOW()"])
        update_columns = [column for column in roster_columns + metadata_columns if column != "employee_no"]

        insert_sql = f"""
            INSERT INTO {self.table_name} (
                {self._quoted_columns(insert_columns)}
            ) VALUES (
                {', '.join(value_placeholders)}
            )
            ON CONFLICT ({self._quote_identifier(roster_column_mapping["employee_no"])}) DO UPDATE SET
                {', '.join(
                    f'{self._quote_identifier(roster_column_mapping[column])} = EXCLUDED.{self._quote_identifier(roster_column_mapping[column])}'
                    for column in update_columns
                )},
                {self._quote_identifier(roster_column_mapping["updated_at"])} = NOW()
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
                if self._column_exists(cursor, "组织列表", "行政组织编码"):
                    return
                if self._column_exists(cursor, "组织列表", "org_code"):
                    raise RuntimeError('Detected legacy English schema for "组织列表". Run automation/sql/012_rename_columns_to_cn_fixed_schema.sql first.')
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
        base_column_mapping = {
            "org_code": "行政组织编码",
            "row_no": "序号",
            "org_name": "行政组织名称",
            "org_type": "行政组织类型",
            "parent_org_name": "上级行政组织",
            "parent_org_code": "上级行政组织编码",
            "established_date": "成立日期",
            "company_name": "所属公司",
            "business_status": "业务状态",
            "org_level": "行政组织层级",
            "org_function": "行政组织职能",
            "city_name": "所在城市",
            "work_location": "工作地",
            "physical_level": "物理层级",
            "pending_disable_date": "待停用日期",
            "department_type": "部门类型",
            "process_level_name": "流程层级_名称",
            "dept_subcategory_code": "部门子分类_编码",
            "dept_subcategory_name": "部门子分类_名称",
            "dept_category_code": "部门分类_编码",
            "dept_category_name": "部门分类_名称",
            "org_created_time": "创建时间",
            "org_full_name": "组织长名称",
            "org_manager_name": "组织负责人",
            "hr_owner_employee_no": "责任HR工号",
            "hr_owner_name": "责任HR姓名",
            "hr_owner_include_children_flag": "责任HR含下级组织",
            "hr_owner_exposed_flag": "责任HR是否透出",
            "source_root_org": "来源根组织",
            "include_all_children": "包含所有下级",
            "source_file_name": "来源文件名",
            "import_batch_no": "导入批次号",
            "created_at": "记录创建时间",
            "updated_at": "记录更新时间",
        }
        with self.connect() as connection:
            with connection.cursor() as cursor:
                self._ensure_extra_columns(cursor, normalized_extra_headers)
                cursor.execute(f"TRUNCATE TABLE {self.table_name}")
                insert_columns = [base_column_mapping[column] for column in self.base_columns] + normalized_extra_headers + [
                    base_column_mapping["created_at"],
                    base_column_mapping["updated_at"],
                ]
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
                        {self._quoted_columns(insert_columns)}
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
        normalized_extra_columns = {
            cls._normalize_physical_column_name(str(header)): value
            for header, value in extra_columns.items()
            if isinstance(header, str)
        }
        for header in extra_headers:
            payload[extra_header_placeholders[header]] = cls._null_if_blank(normalized_extra_columns.get(header))
        return payload

    def _ensure_extra_columns(self, cursor, extra_headers: Iterable[str]) -> None:
        for header in extra_headers:
            cursor.execute(
                f"ALTER TABLE {self.table_name} ADD COLUMN IF NOT EXISTS {self._quote_identifier(self._normalize_physical_column_name(header))} TEXT"
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
            physical_header = cls._normalize_physical_column_name(normalized_header)
            if physical_header in seen:
                return
            seen.add(physical_header)
            ordered_headers.append(physical_header)

        for header in extra_headers or []:
            append_header(header)
        for row in rows:
            for header in row.get("extra_columns", {}).keys():
                append_header(header)
        return ordered_headers

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'
