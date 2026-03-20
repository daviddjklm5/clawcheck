from __future__ import annotations

from datetime import datetime
import unittest

from automation.scripts.windows_task_daemon import (
    TaskConfig,
    bootstrap_interval_state,
    get_due_daily_key,
    is_task_due,
    parse_time_token,
)


class WindowsTaskDaemonTest(unittest.TestCase):
    def test_parse_time_token_accepts_valid_time(self) -> None:
        self.assertEqual(parse_time_token("07:30"), (7, 30))

    def test_parse_time_token_rejects_invalid_time(self) -> None:
        with self.assertRaises(ValueError):
            parse_time_token("24:00")

    def test_bootstrap_interval_state_sets_initial_timestamp(self) -> None:
        task = TaskConfig(
            name="collect",
            script="automation/scripts/run_collect_task.ps1",
            args=[],
            enabled=True,
            interval_minutes=15,
            daily_times=[],
            run_on_startup=False,
        )
        task_state: dict[str, str] = {}
        changed = bootstrap_interval_state(task, task_state, datetime(2026, 3, 20, 8, 0, 0))
        self.assertTrue(changed)
        self.assertEqual(task_state["lastStartedAt"], "2026-03-20T08:00:00")

    def test_disabled_task_does_not_bootstrap_state(self) -> None:
        task = TaskConfig(
            name="collect",
            script="automation/scripts/run_collect_task.ps1",
            args=[],
            enabled=False,
            interval_minutes=15,
            daily_times=[],
            run_on_startup=False,
        )
        task_state: dict[str, str] = {}
        changed = bootstrap_interval_state(task, task_state, datetime(2026, 3, 20, 8, 0, 0))
        self.assertFalse(changed)
        self.assertEqual(task_state, {})

    def test_daily_task_runs_once_per_minute_key(self) -> None:
        task_state = {}
        now = datetime(2026, 3, 20, 7, 30, 2)
        self.assertEqual(get_due_daily_key(task_state, now, ["07:30"]), "2026-03-20T07:30")
        task_state["lastDailyTriggerKey"] = "2026-03-20T07:30"
        self.assertIsNone(get_due_daily_key(task_state, now, ["07:30"]))

    def test_interval_task_becomes_due_after_interval(self) -> None:
        task = TaskConfig(
            name="audit",
            script="automation/scripts/run_audit_task.ps1",
            args=[],
            enabled=True,
            interval_minutes=20,
            daily_times=[],
            run_on_startup=False,
        )
        task_state = {"lastStartedAt": "2026-03-20T08:00:00"}
        due, daily_key = is_task_due(task, task_state, datetime(2026, 3, 20, 8, 20, 0))
        self.assertTrue(due)
        self.assertIsNone(daily_key)

    def test_run_on_startup_task_is_due_without_prior_state(self) -> None:
        task = TaskConfig(
            name="sync",
            script="automation/scripts/run_sync_todo_status_task.ps1",
            args=[],
            enabled=True,
            interval_minutes=30,
            daily_times=[],
            run_on_startup=True,
        )
        due, daily_key = is_task_due(task, {}, datetime(2026, 3, 20, 8, 0, 0))
        self.assertTrue(due)
        self.assertIsNone(daily_key)


if __name__ == "__main__":
    unittest.main()
