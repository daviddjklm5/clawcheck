from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


DIMENSION_LABELS = {
    "applicant_role": "申请人的角色判断",
    "applicant_process_category": "申请人所属的组织流程层级分类",
    "approval_chain": "审批人判断",
    "permission_level": "申请的权限",
    "target_organization": "申请的组织",
}


@dataclass
class RiskTrustPackage:
    version: str
    matrix: dict[str, Any]
    constants: dict[str, Any]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return data


def load_risk_trust_package(config_dir: Path) -> RiskTrustPackage:
    matrix_path = config_dir / "risk_trust_matrix.yaml"
    matrix = _read_yaml(matrix_path)

    constants_merged: dict[str, Any] = {}
    for import_name in matrix.get("imports", []):
        imported = _read_yaml(config_dir / str(import_name))
        constants_merged.update(imported.get("constants", {}))

    return RiskTrustPackage(
        version=str(matrix.get("version", "")).strip(),
        matrix=matrix,
        constants=constants_merged,
    )


class RiskTrustEvaluator:
    def __init__(self, package: RiskTrustPackage) -> None:
        self.package = package
        self.matrix = package.matrix
        self.constants = package.constants
        self.low_score_threshold = float(self.matrix.get("defaults", {}).get("low_score_threshold", 1.0))

    def evaluate_documents(
        self,
        bundles: list[dict[str, Any]],
        assessment_batch_no: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        summary_rows: list[dict[str, Any]] = []
        detail_rows: list[dict[str, Any]] = []
        for bundle in bundles:
            summary_row, current_detail_rows = self.evaluate_document(bundle, assessment_batch_no)
            summary_rows.append(summary_row)
            detail_rows.extend(current_detail_rows)
        return summary_rows, detail_rows

    def evaluate_documents_resilient(
        self,
        bundles: list[dict[str, Any]],
        assessment_batch_no: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        summary_rows: list[dict[str, Any]] = []
        detail_rows: list[dict[str, Any]] = []
        failed_documents: list[dict[str, Any]] = []
        for bundle in bundles:
            document_no = self._bundle_document_no(bundle)
            try:
                summary_row, current_detail_rows = self.evaluate_document(bundle, assessment_batch_no)
            except Exception as exc:  # noqa: BLE001
                failed_documents.append(
                    {
                        "document_no": document_no,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                )
                continue
            summary_rows.append(summary_row)
            detail_rows.extend(current_detail_rows)
        return summary_rows, detail_rows, failed_documents

    def evaluate_document(
        self,
        bundle: dict[str, Any],
        assessment_batch_no: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        facts = self._build_facts(bundle)
        detail_rows: list[dict[str, Any]] = []

        detail_rows.extend(
            self._evaluate_document_dimension(
                dimension_key="applicant_role",
                facts=facts,
                role_row=None,
                target_row=None,
                assessment_batch_no=assessment_batch_no,
            )
        )
        detail_rows.extend(
            self._evaluate_document_dimension(
                dimension_key="applicant_process_category",
                facts=facts,
                role_row=None,
                target_row=None,
                assessment_batch_no=assessment_batch_no,
            )
        )
        detail_rows.extend(
            self._evaluate_document_dimension(
                dimension_key="approval_chain",
                facts=facts,
                role_row=None,
                target_row=None,
                assessment_batch_no=assessment_batch_no,
            )
        )

        for role_row in facts["details"]:
            detail_rows.extend(
                self._evaluate_document_dimension(
                    dimension_key="permission_level",
                    facts=facts,
                    role_row=role_row,
                    target_row=None,
                    assessment_batch_no=assessment_batch_no,
                )
            )
            targets = role_row.get("targets") or [{"org_code": None, "org_auth_level": None, "org_unit_name": None}]
            for target_row in targets:
                detail_rows.extend(
                    self._evaluate_document_dimension(
                        dimension_key="target_organization",
                        facts=facts,
                        role_row=role_row,
                        target_row=target_row,
                        assessment_batch_no=assessment_batch_no,
                    )
                )

        if not detail_rows:
            raise ValueError(f"No risk-trust detail rows produced for document {facts['document_no']}")

        detail_rows.sort(
            key=lambda row: (
                float(row["score"]),
                row["dimension_name"],
                row.get("role_code") or "",
                row.get("org_code") or "",
            )
        )
        lowest_row = detail_rows[0]
        final_score = float(lowest_row["score"])
        summary_mapping = self._summary_mapping_by_score()
        conclusion_info = summary_mapping[self._score_key(final_score)]

        low_score_rows = [row for row in detail_rows if float(row["score"]) <= self.low_score_threshold]
        low_score_conclusions = [str(row["detail_conclusion"]) for row in low_score_rows]
        assessment_explain = f"最低分={self._format_score(final_score)}，总结论={conclusion_info['conclusion']}"

        summary_row = {
            "document_no": facts["document_no"],
            "assessment_batch_no": assessment_batch_no,
            "assessment_version": self.package.version,
            "applicant_hr_type": facts["applicant"]["hr_type"],
            "applicant_process_level_category": facts["applicant"]["process_level_category"],
            "final_score": final_score,
            "summary_conclusion": conclusion_info["conclusion"],
            "suggested_action": conclusion_info["action"],
            "lowest_hit_dimension": lowest_row["dimension_name"],
            "lowest_hit_role_code": lowest_row.get("role_code"),
            "lowest_hit_org_code": lowest_row.get("org_code"),
            "hit_manual_review": any(self._score_key(float(row["score"])) in {"0.5", "1.0"} for row in detail_rows),
            "has_low_score_details": bool(low_score_rows),
            "low_score_detail_count": len(low_score_rows),
            "low_score_detail_conclusion": "；".join(low_score_conclusions) if low_score_conclusions else None,
            "assessment_explain": assessment_explain,
            "input_snapshot": self._json_text(bundle),
        }
        return summary_row, detail_rows

    def _evaluate_document_dimension(
        self,
        dimension_key: str,
        facts: dict[str, Any],
        role_row: dict[str, Any] | None,
        target_row: dict[str, Any] | None,
        assessment_batch_no: str,
    ) -> list[dict[str, Any]]:
        dimension_config = self.matrix["dimensions"][dimension_key]
        context = self._build_rule_context(facts, role_row, target_row)
        candidates: list[dict[str, Any]] = []

        if "score_map_ref" in dimension_config and "rules" not in dimension_config:
            value = self._get_fact_path_value(facts, str(dimension_config.get("fact_path", "")))
            score = self._score_from_ref(
                ref_name=str(dimension_config["score_map_ref"]),
                value=value,
                default_score=dimension_config.get("default_score"),
            )
            candidates.append(
                self._build_detail_row(
                    document_no=str(facts["document_no"]),
                    dimension_key=dimension_key,
                    role_row=role_row,
                    target_row=target_row,
                    score=score,
                    rule_id=f"{dimension_key.upper()}_SCORE_MAP",
                    rule_summary=f"按 {dimension_key} 映射评分",
                    detail_text=f"按配置映射得分 {self._format_score(score)}",
                    intervention_action=None,
                    assessment_batch_no=assessment_batch_no,
                )
            )

        for rule in dimension_config.get("rules", []):
            if not self._rule_matches(rule.get("when", {}), context):
                continue
            score: float
            if "score" in rule:
                score = float(rule["score"])
            else:
                source_value = context.get(str(rule.get("score_source_fact", "")))
                score = self._score_from_ref(
                    ref_name=str(rule["score_map_ref"]),
                    value=source_value,
                    default_score=None,
                )
            candidates.append(
                self._build_detail_row(
                    document_no=str(facts["document_no"]),
                    dimension_key=dimension_key,
                    role_row=role_row,
                    target_row=target_row,
                    score=score,
                    rule_id=str(rule["id"]),
                    rule_summary=str(rule.get("summary", "")),
                    detail_text=str(rule.get("low_score_detail") or rule.get("summary") or ""),
                    intervention_action=rule.get("intervention_action"),
                    assessment_batch_no=assessment_batch_no,
                )
            )

        if not candidates:
            raise ValueError(
                f"No matched rule for dimension={dimension_key}, document={facts['document_no']}, "
                f"role={role_row.get('role_code') if role_row else None}, org={target_row.get('org_code') if target_row else None}"
            )

        min_score = min(float(item["score"]) for item in candidates)
        selected = [item for item in candidates if float(item["score"]) == min_score]
        selected.sort(key=lambda item: str(item["rule_id"]))
        return [selected[0]]

    def _build_rule_context(
        self,
        facts: dict[str, Any],
        role_row: dict[str, Any] | None,
        target_row: dict[str, Any] | None,
    ) -> dict[str, Any]:
        applicant = facts["applicant"]
        approval = facts["approval"]
        basic_info = self._as_dict(facts.get("basic_info"))
        document_flags = self._as_dict(facts.get("document_flags"))
        role_row = role_row or {}
        target_row = target_row or {}

        applicant_org_unit = self._normalized_text(applicant.get("org_unit_name"))
        target_org_unit = self._normalized_text(target_row.get("org_unit_name"))
        permission_target_company_name = self._normalized_text(basic_info.get("company_name"))
        target_org_company_name = self._normalized_text(target_row.get("org_company_name"))
        target_org_unit_name = self._normalized_text(target_row.get("org_unit_name"))

        return {
            "applicant_hr_type": self._normalized_text(applicant.get("hr_type")),
            "applicant_process_level_category": self._normalized_text(applicant.get("process_level_category")),
            "applicant_org_unit_name": applicant_org_unit,
            "permission_target_company_name": permission_target_company_name,
            "target_org_company_name": target_org_company_name,
            "permission_target_company_equal_target_org_company": (
                permission_target_company_name != "<NULL>"
                and target_org_company_name != "<NULL>"
                and permission_target_company_name == target_org_company_name
            ),
            "current_round_all_approvers_equal_submitter": bool(approval.get("current_round_all_approvers_equal_submitter")),
            "has_warzone_hr_in_history": bool(approval.get("has_warzone_hr_in_history")),
            "has_warzone_hr_in_current_round": bool(approval.get("has_warzone_hr_in_current_round")),
            "all_details_cancel_role_apply_type": bool(document_flags.get("all_details_cancel_role_apply_type")),
            "role_catalog_matched": bool(role_row.get("catalog_matched")),
            "apply_type": self._normalized_text(role_row.get("apply_type")),
            "permission_level": self._normalized_text(role_row.get("permission_level")),
            "role_skip_org_scope_check": bool(role_row.get("skip_org_scope_check")),
            "target_org_auth_level": self._normalized_text(target_row.get("org_auth_level")),
            "target_org_unit_name": target_org_unit_name,
            "target_org_code": self._normalized_text(target_row.get("org_code")),
            "applicant_org_unit_not_equal_target_org_unit": (
                applicant_org_unit != "<NULL>"
                and target_org_unit != "<NULL>"
                and applicant_org_unit != target_org_unit
            ),
        }

    def _build_facts(self, bundle: dict[str, Any]) -> dict[str, Any]:
        basic_info = self._as_dict(bundle.get("basic_info"))
        applicant_person = self._as_dict(bundle.get("applicant_person_attributes"))
        applicant_org = self._as_dict(bundle.get("applicant_org_attributes"))
        ignored_node_names = {
            self._normalized_text(node_name)
            for node_name in self._as_list(self.constants.get("ignored_approval_node_names"))
            if self._normalized_text(node_name) != "<NULL>"
        }
        approval_records = self._as_dict_list(bundle.get("approval_records"))
        applicant_employee_no = self._normalized_text(basic_info.get("employee_no"))
        last_submit_index = -1
        for idx, row in enumerate(approval_records):
            if self._normalized_text(row.get("approval_action")) == "提交":
                last_submit_index = idx
        current_round_records = approval_records[last_submit_index:] if last_submit_index >= 0 else approval_records

        def _non_ignored_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            filtered: list[dict[str, Any]] = []
            for row in rows:
                node_name = self._normalized_text(row.get("node_name"))
                if node_name in ignored_node_names:
                    continue
                filtered.append(row)
            return filtered

        def _valid_approval_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            filtered: list[dict[str, Any]] = []
            for row in _non_ignored_rows(rows):
                approver_employee_no = self._normalized_text(row.get("approver_employee_no"))
                if approver_employee_no == "<NULL>" or approver_employee_no == applicant_employee_no:
                    continue
                filtered.append(row)
            return filtered

        current_round_non_ignored = _non_ignored_rows(current_round_records)
        history_valid_rows = _valid_approval_rows(approval_records)
        current_round_valid_rows = _valid_approval_rows(current_round_records)

        current_round_all_approvers_equal_submitter = bool(current_round_non_ignored) and all(
            self._normalized_text(row.get("approver_employee_no")) == applicant_employee_no
            for row in current_round_non_ignored
            if self._normalized_text(row.get("approver_employee_no")) != "<NULL>"
        )

        def _is_warzone_hr(row: dict[str, Any]) -> bool:
            approver_org = self._as_dict(row.get("approver_org_attributes"))
            process_level_category = self._normalized_text(approver_org.get("process_level_category"))
            return process_level_category == "战区人行部门"

        details: list[dict[str, Any]] = []
        for detail_row in self._as_dict_list(bundle.get("permission_details")):
            targets = []
            for target in self._as_dict_list(detail_row.get("targets")):
                targets.append(
                    {
                        "org_code": target.get("org_code"),
                        "org_auth_level": target.get("org_auth_level"),
                        "org_unit_name": target.get("org_unit_name"),
                        "org_company_name": target.get("org_company_name"),
                    }
                )
            if not targets:
                targets.append({"org_code": None, "org_auth_level": None, "org_unit_name": None, "org_company_name": None})
            details.append(
                {
                    "line_no": detail_row.get("line_no"),
                    "role_code": detail_row.get("role_code"),
                    "role_name": detail_row.get("role_name"),
                    "apply_type": detail_row.get("apply_type"),
                    "permission_level": detail_row.get("permission_level"),
                    "skip_org_scope_check": bool(detail_row.get("skip_org_scope_check")),
                    "catalog_matched": bool(detail_row.get("catalog_matched")),
                    "targets": targets,
                }
            )

        cancel_role_apply_types = {
            self._normalized_text(value)
            for value in self._as_list(self.constants.get("cancel_role_apply_types"))
            if self._normalized_text(value) != "<NULL>"
        }
        all_details_cancel_role_apply_type = bool(details) and bool(cancel_role_apply_types) and all(
            self._normalized_text(row.get("apply_type")) in cancel_role_apply_types
            for row in details
        )

        return {
            "document_no": basic_info.get("document_no"),
            "basic_info": basic_info,
            "document_flags": {
                "all_details_cancel_role_apply_type": all_details_cancel_role_apply_type,
            },
            "applicant": {
                "employee_no": basic_info.get("employee_no"),
                "hr_type": applicant_person.get("hr_type"),
                "process_level_category": applicant_org.get("process_level_category"),
                "org_unit_name": applicant_org.get("org_unit_name"),
            },
            "approval": {
                "last_submit_time": current_round_records[0].get("approval_time") if current_round_records else None,
                "ignored_node_names": sorted(ignored_node_names),
                "excluded_node_names": [
                    self._normalized_text(row.get("node_name"))
                    for row in approval_records
                    if self._normalized_text(row.get("node_name")) in ignored_node_names
                ],
                "current_round_effective_approvers": [
                    self._normalized_text(row.get("approver_employee_no")) for row in current_round_valid_rows
                ],
                "has_warzone_hr_in_history": any(_is_warzone_hr(row) for row in history_valid_rows),
                "has_warzone_hr_in_current_round": any(_is_warzone_hr(row) for row in current_round_valid_rows),
                "current_round_all_approvers_equal_submitter": current_round_all_approvers_equal_submitter,
            },
            "details": details,
        }

    def _rule_matches(self, when: dict[str, Any], context: dict[str, Any]) -> bool:
        if not when:
            return False
        for key, expected in when.items():
            if key == "default":
                return bool(expected)
            if key.endswith("_not_in_ref"):
                actual = self._normalized_text(context[self._base_key(key, "_not_in_ref")])
                ref_values = {self._normalized_text(value) for value in self.constants.get(str(expected), [])}
                if actual in ref_values:
                    return False
                continue
            if key.endswith("_in_ref"):
                actual = self._normalized_text(context[self._base_key(key, "_in_ref")])
                ref_values = {self._normalized_text(value) for value in self.constants.get(str(expected), [])}
                if actual not in ref_values:
                    return False
                continue
            if key.endswith("_in"):
                actual = self._normalized_text(context[self._base_key(key, "_in")])
                expected_values = {self._normalized_text(value) for value in expected}
                if actual not in expected_values:
                    return False
                continue
            if key.endswith("_equals"):
                actual = self._normalized_text(context[self._base_key(key, "_equals")])
                if actual != self._normalized_text(expected):
                    return False
                continue
            if key.endswith("_is_null"):
                actual = self._normalized_text(context[self._base_key(key, "_is_null")])
                is_null = actual == "<NULL>"
                if is_null is not bool(expected):
                    return False
                continue
            if context.get(key) != expected:
                return False
        return True

    def _build_detail_row(
        self,
        document_no: str,
        dimension_key: str,
        role_row: dict[str, Any] | None,
        target_row: dict[str, Any] | None,
        score: float,
        rule_id: str,
        rule_summary: str,
        detail_text: str,
        intervention_action: Any,
        assessment_batch_no: str,
    ) -> dict[str, Any]:
        role_row = role_row or {}
        target_row = target_row or {}
        dimension_name = DIMENSION_LABELS[dimension_key]
        detail_conclusion = (
            f"维度={dimension_name}，角色编码={role_row.get('role_code') or '<NONE>'}，"
            f"组织编码={target_row.get('org_code') or '<NONE>'}，"
            f"命中规则={rule_id}，得分={self._format_score(score)}，"
            f"结论={detail_text or rule_summary}"
        )
        return {
            "document_no": document_no,
            "assessment_batch_no": assessment_batch_no,
            "assessment_version": self.package.version,
            "role_code": role_row.get("role_code"),
            "role_name": role_row.get("role_name"),
            "org_code": target_row.get("org_code"),
            "dimension_name": dimension_name,
            "rule_id": rule_id,
            "rule_summary": rule_summary,
            "score": score,
            "detail_conclusion": detail_conclusion,
            "is_low_score": score <= self.low_score_threshold,
            "intervention_action": self._null_if_blank(intervention_action),
            "evidence_summary": detail_text or rule_summary,
            "evidence_snapshot": None,
        }

    def _score_from_ref(self, ref_name: str, value: Any, default_score: Any) -> float:
        ref_map = self.constants.get(ref_name, {})
        normalized_value = self._normalized_text(value)
        if normalized_value in ref_map:
            return float(ref_map[normalized_value])
        if default_score is None:
            raise ValueError(f"Missing score mapping for ref={ref_name}, value={normalized_value}")
        return float(default_score)

    @staticmethod
    def _bundle_document_no(bundle: dict[str, Any]) -> str:
        basic_info = bundle.get("basic_info")
        if isinstance(basic_info, Mapping):
            value = basic_info.get("document_no")
            if value is not None:
                return str(value).strip()
        return ""

    @staticmethod
    def _base_key(condition_key: str, suffix: str) -> str:
        return condition_key[: -len(suffix)]

    def _summary_mapping_by_score(self) -> dict[str, dict[str, Any]]:
        mapping: dict[str, dict[str, Any]] = {}
        for item in self.matrix.get("summary_conclusions", []):
            mapping[self._score_key(float(item["score"]))] = {
                "conclusion": item["conclusion"],
                "action": item["action"],
            }
        return mapping

    @staticmethod
    def _format_score(score: float) -> str:
        return f"{score:.1f}".rstrip("0").rstrip(".") if "." in f"{score:.1f}" else f"{score:.1f}"

    @staticmethod
    def _score_key(score: float) -> str:
        return f"{score:.1f}"

    @staticmethod
    def _null_if_blank(value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @staticmethod
    def _normalized_text(value: Any) -> str:
        if value is None:
            return "<NULL>"
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or "<NULL>"
        return str(value).strip() or "<NULL>"

    @staticmethod
    def _get_fact_path_value(payload: dict[str, Any], fact_path: str) -> Any:
        current: Any = payload
        for part in fact_path.split("."):
            if not part:
                continue
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    @staticmethod
    def _json_text(payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {}

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return []

    def _as_dict_list(self, value: Any) -> list[dict[str, Any]]:
        return [row for row in self._as_list(value) if isinstance(row, dict)]
