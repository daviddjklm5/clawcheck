from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from automation.api import process_dashboard


class ProcessDashboardBatchApprovalTest(unittest.TestCase):
    def test_resolve_batch_approval_opinion_reuses_generated_reject_lines(self) -> None:
        store = MagicMock()
        store.fetch_process_document_detail.return_value = {
            "feedbackOverview": {
                "feedbackGroups": [
                    {
                        "summaryLines": ["审批链缺少区域负责人", "申请组织超出当前岗位职责范围"],
                    }
                ]
            }
        }

        result = process_dashboard._resolve_batch_approval_opinion(
            store=store,
            document_no="RA-TEST-001",
            action="reject",
        )

        self.assertEqual(result, "审批链缺少区域负责人\n申请组织超出当前岗位职责范围")
        store.fetch_process_document_detail.assert_called_once_with(document_no="RA-TEST-001")

    def test_approve_process_documents_batch_tracks_pending_confirmation_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            logs_dir = temp_path / "logs"
            screenshots_dir = temp_path / "screenshots"
            state_file = temp_path / "state" / "approval.json"
            logs_dir.mkdir(parents=True, exist_ok=True)
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            state_file.parent.mkdir(parents=True, exist_ok=True)

            settings = SimpleNamespace(
                browser=SimpleNamespace(headed=True),
                db=object(),
            )
            fake_permission_store = MagicMock()
            fake_risk_store = MagicMock()
            fake_page = object()
            fake_context = object()

            run_results = [
                (
                    {
                        "documentNo": "RA-TEST-001",
                        "status": "succeeded",
                        "message": "ok",
                        "logFile": "automation/logs/approval_1.json",
                    },
                    fake_page,
                ),
                (
                    {
                        "documentNo": "RA-TEST-002",
                        "status": "submitted_pending_confirmation",
                        "message": "提交动作已发出，但当前未拿到强成功回执。",
                        "logFile": "automation/logs/approval_2.json",
                    },
                    fake_page,
                ),
                (
                    {
                        "documentNo": "RA-TEST-003",
                        "status": "failed",
                        "message": "EHR 页面未找到提交按钮",
                        "logFile": "automation/logs/approval_3.json",
                    },
                    fake_page,
                ),
            ]

            with (
                patch.object(
                    process_dashboard,
                    "_prepare_approval_runtime",
                    return_value=(
                        temp_path / "settings.yaml",
                        settings,
                        temp_path / "credentials.yaml",
                        {},
                        logs_dir,
                        screenshots_dir,
                        state_file,
                    ),
                ),
                patch.object(process_dashboard, "PostgresPermissionStore", return_value=fake_permission_store),
                patch.object(process_dashboard, "PostgresRiskTrustStore", return_value=fake_risk_store),
                patch.object(
                    process_dashboard,
                    "run_process_todo_sync_now",
                    return_value={
                        "status": "succeeded",
                        "pendingCount": 3,
                        "processedCount": 8,
                        "changedCount": 2,
                        "dumpFile": "automation/logs/todo_sync_1.json",
                        "logFile": "automation/logs/run_1.log",
                        "message": "待办状态同步完成",
                    },
                ) as mocked_todo_sync,
                patch.object(
                    process_dashboard,
                    "acquire_approval_browser_session",
                    return_value=("browser", fake_context, fake_page, {"reused": False, "pageRecreated": False}),
                ) as mocked_acquire,
                patch.object(process_dashboard, "release_approval_browser_session") as mocked_release,
                patch.object(
                    process_dashboard,
                    "_resolve_batch_approval_opinion",
                    side_effect=["通过", "请补齐审批链", "请检查组织范围"],
                ) as mocked_resolve_opinion,
                patch.object(
                    process_dashboard,
                    "_run_logged_document_approval_in_active_session",
                    side_effect=run_results,
                ) as mocked_run,
            ):
                result = process_dashboard.approve_process_documents_batch(
                    document_nos=["RA-TEST-001", "RA-TEST-002", "RA-TEST-002", "RA-TEST-003"],
                    action="approve",
                    dry_run=False,
                    headed=True,
                )

        mocked_todo_sync.assert_called_once_with(dry_run=False, headed=True)
        mocked_acquire.assert_called_once()
        mocked_release.assert_called_once_with(
            close_session=True,
            close_reason="batch_approval_request_finished",
        )
        self.assertEqual(mocked_resolve_opinion.call_count, 3)
        self.assertEqual(mocked_run.call_count, 3)
        self.assertEqual(result["documentNos"], ["RA-TEST-001", "RA-TEST-002", "RA-TEST-003"])
        self.assertEqual(result["succeededCount"], 1)
        self.assertEqual(result["pendingConfirmationCount"], 1)
        self.assertEqual(result["failedCount"], 1)
        self.assertEqual(result["status"], "partial")
        self.assertIn("待确认 1", result["message"])
        self.assertEqual([item["status"] for item in result["results"]], ["succeeded", "submitted_pending_confirmation", "failed"])

    def test_approve_process_documents_batch_fails_fast_when_todo_sync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            logs_dir = temp_path / "logs"
            screenshots_dir = temp_path / "screenshots"
            state_file = temp_path / "state" / "approval.json"
            logs_dir.mkdir(parents=True, exist_ok=True)
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            state_file.parent.mkdir(parents=True, exist_ok=True)

            settings = SimpleNamespace(
                browser=SimpleNamespace(headed=True),
                db=object(),
            )

            with (
                patch.object(
                    process_dashboard,
                    "_prepare_approval_runtime",
                    return_value=(
                        temp_path / "settings.yaml",
                        settings,
                        temp_path / "credentials.yaml",
                        {},
                        logs_dir,
                        screenshots_dir,
                        state_file,
                    ),
                ),
                patch.object(process_dashboard, "PostgresPermissionStore", return_value=MagicMock()),
                patch.object(process_dashboard, "PostgresRiskTrustStore", return_value=MagicMock()),
                patch.object(
                    process_dashboard,
                    "run_process_todo_sync_now",
                    side_effect=RuntimeError("EHR 待办页打开失败"),
                ) as mocked_todo_sync,
                patch.object(process_dashboard, "acquire_approval_browser_session") as mocked_acquire,
            ):
                result = process_dashboard.approve_process_documents_batch(
                    document_nos=["RA-TEST-001", "RA-TEST-002"],
                    action="approve",
                    dry_run=False,
                    headed=True,
                )

        mocked_todo_sync.assert_called_once_with(dry_run=False, headed=True)
        mocked_acquire.assert_not_called()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["failedCount"], 2)
        self.assertTrue(all(item["status"] == "failed" for item in result["results"]))
        self.assertIn("同步待办状态失败", result["results"][0]["message"])


if __name__ == "__main__":
    unittest.main()
