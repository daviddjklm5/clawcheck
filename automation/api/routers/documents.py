from __future__ import annotations

from fastapi import APIRouter

from automation.api.mock_data import get_collect_dashboard, get_process_dashboard

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/collect-dashboard")
def get_collect_documents() -> dict[str, object]:
    return get_collect_dashboard()


@router.get("/process-dashboard")
def get_process_documents() -> dict[str, object]:
    return get_process_dashboard()
