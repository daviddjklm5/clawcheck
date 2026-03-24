from __future__ import annotations

from datetime import datetime
import unittest
from unittest.mock import patch

from automation.utils.collect_schedule import COLLECT_TASK_RUNNING_MESSAGE
from automation.scripts.windows_task_daemon import (
    DEFAULT_LOG_DIR,
    TaskConfig,
    bootstrap_interval_state,
    get_due_daily_key,
    is_task_due,
    parse_time_token,
    run_cycle,
)


class WindowsTaskDaemonTest(unittest.TestCase):
    class _FakeProcess:
        def __init__(self, return_code: int | None) -> None:
            self._return_code = return_code

        def poll(self) -> int | None:
            return self._return_code

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
        self.assertEqual(task_state["scheduleAnchorAt"], "2026-03-20T08:00:00")

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

    def test_collect_task_becomes_due_after_interval_from_last_finished(self) -> None:
        task = TaskConfig(
            name="collect",
            script="automation/scripts/run_collect_task.ps1",
            args=[],
            enabled=True,
            interval_minutes=15,
            daily_times=[],
            run_on_startup=False,
        )
        task_state = {"lastFinishedAt": "2026-03-20T08:03:12"}
        due_before, _ = is_task_due(task, task_state, datetime(2026, 3, 20, 8, 18, 11))
        due_after, _ = is_task_due(task, task_state, datetime(2026, 3, 20, 8, 18, 12))
        self.assertFalse(due_before)
        self.assertTrue(due_after)

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

    def test_collect_due_cycle_skips_when_collect_lock_exists(self) -> None:
        from automation.scripts import windows_task_daemon

        task = TaskConfig(
            name="collect",
            script="automation/scripts/run_collect_task.ps1",
            args=[],
            enabled=True,
            interval_minutes=15,
            daily_times=[],
            run_on_startup=False,
        )
        state_payload = {"tasks": {"collect": {"lastFinishedAt": "2026-03-20T08:00:00"}}}

        with (
            patch("automation.scripts.windows_task_daemon.is_collect_execution_locked", return_value=True),
            patch("automation.scripts.windows_task_daemon.start_task") as mocked_start_task,
        ):
            changed = windows_task_daemon.run_cycle(
                tasks=[task],
                state_payload=state_payload,
                running_tasks={},
                log_dir=windows_task_daemon.DEFAULT_LOG_DIR,
                now=datetime(2026, 3, 20, 8, 15, 0),
            )

        self.assertFalse(changed)
        mocked_start_task.assert_not_called()

    def test_run_cycle_marks_changed_when_non_collect_task_completes(self) -> None:
        task = TaskConfig(
            name="audit",
            script="automation/scripts/run_audit_task.ps1",
            args=[],
            enabled=True,
            interval_minutes=20,
            daily_times=[],
            run_on_startup=False,
        )
        state_payload = {"tasks": {"audit": {"lastStartedAt": "2026-03-20T08:00:00"}}}
        running_tasks = {"audit": self._FakeProcess(return_code=0)}

        changed = run_cycle(
            tasks=[task],
            state_payload=state_payload,
            running_tasks=running_tasks,
            log_dir=DEFAULT_LOG_DIR,
            now=datetime(2026, 3, 20, 8, 5, 0),
        )

        self.assertTrue(changed)
        self.assertEqual(running_tasks, {})
        self.assertIn("lastFinishedAt", state_payload["tasks"]["audit"])
        self.assertEqual(state_payload["tasks"]["audit"]["lastExitCode"], 0)

    def test_run_cycle_repairs_collect_state_when_process_exits_without_finish_write(self) -> None:
        task = TaskConfig(
            name="collect",
            script="automation/scripts/run_collect_task.ps1",
            args=[],
            enabled=True,
            interval_minutes=15,
            daily_times=[],
            run_on_startup=False,
        )
        state_payload = {
            "tasks": {
                "collect": {
                    "lastStartedAt": "2026-03-20T08:00:00",
                    "lastMessage": COLLECT_TASK_RUNNING_MESSAGE,
                }
            }
        }
        running_tasks = {"collect": self._FakeProcess(return_code=1)}

        changed = run_cycle(
            tasks=[task],
            state_payload=state_payload,
            running_tasks=running_tasks,
            log_dir=DEFAULT_LOG_DIR,
            now=datetime(2026, 3, 20, 8, 5, 0),
        )

        self.assertTrue(changed)
        self.assertEqual(running_tasks, {})
        self.assertIn("lastFinishedAt", state_payload["tasks"]["collect"])
        self.assertEqual(state_payload["tasks"]["collect"]["lastExitCode"], 1)
        self.assertEqual(state_payload["tasks"]["collect"]["lastMessage"], "采集任务异常结束（退出码 1），请查看日志")


if __name__ == "__main__":
    unittest.main()
