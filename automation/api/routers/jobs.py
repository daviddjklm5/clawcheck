from __future__ import annotations

from fastapi import APIRouter

from automation.api.mock_data import get_master_data_dashboard

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/master-data")
def get_master_data() -> dict[str, object]:
    return get_master_data_dashboard()
