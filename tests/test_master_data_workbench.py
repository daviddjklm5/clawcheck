from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from automation.api.master_data_workbench import get_master_data_workbench


class MasterDataWorkbenchTest(unittest.TestCase):
    def test_get_master_data_workbench_returns_degraded_stats_when_db_unavailable(self) -> None:
        runtime_settings = SimpleNamespace(
            runtime=SimpleNamespace(logs_dir="automation/logs"),
            db=SimpleNamespace(),
        )
        store_instance = SimpleNamespace()
        store_instance.fetch_master_data_workbench = lambda: (_ for _ in ()).throw(RuntimeError("db unavailable"))

        with (
            patch("automation.api.master_data_workbench._load_runtime_settings", return_value=(None, runtime_settings)),
            patch("automation.api.master_data_workbench.PostgresMasterDataStore", return_value=store_instance),
            patch("automation.api.master_data_workbench._load_recent_runs", return_value=[]),
        ):
            payload = get_master_data_workbench()

        self.assertIn("stats", payload)
        self.assertIn("actions", payload)
        self.assertEqual(payload["currentTask"], None)
        self.assertEqual(payload["recentRuns"], [])
        db_status = next(item for item in payload["stats"] if item["label"] == "数据库连接状态")
        self.assertEqual(db_status["value"], "异常")
        self.assertIn("主数据摘要查询失败", db_status["hint"])


if __name__ == "__main__":
    unittest.main()
