from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from automation.api.process_dashboard import approve_process_document, get_process_document_detail
from automation.api.config_summary import _load_runtime_settings
from automation.chat.approval_models import (
    ACTIVE_APPROVAL_PLAN_STATUSES,
    ApprovalCommand,
    ApprovalPlan,
    ApprovalPlanSnapshot,
    ApprovalRequest,
    TERMINAL_APPROVAL_PLAN_STATUSES,
)
from automation.chat.approval_plan_store import ApprovalPlanStore
from automation.chat.codex_runner import (
    CodexExecutionResult,
    resolve_codex_cli_path,
    run_codex_exec,
    run_router_exec,
)
from automation.chat.execution_adapter import ModelExecutionAdapter, build_execution_adapter
from automation.chat.execution_scheduler import ExecutionScheduler
from automation.chat.provider_config import ChatProviderConfig, load_chat_provider_config
from automation.chat.router_models import RouterDecision, router_decision_json_schema
from automation.chat.router_prompt import build_router_prompt
from automation.chat.run_state_store import RunStateStore
from automation.chat.skill_loader import LoadedSkillContext, SkillLoader
from automation.chat.tool_registry import (
    ToolExecutionResult,
    ToolRegistry,
    build_default_tool_registry,
)
from automation.db.postgres import PostgresChatStore
from automation.utils.config_loader import Settings


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _approx_token_count(text: str) -> int:
    return max(len(text) // 4, 1) if text else 0


def _new_id() -> str:
    return uuid4().hex


def _env_flag(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"0", "false", "no", "off"}:
        return False
    if normalized in {"1", "true", "yes", "on"}:
        return True
    return default


def _env_int(name: str, *, default: int, minimum: int = 1) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return max(default, minimum)
    try:
        parsed = int(raw_value.strip())
    except ValueError:
        return max(default, minimum)
    return max(parsed, minimum)


_APPROVAL_COMMAND_PATTERN = re.compile(
    r"^\s*(确认审批计划|验证审批计划|取消审批计划)\s+([A-Za-z0-9._:-]+)\s*$"
)


_APPROVAL_PLAN_ID_PATTERN = re.compile(r"(approval-plan-[A-Za-z0-9._:-]+)", re.IGNORECASE)
_APPROVAL_CONFIRM_KEYWORDS = (
    "确认审批计划",
    "确认命令",
    "确认",
    "提交",
    "confirm",
    "submit",
)
_APPROVAL_VERIFY_KEYWORDS = (
    "验证审批计划",
    "验证命令",
    "验证",
    "dry-run",
    "dry run",
    "dryrun",
    "verify",
)
_APPROVAL_CANCEL_KEYWORDS = (
    "取消审批计划",
    "取消命令",
    "取消",
    "cancel",
)


_FAST_PATH_DOCUMENT_NO_PATTERN = re.compile(r"\bRA-\d{8}-\d{8}\b", re.IGNORECASE)
_FAST_PATH_PENDING_HINTS = ("\u5f85\u5904\u7406", "\u5f85\u529e")
_FAST_PATH_DOCUMENT_HINTS = ("\u5355\u636e",)
_FAST_PATH_LIST_HINTS = (
    "\u5217\u51fa",
    "\u5217\u4e00\u4e0b",
    "\u6e05\u5355",
    "\u5217\u8868",
    "\u7f16\u53f7",
    "\u5168\u90e8",
    "\u660e\u7ec6",
    "\u90fd\u5217",
)
_FAST_PATH_COUNT_HINTS = (
    "\u591a\u5c11",
    "\u51e0\u6761",
    "\u51e0\u5f20",
    "\u6570\u91cf",
    "\u7edf\u8ba1",
    "\u603b\u6570",
    "count",
)
_FAST_PATH_STATUS_HINTS = (
    "\u72b6\u6001",
    "\u5f85\u529e",
    "\u5f85\u5904\u7406",
    "\u5df2\u5904\u7406",
    "\u8be6\u60c5",
    "\u60c5\u51b5",
    "status",
)
_FAST_PATH_APPROVAL_ACTION_HINTS = (
    "\u6279\u51c6",
    "\u9a73\u56de",
    "\u62d2\u7edd",
    "\u540c\u610f",
    "\u4e0d\u540c\u610f",
    "\u5ba1\u6279\u610f\u89c1",
    "\u786e\u8ba4\u5ba1\u6279\u8ba1\u5212",
    "\u9a8c\u8bc1\u5ba1\u6279\u8ba1\u5212",
    "\u53d6\u6d88\u5ba1\u6279\u8ba1\u5212",
    "approve",
    "approval",
    "reject",
)


@dataclass
class _SessionRunState:
    run_id: str
    session_id: str
    user_message_id: str
    assistant_message_id: str
    cancel_event: threading.Event
    thread: threading.Thread
    status: str
    backend_mode: str = "oneshot_exec"


@dataclass
class _TurnOutcome:
    status: str
    assistant_text: str
    output_tail: str
    token_count: int
    exit_code: int


class ChatService:
    TOOL_FIRST_CONFIDENCE_THRESHOLD = 0.75

    def __init__(
        self,
        settings: Settings,
        *,
        store: PostgresChatStore | None = None,
        provider_config: ChatProviderConfig | None = None,
        skill_loader: SkillLoader | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self._settings = settings
        self._provider_config = provider_config or load_chat_provider_config(settings)
        self._store = store or PostgresChatStore(settings.db)
        self._store.ensure_table()
        self._skill_loader = skill_loader or SkillLoader()
        self._tool_registry = tool_registry or build_default_tool_registry()
        self._router_enabled = _env_flag("CLAWCHECK_CHAT_ROUTER_ENABLED", default=True)
        self._fast_path_enabled = _env_flag("CLAWCHECK_CHAT_FAST_PATH_ENABLED", default=True)
        self._runtime_dir = Path(__file__).resolve().parents[1] / "runtime" / "chat"
        self._approval_enabled = _env_flag("CLAWCHECK_CHAT_APPROVAL_ENABLED", default=False)
        self._approval_dry_run_only = _env_flag("CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY", default=True)
        self._approval_plan_ttl_seconds = _env_int(
            "CLAWCHECK_CHAT_APPROVAL_PLAN_TTL_SECONDS",
            default=600,
            minimum=60,
        )
        self._approval_plan_store = ApprovalPlanStore(self._runtime_dir / "approval-plans")

        self._run_lock = threading.Lock()
        self._runs_by_session: dict[str, _SessionRunState] = {}

        self._event_condition = threading.Condition()
        self._events_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._next_event_seq_by_session: dict[str, int] = defaultdict(lambda: 1)
        self._execution_adapter: ModelExecutionAdapter = build_execution_adapter(
            self._provider_config.exec_mode
        )
        self._execution_scheduler = ExecutionScheduler(
            max_concurrent_runs=self._provider_config.global_max_concurrent_runs,
            queue_size=self._provider_config.run_queue_size,
        )
        self._run_state_store = RunStateStore(self._store)
        self._recover_interrupted_runs_on_boot()

    def refresh_settings(self, settings: Settings) -> None:
        self._settings = settings
        self._provider_config = load_chat_provider_config(settings)
        self._store = PostgresChatStore(settings.db)
        self._store.ensure_table()
        self._run_state_store = RunStateStore(self._store)
        self._router_enabled = _env_flag("CLAWCHECK_CHAT_ROUTER_ENABLED", default=True)
        self._fast_path_enabled = _env_flag("CLAWCHECK_CHAT_FAST_PATH_ENABLED", default=True)
        self._approval_enabled = _env_flag("CLAWCHECK_CHAT_APPROVAL_ENABLED", default=False)
        self._approval_dry_run_only = _env_flag("CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY", default=True)
        self._approval_plan_ttl_seconds = _env_int(
            "CLAWCHECK_CHAT_APPROVAL_PLAN_TTL_SECONDS",
            default=600,
            minimum=60,
        )
        self._execution_adapter = build_execution_adapter(self._provider_config.exec_mode)
        with self._run_lock:
            has_active_runs = bool(self._runs_by_session)
        if not has_active_runs:
            self._execution_scheduler = ExecutionScheduler(
                max_concurrent_runs=self._provider_config.global_max_concurrent_runs,
                queue_size=self._provider_config.run_queue_size,
            )

    def _recover_interrupted_runs_on_boot(self) -> None:
        interrupted_runs = self._run_state_store.mark_inflight_as_interrupted()
        for record in interrupted_runs:
            if not record.session_id or not record.run_id:
                continue
            self._publish_event(
                record.session_id,
                "event",
                {
                    "runId": record.run_id,
                    "eventType": "run_interrupted",
                    "summary": "上次运行在服务重启前中断，请按需重试。",
                },
            )

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

    def _publish_status(
        self,
        *,
        session_id: str,
        run_id: str,
        status: str,
        message_id: str | None,
    ) -> None:
        self._publish_event(session_id, "status", {"runId": run_id, "status": status})
        self._append_execution_log(
            session_id=session_id,
            message_id=message_id,
            event_type="status",
            event_summary=status,
        )

    def _publish_summary_event(
        self,
        *,
        session_id: str,
        run_id: str,
        event_type: str,
        summary: str,
        message_id: str | None,
    ) -> None:
        self._publish_event(
            session_id,
            "event",
            {"runId": run_id, "eventType": event_type, "summary": summary},
        )
        self._append_execution_log(
            session_id=session_id,
            message_id=message_id,
            event_type=event_type,
            event_summary=summary,
        )

    def _publish_tool_event(
        self,
        *,
        session_id: str,
        run_id: str,
        event_type: str,
        summary: str,
        message_id: str | None,
    ) -> None:
        self._publish_event(
            session_id,
            "tool",
            {"runId": run_id, "eventType": event_type, "summary": summary},
        )
        self._append_execution_log(
            session_id=session_id,
            message_id=message_id,
            event_type=event_type,
            event_summary=summary,
        )

    def _resolve_run_workspace(self, session: dict[str, Any] | None) -> Path:
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
        return run_workspace.resolve()

    def _active_backend_mode(self) -> str:
        mode = (self._provider_config.exec_mode or "").strip().lower()
        if mode in {"oneshot_exec", "persistent_subprocess", "app_server"}:
            return mode
        return "oneshot_exec"

    def _run_backend_mode(self, *, session_id: str) -> str:
        with self._run_lock:
            run_state = self._runs_by_session.get(session_id)
            if run_state is not None:
                normalized = (run_state.backend_mode or "").strip().lower()
                if normalized in {"oneshot_exec", "persistent_subprocess", "app_server"}:
                    return normalized
        return self._active_backend_mode()

    def _set_active_run_backend_mode(self, *, session_id: str, backend_mode: str) -> None:
        with self._run_lock:
            run_state = self._runs_by_session.get(session_id)
            if run_state is None:
                return
            run_state.backend_mode = backend_mode

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
        backend_mode = self._run_backend_mode(session_id=session_id)
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
            backend_mode=backend_mode,
        )
        with self._run_lock:
            self._runs_by_session[session_id] = run_state
        self._run_state_store.upsert(
            run_id=run_id,
            session_id=session_id,
            status="queued",
            backend_mode=backend_mode,
        )

        self._publish_status(
            session_id=session_id,
            run_id=run_id,
            status="queued",
            message_id=str(assistant_message["messageId"]),
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

    def _build_general_prompt(self, *, session_id: str, max_messages: int = 30) -> str:
        messages = self._store.list_messages(session_id=session_id, limit=max_messages)
        lines = [
            "You are an assistant for the clawcheck project.",
            "Use concise Chinese by default unless the user asks for another language.",
            "When discussing project implementation, provide actionable steps and do not expose secrets.",
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

    def _build_answer_prompt(
        self,
        *,
        session_id: str,
        latest_user_message: str,
        loaded_skill_contexts: list[LoadedSkillContext],
        tool_results: list[ToolExecutionResult],
    ) -> str:
        messages = self._store.list_messages(session_id=session_id, limit=12)
        lines = [
            "You are an assistant for the clawcheck project.",
            "Use concise Chinese by default unless the user asks for another language.",
            "When tool results are provided, they are the source of truth and take priority over generic repository knowledge.",
            "Do not invent fields, APIs, parameters, or business conclusions that are not supported by the supplied context.",
            "",
            "Recent conversation:",
        ]
        for message in messages[-8:]:
            role = str(message.get("role") or "").strip().lower() or "user"
            content = str(message.get("content") or "")
            if not content.strip() and role == "assistant":
                continue
            lines.append(f"[{role}] {content}")

        if loaded_skill_contexts:
            lines.append("")
            lines.append("Selected project skill context:")
            for context in loaded_skill_contexts:
                lines.append(f"## Skill: {context.skill_name}")
                if context.description:
                    lines.append(context.description)
                if context.body:
                    lines.append(context.body)
                for reference_name, reference_text in context.references.items():
                    lines.append(f"### Reference: {reference_name}")
                    lines.append(reference_text)

        if tool_results:
            lines.append("")
            lines.append("Official tool results:")
            serialized_results = [
                {
                    "name": tool_result.name,
                    "sourceOfTruth": tool_result.source_of_truth,
                    "arguments": tool_result.arguments,
                    "resultSummary": self._summarize_tool_result(tool_result),
                }
                for tool_result in tool_results
            ]
            lines.append(json.dumps(serialized_results, ensure_ascii=False, indent=2))

        lines.append("")
        lines.append(f"Latest user question: {latest_user_message.strip()}")
        lines.append("Answer the user directly. Mention the official source succinctly when using tool results.")
        return "\n".join(lines)

    def _summarize_tool_result(self, tool_result: ToolExecutionResult) -> Any:
        result = tool_result.result
        if tool_result.name == "get_process_workbench" and isinstance(result, dict):
            documents = result.get("documents") if isinstance(result.get("documents"), list) else []
            pending_document_nos = self._extract_pending_document_nos(result)
            return {
                "stats": result.get("stats", []),
                "documentCount": len(documents),
                "pendingDocumentCount": len(pending_document_nos),
                "pendingDocumentNos": pending_document_nos,
                "documents": documents[:10],
            }
        if tool_result.name == "get_process_document_detail" and isinstance(result, dict):
            roles = result.get("roles") if isinstance(result.get("roles"), list) else []
            approvals = result.get("approvals") if isinstance(result.get("approvals"), list) else []
            return {
                "documentNo": result.get("documentNo", ""),
                "overviewFields": result.get("overviewFields", []),
                "roleCount": len(roles),
                "approvalCount": len(approvals),
                "notes": result.get("notes", [])[:10] if isinstance(result.get("notes"), list) else [],
            }
        if tool_result.name == "get_collect_workbench" and isinstance(result, dict):
            documents = result.get("documents") if isinstance(result.get("documents"), list) else []
            recent_runs = result.get("recentRuns") if isinstance(result.get("recentRuns"), list) else []
            return {
                "stats": result.get("stats", []),
                "documentCount": len(documents),
                "documents": documents[:10],
                "currentTask": result.get("currentTask"),
                "recentRuns": recent_runs[:5],
            }
        return result

    def _build_runner_callback(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        assistant_chunks: list[str],
    ):
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
                self._publish_status(
                    session_id=session_id,
                    run_id=run_id,
                    status=status_value,
                    message_id=assistant_message_id,
                )
            elif event_type == "tool":
                summary = str(event.get("summary") or "")
                event_name = str(event.get("eventType") or "tool")
                self._publish_tool_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type=event_name,
                    summary=summary,
                    message_id=assistant_message_id,
                )
            elif event_type == "error":
                message = str(event.get("message") or "Unknown runner error")
                self._publish_event(session_id, "error", {"runId": run_id, "message": message})
                self._append_execution_log(
                    session_id=session_id,
                    message_id=assistant_message_id,
                    event_type="error",
                    event_summary=message,
                )
            elif event_type == "done":
                status_value = str(event.get("status") or "")
                exit_code = event.get("exitCode")
                self._publish_status(
                    session_id=session_id,
                    run_id=run_id,
                    status=status_value,
                    message_id=assistant_message_id,
                )
                self._append_execution_log(
                    session_id=session_id,
                    message_id=assistant_message_id,
                    event_type="done",
                    event_summary=status_value,
                    exit_code=int(exit_code) if isinstance(exit_code, int) else None,
                )
            elif event_type == "event":
                event_name = str(event.get("eventType") or "runner_event")
                summary = str(event.get("summary") or "")
                self._publish_summary_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type=event_name,
                    summary=summary,
                    message_id=assistant_message_id,
                )

        return _on_runner_event

    def _run_model_prompt(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        prompt: str,
        workspace_dir: Path,
        cancel_event: threading.Event,
    ) -> _TurnOutcome:
        assistant_chunks: list[str] = []
        final_result: CodexExecutionResult | None = None
        run_error: str | None = None
        backend_mode = self._run_backend_mode(session_id=session_id)
        callback = self._build_runner_callback(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            assistant_chunks=assistant_chunks,
        )

        try:
            if backend_mode == "oneshot_exec":
                final_result = run_codex_exec(
                    config=self._provider_config,
                    prompt=prompt,
                    workspace_dir=workspace_dir,
                    cancel_event=cancel_event,
                    callback=callback,
                )
            else:
                final_result = self._execution_adapter.run_answer(
                    config=self._provider_config,
                    prompt=prompt,
                    workspace_dir=workspace_dir,
                    cancel_event=cancel_event,
                    callback=callback,
                )
        except Exception as exc:  # noqa: BLE001
            run_error = str(exc)
            if (
                self._provider_config.exec_auto_fallback
                and backend_mode != "oneshot_exec"
                and not cancel_event.is_set()
            ):
                self._publish_summary_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type="backend_auto_fallback",
                    summary=f"执行后端 {backend_mode} 失败，自动降级到 oneshot_exec。原因：{run_error}",
                    message_id=assistant_message_id,
                )
                self._set_active_run_backend_mode(session_id=session_id, backend_mode="oneshot_exec")
                try:
                    final_result = run_codex_exec(
                        config=self._provider_config,
                        prompt=prompt,
                        workspace_dir=workspace_dir,
                        cancel_event=cancel_event,
                        callback=callback,
                    )
                    run_error = None
                except Exception as fallback_exc:  # noqa: BLE001
                    run_error = f"{run_error}; fallback failed: {fallback_exc}"

        if final_result is None:
            assistant_text = "".join(assistant_chunks).strip() or run_error or "Conversation run failed."
            return _TurnOutcome(
                status="failed",
                assistant_text=assistant_text,
                output_tail=run_error or assistant_text[:4000],
                token_count=_approx_token_count(assistant_text),
                exit_code=1,
            )

        assistant_text = final_result.final_text.strip() or "".join(assistant_chunks).strip()
        if not assistant_text and final_result.status != "succeeded":
            assistant_text = f"Execution finished with status: {final_result.status}"
        token_count = final_result.usage.get("output_tokens") or _approx_token_count(assistant_text)
        return _TurnOutcome(
            status=final_result.status,
            assistant_text=assistant_text,
            output_tail=final_result.output_tail,
            token_count=token_count,
            exit_code=final_result.exit_code,
        )

    def _publish_static_reply(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        status: str,
        assistant_text: str,
    ) -> _TurnOutcome:
        self._publish_event(
            session_id,
            "token",
            {
                "runId": run_id,
                "messageId": assistant_message_id,
                "delta": assistant_text,
            },
        )
        self._publish_status(
            session_id=session_id,
            run_id=run_id,
            status=status,
            message_id=assistant_message_id,
        )
        return _TurnOutcome(
            status=status,
            assistant_text=assistant_text,
            output_tail=assistant_text[:4000],
            token_count=_approx_token_count(assistant_text),
            exit_code=0,
        )

    def _find_stat_value(self, payload: dict[str, Any], label: str) -> str | None:
        stats = payload.get("stats")
        if not isinstance(stats, list):
            return None
        for row in stats:
            if not isinstance(row, dict):
                continue
            if str(row.get("label") or "").strip() == label:
                value = row.get("value")
                return str(value) if value is not None else None
        return None

    def _find_overview_value(self, payload: dict[str, Any], label: str) -> str | None:
        fields = payload.get("overviewFields")
        if not isinstance(fields, list):
            return None
        for row in fields:
            if not isinstance(row, dict):
                continue
            if str(row.get("label") or "").strip() == label:
                value = row.get("value")
                return str(value) if value is not None else None
        return None

    def _extract_pending_document_nos(self, payload: dict[str, Any]) -> list[str]:
        documents = payload.get("documents")
        if not isinstance(documents, list):
            return []
        pending_document_nos: list[str] = []
        for row in documents:
            if not isinstance(row, dict):
                continue
            todo_status = str(row.get("todoProcessStatus") or "").strip()
            if todo_status != "待处理":
                continue
            document_no = str(row.get("documentNo") or "").strip()
            if document_no:
                pending_document_nos.append(document_no)
        return pending_document_nos

    @staticmethod
    def _normalize_fast_path_text(text: str) -> str:
        return "".join(str(text or "").lower().split())

    @staticmethod
    def _contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _match_fast_path_plan(
        self,
        latest_user_message: str,
    ) -> tuple[str, str, dict[str, Any], str] | None:
        normalized_text = self._normalize_fast_path_text(latest_user_message)
        if not normalized_text:
            return None

        has_pending_scope = (
            self._contains_any_keyword(normalized_text, _FAST_PATH_PENDING_HINTS)
            and self._contains_any_keyword(normalized_text, _FAST_PATH_DOCUMENT_HINTS)
        )
        if has_pending_scope and self._contains_any_keyword(normalized_text, _FAST_PATH_LIST_HINTS):
            return (
                "pending_document_list",
                "get_process_workbench",
                {},
                "命中待处理单据编号清单快路径。",
            )
        if has_pending_scope and self._contains_any_keyword(normalized_text, _FAST_PATH_COUNT_HINTS):
            return (
                "pending_document_count",
                "get_process_workbench",
                {},
                "命中待处理单据数量快路径。",
            )

        document_match = _FAST_PATH_DOCUMENT_NO_PATTERN.search(latest_user_message)
        if document_match is None:
            return None
        if self._contains_any_keyword(normalized_text, _FAST_PATH_APPROVAL_ACTION_HINTS):
            return None
        if not self._contains_any_keyword(normalized_text, _FAST_PATH_STATUS_HINTS):
            return None
        document_no = document_match.group(0).upper()
        return (
            "document_status_query",
            "get_process_document_detail",
            {"documentNo": document_no},
            f"命中单据状态查询快路径：{document_no}。",
        )

    def try_handle_fast_path_query(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        latest_user_message: str,
    ) -> _TurnOutcome | None:
        if not self._fast_path_enabled:
            return None

        matched = self._match_fast_path_plan(latest_user_message)
        if matched is None:
            return None
        intent_name, tool_name, tool_arguments, intent_summary = matched
        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="fast_path_hit",
            summary=intent_summary,
            message_id=assistant_message_id,
        )
        self._publish_status(
            session_id=session_id,
            run_id=run_id,
            status="running_tool",
            message_id=assistant_message_id,
        )
        self._publish_tool_event(
            session_id=session_id,
            run_id=run_id,
            event_type="tool_call",
            summary=(
                f"快路径直接调用正式工具 {tool_name}，参数："
                f"{json.dumps(tool_arguments, ensure_ascii=False)}"
            ),
            message_id=assistant_message_id,
        )
        try:
            tool_result = self._tool_registry.execute(tool_name, tool_arguments)
            if tool_result.result is None:
                raise LookupError(f"正式工具 {tool_name} 未返回结果。")
        except Exception as exc:  # noqa: BLE001
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="fast_path_fallback",
                summary=f"快路径执行失败，回退到常规路由链路。原因：{exc}",
                message_id=assistant_message_id,
            )
            return None

        self._publish_tool_event(
            session_id=session_id,
            run_id=run_id,
            event_type="tool_result",
            summary=f"正式工具 {tool_result.name} 调用成功，来源：{tool_result.source_of_truth}",
            message_id=assistant_message_id,
        )
        if intent_name == "pending_document_list":
            assistant_text = self._build_pending_document_list_reply(tool_result)
        else:
            assistant_text = self.build_templated_reply(tool_results=[tool_result])

        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="templated_answer",
            summary="快路径已完成模板化直答。",
            message_id=assistant_message_id,
        )
        return self._publish_static_reply(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            status="templated",
            assistant_text=assistant_text,
        )

    def _build_pending_document_list_reply(self, tool_result: ToolExecutionResult) -> str:
        if not isinstance(tool_result.result, dict):
            return self.build_templated_reply(tool_results=[tool_result])

        pending_document_nos = self._extract_pending_document_nos(tool_result.result)
        queried_at = _now_text()
        stats_pending = self._find_stat_value(tool_result.result, "待处理单据")
        lines = ["根据处理工作台实时口径，当前“待处理”单据编号如下："]
        if pending_document_nos:
            lines.append("")
            lines.extend(f"{index}. {document_no}" for index, document_no in enumerate(pending_document_nos, start=1))
        else:
            lines.append("（当前 documents 列表中未命中 todoProcessStatus=待处理 的单据）")

        if stats_pending is not None and stats_pending != str(len(pending_document_nos)):
            lines.append("")
            lines.append(
                "口径提示："
                f"stats 显示待处理 {stats_pending} 条，"
                f"documents 过滤得到 {len(pending_document_nos)} 条；当前按 documents 过滤结果返回编号清单。"
            )

        lines.append(f"来源：{tool_result.source_of_truth}")
        lines.append(f"查询时间：{queried_at}")
        return "\n".join(lines)

    def _parse_approval_command(self, text: str) -> ApprovalCommand | None:
        match = _APPROVAL_COMMAND_PATTERN.match(text.strip())
        if match is None:
            return None
        command_map = {
            "确认审批计划": "confirm",
            "验证审批计划": "verify",
            "取消审批计划": "cancel",
        }
        command_type = command_map.get(match.group(1))
        if command_type is None:
            return None
        return ApprovalCommand(commandType=command_type, planId=match.group(2))

    def _extract_feedback_summary_lines(self, payload: dict[str, Any]) -> list[str]:
        feedback_overview = payload.get("feedbackOverview")
        if not isinstance(feedback_overview, dict):
            return []
        groups = feedback_overview.get("feedbackGroups")
        if not isinstance(groups, list):
            return []

        seen: set[str] = set()
        lines: list[str] = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            candidates = group.get("summaryLines")
            if isinstance(candidates, list) and candidates:
                raw_items = candidates
            else:
                summary = str(group.get("summary") or "").strip()
                raw_items = [summary] if summary else []
            for raw_item in raw_items:
                normalized = " ".join(str(raw_item or "").split()).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                lines.append(normalized)
        return lines

    def _build_reject_suggestion(self, payload: dict[str, Any]) -> str:
        return "\n".join(self._extract_feedback_summary_lines(payload)).strip()

    def _build_risk_summary(self, payload: dict[str, Any]) -> str:
        summary_lines = self._extract_feedback_summary_lines(payload)
        if summary_lines:
            summary = "；".join(summary_lines)
            return summary if len(summary) <= 200 else f"{summary[:197]}..."
        feedback_overview = payload.get("feedbackOverview")
        if isinstance(feedback_overview, dict):
            conclusion = str(feedback_overview.get("summaryConclusionLabel") or "").strip()
            if conclusion:
                return conclusion
        return "-"

    def _build_approval_request(self, decision: RouterDecision) -> ApprovalRequest:
        if decision.approvalRequest is not None:
            return decision.approvalRequest
        return ApprovalRequest()

    def _build_approval_missing_input_reply(self, request: ApprovalRequest) -> str:
        if not request.documentNo.strip():
            return "请提供单据编号，我再帮你生成审批计划。"
        if request.action is None:
            return "请明确这是要批准还是驳回，我再帮你生成审批计划。"
        if request.action == "approve":
            return "请提供审批意见，我再帮你生成批准计划。"
        return "未能生成可用的驳回建议稿，请直接补充最终驳回意见后再发起审批。"

    @staticmethod
    def _build_approval_disabled_reply(*, for_command: bool) -> str:
        action_text = "无法执行审批计划命令" if for_command else "请先在处理单据页执行"
        return (
            f"当前环境未开启对话审批能力，{action_text}。"
            "请设置环境变量 CLAWCHECK_CHAT_APPROVAL_ENABLED=true 后重启 API。"
            "如需限制为仅连通性验证，请同时设置 CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY=true；"
            "如需真实提交，请设置为 false。"
        )

    def _build_approval_plan_commands(self, plan_id: str) -> tuple[str, str, str]:
        return (
            f"确认审批计划 {plan_id}",
            f"验证审批计划 {plan_id}",
            f"取消审批计划 {plan_id}",
        )

    def _build_approval_plan_reply(self, plan: ApprovalPlan) -> str:
        action_label = "批准" if plan.action == "approve" else "驳回"
        suggestion_notice = ""
        if plan.approvalOpinionSource == "suggested_from_109":
            suggestion_notice = (
                "当前审批意见为系统建议稿，不能直接真实提交。"
                "请补充最终审批意见后，再重新发起审批请求。"
            )
        dry_run_hint = "建议先执行 dry-run 验证。" if not plan.requestedDryRun else "本轮请求已标记为优先做 dry-run 验证。"
        lines = [
            f"已生成待确认审批计划 {plan.planId}。",
            f"单据编号：{plan.documentNo}",
            f"当前待办处理状态：{plan.snapshot.todoProcessStatus or '-'}",
            f"当前单据状态：{plan.snapshot.documentStatus or '-'}",
            f"目标动作：{action_label}",
            f"审批意见：{plan.approvalOpinion or '-'}",
            f"风险摘要：{plan.snapshot.riskSummary or '-'}",
            dry_run_hint,
        ]
        if suggestion_notice:
            lines.append(suggestion_notice)
        lines.extend(
            [
                f"确认命令：{plan.confirmCommand}",
                f"验证命令：{plan.dryRunCommand}",
                f"取消命令：{plan.cancelCommand}",
            ]
        )
        return "\n".join(lines)

    def _build_approval_execution_reply(self, plan: ApprovalPlan, result: dict[str, Any]) -> str:
        dry_run = bool(result.get("dryRun"))
        action = str(result.get("action") or plan.action)
        action_label = "批准" if action == "approve" else "驳回"
        lines = [
            f"审批计划 {plan.planId} 已执行完成。",
            f"单据编号：{plan.documentNo}",
            f"执行动作：{action_label}",
            f"dry-run：{'是' if dry_run else '否'}",
            f"执行状态：{result.get('status') or '-'}",
            f"结果说明：{result.get('message') or '-'}",
        ]
        log_file = str(result.get("logFile") or "").strip()
        screenshot_file = str(result.get("screenshotFile") or "").strip()
        if log_file:
            lines.append(f"日志文件：{log_file}")
        if screenshot_file:
            lines.append(f"截图文件：{screenshot_file}")
        return "\n".join(lines)

    def _create_approval_plan(
        self,
        *,
        session_id: str,
        request: ApprovalRequest,
        approval_opinion: str,
        approval_opinion_source: str,
        document_detail: dict[str, Any],
    ) -> ApprovalPlan:
        created_at = datetime.now()
        expires_at = created_at + timedelta(seconds=self._approval_plan_ttl_seconds)
        plan_id = f"approval-plan-{created_at.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
        confirm_command, dry_run_command, cancel_command = self._build_approval_plan_commands(plan_id)
        return ApprovalPlan(
            planId=plan_id,
            sessionId=session_id,
            documentNo=request.documentNo.strip(),
            action=request.action or "approve",
            approvalOpinion=approval_opinion,
            approvalOpinionSource=approval_opinion_source,  # type: ignore[arg-type]
            requestedDryRun=bool(request.dryRun),
            status="pending_confirmation",
            snapshot=ApprovalPlanSnapshot(
                todoProcessStatus=self._find_overview_value(document_detail, "待办处理状态") or "待处理",
                documentStatus=self._find_overview_value(document_detail, "单据状态") or "-",
                riskSummary=self._build_risk_summary(document_detail),
                assessmentBatchNo=self._find_overview_value(document_detail, "评估批次号") or "",
            ),
            confirmCommand=confirm_command,
            dryRunCommand=dry_run_command,
            cancelCommand=cancel_command,
            createdAt=created_at.strftime("%Y-%m-%d %H:%M:%S"),
            updatedAt=created_at.strftime("%Y-%m-%d %H:%M:%S"),
            expiresAt=expires_at.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _update_plan_status(
        self,
        *,
        session_id: str,
        plan_id: str,
        status: str,
    ) -> ApprovalPlan | None:
        def _apply(plan: ApprovalPlan) -> ApprovalPlan:
            plan.status = status  # type: ignore[assignment]
            plan.updatedAt = _now_text()
            return plan

        return self._approval_plan_store.update_plan(session_id, plan_id, _apply)

    def build_clarification_reply(self, decision: RouterDecision) -> str:
        question = decision.clarificationQuestion.strip()
        if question:
            return question
        missing_inputs = decision.missingInputs
        if missing_inputs == ["documentNo"]:
            return "请提供单据编号，我再帮你查询当前状态。"
        if missing_inputs == ["approvalOpinion"]:
            return "请提供审批意见，我再继续。"
        if missing_inputs:
            joined = "、".join(missing_inputs)
            return f"请先补充以下关键信息：{joined}。"
        return "请补充关键信息后，我再继续查询。"

    def build_templated_reply(
        self,
        *,
        tool_results: list[ToolExecutionResult],
    ) -> str:
        if not tool_results:
            return f"查询时间：{_now_text()}"

        primary_result = tool_results[0]
        queried_at = _now_text()
        if primary_result.name == "get_process_workbench" and isinstance(primary_result.result, dict):
            pending_count = self._find_stat_value(primary_result.result, "待处理单据") or "-"
            return (
                f"根据处理工作台实时口径，当前待处理单据为 {pending_count} 条。\n"
                f"来源：{primary_result.source_of_truth}\n"
                f"查询时间：{queried_at}"
            )
        if primary_result.name == "get_process_document_detail" and isinstance(primary_result.result, dict):
            document_no = str(primary_result.result.get("documentNo") or primary_result.arguments.get("documentNo") or "-")
            todo_status = self._find_overview_value(primary_result.result, "待办处理状态") or "-"
            document_status = self._find_overview_value(primary_result.result, "单据状态") or "-"
            summary_conclusion = self._find_overview_value(primary_result.result, "总结论") or "-"
            return (
                f"单据 {document_no} 当前单据状态为 {document_status}，待办处理状态为 {todo_status}，总结论为 {summary_conclusion}。\n"
                f"来源：{primary_result.source_of_truth}\n"
                f"查询时间：{queried_at}"
            )
        if primary_result.name == "get_collect_workbench" and isinstance(primary_result.result, dict):
            entered_count = self._find_stat_value(primary_result.result, "已进入处理单据") or "-"
            recollect_count = self._find_stat_value(primary_result.result, "待补采单据") or "-"
            return (
                f"根据采集工作台实时口径，当前已进入处理单据 {entered_count} 条，待补采单据 {recollect_count} 条。\n"
                f"来源：{primary_result.source_of_truth}\n"
                f"查询时间：{queried_at}"
            )
        return f"已完成正式数据源查询。\n来源：{primary_result.source_of_truth}\n查询时间：{queried_at}"

    def _validate_router_decision(self, decision: RouterDecision) -> tuple[bool, str]:
        if decision.route == "tool_first" and not decision.requires_clarification and not decision.toolCalls:
            return False, "tool_first route requires at least one tool call."
        if decision.route != "tool_first" and decision.toolCalls:
            return False, "Only tool_first route may include tool calls."
        if decision.route == "approval_prepare" and decision.approvalRequest is None:
            return False, "approval_prepare route requires approvalRequest."
        if decision.route != "approval_prepare" and decision.approvalRequest is not None:
            request = decision.approvalRequest
            if request.documentNo.strip() or request.action is not None or request.approvalOpinion.strip() or request.dryRun:
                return False, "approvalRequest is only allowed for approval_prepare route."
        if (
            decision.route == "tool_first"
            and not decision.requires_clarification
            and decision.confidence < self.TOOL_FIRST_CONFIDENCE_THRESHOLD
        ):
            return False, "Router confidence below tool_first threshold."
        if decision.requiresPendingDocumentList:
            if decision.route != "tool_first":
                return False, "requiresPendingDocumentList requires tool_first route."
            if decision.requires_clarification:
                return False, "requiresPendingDocumentList cannot be combined with missingInputs."
            if not decision.toolCalls:
                return False, "requiresPendingDocumentList requires get_process_workbench tool call."
            primary_tool_name = decision.toolCalls[0].name
            if primary_tool_name != "get_process_workbench":
                return False, "requiresPendingDocumentList requires get_process_workbench as primary tool."

        index = self._skill_loader.get_index()
        allowed_references: set[str] = set()
        for skill_name in decision.selectedSkills:
            entry = index.entries.get(skill_name)
            if entry is None:
                return False, f"Router selected unknown skill: {skill_name}"
            if entry.status == "deprecated":
                return False, f"Router selected deprecated skill: {skill_name}"
            allowed_references.update(entry.references)

        for reference_name in decision.selectedReferences:
            if reference_name not in allowed_references:
                return False, f"Router selected invalid reference: {reference_name}"

        if decision.route == "approval_prepare" and "process-approval" not in decision.selectedReferences:
            return False, "approval_prepare route must include process-approval reference."

        for tool_call in decision.toolCalls:
            if self._tool_registry.get_tool(tool_call.name) is None:
                return False, f"Router selected unregistered tool: {tool_call.name}"
        return True, ""

    def _normalize_router_decision(self, decision: RouterDecision) -> list[str]:
        notes: list[str] = []
        if decision.route != "approval_prepare":
            return notes

        target_reference = "process-approval"
        if target_reference in decision.selectedReferences:
            return notes

        index = self._skill_loader.get_index()
        selected_skill_supports_reference = any(
            (
                entry is not None
                and entry.status != "deprecated"
                and target_reference in entry.references
            )
            for entry in (index.entries.get(skill_name) for skill_name in decision.selectedSkills)
        )
        if selected_skill_supports_reference:
            decision.selectedReferences.append(target_reference)
            notes.append("approval_prepare missing process-approval reference; auto-added reference.")
            return notes

        supporting_skills = [
            entry.skill_name
            for entry in index.active_entries()
            if target_reference in entry.references
        ]
        if not supporting_skills:
            return notes

        fallback_skill = supporting_skills[0]
        if fallback_skill not in decision.selectedSkills:
            decision.selectedSkills.append(fallback_skill)
            notes.append(
                "approval_prepare missing skill with process-approval reference; "
                f"auto-added skill {fallback_skill}."
            )
        decision.selectedReferences.append(target_reference)
        notes.append("approval_prepare missing process-approval reference; auto-added reference.")
        return notes

    def prepare_approval_plan(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        decision: RouterDecision,
    ) -> _TurnOutcome:
        if not self._approval_enabled:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=self._build_approval_disabled_reply(for_command=False),
            )

        request = self._build_approval_request(decision)
        if not request.documentNo.strip() or request.action is None:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=self._build_approval_missing_input_reply(request),
            )

        self._publish_status(
            session_id=session_id,
            run_id=run_id,
            status="approval_preparing",
            message_id=assistant_message_id,
        )
        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="approval_plan_prepare_started",
            summary=f"正在为单据 {request.documentNo.strip()} 生成待确认审批计划。",
            message_id=assistant_message_id,
        )

        document_detail = get_process_document_detail(request.documentNo.strip())
        if document_detail is None:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=f"未找到单据 {request.documentNo.strip()} 的正式工作台详情，无法生成审批计划。",
            )

        todo_process_status = (self._find_overview_value(document_detail, "待办处理状态") or "待处理").strip()
        if todo_process_status in {"已处理", "已驳回"}:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=(
                    f"单据 {request.documentNo.strip()} 当前待办处理状态为“{todo_process_status}”，"
                    "不再允许通过对话工作台继续审批。"
                ),
            )

        approval_opinion = request.approvalOpinion.strip()
        approval_opinion_source = "user_input"
        if request.action == "approve" and not approval_opinion:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text="请提供审批意见，我再帮你生成批准计划。",
            )
        if request.action == "reject" and not approval_opinion:
            approval_opinion = self._build_reject_suggestion(document_detail)
            if not approval_opinion:
                return self._publish_static_reply(
                    session_id=session_id,
                    run_id=run_id,
                    assistant_message_id=assistant_message_id,
                    status="clarifying",
                    assistant_text="当前未能从风险总览生成可用的驳回建议稿，请直接补充最终驳回意见后再发起审批。",
                )
            approval_opinion_source = "suggested_from_109"

        plan = self._create_approval_plan(
            session_id=session_id,
            request=request,
            approval_opinion=approval_opinion,
            approval_opinion_source=approval_opinion_source,
            document_detail=document_detail,
        )
        self._approval_plan_store.save_plan(plan)
        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="approval_plan_created",
            summary=f"已生成审批计划 {plan.planId}，等待用户确认。",
            message_id=assistant_message_id,
        )
        return self._publish_static_reply(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            status="approval_confirmation_required",
            assistant_text=self._build_approval_plan_reply(plan),
        )

    def execute_pending_approval_plan(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        plan: ApprovalPlan,
        dry_run: bool,
    ) -> _TurnOutcome:
        status = "approval_dry_running" if dry_run else "approval_submitting"
        event_type = "approval_plan_dry_run_started" if dry_run else "approval_plan_submit_started"
        summary = (
            f"审批计划 {plan.planId} 开始执行 dry-run。"
            if dry_run
            else f"审批计划 {plan.planId} 开始执行真实提交。"
        )
        self._publish_status(
            session_id=session_id,
            run_id=run_id,
            status=status,
            message_id=assistant_message_id,
        )
        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type=event_type,
            summary=summary,
            message_id=assistant_message_id,
        )

        latest_detail = get_process_document_detail(plan.documentNo)
        if latest_detail is None:
            self._update_plan_status(session_id=session_id, plan_id=plan.planId, status="failed")
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="failed",
                assistant_text=f"未找到单据 {plan.documentNo} 的最新正式详情，审批计划已中止。",
            )

        latest_todo_status = (self._find_overview_value(latest_detail, "待办处理状态") or "待处理").strip()
        if latest_todo_status in {"已处理", "已驳回"}:
            self._update_plan_status(session_id=session_id, plan_id=plan.planId, status="failed")
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="failed",
                assistant_text=(
                    f"单据 {plan.documentNo} 当前待办处理状态为“{latest_todo_status}”，"
                    "审批计划已失效，请勿继续执行。"
                ),
            )

        try:
            result = approve_process_document(
                document_no=plan.documentNo,
                action=plan.action,
                approval_opinion=plan.approvalOpinion,
                dry_run=dry_run,
            )
        except Exception as exc:  # noqa: BLE001
            self._update_plan_status(session_id=session_id, plan_id=plan.planId, status="failed")
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="approval_plan_finished",
                summary=f"审批计划 {plan.planId} 执行失败：{exc}",
                message_id=assistant_message_id,
            )
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="failed",
                assistant_text=f"审批计划 {plan.planId} 执行失败：{exc}",
            )

        final_status = "dry_run_succeeded" if dry_run else "submitted"
        self._update_plan_status(session_id=session_id, plan_id=plan.planId, status=final_status)
        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="approval_plan_finished",
            summary=f"审批计划 {plan.planId} 执行完成，status={result.get('status') or '-'}。",
            message_id=assistant_message_id,
        )
        return self._publish_static_reply(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            status=str(result.get("status") or "succeeded"),
            assistant_text=self._build_approval_execution_reply(plan, result),
        )

    def cancel_pending_approval_plan(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        plan: ApprovalPlan,
    ) -> _TurnOutcome:
        self._update_plan_status(session_id=session_id, plan_id=plan.planId, status="canceled")
        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="approval_plan_canceled",
            summary=f"审批计划 {plan.planId} 已取消。",
            message_id=assistant_message_id,
        )
        return self._publish_static_reply(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            status="canceled",
            assistant_text=f"审批计划 {plan.planId} 已取消，不会再执行真实提交。",
        )

    @staticmethod
    def _normalize_command_text(text: str) -> str:
        return " ".join(str(text or "").strip().lower().split())

    def _detect_approval_command_type(self, normalized_text: str) -> str | None:
        if any(keyword in normalized_text for keyword in _APPROVAL_VERIFY_KEYWORDS):
            return "verify"
        if any(keyword in normalized_text for keyword in _APPROVAL_CANCEL_KEYWORDS):
            return "cancel"
        if any(keyword in normalized_text for keyword in _APPROVAL_CONFIRM_KEYWORDS):
            return "confirm"
        return None

    def _parse_approval_command(self, text: str) -> ApprovalCommand | None:
        normalized_text = self._normalize_command_text(text)
        if not normalized_text:
            return None
        command_type = self._detect_approval_command_type(normalized_text)
        if command_type is None:
            return None
        plan_id_match = _APPROVAL_PLAN_ID_PATTERN.search(normalized_text)
        if plan_id_match is None:
            return None
        return ApprovalCommand(commandType=command_type, planId=plan_id_match.group(1))

    def _infer_implicit_approval_command(
        self,
        *,
        session_id: str,
        text: str,
    ) -> tuple[ApprovalCommand | None, str | None]:
        normalized_text = self._normalize_command_text(text)
        if not normalized_text:
            return None, None
        if _APPROVAL_PLAN_ID_PATTERN.search(normalized_text) is not None:
            return None, None

        command_type = self._detect_approval_command_type(normalized_text)
        if command_type is None:
            return None, None

        active_plans = [
            plan
            for plan in self._approval_plan_store.list_session_plans(session_id)
            if plan.status in ACTIVE_APPROVAL_PLAN_STATUSES
        ]
        if not active_plans:
            return None, None

        if len(active_plans) > 1:
            candidate_ids = "、".join(plan.planId for plan in active_plans[-3:])
            return (
                None,
                f"检测到多个待确认审批计划，请指定 planId 再执行。可用计划：{candidate_ids}",
            )

        plan = active_plans[-1]
        return ApprovalCommand(commandType=command_type, planId=plan.planId), None

    def try_handle_approval_confirmation_command(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        latest_user_message: str,
    ) -> _TurnOutcome | None:
        command = self._parse_approval_command(latest_user_message)
        if command is None:
            command, infer_error = self._infer_implicit_approval_command(
                session_id=session_id,
                text=latest_user_message,
            )
            if infer_error:
                return self._publish_static_reply(
                    session_id=session_id,
                    run_id=run_id,
                    assistant_message_id=assistant_message_id,
                    status="clarifying",
                    assistant_text=infer_error,
                )
            if command is None:
                return None
        if not self._approval_enabled:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=self._build_approval_disabled_reply(for_command=True),
            )

        plan = self._approval_plan_store.get_plan(session_id, command.planId)
        if plan is None:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=f"未找到审批计划 {command.planId}，请确认 planId 是否正确。",
            )
        if plan.status == "expired":
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=f"审批计划 {plan.planId} 已过期，请重新发起审批请求。",
            )
        if command.commandType == "cancel":
            if plan.status in TERMINAL_APPROVAL_PLAN_STATUSES:
                return self._publish_static_reply(
                    session_id=session_id,
                    run_id=run_id,
                    assistant_message_id=assistant_message_id,
                    status="clarifying",
                    assistant_text=f"审批计划 {plan.planId} 当前状态为 {plan.status}，不能再取消。",
                )
            return self.cancel_pending_approval_plan(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                plan=plan,
            )
        if plan.status not in ACTIVE_APPROVAL_PLAN_STATUSES:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=f"审批计划 {plan.planId} 当前状态为 {plan.status}，不能继续执行。",
            )
        if command.commandType == "verify" and plan.status != "pending_confirmation":
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=f"审批计划 {plan.planId} 当前状态为 {plan.status}，不能再次执行 dry-run。",
            )
        if command.commandType == "confirm" and self._approval_dry_run_only:
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text="当前环境处于 dry-run only 灰度期，暂不允许真实提交。请先执行验证审批计划命令。",
            )
        if command.commandType == "confirm" and plan.approvalOpinionSource == "suggested_from_109":
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=(
                    f"审批计划 {plan.planId} 当前审批意见仍是系统建议稿，不能直接真实提交。"
                    "请重新发起审批请求并补充最终审批意见。"
                ),
            )
        if command.commandType == "confirm":
            self._update_plan_status(session_id=session_id, plan_id=plan.planId, status="submit_requested")
            plan = self._approval_plan_store.get_plan(session_id, plan.planId) or plan
        return self.execute_pending_approval_plan(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            plan=plan,
            dry_run=command.commandType == "verify",
        )

    def route_turn(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        latest_user_message: str,
        workspace_dir: Path,
        cancel_event: threading.Event,
    ) -> RouterDecision | None:
        self._publish_status(
            session_id=session_id,
            run_id=run_id,
            status="routing",
            message_id=assistant_message_id,
        )
        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="router_start",
            summary="正在识别问题意图并评估是否需要调用正式工具。",
            message_id=assistant_message_id,
        )

        recent_messages = self._store.list_messages(session_id=session_id, limit=12)
        router_prompt = build_router_prompt(
            latest_user_message=latest_user_message,
            recent_messages=recent_messages,
            available_skills=self._skill_loader.list_router_metadata(),
            available_tools=self._tool_registry.list_router_metadata(),
            confidence_threshold=self.TOOL_FIRST_CONFIDENCE_THRESHOLD,
        )
        backend_mode = self._active_backend_mode()
        try:
            if backend_mode == "oneshot_exec":
                router_result = run_router_exec(
                    config=self._provider_config,
                    prompt=router_prompt,
                    workspace_dir=workspace_dir,
                    output_schema=router_decision_json_schema(),
                    cancel_event=cancel_event,
                    runtime_dir=self._runtime_dir,
                )
            else:
                router_result = self._execution_adapter.run_router(
                    config=self._provider_config,
                    prompt=router_prompt,
                    workspace_dir=workspace_dir,
                    output_schema=router_decision_json_schema(),
                    cancel_event=cancel_event,
                    runtime_dir=self._runtime_dir,
                )
        except Exception as exc:  # noqa: BLE001
            if self._provider_config.exec_auto_fallback and backend_mode != "oneshot_exec":
                self._publish_summary_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type="backend_auto_fallback",
                    summary=f"路由后端 {backend_mode} 失败，自动降级到 oneshot_exec。原因：{exc}",
                    message_id=assistant_message_id,
                )
                self._set_active_run_backend_mode(session_id=session_id, backend_mode="oneshot_exec")
                router_result = run_router_exec(
                    config=self._provider_config,
                    prompt=router_prompt,
                    workspace_dir=workspace_dir,
                    output_schema=router_decision_json_schema(),
                    cancel_event=cancel_event,
                    runtime_dir=self._runtime_dir,
                )
            else:
                router_result = None
        if router_result is None:
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="router_fallback",
                summary="路由阶段异常，已回退到通用对话链路。",
                message_id=assistant_message_id,
            )
            return None
        if router_result.status != "succeeded" or router_result.decision is None:
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="router_fallback",
                summary=(
                    "路由阶段失败，已回退到通用对话链路。"
                    f" 原因：{router_result.error_message or router_result.status}"
                ),
                message_id=assistant_message_id,
            )
            return None

        try:
            decision = RouterDecision.model_validate(router_result.decision)
        except ValidationError as exc:
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="router_validation_failed",
                summary=f"路由输出未通过校验，已回退到通用对话链路。{exc}",
                message_id=assistant_message_id,
            )
            return None

        normalization_notes = self._normalize_router_decision(decision)
        if normalization_notes:
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="router_decision_normalized",
                summary="; ".join(normalization_notes),
                message_id=assistant_message_id,
            )

        is_valid, validation_message = self._validate_router_decision(decision)
        if not is_valid:
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="router_fallback",
                summary=f"路由结果未通过后端校验，已回退到通用对话链路。原因：{validation_message}",
                message_id=assistant_message_id,
            )
            return None

        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="router_decision",
            summary=(
                f"路由结果：{decision.route}，answerMode={decision.answerMode}，"
                f"skills={decision.selectedSkills}，tools={[tool.name for tool in decision.toolCalls]}"
            ),
            message_id=assistant_message_id,
        )
        return decision

    def _load_selected_skill_contexts(self, decision: RouterDecision) -> list[LoadedSkillContext]:
        index = self._skill_loader.get_index()
        selected_reference_set = set(decision.selectedReferences)
        loaded_contexts: list[LoadedSkillContext] = []
        for skill_name in decision.selectedSkills:
            entry = index.entries.get(skill_name)
            if entry is None or entry.status == "deprecated":
                raise ValueError(f"Skill not available: {skill_name}")
            references = [reference for reference in entry.references if reference in selected_reference_set]
            loaded_contexts.append(
                self._skill_loader.load_skill_context(skill_name, references=references)
            )
        return loaded_contexts

    def execute_tool_plan(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        decision: RouterDecision,
    ) -> list[ToolExecutionResult]:
        tool_results: list[ToolExecutionResult] = []
        for tool_call in decision.toolCalls:
            self._publish_status(
                session_id=session_id,
                run_id=run_id,
                status="running_tool",
                message_id=assistant_message_id,
            )
            self._publish_tool_event(
                session_id=session_id,
                run_id=run_id,
                event_type="tool_call",
                summary=(
                    f"正在调用正式工具 {tool_call.name}，参数："
                    f"{json.dumps(tool_call.arguments, ensure_ascii=False)}"
                ),
                message_id=assistant_message_id,
            )
            tool_result = self._tool_registry.execute(tool_call.name, tool_call.arguments)
            if tool_result.result is None:
                if tool_result.name == "get_process_document_detail":
                    document_no = tool_result.arguments.get("documentNo", "")
                    raise LookupError(f"未找到单据 {document_no} 的正式工作台结果。")
                raise LookupError(f"正式工具 {tool_result.name} 未返回结果。")
            tool_results.append(tool_result)
            self._publish_tool_event(
                session_id=session_id,
                run_id=run_id,
                event_type="tool_result",
                summary=f"正式工具 {tool_result.name} 调用成功，来源：{tool_result.source_of_truth}",
                message_id=assistant_message_id,
            )
        return tool_results

    def _build_tool_failure_reply(
        self,
        *,
        tool_name: str,
        source_of_truth: str,
        error_message: str,
    ) -> str:
        return (
            f"我已尝试调用正式数据源 {source_of_truth}（工具：{tool_name}），但本次查询失败：{error_message}\n"
            "建议先确认参数是否完整，再检查对应工作台接口与数据库运行状态。"
        )

    def compose_answer(
        self,
        *,
        session_id: str,
        run_id: str,
        assistant_message_id: str,
        latest_user_message: str,
        decision: RouterDecision,
        loaded_skill_contexts: list[LoadedSkillContext],
        tool_results: list[ToolExecutionResult],
        workspace_dir: Path,
        cancel_event: threading.Event,
    ) -> _TurnOutcome:
        if decision.requires_clarification:
            self._publish_status(
                session_id=session_id,
                run_id=run_id,
                status="clarifying",
                message_id=assistant_message_id,
            )
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="clarification",
                summary="当前缺少关键参数，已进入追问补齐分支。",
                message_id=assistant_message_id,
            )
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="clarifying",
                assistant_text=self.build_clarification_reply(decision),
            )

        if decision.answerMode == "templated":
            if tool_results:
                primary_result = tool_results[0]
                if (
                    decision.requiresPendingDocumentList
                    and primary_result.name == "get_process_workbench"
                    and isinstance(primary_result.result, dict)
                ):
                    self._publish_status(
                        session_id=session_id,
                        run_id=run_id,
                        status="templated",
                        message_id=assistant_message_id,
                    )
                    self._publish_summary_event(
                        session_id=session_id,
                        run_id=run_id,
                        event_type="templated_answer",
                        summary="已根据路由意图输出待处理单据编号清单。",
                        message_id=assistant_message_id,
                    )
                    return self._publish_static_reply(
                        session_id=session_id,
                        run_id=run_id,
                        assistant_message_id=assistant_message_id,
                        status="templated",
                        assistant_text=self._build_pending_document_list_reply(primary_result),
                    )
            self._publish_status(
                session_id=session_id,
                run_id=run_id,
                status="templated",
                message_id=assistant_message_id,
            )
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="templated_answer",
                summary="已使用正式工具结果生成模板化直答。",
                message_id=assistant_message_id,
            )
            return self._publish_static_reply(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                status="templated",
                assistant_text=self.build_templated_reply(tool_results=tool_results),
            )

        self._publish_status(
            session_id=session_id,
            run_id=run_id,
            status="composing",
            message_id=assistant_message_id,
        )
        self._publish_summary_event(
            session_id=session_id,
            run_id=run_id,
            event_type="compose_answer",
            summary="正在基于项目上下文和正式工具结果组织最终答复。",
            message_id=assistant_message_id,
        )
        answer_prompt = self._build_answer_prompt(
            session_id=session_id,
            latest_user_message=latest_user_message,
            loaded_skill_contexts=loaded_skill_contexts,
            tool_results=tool_results,
        )
        return self._run_model_prompt(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            prompt=answer_prompt,
            workspace_dir=workspace_dir,
            cancel_event=cancel_event,
        )

    def _execute_structured_turn(
        self,
        *,
        run_id: str,
        session_id: str,
        assistant_message_id: str,
        latest_user_message: str,
        workspace_dir: Path,
        cancel_event: threading.Event,
    ) -> _TurnOutcome | None:
        decision = self.route_turn(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            latest_user_message=latest_user_message,
            workspace_dir=workspace_dir,
            cancel_event=cancel_event,
        )
        if decision is None:
            return None

        if decision.route == "general_chat":
            self._publish_summary_event(
                session_id=session_id,
                run_id=run_id,
                event_type="router_fallback",
                summary="路由结果为 general_chat，已回退到通用对话链路。",
                message_id=assistant_message_id,
            )
            return None

        if decision.route == "approval_prepare":
            return self.prepare_approval_plan(
                session_id=session_id,
                run_id=run_id,
                assistant_message_id=assistant_message_id,
                decision=decision,
            )

        loaded_skill_contexts = self._load_selected_skill_contexts(decision)
        tool_results: list[ToolExecutionResult] = []
        if decision.route == "tool_first" and not decision.requires_clarification:
            try:
                tool_results = self.execute_tool_plan(
                    session_id=session_id,
                    run_id=run_id,
                    assistant_message_id=assistant_message_id,
                    decision=decision,
                )
            except Exception as exc:  # noqa: BLE001
                failed_tool_name = decision.toolCalls[0].name if decision.toolCalls else "unknown_tool"
                failed_tool = self._tool_registry.get_tool(failed_tool_name)
                source_of_truth = failed_tool.source_of_truth if failed_tool is not None else failed_tool_name
                self._publish_summary_event(
                    session_id=session_id,
                    run_id=run_id,
                    event_type="tool_failure",
                    summary=f"正式工具调用失败：{failed_tool_name}，原因：{exc}",
                    message_id=assistant_message_id,
                )
                return self._publish_static_reply(
                    session_id=session_id,
                    run_id=run_id,
                    assistant_message_id=assistant_message_id,
                    status="tool_failed",
                    assistant_text=self._build_tool_failure_reply(
                        tool_name=failed_tool_name,
                        source_of_truth=source_of_truth,
                        error_message=str(exc),
                    ),
                )

        return self.compose_answer(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            latest_user_message=latest_user_message,
            decision=decision,
            loaded_skill_contexts=loaded_skill_contexts,
            tool_results=tool_results,
            workspace_dir=workspace_dir,
            cancel_event=cancel_event,
        )

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
            cancel_event = run_state.cancel_event
            backend_mode = run_state.backend_mode or self._active_backend_mode()

        acquire_result = self._execution_scheduler.acquire(
            run_id=run_id,
            cancel_event=cancel_event,
        )
        try:
            if not acquire_result.acquired:
                if acquire_result.reason == "queue_full":
                    self._publish_summary_event(
                        session_id=session_id,
                        run_id=run_id,
                        event_type="run_rejected",
                        summary="系统并发已满且队列已达上限，请稍后重试。",
                        message_id=assistant_message_id,
                    )
                    self._publish_status(
                        session_id=session_id,
                        run_id=run_id,
                        status="failed",
                        message_id=assistant_message_id,
                    )
                    outcome = _TurnOutcome(
                        status="failed",
                        assistant_text="当前请求较多，队列已满，请稍后重试。",
                        output_tail="queue_full",
                        token_count=_approx_token_count("当前请求较多，队列已满，请稍后重试。"),
                        exit_code=1,
                    )
                elif acquire_result.reason == "canceled":
                    self._publish_status(
                        session_id=session_id,
                        run_id=run_id,
                        status="canceled",
                        message_id=assistant_message_id,
                    )
                    outcome = _TurnOutcome(
                        status="canceled",
                        assistant_text="会话运行已取消。",
                        output_tail="canceled_while_queued",
                        token_count=_approx_token_count("会话运行已取消。"),
                        exit_code=130,
                    )
                else:
                    self._publish_status(
                        session_id=session_id,
                        run_id=run_id,
                        status="failed",
                        message_id=assistant_message_id,
                    )
                    outcome = _TurnOutcome(
                        status="failed",
                        assistant_text="会话调度失败，请稍后重试。",
                        output_tail=acquire_result.reason or "scheduler_failed",
                        token_count=_approx_token_count("会话调度失败，请稍后重试。"),
                        exit_code=1,
                    )
            else:
                if acquire_result.queued:
                    self._publish_summary_event(
                        session_id=session_id,
                        run_id=run_id,
                        event_type="queue_acquired",
                        summary="已从排队状态进入执行。",
                        message_id=assistant_message_id,
                    )

                with self._run_lock:
                    current = self._runs_by_session.get(session_id)
                    if current is not None:
                        current.status = "running"
                        backend_mode = current.backend_mode or backend_mode
                self._run_state_store.upsert(
                    run_id=run_id,
                    session_id=session_id,
                    status="running",
                    backend_mode=backend_mode,
                )
                self._publish_status(
                    session_id=session_id,
                    run_id=run_id,
                    status="running",
                    message_id=assistant_message_id,
                )

                user_message = self._store.get_message(user_message_id) or {}
                latest_user_message = str(user_message.get("content") or "").strip()
                session = self._store.get_session(session_id)
                run_workspace = self._resolve_run_workspace(session)

                try:
                    approval_outcome = self.try_handle_approval_confirmation_command(
                        session_id=session_id,
                        run_id=run_id,
                        assistant_message_id=assistant_message_id,
                        latest_user_message=latest_user_message,
                    )

                    if approval_outcome is not None:
                        outcome = approval_outcome
                    elif (
                        fast_path_outcome := self.try_handle_fast_path_query(
                            session_id=session_id,
                            run_id=run_id,
                            assistant_message_id=assistant_message_id,
                            latest_user_message=latest_user_message,
                        )
                    ) is not None:
                        outcome = fast_path_outcome
                    elif self._router_enabled:
                        outcome = self._execute_structured_turn(
                            run_id=run_id,
                            session_id=session_id,
                            assistant_message_id=assistant_message_id,
                            latest_user_message=latest_user_message,
                            workspace_dir=run_workspace,
                            cancel_event=cancel_event,
                        )
                    else:
                        self._publish_summary_event(
                            session_id=session_id,
                            run_id=run_id,
                            event_type="router_disabled",
                            summary="Router 阶段已关闭，直接使用通用对话链路。",
                            message_id=assistant_message_id,
                        )
                        outcome = None

                    if outcome is None:
                        prompt = self._build_general_prompt(session_id=session_id)
                        outcome = self._run_model_prompt(
                            session_id=session_id,
                            run_id=run_id,
                            assistant_message_id=assistant_message_id,
                            prompt=prompt,
                            workspace_dir=run_workspace,
                            cancel_event=cancel_event,
                        )
                except Exception as exc:  # noqa: BLE001
                    outcome = _TurnOutcome(
                        status="failed",
                        assistant_text=f"会话执行失败：{exc}",
                        output_tail=str(exc)[:4000],
                        token_count=_approx_token_count(f"会话执行失败：{exc}"),
                        exit_code=1,
                    )

            self._store.update_message_content(
                message_id=assistant_message_id,
                content=outcome.assistant_text,
                token_count=outcome.token_count,
            )
            normalized_session_status = "idle"
            if outcome.status == "canceled":
                normalized_session_status = "canceled"
            elif outcome.status in {"failed", "timeout", "tool_failed"}:
                normalized_session_status = "failed"
            self._store.update_session_status(session_id=session_id, status=normalized_session_status)
            self._store.touch_session(session_id=session_id)
            self._append_execution_log(
                session_id=session_id,
                message_id=assistant_message_id,
                event_type="result",
                event_summary=outcome.output_tail or outcome.assistant_text[:4000],
                exit_code=outcome.exit_code,
            )
            self._publish_event(
                session_id,
                "done",
                {
                    "runId": run_id,
                    "sessionId": session_id,
                    "userMessageId": user_message_id,
                    "assistantMessageId": assistant_message_id,
                    "status": outcome.status,
                    "message": outcome.assistant_text,
                    "tokenCount": outcome.token_count,
                },
            )

            with self._run_lock:
                current = self._runs_by_session.get(session_id)
                if current is not None:
                    backend_mode = current.backend_mode or backend_mode

            terminal_run_status = "succeeded"
            if outcome.status in {"failed", "timeout", "tool_failed"}:
                terminal_run_status = outcome.status
            elif outcome.status in {"canceled", "cancel_requested"}:
                terminal_run_status = "canceled"
            self._run_state_store.upsert(
                run_id=run_id,
                session_id=session_id,
                status=terminal_run_status,
                backend_mode=backend_mode,
                error_code=terminal_run_status if terminal_run_status in {"failed", "timeout", "tool_failed"} else "",
                error_message=(outcome.output_tail or outcome.assistant_text)[:2000]
                if terminal_run_status in {"failed", "timeout", "tool_failed"}
                else "",
            )
        finally:
            self._execution_scheduler.release(run_id=run_id)
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
            backend_mode = run_state.backend_mode or self._active_backend_mode()
        self._run_state_store.upsert(
            run_id=run_id,
            session_id=session_id,
            status="cancel_requested",
            backend_mode=backend_mode,
        )
        self._publish_status(
            session_id=session_id,
            run_id=run_id,
            status="cancel_requested",
            message_id=run_state.assistant_message_id,
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
        scheduler_snapshot = self._execution_scheduler.snapshot()
        return {
            "provider": self._provider_config.provider,
            "baseUrl": self._provider_config.base_url,
            "model": self._provider_config.model,
            "routerModel": self._provider_config.router_model,
            "routerReasoningEffort": self._provider_config.router_reasoning_effort,
            "timeoutSeconds": self._provider_config.timeout_seconds,
            "maxOutputTokens": self._provider_config.max_output_tokens,
            "apiKeyEnv": self._provider_config.api_key_env,
            "apiKeyConfigured": bool(self._provider_config.api_key),
            "codexCliExecutable": self._provider_config.codex_cli_executable,
            "codexCliResolvedPath": codex_path or "",
            "workspaceDir": str(self._provider_config.workspace_dir),
            "execMode": self._provider_config.exec_mode,
            "execAutoFallback": self._provider_config.exec_auto_fallback,
            "globalMaxConcurrentRuns": self._provider_config.global_max_concurrent_runs,
            "runQueueSize": self._provider_config.run_queue_size,
            "sessionIdleTtlSeconds": self._provider_config.session_idle_ttl_seconds,
            "appServerBaseUrl": self._provider_config.app_server_base_url,
            "appServerTimeoutSeconds": self._provider_config.app_server_timeout_seconds,
            "scheduler": scheduler_snapshot,
            "routerEnabled": self._router_enabled,
            "fastPathEnabled": self._fast_path_enabled,
            "approvalEnabled": self._approval_enabled,
            "approvalDryRunOnly": self._approval_dry_run_only,
            "approvalPlanTtlSeconds": self._approval_plan_ttl_seconds,
        }

    def get_health(self) -> dict[str, Any]:
        execution_health = self._execution_adapter.health(config=self._provider_config)
        backend_mode = self._active_backend_mode()
        codex_path = resolve_codex_cli_path(self._provider_config)
        codex_version = ""
        codex_ok = False
        if codex_path and backend_mode in {"oneshot_exec", "persistent_subprocess"}:
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
        if backend_mode == "app_server":
            status = "ok" if execution_health.get("ready") else "degraded"
        else:
            status = "ok" if (codex_ok and key_ok) else "degraded"
        return {
            "status": status,
            "execMode": backend_mode,
            "executionBackend": execution_health.get("backend") or backend_mode,
            "executionBackendReady": bool(execution_health.get("ready")),
            "codexCliAvailable": codex_ok,
            "codexCliPath": codex_path or "",
            "codexCliVersion": codex_version,
            "apiKeyEnv": self._provider_config.api_key_env,
            "apiKeyConfigured": key_ok,
            "provider": self._provider_config.provider,
            "model": self._provider_config.model,
            "routerModel": self._provider_config.router_model,
            "routerReasoningEffort": self._provider_config.router_reasoning_effort,
            "routerEnabled": self._router_enabled,
            "fastPathEnabled": self._fast_path_enabled,
            "approvalEnabled": self._approval_enabled,
            "approvalDryRunOnly": self._approval_dry_run_only,
            "approvalPlanTtlSeconds": self._approval_plan_ttl_seconds,
            "scheduler": self._execution_scheduler.snapshot(),
            "appServerBaseUrl": self._provider_config.app_server_base_url,
            "appServerTimeoutSeconds": self._provider_config.app_server_timeout_seconds,
            "appServerHealthUrl": execution_health.get("appServerHealthUrl") or "",
            "appServerStatusCode": execution_health.get("appServerStatusCode") or 0,
            "appServerMessage": execution_health.get("appServerMessage") or "",
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
