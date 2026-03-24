#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterator, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CONFIG_PATH = "automation/config/settings.prod.yaml"
FALLBACK_CONFIG_PATH = "automation/config/settings.yaml"
PERSON_TABLE = "人员属性查询"
ORG_TABLE = "组织属性查询"
REQUIRED_ORG_COLUMNS = ("行政组织编码", "所在城市", "组织单位", "所属战区")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export enhanced person attributes workbook")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Settings YAML path")
    parser.add_argument("--output", default="", help="Optional workbook output path")
    parser.add_argument("--fetch-size", type=int, default=2000, help="Database fetch size per batch")
    return parser.parse_args()


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _load_settings(args: argparse.Namespace):
    from automation.utils.config_loader import load_settings

    settings_path = resolve_path(args.config)
    if args.config == DEFAULT_CONFIG_PATH and not settings_path.exists():
        settings_path = resolve_path(FALLBACK_CONFIG_PATH)
    settings = load_settings(settings_path)
    settings.db.host = os.getenv("IERP_PG_HOST", settings.db.host)
    settings.db.port = int(os.getenv("IERP_PG_PORT", str(settings.db.port)))
    settings.db.dbname = os.getenv("IERP_PG_DBNAME", settings.db.dbname)
    settings.db.user = os.getenv("IERP_PG_USER", settings.db.user)
    settings.db.password = os.getenv("IERP_PG_PASSWORD", settings.db.password)
    settings.db.schema = os.getenv("IERP_PG_SCHEMA", settings.db.schema)
    settings.db.sslmode = os.getenv("IERP_PG_SSLMODE", settings.db.sslmode)
    return settings, settings_path


def _fetch_table_columns(cursor, table_name: str) -> list[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [str(row[0]) for row in cursor.fetchall()]


def _iter_cursor_rows(cursor, query: str, fetch_size: int) -> Iterator[Sequence[object]]:
    cursor.execute(query)
    while True:
        rows = cursor.fetchmany(fetch_size)
        if not rows:
            break
        for row in rows:
            yield row


def main() -> int:
    args = parse_args()

    from automation.db.postgres import PostgresPersonAttributesStore
    from automation.reporting import (
        build_person_attributes_enhanced_headers,
        build_person_attributes_enhanced_query,
        render_person_attributes_enhanced_workbook,
    )
    from automation.utils.logger import setup_logger

    if args.fetch_size <= 0:
        raise ValueError("--fetch-size must be a positive integer")

    settings, settings_path = _load_settings(args)
    logs_dir = resolve_path(settings.runtime.logs_dir)
    logger = setup_logger(logs_dir)
    logger.info("Settings: %s", settings_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = (
        resolve_path(args.output)
        if args.output.strip()
        else logs_dir / f"人员属性查询增强报表_{timestamp}.xlsx"
    )

    store = PostgresPersonAttributesStore(settings.db)
    with store.connect() as connection:
        with connection.cursor() as cursor:
            person_columns = _fetch_table_columns(cursor, PERSON_TABLE)
            if not person_columns:
                raise ValueError(f'Table "{PERSON_TABLE}" does not exist or has no columns')

            org_columns = _fetch_table_columns(cursor, ORG_TABLE)
            missing_org_columns = [column for column in REQUIRED_ORG_COLUMNS if column not in org_columns]
            if missing_org_columns:
                raise ValueError(
                    f'Table "{ORG_TABLE}" is missing required columns: {", ".join(missing_org_columns)}'
                )

            headers = build_person_attributes_enhanced_headers(person_columns)
            query = build_person_attributes_enhanced_query(person_columns)

            cursor.execute(f'SELECT COUNT(*) FROM "{PERSON_TABLE}"')
            person_row_count = int(cursor.fetchone()[0] or 0)

            exported_row_count = render_person_attributes_enhanced_workbook(
                headers=headers,
                rows=_iter_cursor_rows(cursor, query, args.fetch_size),
                output_path=output_path,
            )

    logger.info(
        "Enhanced person attributes workbook exported: %s (rows=%s, columns=%s)",
        output_path,
        exported_row_count,
        len(headers),
    )

    if exported_row_count != person_row_count:
        raise RuntimeError(
            f"Exported row count mismatch: expected {person_row_count}, got {exported_row_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
