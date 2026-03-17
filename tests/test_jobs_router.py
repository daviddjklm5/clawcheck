from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from automation.api.routers.jobs import (
    MasterDataRunRequest,
    get_master_data,
    post_master_data_run,
)


class JobsRouterTest(unittest.TestCase):
    def test_get_master_data_returns_payload(self) -> None:
        payload = {"stats": [], "actions": [], "currentTask": None, "recentRuns": []}
        with patch("automation.api.routers.jobs.get_master_data_workbench", return_value=payload):
            result = get_master_data()
        self.assertEqual(result, payload)

    def test_post_master_data_run_forwards_payload(self) -> None:
        payload = {
            "taskId": "task-001",
            "taskType": "roster",
            "status": "queued",
            "message": "主数据任务已创建，等待执行。",
        }
        request = MasterDataRunRequest(
            taskType="roster",
            headed=None,
            dryRun=True,
            inputFile="/tmp/roster.xlsx",
            skipExport=False,
            skipImport=True,
            queryTimeoutSeconds=90,
            downloadTimeoutMinutes=20,
            scheme="在职花名册基础版",
            employmentType="全职任职",
            forceRefresh=True,
        )
        runtime_settings = SimpleNamespace(browser=SimpleNamespace(headed=False))
        with (
            patch("automation.api.routers.jobs._load_runtime_settings", return_value=(None, runtime_settings)),
            patch("automation.api.routers.jobs.start_master_data_task", return_value=payload) as mocked_start,
        ):
            result = post_master_data_run(request)
        self.assertEqual(result, payload)
        mocked_start.assert_called_once_with(
            task_type="roster",
            headed=False,
            dry_run=True,
            input_file="/tmp/roster.xlsx",
            skip_export=False,
            skip_import=True,
            query_timeout_seconds=90,
            download_timeout_minutes=20,
            scheme="在职花名册基础版",
            employment_type="全职任职",
            force_refresh=True,
        )

    def test_post_master_data_run_maps_value_error_to_400(self) -> None:
        request = MasterDataRunRequest(taskType="bad-task")
        runtime_settings = SimpleNamespace(browser=SimpleNamespace(headed=True))
        with (
            patch("automation.api.routers.jobs._load_runtime_settings", return_value=(None, runtime_settings)),
            patch("automation.api.routers.jobs.start_master_data_task", side_effect=ValueError("参数错误")),
        ):
            with self.assertRaises(HTTPException) as context:
                post_master_data_run(request)
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "参数错误")

    def test_post_master_data_run_maps_runtime_error_to_409(self) -> None:
        request = MasterDataRunRequest(taskType="roster")
        runtime_settings = SimpleNamespace(browser=SimpleNamespace(headed=True))
        with (
            patch("automation.api.routers.jobs._load_runtime_settings", return_value=(None, runtime_settings)),
            patch("automation.api.routers.jobs.start_master_data_task", side_effect=RuntimeError("任务冲突")),
        ):
            with self.assertRaises(HTTPException) as context:
                post_master_data_run(request)
        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail, "任务冲突")


if __name__ == "__main__":
    unittest.main()
