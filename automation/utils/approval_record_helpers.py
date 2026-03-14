from __future__ import annotations

import re
from typing import Any


EMPTY_APPROVAL_RAW_TEXT = "属地人力资源部负责人 通过规则：全部通过"
APPROVER_WITH_EMPLOYEE_NO_RE = re.compile(r"^(?P<name>.+?)[(（](?P<employee_no>\d+)[)）]$")


def normalize_approval_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def is_empty_approval_raw_text(value: Any) -> bool:
    return normalize_approval_text(value) == EMPTY_APPROVAL_RAW_TEXT


def split_approver_name_and_employee_no(value: Any) -> tuple[str, str]:
    normalized = normalize_approval_text(value)
    match = APPROVER_WITH_EMPLOYEE_NO_RE.fullmatch(normalized)
    if match is None:
        return normalized, ""
    return normalize_approval_text(match.group("name")), match.group("employee_no").strip()


def normalize_approval_records(
    records: list[dict[str, Any]],
    approver_employee_no_by_name: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    normalized_records: list[dict[str, str]] = []
    approver_employee_no_by_name = approver_employee_no_by_name or {}

    for row in records:
        raw_text = normalize_approval_text(row.get("raw_text"))
        if is_empty_approval_raw_text(raw_text):
            continue

        approver_name, approver_employee_no_from_name = split_approver_name_and_employee_no(row.get("approver_name"))
        approver_employee_no = normalize_approval_text(row.get("approver_employee_no"))
        if not approver_employee_no:
            approver_employee_no = approver_employee_no_from_name
        if not approver_employee_no and approver_name:
            approver_employee_no = normalize_approval_text(approver_employee_no_by_name.get(approver_name))

        normalized_records.append(
            {
                "record_seq": str(len(normalized_records) + 1),
                "node_name": normalize_approval_text(row.get("node_name")),
                "approver_name": approver_name,
                "approver_employee_no": approver_employee_no,
                "approver_org_or_position": normalize_approval_text(row.get("approver_org_or_position")),
                "approval_action": normalize_approval_text(row.get("approval_action")),
                "approval_opinion": normalize_approval_text(row.get("approval_opinion")),
                "approval_time": normalize_approval_text(row.get("approval_time")),
                "raw_text": raw_text,
            }
        )

    return normalized_records


def derive_latest_approval_time(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return normalize_approval_text(records[-1].get("approval_time"))


def collect_unresolved_approver_names(records: list[dict[str, Any]]) -> set[str]:
    unresolved_names: set[str] = set()
    for row in records:
        approver_name = normalize_approval_text(row.get("approver_name"))
        approver_employee_no = normalize_approval_text(row.get("approver_employee_no"))
        if approver_name and not approver_employee_no:
            unresolved_names.add(approver_name)
    return unresolved_names
