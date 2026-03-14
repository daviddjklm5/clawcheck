from __future__ import annotations

import unittest

from automation.utils.approval_record_helpers import (
    collect_unresolved_approver_names,
    derive_latest_approval_time,
    normalize_approval_records,
)


class ApprovalRecordHelpersTest(unittest.TestCase):
    def test_normalize_approval_records_filters_empty_step_and_extracts_employee_no(self) -> None:
        records = [
            {
                "record_seq": "9",
                "node_name": "属地人力资源部负责人",
                "approver_name": "",
                "approval_action": "",
                "approval_time": "",
                "raw_text": "属地人力资源部负责人 通过规则：全部通过",
            },
            {
                "record_seq": "10",
                "node_name": "部门负责人",
                "approver_name": "何颖(00769528)",
                "approver_org_or_position": "组织发展负责人",
                "approval_action": "同意",
                "approval_opinion": "",
                "approval_time": "2026-03-14 09:30:00",
                "raw_text": "部门负责人 何颖(00769528)|组织发展负责人 同意 2026-03-14 09:30:00",
            },
            {
                "record_seq": "11",
                "node_name": "人力资源共享中心",
                "approver_name": "张三",
                "approver_org_or_position": "HRBP",
                "approval_action": "待审核",
                "approval_opinion": "",
                "approval_time": "2026-03-14 10:00:00",
                "raw_text": "人力资源共享中心 张三|HRBP 待审核 2026-03-14 10:00:00",
            },
        ]

        normalized_records = normalize_approval_records(
            records,
            approver_employee_no_by_name={"张三": "00000001"},
        )

        self.assertEqual(len(normalized_records), 2)
        self.assertEqual(normalized_records[0]["record_seq"], "1")
        self.assertEqual(normalized_records[0]["approver_name"], "何颖")
        self.assertEqual(normalized_records[0]["approver_employee_no"], "00769528")
        self.assertEqual(normalized_records[1]["record_seq"], "2")
        self.assertEqual(normalized_records[1]["approver_name"], "张三")
        self.assertEqual(normalized_records[1]["approver_employee_no"], "00000001")

    def test_collect_unresolved_approver_names_only_returns_blank_employee_no_names(self) -> None:
        records = [
            {"approver_name": "何颖", "approver_employee_no": "00769528"},
            {"approver_name": "张三", "approver_employee_no": ""},
            {"approver_name": "李四", "approver_employee_no": None},
            {"approver_name": "", "approver_employee_no": ""},
        ]

        self.assertEqual(collect_unresolved_approver_names(records), {"张三", "李四"})

    def test_derive_latest_approval_time_uses_last_kept_record(self) -> None:
        records = [
            {"approval_time": "2026-03-14 09:30:00"},
            {"approval_time": "2026-03-14 10:00:00"},
        ]

        self.assertEqual(derive_latest_approval_time(records), "2026-03-14 10:00:00")
        self.assertEqual(derive_latest_approval_time([]), "")


if __name__ == "__main__":
    unittest.main()
