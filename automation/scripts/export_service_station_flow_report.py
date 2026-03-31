#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.api.report_center import export_service_station_flow_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export service station flow workbook")
    parser.add_argument("--start-date", required=True, help="Start effective date in YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End effective date in YYYY-MM-DD")
    parser.add_argument("--output", default="", help="Optional xlsx output path")
    return parser.parse_args()


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise SystemExit(f"Invalid date: {value}") from exc


def main() -> int:
    args = parse_args()
    result = export_service_station_flow_report(
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        save_as_path=args.output,
    )
    export_info = result.get("exportInfo") or {}
    print(f'file={export_info.get("filePath", "")}')
    print(f'rows_left={len(result.get("leftRows", []))}')
    print(f'rows_other_hr_out={len(result.get("otherHrOutRows", []))}')
    print(f'rows_target_flow={len(result.get("targetFlowRows", []))}')
    print(f'rows_other_hr_in={len(result.get("otherHrInRows", []))}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
