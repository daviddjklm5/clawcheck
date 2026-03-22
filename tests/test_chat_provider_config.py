from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from automation.chat.provider_config import load_chat_provider_config
from automation.utils.config_loader import load_settings


class ChatProviderConfigTest(unittest.TestCase):
    @staticmethod
    def _build_settings_file(settings_path: Path, extra_ai_lines: list[str] | None = None) -> None:
        ai_lines = [
            '  provider: "openai_compatible"',
            '  base_url: "https://api.example.com/v1"',
            '  model: "gpt-test"',
            "  timeout_seconds: 90",
            "  max_output_tokens: 1024",
            '  api_key_env: "MY_KEY_ENV"',
        ]
        if extra_ai_lines:
            ai_lines.extend(extra_ai_lines)
        settings_path.write_text(
            "\n".join(
                [
                    "app:",
                    '  base_url: "https://example.com"',
                    '  home_path: "/"',
                    "auth:",
                    '  username: ""',
                    '  password: ""',
                    "browser:",
                    "  headed: true",
                    "  slow_mo_ms: 0",
                    "  timeout_ms: 1000",
                    "  navigation_timeout_ms: 1000",
                    "  ignore_https_errors: true",
                    "runtime:",
                    '  state_file: "state.json"',
                    '  logs_dir: "logs"',
                    '  screenshots_dir: "screenshots"',
                    '  downloads_dir: "downloads"',
                    "  retries: 1",
                    "  retry_wait_sec: 1.0",
                    "db:",
                    '  host: "127.0.0.1"',
                    "  port: 5432",
                    '  dbname: "ierp"',
                    '  user: "postgres"',
                    '  password: "password"',
                    '  schema: "public"',
                    '  sslmode: "prefer"',
                    "ai:",
                    *ai_lines,
                ]
            ),
            encoding="utf-8",
        )

    def test_load_chat_provider_config_prefers_env_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_path = Path(tmp_dir) / "settings.yaml"
            self._build_settings_file(settings_path)
            settings = load_settings(settings_path)
            env = {
                "CLAWCHECK_AI_PROVIDER": "openai_compatible",
                "CLAWCHECK_AI_BASE_URL": "https://api.override.com/v1",
                "CLAWCHECK_AI_MODEL": "gpt-override",
                "CLAWCHECK_AI_TIMEOUT_SECONDS": "60",
                "CLAWCHECK_AI_MAX_OUTPUT_TOKENS": "2048",
                "CLAWCHECK_AI_API_KEY_ENV": "CLAWCHECK_AI_API_KEY",
                "CLAWCHECK_AI_API_KEY": "test-key",
                "CLAWCHECK_CODEX_CLI": "codex",
                "CLAWCHECK_CHAT_WORKDIR": ".",
                "CLAWCHECK_CHAT_ROUTER_MODEL": "gpt-router-override",
                "CLAWCHECK_CHAT_ROUTER_REASONING_EFFORT": "medium",
            }
            with patch.dict(os.environ, env, clear=False):
                config = load_chat_provider_config(settings)

        self.assertEqual(config.base_url, "https://api.override.com/v1")
        self.assertEqual(config.model, "gpt-override")
        self.assertEqual(config.timeout_seconds, 60)
        self.assertEqual(config.max_output_tokens, 2048)
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.api_key_env, "CLAWCHECK_AI_API_KEY")
        self.assertEqual(config.codex_cli_executable, "codex")
        self.assertTrue(config.workspace_dir.is_absolute())
        self.assertEqual(config.router_model, "gpt-router-override")
        self.assertEqual(config.router_reasoning_effort, "medium")

    def test_load_chat_provider_config_uses_yaml_api_key_when_env_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_path = Path(tmp_dir) / "settings.yaml"
            self._build_settings_file(settings_path, extra_ai_lines=['  api_key: "yaml-test-key"'])
            settings = load_settings(settings_path)
            env = {
                "MY_KEY_ENV": "",
                "CLAWCHECK_AI_API_KEY": "",
                "CLAWCHECK_AI_API_KEY_ENV": "",
            }
            with patch.dict(os.environ, env, clear=False):
                config = load_chat_provider_config(settings)

        self.assertEqual(config.api_key_env, "MY_KEY_ENV")
        self.assertEqual(config.api_key, "yaml-test-key")
        self.assertEqual(config.router_model, "gpt-test")
        self.assertEqual(config.router_reasoning_effort, "low")


if __name__ == "__main__":
    unittest.main()
