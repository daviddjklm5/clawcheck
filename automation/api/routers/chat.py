from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from automation.chat.service import get_chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    workspaceDir: str = ""


class SubmitMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)


def _to_sse_frame(event: dict[str, object]) -> str:
    event_id = int(event.get("seq", 0))
    event_type = str(event.get("type", "message"))
    payload = json.dumps(event, ensure_ascii=False)
    return f"id: {event_id}\nevent: {event_type}\ndata: {payload}\n\n"


@router.post("/sessions")
def create_session(payload: CreateSessionRequest) -> dict[str, object]:
    service = get_chat_service()
    session = service.create_session(
        title=payload.title,
        workspace_dir=payload.workspaceDir,
    )
    return {"session": session}


@router.get("/sessions")
def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    service = get_chat_service()
    return {"sessions": service.list_sessions(limit=limit, offset=offset)}


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str) -> dict[str, object]:
    service = get_chat_service()
    detail = service.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return detail


@router.post("/sessions/{session_id}/messages")
def submit_message(session_id: str, payload: SubmitMessageRequest) -> dict[str, object]:
    service = get_chat_service()
    try:
        return service.submit_user_message(session_id=session_id, content=payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/cancel")
def cancel_run(session_id: str) -> dict[str, object]:
    service = get_chat_service()
    try:
        return service.cancel_session_run(session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/stream")
def stream_session_events(
    session_id: str,
    afterSeq: int = Query(default=0, ge=0),
) -> StreamingResponse:
    service = get_chat_service()
    detail = service.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    def _event_stream():
        for event in service.stream_events(session_id, after_seq=afterSeq):
            yield _to_sse_frame(event)

    return StreamingResponse(_event_stream(), media_type="text/event-stream")


@router.get("/config-summary")
def get_chat_config_summary() -> dict[str, object]:
    service = get_chat_service()
    return service.get_config_summary()


@router.get("/health")
def get_chat_health() -> dict[str, object]:
    service = get_chat_service()
    return service.get_health()

