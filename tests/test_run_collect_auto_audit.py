from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from automation.scripts.run import _run_incremental_collect_audit


class RunCollectAutoAuditTest(unittest.TestCase):
    def test_run_incremental_collect_audit_returns_skipped_for_empty_document_list(self) -> None:
        logger = Mock()
        result = _run_incremental_collect_audit(
            settings=SimpleNamespace(db=SimpleNamespace()),
            logs_dir=Path("."),
            document_nos=[],
            logger=logger,
        )

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["document_count"], 0)
        logger.info.assert_not_called()

    def test_run_incremental_collect_audit_persists_results_and_dump(self) -> None:
        fake_store = Mock()
        fake_store.fetch_document_bundles.return_value = [{"basic_info": {"document_no": "RA-TEST-001"}}]
        fake_package = SimpleNamespace(version="2026.03.24")
        fake_evaluator = Mock()
        fake_evaluator.evaluate_documents_resilient.return_value = (
            [{"document_no": "RA-TEST-001", "assessment_batch_no": "placeholder", "assessment_version": "2026.03.24"}],
            [{"document_no": "RA-TEST-001"}],
            [],
        )
        logger = Mock()

        with TemporaryDirectory() as temp_dir:
            with (
                patch("automation.db.postgres.PostgresRiskTrustStore", return_value=fake_store),
                patch("automation.rules.load_risk_trust_package", return_value=fake_package),
                patch("automation.rules.RiskTrustEvaluator", return_value=fake_evaluator),
            ):
                result = _run_incremental_collect_audit(
                    settings=SimpleNamespace(db=SimpleNamespace()),
                    logs_dir=Path(temp_dir),
                    document_nos=["RA-TEST-001", "RA-TEST-001", ""],
                    logger=logger,
                )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["assessment_version"], "2026.03.24")
        self.assertEqual(result["failed_document_count"], 0)
        fake_store.fetch_document_bundles.assert_called_once_with(
            document_nos=["RA-TEST-001"],
            limit=1,
        )
        fake_store.write_assessment_results.assert_called_once()
        logger.info.assert_called()
        self.assertTrue(str(result["dump_file"]).endswith(".json"))


if __name__ == "__main__":
    unittest.main()
