from __future__ import annotations

from typing import Any

HR_SERVICE_CENTER_PATH_MARKER = "人力资源与行政服务中心_"
HR_SERVICE_DEPARTMENT_PATH_MARKER = "人力资源与行政服务部"

HR_SERVICE_PATH_PREFIX_TO_WAR_ZONE: dict[str, str] = {
    "上海": "上海战区",
    "东北": "东北战区",
    "京冀": "京冀战区",
    "佛山": "佛山战区",
    "南京": "南京战区",
    "厦门": "福建战区",
    "安徽": "安徽战区",
    "山东": "山东战区",
    "川云": "川云战区",
    "广州": "广州战区",
    "杭州": "杭州战区",
    "津晋": "津晋战区",
    "深圳": "深圳战区",
    "渝贵": "渝贵战区",
    "湘赣": "湘赣战区",
    "琼桂": "琼桂战区",
    "福州": "福建战区",
    "福建": "福建战区",
    "苏州": "苏州战区",
    "西北": "西北战区",
    "鄂豫": "鄂豫战区",
}


def _strip_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    normalized = str(value).strip()
    return normalized or None


def derive_war_zone_from_org_path(org_path_name: Any) -> str | None:
    normalized_path = _strip_text(org_path_name)
    if normalized_path is None:
        return None
    if HR_SERVICE_CENTER_PATH_MARKER not in normalized_path:
        return None
    if HR_SERVICE_DEPARTMENT_PATH_MARKER not in normalized_path:
        return None

    try:
        prefix = normalized_path.split(HR_SERVICE_CENTER_PATH_MARKER, 1)[1].split(
            HR_SERVICE_DEPARTMENT_PATH_MARKER,
            1,
        )[0]
    except IndexError:
        return None

    normalized_prefix = _strip_text(prefix)
    if normalized_prefix is None:
        return None
    return HR_SERVICE_PATH_PREFIX_TO_WAR_ZONE.get(normalized_prefix)


def resolve_person_war_zone(explicit_war_zone: Any, org_path_name: Any) -> str | None:
    normalized_war_zone = _strip_text(explicit_war_zone)
    if normalized_war_zone is not None:
        return normalized_war_zone
    return derive_war_zone_from_org_path(org_path_name)
