from __future__ import annotations

import unittest

from automation.reporting.low_score_feedback import build_low_score_feedback


class LowScoreFeedbackTest(unittest.TestCase):
    def test_builds_permission_summary_from_pg_preagg_rows(self) -> None:
        overview = build_low_score_feedback(
            summary_row={
                "summary_conclusion": "拒绝",
                "applicant_hr_type": "HX",
                "level1_function_name": "客服",
                "applicant_position_name": "客服员",
            },
            feedback_group_rows=[
                {
                    "group_key": "permission-b1",
                    "dimension_name": "申请的权限",
                    "rule_id": "PERMISSION_B1_NON_HR",
                    "score": 0.0,
                    "evidence_summary": "非HR申请涉薪权限",
                    "intervention_action": "拒绝",
                    "applicant_org_unit_name": "",
                    "target_org_unit_name": "",
                    "raw_detail_count": 1,
                    "role_meta": [
                        {
                            "role_code": "R-B1",
                            "role_name": "离职补偿金",
                            "permission_level": "B1类-涉薪",
                            "line_no": "1",
                        }
                    ],
                    "org_meta": [],
                },
                {
                    "group_key": "permission-b2",
                    "dimension_name": "申请的权限",
                    "rule_id": "PERMISSION_B2_NON_HR",
                    "score": 0.5,
                    "evidence_summary": "非HR申请涉档案绩效权限",
                    "intervention_action": "加强审核",
                    "applicant_org_unit_name": "",
                    "target_org_unit_name": "",
                    "raw_detail_count": 1,
                    "role_meta": [
                        {
                            "role_code": "R-B2",
                            "role_name": "劳动合同/协议续签/改签",
                            "permission_level": "B2类-涉档案绩效",
                            "line_no": "2",
                        }
                    ],
                    "org_meta": [],
                },
            ],
        )

        self.assertEqual(overview["summaryConclusionLabel"], "拒绝")
        self.assertEqual(len(overview["feedbackGroups"]), 1)
        self.assertIn("申请人为非HR岗位", overview["feedbackGroups"][0]["summary"])
        self.assertIn("离职补偿金", overview["feedbackGroups"][0]["summary"])
        self.assertIn("劳动合同/协议续签/改签", overview["feedbackGroups"][0]["summary"])
        self.assertEqual(overview["feedbackStats"][0]["value"], "1")
        self.assertEqual(overview["feedbackStats"][3]["value"], "2")

    def test_suppresses_hr_permission_reminder_when_cross_org_summary_exists(self) -> None:
        overview = build_low_score_feedback(
            summary_row={
                "summary_conclusion": "人工干预",
                "applicant_hr_type": "H1",
                "level1_function_name": "人力资源",
                "applicant_position_name": "招聘经理",
                "applicant_org_unit_name": "人力资源与行政服务中心",
            },
            feedback_group_rows=[
                {
                    "group_key": "cross-org",
                    "dimension_name": "申请的组织",
                    "rule_id": "TARGET_ORG_CROSS_UNIT_LOW",
                    "score": 0.5,
                    "evidence_summary": "申请组织范围跨组织单位",
                    "intervention_action": "明确申请理由",
                    "applicant_org_unit_name": "人力资源与行政服务中心",
                    "target_org_unit_name": "万科物业",
                    "raw_detail_count": 2,
                    "role_meta": [
                        {
                            "role_code": "R-1",
                            "role_name": "人员档案-可查看引出-有定薪有绩效",
                            "permission_level": "B1类-涉薪",
                            "line_no": "1",
                        }
                    ],
                    "org_meta": [
                        {
                            "org_code": "ORG-1",
                            "organization_name": "成都公园都会",
                            "physical_level": "1",
                        },
                        {
                            "org_code": "ORG-2",
                            "organization_name": "成都万科公园传奇",
                            "physical_level": "2",
                        },
                    ],
                },
                {
                    "group_key": "cross-org-2",
                    "dimension_name": "申请的组织",
                    "rule_id": "TARGET_ORG_CROSS_UNIT_LOW",
                    "score": 0.5,
                    "evidence_summary": "申请组织范围跨组织单位",
                    "intervention_action": "明确申请理由",
                    "applicant_org_unit_name": "人力资源与行政服务中心",
                    "target_org_unit_name": "万御安防",
                    "raw_detail_count": 1,
                    "role_meta": [
                        {
                            "role_code": "R-2",
                            "role_name": "定薪申请",
                            "permission_level": "B1类-涉薪",
                            "line_no": "2",
                        }
                    ],
                    "org_meta": [
                        {
                            "org_code": "ORG-3",
                            "organization_name": "成都金域名邸",
                            "physical_level": "1",
                        }
                    ],
                },
                {
                    "group_key": "permission-b1-hr",
                    "dimension_name": "申请的权限",
                    "rule_id": "PERMISSION_B1_HR_STAFF",
                    "score": 1.0,
                    "evidence_summary": "HR申请B1权限需人工关注",
                    "intervention_action": "加强审核",
                    "applicant_org_unit_name": "人力资源与行政服务中心",
                    "target_org_unit_name": "",
                    "raw_detail_count": 1,
                    "role_meta": [
                        {
                            "role_code": "R-1",
                            "role_name": "人员档案-可查看引出-有定薪有绩效",
                            "permission_level": "B1类-涉薪",
                            "line_no": "1",
                        }
                    ],
                    "org_meta": [],
                },
            ],
        )

        self.assertEqual(overview["summaryConclusionLabel"], "加强审核")
        self.assertEqual(len(overview["feedbackGroups"]), 1)
        self.assertEqual(overview["feedbackGroups"][0]["category"], "cross_org")
        self.assertIn("本次申请组织范围跨 2 个组织单位", overview["feedbackGroups"][0]["summary"])
        self.assertIn("需明确跨组织单位申请理由", overview["feedbackGroups"][0]["summary"])
        self.assertEqual(
            overview["feedbackGroups"][0]["summaryLines"],
            [
                "申请人属“人力资源与行政服务中心”，本次申请组织范围跨 2 个组织单位：",
                "涉“万科物业”：成都公园都会、成都万科公园传奇，共 2 个组织；",
                "涉“万御安防”：成都金域名邸，共 1 个组织；",
                "共影响：人员档案-可查看引出-有定薪有绩效、定薪申请 2 个角色；需明确跨组织单位申请理由。",
            ],
        )


if __name__ == "__main__":
    unittest.main()
