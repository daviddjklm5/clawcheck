from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

HEADER_MAP = {
    "公司": "company_name",
    "公司ID": "company_id",
    "部门": "department_name",
    "部门长文本": "department_long_text",
    "部门ID": "department_id",
    "部门所属城市": "department_city",
    "人员编号": "employee_no",
    "姓名": "employee_name",
    "入职日期": "entry_date",
    "一级职能名称": "level1_function_name",
    "职位编码": "position_code",
    "职位名称": "position_name",
    "具体岗位(新)": "specific_post_name",
    "具体岗位（新）": "specific_post_name",
    "是否关键岗位": "critical_post_flag",
    "岗位族": "post_family",
    "职务": "job_title",
    "二级职能名称": "level2_function_name",
    "标准岗位编码": "standard_position_code",
}

HEADER_CANDIDATES = ["公司", "公司ID", "部门", "部门ID", "人员编号", "姓名", "入职日期"]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.hour == 0 and value.minute == 0 and value.second == 0:
            return value.date().isoformat()
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, int):
        return str(value)
    text = str(value).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _rows_from_sheet(sheet) -> list[list[str]]:
    return [[normalize_text(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]


def _load_xlsx_rows(path: Path) -> list[list[str]]:
    try:
        from openpyxl import load_workbook
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ModuleNotFoundError("Missing dependency: openpyxl. Run `pip install -r automation/requirements.txt`.") from exc

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.worksheets[0]
        if getattr(sheet, "max_row", 0) == 1 and getattr(sheet, "max_column", 0) == 1:
            try:
                sheet.reset_dimensions()
            except Exception:  # noqa: BLE001
                pass
        rows = _rows_from_sheet(sheet)
    finally:
        workbook.close()

    if len(rows) > 1:
        return rows

    workbook = load_workbook(path, read_only=False, data_only=True)
    try:
        sheet = workbook.worksheets[0]
        return _rows_from_sheet(sheet)
    finally:
        workbook.close()


def _load_xls_rows(path: Path) -> list[list[str]]:
    try:
        import xlrd
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise ModuleNotFoundError("Missing dependency: xlrd. Run `pip install -r automation/requirements.txt`.") from exc

    book = xlrd.open_workbook(path)
    sheet = next((book.sheet_by_index(idx) for idx in range(book.nsheets) if book.sheet_by_index(idx).nrows > 0), book.sheet_by_index(0))
    rows: list[list[str]] = []
    for row_idx in range(sheet.nrows):
        current: list[str] = []
        for col_idx in range(sheet.ncols):
            cell = sheet.cell(row_idx, col_idx)
            if cell.ctype == xlrd.XL_CELL_DATE:
                parts = xlrd.xldate_as_tuple(cell.value, book.datemode)
                if parts[3:] == (0, 0, 0):
                    value = date(parts[0], parts[1], parts[2])
                else:
                    value = datetime(*parts)
            else:
                value = cell.value
            current.append(normalize_text(value))
        rows.append(current)
    return rows


def _load_rows(path: Path) -> list[list[str]]:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return _load_xlsx_rows(path)
    if suffix == ".xls":
        return _load_xls_rows(path)
    raise ValueError(f"Unsupported roster file type: {path.suffix}")


def _extract_query_date(rows: list[list[str]]) -> date | None:
    for row in rows[:20]:
        for cell in row:
            if "查询日期" not in cell:
                continue
            matched = re.search(r"查询日期[:：]\s*(\d{4}-\d{2}-\d{2})", cell)
            if matched:
                return date.fromisoformat(matched.group(1))
    return None


def _find_header_row(rows: list[list[str]]) -> int:
    best_index = -1
    best_score = -1
    for idx, row in enumerate(rows[:50]):
        score = sum(1 for cell in row if normalize_text(cell) in HEADER_CANDIDATES)
        if score > best_score:
            best_score = score
            best_index = idx
        if score >= 5:
            return idx
    if best_index < 0 or best_score < 3:
        raise ValueError("Unable to identify roster header row from workbook")
    return best_index


def _normalize_headers(row: list[str]) -> list[str]:
    headers: list[str] = []
    counts: dict[str, int] = {}
    for idx, value in enumerate(row):
        header = normalize_text(value)
        if not header:
            header = f"未命名列{idx + 1}"
        counts[header] = counts.get(header, 0) + 1
        if counts[header] > 1:
            header = f"{header}_{counts[header]}"
        headers.append(header)
    return headers


def _is_empty_row(row: list[str]) -> bool:
    return all(not normalize_text(cell) for cell in row)


def _is_noise_row(row: list[str], headers: list[str]) -> bool:
    normalized = [normalize_text(cell) for cell in row]
    if _is_empty_row(normalized):
        return True
    if normalized[: len(headers)] == headers[: len(normalized)]:
        return True
    joined = " ".join(cell for cell in normalized if cell)
    if not joined:
        return True
    if any(key in joined for key in ["查询日期：", "导出时间", "在职人员花名册"]):
        return True
    if len([cell for cell in normalized if cell]) < 2:
        return True
    return False


def _parse_row(headers: list[str], row: list[str], excel_row_index: int) -> dict[str, Any] | None:
    normalized_row = [normalize_text(cell) for cell in row]
    record = {headers[idx]: normalized_row[idx] if idx < len(normalized_row) else "" for idx in range(len(headers))}
    standard: dict[str, Any] = {
        "row_no": excel_row_index,
        "raw_row": record,
    }
    for header, field_name in HEADER_MAP.items():
        if header in record:
            standard[field_name] = record.get(header, "")
    if not standard.get("employee_no"):
        return None
    return standard


def parse_roster_workbook(path: str | Path) -> dict[str, Any]:
    workbook_path = Path(path)
    rows = _load_rows(workbook_path)
    if not rows:
        raise ValueError(f"Workbook is empty: {workbook_path}")

    query_date = _extract_query_date(rows)
    header_row_index = _find_header_row(rows)
    headers = _normalize_headers(rows[header_row_index])

    records: list[dict[str, Any]] = []
    for offset, row in enumerate(rows[header_row_index + 1 :], start=header_row_index + 2):
        if _is_noise_row(row, headers):
            continue
        parsed = _parse_row(headers, row, offset)
        if parsed is None:
            continue
        records.append(parsed)

    if not records:
        raise ValueError(f"No roster data rows found after header parsing: {workbook_path}")

    return {
        "file_path": str(workbook_path),
        "file_name": workbook_path.name,
        "query_date": query_date,
        "headers": headers,
        "records": records,
        "row_count": len(records),
    }
