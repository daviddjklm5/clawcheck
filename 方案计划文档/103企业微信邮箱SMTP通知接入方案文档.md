# 文档编号103：企业微信邮箱 SMTP 通知接入方案文档

## 1. 目标
为本项目现有自动化任务增加一套统一的邮件通知能力，通过“企业微信邮箱”向指定收件人发送运行结果摘要与失败告警。

本方案目标如下：
- 在不改动各业务 flow 主逻辑的前提下，统一在编排层发送邮件
- 支持从 `credentials.prod.local.yaml` 或环境变量读取邮件账号
- 使用企业微信邮箱 SMTP 能力发送邮件
- 对成功、失败场景分别发送摘要通知
- 邮件发送失败不得反向影响主任务执行结果

## 2. 适用范围
本方案适用于以下自动化动作：
- `check`
- `login`
- `run`
- `collect`
- `roster`
- `orglist`
- `rolecatalog`

本方案适用于以下目录及模块：
- `automation/scripts/run.py`
- `automation/utils/config_loader.py`
- `automation/utils/mail_notifier.py`
- `automation/config/settings*.yaml`
- `automation/config/credentials*.yaml`

## 3. 设计背景
当前项目已经具备以下基础能力：
- `automation/scripts/run.py`
  - 统一负责命令行参数解析、配置加载、运行编排、成功/失败收口
- `automation/utils/config_loader.py`
  - 统一负责 `settings.yaml` 与本地凭据文件加载
- `automation/utils/logger.py`
  - 统一负责运行日志文件生成
- `automation/logs/`、`automation/screenshots/`
  - 已有日志、截图、JSON dump 等可复用通知素材

因此，邮件通知最合适的接入位置不是各个 flow 内部，而是 `run.py` 编排层。

## 4. 设计原则

### 4.1 协议原则
企业微信邮箱通知统一采用 `SMTP` 发送，不引入额外 HTTP 消息通道。

推荐默认配置：
- SMTP Host：`smtp.exmail.qq.com`
- 默认端口：`465`
- 默认模式：`SMTP over SSL`
- 可配置兜底：`STARTTLS + 587`

### 4.2 鉴权原则
- 优先使用企业微信邮箱“客户端专用密码”
- 不建议在自动化配置中长期保存邮箱网页登录密码
- 邮件账号应支持替换为专用机器人邮箱或公共邮箱

### 4.3 架构原则
- 业务 flow 只负责采集、导出、入库
- 邮件通知只在 `run.py` 统一收口
- 配置、发送、模板三类职责分离

### 4.4 可靠性原则
- 主任务成功但邮件失败时，主任务仍视为成功
- 主任务失败时，邮件通知属于告警增强能力，不改变原始退出码
- 邮件模块不得依赖数据库，不新增运行时外部强依赖

### 4.5 安全与合规原则
- 不在邮件中发送敏感账号密码
- 不默认附带大体量导出文件
- 失败邮件只允许按配置附带错误截图

## 5. 总体设计

### 5.1 模块分层
邮件通知能力分为三层：
1. 配置层
2. 发送层
3. 触发层

### 5.2 配置层
配置层负责加载以下信息：
- SMTP 服务地址与端口
- SSL / STARTTLS 开关
- 发件账号与密码
- 发件人名称、发件地址
- 收件人、抄送人
- 哪些 action 成功后发送邮件
- 失败是否发送邮件
- 超时时间
- 是否附带错误截图

配置层统一由：
- `automation/utils/config_loader.py`

负责加载来源：
- `automation/config/settings.yaml`
- `automation/config/settings.prod.yaml`
- `automation/config/credentials.local.yaml`
- `automation/config/credentials.prod.local.yaml`
- 环境变量覆盖

### 5.3 发送层
发送层统一封装在：
- `automation/utils/mail_notifier.py`

职责如下：
- 构建邮件主题
- 构建文本正文
- 组装附件
- 根据配置选择 `SMTP_SSL` 或 `SMTP + STARTTLS`
- 登录并发送邮件

发送层统一基于 Python 标准库实现：
- `smtplib`
- `email.message.EmailMessage`

不新增第三方依赖。

### 5.4 触发层
触发层统一位于：
- `automation/scripts/run.py`

触发时机如下：
- `rolecatalog` 成功后发送摘要邮件
- `roster` / `orglist` / `collect` / `run` / `check` / `login` 成功结束后发送摘要邮件
- 任意 action 运行异常时发送失败告警邮件
- `playwright` 缺失导致启动前失败时也应发送失败邮件

## 6. 配置设计

### 6.1 settings 文件结构
新增 `mail` 配置段：

```yaml
mail:
  enabled: false
  host: "smtp.exmail.qq.com"
  port: 465
  use_ssl: true
  use_starttls: false
  username: ""
  password: ""
  from_name: "clawcheck"
  from_addr: ""
  to_addrs:
    - "receiver@example.com"
  cc_addrs: []
  send_on_success:
    - "roster"
    - "orglist"
    - "collect"
  send_on_failure: true
  timeout_sec: 15
  attach_error_screenshot: true
```

说明：
- `enabled=false` 时完全不发送邮件
- `from_addr` 为空时，运行时可回退使用 `mail.username`
- `send_on_success` 为空列表时表示“不限制 action”，否则只对指定 action 成功发送

### 6.2 本地凭据文件结构
本地凭据文件允许增加 `mail` 段：

```yaml
auth:
  username: "your_prod_username"
  password: "your_prod_password"

mail:
  username: "robot@yourcorp.com"
  password: "your_mail_client_password"
```

本方案要求邮件账号可从以下文件读取：
- `automation/config/credentials.local.yaml`
- `automation/config/credentials.prod.local.yaml`

### 6.3 环境变量覆盖规范
运行时允许通过环境变量覆盖邮件配置：
- `IERP_MAIL_ENABLED`
- `IERP_MAIL_HOST`
- `IERP_MAIL_PORT`
- `IERP_MAIL_USE_SSL`
- `IERP_MAIL_USE_STARTTLS`
- `IERP_MAIL_USERNAME`
- `IERP_MAIL_PASSWORD`
- `IERP_MAIL_FROM_NAME`
- `IERP_MAIL_FROM_ADDR`
- `IERP_MAIL_TO_ADDRS`
- `IERP_MAIL_CC_ADDRS`
- `IERP_MAIL_SEND_ON_SUCCESS`
- `IERP_MAIL_SEND_ON_FAILURE`
- `IERP_MAIL_TIMEOUT_SEC`
- `IERP_MAIL_ATTACH_ERROR_SCREENSHOT`

其中：
- `IERP_MAIL_TO_ADDRS`、`IERP_MAIL_CC_ADDRS`、`IERP_MAIL_SEND_ON_SUCCESS`
  - 采用逗号分隔

示例：

```bash
export IERP_MAIL_ENABLED=true
export IERP_MAIL_USERNAME="robot@yourcorp.com"
export IERP_MAIL_PASSWORD="your_mail_client_password"
export IERP_MAIL_TO_ADDRS="a@yourcorp.com,b@yourcorp.com"
```

## 7. 邮件内容设计

### 7.1 主题格式
统一格式如下：

```text
[clawcheck][{action}][SUCCESS|FAILED] {yyyy-mm-dd HH:MM:SS}
```

示例：

```text
[clawcheck][roster][SUCCESS] 2026-03-14 09:30:00
```

### 7.2 正文内容
正文统一包含以下字段：
- `action`
- `status`
- `started_at`
- `finished_at`
- `duration_seconds`
- `error`（失败时）
- `summary`

`summary` 中优先放入以下信息：
- 配置文件路径
- 凭据文件路径
- 运行日志路径
- JSON dump 路径
- 结果截图路径
- 导入结果摘要
- 行数 / 条数 / 批次号等业务摘要

### 7.3 附件策略
默认附件策略如下：
- 成功邮件：不附带导出 Excel
- 失败邮件：按配置可附带 `error` 截图
- 不发送大体量原始导出文件

原因：
- 花名册导出文件可能较大
- 原始文件通常包含敏感业务数据
- 邮件网关对附件大小存在限制

## 8. 运行流程设计

### 8.1 成功场景
成功场景流程如下：
1. `run.py` 加载 settings、凭据文件、环境变量覆盖
2. 执行业务 action
3. 收集运行结果摘要、截图路径、JSON dump 路径
4. 判断该 action 是否命中 `send_on_success`
5. 调用 `mail_notifier.send_action_notification(...)`
6. 邮件发送成功则记录日志
7. 邮件发送失败仅记录 warning，不影响主退出码

### 8.2 失败场景
失败场景流程如下：
1. action 运行异常进入统一异常分支
2. 保留原有 `logger.exception(...)`
3. 截取错误截图
4. 若 `send_on_failure=true`，调用发送层发出失败告警
5. 邮件发送失败只记录 warning
6. 保持原始失败退出码不变

## 9. 实现映射
本方案已映射到当前仓库实现：

- `automation/utils/config_loader.py`
  - 新增 `MailSettings`
  - 新增 `load_local_credentials(...)`
  - 支持 `mail` 配置段与列表字段解析

- `automation/scripts/run.py`
  - 新增邮件环境变量覆盖逻辑
  - 新增统一 `notification_context`
  - 在成功、失败出口统一发送邮件

- `automation/config/settings.yaml`
- `automation/config/settings.prod.yaml`
- `automation/config/settings.example.yaml`
- `automation/config/settings.prod.example.yaml`
  - 新增 `mail` 配置段

- `automation/config/credentials.local.example.yaml`
- `automation/config/credentials.prod.local.example.yaml`
  - 新增 `mail.username`、`mail.password` 示例

## 10. 安全要求
- 真实邮件密码只允许出现在本地未提交文件或环境变量中
- 推荐使用客户端专用密码，不使用网页登录密码
- 不得在日志中打印邮件密码
- 不得在方案中要求将真实凭据提交到 Git
- 收件人列表必须显式配置，默认模板值不得用于生产

## 11. 验收标准
满足以下条件即可视为方案完成：
- `settings*.yaml` 支持 `mail` 配置段
- `credentials.prod.local.yaml` 支持 `mail.username/password`
- `IERP_MAIL_USERNAME`、`IERP_MAIL_PASSWORD` 等环境变量可覆盖本地配置
- `roster` / `orglist` / `collect` 等 action 成功时可发送摘要邮件
- action 失败时可发送失败告警邮件
- 邮件发送失败不影响主任务退出码
- README 中有明确配置说明

## 12. 后续扩展建议
后续可按需扩展：
- 增加 `mailtest` 独立测试 action
- 增加 HTML 邮件模板
- 增加邮件重试与本地 outbox
- 增加不同 action 的主题和正文模板
- 增加值班收件人或按环境动态路由

## 13. 参考
- 企业微信邮件帮助中心：<https://service.exmail.qq.com/cgi-bin/help>
