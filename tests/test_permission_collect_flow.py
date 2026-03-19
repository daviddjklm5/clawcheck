from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from automation.flows.permission_collect_flow import PermissionCollectFlow
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class PermissionCollectFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.page = MagicMock()
        self.logger = MagicMock()
        self.flow = PermissionCollectFlow(
            page=self.page,
            logger=self.logger,
            timeout_ms=2000,
            home_url="https://example.com",
        )

    def test_set_grid_horizontal_position_targets_sticky_scroll(self) -> None:
        self.flow._set_grid_horizontal_position("#entryentity", 0.5)

        script, payload = self.page.evaluate.call_args.args
        self.assertIn("kd-sticky-scroll", script)
        self.assertEqual(payload, {"selector": "#entryentity", "ratio": 0.5})
        self.page.wait_for_timeout.assert_called_once_with(150)

    def test_detail_link_horizontal_ratios_start_from_middle(self) -> None:
        self.assertEqual(
            self.flow._detail_link_horizontal_ratios(),
            (None, 0.5, 0.0, 0.75, 0.25, 1.0),
        )

    def test_focus_detail_row_passes_line_no_and_row_index(self) -> None:
        self.page.evaluate.return_value = True

        matched = self.flow._focus_detail_row("#entryentity", 3, "14")

        self.assertTrue(matched)
        script, payload = self.page.evaluate.call_args.args
        self.assertIn('data-clawcheck-target-row', script)
        self.assertEqual(
            payload,
            {
                "selector": "#entryentity",
                "rowIndex": 3,
                "lineNo": "14",
            },
        )

    def test_wait_for_detail_link_ready_uses_marked_target_row(self) -> None:
        row_collection = MagicMock()
        row_locator = MagicMock()
        row_collection.first = row_locator

        cell_link = MagicMock()
        cell_link.count.return_value = 1
        row_locator.locator.return_value.filter.return_value.first = cell_link

        self.page.locator.return_value = row_collection

        with (
            patch.object(self.flow, "_focus_detail_row", return_value=True),
            patch.object(self.flow, "_set_grid_horizontal_position"),
        ):
            result = self.flow._wait_for_detail_link_ready(
                document_no="RA-20260311-00019907",
                grid_selector="#entryentity",
                row_idx=0,
                detail_row={"line_no": "1"},
            )

        self.assertIs(result, cell_link)
        self.page.locator.assert_called_once_with(
            '#entryentity tbody tr[data-clawcheck-target-row="true"]'
        )
        row_locator.wait_for.assert_called_once_with(state="visible", timeout=1000)

    def test_wait_for_detail_link_ready_scans_middle_before_other_positions(self) -> None:
        row_collection = MagicMock()
        row_locator = MagicMock()
        row_collection.first = row_locator

        cell_link = MagicMock()
        cell_link.count.side_effect = [0, 0, 1]
        row_locator.locator.return_value.filter.return_value.first = cell_link

        self.page.locator.return_value = row_collection

        with (
            patch.object(self.flow, "_focus_detail_row", return_value=True),
            patch.object(self.flow, "_set_grid_horizontal_position") as set_position,
        ):
            result = self.flow._wait_for_detail_link_ready(
                document_no="RA-20260313-00019984",
                grid_selector="#entryentity",
                row_idx=0,
                detail_row={"line_no": "1"},
            )

        self.assertIs(result, cell_link)
        self.assertEqual(
            [call.args for call in set_position.call_args_list],
            [
                ("#entryentity", 0.5),
                ("#entryentity", 0.0),
            ],
        )

    def test_collect_current_document_filters_empty_approval_steps_and_sets_latest_time(self) -> None:
        with (
            patch.object(self.flow, "extract_basic_info", return_value={"单据编号": "QX-1", "工号": "05026859"}),
            patch.object(self.flow, "_wait_for_permission_detail_grid_ready"),
            patch.object(self.flow, "extract_grid_rows", return_value=[]),
            patch.object(self.flow, "extract_role_organization_scopes", return_value=[]),
            patch.object(
                self.flow,
                "extract_approval_records",
                return_value=[
                    {
                        "record_seq": "1",
                        "node_name": "属地人力资源部负责人",
                        "approver_name": "",
                        "approver_org_or_position": "",
                        "approval_action": "",
                        "approval_opinion": "",
                        "approval_time": "",
                        "raw_text": "属地人力资源部负责人 通过规则：全部通过",
                    },
                    {
                        "record_seq": "2",
                        "node_name": "部门负责人",
                        "approver_name": "何颖(00769528)",
                        "approver_org_or_position": "负责人",
                        "approval_action": "同意",
                        "approval_opinion": "",
                        "approval_time": "2026-03-14 10:00:00",
                        "raw_text": "部门负责人 何颖(00769528)|负责人 同意 2026-03-14 10:00:00",
                    },
                ],
            ),
        ):
            document = self.flow.collect_current_document()

        self.assertEqual(document["basic_info"]["latest_approval_time"], "2026-03-14 10:00:00")
        self.assertEqual(len(document["approval_records"]), 1)
        self.assertEqual(document["approval_records"][0]["approver_name"], "何颖")
        self.assertEqual(document["approval_records"][0]["approver_employee_no"], "00769528")

    def test_extract_role_organization_scopes_skips_configured_skip_org_scope_role(self) -> None:
        flow = PermissionCollectFlow(
            page=self.page,
            logger=self.logger,
            timeout_ms=2000,
            home_url="https://example.com",
            skip_org_scope_role_codes={"qbireport"},
        )
        detail_rows = [
            {
                "line_no": "6",
                "role_code": "qbireport",
                "role_name": "QBI报表权限申请",
                "org_scope_count": None,
            }
        ]

        with (
            patch.object(flow, "_wait_for_permission_detail_grid_ready", return_value={"selector": "#entryentity"}),
            patch.object(flow, "_wait_for_grid_row_ready"),
            patch.object(flow, "_wait_for_detail_link_ready") as wait_link,
        ):
            scopes = flow.extract_role_organization_scopes("RA-20260316-00020066", detail_rows)

        self.assertEqual(
            scopes,
            [
                {
                    "line_no": "6",
                    "role_code": "qbireport",
                    "role_name": "QBI报表权限申请",
                    "organization_codes": [],
                }
            ],
        )
        wait_link.assert_not_called()
        self.logger.info.assert_called_once()

    def test_collect_approval_record_cards_uses_scrollable_tabpage_script(self) -> None:
        self.page.evaluate.return_value = []

        self.flow._collect_approval_record_cards()

        script, selector = self.page.evaluate.call_args.args
        self.assertIn("scrollTop", script)
        self.assertEqual(selector, "#tabpageap_approvalrecord")

    def test_extract_grid_rows_uses_virtual_scroll_for_detail_grid(self) -> None:
        detail_grid = {
            "headers": ["#", "申请类型", "角色名称", "角色编码", "角色描述", "参保单位", "行政组织详情"],
            "rows": [["1", "新增角色", "EP查看", "EP002", "", "", "查看详情(1)"]],
            "selector": "#entryentity",
        }
        full_rows = [
            ["1", "新增角色", "EP查看", "EP002", "", "", "查看详情(1)"],
            ["2", "新增角色", "EP维护", "EP001", "", "", "查看详情(1)"],
        ]
        with (
            patch.object(self.flow, "_extract_best_grid", return_value=detail_grid),
            patch.object(self.flow, "_extract_all_detail_grid_rows", return_value=full_rows) as extract_all,
        ):
            rows = self.flow.extract_grid_rows(["申请类型", "角色名称", "角色编码"])

        extract_all.assert_called_once_with(detail_grid)
        self.assertEqual([row["line_no"] for row in rows], ["1", "2"])
        self.assertEqual([row["role_code"] for row in rows], ["EP002", "EP001"])

    def test_extract_all_detail_grid_rows_deduplicates_and_sorts_by_line_no(self) -> None:
        detail_grid = {
            "headers": ["#", "申请类型", "角色名称", "角色编码", "角色描述", "参保单位", "行政组织详情"],
            "rows": [],
            "selector": "#entryentity",
        }
        snapshots = [
            {
                "rows": [
                    ["2", "新增角色", "EP维护", "EP001", "", "", "查看详情(1)"],
                    ["1", "新增角色", "EP查看", "EP002", "", "", "查看详情(1)"],
                ],
                "scrollTop": 0,
                "scrollHeight": 1200,
                "clientHeight": 300,
            },
            {
                "rows": [
                    ["3", "新增角色", "考勤核算（定额新增）", "JQ002", "", "", "查看详情(1)"],
                    ["2", "新增角色", "EP维护", "EP001", "", "", "查看详情(1)"],
                ],
                "scrollTop": 260,
                "scrollHeight": 1200,
                "clientHeight": 300,
            },
            None,
        ]

        with (
            patch.object(self.flow, "_get_grid_virtual_snapshot", side_effect=snapshots),
            patch.object(self.flow, "_set_grid_vertical_position"),
        ):
            rows = self.flow._extract_all_detail_grid_rows(detail_grid)

        self.assertEqual([row[0] for row in rows], ["1", "2", "3"])

    def test_parse_approval_record_cards_preserves_multi_round_records(self) -> None:
        records = [
            {
                "record_seq": "1",
                "header_text": "权限申请提交 何颖(00769528)|人力业务支持专业经理 提交",
                "approval_time": "2026-03-12 09:42:23",
                "approval_opinion": "提交",
                "raw_text": "权限申请提交 何颖(00769528)|人力业务支持专业经理 提交 2026-03-12 09:42:23 提交",
            },
            {
                "record_seq": "5",
                "header_text": "权限申请提交 何颖(00769528)|人力业务支持专业经理 提交",
                "approval_time": "2026-03-13 15:46:49",
                "approval_opinion": "提交",
                "raw_text": "权限申请提交 何颖(00769528)|人力业务支持专业经理 提交 2026-03-13 15:46:49 提交",
            },
        ]

        normalized = self.flow._parse_approval_record_cards(records)

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["approver_name"], "何颖(00769528)")
        self.assertEqual(normalized[0]["approval_time"], "2026-03-12 09:42:23")
        self.assertEqual(normalized[1]["approval_time"], "2026-03-13 15:46:49")

    def test_parse_approval_record_cards_fills_manual_added_sign_node(self) -> None:
        records = [
            {
                "record_seq": "3",
                "header_text": "简思婷|薪酬福利 同意",
                "approval_time": "2026-03-17 09:05:53",
                "approval_opinion": "同意",
                "raw_text": "简思婷|薪酬福利 同意 2026-03-17 09:05:53 同意",
            },
            {
                "record_seq": "4",
                "header_text": "蔡蟒生|深圳人力资源与行政服务部总监 同意",
                "approval_time": "2026-03-17 09:25:34",
                "approval_opinion": "同意",
                "raw_text": "蔡蟒生|深圳人力资源与行政服务部总监 同意 2026-03-17 09:25:34 同意",
            },
        ]

        normalized = self.flow._parse_approval_record_cards(records)

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["node_name"], "加签")
        self.assertEqual(normalized[0]["approver_name"], "简思婷")
        self.assertEqual(normalized[0]["approval_action"], "同意")
        self.assertEqual(normalized[1]["node_name"], "加签")
        self.assertEqual(normalized[1]["approver_name"], "蔡蟒生")
        self.assertEqual(normalized[1]["approval_action"], "同意")

    def test_wait_for_todo_list_ready_continues_without_page_size_selector(self) -> None:
        grid_collection = MagicMock()
        grid_locator = MagicMock()
        grid_collection.first = grid_locator

        def locator_side_effect(selector: str):
            if selector == "#gridview":
                return grid_collection
            raise AssertionError(f"unexpected selector: {selector}")

        self.page.locator.side_effect = locator_side_effect

        with (
            patch.object(
                self.flow,
                "_ensure_todo_page_size",
                side_effect=PlaywrightTimeoutError("page size missing"),
            ),
            patch.object(self.flow, "_wait_for_grid_headers") as wait_headers,
        ):
            self.flow._wait_for_todo_list_ready()

        grid_locator.wait_for.assert_called_once_with(state="visible", timeout=2000)
        wait_headers.assert_called_once()
        self.logger.warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
