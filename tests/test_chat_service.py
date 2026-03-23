from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import threading
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict

from automation.chat.approval_models import ApprovalRequest
from automation.chat.approval_plan_store import ApprovalPlanStore
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


class _DocumentDetailArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentNo: str
    assessmentBatchNo: str = ""


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
        "  - process-approval\n"
        "  - answer-policy\n"
        "---\n\n"
        "test skill body\n",
        encoding="utf-8",
    )
    (reference_dir / "process-workbench.md").write_text("process ref", encoding="utf-8")
    (reference_dir / "process-approval.md").write_text("approval ref", encoding="utf-8")
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


def _build_process_document_detail(
    *,
    document_no: str = "RA-20260310-00019845",
    todo_status: str = "待处理",
    document_status: str = "审批中",
) -> dict[str, Any]:
    return {
        "documentNo": document_no,
        "overviewFields": [
            {"label": "单据编号", "value": document_no},
            {"label": "单据状态", "value": document_status},
            {"label": "待办处理状态", "value": todo_status},
            {"label": "评估批次号", "value": "audit_20260322_103000"},
        ],
        "feedbackOverview": {
            "summaryConclusionLabel": "加强审核",
            "feedbackGroups": [
                {"summaryLines": ["缺战区人行审批", "建议拒绝或补齐审批链"]},
                {"summary": "组织范围扩大，需补充授权依据"},
            ],
        },
        "notes": [],
    }


def _build_process_workbench_payload(
    *,
    pending_document_nos: list[str],
    processed_document_nos: list[str] | None = None,
) -> dict[str, Any]:
    processed_document_nos = processed_document_nos or []
    documents: list[dict[str, Any]] = [
        {"documentNo": document_no, "todoProcessStatus": "\u5f85\u5904\u7406"}
        for document_no in pending_document_nos
    ]
    documents.extend(
        {"documentNo": document_no, "todoProcessStatus": "\u5df2\u5904\u7406"}
        for document_no in processed_document_nos
    )
    return {
        "stats": [{"label": "\u5f85\u5904\u7406\u5355\u636e", "value": str(len(pending_document_nos))}],
        "documents": documents,
    }


def test_execute_turn_uses_fast_path_for_pending_document_list_without_model_calls(tmp_path: Path) -> None:
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
        content="列出全部的待处理单据编号，不要只给数量",
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
                resolver=lambda _: _build_process_workbench_payload(
                    pending_document_nos=["RA-20260310-00019862", "RA-20260316-00020025"],
                    processed_document_nos=["RA-20260317-00020118"],
                ),
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

    with patch("automation.chat.service.run_router_exec", side_effect=AssertionError("fast path should skip router")), patch(
        "automation.chat.service.run_codex_exec",
        side_effect=AssertionError("fast path should skip answer model"),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    content = fake_store.messages["a1"]["content"]
    assert "RA-20260310-00019862" in content
    assert "RA-20260316-00020025" in content
    assert "RA-20260317-00020118" not in content
    assert any(log["eventType"] == "fast_path_hit" for log in fake_store.logs)


def test_execute_turn_uses_fast_path_for_document_status_query_without_model_calls(tmp_path: Path) -> None:
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
        content="RA-20260310-00019862 当前状态是什么",
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
            "get_process_document_detail": ToolDefinition(
                name="get_process_document_detail",
                description="test",
                arguments_model=_DocumentDetailArgs,
                resolver=lambda _: _build_process_document_detail(document_no="RA-20260310-00019862"),
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

    with patch("automation.chat.service.run_router_exec", side_effect=AssertionError("fast path should skip router")), patch(
        "automation.chat.service.run_codex_exec",
        side_effect=AssertionError("fast path should skip answer model"),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    content = fake_store.messages["a1"]["content"]
    assert "RA-20260310-00019862" in content
    assert any(log["eventType"] == "fast_path_hit" for log in fake_store.logs)


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


def test_execute_turn_returns_all_pending_document_numbers_for_list_query_even_when_pending_not_in_first_ten(
    tmp_path: Path,
) -> None:
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
        content="列出全部待处理单据的全部编号，不要只给数量",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    documents: list[dict[str, Any]] = []
    for index in range(10):
        documents.append(
            {
                "documentNo": f"RA-20260301-00010{index}",
                "todoProcessStatus": "已处理",
            }
        )
    documents.append({"documentNo": "RA-20260320-00020275", "todoProcessStatus": "待处理"})
    documents.append({"documentNo": "RA-20260319-00020251", "todoProcessStatus": "待处理"})
    tool_registry = ToolRegistry(
        {
            "get_process_workbench": ToolDefinition(
                name="get_process_workbench",
                description="test",
                arguments_model=_EmptyArgs,
                resolver=lambda _: {"stats": [{"label": "待处理单据", "value": "2"}], "documents": documents},
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
                    "reason": "pending list query",
                    "requiresPendingDocumentList": True,
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

    content = fake_store.messages["a1"]["content"]
    assert "RA-20260320-00020275" in content
    assert "RA-20260319-00020251" in content
    assert "RA-20260301-000100" not in content


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
    with patch.dict(os.environ, {"CLAWCHECK_CHAT_FAST_PATH_ENABLED": "false"}, clear=False):
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


def test_execute_turn_falls_back_to_general_chat_when_pending_list_directive_is_invalid(tmp_path: Path) -> None:
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
        content="列出全部待处理单据编号",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    with patch.dict(os.environ, {"CLAWCHECK_CHAT_FAST_PATH_ENABLED": "false"}, clear=False):
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
                status="succeeded",
                decision={
                    "route": "direct_answer",
                    "selectedSkills": ["clawcheck-project"],
                    "selectedReferences": ["process-workbench", "answer-policy"],
                    "toolCalls": [],
                    "answerMode": "model_generated",
                    "confidence": 0.93,
                    "missingInputs": [],
                    "clarificationQuestion": "",
                    "reason": "invalid pending list directive",
                    "requiresPendingDocumentList": True,
                },
                exit_code=0,
                raw_output="{}",
                error_message="",
            ),
        ),
        patch(
            "automation.chat.service.run_codex_exec",
            return_value=CodexExecutionResult(
                status="succeeded",
                final_text="通用回退已生效。",
                exit_code=0,
                output_tail="ok",
                usage={"output_tokens": 6},
            ),
        ),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert fake_store.messages["a1"]["content"] == "通用回退已生效。"


def test_execute_turn_creates_approval_plan_for_approve_request(tmp_path: Path) -> None:
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
        content="帮我批准单据 RA-20260310-00019845，审批意见：同意，按当前职责范围处理。",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )

    with patch.dict(
        os.environ,
        {
            "CLAWCHECK_CHAT_APPROVAL_ENABLED": "true",
            "CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY": "true",
            "CLAWCHECK_CHAT_APPROVAL_PLAN_TTL_SECONDS": "600",
        },
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )
    service._approval_plan_store = ApprovalPlanStore(tmp_path / "runtime" / "chat" / "approval-plans")
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
                "route": "approval_prepare",
                "selectedSkills": ["clawcheck-project"],
                "selectedReferences": ["process-approval"],
                "toolCalls": [],
                "answerMode": "templated",
                "confidence": 0.95,
                "missingInputs": [],
                "clarificationQuestion": "",
                "reason": "approval intent",
                "approvalRequest": {
                    "documentNo": "RA-20260310-00019845",
                    "action": "approve",
                    "approvalOpinion": "同意，按当前职责范围处理。",
                    "dryRun": False,
                },
            },
            exit_code=0,
            raw_output="{}",
            error_message="",
        ),
    ), patch(
        "automation.chat.service.get_process_document_detail",
        return_value=_build_process_document_detail(),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    content = fake_store.messages["a1"]["content"]
    assert "已生成待确认审批计划 approval-plan-" in content
    assert "确认命令：确认审批计划 approval-plan-" in content
    assert "验证命令：验证审批计划 approval-plan-" in content
    plan_files = list((tmp_path / "runtime" / "chat" / "approval-plans").glob("s1_approval-plan-*.json"))
    assert len(plan_files) == 1


def test_execute_turn_auto_adds_process_approval_reference_for_approval_prepare(tmp_path: Path) -> None:
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
        content="请批准单据 RA-20260310-00019845，意见：同意",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )

    with patch.dict(
        os.environ,
        {
            "CLAWCHECK_CHAT_APPROVAL_ENABLED": "true",
            "CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY": "true",
            "CLAWCHECK_CHAT_APPROVAL_PLAN_TTL_SECONDS": "600",
        },
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )
    service._approval_plan_store = ApprovalPlanStore(tmp_path / "runtime" / "chat" / "approval-plans")
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
                "route": "approval_prepare",
                "selectedSkills": ["clawcheck-project"],
                "selectedReferences": ["answer-policy"],
                "toolCalls": [],
                "answerMode": "templated",
                "confidence": 0.95,
                "missingInputs": [],
                "clarificationQuestion": "",
                "reason": "approval intent",
                "approvalRequest": {
                    "documentNo": "RA-20260310-00019845",
                    "action": "approve",
                    "approvalOpinion": "同意",
                    "dryRun": False,
                },
            },
            exit_code=0,
            raw_output="{}",
            error_message="",
        ),
    ), patch(
        "automation.chat.service.get_process_document_detail",
        return_value=_build_process_document_detail(),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    content = fake_store.messages["a1"]["content"]
    assert "已生成待确认审批计划 approval-plan-" in content
    assert any(
        "process-approval reference; auto-added reference" in log["eventSummary"]
        for log in fake_store.logs
        if log["eventType"] == "router_decision_normalized"
    )


def test_execute_turn_returns_operable_hint_when_chat_approval_disabled(tmp_path: Path) -> None:
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
        content="请批准单据 RA-20260310-00019845，意见：同意",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )

    with patch.dict(os.environ, {"CLAWCHECK_CHAT_APPROVAL_ENABLED": "false"}, clear=False):
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

    with patch(
        "automation.chat.service.run_router_exec",
        return_value=RouterExecutionResult(
            status="succeeded",
            decision={
                "route": "approval_prepare",
                "selectedSkills": ["clawcheck-project"],
                "selectedReferences": ["process-approval"],
                "toolCalls": [],
                "answerMode": "templated",
                "confidence": 0.95,
                "missingInputs": [],
                "clarificationQuestion": "",
                "reason": "approval intent",
                "approvalRequest": {
                    "documentNo": "RA-20260310-00019845",
                    "action": "approve",
                    "approvalOpinion": "同意",
                    "dryRun": False,
                },
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

    content = fake_store.messages["a1"]["content"]
    assert "CLAWCHECK_CHAT_APPROVAL_ENABLED=true" in content
    assert "CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY=true" in content
    assert "false" in content


def test_execute_turn_generates_suggested_reject_plan_without_direct_submit(tmp_path: Path) -> None:
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
        content="帮我驳回单据 RA-20260310-00019845",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )

    with patch.dict(
        os.environ,
        {"CLAWCHECK_CHAT_APPROVAL_ENABLED": "true"},
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )
    service._approval_plan_store = ApprovalPlanStore(tmp_path / "runtime" / "chat" / "approval-plans")
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
                "route": "approval_prepare",
                "selectedSkills": ["clawcheck-project"],
                "selectedReferences": ["process-approval"],
                "toolCalls": [],
                "answerMode": "templated",
                "confidence": 0.95,
                "missingInputs": [],
                "clarificationQuestion": "",
                "reason": "reject intent",
                "approvalRequest": {
                    "documentNo": "RA-20260310-00019845",
                    "action": "reject",
                    "approvalOpinion": "",
                    "dryRun": False,
                },
            },
            exit_code=0,
            raw_output="{}",
            error_message="",
        ),
    ), patch(
        "automation.chat.service.get_process_document_detail",
        return_value=_build_process_document_detail(),
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert "当前审批意见为系统建议稿，不能直接真实提交。" in fake_store.messages["a1"]["content"]
    assert "缺战区人行审批" in fake_store.messages["a1"]["content"]


def test_execute_turn_verify_command_executes_dry_run_on_pending_plan(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )

    with patch.dict(
        os.environ,
        {"CLAWCHECK_CHAT_APPROVAL_ENABLED": "true"},
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )
    service._approval_plan_store = ApprovalPlanStore(tmp_path / "runtime" / "chat" / "approval-plans")

    plan = service._create_approval_plan(
        session_id="s1",
        request=ApprovalRequest(
            documentNo="RA-20260310-00019845",
            action="approve",
            approvalOpinion="同意，按当前职责范围处理。",
            dryRun=False,
        ),
        approval_opinion="同意，按当前职责范围处理。",
        approval_opinion_source="user_input",
        document_detail=_build_process_document_detail(),
    )
    service._approval_plan_store.save_plan(plan)

    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content=f"验证审批计划 {plan.planId}",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with patch(
        "automation.chat.service.get_process_document_detail",
        return_value=_build_process_document_detail(),
    ), patch(
        "automation.chat.service.approve_process_document",
        return_value={
            "documentNo": plan.documentNo,
            "action": "approve",
            "approvalOpinion": plan.approvalOpinion,
            "dryRun": True,
            "status": "succeeded",
            "confirmationType": "dry_run",
            "message": "dry run ok",
            "logFile": "automation/logs/approval.json",
            "screenshotFile": "",
        },
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert "dry-run：是" in fake_store.messages["a1"]["content"]
    saved_plan = service._approval_plan_store.get_plan("s1", plan.planId)
    assert saved_plan is not None
    assert saved_plan.status == "dry_run_succeeded"


def test_execute_turn_verify_short_phrase_uses_single_pending_plan(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )

    with patch.dict(
        os.environ,
        {"CLAWCHECK_CHAT_APPROVAL_ENABLED": "true"},
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )
    service._approval_plan_store = ApprovalPlanStore(tmp_path / "runtime" / "chat" / "approval-plans")

    plan = service._create_approval_plan(
        session_id="s1",
        request=ApprovalRequest(
            documentNo="RA-20260310-00019845",
            action="approve",
            approvalOpinion="同意",
            dryRun=False,
        ),
        approval_opinion="同意",
        approval_opinion_source="user_input",
        document_detail=_build_process_document_detail(),
    )
    service._approval_plan_store.save_plan(plan)

    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content="请先验证",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with patch(
        "automation.chat.service.get_process_document_detail",
        return_value=_build_process_document_detail(),
    ), patch(
        "automation.chat.service.approve_process_document",
        return_value={
            "documentNo": plan.documentNo,
            "action": "approve",
            "approvalOpinion": plan.approvalOpinion,
            "dryRun": True,
            "status": "succeeded",
            "confirmationType": "dry_run",
            "message": "dry run ok",
            "logFile": "automation/logs/approval.json",
            "screenshotFile": "",
        },
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert "dry-run" in fake_store.messages["a1"]["content"]
    saved_plan = service._approval_plan_store.get_plan("s1", plan.planId)
    assert saved_plan is not None
    assert saved_plan.status == "dry_run_succeeded"


def test_execute_turn_confirm_command_with_label_prefix_is_supported(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )

    with patch.dict(
        os.environ,
        {
            "CLAWCHECK_CHAT_APPROVAL_ENABLED": "true",
            "CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY": "false",
        },
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )
    service._approval_plan_store = ApprovalPlanStore(tmp_path / "runtime" / "chat" / "approval-plans")

    plan = service._create_approval_plan(
        session_id="s1",
        request=ApprovalRequest(
            documentNo="RA-20260310-00019845",
            action="approve",
            approvalOpinion="同意",
            dryRun=False,
        ),
        approval_opinion="同意",
        approval_opinion_source="user_input",
        document_detail=_build_process_document_detail(),
    )
    service._approval_plan_store.save_plan(plan)

    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content=f"确认命令：确认审批计划 {plan.planId}",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with patch(
        "automation.chat.service.get_process_document_detail",
        return_value=_build_process_document_detail(),
    ), patch(
        "automation.chat.service.approve_process_document",
        return_value={
            "documentNo": plan.documentNo,
            "action": "approve",
            "approvalOpinion": plan.approvalOpinion,
            "dryRun": False,
            "status": "succeeded",
            "confirmationType": "submitted",
            "message": "submit ok",
            "logFile": "automation/logs/approval_submit.json",
            "screenshotFile": "",
        },
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert "dry-run" in fake_store.messages["a1"]["content"]
    saved_plan = service._approval_plan_store.get_plan("s1", plan.planId)
    assert saved_plan is not None
    assert saved_plan.status == "submitted"


def test_execute_turn_verify_short_phrase_with_multiple_pending_plans_requires_plan_id(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )

    with patch.dict(
        os.environ,
        {"CLAWCHECK_CHAT_APPROVAL_ENABLED": "true"},
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )
    service._approval_plan_store = ApprovalPlanStore(tmp_path / "runtime" / "chat" / "approval-plans")

    for idx in range(2):
        plan = service._create_approval_plan(
            session_id="s1",
            request=ApprovalRequest(
                documentNo=f"RA-20260310-0001984{idx}",
                action="approve",
                approvalOpinion="同意",
                dryRun=False,
            ),
            approval_opinion="同意",
            approval_opinion_source="user_input",
            document_detail=_build_process_document_detail(document_no=f"RA-20260310-0001984{idx}"),
        )
        service._approval_plan_store.save_plan(plan)

    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content="请先验证",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with patch("automation.chat.service.approve_process_document") as mocked_approve:
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert "多个待确认审批计划" in fake_store.messages["a1"]["content"]
    mocked_approve.assert_not_called()


def test_execute_turn_blocks_confirm_for_suggested_plan(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )

    with patch.dict(
        os.environ,
        {
            "CLAWCHECK_CHAT_APPROVAL_ENABLED": "true",
            "CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY": "false",
        },
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )
    service._approval_plan_store = ApprovalPlanStore(tmp_path / "runtime" / "chat" / "approval-plans")

    plan = service._create_approval_plan(
        session_id="s1",
        request=ApprovalRequest(documentNo="RA-20260310-00019845", action="reject", approvalOpinion="", dryRun=False),
        approval_opinion="缺战区人行审批\n建议拒绝或补齐审批链",
        approval_opinion_source="suggested_from_109",
        document_detail=_build_process_document_detail(),
    )
    service._approval_plan_store.save_plan(plan)

    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content=f"确认审批计划 {plan.planId}",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with patch("automation.chat.service.approve_process_document") as mocked_approve:
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert "当前审批意见仍是系统建议稿" in fake_store.messages["a1"]["content"]
    mocked_approve.assert_not_called()


def test_execute_turn_confirm_command_executes_real_submit_when_allowed(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    fake_store.create_session(
        session_id="s1",
        title="Test",
        workspace_dir=str(Path.cwd()),
        model_provider="openai_compatible",
        model_name="gpt-test",
    )

    with patch.dict(
        os.environ,
        {
            "CLAWCHECK_CHAT_APPROVAL_ENABLED": "true",
            "CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY": "false",
        },
        clear=False,
    ):
        service = ChatService(
            _build_settings(),
            store=fake_store,  # type: ignore[arg-type]
            provider_config=_build_provider_config(),
            skill_loader=_build_skill_loader(tmp_path),
            tool_registry=ToolRegistry({}),
        )

    plan = service._create_approval_plan(
        session_id="s1",
        request=ApprovalRequest(
            documentNo="RA-20260310-00019845",
            action="approve",
            approvalOpinion="同意，按当前职责范围处理。",
            dryRun=False,
        ),
        approval_opinion="同意，按当前职责范围处理。",
        approval_opinion_source="user_input",
        document_detail=_build_process_document_detail(),
    )
    service._approval_plan_store.save_plan(plan)

    user_message = fake_store.create_message(
        message_id="u1",
        session_id="s1",
        role="user",
        content=f"确认审批计划 {plan.planId}",
        token_count=1,
    )
    assistant_message = fake_store.create_message(
        message_id="a1",
        session_id="s1",
        role="assistant",
        content="",
        token_count=0,
    )
    _attach_active_run(
        service,
        session_id="s1",
        user_message_id=user_message["messageId"],
        assistant_message_id=assistant_message["messageId"],
    )

    with patch(
        "automation.chat.service.get_process_document_detail",
        return_value=_build_process_document_detail(),
    ), patch(
        "automation.chat.service.approve_process_document",
        return_value={
            "documentNo": plan.documentNo,
            "action": "approve",
            "approvalOpinion": plan.approvalOpinion,
            "dryRun": False,
            "status": "succeeded",
            "confirmationType": "submitted",
            "message": "submit ok",
            "logFile": "automation/logs/approval_submit.json",
            "screenshotFile": "",
        },
    ):
        service._execute_turn(
            run_id="run-1",
            session_id="s1",
            user_message_id=user_message["messageId"],
            assistant_message_id=assistant_message["messageId"],
        )

    assert "dry-run：否" in fake_store.messages["a1"]["content"]
    saved_plan = service._approval_plan_store.get_plan("s1", plan.planId)
    assert saved_plan is not None
    assert saved_plan.status == "submitted"


def test_run_model_prompt_app_server_auto_fallback_to_oneshot(tmp_path: Path) -> None:
    fake_store = _FakeChatStore()
    provider_config = ChatProviderConfig(
        provider="openai_compatible",
        base_url="https://api.example.com/v1",
        model="gpt-test",
        timeout_seconds=60,
        max_output_tokens=1024,
        api_key_env="CLAWCHECK_AI_API_KEY",
        api_key="test-key",
        codex_cli_executable="codex",
        workspace_dir=Path.cwd(),
        exec_mode="app_server",
        app_server_base_url="http://127.0.0.1:9999",
        app_server_timeout_seconds=30,
        exec_auto_fallback=True,
    )
    service = ChatService(
        _build_settings(),
        store=fake_store,  # type: ignore[arg-type]
        provider_config=provider_config,
        skill_loader=_build_skill_loader(tmp_path),
        tool_registry=ToolRegistry({}),
    )

    with patch.object(service._execution_adapter, "run_answer", side_effect=RuntimeError("app-server down")), patch(
        "automation.chat.service.run_codex_exec",
        return_value=CodexExecutionResult(
            status="succeeded",
            final_text="fallback answer",
            exit_code=0,
            output_tail="fallback ok",
            usage={"output_tokens": 3},
        ),
    ):
        outcome = service._run_model_prompt(
            session_id="s1",
            run_id="run-1",
            assistant_message_id="a1",
            prompt="test prompt",
            workspace_dir=Path.cwd(),
            cancel_event=threading.Event(),
        )

    assert outcome.status == "succeeded"
    assert outcome.assistant_text == "fallback answer"
    assert any(log["eventType"] == "backend_auto_fallback" for log in fake_store.logs)
