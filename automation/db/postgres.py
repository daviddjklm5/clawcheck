from __future__ import annotations
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date, datetime
import json
from pathlib import Path
import re
import threading
from typing import Any

from automation.utils.approval_record_helpers import (
    collect_unresolved_approver_names,
    derive_latest_approval_time,
    normalize_approval_records,
)
from automation.utils.config_loader import DatabaseSettings
from automation.reporting.low_score_feedback import (
    build_low_score_feedback,
    display_summary_conclusion,
)
from automation.rules.role_facts import build_detail_role_facts

try:
    import psycopg
except ModuleNotFoundError:  # pragma: no cover
    psycopg = None


BASIC_INFO_TABLE = '"申请单基本信息"'
PERMISSION_APPLY_DETAIL_TABLE = '"申请单权限列表"'
APPROVAL_RECORD_TABLE = '"申请单审批记录"'
APPLY_FORM_ORG_SCOPE_TABLE = '"申请表组织范围"'
PERSON_ATTRIBUTES_TABLE = '"人员属性查询"'
RISK_TRUST_ASSESSMENT_TABLE = '"申请单风险信任评估"'
RISK_TRUST_ASSESSMENT_DETAIL_TABLE = '"申请单风险信任评估明细"'
RISK_TRUST_LOW_SCORE_ENRICHED_VIEW = '"申请单低分明细富化视图"'
RISK_TRUST_LOW_SCORE_FEEDBACK_GROUP_VIEW = '"申请单低分反馈预聚合视图"'

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

PERSON_ATTRIBUTES_COLUMNS = {
    "employee_no": "工号",
    "employee_name": "姓名",
    "department_id": "部门ID",
    "level1_function_name": "一级职能名称",
    "level2_function_name": "二级职能名称",
    "position_name": "职位名称",
    "standard_position_name": "标准岗位名称",
    "org_path_name": "组织路径名称",
    "wanyu_city_sales_department": "万御城市营业部",
    "responsible_hr_employee_no": "责任HR工号",
    "responsible_hr_import_batch_no": "责任HR导入批次号",
    "roster_query_date": "花名册查询日期",
    "roster_import_batch_no": "花名册导入批次号",
    "roster_match_status": "花名册匹配状态",
    "hr_type": "申请人HR类型",
    "is_responsible_hr": "是否责任HR",
    "is_hr_staff": "是否HR人员",
    "is_suspected_hr_staff": "是否疑似HR人员",
    "hr_primary_evidence": "HR主判定依据",
    "hr_primary_value": "HR主判定值",
    "hr_subdomain": "HR子域",
    "hr_judgement_reason": "HR判定原因",
    "created_at": "记录创建时间",
    "updated_at": "记录更新时间",
}

ORG_ATTRIBUTE_COLUMNS = {
    "org_code": "行政组织编码",
    "org_name": "行政组织名称",
    "process_level_category": "组织流程层级分类",
    "org_auth_level": "组织授权级别",
    "org_unit_name": "组织单位",
    "physical_level": "物理层级",
    "war_zone": "所属战区",
}

RISK_TRUST_ASSESSMENT_COLUMNS = {
    "id": "评估ID",
    "document_no": "单据编号",
    "assessment_batch_no": "评估批次号",
    "assessment_version": "评估版本",
    "applicant_hr_type": "申请人HR类型",
    "applicant_process_level_category": "申请人组织流程层级分类",
    "final_score": "最终信任分",
    "summary_conclusion": "总结论",
    "suggested_action": "建议动作",
    "lowest_hit_dimension": "最低命中维度",
    "lowest_hit_role_code": "最低命中角色编码",
    "lowest_hit_org_code": "最低命中组织编码",
    "hit_manual_review": "是否命中人工干预",
    "has_low_score_details": "是否存在低分明细",
    "low_score_detail_count": "低分明细条数",
    "low_score_detail_conclusion": "低分明细结论",
    "assessment_explain": "评估说明",
    "input_snapshot": "输入快照",
    "assessed_at": "评估时间",
    "created_at": "记录创建时间",
    "updated_at": "记录更新时间",
}

RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS = {
    "id": "评估明细ID",
    "document_no": "单据编号",
    "assessment_batch_no": "评估批次号",
    "assessment_version": "评估版本",
    "role_code": "角色编码",
    "role_name": "角色名称",
    "org_code": "组织编码",
    "dimension_name": "维度名称",
    "rule_id": "命中规则编码",
    "rule_summary": "命中规则说明",
    "score": "维度得分",
    "detail_conclusion": "明细结论",
    "is_low_score": "是否低分明细",
    "intervention_action": "建议干预动作",
    "evidence_summary": "证据摘要",
    "evidence_snapshot": "证据快照",
    "assessed_at": "评估时间",
    "created_at": "记录创建时间",
}

APPLICANT_HR_PATH_KEYWORDS = ("人力", "人事", "组织发展中心", "组织人才中心")
APPLICANT_HR_H1_POSITION_KEYWORD_PATTERN = re.compile(
    r"(人力|人事|HRBP|HR共享|业务HR|项目HR|综合人事|人力资源|人力行政|人力业务支持|hrbp|hr)",
    re.IGNORECASE,
)
APPLICANT_HR_H1_STANDARD_POSITION_PATTERN = re.compile(
    r"(人力|人事|HRBP|HR共享|综合人事|人力资源|人力行政|人力业务支持|人力综合|hrbp|hr)",
    re.IGNORECASE,
)
APPLICANT_HR_H1_ORG_DEV_PATTERN = re.compile(r"(组织发展|薪酬|绩效|福利)")
APPLICANT_HR_H2_MANAGEMENT_POSITION_PATTERN = re.compile(r"(总裁|总经理)")
APPLICANT_HR_H2_POSITION_WHITELIST = {
    "组织与效能资深总监",
    "部门负责人",
    "AI与流程变革资深总监",
    "平台与运营资深总监",
}
APPLICANT_HR_H2_WEAK_SIGNAL_POSITION_WHITELIST = {
    "运营经理",
    "运营主管",
    "数据分析",
}
APPLICANT_HR_H2_SPECIAL_ORG_UNIT = "人力资源与行政服务中心"
APPLICANT_HR_H2_EMPLOYEE_EXPERIENCE_POSITION_PATTERN = re.compile(r"员工体验与行政")
APPLICANT_HR_H1_WANYU_POSITION_WHITELIST = {
    "认证中心负责人",
    "服务站总站长",
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
                "Missing dependency: psycopg. Run `.venv/bin/python -m pip install -r automation/requirements.txt`."
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

    @staticmethod
    def _strip_text(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        normalized = str(value).strip()
        return normalized or None

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

    @staticmethod
    def _table_exists(cursor, table_name: str) -> bool:
        cursor.execute(
            """
            SELECT to_regclass(current_schema() || '.' || quote_ident(%s)) IS NOT NULL
            """,
            (table_name,),
        )
        row = cursor.fetchone()
        return bool(row[0]) if row else False


class PostgresPermissionStore(_PostgresStoreBase):
    _ensure_table_lock = threading.Lock()
    _ensured_schema_keys: set[tuple[str, int, str, str]] = set()
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

    @classmethod
    def _is_hr_org_path(cls, org_path_name: str | None) -> bool:
        if org_path_name is None:
            return False
        return any(keyword in org_path_name for keyword in APPLICANT_HR_PATH_KEYWORDS)

    @classmethod
    def _build_applicant_hr_tags(cls, applicant_profile: dict[str, Any]) -> dict[str, Any]:
        employee_no = cls._strip_text(applicant_profile.get("employee_no"))
        level1_function_name = cls._strip_text(applicant_profile.get("level1_function_name"))
        level2_function_name = cls._strip_text(applicant_profile.get("level2_function_name"))
        position_name = cls._strip_text(applicant_profile.get("position_name"))
        standard_position_name = cls._strip_text(applicant_profile.get("standard_position_name"))
        org_path_name = cls._strip_text(applicant_profile.get("org_path_name"))
        org_unit_name = cls._strip_text(applicant_profile.get("org_unit_name"))
        wanyu_city_sales_department = cls._strip_text(applicant_profile.get("wanyu_city_sales_department"))
        employee_name = cls._strip_text(applicant_profile.get("employee_name"))
        is_responsible_hr = bool(applicant_profile.get("is_responsible_hr"))
        is_hr_org_path = cls._is_hr_org_path(org_path_name)

        result = {
            "roster_match_status": "UNMATCHED" if employee_name is None else "MATCHED",
            "hr_type": None,
            "is_responsible_hr": is_responsible_hr,
            "is_hr_staff": False,
            "is_suspected_hr_staff": False,
            "hr_primary_evidence": None,
            "hr_primary_value": None,
            "hr_subdomain": None,
            "hr_judgement_reason": "roster_not_found" if employee_name is None else "no_hr_signal",
        }

        if employee_name is None:
            return result

        if level1_function_name == "人力资源":
            hr_type = "H1"
            hr_primary_evidence = "level1_function_name"
            hr_primary_value = level1_function_name
            hr_judgement_reason = "level1_is_hr"
        elif position_name is not None and APPLICANT_HR_H1_POSITION_KEYWORD_PATTERN.search(position_name):
            hr_type = "H1"
            hr_primary_evidence = "position_name"
            hr_primary_value = position_name
            hr_judgement_reason = "position_keyword_hit"
        elif position_name == "目标与绩效管理专业总监" and is_hr_org_path:
            hr_type = "H1"
            hr_primary_evidence = "position_name"
            hr_primary_value = position_name
            hr_judgement_reason = "position_org_dev_comp_perf_benefit_hit"
        elif (
            position_name is not None
            and position_name != "目标与绩效管理专业总监"
            and APPLICANT_HR_H1_ORG_DEV_PATTERN.search(position_name)
        ):
            hr_type = "H1"
            hr_primary_evidence = "position_name"
            hr_primary_value = position_name
            hr_judgement_reason = "position_org_dev_comp_perf_benefit_hit"
        elif standard_position_name is not None and APPLICANT_HR_H1_STANDARD_POSITION_PATTERN.search(standard_position_name):
            hr_type = "H1"
            hr_primary_evidence = "standard_position_name"
            hr_primary_value = standard_position_name
            hr_judgement_reason = "standard_position_keyword_hit"
        elif wanyu_city_sales_department is not None and position_name in APPLICANT_HR_H1_WANYU_POSITION_WHITELIST:
            hr_type = "H1"
            hr_primary_evidence = "wanyu_city_sales_department"
            hr_primary_value = wanyu_city_sales_department
            hr_judgement_reason = "wanyu_city_sales_department_position_hit"
        elif is_hr_org_path and (
            position_name in APPLICANT_HR_H2_POSITION_WHITELIST
            or (position_name is not None and APPLICANT_HR_H2_MANAGEMENT_POSITION_PATTERN.search(position_name))
        ):
            hr_type = "H2"
            hr_primary_evidence = "position_name"
            hr_primary_value = position_name
            hr_judgement_reason = "weak_signal_management_position_promoted_to_h2"
        elif is_hr_org_path and position_name in APPLICANT_HR_H2_WEAK_SIGNAL_POSITION_WHITELIST:
            hr_type = "H2"
            hr_primary_evidence = "position_name"
            hr_primary_value = position_name
            hr_judgement_reason = "weak_signal_position_promoted_to_h2"
        elif (
            org_unit_name == APPLICANT_HR_H2_SPECIAL_ORG_UNIT
            and position_name is not None
            and APPLICANT_HR_H2_EMPLOYEE_EXPERIENCE_POSITION_PATTERN.search(position_name)
        ):
            hr_type = "H2"
            hr_primary_evidence = "org_unit_name+position_name"
            hr_primary_value = f"{org_unit_name}|{position_name}"
            hr_judgement_reason = "org_unit_employee_experience_position_promoted_to_h2"
        elif is_responsible_hr:
            hr_type = "H3"
            hr_primary_evidence = "responsible_hr_employee_no"
            hr_primary_value = employee_no
            hr_judgement_reason = "responsible_hr_hit"
        elif is_hr_org_path:
            hr_type = "HY"
            hr_primary_evidence = "org_path_name"
            hr_primary_value = org_path_name
            hr_judgement_reason = "org_path_keyword_hit_only"
        else:
            hr_type = "HX"
            hr_primary_evidence = None
            hr_primary_value = None
            hr_judgement_reason = "no_hr_signal"

        hr_subdomain = None
        if hr_type in {"H1", "H2"}:
            if position_name is not None and APPLICANT_HR_H2_MANAGEMENT_POSITION_PATTERN.search(position_name):
                hr_subdomain = "hr_management"
            elif level2_function_name == "人力资源":
                hr_subdomain = "hr_general"
            elif level2_function_name == "人事运营":
                hr_subdomain = "hr_operations"
            elif level2_function_name in {"招聘", "招聘外包服务"}:
                hr_subdomain = "recruiting"
            elif level2_function_name == "薪酬绩效":
                hr_subdomain = "compensation_performance"
            elif level2_function_name == "员工关系":
                hr_subdomain = "employee_relations"
            elif level2_function_name in {"人才发展", "组织发展"}:
                hr_subdomain = "org_talent_development"
            elif level2_function_name == "人力业务支持":
                hr_subdomain = "hr_business_support"
            elif level1_function_name in {"管理", "职能综合管理"}:
                hr_subdomain = "hr_management"
            else:
                hr_subdomain = "other_hr_domain"

        result.update(
            {
                "hr_type": hr_type,
                "is_hr_staff": hr_type in {"H1", "H2", "H3"},
                "is_suspected_hr_staff": hr_type == "HY",
                "hr_primary_evidence": hr_primary_evidence,
                "hr_primary_value": hr_primary_value,
                "hr_subdomain": hr_subdomain,
                "hr_judgement_reason": hr_judgement_reason,
            }
        )
        return result

    def _fetch_applicant_hr_profiles(
        self,
        cursor,
        employee_nos: Iterable[str],
    ) -> dict[str, dict[str, Any]]:
        normalized_employee_nos = sorted(
            {
                employee_no
                for value in employee_nos
                if (employee_no := self._strip_text(value)) is not None
            }
        )
        if not normalized_employee_nos:
            return {}

        roster_profiles: dict[str, dict[str, Any]] = {
            employee_no: {
                "employee_no": employee_no,
                "employee_name": None,
                "roster_query_date": None,
                "roster_import_batch_no": None,
                "level1_function_name": None,
                "level2_function_name": None,
                "position_name": None,
                "standard_position_name": None,
                "org_path_name": None,
                "department_id": None,
                "org_unit_name": None,
                "wanyu_city_sales_department": None,
                "responsible_hr_employee_no": None,
                "responsible_hr_import_batch_no": None,
                "is_responsible_hr": False,
            }
            for employee_no in normalized_employee_nos
        }

        has_roster_table = self._table_exists(cursor, "在职花名册表")
        roster_required_columns = (
            "人员编号",
            "部门ID",
            "查询日期",
            "导入批次号",
            "姓名",
            "一级职能名称",
            "二级职能名称",
            "职位名称",
            "标准岗位名称",
            "组织路径名称",
        )
        if has_roster_table and all(self._column_exists(cursor, "在职花名册表", column_name) for column_name in roster_required_columns):
            cursor.execute(
                """
                SELECT
                    BTRIM("人员编号") AS employee_no,
                    BTRIM("部门ID") AS department_id,
                    "查询日期",
                    "导入批次号",
                    "姓名",
                    "一级职能名称",
                    "二级职能名称",
                    "职位名称",
                    "标准岗位名称",
                    "组织路径名称"
                FROM "在职花名册表"
                WHERE BTRIM("人员编号") = ANY(%s)
                """,
                (normalized_employee_nos,),
            )
            for row in cursor.fetchall():
                employee_no = self._strip_text(row[0])
                if employee_no is None:
                    continue
                roster_profiles[employee_no].update(
                    {
                        "roster_query_date": row[2],
                        "roster_import_batch_no": self._strip_text(row[3]),
                        "employee_name": self._strip_text(row[4]),
                        "level1_function_name": self._strip_text(row[5]),
                        "level2_function_name": self._strip_text(row[6]),
                        "position_name": self._strip_text(row[7]),
                        "standard_position_name": self._strip_text(row[8]),
                        "org_path_name": self._strip_text(row[9]),
                        "department_id": self._strip_text(row[1]),
                    }
                )

        department_ids = sorted(
            {
                department_id
                for profile in roster_profiles.values()
                if (department_id := self._strip_text(profile.get("department_id"))) is not None
            }
        )
        org_attr_by_code: dict[str, dict[str, str | None]] = {}
        if (
            department_ids
            and self._table_exists(cursor, "组织属性查询")
            and self._column_exists(cursor, "组织属性查询", "行政组织编码")
        ):
            has_wanyu_city_sales_department = self._column_exists(cursor, "组织属性查询", "万御城市营业部")
            has_org_unit_name = self._column_exists(cursor, "组织属性查询", "组织单位")
            if has_wanyu_city_sales_department or has_org_unit_name:
                wanyu_city_sales_department_select = (
                    '"万御城市营业部"' if has_wanyu_city_sales_department else 'NULL::TEXT AS "万御城市营业部"'
                )
                org_unit_name_select = '"组织单位"' if has_org_unit_name else 'NULL::TEXT AS "组织单位"'
                cursor.execute(
                    f"""
                    SELECT
                        BTRIM("行政组织编码") AS org_code,
                        {wanyu_city_sales_department_select},
                        {org_unit_name_select}
                    FROM "组织属性查询"
                    WHERE BTRIM("行政组织编码") = ANY(%s)
                    """,
                    (department_ids,),
                )
                org_attr_by_code = {
                    org_code: {
                        "wanyu_city_sales_department": self._strip_text(row[1]),
                        "org_unit_name": self._strip_text(row[2]),
                    }
                    for row in cursor.fetchall()
                    if (org_code := self._strip_text(row[0])) is not None
                }

        responsible_hr_employee_nos: set[str] = set()
        responsible_hr_import_batch_no: str | None = None
        if (
            self._table_exists(cursor, "组织列表")
            and self._column_exists(cursor, "组织列表", "责任HR工号")
            and self._column_exists(cursor, "组织列表", "导入批次号")
            and self._column_exists(cursor, "组织列表", "记录创建时间")
        ):
            cursor.execute(
                """
                SELECT "导入批次号"
                FROM "组织列表"
                ORDER BY "记录创建时间" DESC
                LIMIT 1
                """,
            )
            row = cursor.fetchone()
            responsible_hr_import_batch_no = self._strip_text(row[0]) if row else None

            cursor.execute(
                """
                SELECT DISTINCT BTRIM("责任HR工号") AS employee_no
                FROM "组织列表"
                WHERE "导入批次号" = %s
                  AND NULLIF(BTRIM("责任HR工号"), '') IS NOT NULL
                """,
                (responsible_hr_import_batch_no,),
            )
            responsible_hr_employee_nos = {
                employee_no
                for row in cursor.fetchall()
                if (employee_no := self._strip_text(row[0])) is not None
            }

        for employee_no, profile in roster_profiles.items():
            department_id = self._strip_text(profile.get("department_id"))
            org_attr = org_attr_by_code.get(department_id, {})
            profile["wanyu_city_sales_department"] = org_attr.get("wanyu_city_sales_department")
            profile["org_unit_name"] = org_attr.get("org_unit_name")
            profile["is_responsible_hr"] = employee_no in responsible_hr_employee_nos
            profile["responsible_hr_employee_no"] = employee_no if profile["is_responsible_hr"] else None
            profile["responsible_hr_import_batch_no"] = responsible_hr_import_batch_no if profile["is_responsible_hr"] else None

        return roster_profiles

    def ensure_table(self) -> None:
        schema_key = (
            self.settings.host,
            self.settings.port,
            self.settings.dbname,
            self.settings.schema,
        )
        if schema_key in self._ensured_schema_keys:
            return

        ddl = self.schema_sql.read_text(encoding="utf-8")
        with self._ensure_table_lock:
            if schema_key in self._ensured_schema_keys:
                return

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

            self._ensured_schema_keys.add(schema_key)

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

    @staticmethod
    def _format_datetime_value(value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        return str(value)

    @staticmethod
    def _format_bool_label(value: Any) -> str:
        return "是" if bool(value) else "否"

    @staticmethod
    def _build_collect_status(permission_count: int, approval_count: int, org_scope_count: int) -> str:
        if permission_count <= 0 or org_scope_count <= 0:
            return "待补采"
        if approval_count <= 0:
            return "审批为空"
        return "已落库"

    def _empty_collect_workbench(self) -> dict[str, Any]:
        return {
            "stats": [
                {
                    "label": "已入库单据",
                    "value": "0",
                    "hint": "当前申请单四张表中还没有采集结果。",
                    "tone": "info",
                },
                {
                    "label": "待补采单据",
                    "value": "0",
                    "hint": "当角色明细或组织范围缺失时会计入待补采。",
                    "tone": "success",
                },
                {
                    "label": "审批为空单据",
                    "value": "0",
                    "hint": "审批记录为空时单独提示，避免与待补采混淆。",
                    "tone": "default",
                },
                {
                    "label": "最近落库时间",
                    "value": "-",
                    "hint": "执行采集任务后会显示最新落库时间。",
                    "tone": "default",
                },
            ],
            "documents": [],
        }

    def _fetch_collect_table_metrics(
        self,
        cursor,
        document_nos: Iterable[str],
    ) -> dict[str, dict[str, dict[str, Any]]]:
        normalized_document_nos = [document_no for document_no in document_nos if document_no]
        if not normalized_document_nos:
            return {}

        metrics: dict[str, dict[str, dict[str, Any]]] = {
            document_no: {
                "basic": {"records": 0, "updated_at": None},
                "permission": {"records": 0, "updated_at": None},
                "approval": {"records": 0, "updated_at": None},
                "orgScope": {"records": 0, "updated_at": None},
            }
            for document_no in normalized_document_nos
        }

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])},
                COUNT(*)::INTEGER AS records,
                MAX({self._quote_identifier(BASIC_INFO_COLUMNS["updated_at"])}) AS updated_at
            FROM {BASIC_INFO_TABLE}
            WHERE {self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])} = ANY(%s)
            GROUP BY {self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])}
            """,
            (normalized_document_nos,),
        )
        for row in cursor.fetchall():
            document_no = self._strip_text(row[0])
            if document_no is None:
                continue
            metrics.setdefault(document_no, {}).setdefault("basic", {})
            metrics[document_no]["basic"] = {
                "records": int(row[1] or 0),
                "updated_at": row[2],
            }

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])},
                COUNT(*)::INTEGER AS records,
                MAX({self._quote_identifier(PERMISSION_DETAIL_COLUMNS["updated_at"])}) AS updated_at
            FROM {PERMISSION_APPLY_DETAIL_TABLE}
            WHERE {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])} = ANY(%s)
            GROUP BY {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])}
            """,
            (normalized_document_nos,),
        )
        for row in cursor.fetchall():
            document_no = self._strip_text(row[0])
            if document_no is None:
                continue
            metrics.setdefault(document_no, {}).setdefault("permission", {})
            metrics[document_no]["permission"] = {
                "records": int(row[1] or 0),
                "updated_at": row[2],
            }

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])},
                COUNT(*)::INTEGER AS records,
                MAX({self._quote_identifier(APPROVAL_RECORD_COLUMNS["created_at"])}) AS updated_at
            FROM {APPROVAL_RECORD_TABLE}
            WHERE {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])} = ANY(%s)
            GROUP BY {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])}
            """,
            (normalized_document_nos,),
        )
        for row in cursor.fetchall():
            document_no = self._strip_text(row[0])
            if document_no is None:
                continue
            metrics.setdefault(document_no, {}).setdefault("approval", {})
            metrics[document_no]["approval"] = {
                "records": int(row[1] or 0),
                "updated_at": row[2],
            }

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])},
                COUNT(*)::INTEGER AS records,
                MAX({self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["created_at"])}) AS updated_at
            FROM {APPLY_FORM_ORG_SCOPE_TABLE}
            WHERE {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])} = ANY(%s)
            GROUP BY {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])}
            """,
            (normalized_document_nos,),
        )
        for row in cursor.fetchall():
            document_no = self._strip_text(row[0])
            if document_no is None:
                continue
            metrics.setdefault(document_no, {}).setdefault("orgScope", {})
            metrics[document_no]["orgScope"] = {
                "records": int(row[1] or 0),
                "updated_at": row[2],
            }

        return metrics

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

    def fetch_collect_workbench(self, limit: int = 200) -> dict[str, Any]:
        query_limit = max(limit, 0)

        self.ensure_table()
        helper_store = PostgresRiskTrustStore(self.settings)
        with self.connect() as connection:
            with connection.cursor() as cursor:
                basic_rows = helper_store._fetch_basic_info_rows(cursor, document_no=None, limit=query_limit)
                if not basic_rows:
                    return self._empty_collect_workbench()

                document_nos = [row["document_no"] for row in basic_rows]
                table_metrics = self._fetch_collect_table_metrics(cursor, document_nos)
                applicant_profiles = helper_store._fetch_person_attributes_map(
                    cursor,
                    [row["employee_no"] for row in basic_rows],
                )

        documents: list[dict[str, Any]] = []
        pending_count = 0
        approval_empty_count = 0
        latest_collected_at: datetime | date | str | None = None

        for basic_row in basic_rows:
            document_no = basic_row["document_no"]
            applicant_profile = applicant_profiles.get(basic_row["employee_no"] or "", {})
            metrics = table_metrics.get(document_no, {})
            permission_count = int(metrics.get("permission", {}).get("records") or 0)
            approval_count = int(metrics.get("approval", {}).get("records") or 0)
            org_scope_count = int(metrics.get("orgScope", {}).get("records") or 0)
            collect_status = self._build_collect_status(permission_count, approval_count, org_scope_count)

            if collect_status == "待补采":
                pending_count += 1
            elif collect_status == "审批为空":
                approval_empty_count += 1

            collected_at_value = metrics.get("basic", {}).get("updated_at") or basic_row.get("updated_at")
            if collected_at_value is not None and (
                latest_collected_at is None or collected_at_value > latest_collected_at
            ):
                latest_collected_at = collected_at_value

            documents.append(
                {
                    "id": document_no,
                    "documentNo": document_no,
                    "applicantName": self._strip_text(applicant_profile.get("employee_name")) or "-",
                    "applicantNo": basic_row["employee_no"] or "-",
                    "permissionTarget": basic_row["permission_target"] or "-",
                    "departmentName": basic_row["department_name"] or "-",
                    "documentStatus": basic_row["document_status"] or "-",
                    "collectStatus": collect_status,
                    "applyTime": self._format_datetime_value(basic_row["apply_time"]),
                    "latestApprovalTime": self._format_datetime_value(basic_row["latest_approval_time"]),
                    "collectedAt": self._format_datetime_value(collected_at_value),
                    "roleCount": permission_count,
                    "approvalCount": approval_count,
                    "orgScopeCount": org_scope_count,
                    "collectionCount": int(basic_row["collection_count"] or 1),
                }
            )

        return {
            "stats": [
                {
                    "label": "已入库单据",
                    "value": str(len(documents)),
                    "hint": "来自 `申请单基本信息` 中当前可查询到的单据数。",
                    "tone": "info" if documents else "default",
                },
                {
                    "label": "待补采单据",
                    "value": str(pending_count),
                    "hint": "角色明细或组织范围缺失时会计入待补采。",
                    "tone": "warning" if pending_count else "success",
                },
                {
                    "label": "审批为空单据",
                    "value": str(approval_empty_count),
                    "hint": "审批记录为空时单独标识，避免误判为主表缺失。",
                    "tone": "info" if approval_empty_count else "default",
                },
                {
                    "label": "最近落库时间",
                    "value": self._format_datetime_value(latest_collected_at),
                    "hint": "取 `申请单基本信息.记录更新时间` 的最新值。",
                    "tone": "default",
                },
            ],
            "documents": documents,
        }

    def fetch_collect_document_detail(self, document_no: str) -> dict[str, Any] | None:
        normalized_document_no = self._strip_text(document_no)
        if normalized_document_no is None:
            return None

        self.ensure_table()
        helper_store = PostgresRiskTrustStore(self.settings)
        with self.connect() as connection:
            with connection.cursor() as cursor:
                basic_rows = helper_store._fetch_basic_info_rows(cursor, document_no=normalized_document_no, limit=1)
                if not basic_rows:
                    return None

                basic_row = basic_rows[0]
                detail_rows = helper_store._fetch_permission_detail_rows(cursor, [normalized_document_no])
                approval_rows = helper_store._fetch_approval_rows(cursor, [normalized_document_no])
                org_scope_rows = helper_store._fetch_org_scope_rows(cursor, [normalized_document_no])
                table_metrics = self._fetch_collect_table_metrics(cursor, [normalized_document_no]).get(
                    normalized_document_no,
                    {},
                )
                applicant_profiles = helper_store._fetch_person_attributes_map(
                    cursor,
                    [basic_row["employee_no"]],
                )
                permission_catalog = helper_store._fetch_permission_catalog_rows(
                    cursor,
                    [row["role_code"] for row in [*detail_rows, *org_scope_rows]],
                )
                org_attributes = helper_store._fetch_org_attributes_map(
                    cursor,
                    [row["org_code"] for row in org_scope_rows],
                )

        applicant_profile = applicant_profiles.get(basic_row["employee_no"] or "", {})
        permission_count = int(table_metrics.get("permission", {}).get("records") or 0)
        approval_count = int(table_metrics.get("approval", {}).get("records") or 0)
        org_scope_count = int(table_metrics.get("orgScope", {}).get("records") or 0)
        collect_status = self._build_collect_status(permission_count, approval_count, org_scope_count)

        notes: list[str] = []
        if collect_status == "待补采":
            notes.append("当前单据仍存在待补采表，请优先重跑当前单据并核对角色明细与组织范围。")
        if collect_status == "审批为空":
            notes.append("当前审批记录为空，请确认该单据在 iERP 页面是否尚未产生审批轨迹。")
        if int(basic_row["collection_count"] or 1) > 1:
            notes.append(f"该单据已发生重采 {int(basic_row['collection_count'] or 1)} 次。")
        if not notes:
            notes.append("当前四张申请单表已形成可查询的采集闭环。")

        return {
            "documentNo": normalized_document_no,
            "collectStatus": collect_status,
            "overviewFields": [
                {"label": "单据编号", "value": normalized_document_no, "hint": "主键来自 `申请单基本信息`。"},
                {
                    "label": "申请人",
                    "value": self._strip_text(applicant_profile.get("employee_name")) or "-",
                    "hint": "通过 `申请单基本信息.工号 -> 人员属性查询.工号` 关联得到。",
                },
                {"label": "工号", "value": basic_row["employee_no"] or "-", "hint": "申请人主键。"},
                {"label": "权限对象", "value": basic_row["permission_target"] or "-", "hint": "来自主表字段。"},
                {"label": "单据状态", "value": basic_row["document_status"] or "-", "hint": "业务单据自身状态。"},
                {"label": "采集状态", "value": collect_status, "hint": "根据四张表当前落库情况推导。"},
                {"label": "公司", "value": basic_row["company_name"] or "-", "hint": "来自主表。"},
                {"label": "部门", "value": basic_row["department_name"] or "-", "hint": "来自主表。"},
                {"label": "职位", "value": basic_row["position_name"] or "-", "hint": "来自主表。"},
                {"label": "申请日期", "value": self._format_datetime_value(basic_row["apply_time"]), "hint": "来自 iERP 页面。"},
                {
                    "label": "最新审批时间",
                    "value": self._format_datetime_value(basic_row["latest_approval_time"]),
                    "hint": "由审批记录归一化后回填。",
                },
                {
                    "label": "申请人HR类型",
                    "value": self._strip_text(applicant_profile.get("hr_type")) or "-",
                    "hint": "来自 `人员属性查询`。",
                },
                {
                    "label": "采集次数",
                    "value": str(int(basic_row["collection_count"] or 1)),
                    "hint": "由 `017` 重采策略维护。",
                },
                {
                    "label": "最近落库时间",
                    "value": self._format_datetime_value(table_metrics.get("basic", {}).get("updated_at") or basic_row.get("updated_at")),
                    "hint": "取 `申请单基本信息.记录更新时间`。",
                },
            ],
            "tableStatus": [
                {
                    "id": "basic",
                    "tableName": "申请单基本信息",
                    "status": "已落库" if int(table_metrics.get("basic", {}).get("records") or 0) > 0 else "待补采",
                    "records": int(table_metrics.get("basic", {}).get("records") or 0),
                    "updatedAt": self._format_datetime_value(table_metrics.get("basic", {}).get("updated_at")),
                    "remark": "主表，单据编号为业务主键。",
                },
                {
                    "id": "permission",
                    "tableName": "申请单权限列表",
                    "status": "已落库" if permission_count > 0 else "待补采",
                    "records": permission_count,
                    "updatedAt": self._format_datetime_value(table_metrics.get("permission", {}).get("updated_at")),
                    "remark": "角色级明细，包含角色编码、角色名称、申请类型。",
                },
                {
                    "id": "approval",
                    "tableName": "申请单审批记录",
                    "status": "已落库" if approval_count > 0 else "审批为空",
                    "records": approval_count,
                    "updatedAt": self._format_datetime_value(table_metrics.get("approval", {}).get("updated_at")),
                    "remark": "审批轨迹可能为空，不直接等同主表缺失。",
                },
                {
                    "id": "orgScope",
                    "tableName": "申请表组织范围",
                    "status": "已落库" if org_scope_count > 0 else "待补采",
                    "records": org_scope_count,
                    "updatedAt": self._format_datetime_value(table_metrics.get("orgScope", {}).get("updated_at")),
                    "remark": "按 `013` 方案以角色-组织粒度展开。",
                },
            ],
            "roles": [
                {
                    "id": f"{normalized_document_no}-{row['line_no'] or index}",
                    "lineNo": row["line_no"] or "-",
                    "applyType": row["apply_type"] or "-",
                    "roleCode": row["role_code"] or "-",
                    "roleName": row["role_name"] or permission_catalog.get(row["role_code"] or "", {}).get("role_name") or "-",
                    "permissionLevel": permission_catalog.get(row["role_code"] or "", {}).get("permission_level") or "-",
                    "orgScopeCount": int(row["org_scope_count"] or 0),
                    "skipOrgScopeCheck": self._format_bool_label(
                        permission_catalog.get(row["role_code"] or "", {}).get("skip_org_scope_check"),
                    ),
                }
                for index, row in enumerate(detail_rows, start=1)
            ],
            "approvals": [
                {
                    "id": f"{normalized_document_no}-{row['record_seq'] or index}",
                    "nodeName": row["node_name"] or "-",
                    "approver": " / ".join(
                        item
                        for item in [row["approver_name"] or "-", row["approver_employee_no"] or ""]
                        if item
                    ),
                    "action": row["approval_action"] or "-",
                    "finishedAt": self._format_datetime_value(row["approval_time"]),
                    "comment": row["approval_opinion"] or row["raw_text"] or "-",
                }
                for index, row in enumerate(approval_rows, start=1)
            ],
            "orgScopes": [
                {
                    "id": f"{normalized_document_no}-{row['role_code'] or 'role'}-{row['org_code'] or 'null'}-{index}",
                    "roleCode": row["role_code"] or "-",
                    "roleName": row["role_name"] or permission_catalog.get(row["role_code"] or "", {}).get("role_name") or "-",
                    "organizationCode": row["org_code"] or "-",
                    "organizationName": org_attributes.get(row["org_code"] or "", {}).get("org_name") or "-",
                    "orgUnitName": org_attributes.get(row["org_code"] or "", {}).get("org_unit_name") or "-",
                    "physicalLevel": org_attributes.get(row["org_code"] or "", {}).get("physical_level") or "-",
                    "skipOrgScopeCheck": self._format_bool_label(
                        permission_catalog.get(row["role_code"] or "", {}).get("skip_org_scope_check"),
                    ),
                }
                for index, row in enumerate(org_scope_rows, start=1)
            ],
            "notes": notes,
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


class PostgresPersonAttributesStore(_PostgresStoreBase):
    table_name = PERSON_ATTRIBUTES_TABLE
    schema_sql = Path(__file__).resolve().parents[1] / "sql" / "019_person_attributes.sql"

    @classmethod
    def _build_applicant_hr_tags(cls, applicant_profile: dict[str, Any]) -> dict[str, Any]:
        return PostgresPermissionStore._build_applicant_hr_tags(applicant_profile)

    def _ensure_schema(self, cursor) -> None:
        if self._column_exists(cursor, "人员属性查询", "employee_no"):
            raise RuntimeError('Detected legacy English schema for "人员属性查询". Run automation/sql/012_rename_columns_to_cn_fixed_schema.sql first.')
        cursor.execute(self.schema_sql.read_text(encoding="utf-8"))

    def ensure_table(self) -> None:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                self._ensure_schema(cursor)

    def _fetch_roster_employee_nos(self, cursor) -> list[str]:
        if (
            not self._table_exists(cursor, "在职花名册表")
            or not self._column_exists(cursor, "在职花名册表", "人员编号")
        ):
            return []

        cursor.execute(
            """
            SELECT BTRIM("人员编号") AS employee_no
            FROM "在职花名册表"
            WHERE NULLIF(BTRIM("人员编号"), '') IS NOT NULL
            ORDER BY BTRIM("人员编号")
            """
        )
        return [
            employee_no
            for row in cursor.fetchall()
            if (employee_no := self._strip_text(row[0])) is not None
        ]

    def _build_person_attribute_payload(self, profile: dict[str, Any]) -> dict[str, Any]:
        tags = self._build_applicant_hr_tags(profile)
        return {
            "employee_no": self._null_if_blank(profile.get("employee_no")),
            "employee_name": self._null_if_blank(profile.get("employee_name")),
            "department_id": self._null_if_blank(profile.get("department_id")),
            "level1_function_name": self._null_if_blank(profile.get("level1_function_name")),
            "level2_function_name": self._null_if_blank(profile.get("level2_function_name")),
            "position_name": self._null_if_blank(profile.get("position_name")),
            "standard_position_name": self._null_if_blank(profile.get("standard_position_name")),
            "org_path_name": self._null_if_blank(profile.get("org_path_name")),
            "wanyu_city_sales_department": self._null_if_blank(profile.get("wanyu_city_sales_department")),
            "responsible_hr_employee_no": self._null_if_blank(profile.get("responsible_hr_employee_no")),
            "responsible_hr_import_batch_no": self._null_if_blank(profile.get("responsible_hr_import_batch_no")),
            "roster_query_date": profile.get("roster_query_date"),
            "roster_import_batch_no": self._null_if_blank(profile.get("roster_import_batch_no")),
            "roster_match_status": self._null_if_blank(tags.get("roster_match_status")),
            "hr_type": self._null_if_blank(tags.get("hr_type")),
            "is_responsible_hr": bool(tags.get("is_responsible_hr")),
            "is_hr_staff": bool(tags.get("is_hr_staff")),
            "is_suspected_hr_staff": bool(tags.get("is_suspected_hr_staff")),
            "hr_primary_evidence": self._null_if_blank(tags.get("hr_primary_evidence")),
            "hr_primary_value": self._null_if_blank(tags.get("hr_primary_value")),
            "hr_subdomain": self._null_if_blank(tags.get("hr_subdomain")),
            "hr_judgement_reason": self._null_if_blank(tags.get("hr_judgement_reason")),
        }

    def _refresh_from_roster(self, cursor) -> int:
        self._ensure_schema(cursor)
        employee_nos = self._fetch_roster_employee_nos(cursor)
        cursor.execute(f"TRUNCATE TABLE {self.table_name}")
        if not employee_nos:
            return 0

        permission_store = PostgresPermissionStore(self.settings)
        profiles = permission_store._fetch_applicant_hr_profiles(cursor, employee_nos)
        payloads = [
            self._build_person_attribute_payload(profiles[employee_no])
            for employee_no in sorted(profiles)
        ]
        if not payloads:
            return 0

        insert_columns = [
            PERSON_ATTRIBUTES_COLUMNS["employee_no"],
            PERSON_ATTRIBUTES_COLUMNS["employee_name"],
            PERSON_ATTRIBUTES_COLUMNS["department_id"],
            PERSON_ATTRIBUTES_COLUMNS["level1_function_name"],
            PERSON_ATTRIBUTES_COLUMNS["level2_function_name"],
            PERSON_ATTRIBUTES_COLUMNS["position_name"],
            PERSON_ATTRIBUTES_COLUMNS["standard_position_name"],
            PERSON_ATTRIBUTES_COLUMNS["org_path_name"],
            PERSON_ATTRIBUTES_COLUMNS["wanyu_city_sales_department"],
            PERSON_ATTRIBUTES_COLUMNS["responsible_hr_employee_no"],
            PERSON_ATTRIBUTES_COLUMNS["responsible_hr_import_batch_no"],
            PERSON_ATTRIBUTES_COLUMNS["roster_query_date"],
            PERSON_ATTRIBUTES_COLUMNS["roster_import_batch_no"],
            PERSON_ATTRIBUTES_COLUMNS["roster_match_status"],
            PERSON_ATTRIBUTES_COLUMNS["hr_type"],
            PERSON_ATTRIBUTES_COLUMNS["is_responsible_hr"],
            PERSON_ATTRIBUTES_COLUMNS["is_hr_staff"],
            PERSON_ATTRIBUTES_COLUMNS["is_suspected_hr_staff"],
            PERSON_ATTRIBUTES_COLUMNS["hr_primary_evidence"],
            PERSON_ATTRIBUTES_COLUMNS["hr_primary_value"],
            PERSON_ATTRIBUTES_COLUMNS["hr_subdomain"],
            PERSON_ATTRIBUTES_COLUMNS["hr_judgement_reason"],
            PERSON_ATTRIBUTES_COLUMNS["created_at"],
            PERSON_ATTRIBUTES_COLUMNS["updated_at"],
        ]
        cursor.executemany(
            f"""
            INSERT INTO {self.table_name} (
                {self._quoted_columns(insert_columns)}
            ) VALUES (
                %(employee_no)s,
                %(employee_name)s,
                %(department_id)s,
                %(level1_function_name)s,
                %(level2_function_name)s,
                %(position_name)s,
                %(standard_position_name)s,
                %(org_path_name)s,
                %(wanyu_city_sales_department)s,
                %(responsible_hr_employee_no)s,
                %(responsible_hr_import_batch_no)s,
                %(roster_query_date)s,
                %(roster_import_batch_no)s,
                %(roster_match_status)s,
                %(hr_type)s,
                %(is_responsible_hr)s,
                %(is_hr_staff)s,
                %(is_suspected_hr_staff)s,
                %(hr_primary_evidence)s,
                %(hr_primary_value)s,
                %(hr_subdomain)s,
                %(hr_judgement_reason)s,
                NOW(),
                NOW()
            )
            """,
            payloads,
        )
        return len(payloads)

    def refresh_from_roster(self) -> int:
        with self.connect() as connection:
            with connection.cursor() as cursor:
                return self._refresh_from_roster(cursor)


class PostgresRiskTrustStore(_PostgresStoreBase):
    _ensure_table_lock = threading.Lock()
    _ensured_schema_keys: set[tuple[str, int, str, str]] = set()
    schema_sql = Path(__file__).resolve().parents[1] / "sql" / "022_risk_trust_assessment.sql"
    schema_upgrade_sql_files = [
        Path(__file__).resolve().parents[1] / "sql" / "023_low_score_feedback_preagg.sql",
    ]

    def ensure_table(self) -> None:
        schema_key = (
            self.settings.host,
            self.settings.port,
            self.settings.dbname,
            self.settings.schema,
        )
        if schema_key in self._ensured_schema_keys:
            return

        ddl = self.schema_sql.read_text(encoding="utf-8")
        with self._ensure_table_lock:
            if schema_key in self._ensured_schema_keys:
                return

            with self.connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(ddl)
                    for migration_sql_file in self.schema_upgrade_sql_files:
                        cursor.execute(migration_sql_file.read_text(encoding="utf-8"))

            self._ensured_schema_keys.add(schema_key)

    @staticmethod
    def _format_datetime_value(value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        return str(value)

    @staticmethod
    def _format_score_value(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _format_bool_label(value: Any) -> str:
        return "是" if bool(value) else "否"

    @staticmethod
    def _suggested_action_label(value: str | None) -> str:
        mapping = {
            "reject": "建议拒绝",
            "manual_review": "建议人工复核",
            "warning": "建议关注",
            "allow": "建议通过",
        }
        normalized = (value or "").strip()
        return mapping.get(normalized, normalized or "-")

    @staticmethod
    def _applicant_identity_label(
        *,
        hr_type: str | None,
        position_name: str | None,
        level1_function_name: str | None,
    ) -> str:
        normalized_hr_type = (hr_type or "").strip()
        if normalized_hr_type in {"H1", "H2", "H3"}:
            identity = "申请人为HR岗位"
        elif normalized_hr_type == "HY":
            identity = "申请人为疑似HR岗位"
        elif normalized_hr_type:
            identity = "申请人为非HR岗位"
        else:
            identity = "申请人身份待确认"
        parts: list[str] = []
        if (normalized_position := (position_name or "").strip()):
            parts.append(f"职位：{normalized_position}")
        if (normalized_function := (level1_function_name or "").strip()):
            parts.append(f"一级职能：{normalized_function}")
        if not parts:
            return identity
        return f"{identity}（{'，'.join(parts)}）"

    def fetch_existing_assessment_batches(self, batch_nos: Iterable[str]) -> set[str]:
        normalized_batch_nos = sorted(
            {
                batch_no
                for value in batch_nos
                if (batch_no := self._strip_text(value)) is not None
            }
        )
        if not normalized_batch_nos:
            return set()

        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])}
                    FROM {RISK_TRUST_ASSESSMENT_TABLE}
                    WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])} = ANY(%s)
                    GROUP BY {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])}
                    """,
                    (normalized_batch_nos,),
                )
                return {
                    batch_no
                    for row in cursor.fetchall()
                    if (batch_no := self._strip_text(row[0])) is not None
                }

    def _empty_process_workbench(self) -> dict[str, Any]:
        return {
            "stats": [
                {
                    "label": "待处理单据",
                    "value": "0",
                    "hint": "当前尚未写入任何风险信任评估结果。",
                    "tone": "info",
                },
                {
                    "label": "最近评估批次",
                    "value": "-",
                    "hint": "执行 `python automation/scripts/run.py audit` 后会显示最新批次。",
                    "tone": "default",
                },
            ],
            "documents": [],
        }

    def _empty_process_analysis_dashboard(self) -> dict[str, Any]:
        return {
            "latestBatch": None,
            "distributionSections": [],
        }

    def _build_process_workbench_stats(
        self,
        summary_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        reject_count = sum(1 for row in summary_rows if row["summary_conclusion"] == "拒绝")
        manual_review_count = sum(1 for row in summary_rows if row["summary_conclusion"] == "人工干预")
        latest_row = (
            max(
                summary_rows,
                key=lambda row: (
                    row["assessed_at"] or datetime.min,
                    row["assessment_batch_no"] or "",
                    row["document_no"] or "",
                ),
            )
            if summary_rows
            else None
        )
        latest_batch_no = latest_row["assessment_batch_no"] if latest_row is not None else "-"
        latest_version = latest_row["assessment_version"] if latest_row is not None else "-"
        latest_assessed_at = self._format_datetime_value(latest_row["assessed_at"]) if latest_row is not None else "-"
        return [
            {
                "label": "待处理单据",
                "value": str(len(summary_rows)),
                "hint": "来自逐单最新评估结果快照的单据数。",
                "tone": "warning" if summary_rows else "info",
            },
            {
                "label": "拒绝",
                "value": str(reject_count),
                "hint": "逐单最新结果中总结论为“拒绝”的单据数。",
                "tone": "danger" if reject_count else "success",
            },
            {
                "label": display_summary_conclusion("人工干预"),
                "value": str(manual_review_count),
                "hint": "逐单最新结果中需要加强审核的单据数。",
                "tone": "warning" if manual_review_count else "success",
            },
            {
                "label": "最近评估批次",
                "value": latest_batch_no,
                "hint": f"来自逐单最新结果中的最近一次评估写入，版本 {latest_version}，评估时间 {latest_assessed_at}。",
                "tone": "default",
            },
        ]

    def _build_process_document_rows(self, summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": row["document_no"],
                "documentNo": row["document_no"],
                "applicantName": row["applicant_name"] or "-",
                "applicantNo": row["employee_no"] or "-",
                "permissionTarget": row["permission_target"] or "-",
                "department": row["department_name"] or "-",
                "documentStatus": row["document_status"] or "-",
                "finalScore": row["final_score"],
                "summaryConclusion": row["summary_conclusion"] or "-",
                "summaryConclusionLabel": display_summary_conclusion(row["summary_conclusion"]),
                "suggestedAction": row["suggested_action"] or "",
                "suggestedActionLabel": self._suggested_action_label(row["suggested_action"]),
                "lowScoreDetailCount": int(row["low_score_detail_count"] or 0),
                "assessedAt": self._format_datetime_value(row["assessed_at"]),
                "latestBatchNo": row["assessment_batch_no"] or "-",
            }
            for row in summary_rows
        ]

    def fetch_process_workbench(self) -> dict[str, Any]:
        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                summary_rows = self._fetch_latest_process_summary_rows(cursor)
                if not summary_rows:
                    return self._empty_process_workbench()

        return {
            "stats": self._build_process_workbench_stats(summary_rows),
            "documents": self._build_process_document_rows(summary_rows),
        }

    def fetch_process_analysis_dashboard(self) -> dict[str, Any]:
        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                latest_batch_no = self._fetch_latest_assessment_batch_no(cursor)
                if latest_batch_no is None:
                    return self._empty_process_analysis_dashboard()

                batch_summary = self._fetch_process_batch_summary(cursor, latest_batch_no)
                distribution_sections = self._fetch_process_distribution_sections(cursor, latest_batch_no)

        return {
            "latestBatch": {
                "batchNo": latest_batch_no,
                **batch_summary,
            },
            "distributionSections": distribution_sections,
        }

    def fetch_process_dashboard(self) -> dict[str, Any]:
        workbench = self.fetch_process_workbench()
        analysis = self.fetch_process_analysis_dashboard()
        return {
            **workbench,
            **analysis,
        }

    def fetch_process_document_detail(
        self,
        document_no: str,
        assessment_batch_no: str | None = None,
    ) -> dict[str, Any] | None:
        normalized_document_no = self._strip_text(document_no)
        if normalized_document_no is None:
            return None

        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                batch_no = self._strip_text(assessment_batch_no)
                if batch_no is None:
                    summary_rows = self._fetch_latest_process_summary_rows(
                        cursor,
                        document_no=normalized_document_no,
                    )
                    if not summary_rows:
                        return None
                    batch_no = self._strip_text(summary_rows[0]["assessment_batch_no"])
                else:
                    summary_rows = self._fetch_process_summary_rows(
                        cursor,
                        batch_no,
                        document_no=normalized_document_no,
                    )
                if not summary_rows:
                    return None
                summary_row = summary_rows[0]
                role_rows = self._fetch_process_role_rows(cursor, [normalized_document_no])
                approval_rows = self._fetch_approval_rows(cursor, [normalized_document_no])
                org_scope_rows = self._fetch_process_org_scope_display_rows(cursor, [normalized_document_no])
                low_score_rows = self._fetch_process_low_score_rows(
                    cursor,
                    batch_no,
                    [normalized_document_no],
                )
                feedback_group_rows = self._fetch_process_feedback_group_rows(
                    cursor,
                    batch_no,
                    [normalized_document_no],
                )

        feedback_overview = build_low_score_feedback(
            summary_row=summary_row,
            feedback_group_rows=feedback_group_rows,
        )
        notes: list[str] = []
        if summary_row["assessment_explain"]:
            notes.append(f"评估说明：{summary_row['assessment_explain']}")
        if feedback_overview["feedbackLines"]:
            notes.append(
                f"默认已按 104 方案聚合为 {len(feedback_overview['feedbackLines'])} 类风险摘要，原始低分明细留在“原始低分明细”页签。"
            )
        if summary_row["suggested_action"] == "reject":
            notes.append("当前建议动作为拒绝，需结合原始单据与审批链复核后再处理。")
        elif summary_row["suggested_action"] == "manual_review":
            notes.append("当前建议动作为人工复核，默认展示文案已映射为“加强审核”。")

        return {
            "documentNo": summary_row["document_no"],
            "overviewFields": [
                {"label": "单据编号", "value": summary_row["document_no"] or "-", "hint": "当前选中单据"},
                {
                    "label": "申请人",
                    "value": f"{summary_row['applicant_name'] or '-'} / {summary_row['employee_no'] or '-'}",
                    "hint": "申请人姓名通过 `人员属性查询` 关联。",
                },
                {
                    "label": "权限对象",
                    "value": summary_row["permission_target"] or "-",
                    "hint": "来自 `申请单基本信息.权限对象`。",
                },
                {
                    "label": "单据状态",
                    "value": summary_row["document_status"] or "-",
                    "hint": "当前待办单据状态。",
                },
                {
                    "label": "部门",
                    "value": summary_row["department_name"] or "-",
                    "hint": "申请人当前部门。",
                },
                {
                    "label": "申请日期",
                    "value": self._format_datetime_value(summary_row["apply_time"]),
                    "hint": "若源页面缺失则显示 `-`。",
                },
                {
                    "label": "申请人身份",
                    "value": summary_row["applicant_identity_label"] or "-",
                    "hint": "按 104 方案以自然语言展示申请人身份，不直接输出 H1/HX 等内部编码。",
                },
                {
                    "label": "申请人组织单位",
                    "value": summary_row["applicant_org_unit_name"] or "-",
                    "hint": "来自 `组织属性查询.组织单位`。",
                },
                {
                    "label": "最新审批时间",
                    "value": self._format_datetime_value(summary_row["latest_approval_time"]),
                    "hint": "用于判断审批轨迹是否已更新。",
                },
                {
                    "label": "申请人组织流程层级分类",
                    "value": summary_row["applicant_process_level_category"] or "-",
                    "hint": "来自 `组织属性查询`。",
                },
                {
                    "label": "最终信任分",
                    "value": f"{summary_row['final_score']:.1f}" if summary_row["final_score"] is not None else "-",
                    "hint": "整单按最低分汇总。",
                },
                {
                    "label": "总结论",
                    "value": display_summary_conclusion(summary_row["summary_conclusion"]),
                    "hint": f"建议动作：{self._suggested_action_label(summary_row['suggested_action'])}",
                },
                {
                    "label": "最低命中维度",
                    "value": summary_row["lowest_hit_dimension"] or "-",
                    "hint": "当前整单最低分来源。",
                },
                {
                    "label": "低分明细条数",
                    "value": str(int(summary_row["low_score_detail_count"] or 0)),
                    "hint": "原始 `<= 1.0` 低分明细条数，不等于风险点数量。",
                },
                {
                    "label": "评估批次号",
                    "value": summary_row["assessment_batch_no"] or "-",
                    "hint": f"版本 {summary_row['assessment_version'] or '-'}。",
                },
                {
                    "label": "评估时间",
                    "value": self._format_datetime_value(summary_row["assessed_at"]),
                    "hint": "结果写入批次时间。",
                },
            ],
            "roles": [
                {
                    "id": row["id"],
                    "lineNo": row["line_no"] or "-",
                    "roleCode": row["role_code"] or "-",
                    "roleName": row["role_name"] or "-",
                    "permissionLevel": row["permission_level"] or "-",
                    "applyType": row["apply_type"] or "-",
                    "orgScopeCount": int(row["org_scope_count"] or 0),
                    "skipOrgScopeCheck": self._format_bool_label(row["skip_org_scope_check"]),
                }
                for row in role_rows
            ],
            "approvals": [
                {
                    "id": f"{row['document_no']}:{row['record_seq']}",
                    "nodeName": row["node_name"] or "-",
                    "approver": row["approver_name"] or (row["approver_employee_no"] or "-"),
                    "action": row["approval_action"] or "-",
                    "finishedAt": self._format_datetime_value(row["approval_time"]),
                    "comment": row["approval_opinion"] or "-",
                }
                for row in approval_rows
            ],
            "orgScopes": [
                {
                    "id": row["id"],
                    "roleCode": row["role_code"] or "-",
                    "roleName": row["role_name"] or "-",
                    "organizationCode": row["org_code"] or "-",
                    "organizationName": row["organization_name"] or "-",
                    "orgUnitName": row["org_unit_name"] or "-",
                    "physicalLevel": row["physical_level"] or "-",
                    "skipOrgScopeCheck": self._format_bool_label(row["skip_org_scope_check"]),
                }
                for row in org_scope_rows
            ],
            "riskDetails": [
                {
                    "id": row["id"],
                    "dimensionName": row["dimension_name"] or "-",
                    "ruleId": row["rule_id"] or "-",
                    "ruleSummary": row["rule_summary"] or "-",
                    "roleCode": row["role_code"] or "-",
                    "roleName": row["role_name"] or "-",
                    "orgCode": row["org_code"] or "-",
                    "score": row["score"],
                    "detailConclusion": row["detail_conclusion"] or "-",
                    "interventionAction": row["intervention_action"] or "-",
                }
                for row in low_score_rows
            ],
            "feedbackOverview": feedback_overview,
            "notes": notes,
        }

    def fetch_document_bundles(
        self,
        document_no: str | None = None,
        document_nos: Iterable[str] | None = None,
        limit: int = 0,
    ) -> list[dict[str, Any]]:
        normalized_document_no = self._strip_text(document_no)
        normalized_document_nos: list[str] = []
        seen_document_nos: set[str] = set()
        for value in document_nos or []:
            normalized = self._strip_text(value)
            if normalized is None or normalized in seen_document_nos:
                continue
            seen_document_nos.add(normalized)
            normalized_document_nos.append(normalized)
        query_limit = max(limit, 0)

        with self.connect() as connection:
            with connection.cursor() as cursor:
                basic_rows = self._fetch_basic_info_rows(
                    cursor,
                    normalized_document_no,
                    query_limit,
                    document_nos=normalized_document_nos,
                )
                if not basic_rows:
                    return []

                document_nos = [row["document_no"] for row in basic_rows]
                detail_rows = self._fetch_permission_detail_rows(cursor, document_nos)
                approval_rows = self._fetch_approval_rows(cursor, document_nos)
                org_scope_rows = self._fetch_org_scope_rows(cursor, document_nos)

                applicant_employee_nos = [row["employee_no"] for row in basic_rows]
                approver_employee_nos = [row["approver_employee_no"] for row in approval_rows]
                person_attributes_by_employee_no = self._fetch_person_attributes_map(
                    cursor,
                    [*applicant_employee_nos, *approver_employee_nos],
                )

                role_catalog_by_role_code = self._fetch_permission_catalog_rows(
                    cursor,
                    [row["role_code"] for row in detail_rows],
                )

                org_codes_to_fetch: list[str] = []
                for row in basic_rows:
                    applicant_profile = person_attributes_by_employee_no.get(row["employee_no"], {})
                    org_codes_to_fetch.append(self._strip_text(applicant_profile.get("department_id")) or "")
                for row in approval_rows:
                    approver_profile = person_attributes_by_employee_no.get(row["approver_employee_no"], {})
                    org_codes_to_fetch.append(self._strip_text(approver_profile.get("department_id")) or "")
                for row in org_scope_rows:
                    org_codes_to_fetch.append(row["org_code"] or "")

                org_attributes_by_org_code = self._fetch_org_attributes_map(cursor, org_codes_to_fetch)

        detail_rows_by_document: dict[str, list[dict[str, Any]]] = {}
        for row in detail_rows:
            detail_rows_by_document.setdefault(row["document_no"], []).append(row)

        approval_rows_by_document: dict[str, list[dict[str, Any]]] = {}
        for row in approval_rows:
            approver_profile = person_attributes_by_employee_no.get(row["approver_employee_no"], {})
            approver_org = org_attributes_by_org_code.get(self._strip_text(approver_profile.get("department_id")) or "")
            approval_rows_by_document.setdefault(row["document_no"], []).append(
                {
                    **row,
                    "approver_person_attributes": approver_profile,
                    "approver_org_attributes": approver_org,
                }
            )

        org_scope_rows_by_document_role: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in org_scope_rows:
            org_scope_rows_by_document_role.setdefault((row["document_no"], row["role_code"]), []).append(row)

        bundles: list[dict[str, Any]] = []
        for basic_row in basic_rows:
            applicant_profile = person_attributes_by_employee_no.get(basic_row["employee_no"], {})
            applicant_org = org_attributes_by_org_code.get(self._strip_text(applicant_profile.get("department_id")) or "")

            document_detail_rows: list[dict[str, Any]] = []
            for detail_row in detail_rows_by_document.get(basic_row["document_no"], []):
                catalog_row = role_catalog_by_role_code.get(detail_row["role_code"])
                role_facts = build_detail_role_facts(detail_row, catalog_row)
                targets: list[dict[str, Any]] = []
                for target_row in org_scope_rows_by_document_role.get((basic_row["document_no"], detail_row["role_code"]), []):
                    org_attributes = org_attributes_by_org_code.get(target_row["org_code"] or "", {})
                    targets.append(
                        {
                            "org_code": target_row["org_code"],
                            "org_name": org_attributes.get("org_name"),
                            "org_auth_level": org_attributes.get("org_auth_level"),
                            "org_unit_name": org_attributes.get("org_unit_name"),
                            "physical_level": org_attributes.get("physical_level"),
                            "org_attributes": org_attributes,
                        }
                    )
                document_detail_rows.append(
                    {
                        **detail_row,
                        "catalog_matched": role_facts["catalog_matched"],
                        "permission_level": role_facts["permission_level"],
                        "skip_org_scope_check": role_facts["skip_org_scope_check"],
                        "targets": targets,
                    }
                )

            bundles.append(
                {
                    "basic_info": basic_row,
                    "applicant_person_attributes": applicant_profile,
                    "applicant_org_attributes": applicant_org,
                    "permission_details": document_detail_rows,
                    "approval_records": approval_rows_by_document.get(basic_row["document_no"], []),
                }
            )
        return bundles

    def write_assessment_results(
        self,
        summary_rows: Iterable[dict[str, Any]],
        detail_rows: Iterable[dict[str, Any]],
    ) -> None:
        normalized_summary_rows = list(summary_rows)
        normalized_detail_rows = list(detail_rows)
        if not normalized_summary_rows:
            return

        self.ensure_table()
        document_nos = sorted(
            {
                str(row["document_no"]).strip()
                for row in normalized_summary_rows
                if isinstance(row.get("document_no"), str) and row["document_no"].strip()
            }
        )
        batch_no = str(normalized_summary_rows[0]["assessment_batch_no"]).strip()
        version = str(normalized_summary_rows[0]["assessment_version"]).strip()

        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    DELETE FROM {RISK_TRUST_ASSESSMENT_DETAIL_TABLE}
                    WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["document_no"])} = ANY(%s)
                      AND {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessment_batch_no"])} = %s
                      AND {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessment_version"])} = %s
                    """,
                    (document_nos, batch_no, version),
                )
                cursor.execute(
                    f"""
                    DELETE FROM {RISK_TRUST_ASSESSMENT_TABLE}
                    WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["document_no"])} = ANY(%s)
                      AND {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])} = %s
                      AND {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_version"])} = %s
                    """,
                    (document_nos, batch_no, version),
                )
                self._insert_assessment_summary_rows(cursor, normalized_summary_rows)
                self._insert_assessment_detail_rows(cursor, normalized_detail_rows)

    def _fetch_basic_info_rows(
        self,
        cursor,
        document_no: str | None,
        limit: int,
        document_nos: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_document_nos: list[str] = []
        seen_document_nos: set[str] = set()
        for value in document_nos or []:
            normalized = self._strip_text(value)
            if normalized is None or normalized in seen_document_nos:
                continue
            seen_document_nos.add(normalized)
            normalized_document_nos.append(normalized)
        sql = f"""
            SELECT
                {self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["employee_no"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["permission_target"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["apply_reason"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["document_status"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["hr_org"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["company_name"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["department_name"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["position_name"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["apply_time"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["latest_approval_time"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["collection_count"])},
                {self._quote_identifier(BASIC_INFO_COLUMNS["updated_at"])}
            FROM {BASIC_INFO_TABLE}
        """
        params: list[Any] = []
        if normalized_document_nos:
            sql += f" WHERE {self._quote_identifier(BASIC_INFO_COLUMNS['document_no'])} = ANY(%s)"
            params.append(normalized_document_nos)
            sql += (
                f" ORDER BY ARRAY_POSITION(%s::varchar[], {self._quote_identifier(BASIC_INFO_COLUMNS['document_no'])}),"
                f" {self._quote_identifier(BASIC_INFO_COLUMNS['latest_approval_time'])} DESC NULLS LAST,"
                f" {self._quote_identifier(BASIC_INFO_COLUMNS['apply_time'])} DESC NULLS LAST,"
                f" {self._quote_identifier(BASIC_INFO_COLUMNS['document_no'])}"
            )
            params.append(normalized_document_nos)
        elif document_no is not None:
            sql += f" WHERE {self._quote_identifier(BASIC_INFO_COLUMNS['document_no'])} = %s"
            params.append(document_no)
            sql += (
                f" ORDER BY {self._quote_identifier(BASIC_INFO_COLUMNS['latest_approval_time'])} DESC NULLS LAST,"
                f" {self._quote_identifier(BASIC_INFO_COLUMNS['apply_time'])} DESC NULLS LAST,"
                f" {self._quote_identifier(BASIC_INFO_COLUMNS['document_no'])}"
            )
        else:
            sql += (
                f" ORDER BY {self._quote_identifier(BASIC_INFO_COLUMNS['latest_approval_time'])} DESC NULLS LAST,"
                f" {self._quote_identifier(BASIC_INFO_COLUMNS['apply_time'])} DESC NULLS LAST,"
                f" {self._quote_identifier(BASIC_INFO_COLUMNS['document_no'])}"
            )
        if limit > 0 and not normalized_document_nos:
            sql += " LIMIT %s"
            params.append(limit)
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "employee_no": self._strip_text(row[1]),
                "permission_target": self._strip_text(row[2]),
                "apply_reason": self._strip_text(row[3]),
                "document_status": self._strip_text(row[4]),
                "hr_org": self._strip_text(row[5]),
                "company_name": self._strip_text(row[6]),
                "department_name": self._strip_text(row[7]),
                "position_name": self._strip_text(row[8]),
                "apply_time": row[9],
                "latest_approval_time": row[10],
                "collection_count": row[11],
                "updated_at": row[12],
            }
            for row in rows
            if self._strip_text(row[0]) is not None
        ]

    def _fetch_permission_detail_rows(self, cursor, document_nos: Iterable[str]) -> list[dict[str, Any]]:
        normalized_document_nos = [document_no for document_no in document_nos if document_no]
        if not normalized_document_nos:
            return []
        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])},
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["line_no"])},
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["apply_type"])},
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["role_name"])},
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["role_desc"])},
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["role_code"])},
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["social_security_unit"])},
                {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["org_scope_count"])}
            FROM {PERMISSION_APPLY_DETAIL_TABLE}
            WHERE {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])} = ANY(%s)
            ORDER BY {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])},
                     {self._quote_identifier(PERMISSION_DETAIL_COLUMNS["line_no"])}
            """,
            (normalized_document_nos,),
        )
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "line_no": self._strip_text(row[1]),
                "apply_type": self._strip_text(row[2]),
                "role_name": self._strip_text(row[3]),
                "role_desc": self._strip_text(row[4]),
                "role_code": self._strip_text(row[5]),
                "social_security_unit": self._strip_text(row[6]),
                "org_scope_count": row[7],
            }
            for row in rows
            if self._strip_text(row[0]) is not None
        ]

    def _fetch_approval_rows(self, cursor, document_nos: Iterable[str]) -> list[dict[str, Any]]:
        normalized_document_nos = [document_no for document_no in document_nos if document_no]
        if not normalized_document_nos:
            return []
        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["record_seq"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["node_name"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["approver_name"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["approver_employee_no"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["approver_org_or_position"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["approval_action"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["approval_opinion"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["approval_time"])},
                {self._quote_identifier(APPROVAL_RECORD_COLUMNS["raw_text"])}
            FROM {APPROVAL_RECORD_TABLE}
            WHERE {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])} = ANY(%s)
            ORDER BY {self._quote_identifier(APPROVAL_RECORD_COLUMNS["document_no"])},
                     {self._quote_identifier(APPROVAL_RECORD_COLUMNS["record_seq"])}
            """,
            (normalized_document_nos,),
        )
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "record_seq": row[1],
                "node_name": self._strip_text(row[2]),
                "approver_name": self._strip_text(row[3]),
                "approver_employee_no": self._strip_text(row[4]),
                "approver_org_or_position": self._strip_text(row[5]),
                "approval_action": self._strip_text(row[6]),
                "approval_opinion": self._strip_text(row[7]),
                "approval_time": row[8],
                "raw_text": self._strip_text(row[9]),
            }
            for row in rows
            if self._strip_text(row[0]) is not None
        ]

    def _fetch_org_scope_rows(self, cursor, document_nos: Iterable[str]) -> list[dict[str, Any]]:
        normalized_document_nos = [document_no for document_no in document_nos if document_no]
        if not normalized_document_nos:
            return []
        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])},
                {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_code"])},
                {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_name"])},
                {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["org_code"])}
            FROM {APPLY_FORM_ORG_SCOPE_TABLE}
            WHERE {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])} = ANY(%s)
            ORDER BY {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])},
                     {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_code"])},
                     {self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["org_code"])}
            """,
            (normalized_document_nos,),
        )
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "role_code": self._strip_text(row[1]),
                "role_name": self._strip_text(row[2]),
                "org_code": self._strip_text(row[3]),
            }
            for row in rows
            if self._strip_text(row[0]) is not None and self._strip_text(row[1]) is not None
        ]

    def _fetch_person_attributes_map(self, cursor, employee_nos: Iterable[str]) -> dict[str, dict[str, Any]]:
        normalized_employee_nos = sorted(
            {
                employee_no
                for value in employee_nos
                if (employee_no := self._strip_text(value)) is not None
            }
        )
        if not normalized_employee_nos:
            return {}
        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["employee_no"])},
                {self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["employee_name"])},
                {self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["department_id"])},
                {self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["hr_type"])},
                {self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["roster_match_status"])},
                {self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["hr_judgement_reason"])}
            FROM {PERSON_ATTRIBUTES_TABLE}
            WHERE {self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["employee_no"])} = ANY(%s)
            """,
            (normalized_employee_nos,),
        )
        rows = cursor.fetchall()
        return {
            self._strip_text(row[0]) or "": {
                "employee_no": self._strip_text(row[0]),
                "employee_name": self._strip_text(row[1]),
                "department_id": self._strip_text(row[2]),
                "hr_type": self._strip_text(row[3]),
                "roster_match_status": self._strip_text(row[4]),
                "hr_judgement_reason": self._strip_text(row[5]),
            }
            for row in rows
            if self._strip_text(row[0]) is not None
        }

    def _fetch_permission_catalog_rows(self, cursor, role_codes: Iterable[str]) -> dict[str, dict[str, Any]]:
        normalized_role_codes = sorted(
            {
                role_code
                for value in role_codes
                if (role_code := self._strip_text(value)) is not None
            }
        )
        if not normalized_role_codes:
            return {}
        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])},
                {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_name"])},
                {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["permission_level"])},
                {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["skip_org_scope_check"])}
            FROM "权限列表"
            WHERE {self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])} = ANY(%s)
            """,
            (normalized_role_codes,),
        )
        rows = cursor.fetchall()
        return {
            self._strip_text(row[0]) or "": {
                "role_code": self._strip_text(row[0]),
                "role_name": self._strip_text(row[1]),
                "permission_level": self._strip_text(row[2]),
                "skip_org_scope_check": bool(row[3]),
            }
            for row in rows
            if self._strip_text(row[0]) is not None
        }

    def _fetch_org_attributes_map(self, cursor, org_codes: Iterable[str]) -> dict[str, dict[str, Any]]:
        normalized_org_codes = sorted(
            {
                org_code
                for value in org_codes
                if (org_code := self._strip_text(value)) is not None
            }
        )
        if not normalized_org_codes:
            return {}
        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_code"])},
                {self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_name"])},
                {self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["process_level_category"])},
                {self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_auth_level"])},
                {self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_unit_name"])},
                {self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["physical_level"])},
                {self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["war_zone"])}
            FROM "组织属性查询"
            WHERE {self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_code"])} = ANY(%s)
            """,
            (normalized_org_codes,),
        )
        rows = cursor.fetchall()
        return {
            self._strip_text(row[0]) or "": {
                "org_code": self._strip_text(row[0]),
                "org_name": self._strip_text(row[1]),
                "process_level_category": self._strip_text(row[2]),
                "org_auth_level": self._strip_text(row[3]),
                "org_unit_name": self._strip_text(row[4]),
                "physical_level": self._strip_text(row[5]),
                "war_zone": self._strip_text(row[6]),
            }
            for row in rows
            if self._strip_text(row[0]) is not None
        }

    def _fetch_latest_assessment_batch_no(self, cursor) -> str | None:
        cursor.execute(
            f"""
            SELECT {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])}
            FROM {RISK_TRUST_ASSESSMENT_TABLE}
            ORDER BY {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessed_at"])} DESC,
                     {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["id"])} DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._strip_text(row[0])

    def _fetch_process_batch_summary(self, cursor, assessment_batch_no: str) -> dict[str, Any]:
        cursor.execute(
            f"""
            SELECT
                MAX({self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_version"])}),
                COUNT(*),
                COALESCE(SUM({self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_count"])}), 0),
                MAX({self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessed_at"])})
            FROM {RISK_TRUST_ASSESSMENT_TABLE}
            WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])} = %s
            """,
            (assessment_batch_no,),
        )
        row = cursor.fetchone()
        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM {RISK_TRUST_ASSESSMENT_DETAIL_TABLE}
            WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessment_batch_no"])} = %s
            """,
            (assessment_batch_no,),
        )
        detail_count = cursor.fetchone()[0]
        return {
            "assessmentVersion": self._strip_text(row[0]) or "-",
            "documentCount": int(row[1] or 0),
            "lowScoreDetailCount": int(row[2] or 0),
            "detailCount": int(detail_count or 0),
            "assessedAt": self._format_datetime_value(row[3]),
        }

    def _fetch_process_summary_rows(
        self,
        cursor,
        assessment_batch_no: str,
        document_no: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = f"""
            SELECT
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["document_no"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["employee_no"])},
                person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["employee_name"])},
                person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["level1_function_name"])},
                person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["position_name"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["permission_target"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["document_status"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["company_name"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["department_name"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["position_name"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["apply_time"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["latest_approval_time"])},
                applicant_org.{self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_unit_name"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_version"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["applicant_hr_type"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["applicant_process_level_category"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["final_score"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["summary_conclusion"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["suggested_action"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_dimension"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_role_code"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_org_code"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["hit_manual_review"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["has_low_score_details"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_count"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_conclusion"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_explain"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessed_at"])}
            FROM {RISK_TRUST_ASSESSMENT_TABLE} AS assessment
            INNER JOIN {BASIC_INFO_TABLE} AS basic
                ON basic.{self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])} =
                   assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["document_no"])}
            LEFT JOIN {PERSON_ATTRIBUTES_TABLE} AS person
                ON person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["employee_no"])} =
                   basic.{self._quote_identifier(BASIC_INFO_COLUMNS["employee_no"])}
            LEFT JOIN "组织属性查询" AS applicant_org
                ON applicant_org.{self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_code"])} =
                   person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["department_id"])}
            WHERE assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])} = %s
        """
        params: list[Any] = [assessment_batch_no]
        if document_no is not None:
            sql += (
                f" AND assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS['document_no'])} = %s"
            )
            params.append(document_no)
        sql += f"""
            ORDER BY assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["final_score"])} ASC,
                     assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_count"])} DESC,
                     basic.{self._quote_identifier(BASIC_INFO_COLUMNS["latest_approval_time"])} DESC NULLS LAST,
                     basic.{self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])}
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "employee_no": self._strip_text(row[1]),
                "applicant_name": self._strip_text(row[2]),
                "level1_function_name": self._strip_text(row[3]),
                "applicant_position_name": self._strip_text(row[4]),
                "permission_target": self._strip_text(row[5]),
                "document_status": self._strip_text(row[6]),
                "company_name": self._strip_text(row[7]),
                "department_name": self._strip_text(row[8]),
                "position_name": self._strip_text(row[9]),
                "apply_time": row[10],
                "latest_approval_time": row[11],
                "applicant_org_unit_name": self._strip_text(row[12]),
                "assessment_batch_no": self._strip_text(row[13]),
                "assessment_version": self._strip_text(row[14]),
                "applicant_hr_type": self._strip_text(row[15]),
                "applicant_process_level_category": self._strip_text(row[16]),
                "final_score": self._format_score_value(row[17]),
                "summary_conclusion": self._strip_text(row[18]),
                "suggested_action": self._strip_text(row[19]),
                "lowest_hit_dimension": self._strip_text(row[20]),
                "lowest_hit_role_code": self._strip_text(row[21]),
                "lowest_hit_org_code": self._strip_text(row[22]),
                "hit_manual_review": bool(row[23]),
                "has_low_score_details": bool(row[24]),
                "low_score_detail_count": row[25],
                "low_score_detail_conclusion": self._strip_text(row[26]),
                "assessment_explain": self._strip_text(row[27]),
                "assessed_at": row[28],
                "applicant_identity_label": self._applicant_identity_label(
                    hr_type=self._strip_text(row[15]),
                    position_name=self._strip_text(row[4]) or self._strip_text(row[9]),
                    level1_function_name=self._strip_text(row[3]),
                ),
            }
            for row in rows
            if self._strip_text(row[0]) is not None
        ]

    def _fetch_latest_process_summary_rows(
        self,
        cursor,
        document_no: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = f"""
            WITH latest_assessment AS (
                SELECT
                    assessment.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["document_no"])}
                        ORDER BY assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessed_at"])} DESC,
                                 assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["id"])} DESC
                    ) AS rn
                FROM {RISK_TRUST_ASSESSMENT_TABLE} AS assessment
            )
            SELECT
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["document_no"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["employee_no"])},
                person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["employee_name"])},
                person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["level1_function_name"])},
                person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["position_name"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["permission_target"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["document_status"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["company_name"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["department_name"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["position_name"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["apply_time"])},
                basic.{self._quote_identifier(BASIC_INFO_COLUMNS["latest_approval_time"])},
                applicant_org.{self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_unit_name"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_version"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["applicant_hr_type"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["applicant_process_level_category"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["final_score"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["summary_conclusion"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["suggested_action"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_dimension"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_role_code"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_org_code"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["hit_manual_review"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["has_low_score_details"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_count"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_conclusion"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_explain"])},
                assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessed_at"])}
            FROM latest_assessment AS assessment
            INNER JOIN {BASIC_INFO_TABLE} AS basic
                ON basic.{self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])} =
                   assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["document_no"])}
            LEFT JOIN {PERSON_ATTRIBUTES_TABLE} AS person
                ON person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["employee_no"])} =
                   basic.{self._quote_identifier(BASIC_INFO_COLUMNS["employee_no"])}
            LEFT JOIN "组织属性查询" AS applicant_org
                ON applicant_org.{self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_code"])} =
                   person.{self._quote_identifier(PERSON_ATTRIBUTES_COLUMNS["department_id"])}
            WHERE assessment.rn = 1
        """
        params: list[Any] = []
        if document_no is not None:
            sql += (
                f" AND assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS['document_no'])} = %s"
            )
            params.append(document_no)
        sql += f"""
            ORDER BY assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["final_score"])} ASC,
                     assessment.{self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_count"])} DESC,
                     basic.{self._quote_identifier(BASIC_INFO_COLUMNS["latest_approval_time"])} DESC NULLS LAST,
                     basic.{self._quote_identifier(BASIC_INFO_COLUMNS["document_no"])}
        """
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "employee_no": self._strip_text(row[1]),
                "applicant_name": self._strip_text(row[2]),
                "level1_function_name": self._strip_text(row[3]),
                "applicant_position_name": self._strip_text(row[4]),
                "permission_target": self._strip_text(row[5]),
                "document_status": self._strip_text(row[6]),
                "company_name": self._strip_text(row[7]),
                "department_name": self._strip_text(row[8]),
                "position_name": self._strip_text(row[9]),
                "apply_time": row[10],
                "latest_approval_time": row[11],
                "applicant_org_unit_name": self._strip_text(row[12]),
                "assessment_batch_no": self._strip_text(row[13]),
                "assessment_version": self._strip_text(row[14]),
                "applicant_hr_type": self._strip_text(row[15]),
                "applicant_process_level_category": self._strip_text(row[16]),
                "final_score": self._format_score_value(row[17]),
                "summary_conclusion": self._strip_text(row[18]),
                "suggested_action": self._strip_text(row[19]),
                "lowest_hit_dimension": self._strip_text(row[20]),
                "lowest_hit_role_code": self._strip_text(row[21]),
                "lowest_hit_org_code": self._strip_text(row[22]),
                "hit_manual_review": bool(row[23]),
                "has_low_score_details": bool(row[24]),
                "low_score_detail_count": row[25],
                "low_score_detail_conclusion": self._strip_text(row[26]),
                "assessment_explain": self._strip_text(row[27]),
                "assessed_at": row[28],
                "applicant_identity_label": self._applicant_identity_label(
                    hr_type=self._strip_text(row[15]),
                    position_name=self._strip_text(row[4]) or self._strip_text(row[9]),
                    level1_function_name=self._strip_text(row[3]),
                ),
            }
            for row in rows
            if self._strip_text(row[0]) is not None
        ]

    def _fetch_process_role_rows(self, cursor, document_nos: Iterable[str]) -> list[dict[str, Any]]:
        normalized_document_nos = [document_no for document_no in document_nos if document_no]
        if not normalized_document_nos:
            return []
        cursor.execute(
            f"""
            SELECT
                detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])},
                detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["id"])},
                detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["line_no"])},
                detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["role_code"])},
                detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["role_name"])},
                detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["apply_type"])},
                detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["org_scope_count"])},
                catalog.{self._quote_identifier(PERMISSION_CATALOG_COLUMNS["skip_org_scope_check"])},
                catalog.{self._quote_identifier(PERMISSION_CATALOG_COLUMNS["permission_level"])}
            FROM {PERMISSION_APPLY_DETAIL_TABLE} AS detail
            LEFT JOIN "权限列表" AS catalog
                ON catalog.{self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])} =
                   detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["role_code"])}
            WHERE detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])} = ANY(%s)
            ORDER BY detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["document_no"])},
                     detail.{self._quote_identifier(PERMISSION_DETAIL_COLUMNS["line_no"])}
            """,
            (normalized_document_nos,),
        )
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "id": f"{self._strip_text(row[0])}:{self._strip_text(row[1]) or index}",
                "line_no": self._strip_text(row[2]),
                "role_code": self._strip_text(row[3]),
                "role_name": self._strip_text(row[4]),
                "apply_type": self._strip_text(row[5]),
                "org_scope_count": row[6],
                "skip_org_scope_check": bool(row[7]),
                "permission_level": self._strip_text(row[8]),
            }
            for index, row in enumerate(rows, start=1)
            if self._strip_text(row[0]) is not None
        ]

    def _fetch_process_org_scope_display_rows(self, cursor, document_nos: Iterable[str]) -> list[dict[str, Any]]:
        normalized_document_nos = [document_no for document_no in document_nos if document_no]
        if not normalized_document_nos:
            return []
        cursor.execute(
            f"""
            SELECT
                scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])},
                scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_code"])},
                scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_name"])},
                scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["org_code"])},
                catalog.{self._quote_identifier(PERMISSION_CATALOG_COLUMNS["skip_org_scope_check"])},
                org.{self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_name"])},
                org.{self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_unit_name"])},
                org.{self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["physical_level"])}
            FROM {APPLY_FORM_ORG_SCOPE_TABLE} AS scope
            LEFT JOIN "权限列表" AS catalog
                ON catalog.{self._quote_identifier(PERMISSION_CATALOG_COLUMNS["role_code"])} =
                   scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_code"])}
            LEFT JOIN "组织属性查询" AS org
                ON org.{self._quote_identifier(ORG_ATTRIBUTE_COLUMNS["org_code"])} =
                   scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["org_code"])}
            WHERE scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])} = ANY(%s)
            ORDER BY scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["document_no"])},
                     scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["role_code"])},
                     scope.{self._quote_identifier(APPLY_FORM_ORG_SCOPE_COLUMNS["org_code"])}
            """,
            (normalized_document_nos,),
        )
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "id": f"{self._strip_text(row[0])}:{self._strip_text(row[1]) or '-'}:{self._strip_text(row[3]) or '<NONE>'}",
                "role_code": self._strip_text(row[1]),
                "role_name": self._strip_text(row[2]),
                "org_code": self._strip_text(row[3]),
                "skip_org_scope_check": bool(row[4]),
                "organization_name": self._strip_text(row[5]),
                "org_unit_name": self._strip_text(row[6]),
                "physical_level": self._strip_text(row[7]),
            }
            for row in rows
            if self._strip_text(row[0]) is not None and self._strip_text(row[1]) is not None
        ]

    def _fetch_process_low_score_rows(
        self,
        cursor,
        assessment_batch_no: str,
        document_nos: Iterable[str],
    ) -> list[dict[str, Any]]:
        normalized_document_nos = [document_no for document_no in document_nos if document_no]
        if not normalized_document_nos:
            return []
        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["document_no"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["role_code"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["role_name"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["org_code"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["dimension_name"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["rule_id"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["rule_summary"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["score"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["detail_conclusion"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["intervention_action"])},
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["evidence_summary"])}
            FROM {RISK_TRUST_ASSESSMENT_DETAIL_TABLE}
            WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessment_batch_no"])} = %s
              AND {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["document_no"])} = ANY(%s)
              AND {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["is_low_score"])} = TRUE
            ORDER BY {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["document_no"])},
                     {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["score"])} ASC,
                     {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["dimension_name"])},
                     {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["role_code"])} NULLS FIRST,
                     {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["org_code"])} NULLS FIRST,
                     {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["rule_id"])}
            """,
            (assessment_batch_no, normalized_document_nos),
        )
        rows = cursor.fetchall()
        return [
            {
                "document_no": self._strip_text(row[0]),
                "id": (
                    f"{self._strip_text(row[0])}:{self._strip_text(row[4]) or '-'}:"
                    f"{self._strip_text(row[5]) or '-'}:{self._strip_text(row[1]) or '-'}:"
                    f"{self._strip_text(row[3]) or '<NONE>'}:{index}"
                ),
                "role_code": self._strip_text(row[1]),
                "role_name": self._strip_text(row[2]),
                "org_code": self._strip_text(row[3]),
                "dimension_name": self._strip_text(row[4]),
                "rule_id": self._strip_text(row[5]),
                "rule_summary": self._strip_text(row[6]),
                "score": self._format_score_value(row[7]),
                "detail_conclusion": self._strip_text(row[8]),
                "intervention_action": self._strip_text(row[9]),
                "evidence_summary": self._strip_text(row[10]),
            }
            for index, row in enumerate(rows, start=1)
            if self._strip_text(row[0]) is not None
        ]

    def _fetch_process_feedback_group_rows(
        self,
        cursor,
        assessment_batch_no: str,
        document_nos: Iterable[str],
    ) -> list[dict[str, Any]]:
        normalized_document_nos = [document_no for document_no in document_nos if document_no]
        if not normalized_document_nos:
            return []
        cursor.execute(
            f"""
            SELECT
                "分组键",
                "单据编号",
                "维度名称",
                "命中规则编码",
                "维度得分",
                "低分原因文案",
                "建议干预动作",
                "申请人组织单位",
                "目标组织单位",
                "原始低分明细数",
                "影响组织数",
                "影响角色数",
                "角色列表",
                "组织列表"
            FROM {RISK_TRUST_LOW_SCORE_FEEDBACK_GROUP_VIEW}
            WHERE "评估批次号" = %s
              AND "单据编号" = ANY(%s)
            ORDER BY "单据编号", "维度得分" ASC, "维度名称", "命中规则编码", "目标组织单位"
            """,
            (assessment_batch_no, normalized_document_nos),
        )
        rows = cursor.fetchall()
        return [
            {
                "group_key": self._strip_text(row[0]),
                "document_no": self._strip_text(row[1]),
                "dimension_name": self._strip_text(row[2]),
                "rule_id": self._strip_text(row[3]),
                "score": self._format_score_value(row[4]),
                "evidence_summary": self._strip_text(row[5]),
                "intervention_action": self._strip_text(row[6]),
                "applicant_org_unit_name": self._strip_text(row[7]),
                "target_org_unit_name": self._strip_text(row[8]),
                "raw_detail_count": int(row[9] or 0),
                "affected_org_count": int(row[10] or 0),
                "affected_role_count": int(row[11] or 0),
                "role_meta": list(row[12] or []),
                "org_meta": list(row[13] or []),
            }
            for row in rows
            if self._strip_text(row[1]) is not None
        ]

    def fetch_document_feedback_overviews(
        self,
        *,
        assessment_batch_no: str,
        document_nos: Iterable[str],
    ) -> dict[str, dict[str, Any]]:
        normalized_document_nos = [
            document_no
            for value in document_nos
            if (document_no := self._strip_text(value)) is not None
        ]
        if not normalized_document_nos:
            return {}

        self.ensure_table()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                summary_rows = self._fetch_process_summary_rows(cursor, assessment_batch_no)
                summary_by_document = {
                    row["document_no"]: row
                    for row in summary_rows
                    if row["document_no"] in normalized_document_nos
                }
                feedback_group_rows = self._fetch_process_feedback_group_rows(
                    cursor,
                    assessment_batch_no,
                    normalized_document_nos,
                )

        grouped_rows_by_document: dict[str, list[dict[str, Any]]] = {}
        for row in feedback_group_rows:
            grouped_rows_by_document.setdefault(row["document_no"], []).append(row)

        return {
            document_no: build_low_score_feedback(
                summary_row=summary_by_document.get(document_no, {"summary_conclusion": None}),
                feedback_group_rows=grouped_rows_by_document.get(document_no, []),
            )
            for document_no in normalized_document_nos
        }

    def _fetch_process_distribution_sections(self, cursor, assessment_batch_no: str) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["summary_conclusion"])},
                COUNT(*)
            FROM {RISK_TRUST_ASSESSMENT_TABLE}
            WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])} = %s
            GROUP BY {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["summary_conclusion"])}
            ORDER BY COUNT(*) DESC, {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["summary_conclusion"])}
            """,
            (assessment_batch_no,),
        )
        conclusion_rows = cursor.fetchall()
        sections.append(
            {
                "id": "summary-conclusion",
                "title": "总结论分布",
                "subtitle": "基于最新评估批次的单据级总结论统计。",
                "items": [
                    {
                        "id": f"summary-conclusion-{index}",
                        "label": self._strip_text(row[0]) or "-",
                        "count": int(row[1] or 0),
                    }
                    for index, row in enumerate(conclusion_rows, start=1)
                ],
            }
        )

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["final_score"])},
                COUNT(*)
            FROM {RISK_TRUST_ASSESSMENT_TABLE}
            WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"])} = %s
            GROUP BY {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["final_score"])}
            ORDER BY {self._quote_identifier(RISK_TRUST_ASSESSMENT_COLUMNS["final_score"])}
            """,
            (assessment_batch_no,),
        )
        score_rows = cursor.fetchall()
        sections.append(
            {
                "id": "score-distribution",
                "title": "最终信任分分布",
                "subtitle": "按单据最终信任分汇总。",
                "items": [
                    {
                        "id": f"score-distribution-{index}",
                        "label": f"{float(row[0]):.1f}",
                        "count": int(row[1] or 0),
                    }
                    for index, row in enumerate(score_rows, start=1)
                ],
            }
        )

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["dimension_name"])},
                COUNT(*)
            FROM {RISK_TRUST_ASSESSMENT_DETAIL_TABLE}
            WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessment_batch_no"])} = %s
              AND {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["is_low_score"])} = TRUE
            GROUP BY {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["dimension_name"])}
            ORDER BY COUNT(*) DESC, {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["dimension_name"])}
            LIMIT 10
            """,
            (assessment_batch_no,),
        )
        dimension_rows = cursor.fetchall()
        sections.append(
            {
                "id": "low-score-dimensions",
                "title": "低分维度分布",
                "subtitle": "只统计低分明细，用于快速定位批次主要风险来源。",
                "items": [
                    {
                        "id": f"low-score-dimensions-{index}",
                        "label": self._strip_text(row[0]) or "-",
                        "count": int(row[1] or 0),
                    }
                    for index, row in enumerate(dimension_rows, start=1)
                ],
            }
        )

        cursor.execute(
            f"""
            SELECT
                {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["rule_id"])},
                COUNT(*)
            FROM {RISK_TRUST_ASSESSMENT_DETAIL_TABLE}
            WHERE {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessment_batch_no"])} = %s
              AND {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["is_low_score"])} = TRUE
            GROUP BY {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["rule_id"])}
            ORDER BY COUNT(*) DESC, {self._quote_identifier(RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["rule_id"])}
            LIMIT 10
            """,
            (assessment_batch_no,),
        )
        rule_rows = cursor.fetchall()
        sections.append(
            {
                "id": "low-score-rules",
                "title": "低分规则 Top 10",
                "subtitle": "便于快速定位当前批次命中最多的低分规则。",
                "items": [
                    {
                        "id": f"low-score-rules-{index}",
                        "label": self._strip_text(row[0]) or "-",
                        "count": int(row[1] or 0),
                    }
                    for index, row in enumerate(rule_rows, start=1)
                ],
            }
        )

        return sections

    def _insert_assessment_summary_rows(self, cursor, rows: list[dict[str, Any]]) -> None:
        insert_columns = [
            RISK_TRUST_ASSESSMENT_COLUMNS["document_no"],
            RISK_TRUST_ASSESSMENT_COLUMNS["assessment_batch_no"],
            RISK_TRUST_ASSESSMENT_COLUMNS["assessment_version"],
            RISK_TRUST_ASSESSMENT_COLUMNS["applicant_hr_type"],
            RISK_TRUST_ASSESSMENT_COLUMNS["applicant_process_level_category"],
            RISK_TRUST_ASSESSMENT_COLUMNS["final_score"],
            RISK_TRUST_ASSESSMENT_COLUMNS["summary_conclusion"],
            RISK_TRUST_ASSESSMENT_COLUMNS["suggested_action"],
            RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_dimension"],
            RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_role_code"],
            RISK_TRUST_ASSESSMENT_COLUMNS["lowest_hit_org_code"],
            RISK_TRUST_ASSESSMENT_COLUMNS["hit_manual_review"],
            RISK_TRUST_ASSESSMENT_COLUMNS["has_low_score_details"],
            RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_count"],
            RISK_TRUST_ASSESSMENT_COLUMNS["low_score_detail_conclusion"],
            RISK_TRUST_ASSESSMENT_COLUMNS["assessment_explain"],
            RISK_TRUST_ASSESSMENT_COLUMNS["input_snapshot"],
            RISK_TRUST_ASSESSMENT_COLUMNS["assessed_at"],
            RISK_TRUST_ASSESSMENT_COLUMNS["created_at"],
            RISK_TRUST_ASSESSMENT_COLUMNS["updated_at"],
        ]
        cursor.executemany(
            f"""
            INSERT INTO {RISK_TRUST_ASSESSMENT_TABLE} (
                {self._quoted_columns(insert_columns)}
            ) VALUES (
                %(document_no)s,
                %(assessment_batch_no)s,
                %(assessment_version)s,
                %(applicant_hr_type)s,
                %(applicant_process_level_category)s,
                %(final_score)s,
                %(summary_conclusion)s,
                %(suggested_action)s,
                %(lowest_hit_dimension)s,
                %(lowest_hit_role_code)s,
                %(lowest_hit_org_code)s,
                %(hit_manual_review)s,
                %(has_low_score_details)s,
                %(low_score_detail_count)s,
                %(low_score_detail_conclusion)s,
                %(assessment_explain)s,
                %(input_snapshot)s::jsonb,
                NOW(),
                NOW(),
                NOW()
            )
            """,
            rows,
        )

    def _insert_assessment_detail_rows(self, cursor, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        insert_columns = [
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["document_no"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessment_batch_no"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessment_version"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["role_code"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["role_name"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["org_code"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["dimension_name"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["rule_id"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["rule_summary"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["score"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["detail_conclusion"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["is_low_score"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["intervention_action"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["evidence_summary"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["evidence_snapshot"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["assessed_at"],
            RISK_TRUST_ASSESSMENT_DETAIL_COLUMNS["created_at"],
        ]
        cursor.executemany(
            f"""
            INSERT INTO {RISK_TRUST_ASSESSMENT_DETAIL_TABLE} (
                {self._quoted_columns(insert_columns)}
            ) VALUES (
                %(document_no)s,
                %(assessment_batch_no)s,
                %(assessment_version)s,
                %(role_code)s,
                %(role_name)s,
                %(org_code)s,
                %(dimension_name)s,
                %(rule_id)s,
                %(rule_summary)s,
                %(score)s,
                %(detail_conclusion)s,
                %(is_low_score)s,
                %(intervention_action)s,
                %(evidence_summary)s,
                %(evidence_snapshot)s::jsonb,
                NOW(),
                NOW()
            )
            """,
            rows,
        )


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

        insert_sql = f"""
            INSERT INTO {self.table_name} (
                {self._quoted_columns(insert_columns)}
            ) VALUES (
                {', '.join(value_placeholders)}
            )
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
                cursor.execute(f"TRUNCATE TABLE {self.table_name}")
                cursor.executemany(insert_sql, payloads)
                person_attributes_store = PostgresPersonAttributesStore(self.settings)
                person_attributes_store._refresh_from_roster(cursor)
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
