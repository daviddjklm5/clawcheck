from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RouterToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    argumentsJson: str = "{}"

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_arguments(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "argumentsJson" in value or "arguments" not in value:
            return value
        normalized = dict(value)
        normalized["argumentsJson"] = json.dumps(normalized.pop("arguments") or {}, ensure_ascii=False)
        return normalized

    @field_validator("argumentsJson")
    @classmethod
    def _validate_arguments_json(cls, value: str) -> str:
        text = (value or "").strip() or "{}"
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("argumentsJson must be valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("argumentsJson must decode to a JSON object.")
        return text

    @property
    def arguments(self) -> dict[str, Any]:
        parsed = json.loads(self.argumentsJson)
        return parsed if isinstance(parsed, dict) else {}


class RouterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Literal["tool_first", "direct_answer", "general_chat"]
    selectedSkills: list[str] = Field(default_factory=list)
    selectedReferences: list[str] = Field(default_factory=list)
    toolCalls: list[RouterToolCall] = Field(default_factory=list)
    answerMode: Literal["templated", "model_generated"] = "model_generated"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    missingInputs: list[str] = Field(default_factory=list)
    clarificationQuestion: str = ""
    reason: str = ""

    @property
    def requires_clarification(self) -> bool:
        return bool(self.missingInputs)


def _normalize_response_format_schema(node: Any) -> Any:
    if isinstance(node, dict):
        normalized = {key: _normalize_response_format_schema(value) for key, value in node.items()}
        if normalized.get("type") == "object":
            properties = normalized.get("properties")
            if isinstance(properties, dict):
                normalized["required"] = list(properties.keys())
                normalized["additionalProperties"] = False
        return normalized
    if isinstance(node, list):
        return [_normalize_response_format_schema(item) for item in node]
    return node


def router_decision_json_schema() -> dict[str, Any]:
    return _normalize_response_format_schema(RouterDecision.model_json_schema())
