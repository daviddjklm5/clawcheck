from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from automation.api.config_summary import _load_runtime_settings
from automation.chat.codex_runner import (
    CodexExecutionResult,
    resolve_codex_cli_path,
    run_codex_exec,
    run_router_exec,
)
from automation.chat.provider_config import ChatProviderConfig, load_chat_provider_config
from automation.chat.router_models import RouterDecision, router_decision_json_schema
from automation.chat.router_prompt import build_router_prompt
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


@dataclass
class _SessionRunState:
    run_id: str
    session_id: str
    user_message_id: str
    assistant_message_id: str
    cancel_event: threading.Event
    thread: threading.Thread
    status: str


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
        self._runtime_dir = Path(__file__).resolve().parents[1] / "runtime" / "chat"

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
        self._router_enabled = _env_flag("CLAWCHECK_CHAT_ROUTER_ENABLED", default=True)

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
            return {
                "stats": result.get("stats", []),
                "documentCount": len(documents),
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
        callback = self._build_runner_callback(
            session_id=session_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            assistant_chunks=assistant_chunks,
        )

        try:
            final_result = run_codex_exec(
                config=self._provider_config,
                prompt=prompt,
                workspace_dir=workspace_dir,
                cancel_event=cancel_event,
                callback=callback,
            )
        except Exception as exc:  # noqa: BLE001
            run_error = str(exc)

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

    def build_clarification_reply(self, decision: RouterDecision) -> str:
        question = decision.clarificationQuestion.strip()
        if question:
            return question
        missing_inputs = decision.missingInputs
        if missing_inputs == ["documentNo"]:
            return "请提供单据编号，我再帮你查询当前状态。"
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
        if (
            decision.route == "tool_first"
            and not decision.requires_clarification
            and decision.confidence < self.TOOL_FIRST_CONFIDENCE_THRESHOLD
        ):
            return False, "Router confidence below tool_first threshold."

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

        for tool_call in decision.toolCalls:
            if self._tool_registry.get_tool(tool_call.name) is None:
                return False, f"Router selected unregistered tool: {tool_call.name}"
        return True, ""

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
        router_result = run_router_exec(
            config=self._provider_config,
            prompt=router_prompt,
            workspace_dir=workspace_dir,
            output_schema=router_decision_json_schema(),
            cancel_event=cancel_event,
            runtime_dir=self._runtime_dir,
        )
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
            run_state.status = "running"
            cancel_event = run_state.cancel_event

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

        if self._router_enabled:
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
            "routerEnabled": self._router_enabled,
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
            "routerEnabled": self._router_enabled,
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
