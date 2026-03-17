from __future__ import annotations

from typing import Any


MANUAL_REVIEW_CONCLUSION = "人工干预"
MANUAL_REVIEW_DISPLAY = "加强审核"

HR_STAFF_TYPES = {"H1", "H2", "H3"}
HR_SUSPECTED_TYPES = {"HY"}

CROSS_ORG_RULE_IDS = {
    "TARGET_ORG_CROSS_UNIT_LOW",
    "TARGET_ORG_CROSS_UNIT_OTHER",
}

SUPPRESSED_WITH_CROSS_ORG_RULE_IDS = {
    "PERMISSION_B1_HR_STAFF",
}

FORCE_FULL_PERMISSION_LEVELS = {
    "S1类-限定",
    "S2类-限定",
    "A类-远程",
    "W类-取消",
}

PERMISSION_PRIORITY = {
    "S1类-限定": 0,
    "S2类-限定": 1,
    "A类-远程": 2,
    "W类-取消": 3,
    "B1类-涉薪": 4,
    "B2类-涉档案绩效": 5,
    "C类-常规": 6,
}

GENERIC_RULE_PRIORITY = {
    "approval": 30,
    "permission": 40,
    "applicant": 50,
    "fallback": 60,
}


def display_summary_conclusion(value: str | None) -> str:
    text = _text(value)
    if text == MANUAL_REVIEW_CONCLUSION:
        return MANUAL_REVIEW_DISPLAY
    return text or "-"


def build_low_score_feedback(
    *,
    summary_row: dict[str, Any],
    feedback_group_rows: list[dict[str, Any]] | None = None,
    role_rows: list[dict[str, Any]] | None = None,
    org_scope_rows: list[dict[str, Any]] | None = None,
    low_score_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_feedback_group_rows = list(feedback_group_rows or [])
    normalized_role_rows = list(role_rows or [])
    normalized_org_scope_rows = list(org_scope_rows or [])
    normalized_low_score_rows = list(low_score_rows or [])
    role_meta_by_code = _build_role_meta_map(normalized_role_rows)
    org_meta_by_code = _build_org_meta_map(normalized_org_scope_rows)

    applicant_org_unit_name = _text(summary_row.get("applicant_org_unit_name"))
    if normalized_feedback_group_rows:
        base_groups = _build_base_groups_from_feedback_rows(normalized_feedback_group_rows)
        role_meta_by_code = _merge_role_meta_map_from_base_groups(role_meta_by_code, base_groups)
        org_meta_by_code = _merge_org_meta_map_from_base_groups(org_meta_by_code, base_groups)
    else:
        base_groups = _build_base_groups(
            summary_row=summary_row,
            low_score_rows=normalized_low_score_rows,
            role_meta_by_code=role_meta_by_code,
            org_meta_by_code=org_meta_by_code,
        )

    display_groups: list[dict[str, Any]] = []
    consumed_keys: set[str] = set()

    cross_org_groups = _build_cross_org_groups(
        base_groups=base_groups,
        applicant_org_unit_name=applicant_org_unit_name,
    )
    display_groups.extend(cross_org_groups)
    for group in cross_org_groups:
        consumed_keys.update(group["base_group_keys"])

    permission_groups = _build_permission_groups(
        summary_row=summary_row,
        base_groups=base_groups,
        consumed_keys=consumed_keys,
        role_meta_by_code=role_meta_by_code,
    )
    if cross_org_groups:
        visible_permission_groups: list[dict[str, Any]] = []
        for group in permission_groups:
            if set(group["ruleIds"]).issubset(SUPPRESSED_WITH_CROSS_ORG_RULE_IDS):
                consumed_keys.update(group["base_group_keys"])
                continue
            visible_permission_groups.append(group)
        permission_groups = visible_permission_groups
    display_groups.extend(permission_groups)
    for group in permission_groups:
        consumed_keys.update(group["base_group_keys"])

    approval_groups = _build_approval_groups(
        base_groups=base_groups,
        consumed_keys=consumed_keys,
    )
    display_groups.extend(approval_groups)
    for group in approval_groups:
        consumed_keys.update(group["base_group_keys"])

    applicant_groups = _build_applicant_groups(
        summary_row=summary_row,
        base_groups=base_groups,
        consumed_keys=consumed_keys,
        has_permission_identity_group=any(group["category"] == "permission_identity" for group in permission_groups),
    )
    display_groups.extend(applicant_groups)
    for group in applicant_groups:
        consumed_keys.update(group["base_group_keys"])

    fallback_groups = _build_fallback_groups(
        base_groups=base_groups,
        consumed_keys=consumed_keys,
        org_meta_by_code=org_meta_by_code,
    )
    display_groups.extend(fallback_groups)

    display_groups.sort(
        key=lambda item: (
            int(item["priority"]),
            -int(item["rawDetailCount"]),
            item["title"],
            item["id"],
        )
    )

    unique_target_org_units = sorted(
        {
            _text(group.get("target_org_unit_name"))
            for group in base_groups
            if _text(group.get("target_org_unit_name"))
        }
    )
    unique_target_org_codes = sorted(
        {
            _text(item.get("org_code"))
            for group in base_groups
            for item in group.get("org_meta", [])
            if _text(item.get("org_code"))
        }
    )
    unique_role_codes = sorted(
        {
            _text(item.get("role_code"))
            for group in base_groups
            for item in group.get("role_meta", [])
            if _text(item.get("role_code"))
        }
    )
    raw_low_score_detail_count = sum(int(group.get("raw_detail_count") or 0) for group in base_groups)

    feedback_stats = [
        {
            "label": "风险类型数",
            "value": str(len(display_groups)),
            "hint": "按 104 方案聚合后的风险分组数。",
            "tone": "warning" if display_groups else "success",
        },
        {
            "label": "影响组织单位数",
            "value": str(len(unique_target_org_units)),
            "hint": "低分命中覆盖的目标组织单位去重数。",
            "tone": "info" if unique_target_org_units else "default",
        },
        {
            "label": "影响组织数",
            "value": str(len(unique_target_org_codes)),
            "hint": "低分命中覆盖的目标组织编码去重数。",
            "tone": "info" if unique_target_org_codes else "default",
        },
        {
            "label": "影响角色数",
            "value": str(len(unique_role_codes)),
            "hint": "低分命中覆盖的角色编码去重数。",
            "tone": "info" if unique_role_codes else "default",
        },
        {
            "label": "原始低分明细数",
            "value": str(raw_low_score_detail_count),
            "hint": "原始 `<= 1.0` 低分明细条数，保留用于审计与回放。",
            "tone": "warning" if raw_low_score_detail_count else "success",
        },
    ]

    return {
        "summaryConclusionLabel": display_summary_conclusion(summary_row.get("summary_conclusion")),
        "feedbackStats": feedback_stats,
        "feedbackGroups": display_groups,
        "feedbackLines": [group["summary"] for group in display_groups],
    }


def _build_base_groups_from_feedback_rows(feedback_group_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_groups: list[dict[str, Any]] = []
    for row in feedback_group_rows:
        role_meta = [
            {
                "role_code": _text(item.get("role_code")),
                "role_name": _text(item.get("role_name")),
                "permission_level": _text(item.get("permission_level")),
                "line_no": _sort_int(item.get("line_no")),
            }
            for item in list(row.get("role_meta") or [])
            if _text(item.get("role_code"))
        ]
        org_meta = [
            {
                "org_code": _text(item.get("org_code")),
                "organization_name": _text(item.get("organization_name")),
                "physical_level": _text(item.get("physical_level")),
            }
            for item in list(row.get("org_meta") or [])
            if _text(item.get("org_code"))
        ]
        base_groups.append(
            {
                "key": _text(row.get("group_key")) or f"group:{len(base_groups) + 1}",
                "dimension_name": _text(row.get("dimension_name")),
                "rule_id": _text(row.get("rule_id")),
                "score": _score_text(row.get("score")),
                "evidence_summary": _text(row.get("evidence_summary")),
                "intervention_action": _text(row.get("intervention_action")),
                "applicant_org_unit_name": _text(row.get("applicant_org_unit_name")),
                "target_org_unit_name": _text(row.get("target_org_unit_name")),
                "role_codes": {item["role_code"] for item in role_meta if item["role_code"]},
                "org_codes": {item["org_code"] for item in org_meta if item["org_code"]},
                "raw_detail_count": int(row.get("raw_detail_count") or 0),
                "role_meta": role_meta,
                "org_meta": org_meta,
            }
        )
    return base_groups


def _build_role_meta_map(role_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    role_meta_by_code: dict[str, dict[str, Any]] = {}
    for row in role_rows:
        role_code = _text(row.get("role_code"))
        if not role_code:
            continue
        role_meta_by_code[role_code] = {
            "role_code": role_code,
            "role_name": _text(row.get("role_name")),
            "permission_level": _text(row.get("permission_level")),
            "line_no": _sort_int(row.get("line_no")),
        }
    return role_meta_by_code


def _merge_role_meta_map_from_base_groups(
    role_meta_by_code: dict[str, dict[str, Any]],
    base_groups: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {
        role_code: dict(role_meta)
        for role_code, role_meta in role_meta_by_code.items()
    }
    for group in base_groups:
        for role_meta in list(group.get("role_meta") or []):
            role_code = _text(role_meta.get("role_code"))
            if not role_code:
                continue
            current = merged.setdefault(
                role_code,
                {
                    "role_code": role_code,
                    "role_name": "",
                    "permission_level": "",
                    "line_no": 999999,
                },
            )
            role_name = _text(role_meta.get("role_name"))
            permission_level = _text(role_meta.get("permission_level"))
            line_no = _sort_int(role_meta.get("line_no"))
            if not _text(current.get("role_name")) and role_name:
                current["role_name"] = role_name
            if not _text(current.get("permission_level")) and permission_level:
                current["permission_level"] = permission_level
            if line_no < _sort_int(current.get("line_no")):
                current["line_no"] = line_no
    return merged


def _build_org_meta_map(org_scope_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    org_meta_by_code: dict[str, dict[str, Any]] = {}
    for row in org_scope_rows:
        org_code = _text(row.get("org_code"))
        if not org_code:
            continue
        current = org_meta_by_code.setdefault(
            org_code,
            {
                "org_code": org_code,
                "organization_name": _text(row.get("organization_name")),
                "org_unit_name": _text(row.get("org_unit_name")),
                "physical_level": _text(row.get("physical_level")),
            },
        )
        if not current["organization_name"] and _text(row.get("organization_name")):
            current["organization_name"] = _text(row.get("organization_name"))
        if not current["org_unit_name"] and _text(row.get("org_unit_name")):
            current["org_unit_name"] = _text(row.get("org_unit_name"))
        if not current["physical_level"] and _text(row.get("physical_level")):
            current["physical_level"] = _text(row.get("physical_level"))
    return org_meta_by_code


def _merge_org_meta_map_from_base_groups(
    org_meta_by_code: dict[str, dict[str, Any]],
    base_groups: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {
        org_code: dict(org_meta)
        for org_code, org_meta in org_meta_by_code.items()
    }
    for group in base_groups:
        target_org_unit_name = _text(group.get("target_org_unit_name"))
        for org_meta in list(group.get("org_meta") or []):
            org_code = _text(org_meta.get("org_code"))
            if not org_code:
                continue
            current = merged.setdefault(
                org_code,
                {
                    "org_code": org_code,
                    "organization_name": "",
                    "org_unit_name": target_org_unit_name,
                    "physical_level": "",
                },
            )
            organization_name = _text(org_meta.get("organization_name"))
            physical_level = _text(org_meta.get("physical_level"))
            if not _text(current.get("organization_name")) and organization_name:
                current["organization_name"] = organization_name
            if not _text(current.get("org_unit_name")) and target_org_unit_name:
                current["org_unit_name"] = target_org_unit_name
            if not _text(current.get("physical_level")) and physical_level:
                current["physical_level"] = physical_level
    return merged


def _build_base_groups(
    *,
    summary_row: dict[str, Any],
    low_score_rows: list[dict[str, Any]],
    role_meta_by_code: dict[str, dict[str, Any]],
    org_meta_by_code: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    applicant_org_unit_name = _text(summary_row.get("applicant_org_unit_name"))
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in low_score_rows:
        role_code = _text(row.get("role_code"))
        org_code = _text(row.get("org_code"))
        org_meta = _org_meta_for_code(org_meta_by_code, org_code)
        key = (
            _text(row.get("dimension_name")),
            _text(row.get("rule_id")),
            _score_text(row.get("score")),
            _text(row.get("evidence_summary")) or _text(row.get("rule_summary")) or _text(row.get("detail_conclusion")),
            _text(row.get("intervention_action")),
            applicant_org_unit_name,
            _text(org_meta.get("org_unit_name")),
        )
        current = groups.setdefault(
            key,
            {
                "key": "|".join(value or "<NULL>" for value in key),
                "dimension_name": key[0],
                "rule_id": key[1],
                "score": key[2],
                "evidence_summary": key[3],
                "intervention_action": key[4],
                "applicant_org_unit_name": key[5],
                "target_org_unit_name": key[6],
                "role_codes": set(),
                "org_codes": set(),
                "raw_detail_count": 0,
                "role_meta": [],
                "org_meta": [],
            },
        )
        if role_code:
            current["role_codes"].add(role_code)
        if org_code:
            current["org_codes"].add(org_code)
        current["raw_detail_count"] += 1

    result: list[dict[str, Any]] = []
    for current in groups.values():
        current["role_meta"] = [
            role_meta_by_code.get(
                role_code,
                {
                    "role_code": role_code,
                    "role_name": role_code,
                    "permission_level": "",
                    "line_no": 999999,
                },
            )
            for role_code in sorted(current["role_codes"])
        ]
        current["org_meta"] = [
            _org_meta_for_code(org_meta_by_code, org_code)
            for org_code in sorted(current["org_codes"])
            if org_code in org_meta_by_code
        ]
        result.append(current)
    return result


def _build_cross_org_groups(
    *,
    base_groups: list[dict[str, Any]],
    applicant_org_unit_name: str,
) -> list[dict[str, Any]]:
    combined_groups: dict[tuple[str, ...], dict[str, Any]] = {}
    for group in base_groups:
        target_org_unit_name = _text(group.get("target_org_unit_name"))
        if group["rule_id"] not in CROSS_ORG_RULE_IDS:
            continue
        if not applicant_org_unit_name or not target_org_unit_name or applicant_org_unit_name == target_org_unit_name:
            continue
        combine_key = (
            group["dimension_name"],
            group["rule_id"],
            group["score"],
            group["evidence_summary"],
            group["intervention_action"],
            applicant_org_unit_name,
        )
        current = combined_groups.setdefault(
            combine_key,
            {
                "id": f"cross_org:{len(combined_groups) + 1}",
                "category": "cross_org",
                "title": "跨组织单位申请",
                "priority": 10,
                "rule_ids": [group["rule_id"]],
                "base_group_keys": set(),
                "unit_groups": [],
                "role_codes": set(),
                "org_codes": set(),
                "raw_detail_count": 0,
            },
        )
        current["base_group_keys"].add(group["key"])
        current["unit_groups"].append(group)
        current["role_codes"].update(group["role_codes"])
        current["org_codes"].update(group["org_codes"])
        current["raw_detail_count"] += group["raw_detail_count"]

    result: list[dict[str, Any]] = []
    for current in combined_groups.values():
        unit_groups = sorted(
            current["unit_groups"],
            key=lambda item: (-len(item["org_codes"]), item["target_org_unit_name"]),
        )
        segments = [
            f'涉“{item["target_org_unit_name"]}”：{_format_org_sample_text(item["org_meta"])}'
            for item in unit_groups
        ]
        role_sample_text = _format_role_sample_text(current["role_codes"], base_groups=current["unit_groups"])
        prefix = f'申请人属“{applicant_org_unit_name}”，' if applicant_org_unit_name else ""
        if len(unit_groups) > 1:
            summary_lines = [
                f"{prefix}本次申请组织范围跨 {len(unit_groups)} 个组织单位：",
                *[f"{segment}；" for segment in segments],
                f"共影响：{role_sample_text}；需明确跨组织单位申请理由。",
            ]
            summary = (
                f"{prefix}本次申请组织范围跨 {len(unit_groups)} 个组织单位："
                f"{'；'.join(segments)}；共影响：{role_sample_text}；需明确跨组织单位申请理由。"
            )
        else:
            summary_lines = [
                f"{prefix}申请组织范围涉“{unit_groups[0]['target_org_unit_name']}”："
                f"{_format_org_sample_text(unit_groups[0]['org_meta'])}；",
                f"共影响：{role_sample_text}；需明确跨组织单位申请理由。",
            ]
            summary = (
                f"{prefix}申请组织范围涉“{unit_groups[0]['target_org_unit_name']}”："
                f"{_format_org_sample_text(unit_groups[0]['org_meta'])}；共影响：{role_sample_text}；"
                "需明确跨组织单位申请理由。"
            )
        result.append(
            {
                "id": current["id"],
                "category": current["category"],
                "title": current["title"],
                "summary": summary,
                "summaryLines": summary_lines,
                "hint": "默认按组织单位聚合展示，原始明细保留在下方审计页签。",
                "ruleIds": current["rule_ids"],
                "rawDetailCount": current["raw_detail_count"],
                "affectedOrgUnitCount": len(unit_groups),
                "affectedOrgCount": len(current["org_codes"]),
                "affectedRoleCount": len(current["role_codes"]),
                "base_group_keys": sorted(current["base_group_keys"]),
                "priority": current["priority"],
            }
        )
    return result


def _build_permission_groups(
    *,
    summary_row: dict[str, Any],
    base_groups: list[dict[str, Any]],
    consumed_keys: set[str],
    role_meta_by_code: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    groups_by_rule_id = {
        group["rule_id"]: group
        for group in base_groups
        if group["dimension_name"] == "申请的权限" and group["key"] not in consumed_keys
    }

    result: list[dict[str, Any]] = []
    identity_label = _build_identity_label(summary_row)

    combined_non_hr_rule_ids = [
        rule_id
        for rule_id in ("PERMISSION_B1_NON_HR", "PERMISSION_B2_NON_HR")
        if rule_id in groups_by_rule_id
    ]
    if combined_non_hr_rule_ids:
        combined_groups = [groups_by_rule_id[rule_id] for rule_id in combined_non_hr_rule_ids]
        salary_roles = _collect_role_codes_by_permission_level(combined_groups, permission_level="B1类-涉薪")
        archive_roles = _collect_role_codes_by_permission_level(combined_groups, permission_level="B2类-涉档案绩效")
        parts: list[str] = []
        if salary_roles:
            parts.append(f'“{_format_role_name_list(salary_roles, role_meta_by_code)}”属涉薪权限')
        if archive_roles:
            parts.append(f'“{_format_role_name_list(archive_roles, role_meta_by_code)}”属涉档案绩效权限')
        tail = "非HR一般不申请，建议拒绝。" if "PERMISSION_B1_NON_HR" in combined_non_hr_rule_ids else "非HR一般不申请，需加强审核。"
        summary_parts = "，".join(part for part in parts if part)
        result.append(
            {
                "id": "permission_identity:non_hr",
                "category": "permission_identity",
                "title": "权限类型风险",
                "summary": f"{identity_label}，{summary_parts}，{tail}" if summary_parts else f"{identity_label}，{tail}",
                "hint": "使用 104 方案的权限类型极简模板展示。",
                "ruleIds": combined_non_hr_rule_ids,
                "rawDetailCount": sum(group["raw_detail_count"] for group in combined_groups),
                "affectedOrgUnitCount": 0,
                "affectedOrgCount": 0,
                "affectedRoleCount": len(set().union(*(group["role_codes"] for group in combined_groups))),
                "base_group_keys": [group["key"] for group in combined_groups],
                "priority": 20,
            }
        )

    if "PERMISSION_B1_HR_STAFF" in groups_by_rule_id:
        group = groups_by_rule_id["PERMISSION_B1_HR_STAFF"]
        salary_roles = _collect_role_codes_by_permission_level([group], permission_level="B1类-涉薪")
        result.append(
            {
                "id": "permission_identity:hr_b1",
                "category": "permission_identity",
                "title": "权限类型风险",
                "summary": (
                    f"{identity_label}，“{_format_role_name_list(salary_roles, role_meta_by_code) or '相关角色'}”属涉薪权限，"
                    "需结合申请依据加强审核。"
                ),
                "hint": "基础权限提醒在存在跨组织单位主风险时会自动下沉。",
                "ruleIds": ["PERMISSION_B1_HR_STAFF"],
                "rawDetailCount": group["raw_detail_count"],
                "affectedOrgUnitCount": 0,
                "affectedOrgCount": 0,
                "affectedRoleCount": len(group["role_codes"]),
                "base_group_keys": [group["key"]],
                "priority": 25,
            }
        )

    generic_rules = {
        "PERMISSION_CATALOG_MISSING": "“{roles}”未命中权限主数据，需管理员更新权限列表后复核。",
        "PERMISSION_W": "“{roles}”为已取消权限，建议拒绝。",
        "PERMISSION_A_REMOTE_NOT_ALLOWED": "申请人不属于远程交付中心，“{roles}”属 A 类远程权限，建议拒绝。",
        "PERMISSION_S1_NOT_ALLOWED": "申请人组织不在 S1 类权限允许范围内，“{roles}”属 S1 类限定权限，建议拒绝。",
        "PERMISSION_S1_ALLOWED": "“{roles}”属 S1 类限定权限，需人工复核后放行。",
        "PERMISSION_S2_DENIED": "申请人组织分类不满足 S2 类权限要求，“{roles}”属 S2 类限定权限，建议拒绝。",
        "PERMISSION_S2_ALLOWED": "“{roles}”属 S2 类限定权限，需人工复核后放行。",
    }
    for rule_id, template in generic_rules.items():
        group = groups_by_rule_id.get(rule_id)
        if group is None:
            continue
        role_text = _format_role_sample_text(group["role_codes"], base_groups=[group])
        result.append(
            {
                "id": f"permission:{rule_id}",
                "category": "permission",
                "title": "权限类型风险",
                "summary": template.format(roles=role_text),
                "hint": "当前分组按角色去重后列举权限样例。",
                "ruleIds": [rule_id],
                "rawDetailCount": group["raw_detail_count"],
                "affectedOrgUnitCount": 0,
                "affectedOrgCount": 0,
                "affectedRoleCount": len(group["role_codes"]),
                "base_group_keys": [group["key"]],
                "priority": GENERIC_RULE_PRIORITY["permission"],
            }
        )

    return result


def _build_approval_groups(
    *,
    base_groups: list[dict[str, Any]],
    consumed_keys: set[str],
) -> list[dict[str, Any]]:
    templates = {
        "APPROVAL_ALL_EQUAL_SUBMITTER": "当前审批链未形成有效复核，需补齐审批链后再处理。",
        "APPROVAL_LOCAL_WITHOUT_WARZONE_HISTORY": "审批链缺少战区人行部门审批，建议拒绝或补齐审批链。",
        "APPROVAL_LOCAL_WITHOUT_WARZONE_CURRENT_ROUND": "当前审批轮缺少战区人行部门审批，需补齐审批链后复核。",
    }
    result: list[dict[str, Any]] = []
    for group in base_groups:
        if group["key"] in consumed_keys or group["dimension_name"] != "审批人判断":
            continue
        summary = templates.get(group["rule_id"]) or _format_generic_summary(group)
        result.append(
            {
                "id": f"approval:{group['rule_id']}",
                "category": "approval",
                "title": "审批链风险",
                "summary": summary,
                "hint": "审批维度默认不展开技术规则编码，原始规则留在审计页签。",
                "ruleIds": [group["rule_id"]],
                "rawDetailCount": group["raw_detail_count"],
                "affectedOrgUnitCount": 0,
                "affectedOrgCount": 0,
                "affectedRoleCount": 0,
                "base_group_keys": [group["key"]],
                "priority": GENERIC_RULE_PRIORITY["approval"],
            }
        )
    return result


def _build_applicant_groups(
    *,
    summary_row: dict[str, Any],
    base_groups: list[dict[str, Any]],
    consumed_keys: set[str],
    has_permission_identity_group: bool,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    identity_label = _build_identity_label(summary_row)
    for group in base_groups:
        if group["key"] in consumed_keys:
            continue
        if group["rule_id"] == "APPLICANT_HR_TYPE_MISSING":
            result.append(
                {
                    "id": "applicant:missing_hr_type",
                    "category": "applicant",
                    "title": "申请人身份风险",
                    "summary": "申请人未匹配到人员属性，需补齐人员属性后复核。",
                    "hint": "人员属性异常不影响原始评估留痕。",
                    "ruleIds": [group["rule_id"]],
                    "rawDetailCount": group["raw_detail_count"],
                    "affectedOrgUnitCount": 0,
                    "affectedOrgCount": 0,
                    "affectedRoleCount": len(group["role_codes"]),
                    "base_group_keys": [group["key"]],
                    "priority": GENERIC_RULE_PRIORITY["applicant"],
                }
            )
            continue
        if group["rule_id"] == "APPLICANT_HR_NON_HR" and not has_permission_identity_group:
            result.append(
                {
                    "id": "applicant:non_hr",
                    "category": "applicant",
                    "title": "申请人身份风险",
                    "summary": f"{identity_label}，当前申请需结合权限与组织继续复核。",
                    "hint": "若权限类型风险已足够解释，申请人身份提醒会自动下沉。",
                    "ruleIds": [group["rule_id"]],
                    "rawDetailCount": group["raw_detail_count"],
                    "affectedOrgUnitCount": 0,
                    "affectedOrgCount": 0,
                    "affectedRoleCount": len(group["role_codes"]),
                    "base_group_keys": [group["key"]],
                    "priority": GENERIC_RULE_PRIORITY["applicant"],
                }
            )
    return result


def _build_fallback_groups(
    *,
    base_groups: list[dict[str, Any]],
    consumed_keys: set[str],
    org_meta_by_code: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for group in base_groups:
        if group["key"] in consumed_keys:
            continue
        summary = _format_generic_summary(group)
        role_count = len(group["role_codes"])
        org_count = len(group["org_codes"])
        org_unit_count = len(
            {
                _text(_org_meta_for_code(org_meta_by_code, org_code).get("org_unit_name"))
                for org_code in group["org_codes"]
                if _text(_org_meta_for_code(org_meta_by_code, org_code).get("org_unit_name"))
            }
        )
        if role_count:
            summary = f"{summary} 涉及角色：{_format_role_sample_text(group['role_codes'], base_groups=[group])}。"
        elif org_count:
            summary = f"{summary} 涉及组织：{_format_org_sample_text(group['org_meta'])}。"
        result.append(
            {
                "id": f"fallback:{group['rule_id']}:{len(result) + 1}",
                "category": "fallback",
                "title": group["dimension_name"] or "风险提醒",
                "summary": summary,
                "hint": "当前分组未命中 104 的专用极简模板，保留自然语言兜底展示。",
                "ruleIds": [group["rule_id"]],
                "rawDetailCount": group["raw_detail_count"],
                "affectedOrgUnitCount": org_unit_count,
                "affectedOrgCount": org_count,
                "affectedRoleCount": role_count,
                "base_group_keys": [group["key"]],
                "priority": GENERIC_RULE_PRIORITY["fallback"],
            }
        )
    return result


def _collect_role_codes_by_permission_level(
    groups: list[dict[str, Any]],
    *,
    permission_level: str,
) -> list[str]:
    role_codes: set[str] = set()
    for group in groups:
        for role_meta in group["role_meta"]:
            if _text(role_meta.get("permission_level")) == permission_level:
                role_codes.add(_text(role_meta.get("role_code")))
    return sorted(role_codes)


def _format_org_sample_text(org_meta_rows: list[dict[str, Any]]) -> str:
    unique_rows = {
        _text(item.get("org_code")): {
            "org_code": _text(item.get("org_code")),
            "organization_name": _text(item.get("organization_name")),
            "physical_level": _text(item.get("physical_level")),
        }
        for item in org_meta_rows
        if _text(item.get("org_code"))
    }
    sorted_rows = sorted(
        unique_rows.values(),
        key=lambda item: (_sort_int(item.get("physical_level")), item["org_code"]),
    )
    display_names = [
        item["organization_name"] or item["org_code"]
        for item in sorted_rows[:3]
    ]
    total_count = len(sorted_rows)
    if total_count <= 3:
        return f"{'、'.join(display_names)}，共 {total_count} 个组织"
    return f"{'、'.join(display_names)}等 {total_count} 个组织"


def _format_role_sample_text(role_codes: set[str], *, base_groups: list[dict[str, Any]]) -> str:
    role_meta_by_code: dict[str, dict[str, Any]] = {}
    for group in base_groups:
        for role_meta in group["role_meta"]:
            role_code = _text(role_meta.get("role_code"))
            if role_code:
                role_meta_by_code[role_code] = role_meta
    for role_code in role_codes:
        role_meta_by_code.setdefault(
            role_code,
            {
                "role_code": role_code,
                "role_name": role_code,
                "permission_level": "",
                "line_no": 999999,
            },
        )
    forced_roles = [
        role_meta_by_code[role_code]
        for role_code in role_codes
        if _text(role_meta_by_code.get(role_code, {}).get("permission_level")) in FORCE_FULL_PERMISSION_LEVELS
    ]
    normal_roles = [
        role_meta_by_code[role_code]
        for role_code in role_codes
        if role_code in role_meta_by_code
        and _text(role_meta_by_code[role_code].get("permission_level")) not in FORCE_FULL_PERMISSION_LEVELS
    ]
    forced_roles.sort(key=_role_sort_key)
    normal_roles.sort(key=_role_sort_key)
    included_roles = forced_roles + normal_roles[:3]
    labels = [_format_role_label(role_meta, role_meta_by_code) for role_meta in included_roles]
    if not labels:
        return "-"
    if len(role_codes) <= len(included_roles):
        return f"{'、'.join(labels)} {len(role_codes)} 个角色"
    return f"{'、'.join(labels)}等 {len(role_codes)} 个角色"


def _format_role_name_list(role_codes: list[str], role_meta_by_code: dict[str, dict[str, Any]]) -> str:
    items = [
        _format_role_label(role_meta_by_code[role_code], role_meta_by_code)
        for role_code in role_codes
        if role_code in role_meta_by_code
    ]
    return "、".join(items)


def _format_role_label(
    role_meta: dict[str, Any],
    role_meta_by_code: dict[str, dict[str, Any]],
) -> str:
    role_code = _text(role_meta.get("role_code"))
    role_name = _text(role_meta.get("role_name")) or role_code
    same_name_codes = sorted(
        [
            _text(candidate.get("role_code"))
            for candidate in role_meta_by_code.values()
            if _text(candidate.get("role_name")) == role_name
        ]
    )
    if role_name and len(set(same_name_codes)) > 1:
        return f"{role_name}（{role_code}）"
    return role_name or role_code


def _role_sort_key(role_meta: dict[str, Any]) -> tuple[int, int, str]:
    permission_level = _text(role_meta.get("permission_level"))
    return (
        PERMISSION_PRIORITY.get(permission_level, 99),
        _sort_int(role_meta.get("line_no")),
        _text(role_meta.get("role_code")),
    )


def _format_generic_summary(group: dict[str, Any]) -> str:
    evidence_summary = _text(group.get("evidence_summary"))
    intervention_action = _text(group.get("intervention_action"))
    if intervention_action:
        return f"{evidence_summary}，需{intervention_action}"
    return evidence_summary or "当前风险需人工复核"


def _build_identity_label(summary_row: dict[str, Any]) -> str:
    hr_type = _text(summary_row.get("applicant_hr_type"))
    position_name = _text(summary_row.get("applicant_position_name")) or _text(summary_row.get("position_name"))
    level1_function_name = _text(summary_row.get("level1_function_name"))
    if hr_type in HR_STAFF_TYPES:
        role_label = "申请人为HR岗位"
    elif hr_type in HR_SUSPECTED_TYPES:
        role_label = "申请人为疑似HR岗位"
    elif hr_type:
        role_label = "申请人为非HR岗位"
    else:
        role_label = "申请人身份待确认"
    parts: list[str] = []
    if position_name:
        parts.append(f"职位：{position_name}")
    if level1_function_name:
        parts.append(f"一级职能：{level1_function_name}")
    if not parts:
        return role_label
    return f"{role_label}（{'，'.join(parts)}）"


def _org_meta_for_code(org_meta_by_code: dict[str, dict[str, Any]], org_code: Any) -> dict[str, Any]:
    normalized_org_code = _text(org_code)
    return org_meta_by_code.get(normalized_org_code, {"org_code": normalized_org_code})


def _score_text(value: Any) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return _text(value)


def _sort_int(value: Any) -> int:
    text = _text(value)
    if not text:
        return 999999
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return 999999


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text
