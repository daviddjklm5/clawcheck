# Process Workbench

- 正式来源：`GET /api/documents/process-workbench`
- 后端入口：`automation/api/process_dashboard.py:get_process_workbench`
- 数据来源：PostgreSQL 实时查询结果
- 主要用途：
  - 查询处理工作台当前统计
  - 查询待处理单据数量
  - 查询处理工作台当前单据列表
- 关键字段：
  - `stats`：工作台顶部正式统计口径
  - `documents`：当前单据列表
- 回答要求：
  - 明确这是“处理工作台实时口径”
  - 回答中说明来源是正式工作台接口
  - 若只问待办数量，优先直接报数，不展开额外推理
