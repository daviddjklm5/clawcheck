from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


REMOTE_PERMISSION_LEVEL = "A类-远程"
DEPRECATED_PERMISSION_LEVEL = "W类-取消"


def _normalized_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def is_remote_permission_level(permission_level: str | None) -> bool:
    return _normalized_text(permission_level) == REMOTE_PERMISSION_LEVEL


def is_deprecated_permission_level(permission_level: str | None) -> bool:
    return _normalized_text(permission_level) == DEPRECATED_PERMISSION_LEVEL


def build_detail_role_facts(
    detail_row: Mapping[str, Any],
    catalog_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    role_code = _normalized_text(detail_row.get("role_code"))
    catalog_name = _normalized_text(catalog_row.get("role_name")) if catalog_row else ""
    detail_name = _normalized_text(detail_row.get("role_name"))
    permission_level = _normalized_text(catalog_row.get("permission_level")) if catalog_row else ""
    skip_org_scope_check = bool(catalog_row.get("skip_org_scope_check")) if catalog_row else False

    return {
        "code": role_code,
        "name": detail_name or catalog_name,
        "permission_level": permission_level,
        "skip_org_scope_check": skip_org_scope_check,
        "catalog_matched": bool(catalog_row),
    }


def build_detail_role_facts_list(
    detail_rows: Iterable[Mapping[str, Any]],
    catalog_by_role_code: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for detail_row in detail_rows:
        role_code = _normalized_text(detail_row.get("role_code"))
        facts.append(build_detail_role_facts(detail_row, catalog_by_role_code.get(role_code)))
    return facts
