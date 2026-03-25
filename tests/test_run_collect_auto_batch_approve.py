from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from automation.scripts.run import (
    _resolve_collect_auto_batch_approve_candidates,
    _run_collect_auto_batch_approve,
)


class RunCollectAutoBatchApproveTest(unittest.TestCase):
    def test_resolve_collect_auto_batch_approve_candidates_filters_by_status_and_score(self) -> None:
        fake_store = Mock()
        fake_store.fetch_process_workbench.return_value = {
            "documents": [
                {"documentNo": "RA-001", "todoProcessStatus": "待处理", "finalScore": 2.0},
                {"documentNo": "RA-002", "todoProcessStatus": "待处理", "finalScore": 2.5},
                {"documentNo": "RA-003", "todoProcessStatus": "待处理", "finalScore": 3.0},
                {"documentNo": "RA-004", "todoProcessStatus": "已处理", "finalScore": 2.0},
            ]
        }
        logger = Mock()

        with patch("automation.db.postgres.PostgresRiskTrustStore", return_value=fake_store):
            result = _resolve_collect_auto_batch_approve_candidates(
                settings=SimpleNamespace(db=SimpleNamespace()),
                document_nos=["RA-001", "RA-002", "RA-003", "RA-004", "RA-005"],
                logger=logger,
            )

        self.assertEqual(result["candidates"], ["RA-001", "RA-002"])
        self.assertEqual(result["target_scores"], [2.0, 2.5])

    def test_run_collect_auto_batch_approve_returns_skipped_when_no_candidate(self) -> None:
        logger = Mock()
        settings = SimpleNamespace(browser=SimpleNamespace(headed=False), db=SimpleNamespace())

        with (
            patch(
                "automation.scripts.run._resolve_collect_auto_batch_approve_candidates",
                return_value={"candidates": [], "target_scores": [2.0, 2.5]},
            ),
            patch("automation.api.process_dashboard.approve_process_documents_batch") as mocked_batch_approve,
        ):
            result = _run_collect_auto_batch_approve(
                settings=settings,
                document_nos=["RA-001"],
                logger=logger,
            )

        self.assertEqual(result["status"], "skipped")
        mocked_batch_approve.assert_not_called()

    def test_run_collect_auto_batch_approve_calls_batch_approve(self) -> None:
        logger = Mock()
        settings = SimpleNamespace(browser=SimpleNamespace(headed=True), db=SimpleNamespace())

        with (
            patch(
                "automation.scripts.run._resolve_collect_auto_batch_approve_candidates",
                return_value={"candidates": ["RA-001", "RA-002"], "target_scores": [2.0, 2.5]},
            ),
            patch(
                "automation.api.process_dashboard.approve_process_documents_batch",
                return_value={"status": "succeeded", "message": "ok", "logFile": "automation/logs/batch.json"},
            ) as mocked_batch_approve,
        ):
            result = _run_collect_auto_batch_approve(
                settings=settings,
                document_nos=["RA-001", "RA-002"],
                logger=logger,
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["log_file"], "automation/logs/batch.json")
        mocked_batch_approve.assert_called_once_with(
            document_nos=["RA-001", "RA-002"],
            action="approve",
            dry_run=False,
            headed=True,
        )


if __name__ == "__main__":
    unittest.main()
