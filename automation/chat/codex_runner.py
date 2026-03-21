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


def run_codex_exec(
    *,
    config: ChatProviderConfig,
    prompt: str,
    workspace_dir: Path,
    cancel_event: threading.Event,
    callback: EventCallback,
) -> CodexExecutionResult:
    codex_cli_path = resolve_codex_cli_path(config)
    if codex_cli_path is None:
        raise RuntimeError(
            f"Codex CLI not found: {config.codex_cli_executable}. Set CLAWCHECK_CODEX_CLI or install codex."
        )
    if not config.api_key:
        raise RuntimeError(
            f"Missing model API key. Set environment variable {config.api_key_env}."
        )

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
        config.model,
    ]
    if _supports_exec_option(codex_cli_path, "--ask-for-approval"):
        command.extend(["--ask-for-approval", "never"])
    if config.base_url:
        command.extend(["-c", f'openai_base_url="{config.base_url}"'])
    command.append("-")

    env = dict(os.environ)
    env["OPENAI_API_KEY"] = config.api_key
    env["CLAWCHECK_AI_PROVIDER"] = config.provider

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
    stream_done = False
    return_code: int | None = None
    status = "running"

    callback({"type": "status", "status": "running"})

    while True:
        if cancel_event.is_set() and process.poll() is None:
            process.terminate()
            status = "canceled"

        elapsed = time.monotonic() - started_at
        if elapsed > config.timeout_seconds and process.poll() is None:
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
                        callback({"type": "token", "delta": text})
                    continue
                if item_type == "error":
                    message = str(item.get("message") or "").strip()
                    callback({"type": "error", "message": message or "Codex returned an error item."})
                    continue
                if item_type:
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
        else:
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
        callback({"type": "error", "message": f"Execution timed out after {config.timeout_seconds}s"})
    elif status == "canceled":
        callback({"type": "status", "status": "canceled"})
    elif status == "failed":
        callback({"type": "error", "message": f"Codex exited with code {return_code}"})

    output_tail = "\n".join(output_lines)[-8000:]
    callback({"type": "done", "status": status, "exitCode": return_code})
    return CodexExecutionResult(
        status=status,
        final_text=final_text,
        exit_code=return_code,
        output_tail=output_tail,
        usage=usage,
    )
