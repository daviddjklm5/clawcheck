from __future__ import annotations

from fastapi import APIRouter

from automation.api.config_summary import get_runtime_configuration_summary

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/runtime")
def get_runtime_settings() -> dict[str, object]:
    return get_runtime_configuration_summary()
