from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any
from urllib import error as url_error
from urllib import request as url_request

from automation.chat.codex_runner import CodexExecutionResult, EventCallback, RouterExecutionResult
from automation.chat.provider_config import ChatProviderConfig


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return ""
    return normalized


def _responses_endpoint(base_url: str) -> str:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return ""
    if normalized.endswith("/responses"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/responses"
    if "/v1/" in normalized:
        return normalized
    return f"{normalized}/v1/responses"


def _health_candidates(base_url: str) -> list[str]:
    normalized = _normalize_base_url(base_url)
    if not normalized:
        return []
    candidates = [
        f"{normalized}/health",
        f"{normalized}/healthz",
        f"{normalized}/v1/health",
        f"{normalized}/v1/healthz",
        f"{normalized}/v1/models",
        f"{normalized}/models",
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _extract_response_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = payload.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for content_item in content:
                    if not isinstance(content_item, dict):
                        continue
                    text = content_item.get("text")
                    if isinstance(text, str) and text:
                        chunks.append(text)
            text = item.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)
        if chunks:
            return "".join(chunks)

    choices = payload.get("choices")
    if isinstance(choices, list):
        chunks = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content:
                    chunks.append(content)
        if chunks:
            return "".join(chunks)

    content = payload.get("content")
    if isinstance(content, str) and content.strip():
        return content
    return ""


def _extract_usage(payload: dict[str, Any]) -> dict[str, int]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {}
    output_tokens = usage.get("output_tokens")
    input_tokens = usage.get("input_tokens")
    normalized: dict[str, int] = {}
    if isinstance(output_tokens, int):
        normalized["output_tokens"] = output_tokens
    if isinstance(input_tokens, int):
        normalized["input_tokens"] = input_tokens
    return normalized


def _extract_json_object(text: str) -> dict[str, Any] | None:
    payload_text = text.strip()
    if not payload_text:
        return None
    try:
        parsed = json.loads(payload_text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    start = payload_text.find("{")
    end = payload_text.rfind("}")
    if start < 0 or end <= start:
        return None
    snippet = payload_text[start : end + 1]
    try:
        parsed = json.loads(snippet)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _request_json(
    *,
    url: str,
    method: str,
    timeout_seconds: int,
    api_key: str,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | None, str]:
    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    request = url_request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method.upper(),
    )
    try:
        with url_request.urlopen(request, timeout=max(timeout_seconds, 5)) as response:
            raw = response.read().decode("utf-8", errors="replace")
            code = int(getattr(response, "status", 200))
    except url_error.HTTPError as exc:
        raw = (exc.read() or b"").decode("utf-8", errors="replace")
        return int(exc.code), _extract_json_object(raw), raw
    except Exception as exc:  # noqa: BLE001
        return 0, None, str(exc)

    body = _extract_json_object(raw)
    if body is None:
        return code, None, raw
    return code, body, raw


def run_app_server_exec(
    *,
    config: ChatProviderConfig,
    prompt: str,
    workspace_dir: Path,
    cancel_event: threading.Event,
    callback: EventCallback | None,
    model_override: str | None = None,
    reasoning_effort_override: str | None = None,
) -> CodexExecutionResult:
    if cancel_event.is_set():
        if callback is not None:
            callback({"type": "status", "status": "canceled"})
            callback({"type": "done", "status": "canceled", "exitCode": 130})
        return CodexExecutionResult(
            status="canceled",
            final_text="",
            exit_code=130,
            output_tail="canceled",
            usage={},
        )

    endpoint = _responses_endpoint(config.app_server_base_url)
    if not endpoint:
        raise RuntimeError("CLAWCHECK_CHAT_APP_SERVER_BASE_URL is empty.")

    selected_model = (model_override or "").strip() or config.model
    reasoning_effort = (reasoning_effort_override or "").strip().lower()
    request_payload: dict[str, Any] = {
        "model": selected_model,
        "input": prompt,
        "max_output_tokens": max(config.max_output_tokens, 256),
    }
    if reasoning_effort:
        request_payload["reasoning"] = {"effort": reasoning_effort}

    if callback is not None:
        callback({"type": "status", "status": "running"})

    status_code, body, raw = _request_json(
        url=endpoint,
        method="POST",
        timeout_seconds=config.app_server_timeout_seconds,
        api_key=config.api_key,
        payload=request_payload,
    )

    if cancel_event.is_set():
        if callback is not None:
            callback({"type": "status", "status": "canceled"})
            callback({"type": "done", "status": "canceled", "exitCode": 130})
        return CodexExecutionResult(
            status="canceled",
            final_text="",
            exit_code=130,
            output_tail=raw[-12000:],
            usage={},
        )

    if status_code < 200 or status_code >= 300 or body is None:
        error_message = "app-server request failed"
        if body is not None:
            message = body.get("error")
            if isinstance(message, dict):
                error_message = str(message.get("message") or error_message)
            elif isinstance(message, str) and message.strip():
                error_message = message
        elif raw.strip():
            error_message = raw.strip()[:600]
        if callback is not None:
            callback({"type": "error", "message": error_message})
            callback({"type": "done", "status": "failed", "exitCode": 1})
        return CodexExecutionResult(
            status="failed",
            final_text="",
            exit_code=1,
            output_tail=raw[-12000:],
            usage={},
        )

    text = _extract_response_text(body).strip()
    usage = _extract_usage(body)
    if callback is not None and text:
        callback({"type": "token", "delta": text})
    if callback is not None:
        callback({"type": "done", "status": "succeeded", "exitCode": 0})
    return CodexExecutionResult(
        status="succeeded",
        final_text=text,
        exit_code=0,
        output_tail=raw[-12000:],
        usage=usage,
    )


def run_app_server_router(
    *,
    config: ChatProviderConfig,
    prompt: str,
    workspace_dir: Path,
    output_schema: dict[str, Any],
    cancel_event: threading.Event,
) -> RouterExecutionResult:
    endpoint = _responses_endpoint(config.app_server_base_url)
    if not endpoint:
        return RouterExecutionResult(
            status="failed",
            decision=None,
            exit_code=1,
            raw_output="",
            error_message="CLAWCHECK_CHAT_APP_SERVER_BASE_URL is empty.",
        )
    if cancel_event.is_set():
        return RouterExecutionResult(
            status="canceled",
            decision=None,
            exit_code=130,
            raw_output="canceled",
            error_message="router canceled",
        )

    router_model = config.router_model.strip() or config.model
    format_instruction = (
        "\n\nOutput requirements:\n"
        "1) Return strictly one JSON object only.\n"
        "2) The JSON must satisfy this schema:\n"
        f"{json.dumps(output_schema, ensure_ascii=False)}\n"
    )
    request_payload: dict[str, Any] = {
        "model": router_model,
        "input": f"{prompt}{format_instruction}",
        "max_output_tokens": 800,
    }
    if config.router_reasoning_effort.strip():
        request_payload["reasoning"] = {"effort": config.router_reasoning_effort.strip().lower()}

    status_code, body, raw = _request_json(
        url=endpoint,
        method="POST",
        timeout_seconds=config.app_server_timeout_seconds,
        api_key=config.api_key,
        payload=request_payload,
    )
    if status_code < 200 or status_code >= 300 or body is None:
        return RouterExecutionResult(
            status="failed",
            decision=None,
            exit_code=1,
            raw_output=raw[-12000:],
            error_message=f"app-server router request failed: status={status_code}",
        )

    text = _extract_response_text(body)
    decision = _extract_json_object(text)
    if decision is None:
        return RouterExecutionResult(
            status="failed",
            decision=None,
            exit_code=1,
            raw_output=raw[-12000:],
            error_message="router decision JSON parse failed",
        )
    return RouterExecutionResult(
        status="succeeded",
        decision=decision,
        exit_code=0,
        raw_output=raw[-12000:],
        error_message="",
    )


def probe_app_server_health(
    *,
    base_url: str,
    timeout_seconds: int,
    api_key: str,
) -> dict[str, Any]:
    for health_url in _health_candidates(base_url):
        status_code, body, raw = _request_json(
            url=health_url,
            method="GET",
            timeout_seconds=timeout_seconds,
            api_key=api_key,
            payload=None,
        )
        if 200 <= status_code < 300:
            return {
                "ok": True,
                "url": health_url,
                "statusCode": status_code,
                "message": str((body or {}).get("status") or raw or "ok")[:300],
            }
    return {
        "ok": False,
        "url": "",
        "statusCode": 0,
        "message": "health probe failed",
    }
