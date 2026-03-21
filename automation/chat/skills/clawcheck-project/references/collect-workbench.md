# Collect Workbench

- 正式来源：`GET /api/documents/collect-workbench`
- 后端入口：`automation/api/collect_workbench.py:get_collect_workbench`
- 数据来源：PostgreSQL 聚合结果与任务运行状态
- 主要用途：
  - 查询采集工作台当前统计
  - 查询采集任务状态
  - 查询最近采集运行结果
- 回答要求：
  - 明确来源是采集工作台正式接口
  - 需要说明当前结果是工作台实时快照
