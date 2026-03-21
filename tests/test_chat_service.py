from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict

from automation.chat.codex_runner import CodexExecutionResult, RouterExecutionResult
from automation.chat.provider_config import ChatProviderConfig
from automation.chat.service import ChatService, _SessionRunState
from automation.chat.skill_loader import SkillLoader
from automation.chat.tool_registry import ToolDefinition, ToolRegistry
from automation.utils.config_loader import (
    AISettings,
    AppSettings,
    AuthSettings,
    BrowserSettings,
    DatabaseSettings,
    RuntimeSettings,
    Settings,
)


class _EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass
class _FakeThread:
    name: str = "fake-thread"


class _FakeChatStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, dict[str, Any]] = {}
        self.logs: list[dict[str, Any]] = []

    def ensure_table(self) -> None:
        return None

    def create_session(
        self,
        *,
        session_id: str,
        title: str,
        workspace_dir: str,
        model_provider: str,
        model_name: str,
        status: str = "idle",
    ) -> dict[str, Any]:
        session = {
            "sessionId": session_id,
            "title": title,
            "workspaceDir": workspace_dir,
            "modelProvider": model_provider,
            "modelName": model_name,
            "status": status,
            "createdAt": "2026-03-21 10:00:00",
            "lastActiveAt": "2026-03-21 10:00:00",
        }
        self.sessions[session_id] = session
        return session

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        rows = list(self.sessions.values())
        return rows[offset : offset + limit]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        return self.sessions.get(session_id)

    def update_session_status(self, *, session_id: str, status: str) -> None:
        self.sessions[session_id]["status"] = status

    def touch_session(self, *, session_id: str) -> None:
        self.sessions[session_id]["lastActiveAt"] = "2026-03-21 10:00:01"

    def create_message(
        self,
        *,
        message_id: str,
        session_id: str,
        role: str,
        content: str,
        token_count: int | None = None,
    ) -> dict[str, Any]:
        message = {
            "messageId": message_id,
            "sessionId": session_id,
            "role": role,
            "content": content,
            "tokenCount": token_count,
            "createdAt": f"2026-03-21 10:00:{len(self.messages):02d}",
        }
        self.messages[message_id] = message
        return message

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        return self.messages.get(message_id)

    def update_message_content(self, *, message_id: str, content: str, token_count: int | None) -> None:
        self.messages[message_id]["content"] = content
        self.messages[message_id]["tokenCount"] = token_count

    def list_messages(self, *, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = [item for item in self.messages.values() if item["sessionId"] == session_id]
        rows.sort(key=lambda item: item["createdAt"])
        return rows[:limit]

    def append_execution_log(
        self,
        *,
        log_id: str,
        session_id: str,
        message_id: str | None,
        event_type: str,
        event_summary: str,
        exit_code: int | None = None,
    ) -> None:
        self.logs.append(
            {
                "logId": log_id,
                "sessionId": session_id,
                "messageId": message_id,
                "eventType": event_type,
                "eventSummary": event_summary,
                "exitCode": exit_code,
            }
        )


def _build_settings() -> Settings:
    return Settings(
        app=AppSettings(base_url="https://example.com", home_path="/"),
        auth=AuthSettings(username="", password="", require_manual_captcha=False),
        browser=BrowserSettings(
            headed=False,
            slow_mo_ms=0,
            timeout_ms=1000,
            navigation_timeout_ms=1000,
            ignore_https_errors=True,
        ),
        runtime=RuntimeSettings(
            state_file="state.json",
            logs_dir="logs",
            screenshots_dir="screenshots",
            downloads_dir="downloads",
            retries=1,
            retry_wait_sec=1.0,
        ),
        db=DatabaseSettings(
            host="127.0.0.1",
            port=5432,
            dbname="ierp",
            user="postgres",
            password="password",
            schema="public",
            sslmode="prefer",
        ),
        ai=AISettings(
            provider="openai_compatible",
            base_url="https://api.example.com/v1",
            model="gpt-test",
            timeout_seconds=60,
            max_output_tokens=1024,
            api_key_env="CLAWCHECK_AI_API_KEY",
            api_key="test-key",
        ),
    )


def _build_provider_config() -> ChatProviderConfig:
    return ChatProviderConfig(
        provider="openai_compatible",
        base_url="https://api.example.com/v1",
        model="gpt-test",
        timeout_seconds=60,
        max_output_tokens=1024,
        api_key_env="CLAWCHECK_AI_API_KEY",
        api_key="test-key",
        codex_cli_executable="codex",
        workspace_dir=Path.cwd(),
    )


def _build_skill_loader(tmp_path: Path) -> SkillLoader:
    skill_dir = tmp_path / "skills" / "clawcheck-project"
    reference_dir = skill_dir / "references"
    reference_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: clawcheck-project\n"
        "description: test skill\n"
        "status: active\n"
        "references:\n"
        "  - process-workbench\n"
        "  - answer-policy\n"
        "---\n\n"
        "test skill body\n",
        encoding="utf-8",
    )
    (reference_dir / "process-workbench.md").write_text("process ref", encoding="utf-8")
    (reference_dir / "answer-policy.md").write_text("answer policy", encoding="utf-8")
    return SkillLoader(
        root_dir=tmp_path / "skills",
        runtime_snapshot_path=tmp_path / "runtime" / "skill-index.json",
    )


def _attach_active_run(service: ChatService, *, session_id: str, user_message_id: str, assistant_message_id: str) -> None:
    service._runs_by_session[session_id] = _SessionRunState(
        run_id="run-1",
        session_id=session_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        cancel_event=threading.Event(),
        thread=_FakeThread(),  # type: ignore[arg-type]
        status="queued",
    )


def test_execute_turn_uses_process_workbench_templated_reply_for_pending_count_query(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )
    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content="单据处理模块有多少条待办",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    tool_registry = ToolRegistry(
        {
            "get_process_workbench": ToolDefinition(
                name="get_process_workbench",
                description="test",
                arguments_model=_EmptyArgs,
                resolver=lambda _: {"stats": [{"label": "待处理单据", "value": "7"}], "documents": []},
                source_of_truth="GET /api/documents/process-workbench",
            )
        }
    )
    service = ChatService(
        _build_settings(),
        store=fake_store,  # type: ignore[arg-type]
        provider_config=_build_provider_config(),
        skill_loader=_build_skill_loader(tmp_path),
        tool_registry=tool_registry,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with (
        patch(
            "automation.chat.service.run_router_exec",
            return_value=RouterExecutionResult(
                status="succeeded",
                decision={
                    "route": "tool_first",
                    "selectedSkills": ["clawcheck-project"],
                    "selectedReferences": ["process-workbench", "answer-policy"],
                    "toolCalls": [{"name": "get_process_workbench", "arguments": {}}],
                    "answerMode": "templated",
                    "confidence": 0.96,
                    "missingInputs": [],
                    "clarificationQuestion": "",
                    "reason": "pending count query",
                },
                exit_code=0,
                raw_output="{}",
                error_message="",
            ),
        ),
        patch("automation.chat.service.run_codex_exec", side_effect=AssertionError("templated reply should not call main model")),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert "当前待处理单据为 7 条" in fake_store.messages["a1"]["content"]
    assert fake_store.messages["a1"]["tokenCount"] is not None


def test_execute_turn_returns_clarification_without_tool_execution_when_document_number_missing(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )
    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content="这张单据现在什么状态",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    execute_calls: list[str] = []
    tool_registry = ToolRegistry(
        {
            "get_process_document_detail": ToolDefinition(
                name="get_process_document_detail",
                description="test",
                arguments_model=_EmptyArgs,
                resolver=lambda _: execute_calls.append("called"),
                source_of_truth="GET /api/documents/process-workbench/{document_no}",
            )
        }
    )
    service = ChatService(
        _build_settings(),
        store=fake_store,  # type: ignore[arg-type]
        provider_config=_build_provider_config(),
        skill_loader=_build_skill_loader(tmp_path),
        tool_registry=tool_registry,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with patch(
        "automation.chat.service.run_router_exec",
        return_value=RouterExecutionResult(
            status="succeeded",
            decision={
                "route": "direct_answer",
                "selectedSkills": ["clawcheck-project"],
                "selectedReferences": ["answer-policy"],
                "toolCalls": [],
                "answerMode": "model_generated",
                "confidence": 0.9,
                "missingInputs": ["documentNo"],
                "clarificationQuestion": "请提供单据编号，我再帮你查询当前状态。",
                "reason": "missing document number",
            },
            exit_code=0,
            raw_output="{}",
            error_message="",
        ),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert fake_store.messages["a1"]["content"] == "请提供单据编号，我再帮你查询当前状态。"
    assert execute_calls == []


def test_execute_turn_accepts_tool_first_clarification_without_tool_calls(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )
    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content="What is the current status of this document?",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    execute_calls: list[str] = []
    tool_registry = ToolRegistry(
        {
            "get_process_document_detail": ToolDefinition(
                name="get_process_document_detail",
                description="test",
                arguments_model=_EmptyArgs,
                resolver=lambda _: execute_calls.append("called"),
                source_of_truth="GET /api/documents/process-workbench/{document_no}",
            )
        }
    )
    service = ChatService(
        _build_settings(),
        store=fake_store,  # type: ignore[arg-type]
        provider_config=_build_provider_config(),
        skill_loader=_build_skill_loader(tmp_path),
        tool_registry=tool_registry,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with patch(
        "automation.chat.service.run_router_exec",
        return_value=RouterExecutionResult(
            status="succeeded",
            decision={
                "route": "tool_first",
                "selectedSkills": ["clawcheck-project"],
                "selectedReferences": ["answer-policy"],
                "toolCalls": [],
                "answerMode": "templated",
                "confidence": 0.42,
                "missingInputs": ["documentNo"],
                "clarificationQuestion": "Please provide the document number first.",
                "reason": "missing document number",
            },
            exit_code=0,
            raw_output="{}",
            error_message="",
        ),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert fake_store.messages["a1"]["content"] == "Please provide the document number first."
    assert execute_calls == []


def test_execute_turn_falls_back_to_general_chat_when_router_fails(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )
    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content="介绍一下本项目",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    service = ChatService(
        _build_settings(),
        store=fake_store,  # type: ignore[arg-type]
        provider_config=_build_provider_config(),
        skill_loader=_build_skill_loader(tmp_path),
        tool_registry=ToolRegistry({}),
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with (
        patch(
            "automation.chat.service.run_router_exec",
            return_value=RouterExecutionResult(
                status="failed",
                decision=None,
                exit_code=1,
                raw_output="",
                error_message="router failed",
            ),
        ),
        patch(
            "automation.chat.service.run_codex_exec",
            return_value=CodexExecutionResult(
                status="succeeded",
                final_text="这是 clawcheck 项目的通用介绍。",
                exit_code=0,
                output_tail="ok",
                usage={"output_tokens": 10},
            ),
        ),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert fake_store.messages["a1"]["content"] == "这是 clawcheck 项目的通用介绍。"
