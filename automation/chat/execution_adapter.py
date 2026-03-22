from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import threading
from typing import Any

from automation.chat.app_server_runner import probe_app_server_health, run_app_server_exec, run_app_server_router
from automation.chat.codex_runner import (
    CodexExecutionResult,
    EventCallback,
    RouterExecutionResult,
    resolve_codex_cli_path,
    run_codex_exec,
    run_router_exec,
)
from automation.chat.provider_config import ChatProviderConfig


class ModelExecutionAdapter(ABC):
    @property
    @abstractmethod
    def mode(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def run_answer(
        self,
        *,
        config: ChatProviderConfig,
        prompt: str,
        workspace_dir: Path,
        cancel_event: threading.Event,
        callback: EventCallback,
    ) -> CodexExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def run_router(
        self,
        *,
        config: ChatProviderConfig,
        prompt: str,
        workspace_dir: Path,
        output_schema: dict[str, Any],
        cancel_event: threading.Event,
        runtime_dir: Path,
    ) -> RouterExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def health(self, *, config: ChatProviderConfig) -> dict[str, Any]:
        raise NotImplementedError


class OneShotExecAdapter(ModelExecutionAdapter):
    @property
    def mode(self) -> str:
        return "oneshot_exec"

    def run_answer(
        self,
        *,
        config: ChatProviderConfig,
        prompt: str,
        workspace_dir: Path,
        cancel_event: threading.Event,
        callback: EventCallback,
    ) -> CodexExecutionResult:
        return run_codex_exec(
            config=config,
            prompt=prompt,
            workspace_dir=workspace_dir,
            cancel_event=cancel_event,
            callback=callback,
        )

    def run_router(
        self,
        *,
        config: ChatProviderConfig,
        prompt: str,
        workspace_dir: Path,
        output_schema: dict[str, Any],
        cancel_event: threading.Event,
        runtime_dir: Path,
    ) -> RouterExecutionResult:
        return run_router_exec(
            config=config,
            prompt=prompt,
            workspace_dir=workspace_dir,
            output_schema=output_schema,
            cancel_event=cancel_event,
            runtime_dir=runtime_dir,
        )

    def health(self, *, config: ChatProviderConfig) -> dict[str, Any]:
        codex_path = resolve_codex_cli_path(config)
        return {
            "backend": "oneshot_exec",
            "ready": bool(codex_path and config.api_key),
            "codexCliPath": codex_path or "",
        }


class PersistentSubprocessAdapter(OneShotExecAdapter):
    @property
    def mode(self) -> str:
        return "persistent_subprocess"


class AppServerAdapter(ModelExecutionAdapter):
    @property
    def mode(self) -> str:
        return "app_server"

    def run_answer(
        self,
        *,
        config: ChatProviderConfig,
        prompt: str,
        workspace_dir: Path,
        cancel_event: threading.Event,
        callback: EventCallback,
    ) -> CodexExecutionResult:
        return run_app_server_exec(
            config=config,
            prompt=prompt,
            workspace_dir=workspace_dir,
            cancel_event=cancel_event,
            callback=callback,
        )

    def run_router(
        self,
        *,
        config: ChatProviderConfig,
        prompt: str,
        workspace_dir: Path,
        output_schema: dict[str, Any],
        cancel_event: threading.Event,
        runtime_dir: Path,
    ) -> RouterExecutionResult:
        return run_app_server_router(
            config=config,
            prompt=prompt,
            workspace_dir=workspace_dir,
            output_schema=output_schema,
            cancel_event=cancel_event,
        )

    def health(self, *, config: ChatProviderConfig) -> dict[str, Any]:
        probe = probe_app_server_health(
            base_url=config.app_server_base_url,
            timeout_seconds=config.app_server_timeout_seconds,
            api_key=config.api_key,
        )
        return {
            "backend": "app_server",
            "ready": bool(probe.get("ok")),
            "appServerBaseUrl": config.app_server_base_url,
            "appServerHealthUrl": probe.get("url") or "",
            "appServerStatusCode": int(probe.get("statusCode") or 0),
            "appServerMessage": str(probe.get("message") or ""),
        }


def build_execution_adapter(mode: str) -> ModelExecutionAdapter:
    normalized = (mode or "").strip().lower()
    if normalized == "app_server":
        return AppServerAdapter()
    if normalized == "persistent_subprocess":
        return PersistentSubprocessAdapter()
    return OneShotExecAdapter()

