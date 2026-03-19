from __future__ import annotations

import copy
from typing import Any

MASTER_DATA_DASHBOARD = {
    "stats": [
        {
            "label": "在职花名册",
            "value": "2026-03-15 09:15",
            "hint": "最新一次导入成功，刷新了人员属性查询。",
            "tone": "success",
        },
        {
            "label": "组织列表",
            "value": "2026-03-13 12:12",
            "hint": "最近一次完成 96017 行组织数据导入。",
            "tone": "info",
        },
        {
            "label": "权限列表",
            "value": "12 个等级口径",
            "hint": "沿用现有权限主数据与例外配置。",
            "tone": "default",
        },
        {
            "label": "任务成功率",
            "value": "92%",
            "hint": "近 7 天主数据同步任务。",
            "tone": "warning",
        },
    ],
    "actions": [
        {
            "id": "roster",
            "title": "同步在职花名册",
            "description": "下载最新在职花名册并刷新人员属性查询。",
            "buttonLabel": "执行同步",
            "command": "python automation/scripts/run.py roster --headed",
            "status": "建议保留人工可见浏览器模式",
        },
        {
            "id": "orglist",
            "title": "同步组织列表",
            "description": "下载组织快速维护清单并更新组织属性相关表。",
            "buttonLabel": "执行同步",
            "command": "python automation/scripts/run.py orglist --headed",
            "status": "导出量大，建议单独观察执行",
        },
        {
            "id": "rolecatalog",
            "title": "初始化权限主数据",
            "description": "写入权限列表基础字典与权限级别口径。",
            "buttonLabel": "初始化",
            "command": "python automation/scripts/run.py rolecatalog",
            "status": "适用于新库初始化或口径刷新",
        },
    ],
    "jobs": [
        {
            "id": "job-2001",
            "jobType": "在职花名册同步",
            "target": "在职花名册表 / 人员属性查询",
            "status": "成功",
            "startedAt": "2026-03-15 09:01",
            "finishedAt": "2026-03-15 09:15",
            "records": 18462,
            "operator": "system",
        },
        {
            "id": "job-2002",
            "jobType": "组织列表同步",
            "target": "组织列表 / 组织属性查询",
            "status": "成功",
            "startedAt": "2026-03-13 11:48",
            "finishedAt": "2026-03-13 12:12",
            "records": 96017,
            "operator": "system",
        },
        {
            "id": "job-2003",
            "jobType": "权限主数据初始化",
            "target": "权限列表",
            "status": "待确认",
            "startedAt": "2026-03-12 18:30",
            "finishedAt": "2026-03-12 18:31",
            "records": 312,
            "operator": "admin",
        },
    ],
}

COLLECT_DASHBOARD = {
    "stats": [
        {
            "label": "今日新采集单据",
            "value": "18",
            "hint": "来自权限申请单待办列表。",
            "tone": "info",
        },
        {
            "label": "待补采集单据",
            "value": "4",
            "hint": "存在字段缺口，建议重跑。",
            "tone": "warning",
        },
        {
            "label": "最近批次",
            "value": "collect_20260315_112428",
            "hint": "对应日志目录中的 JSON 输出。",
            "tone": "default",
        },
        {
            "label": "落库目标",
            "value": "4 张申请单表",
            "hint": "主表、权限明细、审批记录、组织范围。",
            "tone": "success",
        },
    ],
    "scopes": [
        {
            "id": "basic",
            "title": "申请单基本信息",
            "description": "采集单据主表、申请人、单据状态与申请原因。",
            "buttonLabel": "查看表结构",
            "command": "申请单基本信息",
            "status": "已接入中文字段落库",
        },
        {
            "id": "permission",
            "title": "申请单权限列表",
            "description": "采集角色编码、角色名称、申请类型与组织范围数量。",
            "buttonLabel": "查看表结构",
            "command": "申请单权限列表",
            "status": "支持角色级明细",
        },
        {
            "id": "approval",
            "title": "申请单审批记录",
            "description": "采集审批轨迹、节点、审批人、审批意见等信息。",
            "buttonLabel": "查看表结构",
            "command": "申请单审批记录",
            "status": "保留最新时间字段",
        },
        {
            "id": "orgscope",
            "title": "申请表组织范围",
            "description": "按 013 方案展开角色与组织范围明细。",
            "buttonLabel": "查看表结构",
            "command": "申请表组织范围",
            "status": "支持跳过组织范围例外规则",
        },
    ],
    "documents": [
        {
            "id": "collect-1",
            "documentNo": "RA-20260315-00020018",
            "applicantName": "张晨",
            "applicantNo": "100218",
            "subject": "新增资金系统查询权限",
            "documentStatus": "已采集",
            "collectedAt": "2026-03-15 11:24",
            "roleCount": 3,
            "approvalCount": 5,
        },
        {
            "id": "collect-2",
            "documentNo": "RA-20260315-00020017",
            "applicantName": "陈霖",
            "applicantNo": "103114",
            "subject": "补采集审批轨迹",
            "documentStatus": "待补采",
            "collectedAt": "2026-03-15 10:56",
            "roleCount": 2,
            "approvalCount": 3,
        },
        {
            "id": "collect-3",
            "documentNo": "RA-20260314-00019986",
            "applicantName": "李菲",
            "applicantNo": "104602",
            "subject": "追加项目费用权限",
            "documentStatus": "已采集",
            "collectedAt": "2026-03-14 18:18",
            "roleCount": 4,
            "approvalCount": 6,
        },
    ],
    "detailsByDocumentNo": {
        "RA-20260315-00020018": {
            "basicInfo": [
                {"label": "单据编号", "value": "RA-20260315-00020018", "hint": "当前选中单据"},
                {"label": "申请人", "value": "张晨 / 100218", "hint": "通过工号关联人员属性查询"},
                {"label": "权限对象", "value": "资金系统", "hint": "业务域摘要"},
                {"label": "申请日期", "value": "2026-03-15 10:49", "hint": "来源 iERP 页面"},
            ],
            "tableStatus": [
                {"id": "t1", "tableName": "申请单基本信息", "status": "已落库", "records": 1, "updatedAt": "2026-03-15 11:24", "remark": "主键为单据编号"},
                {"id": "t2", "tableName": "申请单权限列表", "status": "已落库", "records": 3, "updatedAt": "2026-03-15 11:24", "remark": "含角色编码与组织范围数量"},
                {"id": "t3", "tableName": "申请单审批记录", "status": "已落库", "records": 5, "updatedAt": "2026-03-15 11:24", "remark": "包含审批节点与意见"},
                {"id": "t4", "tableName": "申请表组织范围", "status": "已落库", "records": 8, "updatedAt": "2026-03-15 11:24", "remark": "按 013 方案展开"},
            ],
            "nextActions": [
                "支持继续补跑该单据的风险与信任度评估。",
                "后续可联动 103 计划中的审批建议页签。",
            ],
        },
        "RA-20260315-00020017": {
            "basicInfo": [
                {"label": "单据编号", "value": "RA-20260315-00020017", "hint": "待补采集"},
                {"label": "申请人", "value": "陈霖 / 103114", "hint": "审批记录缺口导致补采"},
                {"label": "权限对象", "value": "采购系统", "hint": "存在历史单据回补需求"},
                {"label": "申请日期", "value": "2026-03-15 09:58", "hint": "页面采集时间稍后"},
            ],
            "tableStatus": [
                {"id": "t5", "tableName": "申请单基本信息", "status": "已落库", "records": 1, "updatedAt": "2026-03-15 10:56", "remark": "主表完整"},
                {"id": "t6", "tableName": "申请单权限列表", "status": "已落库", "records": 2, "updatedAt": "2026-03-15 10:56", "remark": "角色明细完整"},
                {"id": "t7", "tableName": "申请单审批记录", "status": "待补采", "records": 1, "updatedAt": "2026-03-15 10:56", "remark": "审批意见存在空值"},
                {"id": "t8", "tableName": "申请表组织范围", "status": "已落库", "records": 5, "updatedAt": "2026-03-15 10:56", "remark": "组织范围可用"},
            ],
            "nextActions": [
                "建议单据详情页直接提供重新采集入口。",
                "补采成功后自动刷新审批记录与风险评估状态。",
            ],
        },
        "RA-20260314-00019986": {
            "basicInfo": [
                {"label": "单据编号", "value": "RA-20260314-00019986", "hint": "最近已验证通过"},
                {"label": "申请人", "value": "李菲 / 104602", "hint": "涉及 4 个角色"},
                {"label": "权限对象", "value": "项目费用系统", "hint": "含组织范围展开"},
                {"label": "申请日期", "value": "2026-03-14 17:31", "hint": "供联调展示"},
            ],
            "tableStatus": [
                {"id": "t9", "tableName": "申请单基本信息", "status": "已落库", "records": 1, "updatedAt": "2026-03-14 18:18", "remark": "数据完整"},
                {"id": "t10", "tableName": "申请单权限列表", "status": "已落库", "records": 4, "updatedAt": "2026-03-14 18:18", "remark": "角色与申请类型齐全"},
                {"id": "t11", "tableName": "申请单审批记录", "status": "已落库", "records": 6, "updatedAt": "2026-03-14 18:18", "remark": "审批人链路完整"},
                {"id": "t12", "tableName": "申请表组织范围", "status": "已落库", "records": 11, "updatedAt": "2026-03-14 18:18", "remark": "已通过组织范围展开验收"},
            ],
            "nextActions": [
                "可直接进入处理单据模块查看评估结果。",
                "后续可以加上单据号跳转与上下游日志联动。",
            ],
        },
    },
}

PROCESS_DASHBOARD = {
    "stats": [
        {
            "label": "待处理单据",
            "value": "26",
            "hint": "当前待办池中的待评估单据。",
            "tone": "warning",
        },
        {
            "label": "高风险单据",
            "value": "5",
            "hint": "建议优先人工复核。",
            "tone": "danger",
        },
        {
            "label": "高信任单据",
            "value": "11",
            "hint": "适合进入审批建议通道。",
            "tone": "success",
        },
        {
            "label": "后续动作",
            "value": "审批 / 驳回 / 加签",
            "hint": "当前先展示入口与建议，不做页面回写。",
            "tone": "info",
        },
    ],
    "documents": [
        {
            "id": "process-1",
            "documentNo": "RA-20260315-00020018",
            "applicantName": "张晨",
            "department": "财务共享中心",
            "documentStatus": "待处理",
            "riskLevel": "中",
            "trustLevel": "高",
            "recommendation": "建议审批",
            "submittedAt": "2026-03-15 10:49",
        },
        {
            "id": "process-2",
            "documentNo": "RA-20260315-00020017",
            "applicantName": "陈霖",
            "department": "采购管理部",
            "documentStatus": "待处理",
            "riskLevel": "高",
            "trustLevel": "低",
            "recommendation": "建议复核",
            "submittedAt": "2026-03-15 09:58",
        },
        {
            "id": "process-3",
            "documentNo": "RA-20260314-00019986",
            "applicantName": "李菲",
            "department": "项目运营中心",
            "documentStatus": "待补功能",
            "riskLevel": "中",
            "trustLevel": "中",
            "recommendation": "等待 103 功能补齐",
            "submittedAt": "2026-03-14 17:31",
        },
    ],
    "detailsByDocumentNo": {
        "RA-20260315-00020018": {
            "basicInfo": [
                {"label": "单据编号", "value": "RA-20260315-00020018", "hint": "处理链路主键"},
                {"label": "申请人", "value": "张晨 / 100218", "hint": "关联人员属性查询"},
                {"label": "申请部门", "value": "财务共享中心", "hint": "用于 HR 与组织口径判断"},
                {"label": "审批建议", "value": "建议审批", "hint": "基于当前风险与信任度评估"},
            ],
            "roles": [
                {"id": "r1", "roleCode": "FIN_VIEW_001", "roleName": "资金系统查询", "applyType": "新增", "orgScopeCount": 2, "skipOrgScopeCheck": "否"},
                {"id": "r2", "roleCode": "FIN_PAY_002", "roleName": "付款申请查看", "applyType": "新增", "orgScopeCount": 4, "skipOrgScopeCheck": "否"},
                {"id": "r3", "roleCode": "FIN_LEDGER_006", "roleName": "总账查询", "applyType": "续期", "orgScopeCount": 0, "skipOrgScopeCheck": "是"},
            ],
            "approvals": [
                {"id": "a1", "nodeName": "申请提交", "approver": "张晨", "action": "提交", "finishedAt": "2026-03-15 10:49", "comment": "正常发起"},
                {"id": "a2", "nodeName": "部门负责人", "approver": "王敏", "action": "同意", "finishedAt": "2026-03-15 10:58", "comment": "业务需求明确"},
                {"id": "a3", "nodeName": "共享财务审批", "approver": "刘宁", "action": "待处理", "finishedAt": "-", "comment": "待进入审批建议流程"},
            ],
            "orgScopes": [
                {"id": "o1", "roleCode": "FIN_VIEW_001", "roleName": "资金系统查询", "organizationCode": "10001001", "organizationName": "上海财务共享中心", "skipOrgScopeCheck": "否"},
                {"id": "o2", "roleCode": "FIN_VIEW_001", "roleName": "资金系统查询", "organizationCode": "10001002", "organizationName": "苏州财务共享中心", "skipOrgScopeCheck": "否"},
                {"id": "o3", "roleCode": "FIN_LEDGER_006", "roleName": "总账查询", "organizationCode": "-", "organizationName": "不检查组织范围", "skipOrgScopeCheck": "是"},
            ],
            "riskDetails": [
                {"id": "d1", "ruleCode": "RT-001", "ruleName": "申请人 HR 类型匹配", "result": "命中", "riskLevel": "低", "trustLevel": "高", "hitDetail": "申请人属于财务条线，角色权限与岗位相符"},
                {"id": "d2", "ruleCode": "RT-013", "ruleName": "组织范围例外校验", "result": "命中", "riskLevel": "中", "trustLevel": "中", "hitDetail": "存在 1 个跳过组织范围角色，需要人工确认"},
            ],
            "scoreBasisDetails": [],
            "notes": [
                "当前页面仅展示建议，不直接回写审批动作。",
                "103 计划接入后，可在此位置增加审批 / 驳回 / 加签按钮。",
            ],
        },
        "RA-20260315-00020017": {
            "basicInfo": [
                {"label": "单据编号", "value": "RA-20260315-00020017", "hint": "高风险样例"},
                {"label": "申请人", "value": "陈霖 / 103114", "hint": "采集链路需补审批记录"},
                {"label": "申请部门", "value": "采购管理部", "hint": "与目标权限存在偏差"},
                {"label": "审批建议", "value": "建议复核", "hint": "建议先补采审批轨迹再判断"},
            ],
            "roles": [
                {"id": "r4", "roleCode": "PURCHASE_ADMIN", "roleName": "采购主数据维护", "applyType": "新增", "orgScopeCount": 12, "skipOrgScopeCheck": "否"},
                {"id": "r5", "roleCode": "FIN_LEDGER_006", "roleName": "总账查询", "applyType": "新增", "orgScopeCount": 0, "skipOrgScopeCheck": "是"},
            ],
            "approvals": [
                {"id": "a4", "nodeName": "申请提交", "approver": "陈霖", "action": "提交", "finishedAt": "2026-03-15 09:58", "comment": "待补采审批后续节点"},
            ],
            "orgScopes": [
                {"id": "o4", "roleCode": "PURCHASE_ADMIN", "roleName": "采购主数据维护", "organizationCode": "20003018", "organizationName": "华东采购中心", "skipOrgScopeCheck": "否"},
                {"id": "o5", "roleCode": "PURCHASE_ADMIN", "roleName": "采购主数据维护", "organizationCode": "20003019", "organizationName": "华南采购中心", "skipOrgScopeCheck": "否"},
            ],
            "riskDetails": [
                {"id": "d3", "ruleCode": "RT-021", "ruleName": "岗位与权限级别偏差", "result": "命中", "riskLevel": "高", "trustLevel": "低", "hitDetail": "采购管理部申请总账查询，超出常规岗位边界"},
                {"id": "d4", "ruleCode": "RT-031", "ruleName": "审批轨迹完整性", "result": "命中", "riskLevel": "高", "trustLevel": "低", "hitDetail": "审批记录当前不完整，建议补采后再进入审批建议"},
            ],
            "scoreBasisDetails": [],
            "notes": [
                "建议在单据详情顶部保留“重新采集”快捷入口。",
                "当前为 DataGrid 社区版方案，详情区域采用列表 + 页签，不依赖 master-detail。",
            ],
        },
        "RA-20260314-00019986": {
            "basicInfo": [
                {"label": "单据编号", "value": "RA-20260314-00019986", "hint": "103 待补功能样例"},
                {"label": "申请人", "value": "李菲 / 104602", "hint": "中风险、中信任"},
                {"label": "申请部门", "value": "项目运营中心", "hint": "组织范围已完整落库"},
                {"label": "审批建议", "value": "等待功能补齐", "hint": "需结合 103 页面动作"},
            ],
            "roles": [
                {"id": "r6", "roleCode": "COST_VIEW_001", "roleName": "项目费用查询", "applyType": "新增", "orgScopeCount": 3, "skipOrgScopeCheck": "否"},
                {"id": "r7", "roleCode": "COST_EDIT_003", "roleName": "项目费用维护", "applyType": "新增", "orgScopeCount": 3, "skipOrgScopeCheck": "否"},
            ],
            "approvals": [
                {"id": "a5", "nodeName": "申请提交", "approver": "李菲", "action": "提交", "finishedAt": "2026-03-14 17:31", "comment": "流程正常"},
                {"id": "a6", "nodeName": "部门负责人", "approver": "陈涛", "action": "同意", "finishedAt": "2026-03-14 17:48", "comment": "同意补充权限"},
            ],
            "orgScopes": [
                {"id": "o6", "roleCode": "COST_VIEW_001", "roleName": "项目费用查询", "organizationCode": "30005008", "organizationName": "杭州项目运营中心", "skipOrgScopeCheck": "否"},
                {"id": "o7", "roleCode": "COST_EDIT_003", "roleName": "项目费用维护", "organizationCode": "30005008", "organizationName": "杭州项目运营中心", "skipOrgScopeCheck": "否"},
            ],
            "riskDetails": [
                {"id": "d5", "ruleCode": "RT-011", "ruleName": "组织范围与角色匹配", "result": "命中", "riskLevel": "中", "trustLevel": "中", "hitDetail": "角色与项目中心组织范围匹配，但仍需业务确认"},
            ],
            "scoreBasisDetails": [],
            "notes": [
                "适合作为 103 计划补审批动作后的联动验收样例。",
                "后续可追加任务日志页签，用于展示详细执行轨迹。",
            ],
        },
    },
}


def get_master_data_dashboard() -> dict[str, Any]:
    return copy.deepcopy(MASTER_DATA_DASHBOARD)


def get_collect_dashboard() -> dict[str, Any]:
    return copy.deepcopy(COLLECT_DASHBOARD)


def get_process_dashboard() -> dict[str, Any]:
    return copy.deepcopy(PROCESS_DASHBOARD)
