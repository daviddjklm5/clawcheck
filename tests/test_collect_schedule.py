from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from automation.utils.collect_schedule import (
    get_collect_lock_info,
    get_collect_schedule_summary,
    update_collect_schedule,
)


class CollectScheduleTest(unittest.TestCase):
    def test_update_collect_schedule_sets_anchor_for_first_enable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "windows_task_daemon.local.json"
            state_path = Path(temp_dir) / "windows_task_daemon_state.json"
            config_path.write_text(
                json.dumps(
                    {
                        "pollSeconds": 30,
                        "logDir": "automation/logs/windows_task_daemon",
                        "tasks": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = update_collect_schedule(
                enabled=True,
                interval_minutes=20,
                config_path=config_path,
                state_path=state_path,
                now=datetime(2026, 3, 23, 10, 0, 0),
            )

            saved_config = json.loads(config_path.read_text(encoding="utf-8"))
            collect_task = next(task for task in saved_config["tasks"] if task["name"] == "collect")
            saved_state = json.loads(state_path.read_text(encoding="utf-8"))

            self.assertTrue(collect_task["enabled"])
            self.assertEqual(collect_task["intervalMinutes"], 20)
            self.assertIn("-Headless", collect_task["args"])
            self.assertEqual(saved_state["tasks"]["collect"]["scheduleAnchorAt"], "2026-03-23T10:00:00")
            self.assertEqual(summary.next_planned_at, "2026-03-23 10:20:00")

    def test_collect_schedule_summary_hides_next_plan_while_running(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "windows_task_daemon.local.json"
            state_path = Path(temp_dir) / "windows_task_daemon_state.json"
            lock_path = Path(temp_dir) / "collect_task.lock"
            config_path.write_text(
                json.dumps(
                    {
                        "pollSeconds": 15,
                        "logDir": "automation/logs/windows_task_daemon",
                        "tasks": [
                            {
                                "name": "collect",
                                "enabled": True,
                                "script": "automation/scripts/run_windows_task.ps1",
                                "args": ["-Action", "collect", "-Headless", "-Limit", "100"],
                                "intervalMinutes": 15,
                                "dailyTimes": [],
                                "runOnStartup": False,
                            }
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "tasks": {
                            "collect": {
                                "lastStartedAt": "2026-03-23T10:00:00",
                                "lastFinishedAt": "2026-03-23T09:50:00",
                                "lastMessage": "采集任务运行中",
                            }
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            lock_path.write_text(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "createdAt": "2026-03-23T10:00:00",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = get_collect_schedule_summary(
                now=datetime(2026, 3, 23, 10, 5, 0),
                config_path=config_path,
                state_path=state_path,
                lock_path=lock_path,
            )

            self.assertTrue(summary.is_running)
            self.assertEqual(summary.next_planned_at, "")

    def test_get_collect_lock_info_cleans_stale_lock(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "collect_task.lock"
            lock_path.write_text(
                json.dumps(
                    {
                        "pid": 99999999,
                        "createdAt": "2026-03-23T10:00:00",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch("automation.utils.collect_schedule._is_process_running", return_value=False):
                lock_info = get_collect_lock_info(lock_path)

            self.assertIsNone(lock_info)
            self.assertFalse(lock_path.exists())

    def test_get_collect_lock_info_cleans_stale_lock_for_windows_invalid_pid_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "collect_task.lock"
            lock_path.write_text(
                json.dumps(
                    {
                        "pid": 12345,
                        "createdAt": "2026-03-23T10:00:00",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch("automation.utils.collect_schedule.os.kill", side_effect=OSError(22, "invalid", None, 87, None)):
                lock_info = get_collect_lock_info(lock_path)

            self.assertIsNone(lock_info)
            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
