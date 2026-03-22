# 方案编号404A：对话审批 Dry-Run 登录入口打开失败问题记录文档

## 1. 问题背景

在 `404` 对话工作台单据审批能力 Phase 1 开发完成后，按用户要求对单据 `RA-20260319-00020227` 执行一次“批准”场景的 `dry-run` 验证：

1. 动作：`approve`
2. 审批意见：`通过`
3. 目标：停留在最后一步，不点击最终提交

本次验证未能进入审批页面，阻塞在 EHR 登录入口页面打开阶段。

---

## 2. 测试目标

本次测试原目标为验证以下链路：

1. 能按单据编号打开目标待办单据
2. 能进入 `任务处理` 页签
3. 能将审批意见写入为 `通过`
4. 能将审批决策切换为 `同意`
5. 能走到最终提交前一步
6. 因 `dry-run=true`，不点击最终 `提交`

实际结果是：目标 1 尚未完成，流程在登录入口打开阶段失败。

---

## 3. 复现信息

### 3.1 执行时间

- `2026-03-22 09:23`

### 3.2 执行命令

```python
from automation.api.process_dashboard import approve_process_document

approve_process_document(
    document_no="RA-20260319-00020227",
    action="approve",
    approval_opinion="通过",
    dry_run=True,
)
```

### 3.3 运行参数

1. 单据编号：`RA-20260319-00020227`
2. 审批动作：`approve`
3. 审批意见：`通过`
4. `dryRun=true`

### 3.4 使用配置

根据正式日志，本次运行使用：

1. `automation/config/settings.prod.yaml`
2. `automation/config/credentials.prod.local.yaml`
3. `automation/config/selectors.yaml`
4. `automation/state/auth_prod.json`

---

## 4. 现场现象

正式日志显示：

1. 单据待办状态探测成功
   - `todoProcessStatus = 待处理`
2. 浏览器会话创建成功
3. 浏览器上下文创建成功
4. 尝试打开首页：
   - `https://hr.onewo.com/ierp/?formId=home_page`
5. 首页就绪探测失败
6. 系统判断进入登录流程
7. 登录入口连续两次打开后，页面都落到：
   - `chrome-error://chromewebdata/`
8. 最终抛出运行时异常，审批 `dry-run` 失败

---

## 5. 错误摘要

本次关键错误为：

```text
Unable to open login entry page after navigation retries.
Target URL: https://hr.onewo.com/ierp/?formId=home_page;
current URL: chrome-error://chromewebdata/
```

补充日志中还出现：

```text
home_ready_probe_failed
No visible element matched within 20000ms.
text=员工自助服务中心: count=0
text=首页: count=0
text=工作台: count=0
text=待办: count=0
text=常用应用: count=0
```

说明：

1. 不是进入页面后控件失配
2. 不是审批意见写入失败
3. 不是停留在最后一步时失败
4. 而是浏览器在访问入口页面时已经落入 Chromium 错误页

---

## 6. 证据文件

### 6.1 正式日志

- [approval_20260322_092319_RA-20260319-00020227.json](c:/Users/Administrator/source/repos/clawcheck/automation/logs/approval_20260322_092319_RA-20260319-00020227.json)

### 6.2 错误截图

- [approval_error_20260322_092319_RA-20260319-00020227.png](c:/Users/Administrator/source/repos/clawcheck/automation/screenshots/approval_error_20260322_092319_RA-20260319-00020227.png)

---

## 7. 当前判断

截至 `2026-03-22`，本问题更接近“入口访问失败”而不是“审批流逻辑失败”。

优先怀疑方向如下：

1. 当前机器到 `https://hr.onewo.com/ierp/` 的网络访问异常
2. 企业内网 / VPN / 代理状态不满足访问条件
3. Chromium 当前会话环境异常，直接落入错误页
4. 目标站点在当时短时不可达
5. `auth_prod.json` 虽存在，但在需要重新登录时无法成功打开登录入口

暂不优先怀疑以下方向：

1. `approve_process_document()` 业务逻辑错误
2. `DocumentApprovalFlow.execute_action()` 停留最后一步的实现错误
3. 审批意见 `通过` 写入逻辑异常
4. `同意 -> 提交` 的 EHR 控件选择器失配

原因是本次流程尚未走到这些步骤。

---

## 8. 对 404 Phase 1 的影响

本问题对 `404` 当前阶段的影响边界如下：

1. 不影响对话审批计划生成
2. 不影响确认命令解析
3. 不影响 `dry-run/提交/取消` 的 ChatService 编排逻辑
4. 影响真实浏览器链路联调
5. 当前无法用本机环境证明“已成功停留到最后一步但未点击提交”

因此：

1. `404` 的代码闭环已具备
2. 但真实环境连通性验证仍未完成

---

## 9. 建议处理步骤

建议按以下顺序排查：

1. 在本机浏览器手工访问：
   - `https://hr.onewo.com/ierp/?formId=home_page`
2. 确认当前是否需要企业内网 / VPN / 代理
3. 检查当前终端会话是否存在网络隔离或证书问题
4. 若手工可访问，再重新执行同一条 `dry-run`
5. 若手工仍不可访问，先解决入口可达性，再继续审批联调

---

## 10. 后续复测标准

本问题关闭前，至少应完成以下复测：

1. 使用同一单据 `RA-20260319-00020227`
2. 动作仍为 `approve`
3. 审批意见仍为 `通过`
4. `dry-run=true`
5. 结果满足：
   - 成功打开首页
   - 成功进入目标单据
   - 成功写入审批意见
   - 成功切换审批决策
   - 成功停留在最终提交前一步
   - 明确未点击 `提交`

---

## 11. 结论

本次专项问题的结论是：

1. 单据 `RA-20260319-00020227` 的审批 `dry-run` 已执行
2. 审批意见为 `通过`
3. 流程未能进入“最后一步不点击通过”的验证阶段
4. 实际阻塞点在 EHR 登录入口打开失败
5. 当前应先处理入口可达性，再继续真实审批链路复测

---

## 12. 修复落地（2026-03-22）

针对“`dry-run` 在登录入口阶段失败”问题，已完成以下代码修复并回归通过：

1. 统一复用登录重试能力  
   - 新增公共登录韧性工具：`automation/utils/login_resilience.py`  
   - `run.py` 与审批 API 共用同一套“登录重试 + 关闭页重建”逻辑，避免两套实现漂移

2. 增强登录入口打开容错  
   - `LoginPage.open()` 重试预算由 `2` 提升到 `4`  
   - 当主入口不可达时，自动轮询主入口与备用入口（`hr.onewo.com` / `thr.onewo.com:8443`）

3. 审批链路支持页面重建后的引用同步  
   - `DocumentApprovalFlow` 新增 `set_page()`，在登录重试中页面重建后可继续复用审批流对象

4. 审批 API 已接入共享登录重试能力  
   - `approve_process_document()` 不再直接单次 `login_page.login(...)`  
   - 改为走共享 `ensure_login_with_retry(...)`，并沿用 `runtime.retries/retry_wait_sec`

5. 回归结果  
   - `tests/test_login_resilience.py`：`5 passed`  
   - `tests/test_documents_router.py`：`11 passed`

说明：本次为“代码侧修复落地”；最终是否彻底消除 404A 现象，仍需按本文件第 10 节在真实网络环境完成复测确认。

---

## 13. 补充修复（2026-03-22）

针对对话记录中出现的“`当前环境未开启对话审批能力`”阻塞，补充完成以下处理：

1. 明确结论  
   - 该阻塞是审批能力开关未开启导致，不属于登录失败或审批流页面操作失败。

2. 启动脚本默认启用审批能力（可被显式环境变量覆盖）  
   - 变更：`automation/scripts/start_api.ps1`  
   - 规则：仅当环境变量未设置时，自动注入  
     - `CLAWCHECK_CHAT_APPROVAL_ENABLED=true`  
     - `CLAWCHECK_CHAT_APPROVAL_DRY_RUN_ONLY=true`

3. 拦截提示改为可操作  
   - 变更：`automation/chat/service.py`  
   - 在“审批能力未开启”场景中，直接提示需要设置的环境变量和重启 API 操作，避免只报错不指路。

4. 前端状态可视化补齐  
   - 变更：`webui/src/pages/ChatWorkspacePage.tsx` 与 `webui/src/types/chat.ts`  
   - 聊天工作台顶部新增审批能力状态展示（`Disabled / Enabled (Dry-run only) / Enabled (Submit allowed)`），便于快速判断当前环境是否可执行审批。

5. 回归结果  
   - `tests/test_chat_service.py tests/test_chat_router_models.py`：`13 passed`

---

## 14. 补充修复（2026-03-22 12:xx）

针对对话中出现的以下体验问题补充修复：

1. 现象  
   - 已生成审批计划后，输入“请先验证”被当成重新发起审批，触发“请明确这是要批准还是驳回”  
   - 输入“确认命令：确认审批计划 <planId>”未命中审批命令，掉入通用链路并触发策略拦截日志

2. 原因  
   - 原命令解析仅支持严格格式：`确认审批计划 <planId>` / `验证审批计划 <planId>` / `取消审批计划 <planId>`  
   - 不支持“确认命令：”等标签前缀  
   - 不支持“请先验证/确认”等短语在“当前仅有一个待确认计划”场景下的隐式执行

3. 修复  
   - 扩展审批命令解析：支持标签前缀与关键词识别（包含 `确认命令：确认审批计划 <planId>`）  
   - 新增短语隐式命中：当会话内仅有一个活动审批计划时，“请先验证/确认/取消”等短语可直接映射到该计划  
   - 若存在多个活动计划，返回“请指定 planId”而不盲目执行

4. 回归结果  
   - 新增并通过 3 个测试：  
     - 前缀命令可执行真实提交  
     - “请先验证”可命中唯一待确认计划  
     - 多计划场景会要求明确 planId  
   - 汇总：`tests/test_chat_service.py tests/test_chat_router_models.py tests/test_login_resilience.py tests/test_documents_router.py tests/test_chat_approval_plan_store.py` -> `36 passed`
