from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from typing import Any

from automation.chat.provider_config import ChatProviderConfig

EventCallback = Callable[[dict[str, Any]], None]
_EXEC_HELP_CACHE: dict[str, str] = {}


@dataclass
class CodexExecutionResult:
    status: str
    final_text: str
    exit_code: int
    output_tail: str
    usage: dict[str, int]


@dataclass
class RouterExecutionResult:
    status: str
    decision: dict[str, Any] | None
    exit_code: int
    raw_output: str
    error_message: str


@dataclass
class _ExecCollectionResult:
    status: str
    final_text: str
    exit_code: int
    raw_output: str
    usage: dict[str, int]
    error_message: str


def resolve_codex_cli_path(config: ChatProviderConfig) -> str | None:
    executable = config.codex_cli_executable.strip()
    if not executable:
        return None
    if os.path.isabs(executable):
        return executable if Path(executable).exists() else None
    return shutil.which(executable)


def _safe_json_parse(line: str) -> dict[str, Any] | None:
    text = line.strip()
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _exec_help_text(codex_cli_path: str) -> str:
    cached = _EXEC_HELP_CACHE.get(codex_cli_path)
    if cached is not None:
        return cached
    try:
        output = subprocess.run(
            [codex_cli_path, "exec", "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:  # noqa: BLE001
        text = ""
    else:
        text = f"{output.stdout}\n{output.stderr}".strip()
    _EXEC_HELP_CACHE[codex_cli_path] = text
    return text


def _supports_exec_option(codex_cli_path: str, option: str) -> bool:
    help_text = _exec_help_text(codex_cli_path)
    return option in help_text


def _ensure_runtime_prerequisites(config: ChatProviderConfig) -> str:
    codex_cli_path = resolve_codex_cli_path(config)
    if codex_cli_path is None:
        raise RuntimeError(
            f"Codex CLI not found: {config.codex_cli_executable}. Set CLAWCHECK_CODEX_CLI or install codex."
        )
    if not config.api_key:
        raise RuntimeError(
            f"Missing model API key. Set environment variable {config.api_key_env}."
        )
    return codex_cli_path


def _build_exec_command(
    *,
    codex_cli_path: str,
    config: ChatProviderConfig,
    workspace_dir: Path,
    output_schema_path: Path | None = None,
    model_override: str | None = None,
    reasoning_effort_override: str | None = None,
) -> list[str]:
    selected_model = (model_override or "").strip() or config.model
    command = [
        codex_cli_path,
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--cd",
        str(workspace_dir),
        "-m",
        selected_model,
    ]
    selected_reasoning_effort = (reasoning_effort_override or "").strip().lower()
    if selected_reasoning_effort:
        command.extend(["-c", f'model_reasoning_effort="{selected_reasoning_effort}"'])
    if _supports_exec_option(codex_cli_path, "--ask-for-approval"):
        command.extend(["--ask-for-approval", "never"])
    if output_schema_path is not None:
        if not _supports_exec_option(codex_cli_path, "--output-schema"):
            raise RuntimeError("Current Codex CLI does not support --output-schema.")
        command.extend(["--output-schema", str(output_schema_path)])
    if config.base_url:
        command.extend(["-c", f'openai_base_url="{config.base_url}"'])
    command.append("-")
    return command


def _build_exec_env(config: ChatProviderConfig) -> dict[str, str]:
    env = dict(os.environ)
    env["OPENAI_API_KEY"] = config.api_key
    env["CLAWCHECK_AI_PROVIDER"] = config.provider
    return env


def _start_exec_process(
    *,
    command: list[str],
    prompt: str,
    workspace_dir: Path,
    env: dict[str, str],
) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        command,
        cwd=str(workspace_dir),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )
    if process.stdin is not None:
        process.stdin.write(prompt)
        process.stdin.close()
    return process


def _collect_exec_output(
    *,
    process: subprocess.Popen[str],
    cancel_event: threading.Event,
    timeout_seconds: int,
    callback: EventCallback | None = None,
) -> _ExecCollectionResult:
    lines_queue: queue.Queue[str | None] = queue.Queue()

    def _read_stdout_lines() -> None:
        stdout = process.stdout
        if stdout is None:
            lines_queue.put(None)
            return
        try:
            for line in stdout:
                lines_queue.put(line.rstrip("\n"))
        finally:
            lines_queue.put(None)

    reader_thread = threading.Thread(target=_read_stdout_lines, daemon=True)
    reader_thread.start()

    started_at = time.monotonic()
    final_text = ""
    output_lines: list[str] = []
    usage: dict[str, int] = {}
    error_message = ""
    stream_done = False
    return_code: int | None = None
    status = "running"

    if callback is not None:
        callback({"type": "status", "status": "running"})

    while True:
        if cancel_event.is_set() and process.poll() is None:
            process.terminate()
            status = "canceled"

        elapsed = time.monotonic() - started_at
        if elapsed > timeout_seconds and process.poll() is None:
            process.terminate()
            status = "timeout"

        try:
            next_line = lines_queue.get(timeout=0.2)
        except queue.Empty:
            if process.poll() is not None and stream_done:
                break
            continue

        if next_line is None:
            stream_done = True
            if process.poll() is not None:
                break
            continue

        line = next_line.strip()
        if not line:
            continue
        output_lines.append(line)
        event_payload = _safe_json_parse(line)
        if event_payload is None:
            if callback is not None:
                callback({"type": "output", "line": line})
            continue

        event_type = str(event_payload.get("type") or "")
        if event_type == "item.completed":
            item = event_payload.get("item")
            if isinstance(item, dict):
                item_type = str(item.get("type") or "")
                if item_type == "agent_message":
                    text = str(item.get("text") or "")
                    if text:
                        final_text += text
                        if callback is not None:
                            callback({"type": "token", "delta": text})
                    continue
                if item_type == "error":
                    error_message = str(item.get("message") or "").strip() or "Codex returned an error item."
                    if callback is not None:
                        callback({"type": "error", "message": error_message})
                    continue
                if item_type and callback is not None:
                    callback(
                        {
                            "type": "tool",
                            "eventType": item_type,
                            "summary": json.dumps(item, ensure_ascii=False)[:1200],
                        }
                    )
                    continue
        elif event_type == "turn.completed":
            raw_usage = event_payload.get("usage")
            if isinstance(raw_usage, dict):
                for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
                    value = raw_usage.get(key)
                    if isinstance(value, int):
                        usage[key] = value
            continue
        elif callback is not None:
            callback(
                {
                    "type": "event",
                    "eventType": event_type,
                    "summary": json.dumps(event_payload, ensure_ascii=False)[:1200],
                }
            )

    if return_code is None:
        try:
            return_code = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            return_code = process.wait(timeout=2)
    if status == "running":
        status = "succeeded" if return_code == 0 else "failed"

    if status == "timeout":
        error_message = error_message or f"Execution timed out after {timeout_seconds}s"
        if callback is not None:
            callback({"type": "error", "message": error_message})
    elif status == "canceled":
        if callback is not None:
            callback({"type": "status", "status": "canceled"})
    elif status == "failed":
        error_message = error_message or f"Codex exited with code {return_code}"
        if callback is not None:
            callback({"type": "error", "message": error_message})

    raw_output = "\n".join(output_lines)[-12000:]
    if callback is not None:
        callback({"type": "done", "status": status, "exitCode": return_code})
    return _ExecCollectionResult(
        status=status,
        final_text=final_text,
        exit_code=return_code,
        raw_output=raw_output,
        usage=usage,
        error_message=error_message,
    )


def run_codex_exec(
    *,
    config: ChatProviderConfig,
    prompt: str,
    workspace_dir: Path,
    cancel_event: threading.Event,
    callback: EventCallback,
) -> CodexExecutionResult:
    codex_cli_path = _ensure_runtime_prerequisites(config)
    command = _build_exec_command(
        codex_cli_path=codex_cli_path,
        config=config,
        workspace_dir=workspace_dir,
    )
    process = _start_exec_process(
        command=command,
        prompt=prompt,
        workspace_dir=workspace_dir,
        env=_build_exec_env(config),
    )
    result = _collect_exec_output(
        process=process,
        cancel_event=cancel_event,
        timeout_seconds=config.timeout_seconds,
        callback=callback,
    )
    return CodexExecutionResult(
        status=result.status,
        final_text=result.final_text,
        exit_code=result.exit_code,
        output_tail=result.raw_output,
        usage=result.usage,
    )


def run_router_exec(
    *,
    config: ChatProviderConfig,
    prompt: str,
    workspace_dir: Path,
    output_schema: dict[str, Any],
    cancel_event: threading.Event,
    runtime_dir: Path,
) -> RouterExecutionResult:
    try:
        codex_cli_path = _ensure_runtime_prerequisites(config)
    except Exception as exc:  # noqa: BLE001
        return RouterExecutionResult(
            status="failed",
            decision=None,
            exit_code=1,
            raw_output="",
            error_message=str(exc),
        )

    runtime_dir.mkdir(parents=True, exist_ok=True)
    schema_path = runtime_dir / "router-decision.schema.json"
    schema_path.write_text(
        json.dumps(output_schema, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    try:
        router_model = config.router_model.strip() or config.model
        router_reasoning_effort = config.router_reasoning_effort.strip()
        command = _build_exec_command(
            codex_cli_path=codex_cli_path,
            config=config,
            workspace_dir=workspace_dir,
            output_schema_path=schema_path,
            model_override=router_model,
            reasoning_effort_override=router_reasoning_effort,
        )
        process = _start_exec_process(
            command=command,
            prompt=prompt,
            workspace_dir=workspace_dir,
            env=_build_exec_env(config),
        )
        result = _collect_exec_output(
            process=process,
            cancel_event=cancel_event,
            timeout_seconds=config.timeout_seconds,
            callback=None,
        )
    except Exception as exc:  # noqa: BLE001
        return RouterExecutionResult(
            status="failed",
            decision=None,
            exit_code=1,
            raw_output="",
            error_message=str(exc),
        )

    if result.status != "succeeded":
        return RouterExecutionResult(
            status=result.status,
            decision=None,
            exit_code=result.exit_code,
            raw_output=result.raw_output,
            error_message=result.error_message,
        )

    raw_text = result.final_text.strip()
    if not raw_text:
        return RouterExecutionResult(
            status="failed",
            decision=None,
            exit_code=result.exit_code,
            raw_output=result.raw_output,
            error_message="Router returned empty output.",
        )

    try:
        decision = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return RouterExecutionResult(
            status="failed",
            decision=None,
            exit_code=result.exit_code,
            raw_output=result.raw_output or raw_text,
            error_message=f"Router output is not valid JSON: {exc}",
        )
    if not isinstance(decision, dict):
        return RouterExecutionResult(
            status="failed",
            decision=None,
            exit_code=result.exit_code,
            raw_output=result.raw_output or raw_text,
            error_message="Router output JSON must be an object.",
        )

    return RouterExecutionResult(
        status="succeeded",
        decision=decision,
        exit_code=result.exit_code,
        raw_output=result.raw_output or raw_text,
        error_message="",
    )
