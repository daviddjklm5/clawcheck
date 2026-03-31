from __future__ import annotations

from datetime import date, datetime
import os
from pathlib import Path
import subprocess
from typing import Any

from automation.api.config_summary import REPO_ROOT, _load_runtime_settings
from automation.db.postgres import PERSON_ATTRIBUTES_HISTORY_COLUMNS, PostgresPersonAttributesHistoryStore
from automation.reporting import build_service_station_flow_report, render_service_station_flow_workbook

SERVICE_STATION_FLOW_REPORT_ID = "service-station-flow"
DEFAULT_REPORT_EXPORT_DIRNAME = "report_exports"

_SNAPSHOT_QUERY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("employee_no", PERSON_ATTRIBUTES_HISTORY_COLUMNS["employee_no"]),
    ("employee_name", PERSON_ATTRIBUTES_HISTORY_COLUMNS["employee_name"]),
    ("department_id", PERSON_ATTRIBUTES_HISTORY_COLUMNS["department_id"]),
    ("org_unit_name", PERSON_ATTRIBUTES_HISTORY_COLUMNS["org_unit_name"]),
    ("position_name", PERSON_ATTRIBUTES_HISTORY_COLUMNS["position_name"]),
    ("standard_position_name", PERSON_ATTRIBUTES_HISTORY_COLUMNS["standard_position_name"]),
    ("org_path_name", PERSON_ATTRIBUTES_HISTORY_COLUMNS["org_path_name"]),
    ("hr_type", PERSON_ATTRIBUTES_HISTORY_COLUMNS["hr_type"]),
    ("hr_subdomain", PERSON_ATTRIBUTES_HISTORY_COLUMNS["hr_subdomain"]),
    ("war_zone", PERSON_ATTRIBUTES_HISTORY_COLUMNS["war_zone"]),
)


def _resolve_runtime_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def _default_report_export_dir() -> Path:
    _, settings = _load_runtime_settings()
    return (_resolve_runtime_path(settings.runtime.logs_dir) / DEFAULT_REPORT_EXPORT_DIRNAME).resolve()


def _service_station_flow_filename(*, start_date: date, end_date: date, exported_at: datetime | None = None) -> str:
    timestamp = (exported_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"服务站人员流动表_{start_date.isoformat()}_to_{end_date.isoformat()}_{timestamp}.xlsx"


def resolve_service_station_flow_export_path(
    *,
    start_date: date,
    end_date: date,
    save_as_path: str = "",
) -> tuple[Path, Path]:
    default_dir = _default_report_export_dir()
    default_file_name = _service_station_flow_filename(start_date=start_date, end_date=end_date)
    normalized_save_as_path = save_as_path.strip()

    if not normalized_save_as_path:
        output_path = default_dir / default_file_name
    else:
        candidate = Path(normalized_save_as_path).expanduser()
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        if candidate.suffix:
            if candidate.suffix.lower() != ".xlsx":
                raise ValueError("另存为路径若填写到文件级，后缀必须为 .xlsx")
            output_path = candidate
        else:
            output_path = candidate / default_file_name

    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path.resolve(), default_dir


def _fetch_available_snapshot_dates(store: PostgresPersonAttributesHistoryStore) -> list[date]:
    with store.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT DISTINCT {store._quote_identifier(PERSON_ATTRIBUTES_HISTORY_COLUMNS["effective_date"])}
                FROM {store.table_name}
                ORDER BY {store._quote_identifier(PERSON_ATTRIBUTES_HISTORY_COLUMNS["effective_date"])}
                """
            )
            return [row[0] for row in cursor.fetchall() if row[0] is not None]


def get_report_center_catalog() -> dict[str, Any]:
    return {
        "modules": [
            {
                "id": "service-station-analysis",
                "label": "服务站分析",
                "description": "基于人员属性历史快照做服务站人事运营与招聘岗位的点对点流动分析。",
                "reports": [
                    {
                        "id": SERVICE_STATION_FLOW_REPORT_ID,
                        "label": "服务站人员流动表",
                        "path": "/report-center/service-station-flow",
                        "description": "填写开始日期和结束日期，对比两期历史快照并导出 Excel。",
                        "order": 1,
                    }
                ],
            }
        ]
    }


def get_service_station_flow_options() -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresPersonAttributesHistoryStore(settings.db)
    store.ensure_table()
    snapshot_dates = _fetch_available_snapshot_dates(store)
    date_texts = [item.isoformat() for item in snapshot_dates]

    default_start_date = ""
    default_end_date = ""
    can_run = len(snapshot_dates) >= 2
    if can_run:
        default_start_date = snapshot_dates[-2].isoformat()
        default_end_date = snapshot_dates[-1].isoformat()

    return {
        "availableSnapshotDates": date_texts,
        "defaultStartDate": default_start_date,
        "defaultEndDate": default_end_date,
        "defaultExportDirectory": str((_resolve_runtime_path(settings.runtime.logs_dir) / DEFAULT_REPORT_EXPORT_DIRNAME).resolve()),
        "canRun": can_run,
        "hint": "" if can_run else "可用历史快照不足，无法生成流动报表",
    }


def _validate_snapshot_dates(available_dates: list[date], *, start_date: date, end_date: date) -> None:
    if len(available_dates) < 2:
        raise ValueError("可用历史快照不足，无法生成流动报表")
    if start_date not in available_dates:
        raise ValueError(f"开始日期 {start_date.isoformat()} 不存在于人员属性查询历史")
    if end_date not in available_dates:
        raise ValueError(f"结束日期 {end_date.isoformat()} 不存在于人员属性查询历史")
    if start_date >= end_date:
        raise ValueError("开始日期必须早于结束日期")


def _fetch_snapshot_rows(
    store: PostgresPersonAttributesHistoryStore,
    *,
    effective_date: date,
    employee_nos: list[str] | None = None,
    target_only: bool = False,
) -> list[dict[str, Any]]:
    quoted_columns = ", ".join(
        f'{store._quote_identifier(column_name)} AS "{field_name}"'
        for field_name, column_name in _SNAPSHOT_QUERY_COLUMNS
    )
    filters = [f'{store._quote_identifier(PERSON_ATTRIBUTES_HISTORY_COLUMNS["effective_date"])} = %s']
    params: list[Any] = [effective_date]

    if target_only:
        filters.append(f'{store._quote_identifier(PERSON_ATTRIBUTES_HISTORY_COLUMNS["hr_subdomain"])} = ANY(%s)')
        params.append(["服务站-人事运营", "服务站-招聘"])

    if employee_nos is not None:
        if not employee_nos:
            return []
        filters.append(f'{store._quote_identifier(PERSON_ATTRIBUTES_HISTORY_COLUMNS["employee_no"])} = ANY(%s)')
        params.append(employee_nos)

    with store.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {quoted_columns}
                FROM {store.table_name}
                WHERE {' AND '.join(filters)}
                ORDER BY {store._quote_identifier(PERSON_ATTRIBUTES_HISTORY_COLUMNS["employee_no"])}
                """,
                params,
            )
            return [dict(zip((field_name for field_name, _ in _SNAPSHOT_QUERY_COLUMNS), row, strict=True)) for row in cursor.fetchall()]


def build_service_station_flow_report_result(
    *,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    _, settings = _load_runtime_settings()
    store = PostgresPersonAttributesHistoryStore(settings.db)
    store.ensure_table()
    snapshot_dates = _fetch_available_snapshot_dates(store)
    _validate_snapshot_dates(snapshot_dates, start_date=start_date, end_date=end_date)

    start_target_rows = _fetch_snapshot_rows(store, effective_date=start_date, target_only=True)
    end_target_rows = _fetch_snapshot_rows(store, effective_date=end_date, target_only=True)
    employee_nos = sorted(
        {
            row["employee_no"]
            for row in [*start_target_rows, *end_target_rows]
            if row.get("employee_no")
        }
    )

    start_rows = _fetch_snapshot_rows(store, effective_date=start_date, employee_nos=employee_nos)
    end_rows = _fetch_snapshot_rows(store, effective_date=end_date, employee_nos=employee_nos)
    return build_service_station_flow_report(
        start_date=start_date,
        end_date=end_date,
        start_rows=start_rows,
        end_rows=end_rows,
    )


def export_service_station_flow_report(
    *,
    start_date: date,
    end_date: date,
    save_as_path: str = "",
) -> dict[str, Any]:
    report = build_service_station_flow_report_result(start_date=start_date, end_date=end_date)
    output_path, _ = resolve_service_station_flow_export_path(
        start_date=start_date,
        end_date=end_date,
        save_as_path=save_as_path,
    )
    render_service_station_flow_workbook(report=report, output_path=output_path)

    export_info = {
        "fileName": output_path.name,
        "filePath": str(output_path),
        "fileSize": int(output_path.stat().st_size),
        "exportedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return {
        **report,
        "exportInfo": export_info,
    }


def open_report_output_folder(path_text: str) -> dict[str, str]:
    normalized_path = path_text.strip()
    if not normalized_path:
        raise ValueError("导出文件路径不能为空")

    candidate = Path(normalized_path).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    candidate = candidate.resolve()
    directory = candidate if candidate.is_dir() else candidate.parent
    if not directory.exists():
        raise ValueError(f"目录不存在：{directory}")

    startfile = getattr(os, "startfile", None)
    if callable(startfile):
        startfile(str(directory))
    else:  # pragma: no cover
        subprocess.Popen(["xdg-open", str(directory)])
    return {"directory": str(directory)}
