from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font

ORG_ENHANCEMENT_COLUMNS: tuple[str, ...] = ("所在城市", "组织单位", "所属战区")


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def build_person_attributes_enhanced_headers(person_columns: Sequence[str]) -> list[str]:
    if not person_columns:
        raise ValueError("person_columns must not be empty")
    return list(person_columns) + list(ORG_ENHANCEMENT_COLUMNS)


def build_person_attributes_enhanced_query(person_columns: Sequence[str]) -> str:
    headers = build_person_attributes_enhanced_headers(person_columns)
    select_columns = [f'p.{_quote_identifier(column)} AS {_quote_identifier(column)}' for column in headers[: len(person_columns)]]
    select_columns.extend(
        f'o.{_quote_identifier(column)} AS {_quote_identifier(column)}'
        for column in ORG_ENHANCEMENT_COLUMNS
    )
    select_sql = ",\n            ".join(select_columns)
    return f"""
        SELECT
            {select_sql}
        FROM {_quote_identifier("人员属性查询")} AS p
        LEFT JOIN {_quote_identifier("组织属性查询")} AS o
          ON BTRIM(o.{_quote_identifier("行政组织编码")}) = BTRIM(p.{_quote_identifier("部门ID")})
        ORDER BY p.{_quote_identifier("工号")}
        """


def _to_excel_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, bool, int, float)):
        return value
    return str(value)


def render_person_attributes_enhanced_workbook(
    *,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    output_path: Path,
    sheet_name: str = "人员属性查询增强报表",
) -> int:
    if not headers:
        raise ValueError("headers must not be empty")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title=sheet_name)

    header_font = Font(bold=True)
    header_row: list[WriteOnlyCell] = []
    for header in headers:
        cell = WriteOnlyCell(sheet, value=header)
        cell.font = header_font
        header_row.append(cell)
    sheet.append(header_row)

    row_count = 0
    for row in rows:
        sheet.append([_to_excel_value(value) for value in row])
        row_count += 1

    workbook.save(output_path)
    return row_count
