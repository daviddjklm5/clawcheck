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


def _resolve_workspace_dir(raw_path: str | None) -> Path:
    text = (raw_path or "").strip()
    if not text:
        return REPO_ROOT
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


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
    )
