from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from automation.api.routers.documents import (
    CollectRunRequest,
    get_collect_workbench_document,
    get_collect_workbench_documents,
    ProcessDocumentApprovalRequest,
    post_collect_workbench_run,
    get_process_analysis,
    get_process_workbench_document,
    get_process_workbench_documents,
    post_process_workbench_document_approval,
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
        request = CollectRunRequest(documentNo="RA-TEST-001", limit=1, dryRun=True)

        with patch("automation.api.routers.documents.start_collect_task", return_value=payload):
            result = post_collect_workbench_run(request)

        self.assertEqual(result, payload)

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


if __name__ == "__main__":
    unittest.main()
