#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.utils.config_loader import load_settings

DEFAULT_CONFIG_PATH = "automation/config/settings.yaml"
PROD_CONFIG_PATH = "automation/config/settings.prod.yaml"

REQUIRED_TABLES = [
    "申请单基本信息",
    "申请单权限列表",
    "申请单审批记录",
    "申请表组织范围",
    "人员属性查询",
    "在职花名册表",
    "组织列表",
    "城市所属战区",
    "组织属性查询",
    "权限列表",
    "申请单风险信任评估",
    "申请单风险信任评估明细",
]

REQUIRED_FUNCTIONS = [
    "refresh_组织属性查询",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PostgreSQL admin helper for clawcheck Windows migration")
    parser.add_argument("action", choices=["connection-info", "probe", "acceptance"], help="Action to execute")
    parser.add_argument("--config", default="", help="Settings YAML path. Defaults to prod when available.")
    parser.add_argument("--dump-json", default="", help="Optional JSON output path")
    parser.add_argument("--include-password", action="store_true", help="Include password in connection-info output")
    parser.add_argument("--output-format", choices=["json", "env"], default="json", help="connection-info output format")
    parser.add_argument("--host", default="", help="Override db.host")
    parser.add_argument("--port", type=int, default=0, help="Override db.port")
    parser.add_argument("--dbname", default="", help="Override db.dbname")
    parser.add_argument("--user", default="", help="Override db.user")
    parser.add_argument("--password", default="", help="Override db.password")
    parser.add_argument("--schema", default="", help="Override db.schema")
    parser.add_argument("--sslmode", default="", help="Override db.sslmode")
    return parser.parse_args()


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def resolve_default_config_path(explicit_config: str) -> Path:
    if explicit_config.strip():
        return resolve_path(explicit_config.strip())
    prod_path = resolve_path(PROD_CONFIG_PATH)
    if prod_path.exists():
        return prod_path
    return resolve_path(DEFAULT_CONFIG_PATH)


def load_database_settings(args: argparse.Namespace):
    settings_path = resolve_default_config_path(args.config)
    if not isinstance(settings_path, Path):
        settings_path = Path(settings_path)
    settings = load_settings(settings_path)

    settings.db.host = os.getenv("IERP_PG_HOST", settings.db.host)
    settings.db.port = int(os.getenv("IERP_PG_PORT", str(settings.db.port)))
    settings.db.dbname = os.getenv("IERP_PG_DBNAME", settings.db.dbname)
    settings.db.user = os.getenv("IERP_PG_USER", settings.db.user)
    settings.db.password = os.getenv("IERP_PG_PASSWORD", settings.db.password)
    settings.db.schema = os.getenv("IERP_PG_SCHEMA", settings.db.schema)
    settings.db.sslmode = os.getenv("IERP_PG_SSLMODE", settings.db.sslmode)

    if args.host.strip():
        settings.db.host = args.host.strip()
    if args.port:
        settings.db.port = int(args.port)
    if args.dbname.strip():
        settings.db.dbname = args.dbname.strip()
    if args.user.strip():
        settings.db.user = args.user.strip()
    if args.password.strip():
        settings.db.password = args.password
    if args.schema.strip():
        settings.db.schema = args.schema.strip()
    if args.sslmode.strip():
        settings.db.sslmode = args.sslmode.strip()

    return settings_path, settings.db


def build_connection_payload(settings_path: Path, db_settings, include_password: bool) -> dict[str, Any]:
    if not isinstance(settings_path, Path):
        settings_path = Path(settings_path)
    try:
        config_path = settings_path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        config_path = settings_path.resolve().as_posix()
    payload = {
        "configPath": config_path,
        "host": db_settings.host,
        "port": db_settings.port,
        "dbname": db_settings.dbname,
        "user": db_settings.user,
        "schema": db_settings.schema,
        "sslmode": db_settings.sslmode,
    }
    if include_password:
        payload["password"] = db_settings.password
    return payload


def format_env_output(connection_payload: dict[str, Any]) -> str:
    env_map = {
        "PGHOST": connection_payload.get("host", ""),
        "PGPORT": str(connection_payload.get("port", "")),
        "PGDATABASE": connection_payload.get("dbname", ""),
        "PGUSER": connection_payload.get("user", ""),
        "PGPASSWORD": connection_payload.get("password", ""),
        "PGSSLMODE": connection_payload.get("sslmode", ""),
    }
    return "\n".join(f"{key}={value}" for key, value in env_map.items())


def function_exists(cursor, function_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = current_schema()
              AND p.proname = %s
        )
        """,
        (function_name,),
    )
    row = cursor.fetchone()
    return bool(row[0]) if row else False


def build_acceptance_status(required_tables: list[dict[str, Any]], required_functions: list[dict[str, Any]]) -> dict[str, Any]:
    missing_tables = [item["tableName"] for item in required_tables if not item["exists"]]
    missing_functions = [item["functionName"] for item in required_functions if not item["exists"]]
    passed = not missing_tables and not missing_functions
    return {
        "passed": passed,
        "missingTables": missing_tables,
        "missingFunctions": missing_functions,
        "message": (
            "数据库对象验收通过"
            if passed
            else "数据库对象验收失败，请先补齐缺失表/函数"
        ),
    }


def collect_probe_payload(settings_path: Path, db_settings) -> dict[str, Any]:
    from automation.db.postgres import PostgresMasterDataStore, _PostgresStoreBase

    base_store = _PostgresStoreBase(db_settings)
    master_data_store = PostgresMasterDataStore(db_settings)

    with base_store.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database(),
                    current_user,
                    current_schema(),
                    inet_server_addr()::text,
                    inet_server_port(),
                    version()
                """
            )
            server_row = cursor.fetchone() or ("", "", "", "", None, "")
            required_tables = [
                {
                    "tableName": table_name,
                    "exists": base_store._table_exists(cursor, table_name),
                }
                for table_name in REQUIRED_TABLES
            ]
            required_functions = [
                {
                    "functionName": function_name,
                    "exists": function_exists(cursor, function_name),
                }
                for function_name in REQUIRED_FUNCTIONS
            ]

    acceptance = build_acceptance_status(required_tables, required_functions)
    master_data_summary = master_data_store.fetch_master_data_workbench()

    return {
        "status": "ok",
        "checkedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "connection": build_connection_payload(settings_path, db_settings, include_password=False),
        "server": {
            "currentDatabase": server_row[0] or "",
            "currentUser": server_row[1] or "",
            "currentSchema": server_row[2] or "",
            "serverAddress": server_row[3] or "",
            "serverPort": int(server_row[4] or 0),
            "version": server_row[5] or "",
        },
        "requiredTables": required_tables,
        "requiredFunctions": required_functions,
        "acceptance": acceptance,
        "masterData": master_data_summary,
    }


def emit_payload(payload: dict[str, Any], dump_json: str) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if dump_json.strip():
        dump_path = resolve_path(dump_json.strip())
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(rendered, encoding="utf-8")


def main() -> int:
    args = parse_args()
    settings_path, db_settings = load_database_settings(args)

    if args.action == "connection-info":
        payload = build_connection_payload(settings_path, db_settings, include_password=args.include_password)
        if args.output_format == "env":
            print(format_env_output(payload))
        else:
            emit_payload(payload, args.dump_json)
        return 0

    try:
        probe_payload = collect_probe_payload(settings_path, db_settings)
    except Exception as exc:  # noqa: BLE001
        error_payload = {
            "status": "error",
            "checkedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "connection": build_connection_payload(settings_path, db_settings, include_password=False),
            "message": str(exc),
        }
        emit_payload(error_payload, args.dump_json)
        return 1

    if args.action == "probe":
        emit_payload(probe_payload, args.dump_json)
        return 0

    acceptance_payload = {
        "status": "ok" if probe_payload["acceptance"]["passed"] else "failed",
        "checkedAt": probe_payload["checkedAt"],
        "connection": probe_payload["connection"],
        "acceptance": probe_payload["acceptance"],
        "masterData": probe_payload["masterData"],
        "requiredTables": probe_payload["requiredTables"],
        "requiredFunctions": probe_payload["requiredFunctions"],
    }
    emit_payload(acceptance_payload, args.dump_json)
    return 0 if probe_payload["acceptance"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
