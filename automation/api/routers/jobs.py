from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, HTTPException

from automation.api.config_summary import _load_runtime_settings
from automation.api.master_data_workbench import (
    get_master_data_workbench,
    start_master_data_task,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class MasterDataRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taskType: str
    headed: bool | None = None
    dryRun: bool = False
    inputFile: str = ""
    skipExport: bool = False
    skipImport: bool = False
    queryTimeoutSeconds: int = Field(default=0, ge=0)
    downloadTimeoutMinutes: int = Field(default=0, ge=0)
    scheme: str = ""
    employmentType: str = ""
    forceRefresh: bool = True


@router.get("/master-data")
def get_master_data() -> dict[str, object]:
    return get_master_data_workbench()


@router.post("/master-data/run")
def post_master_data_run(payload: MasterDataRunRequest) -> dict[str, object]:
    try:
        _, settings = _load_runtime_settings()
        resolved_headed = settings.browser.headed if payload.headed is None else bool(payload.headed)
        return start_master_data_task(
            task_type=payload.taskType,
            headed=resolved_headed,
            dry_run=payload.dryRun,
            input_file=payload.inputFile,
            skip_export=payload.skipExport,
            skip_import=payload.skipImport,
            query_timeout_seconds=payload.queryTimeoutSeconds,
            download_timeout_minutes=payload.downloadTimeoutMinutes,
            scheme=payload.scheme,
            employment_type=payload.employmentType,
            force_refresh=payload.forceRefresh,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
