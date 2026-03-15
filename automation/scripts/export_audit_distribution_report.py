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


def _fetch_latest_batch_no(cursor) -> str | None:
    cursor.execute(
        '''
        SELECT "评估批次号"
        FROM "申请单风险信任评估"
        ORDER BY "评估时间" DESC, "评估ID" DESC
        LIMIT 1
        '''
    )
    row = cursor.fetchone()
    if not row or not row[0]:
        return None
    return str(row[0]).strip() or None


def _fetch_summary_rows(cursor, batch_no: str) -> list[dict[str, object]]:
    cursor.execute(
        '''
        SELECT
            "单据编号",
            "评估版本",
            "最终信任分",
            "总结论",
            "建议动作",
            "最低命中维度",
            "最低命中角色编码",
            "最低命中组织编码",
            "是否命中人工干预",
            "是否存在低分明细",
            "低分明细条数",
            "低分明细结论"
        FROM "申请单风险信任评估"
        WHERE "评估批次号" = %s
        ORDER BY "最终信任分", "单据编号"
        ''',
        (batch_no,),
    )
    rows = cursor.fetchall()
    return [
        {
            "document_no": row[0],
            "assessment_version": row[1],
            "final_score": row[2],
            "summary_conclusion": row[3],
            "suggested_action": row[4],
            "lowest_hit_dimension": row[5],
            "lowest_hit_role_code": row[6],
            "lowest_hit_org_code": row[7],
            "hit_manual_review": row[8],
            "has_low_score_details": row[9],
            "low_score_detail_count": row[10],
            "low_score_detail_conclusion": row[11],
        }
        for row in rows
    ]


def _fetch_detail_rows(cursor, batch_no: str) -> list[dict[str, object]]:
    cursor.execute(
        '''
        SELECT
            "单据编号",
            "角色编码",
            "组织编码",
            "维度名称",
            "命中规则编码",
            "命中规则说明",
            "维度得分",
            "明细结论",
            "是否低分明细",
            "建议干预动作"
        FROM "申请单风险信任评估明细"
        WHERE "评估批次号" = %s
        ORDER BY "维度得分", "单据编号", "维度名称", "命中规则编码"
        ''',
        (batch_no,),
    )
    rows = cursor.fetchall()
    return [
        {
            "document_no": row[0],
            "role_code": row[1],
            "org_code": row[2],
            "dimension_name": row[3],
            "rule_id": row[4],
            "rule_summary": row[5],
            "score": row[6],
            "detail_conclusion": row[7],
            "is_low_score": row[8],
            "intervention_action": row[9],
        }
        for row in rows
    ]


def _fetch_approval_rows(cursor, document_nos: list[str]) -> list[dict[str, object]]:
    if not document_nos:
        return []
    cursor.execute(
        '''
        SELECT
            "单据编号",
            "节点名称",
            "审批动作",
            "工号"
        FROM "申请单审批记录"
        WHERE "单据编号" = ANY(%s)
        ORDER BY "单据编号", "审批记录顺序号"
        ''',
        (document_nos,),
    )
    rows = cursor.fetchall()
    return [
        {
            "document_no": row[0],
            "node_name": row[1],
            "approval_action": row[2],
            "approver_employee_no": row[3],
        }
        for row in rows
    ]


def main() -> int:
    args = parse_args()
    from automation.db.postgres import PostgresRiskTrustStore
    from automation.reporting.low_score_feedback import display_summary_conclusion
    from automation.reporting import render_audit_distribution_workbook
    from automation.rules import load_risk_trust_package
    from automation.utils.logger import setup_logger

    settings, settings_path = _load_settings(args)
    logs_dir = resolve_path(settings.runtime.logs_dir)
    logger = setup_logger(logs_dir)
    logger.info("Settings: %s", settings_path)

    store = PostgresRiskTrustStore(settings.db)
    package = load_risk_trust_package(REPO_ROOT / "automation" / "config" / "rules")
    with store.connect() as connection:
        with connection.cursor() as cursor:
            batch_no = args.batch_no.strip() or _fetch_latest_batch_no(cursor)
            if not batch_no:
                raise ValueError("No assessment batch found in 申请单风险信任评估")
            summary_rows = _fetch_summary_rows(cursor, batch_no)
            if not summary_rows:
                raise ValueError(f"No summary rows found for batch {batch_no}")
            detail_rows = _fetch_detail_rows(cursor, batch_no)
            approval_rows = _fetch_approval_rows(
                cursor,
                [str(row["document_no"]).strip() for row in summary_rows if row.get("document_no")],
            )

    for row in summary_rows:
        row["summary_conclusion_label"] = display_summary_conclusion(str(row.get("summary_conclusion") or "").strip() or None)

    feedback_overviews = store.fetch_document_feedback_overviews(
        assessment_batch_no=batch_no,
        document_nos=[str(row["document_no"]).strip() for row in summary_rows if row.get("document_no")],
    )
    document_feedback_rows: list[dict[str, object]] = []
    for row in summary_rows:
        document_no = str(row.get("document_no") or "").strip()
        if not document_no:
            continue
        feedback_overview = feedback_overviews.get(document_no, {})
        feedback_stats = {
            str(item.get("label") or ""): str(item.get("value") or "")
            for item in feedback_overview.get("feedbackStats", [])
            if isinstance(item, dict)
        }
        feedback_lines = [
            str(item.get("summary") or "").strip()
            for item in feedback_overview.get("feedbackGroups", [])
            if isinstance(item, dict) and str(item.get("summary") or "").strip()
        ]
        document_feedback_rows.append(
            {
                "document_no": document_no,
                "summary_conclusion_label": feedback_overview.get("summaryConclusionLabel"),
                "risk_type_count": feedback_stats.get("风险类型数", "0"),
                "affected_org_unit_count": feedback_stats.get("影响组织单位数", "0"),
                "affected_org_count": feedback_stats.get("影响组织数", "0"),
                "affected_role_count": feedback_stats.get("影响角色数", "0"),
                "raw_low_score_detail_count": feedback_stats.get("原始低分明细数", "0"),
                "feedback_summary": "\n".join(feedback_lines),
            }
        )

    assessment_version = str(summary_rows[0]["assessment_version"]).strip()
    output_path = (
        resolve_path(args.output)
        if args.output.strip()
        else logs_dir / f"audit_distribution_{batch_no}.xlsx"
    )
    render_audit_distribution_workbook(
        batch_no=batch_no,
        assessment_version=assessment_version,
        summary_rows=summary_rows,
        detail_rows=detail_rows,
        approval_rows=approval_rows,
        ignored_node_names=list(package.constants.get("ignored_approval_node_names", [])),
        document_feedback_rows=document_feedback_rows,
        output_path=output_path,
    )
    logger.info("Audit distribution workbook exported: %s", output_path)
    logger.info(
        "Export summary: batch=%s document_count=%s detail_count=%s approval_record_count=%s",
        batch_no,
        len(summary_rows),
        len(detail_rows),
        len(approval_rows),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
