__all__ = [
    "AuditDistributionWorkbookData",
    "build_approval_node_stats",
    "build_audit_distribution_workbook_data",
    "build_document_feedback_rows",
    "build_dimension_stats",
    "build_document_stats",
    "build_person_attributes_enhanced_headers",
    "build_person_attributes_enhanced_query",
    "build_rule_stats",
    "export_audit_distribution_workbook",
    "load_audit_distribution_workbook_data",
    "render_person_attributes_enhanced_workbook",
    "render_audit_distribution_workbook",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    if name in {
        "AuditDistributionWorkbookData",
        "build_approval_node_stats",
        "build_audit_distribution_workbook_data",
        "build_document_feedback_rows",
        "build_dimension_stats",
        "build_document_stats",
        "build_rule_stats",
        "export_audit_distribution_workbook",
        "load_audit_distribution_workbook_data",
        "render_audit_distribution_workbook",
    }:
        from . import audit_distribution as module
    else:
        from . import person_attributes_enhanced as module

    return getattr(module, name)
