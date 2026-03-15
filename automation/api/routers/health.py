from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "clawcheck-ui-api",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
