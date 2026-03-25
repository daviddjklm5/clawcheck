from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from automation.utils.collect_schedule import (
    COLLECT_TASK_RUNNING_MESSAGE,
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
                auto_audit=True,
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
            self.assertIn("-AutoAudit", collect_task["args"])
            self.assertEqual(saved_state["tasks"]["collect"]["scheduleAnchorAt"], "2026-03-23T10:00:00")
            self.assertEqual(summary.next_planned_at, "2026-03-23 10:20:00")
            self.assertTrue(summary.auto_audit)

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

    def test_update_collect_schedule_can_disable_auto_audit_flag(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "windows_task_daemon.local.json"
            state_path = Path(temp_dir) / "windows_task_daemon_state.json"
            config_path.write_text(
                json.dumps(
                    {
                        "pollSeconds": 30,
                        "logDir": "automation/logs/windows_task_daemon",
                        "tasks": [
                            {
                                "name": "collect",
                                "enabled": True,
                                "script": "automation/scripts/run_windows_task.ps1",
                                "args": ["-Action", "collect", "-Headless", "-AutoAudit", "-Limit", "100"],
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

            summary = update_collect_schedule(
                enabled=True,
                interval_minutes=15,
                auto_audit=False,
                config_path=config_path,
                state_path=state_path,
                now=datetime(2026, 3, 23, 10, 0, 0),
            )

            saved_config = json.loads(config_path.read_text(encoding="utf-8"))
            collect_task = next(task for task in saved_config["tasks"] if task["name"] == "collect")
            self.assertNotIn("-AutoAudit", collect_task["args"])
            self.assertFalse(summary.auto_audit)

    def test_update_collect_schedule_can_enable_auto_batch_approve_flag(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "windows_task_daemon.local.json"
            state_path = Path(temp_dir) / "windows_task_daemon_state.json"
            config_path.write_text(
                json.dumps(
                    {
                        "pollSeconds": 30,
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

            summary = update_collect_schedule(
                enabled=True,
                interval_minutes=15,
                auto_audit=False,
                auto_batch_approve=True,
                config_path=config_path,
                state_path=state_path,
                now=datetime(2026, 3, 23, 10, 0, 0),
            )

            saved_config = json.loads(config_path.read_text(encoding="utf-8"))
            collect_task = next(task for task in saved_config["tasks"] if task["name"] == "collect")
            self.assertIn("-AutoBatchApprove", collect_task["args"])
            self.assertTrue(summary.auto_batch_approve)

    def test_collect_schedule_summary_repairs_incomplete_collect_state_when_lock_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "windows_task_daemon.local.json"
            state_path = Path(temp_dir) / "windows_task_daemon_state.json"
            lock_path = Path(temp_dir) / "collect_task.lock"
            log_path = Path(temp_dir) / "run_20260323_100000.log"
            log_path.write_text("partial log", encoding="utf-8")
            finished_at = datetime(2026, 3, 23, 10, 2, 30).timestamp()
            os.utime(log_path, (finished_at, finished_at))
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
                                "lastMessage": COLLECT_TASK_RUNNING_MESSAGE,
                                "lastLogPath": str(log_path),
                            }
                        }
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

            repaired_state = json.loads(state_path.read_text(encoding="utf-8"))
            repaired_collect_state = repaired_state["tasks"]["collect"]
            self.assertFalse(summary.is_running)
            self.assertEqual(summary.last_finished_at, "2026-03-23 10:02:30")
            self.assertEqual(summary.next_planned_at, "2026-03-23 10:17:30")
            self.assertEqual(summary.last_message, "采集任务已结束，但状态未完整写回，请查看日志")
            self.assertEqual(repaired_collect_state["lastFinishedAt"], "2026-03-23T10:02:30")
            self.assertEqual(repaired_collect_state["lastMessage"], "采集任务已结束，但状态未完整写回，请查看日志")

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
