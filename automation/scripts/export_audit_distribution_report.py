#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CONFIG_PATH = "automation/config/settings.prod.yaml"
FALLBACK_CONFIG_PATH = "automation/config/settings.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export audit distribution workbook")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Settings YAML path")
    parser.add_argument("--batch-no", default="", help="Assessment batch number; defaults to latest batch")
    parser.add_argument("--output", default="", help="Optional workbook output path")
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


def main() -> int:
    args = parse_args()
    from automation.db.postgres import PostgresRiskTrustStore
    from automation.reporting import load_audit_distribution_workbook_data, render_audit_distribution_workbook
    from automation.rules import load_risk_trust_package
    from automation.utils.logger import setup_logger

    settings, settings_path = _load_settings(args)
    logs_dir = resolve_path(settings.runtime.logs_dir)
    logger = setup_logger(logs_dir)
    logger.info("Settings: %s", settings_path)

    store = PostgresRiskTrustStore(settings.db)
    package = load_risk_trust_package(REPO_ROOT / "automation" / "config" / "rules")
    workbook_data = load_audit_distribution_workbook_data(
        store=store,
        batch_no=args.batch_no.strip(),
        ignored_node_names=list(package.constants.get("ignored_approval_node_names", [])),
    )
    output_path = (
        resolve_path(args.output)
        if args.output.strip()
        else logs_dir / f"audit_distribution_{workbook_data.batch_no}.xlsx"
    )
    render_audit_distribution_workbook(
        batch_no=workbook_data.batch_no,
        assessment_version=workbook_data.assessment_version,
        summary_rows=workbook_data.summary_rows,
        detail_rows=workbook_data.detail_rows,
        approval_rows=workbook_data.approval_rows,
        ignored_node_names=workbook_data.ignored_node_names,
        document_feedback_rows=workbook_data.document_feedback_rows,
        output_path=output_path,
    )
    logger.info("Audit distribution workbook exported: %s", output_path)
    logger.info(
        "Export summary: batch=%s document_count=%s detail_count=%s approval_record_count=%s",
        workbook_data.batch_no,
        len(workbook_data.summary_rows),
        len(workbook_data.detail_rows),
        len(workbook_data.approval_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
