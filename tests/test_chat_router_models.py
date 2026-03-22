from __future__ import annotations

from pydantic import ValidationError
import pytest

from automation.chat.router_models import RouterDecision, router_decision_json_schema


def test_router_tool_call_accepts_legacy_arguments_payload() -> None:
    decision = RouterDecision.model_validate(
        {
            "route": "tool_first",
            "selectedSkills": ["clawcheck-project"],
            "selectedReferences": ["process-workbench"],
            "toolCalls": [{"name": "get_process_document_detail", "arguments": {"documentNo": "RA-1"}}],
            "answerMode": "templated",
            "confidence": 0.95,
            "missingInputs": [],
            "clarificationQuestion": "",
            "reason": "test",
        }
    )

    assert decision.toolCalls[0].arguments == {"documentNo": "RA-1"}
    assert decision.toolCalls[0].argumentsJson == '{"documentNo": "RA-1"}'
    assert decision.requiresPendingDocumentList is False


def test_router_decision_supports_pending_document_list_directive() -> None:
    decision = RouterDecision.model_validate(
        {
            "route": "tool_first",
            "selectedSkills": ["clawcheck-project"],
            "selectedReferences": ["process-workbench"],
            "toolCalls": [{"name": "get_process_workbench", "argumentsJson": "{}"}],
            "answerMode": "templated",
            "confidence": 0.98,
            "missingInputs": [],
            "clarificationQuestion": "",
            "reason": "list pending document numbers",
            "requiresPendingDocumentList": True,
            "approvalRequest": None,
        }
    )

    assert decision.requiresPendingDocumentList is True


def test_router_schema_is_strictly_compatible_with_response_format() -> None:
    schema = router_decision_json_schema()
    tool_call_schema = schema["$defs"]["RouterToolCall"]
    root_required = set(schema["required"])
    tool_call_required = set(tool_call_schema["required"])

    assert schema["additionalProperties"] is False
    assert tool_call_schema["additionalProperties"] is False
    assert "argumentsJson" in tool_call_schema["properties"]
    assert "arguments" not in tool_call_schema["properties"]
    assert root_required == set(schema["properties"].keys())
    assert tool_call_required == set(tool_call_schema["properties"].keys())


def test_router_tool_call_rejects_non_object_arguments_json() -> None:
    with pytest.raises(ValidationError):
        RouterDecision.model_validate(
            {
                "route": "tool_first",
                "selectedSkills": [],
                "selectedReferences": [],
                "toolCalls": [{"name": "get_process_workbench", "argumentsJson": '["bad"]'}],
                "answerMode": "templated",
                "confidence": 0.95,
                "missingInputs": [],
                "clarificationQuestion": "",
                "reason": "test",
            }
        )


def test_router_decision_accepts_approval_prepare_payload() -> None:
    decision = RouterDecision.model_validate(
        {
            "route": "approval_prepare",
            "selectedSkills": ["clawcheck-project"],
            "selectedReferences": ["process-approval"],
            "toolCalls": [],
            "answerMode": "templated",
            "confidence": 0.93,
            "missingInputs": [],
            "clarificationQuestion": "",
            "reason": "approval intent",
            "approvalRequest": {
                "documentNo": "RA-20260310-00019845",
                "action": "approve",
                "approvalOpinion": "同意，按当前职责范围处理。",
                "dryRun": False,
            },
        }
    )

    assert decision.route == "approval_prepare"
    assert decision.approvalRequest is not None
    assert decision.approvalRequest.documentNo == "RA-20260310-00019845"
    assert decision.approvalRequest.action == "approve"
