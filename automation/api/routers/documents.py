from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, HTTPException, Query

from automation.api.config_summary import _load_runtime_settings
from automation.api.collect_workbench import (
    get_collect_document_detail,
    get_collect_workbench,
    start_collect_task,
)
from automation.api.audit_workbench import start_audit_task
from automation.api.process_dashboard import (
    approve_process_document,
    get_process_analysis_dashboard,
    get_process_dashboard as get_process_dashboard_live,
    get_process_document_detail,
    get_process_workbench,
)
from automation.api.process_todo_sync import run_process_todo_sync_now

router = APIRouter(prefix="/documents", tags=["documents"])


class ProcessDocumentApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = "approve"
    approvalOpinion: str = ""
    dryRun: bool = False
    headed: bool | None = None


class ProcessTodoSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dryRun: bool = False
    headed: bool | None = None


class CollectRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentNo: str = ""
    limit: int = Field(default=100, ge=1)
    headed: bool | None = None
    dryRun: bool = False
    autoAudit: bool = True
    forceRecollect: bool = False


class ProcessAuditRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentNo: str = ""
    documentNos: list[str] = Field(default_factory=list)
    limit: int = Field(default=0, ge=0)
    dryRun: bool = False


@router.get("/collect-dashboard")
def get_collect_documents() -> dict[str, object]:
    return get_collect_workbench()


@router.get("/collect-workbench")
def get_collect_workbench_documents() -> dict[str, object]:
    return get_collect_workbench()


@router.get("/collect-workbench/{document_no}")
def get_collect_workbench_document(document_no: str) -> dict[str, object]:
    detail = get_collect_document_detail(document_no)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"未找到单据 {document_no} 的采集详情")
    return detail


@router.post("/collect-workbench/run")
def post_collect_workbench_run(payload: CollectRunRequest) -> dict[str, object]:
    try:
        _, settings = _load_runtime_settings()
        resolved_headed = settings.browser.headed if payload.headed is None else bool(payload.headed)
        return start_collect_task(
            document_no=payload.documentNo,
            limit=payload.limit,
            headed=resolved_headed,
            dry_run=payload.dryRun,
            auto_audit=payload.autoAudit,
            force_recollect=payload.forceRecollect,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/process-dashboard")
def get_process_documents() -> dict[str, object]:
    return get_process_dashboard_live()


@router.get("/process-workbench")
def get_process_workbench_documents() -> dict[str, object]:
    return get_process_workbench()


@router.get("/process-analysis")
def get_process_analysis() -> dict[str, object]:
    return get_process_analysis_dashboard()


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


@router.get("/process-workbench/{document_no}")
def get_process_workbench_document(
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


@router.post("/process-workbench/audit")
def post_process_workbench_audit(payload: ProcessAuditRunRequest) -> dict[str, object]:
    try:
        return start_audit_task(
            document_no=payload.documentNo,
            document_nos=payload.documentNos,
            limit=payload.limit,
            dry_run=payload.dryRun,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/process-dashboard/{document_no}/approval")
def post_process_document_approval(
    document_no: str,
    payload: ProcessDocumentApprovalRequest,
) -> dict[str, object]:
    try:
        _, settings = _load_runtime_settings()
        resolved_headed = settings.browser.headed if payload.headed is None else bool(payload.headed)
        return approve_process_document(
            document_no=document_no,
            action=payload.action,
            approval_opinion=payload.approvalOpinion,
            dry_run=payload.dryRun,
            headed=resolved_headed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/process-workbench/{document_no}/approval")
def post_process_workbench_document_approval(
    document_no: str,
    payload: ProcessDocumentApprovalRequest,
) -> dict[str, object]:
    try:
        _, settings = _load_runtime_settings()
        resolved_headed = settings.browser.headed if payload.headed is None else bool(payload.headed)
        return approve_process_document(
            document_no=document_no,
            action=payload.action,
            approval_opinion=payload.approvalOpinion,
            dry_run=payload.dryRun,
            headed=resolved_headed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/process-workbench/todo-sync")
def post_process_workbench_todo_sync(
    payload: ProcessTodoSyncRequest,
) -> dict[str, object]:
    try:
        _, settings = _load_runtime_settings()
        resolved_headed = settings.browser.headed if payload.headed is None else bool(payload.headed)
        return run_process_todo_sync_now(
            dry_run=payload.dryRun,
            headed=resolved_headed,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
