from __future__ import annotations

import unittest
from unittest.mock import ANY, patch

from fastapi import HTTPException

from automation.api.routers.documents import (
    CollectRunRequest,
    get_collect_workbench_document,
    get_collect_workbench_documents,
    ProcessBatchApprovalRequest,
    ProcessDocumentApprovalRequest,
    ProcessAuditRunRequest,
    ProcessTodoSyncRequest,
    post_collect_workbench_run,
    get_process_analysis,
    post_process_workbench_batch_approval,
    get_process_workbench_document,
    get_process_workbench_documents,
    post_process_workbench_audit,
    post_process_workbench_document_approval,
    post_process_workbench_todo_sync,
)


class DocumentsRouterTest(unittest.TestCase):
    def test_get_collect_workbench_documents_returns_payload(self) -> None:
        payload = {"stats": [], "documents": [], "currentTask": None, "recentRuns": []}

        with patch("automation.api.routers.documents.get_collect_workbench", return_value=payload):
            result = get_collect_workbench_documents()

        self.assertEqual(result, payload)

    def test_get_collect_workbench_document_raises_404_when_detail_missing(self) -> None:
        with patch("automation.api.routers.documents.get_collect_document_detail", return_value=None):
            with self.assertRaises(HTTPException) as context:
                get_collect_workbench_document("RA-TEST-001")

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "未找到单据 RA-TEST-001 的采集详情")

    def test_post_collect_workbench_run_returns_payload(self) -> None:
        payload = {
            "id": "task-001",
            "taskId": "task-001",
            "status": "queued",
            "message": "采集任务已创建，等待执行。",
        }
        request = CollectRunRequest(
            documentNo="RA-TEST-001",
            limit=1,
            dryRun=True,
            autoAudit=False,
            forceRecollect=True,
        )

        with patch("automation.api.routers.documents.start_collect_task", return_value=payload) as mocked_start:
            result = post_collect_workbench_run(request)

        self.assertEqual(result, payload)
        mocked_start.assert_called_once_with(
            document_no="RA-TEST-001",
            limit=1,
            headed=ANY,
            dry_run=True,
            auto_audit=False,
            force_recollect=True,
        )

    def test_get_process_workbench_documents_returns_payload(self) -> None:
        payload = {"stats": [], "documents": []}

        with patch("automation.api.routers.documents.get_process_workbench", return_value=payload):
            result = get_process_workbench_documents()

        self.assertEqual(result, payload)

    def test_get_process_analysis_returns_payload(self) -> None:
        payload = {"latestBatch": None, "distributionSections": [], "executionLogs": []}

        with patch("automation.api.routers.documents.get_process_analysis_dashboard", return_value=payload):
            result = get_process_analysis()

        self.assertEqual(result, payload)

    def test_get_process_workbench_document_raises_404_when_detail_missing(self) -> None:
        with patch("automation.api.routers.documents.get_process_document_detail", return_value=None):
            with self.assertRaises(HTTPException) as context:
                get_process_workbench_document("RA-TEST-001", "")

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "未找到单据 RA-TEST-001 的评估详情")

    def test_get_process_workbench_document_returns_detail_with_apply_reason(self) -> None:
        payload = {
            "documentNo": "RA-TEST-001",
            "applyReason": "跨组织协作，需要临时审批处理权限。",
            "overviewFields": [],
            "feedbackOverview": {"summaryConclusionLabel": "-", "feedbackStats": [], "feedbackGroups": [], "feedbackLines": []},
            "roles": [],
            "approvals": [],
            "orgScopes": [],
            "riskDetails": [],
            "notes": [],
        }

        with patch("automation.api.routers.documents.get_process_document_detail", return_value=payload) as mocked_detail:
            result = get_process_workbench_document("RA-TEST-001", "  BATCH-001  ")

        self.assertEqual(result, payload)
        self.assertEqual(result["applyReason"], "跨组织协作，需要临时审批处理权限。")
        mocked_detail.assert_called_once_with(
            document_no="RA-TEST-001",
            assessment_batch_no="BATCH-001",
        )

    def test_post_process_workbench_audit_forwards_document_nos(self) -> None:
        payload = {
            "taskId": "audit-001",
            "status": "queued",
            "requestedDocumentNos": ["RA-TEST-001", "RA-TEST-002"],
        }
        request = ProcessAuditRunRequest(
            documentNo="RA-TEST-001",
            documentNos=["RA-TEST-002"],
            limit=2,
            dryRun=False,
        )

        with patch("automation.api.routers.documents.start_audit_task", return_value=payload) as mocked_start:
            result = post_process_workbench_audit(request)

        self.assertEqual(result, payload)
        mocked_start.assert_called_once_with(
            document_no="RA-TEST-001",
            document_nos=["RA-TEST-002"],
            limit=2,
            dry_run=False,
        )

    def test_post_process_workbench_document_approval_returns_payload(self) -> None:
        payload = {
            "documentNo": "RA-TEST-001",
            "action": "approve",
            "status": "succeeded",
            "message": "ok",
        }
        request = ProcessDocumentApprovalRequest(
            action="approve",
            approvalOpinion="同意",
            dryRun=False,
        )

        with patch("automation.api.routers.documents.approve_process_document", return_value=payload):
            result = post_process_workbench_document_approval("RA-TEST-001", request)

        self.assertEqual(result, payload)

    def test_post_process_workbench_document_reject_returns_payload(self) -> None:
        payload = {
            "documentNo": "RA-TEST-001",
            "action": "reject",
            "status": "succeeded",
            "message": "ok",
        }
        request = ProcessDocumentApprovalRequest(
            action="reject",
            approvalOpinion="审批链缺少战区人行部门审批，建议拒绝或补齐审批链。",
            dryRun=True,
        )

        with patch("automation.api.routers.documents.approve_process_document", return_value=payload):
            result = post_process_workbench_document_approval("RA-TEST-001", request)

        self.assertEqual(result, payload)

    def test_post_process_workbench_batch_approval_returns_payload(self) -> None:
        payload = {
            "action": "approve",
            "status": "partial",
            "succeededCount": 1,
            "pendingConfirmationCount": 1,
            "failedCount": 1,
            "results": [],
            "message": "批量批准完成：成功 1，待确认 1，失败 1，共 3 条。",
        }
        request = ProcessBatchApprovalRequest(
            action="approve",
            documentNos=["RA-TEST-001", "RA-TEST-002", "RA-TEST-003"],
            dryRun=False,
        )

        with patch("automation.api.routers.documents.approve_process_documents_batch", return_value=payload) as mocked_batch:
            result = post_process_workbench_batch_approval(request)

        self.assertEqual(result, payload)
        mocked_batch.assert_called_once_with(
            document_nos=["RA-TEST-001", "RA-TEST-002", "RA-TEST-003"],
            action="approve",
            dry_run=False,
            headed=ANY,
        )

    def test_post_process_workbench_todo_sync_returns_payload(self) -> None:
        payload = {
            "taskId": "sync-001",
            "status": "succeeded",
            "processedCount": 3,
            "message": "待办状态同步完成",
        }
        request = ProcessTodoSyncRequest(dryRun=False)

        with patch("automation.api.routers.documents.run_process_todo_sync_now", return_value=payload) as mocked_sync:
            result = post_process_workbench_todo_sync(request)

        self.assertEqual(result, payload)
        mocked_sync.assert_called_once_with(dry_run=False, headed=ANY)


if __name__ == "__main__":
    unittest.main()
