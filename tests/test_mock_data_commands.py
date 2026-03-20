from __future__ import annotations

import unittest

from automation.api.mock_data import get_master_data_dashboard


class MockDataCommandsTest(unittest.TestCase):
    def test_master_data_actions_use_single_windows_entrypoint(self) -> None:
        dashboard = get_master_data_dashboard()
        commands = [str(action["command"]) for action in dashboard["actions"]]

        self.assertTrue(commands)
        for command in commands:
            self.assertIn(r"run_windows_task.ps1", command)
            self.assertIn(" -Action ", command)


if __name__ == "__main__":
    unittest.main()
