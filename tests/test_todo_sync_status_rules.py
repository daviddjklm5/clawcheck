from __future__ import annotations

import unittest

from automation.scripts.run import build_todo_process_status_by_document_no


class TodoSyncStatusRulesTest(unittest.TestCase):
    def test_rejected_documents_do_not_return_to_pending(self) -> None:
        result = build_todo_process_status_by_document_no(
            project_document_nos=["RA-1", "RA-2", "RA-3"],
            ehr_permission_document_no_set={"RA-1", "RA-2"},
            existing_sync_states={
                "RA-1": {"todo_process_status": "已驳回"},
                "RA-2": {"todo_process_status": "已处理"},
                "RA-3": {"todo_process_status": "待处理"},
            },
        )

        self.assertEqual(
            result,
            {
                "RA-1": "已驳回",
                "RA-2": "待处理",
                "RA-3": "已处理",
            },
        )


if __name__ == "__main__":
    unittest.main()
