from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from automation.api import collect_workbench


class _FakeCompletedProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class CollectWorkbenchTaskTest(unittest.TestCase):
    def tearDown(self) -> None:
        collect_workbench._TASK_STATE_BY_ID.clear()

    def _build_task_state(
        self,
        temp_dir: str,
        *,
        task_id: str = "task-001",
        requested_document_no: str = "RA-TEST-001",
        dry_run: bool = False,
        auto_audit: bool = True,
    ) -> dict[str, object]:
        return {
            "taskId": task_id,
            "status": "queued",
            "requestedAt": "2026-03-16 12:18:35",
            "startedAt": "",
            "finishedAt": "",
            "requestedDocumentNo": requested_document_no,
            "requestedLimit": 1,
            "dryRun": dry_run,
            "autoAudit": auto_audit,
            "requestedCount": 0,
            "successCount": 0,
            "skippedCount": 0,
            "failedCount": 0,
            "message": "采集任务已创建，等待执行。",
            "auditStatus": "",
            "auditBatchNo": "",
            "auditMessage": "",
            "auditLogFile": "",
            "dumpFile": str(Path(temp_dir) / f"{task_id}.json"),
            "skippedDumpFile": str(Path(temp_dir) / f"{task_id}_skipped.json"),
            "failedDumpFile": str(Path(temp_dir) / f"{task_id}_failed.json"),
            "summaryFile": str(Path(temp_dir) / f"{task_id}_summary.json"),
            "logFile": "",
            "outputTail": "",
        }

    def test_run_collect_task_triggers_audit_for_successful_auto_audit(self) -> None:
        with TemporaryDirectory() as temp_dir:
            task_state = self._build_task_state(temp_dir, auto_audit=True, dry_run=False)
            collect_workbench._TASK_STATE_BY_ID["task-001"] = task_state
            dump_file = Path(str(task_state["dumpFile"]))
            dump_payload = [{"basic_info": {"document_no": "RA-TEST-001"}}]
            runtime_settings = SimpleNamespace(runtime=SimpleNamespace(logs_dir=temp_dir))

            def _load_json_file(path: Path):
                if path == dump_file:
                    return dump_payload
                if path == Path(str(task_state["summaryFile"])):
                    return json.loads(Path(path).read_text(encoding="utf-8"))
                return None

            with (
                patch("automation.api.collect_workbench._load_runtime_settings", return_value=(None, runtime_settings)),
                patch(
                    "automation.api.collect_workbench.subprocess.run",
                    return_value=_FakeCompletedProcess(
                        returncode=0,
                        stdout="Log file: /tmp/run_collect.log",
                    ),
                ),
                patch("automation.api.collect_workbench._load_json_file", side_effect=_load_json_file),
                patch("automation.api.collect_workbench._count_from_sidecar", return_value=0),
                patch(
                    "automation.api.collect_workbench.run_audit_now",
                    return_value={
                        "status": "succeeded",
                        "assessmentBatchNo": "audit_20260316_121915",
                        "message": "评估执行完成",
                        "logFile": "automation/logs/run_20260316_121915.log",
                    },
                ) as mocked_audit,
            ):
                collect_workbench._run_collect_task("task-001")

            final_task = collect_workbench._TASK_STATE_BY_ID["task-001"]
            self.assertEqual(final_task["status"], "succeeded")
            self.assertEqual(final_task["successCount"], 1)
            self.assertEqual(final_task["auditStatus"], "succeeded")
            self.assertEqual(final_task["auditBatchNo"], "audit_20260316_121915")
            self.assertIn("已完成增量评估", str(final_task["message"]))
            mocked_audit.assert_called_once_with(
                document_nos=["RA-TEST-001"],
                limit=1,
                dry_run=False,
            )

            summary_payload = json.loads(Path(str(task_state["summaryFile"])).read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["auditBatchNo"], "audit_20260316_121915")
            self.assertEqual(summary_payload["auditStatus"], "succeeded")

    def test_run_collect_task_skips_audit_when_dry_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            task_state = self._build_task_state(temp_dir, auto_audit=True, dry_run=True)
            collect_workbench._TASK_STATE_BY_ID["task-001"] = task_state
            dump_file = Path(str(task_state["dumpFile"]))
            dump_payload = [{"basic_info": {"document_no": "RA-TEST-001"}}]
            runtime_settings = SimpleNamespace(runtime=SimpleNamespace(logs_dir=temp_dir))

            with (
                patch("automation.api.collect_workbench._load_runtime_settings", return_value=(None, runtime_settings)),
                patch(
                    "automation.api.collect_workbench.subprocess.run",
                    return_value=_FakeCompletedProcess(
                        returncode=0,
                        stdout="Log file: /tmp/run_collect.log",
                    ),
                ),
                patch(
                    "automation.api.collect_workbench._load_json_file",
                    side_effect=lambda path: dump_payload if path == dump_file else None,
                ),
                patch("automation.api.collect_workbench._count_from_sidecar", return_value=0),
                patch("automation.api.collect_workbench.run_audit_now") as mocked_audit,
            ):
                collect_workbench._run_collect_task("task-001")

            final_task = collect_workbench._TASK_STATE_BY_ID["task-001"]
            self.assertEqual(final_task["status"], "succeeded")
            self.assertEqual(final_task["successCount"], 1)
            self.assertEqual(final_task["auditStatus"], "")
            self.assertEqual(final_task["auditBatchNo"], "")
            self.assertIn("dry-run", str(final_task["message"]))
            mocked_audit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
