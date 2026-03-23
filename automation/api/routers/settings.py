from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from automation.api.config_summary import get_runtime_configuration_summary
from automation.utils.collect_schedule import update_collect_schedule

router = APIRouter(prefix="/settings", tags=["settings"])


class CollectScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    intervalMinutes: int = Field(default=0, ge=0)


@router.get("/runtime")
def get_runtime_settings() -> dict[str, object]:
    return get_runtime_configuration_summary()


@router.put("/runtime/collect-schedule")
def put_runtime_collect_schedule(payload: CollectScheduleUpdateRequest) -> dict[str, object]:
    try:
        update_collect_schedule(
            enabled=payload.enabled,
            interval_minutes=payload.intervalMinutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return get_runtime_configuration_summary()
