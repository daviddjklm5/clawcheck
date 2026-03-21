# iERP Automation

## 1. 推荐运行方式

本项目自 `300` 方案起，正式运行推荐使用：

- Windows 原生 Python
- Windows 原生 Playwright
- Windows 原生 PostgreSQL 服务或独立 PostgreSQL 实例
- FastAPI 承接 API 与 `webui/dist` 静态资源
- Windows Task Scheduler 承接定时任务

以下形态不再推荐作为正式部署方式：

- WSL 内常驻运行
- `uvicorn --reload`
- `npm run dev`
- Docker Desktop + WSL2 承载 PostgreSQL

WSL 可以继续作为开发辅助环境，但不再是正式运行前提。

## 2. 目录约定

- 配置：`automation/config/`
- SQL：`automation/sql/`
- 数据库入口：`automation/db/postgres.py`
- 自动化流程：`automation/flows/`
- API：`automation/api/`
- Windows 脚本：`automation/scripts/*.ps1`
- 日志：`automation/logs/`
- 备份：`automation/backups/`
- 下载文件：`automation/downloads/`

## 3. Windows 环境安装

### 3.1 前置要求

- Windows 10/11
- Python `3.12.x`
- Node.js `20+`
- PostgreSQL Windows 安装版，或可访问的独立 PostgreSQL 实例
- PowerShell

### 3.2 一键安装 Python 运行环境

在仓库根目录执行：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\install_windows_env.ps1 -IncludeDev
```

默认行为：

- 创建 `.venv-win`
- 安装 `automation/requirements.txt`
- 安装 `automation/requirements-dev.txt`
- 安装 Playwright `chromium`

如需指定 Python 版本：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\install_windows_env.ps1 -PythonVersion 3.12
```

## 4. 配置说明

主要配置文件：

- UAT：`automation/config/settings.yaml`
- PROD：`automation/config/settings.prod.yaml`
- UAT 凭据：`automation/config/credentials.local.yaml`
- PROD 凭据：`automation/config/credentials.prod.local.yaml`
- 选择器：`automation/config/selectors.yaml`
- 审核规则：`automation/config/rules/`

数据库连接优先读取：

1. `settings*.yaml`
2. 环境变量 `IERP_PG_*`

默认口径：

- `check/login/run/collect/roster/orglist/rolecatalog/dbinit/audit/sync-todo-status`
- 若未显式传入 `--config` / `--credentials`，优先使用 `settings.prod.yaml` 与 `credentials.prod.local.yaml`

### 4.1 GitHub 本地配置

- 本地 GitHub CLI / API 凭据文件：`automation/config/github.local.env`
- 示例模板：`automation/config/github.local.example.env`
- 字段：`GH_REPO_OWNER`、`GH_REPO_NAME`、`GH_TOKEN`
- `automation/config/github.local.env` 已加入 `.gitignore`，不会上传远程

PowerShell 加载示例：

```powershell
Get-Content .\automation\config\github.local.env | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name, $value = $_ -split '=', 2
    Set-Item -Path "Env:$name" -Value $value
}

gh repo view "$env:GH_REPO_OWNER/$env:GH_REPO_NAME"
git push origin main
```

## 5. Windows 运行命令

以下命令默认在仓库根目录执行。

### 5.1 直接运行 Python Runner

健康检查：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py check --headed
```

登录并刷新登录态：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py login --headed
```

权限申请采集：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py collect --limit 20 --headless
```

在职花名册同步：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py roster --headless
```

组织列表同步：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py orglist --headless
```

风险评估：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py audit --limit 20
```

待办状态同步：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py sync-todo-status --headless
```

权限主数据初始化：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py rolecatalog
```

数据库初始化：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py dbinit
```

### 5.2 推荐使用 PowerShell 任务脚本

正式运行更推荐使用已封装的 PowerShell 脚本，而不是直接手写 `run.py` 参数。

采集：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\run_collect_task.ps1 -Headless
```

花名册：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\run_roster_task.ps1 -Headless
```

组织列表：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\run_orglist_task.ps1 -Headless
```

评估：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\run_audit_task.ps1
```

待办同步：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\run_sync_todo_status_task.ps1 -Headless
```

这些脚本统一具备以下特性：

- 默认读取 `.venv-win`
- 默认优先取 `settings.prod.yaml`
- 自动落日志到 `automation/logs/windows_tasks`
- 透传退出码，便于计划任务判定成功失败

## 6. Web UI 与 API

### 6.1 构建前端

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\build_webui.ps1 -Install
```

默认行为：

- 执行 `npm ci`
- 执行 `npm run build`
- 默认将前端 API Base 设为同源 `/api`

### 6.2 启动 API

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\start_api.ps1
```

说明：

- 默认启动 `uvicorn automation.api.main:app`
- 默认监听 `127.0.0.1:8000`
- 若存在 `webui/dist`，FastAPI 会自动托管静态页面
- 正式运行不使用 `--reload`

### 6.3 本地前端开发

如果仅做前端开发，仍可使用 Vite：

```powershell
cd .\webui
npm install
npm run dev
```

当前默认已配置 `/api -> http://127.0.0.1:8000` 代理，因此前端开发态一般无需再手工设置 `VITE_API_BASE_URL`。

## 7. PostgreSQL 切换与验收

### 7.1 探测目标数据库

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\probe_postgres.ps1
```

输出内容包括：

- 当前连接到的数据库、用户、schema、版本
- `12` 张核心表是否存在
- `refresh_组织属性查询` 是否存在
- 主数据摘要

### 7.2 备份旧库

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\backup_postgres.ps1 -PgBinDir "C:\Program Files\PostgreSQL\17\bin"
```

### 7.3 恢复到 Windows PostgreSQL

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\restore_postgres.ps1 -InputFile .\automation\backups\clawcheck_20260320_120000.dump -PgBinDir "C:\Program Files\PostgreSQL\17\bin" -DropAndCreateDb
```

### 7.3A 一键执行切库流程

如需将 `probe -> backup -> restore -> dbinit -> acceptance` 串成一次执行，可使用：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\cutover_postgres.ps1 `
  -PgBinDir "C:\Program Files\PostgreSQL\17\bin" `
  -TargetHost "127.0.0.1" `
  -TargetPort 5440 `
  -TargetDbName "clawcheck" `
  -TargetUser "clawcheck" `
  -TargetPassword "your_password" `
  -DropAndCreateDb
```

如果源库仍是旧环境，可再补：

- `-SourceHost`
- `-SourcePort`
- `-SourceDbName`
- `-SourceUser`
- `-SourcePassword`

### 7.4 初始化缺失对象

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\run_dbinit_task.ps1
```

### 7.5 切库后验收

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\accept_postgres.ps1
```

验收通过标准：

- `12` 张核心表全部存在
- `refresh_组织属性查询` 存在
- 探针输出无连接异常

## 8. Windows 计划任务

### 8.1 注册单个计划任务

已提供 Windows 计划任务注册脚本：

- `automation/scripts/register_windows_task.ps1`

示例：每天 `08:30` 运行花名册同步

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\register_windows_task.ps1 `
  -TaskType roster `
  -ScheduleType Daily `
  -At "08:30" `
  -TaskScriptArguments "-Headless"
```

示例：每小时运行待办同步

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\register_windows_task.ps1 `
  -TaskType sync-todo-status `
  -ScheduleType Hourly `
  -At "08:00" `
  -IntervalMinutes 60 `
  -TaskScriptArguments "-Headless"
```

### 8.2 建议的任务拆分

建议至少拆成以下任务：

- `collect`
- `roster`
- `orglist`
- `audit`
- `sync-todo-status`

不建议把所有动作串成一个超级任务，否则失败定位困难、重跑范围过大。

### 8.3 注册 API 开机自启动

如需把 FastAPI 注册为开机自启动任务：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\register_api_startup_task.ps1 -Force
```

默认行为：

- 通过 `start_api.ps1` 启动 API
- 默认在系统启动时触发
- 默认监听 `127.0.0.1:8000`

## 9. 测试

完整 Python 测试：

```powershell
.\.venv-win\Scripts\python.exe -m pytest -q
```

编码检查：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\check_text_encoding.py
```

仅运行本轮新增的基础测试：

```powershell
.\.venv-win\Scripts\python.exe -m pytest .\tests\test_api_main.py .\tests\test_db_admin.py -q
```

## 10. 输出目录

- 日志：`automation/logs/`
- Windows 任务日志：`automation/logs/windows_tasks/`
- 截图：`automation/screenshots/`
- 登录态：`automation/state/`
- 下载目录：`automation/downloads/`
- 数据库备份：`automation/backups/`

## 11. 运行注意事项

- 默认首页入口仍为 `https://hr.onewo.com/ierp/?formId=home_page`
- 花名册实际入口为 `在职人员花名册`
- 花名册导出按钮实际文案为 `转后台执行`
- 花名册导入会刷新 PostgreSQL 表 `人员属性查询`
- 组织列表导入会刷新 PostgreSQL 表 `组织属性查询`
- 若目标库仍为 `011` 之前的英文固定字段结构，先执行 `automation/sql/012_rename_columns_to_cn_fixed_schema.sql`
- `run.py collect` 仍支持把旧辅助表 `basic_info` / `permission_apply_detail` / `approval_record` 迁入中文结构

## 12. 与 WSL 的关系

当前 README 不再把 WSL 作为正式运行前提。

如需继续使用 WSL，请明确区分：

- WSL：个人开发辅助环境
- Windows：正式运行环境

任何正式值班、定时任务、数据库承载、页面发布，均应以 Windows 原生运行链路为准。

## 13. 开发环境标准化补充

### 13.1 Python venv 版本校验

`install_windows_env.ps1` 现在会默认校验 `.venv-win` 的 Python 版本。

- 当 venv 不存在时：自动创建
- 当 venv 版本与 `-PythonVersion` 不一致时：默认自动重建
- 如需保留现有 venv：显式传入 `-SkipRecreateOnVersionMismatch`
- 如需强制重建：显式传入 `-ForceRecreateVenv`

示例：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\install_windows_env.ps1 -IncludeDev -PythonVersion 3.12
```

### 13.2 Node.js 与 npm

项目脚本优先按以下顺序定位 Node.js：

1. `-NodeDir`
2. 用户环境变量 `CLAWCHECK_NODE_DIR`
3. 系统 `PATH`

安装 Node.js：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\install_node_windows.ps1
```

如需把 Node 安装目录同时写入用户 PATH：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\install_node_windows.ps1 -PersistUserPath
```

### 13.3 本地统一启停

统一开发入口：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\start_all.ps1
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\status_all.ps1
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\restart_all.ps1
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\stop_all.ps1
```

前端开发单独启动：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\start_webui_dev.ps1
```

统一运行状态目录：

- `automation/runtime/dev/`

默认会输出：

- PID 文件
- stdout / stderr 日志
- `status.json`

### 13.4 PostgreSQL 探测

标准探测入口：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\probe_postgres.ps1
```

如需统一查看开发服务状态，优先使用：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\status_all.ps1
```

### 13.5 最小质量门禁

统一质量检查入口：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\check_quality.ps1
```

默认包含：

- `ruff check automation tests`
- `python -m compileall automation`
- `python -m pytest -q`
- `npm run build`
