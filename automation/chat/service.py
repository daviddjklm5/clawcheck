from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import subprocess
import threading
import time
from typing import Any
from uuid import uuid4

from automation.api.config_summary import _load_runtime_settings
from automation.chat.codex_runner import (
    CodexExecutionResult,
    resolve_codex_cli_path,
    run_codex_exec,
)
from automation.chat.provider_config import ChatProviderConfig, load_chat_provider_config
from automation.db.postgres import PostgresChatStore
from automation.utils.config_loader import Settings


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _approx_token_count(text: str) -> int:
    return max(len(text) // 4, 1) if text else 0


def _new_id() -> str:
    return uuid4().hex


@dataclass
class _SessionRunState:
    run_id: str
    session_id: str
    user_message_id: str
    assistant_message_id: str
    cancel_event: threading.Event
    thread: threading.Thread
    status: str


class ChatService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._provider_config = load_chat_provider_config(settings)
        self._store = PostgresChatStore(settings.db)
        self._store.ensure_table()

        self._run_lock = threading.Lock()
        self._runs_by_session: dict[str, _SessionRunState] = {}

        self._event_condition = threading.Condition()
        self._events_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._next_event_seq_by_session: dict[str, int] = defaultdict(lambda: 1)

    def refresh_settings(self, settings: Settings) -> None:
        self._settings = settings
        self._provider_config = load_chat_provider_config(settings)
        self._store = PostgresChatStore(settings.db)
        self._store.ensure_table()

    def _publish_event(self, session_id: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        with self._event_condition:
            seq = self._next_event_seq_by_session[session_id]
            self._next_event_seq_by_session[session_id] = seq + 1
            event = {
                "seq": seq,
                "type": event_type,
                "at": _now_text(),
                "data": data,
            }
            events = self._events_by_session[session_id]
            events.append(event)
            if len(events) > 500:
                del events[: len(events) - 500]
            self._event_condition.notify_all()
        return event

    def _append_execution_log(
        self,
        *,
        session_id: str,
        message_id: str | None,
        event_type: str,
        event_summary: str,
        exit_code: int | None = None,
    ) -> None:
        try:
            self._store.append_execution_log(
                log_id=_new_id(),
                session_id=session_id,
                message_id=message_id,
                event_type=event_type,
                event_summary=event_summary,
                exit_code=exit_code,
            )
        except Exception:  # noqa: BLE001
            # Avoid blocking the conversation flow when audit log persistence fails.
            pass

    def create_session(self, *, title: str = "", workspace_dir: str = "") -> dict[str, Any]:
        session_id = _new_id()
        resolved_workspace_dir = workspace_dir.strip() or str(self._provider_config.workspace_dir)
        resolved_title = title.strip() or f"对话 {_now_text()}"
        session = self._store.create_session(
            session_id=session_id,
            title=resolved_title,
            workspace_dir=resolved_workspace_dir,
            model_provider=self._provider_config.provider,
            model_name=self._provider_config.model,
            status="idle",
        )
        self._publish_event(session_id, "session_created", {"sessionId": session_id})
        return session

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self._store.list_sessions(limit=limit, offset=offset)

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self._store.get_session(session_id)

    def get_session_detail(self, session_id: str) -> dict[str, Any] | None:
        session = self._store.get_session(session_id)
        if session is None:
            return None
        messages = self._store.list_messages(session_id=session_id, limit=500)
        running = self._is_session_running(session_id)
        return {
            "session": session,
            "messages": messages,
            "running": running,
        }

    def _is_session_running(self, session_id: str) -> bool:
        with self._run_lock:
            run = self._runs_by_session.get(session_id)
            return run is not None and run.status in {"queued", "running", "cancel_requested"}

    def submit_user_message(self, *, session_id: str, content: str) -> dict[str, Any]:
        normalized_content = content.strip()
        if not normalized_content:
            raise ValueError("Message content cannot be empty.")

        session = self._store.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")

        with self._run_lock:
            existing_run = self._runs_by_session.get(session_id)
            if existing_run is not None and existing_run.status in {"queued", "running", "cancel_requested"}:
                raise RuntimeError("A conversation run is already in progress for this session.")

        user_message = self._store.create_message(
            message_id=_new_id(),
            session_id=session_id,
            role="user",
            content=normalized_content,
            token_count=_approx_token_count(normalized_content),
        )
        assistant_message = self._store.create_message(
            message_id=_new_id(),
            session_id=session_id,
            role="assistant",
            content="",
            token_count=0,
        )
        self._store.update_session_status(session_id=session_id, status="running")
        self._publish_event(
            session_id,
            "message_created",
            {"message": user_message},
        )
        self._publish_event(
            session_id,
            "message_created",
            {"message": assistant_message},
        )

        cancel_event = threading.Event()
        run_id = _new_id()
        worker = threading.Thread(
            target=self._execute_turn,
            kwargs={
                "run_id": run_id,
                "session_id": session_id,
                "user_message_id": str(user_message["messageId"]),
                "assistant_message_id": str(assistant_message["messageId"]),
            },
            daemon=True,
        )
        run_state = _SessionRunState(
            run_id=run_id,
            session_id=session_id,
            user_message_id=str(user_message["messageId"]),
            assistant_message_id=str(assistant_message["messageId"]),
            cancel_event=cancel_event,
            thread=worker,
            status="queued",
        )
        with self._run_lock:
            self._runs_by_session[session_id] = run_state

        self._publish_event(
            session_id,
            "status",
            {"runId": run_id, "status": "queued"},
        )
        self._append_execution_log(
            session_id=session_id,
            message_id=str(assistant_message["messageId"]),
            event_type="status",
            event_summary="queued",
        )
        worker.start()

        return {
            "sessionId": session_id,
            "userMessage": user_message,
            "assistantMessage": assistant_message,
            "run": {
                "runId": run_id,
                "status": "queued",
            },
        }

    def _build_prompt(self, *, session_id: str, max_messages: int = 30) -> str:
        messages = self._store.list_messages(session_id=session_id, limit=max_messages)
        lines = [
            "You are an assistant for the clawcheck project.",
            "Use concise Chinese by default unless user asks for another language.",
            "When discussing project implementation, provide actionable steps and avoid exposing secrets.",
            "",
            "Conversation history:",
        ]
        for message in messages:
            role = str(message.get("role") or "").strip().lower() or "user"
            content = str(message.get("content") or "")
            if not content.strip() and role == "assistant":
                continue
            lines.append(f"[{role}]")
            lines.append(content)
            lines.append(f"[/{role}]")
        lines.append("")
        lines.append("Please answer the latest user question directly.")
        return "\n".join(lines)

    def _execute_turn(
        self,
        *,
        run_id: str,
        session_id: str,
        user_message_id: str,
        assistant_message_id: str,
    ) -> None:
        with self._run_lock:
            run_state = self._runs_by_session.get(session_id)
            if run_state is None:
                return
            run_state.status = "running"
            cancel_event = run_state.cancel_event

        self._publish_event(session_id, "status", {"runId": run_id, "status": "running"})
        self._append_execution_log(
            session_id=session_id,
            message_id=assistant_message_id,
            event_type="status",
            event_summary="running",
        )

        prompt = self._build_prompt(session_id=session_id)
        session = self._store.get_session(session_id)
        workspace_dir = (
            str(session.get("workspaceDir") or "").strip()
            if session is not None
            else str(self._provider_config.workspace_dir)
        )
        if not workspace_dir:
            workspace_dir = str(self._provider_config.workspace_dir)
        run_workspace = Path(workspace_dir).expanduser()
        if not run_workspace.is_absolute():
            run_workspace = self._provider_config.workspace_dir / run_workspace
        if not run_workspace.exists():
            run_workspace = self._provider_config.workspace_dir

        assistant_chunks: list[str] = []
        final_result: CodexExecutionResult | None = None
        run_error: str | None = None

        def _on_runner_event(event: dict[str, Any]) -> None:
            event_type = str(event.get("type") or "")
            if event_type == "token":
                delta = str(event.get("delta") or "")
                if delta:
                    assistant_chunks.append(delta)
                    self._publish_event(
                        session_id,
                        "token",
                        {
                            "runId": run_id,
                            "messageId": assistant_message_id,
                            "delta": delta,
                        },
                    )
            elif event_type == "status":
                status_value = str(event.get("status") or "")
                self._publish_event(
                    session_id,
                    "status",
                    {"runId": run_id, "status": status_value},
                )
                self._append_execution_log(
                    session_id=session_id,
                    message_id=assistant_message_id,
                    event_type="status",
                    event_summary=status_value,
                )
            elif event_type == "tool":
                summary = str(event.get("summary") or "")
                event_name = str(event.get("eventType") or "tool")
                self._publish_event(
                    session_id,
                    "tool",
                    {"runId": run_id, "eventType": event_name, "summary": summary},
                )
                self._append_execution_log(
                    session_id=session_id,
                    message_id=assistant_message_id,
                    event_type=event_name,
                    event_summary=summary,
                )
            elif event_type == "error":
                message = str(event.get("message") or "Unknown runner error")
                self._publish_event(
                    session_id,
                    "error",
                    {"runId": run_id, "message": message},
                )
                self._append_execution_log(
                    session_id=session_id,
                    message_id=assistant_message_id,
                    event_type="error",
                    event_summary=message,
                )
            elif event_type == "done":
                status_value = str(event.get("status") or "")
                exit_code = event.get("exitCode")
                self._publish_event(
                    session_id,
                    "status",
                    {"runId": run_id, "status": status_value},
                )
                self._append_execution_log(
                    session_id=session_id,
                    message_id=assistant_message_id,
                    event_type="done",
                    event_summary=status_value,
                    exit_code=int(exit_code) if isinstance(exit_code, int) else None,
                )

        try:
            final_result = run_codex_exec(
                config=self._provider_config,
                prompt=prompt,
                workspace_dir=run_workspace.resolve(),
                cancel_event=cancel_event,
                callback=_on_runner_event,
            )
        except Exception as exc:  # noqa: BLE001
            run_error = str(exc)

        if final_result is None:
            status = "failed"
            assistant_text = "".join(assistant_chunks).strip()
            if not assistant_text:
                assistant_text = run_error or "Conversation run failed."
            output_tail = run_error or ""
            token_count = _approx_token_count(assistant_text)
        else:
            status = final_result.status
            assistant_text = final_result.final_text.strip() or "".join(assistant_chunks).strip()
            if not assistant_text and final_result.status != "succeeded":
                assistant_text = f"Execution finished with status: {final_result.status}"
            output_tail = final_result.output_tail
            token_count = final_result.usage.get("output_tokens") or _approx_token_count(assistant_text)

        self._store.update_message_content(
            message_id=assistant_message_id,
            content=assistant_text,
            token_count=token_count,
        )
        normalized_session_status = "idle"
        if status == "canceled":
            normalized_session_status = "canceled"
        elif status in {"failed", "timeout"}:
            normalized_session_status = "failed"
        self._store.update_session_status(session_id=session_id, status=normalized_session_status)
        self._store.touch_session(session_id=session_id)
        self._append_execution_log(
            session_id=session_id,
            message_id=assistant_message_id,
            event_type="result",
            event_summary=output_tail or assistant_text[:4000],
            exit_code=final_result.exit_code if final_result is not None else 1,
        )
        self._publish_event(
            session_id,
            "done",
            {
                "runId": run_id,
                "sessionId": session_id,
                "userMessageId": user_message_id,
                "assistantMessageId": assistant_message_id,
                "status": status,
                "message": assistant_text,
                "tokenCount": token_count,
            },
        )

        with self._run_lock:
            current_run = self._runs_by_session.get(session_id)
            if current_run is not None and current_run.run_id == run_id:
                del self._runs_by_session[session_id]

    def cancel_session_run(self, session_id: str) -> dict[str, Any]:
        with self._run_lock:
            run_state = self._runs_by_session.get(session_id)
            if run_state is None:
                raise RuntimeError("No active run for this session.")
            run_state.status = "cancel_requested"
            run_state.cancel_event.set()
            run_id = run_state.run_id
        self._publish_event(
            session_id,
            "status",
            {"runId": run_id, "status": "cancel_requested"},
        )
        self._append_execution_log(
            session_id=session_id,
            message_id=run_state.assistant_message_id,
            event_type="status",
            event_summary="cancel_requested",
        )
        return {"sessionId": session_id, "runId": run_id, "status": "cancel_requested"}

    def stream_events(self, session_id: str, *, after_seq: int = 0):
        cursor = max(after_seq, 0)
        idle_started_at = time.monotonic()

        while True:
            with self._event_condition:
                session_events = self._events_by_session.get(session_id, [])
                pending_events = [event for event in session_events if int(event["seq"]) > cursor]
                if not pending_events:
                    is_running = self._is_session_running(session_id)
                    if not is_running and time.monotonic() - idle_started_at > 30:
                        return
                    self._event_condition.wait(timeout=3.0)
                    continue

            for event in pending_events:
                cursor = int(event["seq"])
                idle_started_at = time.monotonic()
                yield event

    def get_config_summary(self) -> dict[str, Any]:
        codex_path = resolve_codex_cli_path(self._provider_config)
        return {
            "provider": self._provider_config.provider,
            "baseUrl": self._provider_config.base_url,
            "model": self._provider_config.model,
            "timeoutSeconds": self._provider_config.timeout_seconds,
            "maxOutputTokens": self._provider_config.max_output_tokens,
            "apiKeyEnv": self._provider_config.api_key_env,
            "apiKeyConfigured": bool(self._provider_config.api_key),
            "codexCliExecutable": self._provider_config.codex_cli_executable,
            "codexCliResolvedPath": codex_path or "",
            "workspaceDir": str(self._provider_config.workspace_dir),
        }

    def get_health(self) -> dict[str, Any]:
        codex_path = resolve_codex_cli_path(self._provider_config)
        codex_version = ""
        codex_ok = False
        if codex_path:
            try:
                output = subprocess.run(
                    [codex_path, "--version"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                codex_version = (output.stdout or output.stderr or "").strip()
                codex_ok = output.returncode == 0
            except Exception:  # noqa: BLE001
                codex_ok = False
        key_ok = bool(self._provider_config.api_key)
        status = "ok" if (codex_ok and key_ok) else "degraded"
        return {
            "status": status,
            "codexCliAvailable": codex_ok,
            "codexCliPath": codex_path or "",
            "codexCliVersion": codex_version,
            "apiKeyEnv": self._provider_config.api_key_env,
            "apiKeyConfigured": key_ok,
            "provider": self._provider_config.provider,
            "model": self._provider_config.model,
        }


_SERVICE_LOCK = threading.Lock()
_SERVICE: ChatService | None = None


def get_chat_service() -> ChatService:
    global _SERVICE
    _, settings = _load_runtime_settings()
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = ChatService(settings)
        else:
            _SERVICE.refresh_settings(settings)
        return _SERVICE
