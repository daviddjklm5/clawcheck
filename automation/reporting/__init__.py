__all__ = [
    "build_approval_node_stats",
    "build_dimension_stats",
    "build_document_stats",
    "build_rule_stats",
    "render_audit_distribution_workbook",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from . import audit_distribution

    return getattr(audit_distribution, name)
