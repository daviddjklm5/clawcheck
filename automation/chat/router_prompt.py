from __future__ import annotations

import json
from typing import Any


def _normalize_message_content(value: Any, limit: int = 400) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def summarize_recent_messages(
    messages: list[dict[str, Any]],
    *,
    max_messages: int = 5,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "").strip().lower() or "user"
        content = _normalize_message_content(message.get("content"))
        if not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized[-max_messages:]


def build_router_prompt(
    *,
    latest_user_message: str,
    recent_messages: list[dict[str, Any]],
    available_skills: list[dict[str, Any]],
    available_tools: list[dict[str, Any]],
    confidence_threshold: float,
) -> str:
    payload = {
        "latestUserMessage": latest_user_message.strip(),
        "recentConversation": summarize_recent_messages(recent_messages),
        "availableSkills": available_skills,
        "availableTools": available_tools,
        "toolFirstConfidenceThreshold": confidence_threshold,
    }
    instructions = [
        "You are the clawcheck router model.",
        "You are not answering the user directly.",
        "You must output only a JSON object that matches the provided schema.",
        "Choose only from the provided skills, references, and tools.",
        "Do not invent new tools, new references, new parameters, or new fields.",
        "Each tool call must use argumentsJson as a JSON string. Use '{}' when the tool needs no arguments.",
        "Use tool_first for clawcheck project realtime structured queries that should call an official backend tool.",
        "Use direct_answer for project-aware questions that do not require a tool call but still benefit from skill context.",
        "Use approval_prepare for document approval intents such as approving, rejecting, or validating approval connectivity.",
        "Use general_chat for ordinary conversation, repository discussion, or when routing confidence is too low.",
        "If a tool call requires a missing critical input, do not guess. Fill missingInputs and clarificationQuestion, and leave toolCalls empty until the user provides the missing value.",
        "If route is approval_prepare, do not include any toolCalls. approval actions must never be emitted as normal tools.",
        "If route is approval_prepare, fill approvalRequest with only the values explicitly given by the user. Do not invent document numbers, actions, or approval opinions.",
        "If route is not approval_prepare, set approvalRequest to null.",
        "If route is tool_first, confidence must reflect whether calling the selected tool is safe.",
        "Prefer templated answers only when the tool result can answer the user deterministically.",
        "",
        "Routing context:",
        json.dumps(payload, ensure_ascii=False, indent=2),
    ]
    return "\n".join(instructions)
