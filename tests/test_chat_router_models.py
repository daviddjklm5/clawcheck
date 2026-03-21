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
