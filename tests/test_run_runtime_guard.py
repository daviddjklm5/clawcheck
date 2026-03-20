from __future__ import annotations

import argparse
import unittest

from automation.scripts import run


class RunRuntimeGuardTest(unittest.TestCase):
    def test_is_wsl_environment_detects_env_marker(self) -> None:
        self.assertTrue(run.is_wsl_environment(environ={"WSL_DISTRO_NAME": "Ubuntu"}))

    def test_should_block_wsl_runtime_for_prod_defaults(self) -> None:
        args = argparse.Namespace(
            action="collect",
            config=run.DEFAULT_CONFIG_PATH,
            credentials=run.DEFAULT_CREDENTIALS_PATH,
        )

        blocked = run.should_block_wsl_runtime(
            args,
            settings_path=run.resolve_path(run.PROD_CONFIG_PATH),
            credentials_path=run.resolve_path(run.PROD_CREDENTIALS_PATH),
            environ={"WSL_DISTRO_NAME": "Ubuntu"},
        )

        self.assertTrue(blocked)

    def test_should_not_block_wsl_runtime_for_local_config(self) -> None:
        args = argparse.Namespace(
            action="collect",
            config=run.DEFAULT_CONFIG_PATH,
            credentials=run.DEFAULT_CREDENTIALS_PATH,
        )

        blocked = run.should_block_wsl_runtime(
            args,
            settings_path=run.resolve_path(run.DEFAULT_CONFIG_PATH),
            credentials_path=run.resolve_path(run.DEFAULT_CREDENTIALS_PATH),
            environ={"WSL_DISTRO_NAME": "Ubuntu"},
        )

        self.assertFalse(blocked)

    def test_should_not_block_when_override_enabled(self) -> None:
        args = argparse.Namespace(
            action="collect",
            config=run.DEFAULT_CONFIG_PATH,
            credentials=run.DEFAULT_CREDENTIALS_PATH,
        )

        blocked = run.should_block_wsl_runtime(
            args,
            settings_path=run.resolve_path(run.PROD_CONFIG_PATH),
            credentials_path=run.resolve_path(run.PROD_CREDENTIALS_PATH),
            environ={
                "WSL_DISTRO_NAME": "Ubuntu",
                "CLAWCHECK_ALLOW_WSL_RUNTIME": "1",
            },
        )

        self.assertFalse(blocked)

    def test_build_wsl_runtime_block_message_contains_windows_entry(self) -> None:
        message = run.build_wsl_runtime_block_message(
            action="audit",
            settings_path=run.resolve_path(run.PROD_CONFIG_PATH),
            credentials_path=run.resolve_path(run.PROD_CREDENTIALS_PATH),
        )

        self.assertIn("run_windows_task.ps1 -Action audit", message)
        self.assertIn("Blocked Windows-native runtime action on WSL: audit", message)


if __name__ == "__main__":
    unittest.main()
