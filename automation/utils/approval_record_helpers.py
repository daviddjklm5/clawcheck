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
