from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from automation.api.config_summary import REPO_ROOT
from automation.utils.config_loader import Settings


@dataclass
class ChatProviderConfig:
    provider: str
    base_url: str
    model: str
    timeout_seconds: int
    max_output_tokens: int
    api_key_env: str
    api_key: str
    codex_cli_executable: str
    workspace_dir: Path
    router_model: str = ""
    router_reasoning_effort: str = "low"
    exec_mode: str = "oneshot_exec"
    global_max_concurrent_runs: int = 4
    run_queue_size: int = 200
    session_idle_ttl_seconds: int = 900
    app_server_base_url: str = ""
    app_server_timeout_seconds: int = 120
    exec_auto_fallback: bool = True


def _resolve_workspace_dir(raw_path: str | None) -> Path:
    text = (raw_path or "").strip()
    if not text:
        return REPO_ROOT
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _env_int(name: str, *, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return max(default, minimum)
    try:
        parsed = int(raw.strip())
    except ValueError:
        return max(default, minimum)
    return max(parsed, minimum)


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def load_chat_provider_config(settings: Settings) -> ChatProviderConfig:
    provider = os.getenv("CLAWCHECK_AI_PROVIDER", settings.ai.provider).strip() or "openai_compatible"
    base_url = os.getenv("CLAWCHECK_AI_BASE_URL", settings.ai.base_url).strip() or "https://api.openai.com/v1"
    model = os.getenv("CLAWCHECK_AI_MODEL", settings.ai.model).strip() or "gpt-5-mini"
    timeout_seconds = int(
        os.getenv("CLAWCHECK_AI_TIMEOUT_SECONDS", str(settings.ai.timeout_seconds))
    )
    max_output_tokens = int(
        os.getenv("CLAWCHECK_AI_MAX_OUTPUT_TOKENS", str(settings.ai.max_output_tokens))
    )
    api_key_env = (
        os.getenv("CLAWCHECK_AI_API_KEY_ENV")
        or settings.ai.api_key_env
        or "CLAWCHECK_AI_API_KEY"
    ).strip()
    api_key = os.getenv(api_key_env, "").strip()
    if not api_key:
        api_key = os.getenv("CLAWCHECK_AI_API_KEY", "").strip()
    if not api_key:
        api_key = settings.ai.api_key.strip()
    codex_cli_executable = os.getenv("CLAWCHECK_CODEX_CLI", "codex").strip() or "codex"
    workspace_dir = _resolve_workspace_dir(os.getenv("CLAWCHECK_CHAT_WORKDIR"))
    router_model = os.getenv("CLAWCHECK_CHAT_ROUTER_MODEL", "").strip() or model
    router_reasoning_effort = (
        os.getenv("CLAWCHECK_CHAT_ROUTER_REASONING_EFFORT", "low").strip().lower() or "low"
    )
    if router_reasoning_effort not in {"minimal", "low", "medium", "high"}:
        router_reasoning_effort = "low"
    exec_mode = os.getenv("CLAWCHECK_CHAT_EXEC_MODE", "oneshot_exec").strip().lower() or "oneshot_exec"
    if exec_mode not in {"oneshot_exec", "persistent_subprocess", "app_server"}:
        exec_mode = "oneshot_exec"
    global_max_concurrent_runs = _env_int(
        "CLAWCHECK_CHAT_GLOBAL_MAX_CONCURRENT_RUNS",
        default=4,
        minimum=1,
    )
    run_queue_size = _env_int(
        "CLAWCHECK_CHAT_RUN_QUEUE_SIZE",
        default=200,
        minimum=1,
    )
    session_idle_ttl_seconds = _env_int(
        "CLAWCHECK_CHAT_SESSION_IDLE_TTL_SECONDS",
        default=900,
        minimum=60,
    )
    app_server_base_url = os.getenv("CLAWCHECK_CHAT_APP_SERVER_BASE_URL", "").strip()
    app_server_timeout_seconds = _env_int(
        "CLAWCHECK_CHAT_APP_SERVER_TIMEOUT_SECONDS",
        default=max(timeout_seconds, 10),
        minimum=10,
    )
    exec_auto_fallback = _env_flag("CLAWCHECK_CHAT_EXEC_AUTO_FALLBACK", default=True)

    return ChatProviderConfig(
        provider=provider,
        base_url=base_url,
        model=model,
        timeout_seconds=max(timeout_seconds, 10),
        max_output_tokens=max(max_output_tokens, 256),
        api_key_env=api_key_env,
        api_key=api_key,
        codex_cli_executable=codex_cli_executable,
        workspace_dir=workspace_dir,
        router_model=router_model,
        router_reasoning_effort=router_reasoning_effort,
        exec_mode=exec_mode,
        global_max_concurrent_runs=global_max_concurrent_runs,
        run_queue_size=run_queue_size,
        session_idle_ttl_seconds=session_idle_ttl_seconds,
        app_server_base_url=app_server_base_url,
        app_server_timeout_seconds=app_server_timeout_seconds,
        exec_auto_fallback=exec_auto_fallback,
    )
