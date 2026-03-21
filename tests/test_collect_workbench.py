from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from automation.api import collect_workbench
from automation.db.postgres import PostgresPermissionStore
from automation.utils.config_loader import DatabaseSettings


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
        force_recollect: bool = False,
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
            "forceRecollect": force_recollect,
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
                ) as mocked_run,
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
            command = mocked_run.call_args.kwargs["args"] if "args" in mocked_run.call_args.kwargs else mocked_run.call_args.args[0]
            self.assertIn("--headless", command)

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

    def test_run_collect_task_appends_force_recollect_flag(self) -> None:
        with TemporaryDirectory() as temp_dir:
            task_state = self._build_task_state(
                temp_dir,
                task_id="task-force",
                requested_document_no="RA-TEST-999",
                auto_audit=False,
                dry_run=False,
                force_recollect=True,
            )
            collect_workbench._TASK_STATE_BY_ID["task-force"] = task_state
            dump_file = Path(str(task_state["dumpFile"]))
            dump_payload = [{"basic_info": {"document_no": "RA-TEST-999"}}]
            runtime_settings = SimpleNamespace(runtime=SimpleNamespace(logs_dir=temp_dir))

            with (
                patch("automation.api.collect_workbench._load_runtime_settings", return_value=(None, runtime_settings)),
                patch(
                    "automation.api.collect_workbench.subprocess.run",
                    return_value=_FakeCompletedProcess(
                        returncode=0,
                        stdout="Log file: /tmp/run_collect.log",
                    ),
                ) as mocked_run,
                patch(
                    "automation.api.collect_workbench._load_json_file",
                    side_effect=lambda path: dump_payload if path == dump_file else None,
                ),
                patch("automation.api.collect_workbench._count_from_sidecar", return_value=0),
            ):
                collect_workbench._run_collect_task("task-force")

            command = mocked_run.call_args.kwargs["args"] if "args" in mocked_run.call_args.kwargs else mocked_run.call_args.args[0]
            self.assertIn("--headless", command)
            self.assertIn("--force-recollect", command)


if __name__ == "__main__":
    unittest.main()


class _FakeCursor:
    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor


class CollectWorkbenchVisibilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = PostgresPermissionStore(
            DatabaseSettings(
                host="localhost",
                port=5432,
                dbname="clawcheck",
                user="tester",
                password="tester",
                schema="public",
                sslmode="disable",
            )
        )
        self.cursor = _FakeCursor()
        self.connection = _FakeConnection(self.cursor)

    def _fake_connect(self):
        class _Ctx:
            def __enter__(_self):
                return self.connection

            def __exit__(_self, exc_type, exc, tb):
                return None

        return _Ctx()

    def test_fetch_collect_workbench_only_includes_documents_with_process_results(self) -> None:
        assessed_basic_rows = [
            {
                "document_no": "RA-TEST-001",
                "employee_no": "0001",
                "permission_target": "张三",
                "apply_reason": "测试",
                "document_status": "已提交",
                "hr_org": "万物云",
                "company_name": "万物云本部",
                "department_name": "人事部",
                "position_name": "人事经理",
                "apply_time": None,
                "latest_approval_time": None,
                "collection_count": 1,
                "updated_at": None,
            }
        ]

        with (
            patch.object(self.store, "ensure_table"),
            patch.object(self.store, "connect", self._fake_connect),
            patch(
                "automation.db.postgres.PostgresRiskTrustStore._fetch_latest_process_summary_rows",
                return_value=[
                    {"document_no": "RA-TEST-001"},
                ],
            ) as mocked_latest_process_rows,
            patch(
                "automation.db.postgres.PostgresRiskTrustStore._fetch_basic_info_rows",
                return_value=assessed_basic_rows,
            ) as mocked_basic_rows,
            patch.object(
                self.store,
                "_fetch_collect_table_metrics",
                return_value={
                    "RA-TEST-001": {
                        "permission": {"records": 1},
                        "approval": {"records": 1},
                        "orgScope": {"records": 1},
                        "basic": {"updated_at": None},
                    }
                },
            ),
            patch(
                "automation.db.postgres.PostgresRiskTrustStore._fetch_person_attributes_map",
                return_value={"0001": {"employee_name": "张三"}},
            ),
        ):
            result = self.store.fetch_collect_workbench()

        mocked_latest_process_rows.assert_called_once_with(self.cursor)
        mocked_basic_rows.assert_called_once_with(
            self.cursor,
            document_no=None,
            limit=200,
            document_nos=["RA-TEST-001"],
        )
        self.assertEqual(result["stats"][0]["label"], "已进入处理单据")
        self.assertEqual(result["stats"][0]["value"], "1")
        self.assertEqual([row["documentNo"] for row in result["documents"]], ["RA-TEST-001"])
