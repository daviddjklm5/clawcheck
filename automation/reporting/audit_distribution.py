from __future__ import annotations

from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


def _score_text(value: Any) -> str:
    if isinstance(value, Decimal):
        return f"{value:.1f}"
    if isinstance(value, (float, int)):
        return f"{float(value):.1f}"
    text = str(value).strip()
    return text or "<NULL>"


def _text(value: Any) -> str:
    if value is None:
        return "<NULL>"
    text = str(value).strip()
    return text or "<NULL>"


def build_document_stats(summary_rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(summary_rows)
    conclusion_counter = Counter(_text(row.get("summary_conclusion")) for row in rows)
    score_counter = Counter(_score_text(row.get("final_score")) for row in rows)
    manual_review_documents = sum(1 for row in rows if bool(row.get("hit_manual_review")))
    low_score_documents = sum(1 for row in rows if bool(row.get("has_low_score_details")))
    return {
        "document_count": len(rows),
        "manual_review_document_count": manual_review_documents,
        "low_score_document_count": low_score_documents,
        "summary_conclusion_distribution": sorted(
            (
                {"总结论": conclusion, "单据数": count}
                for conclusion, count in conclusion_counter.items()
            ),
            key=lambda item: (-item["单据数"], item["总结论"]),
        ),
        "final_score_distribution": sorted(
            (
                {"最终信任分": score, "单据数": count}
                for score, count in score_counter.items()
            ),
            key=lambda item: (float(item["最终信任分"]), item["最终信任分"]),
        ),
    }


def build_dimension_stats(detail_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for row in detail_rows:
        dimension_name = _text(row.get("dimension_name"))
        item = stats.setdefault(
            dimension_name,
            {
                "维度名称": dimension_name,
                "命中次数": 0,
                "低分命中次数": 0,
                "涉及单据数": set(),
                "低分涉及单据数": set(),
                "分值分布": Counter(),
            },
        )
        item["命中次数"] += 1
        item["涉及单据数"].add(_text(row.get("document_no")))
        score_text = _score_text(row.get("score"))
        item["分值分布"][score_text] += 1
        if bool(row.get("is_low_score")):
            item["低分命中次数"] += 1
            item["低分涉及单据数"].add(_text(row.get("document_no")))

    result: list[dict[str, Any]] = []
    for item in stats.values():
        distribution = "；".join(
            f"{score}:{count}"
            for score, count in sorted(item["分值分布"].items(), key=lambda pair: float(pair[0]))
        )
        result.append(
            {
                "维度名称": item["维度名称"],
                "命中次数": item["命中次数"],
                "低分命中次数": item["低分命中次数"],
                "涉及单据数": len(item["涉及单据数"]),
                "低分涉及单据数": len(item["低分涉及单据数"]),
                "分值分布": distribution,
            }
        )
    result.sort(key=lambda item: (-item["命中次数"], item["维度名称"]))
    return result


def build_rule_stats(detail_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[tuple[str, str], dict[str, Any]] = {}
    for row in detail_rows:
        dimension_name = _text(row.get("dimension_name"))
        rule_id = _text(row.get("rule_id"))
        key = (dimension_name, rule_id)
        item = stats.setdefault(
            key,
            {
                "维度名称": dimension_name,
                "命中规则编码": rule_id,
                "命中规则说明": _text(row.get("rule_summary")),
                "命中次数": 0,
                "低分命中次数": 0,
                "涉及单据数": set(),
                "低分涉及单据数": set(),
                "最低分": None,
                "最高分": None,
            },
        )
        item["命中次数"] += 1
        item["涉及单据数"].add(_text(row.get("document_no")))
        score_value = float(row.get("score") or 0.0)
        item["最低分"] = score_value if item["最低分"] is None else min(item["最低分"], score_value)
        item["最高分"] = score_value if item["最高分"] is None else max(item["最高分"], score_value)
        if bool(row.get("is_low_score")):
            item["低分命中次数"] += 1
            item["低分涉及单据数"].add(_text(row.get("document_no")))

    result: list[dict[str, Any]] = []
    for item in stats.values():
        result.append(
            {
                "维度名称": item["维度名称"],
                "命中规则编码": item["命中规则编码"],
                "命中规则说明": item["命中规则说明"],
                "命中次数": item["命中次数"],
                "低分命中次数": item["低分命中次数"],
                "涉及单据数": len(item["涉及单据数"]),
                "低分涉及单据数": len(item["低分涉及单据数"]),
                "最低分": f"{item['最低分']:.1f}",
                "最高分": f"{item['最高分']:.1f}",
            }
        )
    result.sort(key=lambda item: (-item["命中次数"], item["维度名称"], item["命中规则编码"]))
    return result


def build_approval_node_stats(
    approval_rows: Iterable[dict[str, Any]],
    ignored_node_names: Iterable[str],
) -> list[dict[str, Any]]:
    ignored_set = {_text(name) for name in ignored_node_names}
    stats: dict[str, dict[str, Any]] = {}
    for row in approval_rows:
        node_name = _text(row.get("node_name"))
        action = _text(row.get("approval_action"))
        item = stats.setdefault(
            node_name,
            {
                "节点名称": node_name,
                "记录数": 0,
                "涉及单据数": set(),
                "审批人数": set(),
                "提交记录数": 0,
                "同意记录数": 0,
                "驳回记录数": 0,
                "待审核记录数": 0,
                "其他动作记录数": 0,
                "是否排除评分节点": "是" if node_name in ignored_set else "否",
            },
        )
        item["记录数"] += 1
        item["涉及单据数"].add(_text(row.get("document_no")))
        approver_no = _text(row.get("approver_employee_no"))
        if approver_no != "<NULL>":
            item["审批人数"].add(approver_no)
        if action == "提交":
            item["提交记录数"] += 1
        elif action == "同意":
            item["同意记录数"] += 1
        elif "驳回" in action:
            item["驳回记录数"] += 1
        elif action == "待审核":
            item["待审核记录数"] += 1
        else:
            item["其他动作记录数"] += 1

    result: list[dict[str, Any]] = []
    for item in stats.values():
        result.append(
            {
                "节点名称": item["节点名称"],
                "记录数": item["记录数"],
                "涉及单据数": len(item["涉及单据数"]),
                "审批人数": len(item["审批人数"]),
                "提交记录数": item["提交记录数"],
                "同意记录数": item["同意记录数"],
                "驳回记录数": item["驳回记录数"],
                "待审核记录数": item["待审核记录数"],
                "其他动作记录数": item["其他动作记录数"],
                "是否排除评分节点": item["是否排除评分节点"],
            }
        )
    result.sort(key=lambda item: (-item["记录数"], item["节点名称"]))
    return result


def render_audit_distribution_workbook(
    *,
    batch_no: str,
    assessment_version: str,
    summary_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
    approval_rows: list[dict[str, Any]],
    ignored_node_names: list[str],
    document_feedback_rows: list[dict[str, Any]] | None = None,
    output_path: Path,
) -> Path:
    workbook = Workbook()
    document_stats = build_document_stats(summary_rows)
    dimension_stats = build_dimension_stats(detail_rows)
    rule_stats = build_rule_stats(detail_rows)
    approval_node_stats = build_approval_node_stats(approval_rows, ignored_node_names)
    low_score_rows = [row for row in detail_rows if bool(row.get("is_low_score"))]

    overview_sheet = workbook.active
    overview_sheet.title = "批次总览"
    _append_section(
        overview_sheet,
        "批次信息",
        ["指标", "数值"],
        [
            ["评估批次号", batch_no],
            ["评估版本", assessment_version],
            ["导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ["单据数", document_stats["document_count"]],
            ["明细行数", len(detail_rows)],
            ["审批记录数", len(approval_rows)],
            ["命中人工干预单据数", document_stats["manual_review_document_count"]],
            ["存在低分明细单据数", document_stats["low_score_document_count"]],
        ],
    )
    _append_section(
        overview_sheet,
        "总结论分布",
        ["总结论", "单据数"],
        [[row["总结论"], row["单据数"]] for row in document_stats["summary_conclusion_distribution"]],
    )
    _append_section(
        overview_sheet,
        "最终信任分分布",
        ["最终信任分", "单据数"],
        [[row["最终信任分"], row["单据数"]] for row in document_stats["final_score_distribution"]],
    )

    _append_table_sheet(
        workbook,
        "单据结果",
        [
            "单据编号",
            "最终信任分",
            "展示结论",
            "总结论",
            "建议动作",
            "最低命中维度",
            "最低命中角色编码",
            "最低命中组织编码",
            "是否命中人工干预",
            "低分明细条数",
            "低分明细结论",
        ],
        [
            [
                _text(row.get("document_no")),
                _score_text(row.get("final_score")),
                _text(row.get("summary_conclusion_label")),
                _text(row.get("summary_conclusion")),
                _text(row.get("suggested_action")),
                _text(row.get("lowest_hit_dimension")),
                _text(row.get("lowest_hit_role_code")),
                _text(row.get("lowest_hit_org_code")),
                "是" if bool(row.get("hit_manual_review")) else "否",
                int(row.get("low_score_detail_count") or 0),
                _text(row.get("low_score_detail_conclusion")),
            ]
            for row in sorted(
                summary_rows,
                key=lambda item: (float(item.get("final_score") or 0.0), _text(item.get("document_no"))),
            )
        ],
    )
    if document_feedback_rows:
        _append_table_sheet(
            workbook,
            "104聚合反馈",
            [
                "单据编号",
                "展示结论",
                "风险类型数",
                "影响组织单位数",
                "影响组织数",
                "影响角色数",
                "原始低分明细数",
                "聚合反馈摘要",
            ],
            [
                [
                    _text(row.get("document_no")),
                    _text(row.get("summary_conclusion_label")),
                    _text(row.get("risk_type_count")),
                    _text(row.get("affected_org_unit_count")),
                    _text(row.get("affected_org_count")),
                    _text(row.get("affected_role_count")),
                    _text(row.get("raw_low_score_detail_count")),
                    _text(row.get("feedback_summary")),
                ]
                for row in sorted(document_feedback_rows, key=lambda item: _text(item.get("document_no")))
            ],
        )
    _append_table_sheet(
        workbook,
        "维度分布",
        ["维度名称", "命中次数", "低分命中次数", "涉及单据数", "低分涉及单据数", "分值分布"],
        [
            [
                row["维度名称"],
                row["命中次数"],
                row["低分命中次数"],
                row["涉及单据数"],
                row["低分涉及单据数"],
                row["分值分布"],
            ]
            for row in dimension_stats
        ],
    )
    _append_table_sheet(
        workbook,
        "规则分布",
        ["维度名称", "命中规则编码", "命中规则说明", "命中次数", "低分命中次数", "涉及单据数", "低分涉及单据数", "最低分", "最高分"],
        [
            [
                row["维度名称"],
                row["命中规则编码"],
                row["命中规则说明"],
                row["命中次数"],
                row["低分命中次数"],
                row["涉及单据数"],
                row["低分涉及单据数"],
                row["最低分"],
                row["最高分"],
            ]
            for row in rule_stats
        ],
    )
    _append_table_sheet(
        workbook,
        "审批节点分布",
        ["节点名称", "记录数", "涉及单据数", "审批人数", "提交记录数", "同意记录数", "驳回记录数", "待审核记录数", "其他动作记录数", "是否排除评分节点"],
        [
            [
                row["节点名称"],
                row["记录数"],
                row["涉及单据数"],
                row["审批人数"],
                row["提交记录数"],
                row["同意记录数"],
                row["驳回记录数"],
                row["待审核记录数"],
                row["其他动作记录数"],
                row["是否排除评分节点"],
            ]
            for row in approval_node_stats
        ],
    )
    _append_table_sheet(
        workbook,
        "低分明细",
        ["单据编号", "维度名称", "命中规则编码", "维度得分", "角色编码", "组织编码", "建议干预动作", "明细结论"],
        [
            [
                _text(row.get("document_no")),
                _text(row.get("dimension_name")),
                _text(row.get("rule_id")),
                _score_text(row.get("score")),
                _text(row.get("role_code")),
                _text(row.get("org_code")),
                _text(row.get("intervention_action")),
                _text(row.get("detail_conclusion")),
            ]
            for row in sorted(
                low_score_rows,
                key=lambda item: (
                    float(item.get("score") or 0.0),
                    _text(item.get("document_no")),
                    _text(item.get("dimension_name")),
                    _text(item.get("rule_id")),
                ),
            )
        ],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path


def _append_section(sheet, title: str, headers: list[str], rows: list[list[Any]]) -> None:
    row_index = sheet.max_row + 1 if sheet.max_row > 1 or sheet["A1"].value else 1
    sheet.cell(row=row_index, column=1, value=title)
    sheet.cell(row=row_index, column=1).font = Font(bold=True)
    row_index += 1
    for col_index, header in enumerate(headers, start=1):
        cell = sheet.cell(row=row_index, column=col_index, value=header)
        cell.font = Font(bold=True)
    for row in rows:
        row_index += 1
        for col_index, value in enumerate(row, start=1):
            sheet.cell(row=row_index, column=col_index, value=value)
    row_index += 2
    _autosize_columns(sheet)


def _append_table_sheet(workbook: Workbook, title: str, headers: list[str], rows: list[list[Any]]) -> None:
    sheet = workbook.create_sheet(title)
    for col_index, header in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=col_index, value=header)
        cell.font = Font(bold=True)
    for row_index, row in enumerate(rows, start=2):
        for col_index, value in enumerate(row, start=1):
            sheet.cell(row=row_index, column=col_index, value=value)
    sheet.freeze_panes = "A2"
    _autosize_columns(sheet)


def _autosize_columns(sheet) -> None:
    for column_cells in sheet.columns:
        column_letter = get_column_letter(column_cells[0].column)
        max_length = 0
        for cell in column_cells:
            text = "" if cell.value is None else str(cell.value)
            max_length = max(max_length, min(len(text), 80))
        sheet.column_dimensions[column_letter].width = max(max_length + 2, 12)
