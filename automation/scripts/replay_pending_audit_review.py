#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CONFIG_PATH = "automation/config/settings.prod.yaml"
FALLBACK_CONFIG_PATH = "automation/config/settings.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay current pending documents and render stability review summary")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Settings YAML path")
    parser.add_argument("--document-no", default="", help="Optional single document number")
    parser.add_argument("--limit", type=int, default=0, help="Optional document limit; 0 means all")
    parser.add_argument("--rounds", type=int, default=3, help="Replay rounds for stability verification")
    parser.add_argument("--output-prefix", default="", help="Optional output prefix without extension")
    return parser.parse_args()


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def load_runtime_settings(args: argparse.Namespace):
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


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def normalize_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "basic_info": bundle.get("basic_info", {}),
        "applicant_person_attributes": bundle.get("applicant_person_attributes", {}),
        "applicant_org_attributes": bundle.get("applicant_org_attributes", {}),
        "permission_details": sorted(
            [
                {
                    "line_no": row.get("line_no"),
                    "role_code": row.get("role_code"),
                    "role_name": row.get("role_name"),
                    "permission_level": row.get("permission_level"),
                    "skip_org_scope_check": row.get("skip_org_scope_check"),
                    "catalog_matched": row.get("catalog_matched"),
                    "targets": sorted(
                        [
                            {
                                "org_code": target.get("org_code"),
                                "org_auth_level": target.get("org_auth_level"),
                                "org_unit_name": target.get("org_unit_name"),
                            }
                            for target in row.get("targets", [])
                        ],
                        key=lambda item: (
                            str(item.get("org_code") or ""),
                            str(item.get("org_auth_level") or ""),
                            str(item.get("org_unit_name") or ""),
                        ),
                    ),
                }
                for row in bundle.get("permission_details", [])
            ],
            key=lambda item: (str(item.get("line_no") or ""), str(item.get("role_code") or "")),
        ),
        "approval_records": sorted(
            [
                {
                    "record_seq": row.get("record_seq"),
                    "node_name": row.get("node_name"),
                    "approver_employee_no": row.get("approver_employee_no"),
                    "approval_action": row.get("approval_action"),
                    "approval_time": row.get("approval_time"),
                    "approver_org_attributes": row.get("approver_org_attributes", {}),
                }
                for row in bundle.get("approval_records", [])
            ],
            key=lambda item: (int(item.get("record_seq") or 0), str(item.get("node_name") or "")),
        ),
    }


def normalize_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_no": row.get("document_no"),
        "applicant_hr_type": row.get("applicant_hr_type"),
        "applicant_process_level_category": row.get("applicant_process_level_category"),
        "final_score": float(row.get("final_score") or 0),
        "summary_conclusion": row.get("summary_conclusion"),
        "suggested_action": row.get("suggested_action"),
        "lowest_hit_dimension": row.get("lowest_hit_dimension"),
        "lowest_hit_role_code": row.get("lowest_hit_role_code"),
        "lowest_hit_org_code": row.get("lowest_hit_org_code"),
        "hit_manual_review": bool(row.get("hit_manual_review")),
        "has_low_score_details": bool(row.get("has_low_score_details")),
        "low_score_detail_count": int(row.get("low_score_detail_count") or 0),
        "low_score_detail_conclusion": row.get("low_score_detail_conclusion"),
        "assessment_explain": row.get("assessment_explain"),
    }


def normalize_detail_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_no": row.get("document_no"),
        "role_code": row.get("role_code"),
        "role_name": row.get("role_name"),
        "org_code": row.get("org_code"),
        "dimension_name": row.get("dimension_name"),
        "rule_id": row.get("rule_id"),
        "rule_summary": row.get("rule_summary"),
        "score": float(row.get("score") or 0),
        "detail_conclusion": row.get("detail_conclusion"),
        "is_low_score": bool(row.get("is_low_score")),
        "intervention_action": row.get("intervention_action"),
        "evidence_summary": row.get("evidence_summary"),
    }


def analyze_round(
    bundles: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
    round_no: int,
) -> dict[str, Any]:
    bundles_by_document = {
        str(bundle.get("basic_info", {}).get("document_no") or ""): normalize_bundle(bundle)
        for bundle in bundles
        if bundle.get("basic_info", {}).get("document_no")
    }
    summary_by_document = {
        str(row.get("document_no") or ""): normalize_summary_row(row)
        for row in summary_rows
        if row.get("document_no")
    }
    detail_rows_by_document: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in detail_rows:
        document_no = str(row.get("document_no") or "")
        if not document_no:
            continue
        detail_rows_by_document[document_no].append(normalize_detail_row(row))

    for rows in detail_rows_by_document.values():
        rows.sort(
            key=lambda item: (
                float(item["score"]),
                str(item["dimension_name"] or ""),
                str(item["role_code"] or ""),
                str(item["org_code"] or ""),
                str(item["rule_id"] or ""),
            )
        )

    document_nos = sorted(summary_by_document.keys())
    canonical_result_by_document = {
        document_no: {
            "summary": summary_by_document[document_no],
            "details": detail_rows_by_document.get(document_no, []),
        }
        for document_no in document_nos
    }

    return {
        "roundNo": round_no,
        "documentCount": len(document_nos),
        "detailCount": len(detail_rows),
        "bundleHash": stable_hash(bundles_by_document),
        "resultHash": stable_hash(canonical_result_by_document),
        "bundleHashByDocument": {
            document_no: stable_hash(payload) for document_no, payload in bundles_by_document.items()
        },
        "resultHashByDocument": {
            document_no: stable_hash(payload) for document_no, payload in canonical_result_by_document.items()
        },
        "documents": canonical_result_by_document,
        "bundles": bundles_by_document,
    }


def compare_rounds(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    baseline_bundle_hashes = baseline["bundleHashByDocument"]
    current_bundle_hashes = current["bundleHashByDocument"]
    baseline_result_hashes = baseline["resultHashByDocument"]
    current_result_hashes = current["resultHashByDocument"]

    all_document_nos = sorted(set(baseline_bundle_hashes) | set(current_bundle_hashes))
    changed_bundle_documents = [
        document_no
        for document_no in all_document_nos
        if baseline_bundle_hashes.get(document_no) != current_bundle_hashes.get(document_no)
    ]
    changed_result_documents = [
        document_no
        for document_no in all_document_nos
        if baseline_result_hashes.get(document_no) != current_result_hashes.get(document_no)
    ]

    return {
        "roundNo": current["roundNo"],
        "bundleStable": not changed_bundle_documents,
        "resultStable": not changed_result_documents,
        "changedBundleDocuments": changed_bundle_documents,
        "changedResultDocuments": changed_result_documents,
    }


def build_review_summary(round_result: dict[str, Any]) -> dict[str, Any]:
    documents = round_result["documents"]
    bundles = round_result["bundles"]

    status_counter = Counter(
        str((bundles[document_no]["basic_info"].get("document_status") or "").strip() or "<EMPTY>")
        for document_no in documents
    )
    conclusion_counter = Counter(
        str(documents[document_no]["summary"].get("summary_conclusion") or "<EMPTY>")
        for document_no in documents
    )
    action_counter = Counter(
        str(documents[document_no]["summary"].get("suggested_action") or "<EMPTY>")
        for document_no in documents
    )
    score_counter = Counter(
        f"{float(documents[document_no]['summary'].get('final_score') or 0):.1f}"
        for document_no in documents
    )
    lowest_dimension_counter = Counter(
        str(documents[document_no]["summary"].get("lowest_hit_dimension") or "<EMPTY>")
        for document_no in documents
    )

    top_low_score_rules_counter = Counter()
    top_low_score_rule_docs: dict[str, set[str]] = defaultdict(set)
    primary_rule_counter = Counter()
    primary_rule_doc_examples: dict[str, list[str]] = defaultdict(list)
    top_docs_by_low_score_count: list[dict[str, Any]] = []
    approval_zero_score_docs: set[str] = set()
    approval_half_score_docs: set[str] = set()
    docs_with_null_org_auth_level: set[str] = set()
    null_org_auth_level_row_count = 0

    for document_no in sorted(documents.keys()):
        summary = documents[document_no]["summary"]
        details = documents[document_no]["details"]
        low_score_details = [row for row in details if row.get("is_low_score")]
        for row in details:
            if row.get("dimension_name") != "审批人判断":
                continue
            score = float(row.get("score") or 0)
            if score == 0.0:
                approval_zero_score_docs.add(document_no)
            if score == 0.5:
                approval_half_score_docs.add(document_no)

        for permission_row in bundles[document_no]["permission_details"]:
            for target in permission_row.get("targets", []):
                if not target.get("org_code"):
                    continue
                if target.get("org_auth_level") in {None, ""}:
                    docs_with_null_org_auth_level.add(document_no)
                    null_org_auth_level_row_count += 1

        final_score = float(summary.get("final_score") or 0)
        primary_candidates = [
            row for row in low_score_details if float(row.get("score") or 0) == final_score
        ] or details
        primary_candidates = sorted(
            primary_candidates,
            key=lambda item: (
                float(item.get("score") or 0),
                str(item.get("dimension_name") or ""),
                str(item.get("rule_id") or ""),
            ),
        )
        primary_rule = str(primary_candidates[0].get("rule_id") or "<EMPTY>")
        primary_rule_counter[primary_rule] += 1
        if len(primary_rule_doc_examples[primary_rule]) < 3:
            primary_rule_doc_examples[primary_rule].append(document_no)

        for row in low_score_details:
            rule_id = str(row.get("rule_id") or "<EMPTY>")
            top_low_score_rules_counter[rule_id] += 1
            top_low_score_rule_docs[rule_id].add(document_no)

        top_docs_by_low_score_count.append(
            {
                "document_no": document_no,
                "permission_target": bundles[document_no]["basic_info"].get("permission_target"),
                "applicant_name": bundles[document_no]["applicant_person_attributes"].get("employee_name"),
                "final_score": final_score,
                "summary_conclusion": summary.get("summary_conclusion"),
                "suggested_action": summary.get("suggested_action"),
                "lowest_hit_dimension": summary.get("lowest_hit_dimension"),
                "low_score_detail_count": int(summary.get("low_score_detail_count") or 0),
                "primary_rule_id": primary_rule,
            }
        )

    top_docs_by_low_score_count.sort(
        key=lambda item: (-int(item["low_score_detail_count"]), str(item["document_no"]))
    )

    return {
        "documentStatusCounts": dict(status_counter),
        "summaryConclusionCounts": dict(conclusion_counter),
        "suggestedActionCounts": dict(action_counter),
        "finalScoreCounts": dict(score_counter),
        "lowestDimensionCounts": dict(lowest_dimension_counter),
        "primaryRuleCounts": [
            {
                "rule_id": rule_id,
                "document_count": count,
                "sample_documents": primary_rule_doc_examples.get(rule_id, []),
            }
            for rule_id, count in primary_rule_counter.most_common()
        ],
        "topLowScoreRules": [
            {
                "rule_id": rule_id,
                "detail_count": count,
                "affected_document_count": len(top_low_score_rule_docs[rule_id]),
            }
            for rule_id, count in top_low_score_rules_counter.most_common(15)
        ],
        "topDocumentsByLowScoreCount": top_docs_by_low_score_count[:10],
        "openQuestionMetrics": {
            "approvalZeroScoreDocumentCount": len(approval_zero_score_docs),
            "approvalHalfScoreDocumentCount": len(approval_half_score_docs),
            "documentsWithNullOrgAuthLevel": len(docs_with_null_org_auth_level),
            "targetRowsWithNullOrgAuthLevel": null_org_auth_level_row_count,
        },
    }


def render_markdown(
    generated_at: str,
    rounds: int,
    settings_path: Path,
    round_results: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    review_summary: dict[str, Any],
) -> str:
    baseline = round_results[0]
    stable = all(item["bundleStable"] and item["resultStable"] for item in comparisons)
    lines = [
        "# 当前待办单据批量回放稳定性与复核摘要",
        "",
        f"- 生成时间：`{generated_at}`",
        f"- 配置文件：`{settings_path}`",
        f"- 回放轮次：`{rounds}`",
        f"- 单据数：`{baseline['documentCount']}`",
        f"- 明细数：`{baseline['detailCount']}`",
        f"- 稳定性结论：`{'稳定' if stable else '存在差异'}`",
        "",
        "## 1. 回放稳定性",
        "",
    ]
    for result in round_results:
        lines.append(
            f"- 第 `{result['roundNo']}` 轮：bundleHash=`{result['bundleHash'][:12]}`，resultHash=`{result['resultHash'][:12]}`"
        )
    if comparisons:
        lines.append("")
        for item in comparisons:
            lines.append(
                f"- 第 `{item['roundNo']}` 轮对比首轮：bundleStable=`{item['bundleStable']}`，"
                f"resultStable=`{item['resultStable']}`，"
                f"bundle差异单据数=`{len(item['changedBundleDocuments'])}`，"
                f"结果差异单据数=`{len(item['changedResultDocuments'])}`"
            )

    lines.extend(
        [
            "",
            "## 2. 单据级分布",
            "",
            f"- 单据状态分布：`{review_summary['documentStatusCounts']}`",
            f"- 总结论分布：`{review_summary['summaryConclusionCounts']}`",
            f"- 建议动作分布：`{review_summary['suggestedActionCounts']}`",
            f"- 最终信任分分布：`{review_summary['finalScoreCounts']}`",
            f"- 最低命中维度分布：`{review_summary['lowestDimensionCounts']}`",
            "",
            "## 3. 开放口径影响面",
            "",
            f"- 审批维度命中 `0` 分单据数：`{review_summary['openQuestionMetrics']['approvalZeroScoreDocumentCount']}`",
            f"- 审批维度命中 `0.5` 分单据数：`{review_summary['openQuestionMetrics']['approvalHalfScoreDocumentCount']}`",
            f"- 存在 `NULL` 组织授权级别的单据数：`{review_summary['openQuestionMetrics']['documentsWithNullOrgAuthLevel']}`",
            f"- 存在 `NULL` 组织授权级别的目标组织行数：`{review_summary['openQuestionMetrics']['targetRowsWithNullOrgAuthLevel']}`",
            "",
            "## 4. 主要业务复核结论",
            "",
        ]
    )

    primary_rules = review_summary["primaryRuleCounts"][:8]
    for item in primary_rules:
        lines.append(
            f"- `主低分规则 {item['rule_id']}`：`{item['document_count']}` 张单据，样例：`{', '.join(item['sample_documents'])}`"
        )

    lines.extend(["", "## 5. 低分规则 Top 15", ""])
    for item in review_summary["topLowScoreRules"]:
        lines.append(
            f"- `{item['rule_id']}`：低分明细 `{item['detail_count']}` 条，影响单据 `{item['affected_document_count']}` 张"
        )

    lines.extend(["", "## 6. 低分明细条数 Top 10", ""])
    for item in review_summary["topDocumentsByLowScoreCount"]:
        lines.append(
            f"- `{item['document_no']}` / `{item['applicant_name'] or '-'}` / `{item['permission_target'] or '-'}`："
            f"最终分 `{item['final_score']:.1f}`，总结论 `{item['summary_conclusion']}`，"
            f"低分明细 `{item['low_score_detail_count']}` 条，主低分规则 `{item['primary_rule_id']}`"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    from automation.db.postgres import PostgresRiskTrustStore
    from automation.rules import RiskTrustEvaluator, load_risk_trust_package

    settings, settings_path = load_runtime_settings(args)
    logs_dir = resolve_path(settings.runtime.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    store = PostgresRiskTrustStore(settings.db)
    package = load_risk_trust_package(REPO_ROOT / "automation" / "config" / "rules")
    evaluator = RiskTrustEvaluator(package)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_prefix = (
        resolve_path(args.output_prefix)
        if args.output_prefix.strip()
        else logs_dir / f"pending_audit_replay_review_{timestamp}"
    )

    round_results: list[dict[str, Any]] = []
    for round_no in range(1, max(args.rounds, 1) + 1):
        bundles = store.fetch_document_bundles(
            document_no=args.document_no.strip() or None,
            limit=max(args.limit, 0),
        )
        summary_rows, detail_rows = evaluator.evaluate_documents(
            bundles=bundles,
            assessment_batch_no=f"replay_round_{round_no}",
        )
        round_results.append(analyze_round(bundles, summary_rows, detail_rows, round_no))

    baseline = round_results[0]
    comparisons = [compare_rounds(baseline, result) for result in round_results[1:]]
    review_summary = build_review_summary(baseline)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "generated_at": generated_at,
        "settings_path": str(settings_path),
        "rounds": args.rounds,
        "document_no": args.document_no.strip() or None,
        "limit": max(args.limit, 0),
        "assessment_version": package.version,
        "round_results": [
            {
                "roundNo": result["roundNo"],
                "documentCount": result["documentCount"],
                "detailCount": result["detailCount"],
                "bundleHash": result["bundleHash"],
                "resultHash": result["resultHash"],
            }
            for result in round_results
        ],
        "comparisons": comparisons,
        "review_summary": review_summary,
        "baseline_documents": baseline["documents"],
    }

    json_path = output_prefix.with_suffix(".json")
    md_path = output_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        render_markdown(generated_at, args.rounds, settings_path, round_results, comparisons, review_summary),
        encoding="utf-8",
    )

    print(json.dumps({
        "json_path": str(json_path),
        "md_path": str(md_path),
        "stable": all(item["bundleStable"] and item["resultStable"] for item in comparisons),
        "document_count": baseline["documentCount"],
        "detail_count": baseline["detailCount"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
