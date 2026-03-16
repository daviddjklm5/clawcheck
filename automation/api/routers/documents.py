from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from fastapi import APIRouter, HTTPException, Query

from automation.api.mock_data import get_collect_dashboard
from automation.api.process_dashboard import (
    approve_process_document,
    get_process_dashboard as get_process_dashboard_live,
    get_process_document_detail,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class ProcessDocumentApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "approve"
    approvalOpinion: str = ""
    dryRun: bool = False


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


@router.post("/process-dashboard/{document_no}/approval")
def post_process_document_approval(
    document_no: str,
    payload: ProcessDocumentApprovalRequest,
) -> dict[str, object]:
    try:
        return approve_process_document(
            document_no=document_no,
            action=payload.action,
            approval_opinion=payload.approvalOpinion,
            dry_run=payload.dryRun,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
