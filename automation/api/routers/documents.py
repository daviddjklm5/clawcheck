from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from automation.api.mock_data import get_collect_dashboard
from automation.api.process_dashboard import (
    get_process_dashboard as get_process_dashboard_live,
    get_process_document_detail,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/collect-dashboard")
def get_collect_documents() -> dict[str, object]:
    return get_collect_dashboard()


@router.get("/process-dashboard")
def get_process_documents() -> dict[str, object]:
    return get_process_dashboard_live()


@router.get("/process-dashboard/{document_no}")
def get_process_document(
    document_no: str,
    assessment_batch_no: str = Query(default=""),
) -> dict[str, object]:
    detail = get_process_document_detail(
        document_no=document_no,
        assessment_batch_no=assessment_batch_no.strip() or None,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail=f"未找到单据 {document_no} 的评估详情")
    return detail
