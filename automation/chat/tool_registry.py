from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from automation.api.collect_workbench import get_collect_workbench
from automation.api.process_dashboard import get_process_document_detail, get_process_workbench


class EmptyToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProcessDocumentDetailArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    documentNo: str = Field(min_length=1)
    assessmentBatchNo: str = ""


ToolResolver = Callable[[BaseModel], Any]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    arguments_model: type[BaseModel]
    resolver: ToolResolver
    source_of_truth: str
    allowed_in_chat: bool = True

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "argumentsSchema": self.arguments_model.model_json_schema(),
            "sourceOfTruth": self.source_of_truth,
        }

    def validate_arguments(self, raw_arguments: dict[str, Any] | None) -> BaseModel:
        return self.arguments_model.model_validate(raw_arguments or {})


@dataclass(frozen=True)
class ToolExecutionResult:
    name: str
    arguments: dict[str, Any]
    result: Any
    source_of_truth: str


def _resolve_process_workbench(_: EmptyToolArguments) -> dict[str, Any]:
    return get_process_workbench()


def _resolve_process_document_detail(arguments: ProcessDocumentDetailArguments) -> dict[str, Any] | None:
    return get_process_document_detail(
        document_no=arguments.documentNo.strip(),
        assessment_batch_no=arguments.assessmentBatchNo.strip() or None,
    )


def _resolve_collect_workbench(_: EmptyToolArguments) -> dict[str, Any]:
    return get_collect_workbench()


class ToolRegistry:
    def __init__(self, tools: dict[str, ToolDefinition] | None = None) -> None:
        self._tools = tools or build_default_tool_registry()._tools

    def list_router_metadata(self) -> list[dict[str, Any]]:
        return [
            tool.summary()
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
            if tool.allowed_in_chat
        ]

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def execute(self, name: str, raw_arguments: dict[str, Any] | None) -> ToolExecutionResult:
        tool = self._tools.get(name)
        if tool is None or not tool.allowed_in_chat:
            raise KeyError(f"Tool not registered for chat: {name}")
        validated_arguments = tool.validate_arguments(raw_arguments)
        result = tool.resolver(validated_arguments)
        return ToolExecutionResult(
            name=tool.name,
            arguments=validated_arguments.model_dump(),
            result=result,
            source_of_truth=tool.source_of_truth,
        )


def build_default_tool_registry() -> ToolRegistry:
    tools = {
        "get_process_workbench": ToolDefinition(
            name="get_process_workbench",
            description="Return the official realtime snapshot for the process workbench.",
            arguments_model=EmptyToolArguments,
            resolver=_resolve_process_workbench,
            source_of_truth="GET /api/documents/process-workbench",
        ),
        "get_process_document_detail": ToolDefinition(
            name="get_process_document_detail",
            description="Return the official process document detail for a single document number.",
            arguments_model=ProcessDocumentDetailArguments,
            resolver=_resolve_process_document_detail,
            source_of_truth="GET /api/documents/process-workbench/{document_no}",
        ),
        "get_collect_workbench": ToolDefinition(
            name="get_collect_workbench",
            description="Return the official realtime snapshot for the collect workbench.",
            arguments_model=EmptyToolArguments,
            resolver=_resolve_collect_workbench,
            source_of_truth="GET /api/documents/collect-workbench",
        ),
    }
    return ToolRegistry(tools)
