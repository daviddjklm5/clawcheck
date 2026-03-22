---
name: clawcheck-project
description: 针对 clawcheck 项目正式工作台、实时统计与正式接口的项目内对话能力。
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
- 对确定性强的问题，工具结果足以回答时，优先模板化直答。
- 当正式工具结果与通用仓库知识冲突时，以正式工具结果为准。
