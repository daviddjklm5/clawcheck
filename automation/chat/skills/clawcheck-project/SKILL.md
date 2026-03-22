---
name: clawcheck-project
description: 针对 clawcheck 项目正式工作台、实时统计与正式接口的项目内对话能力；路由规则：数量问题可 templated，凡出现“列出/全部/具体编号/这N条编号”等明细意图时必须 tool_first + get_process_workbench 且 answerMode=model_generated；若问题包含“待处理单据”，编号清单必须仅取 documents 中 todoProcessStatus=待处理 的 documentNo。
status: active
owner: automation/chat
domain: workbench
references:
  - process-workbench
  - collect-workbench
  - process-approval
  - answer-policy
---

# Clawcheck Project

- 当用户询问本项目工作台、单据状态、实时统计或正式业务口径时，优先选择正式工具。
- 不允许猜测未注册接口、未注册参数、未注册字段或 shell/curl 调用方案。
- 当工具调用缺少关键参数时，必须先追问补齐，再进入工具执行。
- 仅当用户问题是“数量/统计”时，才优先模板化直答。
- 当用户明确要求“列出编号/这 N 条都列出来/全部单据编号”时，必须返回编号清单，不能只回复数量。
- 当用户问题限定“待处理单据编号”时，必须先按 `todoProcessStatus = 待处理` 过滤 `documents`，不能混入“已处理/已驳回”。
- 当正式工具结果与通用仓库知识冲突时，以正式工具结果为准。
