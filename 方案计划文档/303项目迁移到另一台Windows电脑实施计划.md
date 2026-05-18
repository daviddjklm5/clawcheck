# 方案编号303：项目迁移到另一台 Windows 电脑实施计划

## 1. 文档状态

- 状态：现行
- 适用范围：将本项目从当前 Windows 电脑迁移到另一台 Windows 电脑
- 关联方案：
  - `300本项目Windows原生部署替代WSL运行方案文档.md`
  - `301开发环境标准化与本地一键启停治理方案文档.md`
  - `001SQL迁移清单.md`
- 是否涉及数据库结构变更：否
- 是否涉及 SQL 迁移清单变更：否

## 2. 目标

本实施计划用于指导将 `clawcheck` 项目完整迁移到另一台 Windows 电脑，并在新电脑上恢复以下能力：

- 代码可拉取、可提交、可推送
- Python 运行环境可重建
- Node.js / npm 与 WebUI 构建可用
- PostgreSQL 可连接，数据可恢复或重新初始化
- Playwright 浏览器依赖可用
- iERP / EHR 登录态可恢复或重新生成
- 后端 API、任务脚本、WebUI 可启动
- 基础测试与构建验收通过

本计划不改变业务表结构、字段中文化口径、采集逻辑和审批规则。

## 3. 迁移原则

### 3.1 代码走 Git

正式迁移优先通过 Git 拉取项目代码，不建议直接复制整个仓库目录作为主方案。

旧电脑迁移前应完成：

```powershell
git status
git push origin main
```

若远程推送因网络原因失败，可临时采用仓库目录压缩包迁移，但新电脑恢复后仍应尽快与远程仓库对齐。

### 3.2 环境重新构建

以下目录不建议从旧电脑直接复制到新电脑：

- `.venv-win`
- `webui/node_modules`
- `webui/dist`
- Playwright 浏览器安装缓存

新电脑应按项目脚本重新安装依赖，避免二进制依赖、路径和版本来源漂移。

### 3.3 真实密码与登录态本地保管

真实数据库密码、生产配置、浏览器登录态不得写入 Git 或方案文档。

允许迁移的本地私有材料包括：

- `automation/config/settings.yaml`
- `automation/config/settings.prod.yaml`
- `automation/config/credentials.prod.local.yaml`，如本机实际使用
- 本机环境变量清单
- Playwright storage state 文件
- PostgreSQL 备份文件

## 4. 旧电脑迁出准备

### 4.1 确认代码状态

执行：

```powershell
git status --short --branch
git log --oneline --decorate -5
```

要求：

- 工作区无未确认变更，或已明确哪些变更需要迁移
- 本地分支已推送到远程，除非存在明确网络阻塞
- 当前迁移分支以 `main` 为主

### 4.2 备份本地配置

从旧电脑备份以下文件：

```text
automation/config/settings.yaml
automation/config/settings.prod.yaml
```

如存在本地凭据文件、`.env` 或系统环境变量，应同步整理迁移清单，但不得写入仓库。

如本机运行链路使用 `automation/config/credentials.prod.local.yaml`，应同步备份该文件。该文件属于本地私有凭据，不得提交到 Git。

数据库配置至少应记录以下非敏感信息：

- host
- port
- dbname
- schema

### 4.3 备份数据库

如新电脑需要保留旧电脑数据，使用 `pg_dump` 备份：

```powershell
pg_dump -h 127.0.0.1 -p 5432 -U postgres -d ierp -Fc -f clawcheck_ierp.backup
```

执行前必须先从 `settings.yaml` 或实际运行环境确认 `host`、`port`、`dbname`、`user`。上方命令中的 `5432`、`postgres`、`ierp` 仅为示例；如旧电脑数据库端口、库名或用户不同，应以实际配置为准。

### 4.4 备份登录态

如采集流程依赖 iERP / EHR 自动登录，应确认 storage state 文件位置，并复制到新电脑相同路径或后续重新生成。

如果登录态与机器、浏览器策略或账号安全策略绑定，旧登录态可能不能复用，此时应在新电脑重新登录生成。

## 5. 新电脑基础软件准备

### 5.1 必装软件

新电脑需安装：

- Git for Windows
- Python `3.12.x`
- Node.js，默认推荐 `C:\Program Files\nodejs\`
- PostgreSQL，版本建议与旧电脑一致或不低于旧电脑
- VS Code，可选

### 5.2 基础验证

执行：

```powershell
git --version
python --version
where python
where node
where npm
node -v
npm -v
```

要求：

- Python 默认开发口径为 `3.12.x`
- Node/npm 来源尽量单一
- 如存在多个 Node/npm 来源，先按 `301` 方案收敛 PATH

## 6. 拉取项目代码

推荐目录：

```powershell
cd C:\Users\Administrator\source\repos
git clone https://github.com/daviddjklm5/clawcheck.git
cd clawcheck
git checkout main
git pull origin main
```

验证：

```powershell
git status --short --branch
```

要求工作区干净，并位于预期分支。

## 7. 恢复本地配置

将旧电脑备份的配置文件复制到新电脑对应位置：

```text
automation/config/settings.yaml
automation/config/settings.prod.yaml
automation/config/credentials.prod.local.yaml
```

其中 `credentials.prod.local.yaml` 仅在旧电脑实际使用该文件时迁移。

重点确认：

```yaml
db:
  host: "127.0.0.1"
  port: 5432
  dbname: "ierp"
  user: "postgres"
  password: "本机真实密码"
  schema: "public"
  sslmode: "prefer"
```

如使用环境变量覆盖，应确认以下变量：

```text
IERP_PG_HOST
IERP_PG_PORT
IERP_PG_DBNAME
IERP_PG_USER
IERP_PG_PASSWORD
IERP_PG_SCHEMA
IERP_PG_SSLMODE
```

## 8. Python 环境初始化

在项目根目录执行：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\install_windows_env.ps1 -PythonVersion 3.12 -IncludeDev
```

完成后验证：

```powershell
.\.venv-win\Scripts\python.exe --version
Get-Content .\.venv-win\pyvenv.cfg
```

要求：

- `.venv-win` 创建成功
- Python 版本为 `3.12.x`
- VS Code 解释器选择 `.venv-win\Scripts\python.exe`
- 开发机应使用 `-IncludeDev` 安装测试依赖
- 正式运行机如不执行测试，可省略 `-IncludeDev`，但迁机验收阶段建议保留

如重建失败，先执行：

```powershell
.\automation\scripts\stop_all.ps1
```

再确认没有残留进程占用 `.venv-win\Scripts\python.exe`。

## 9. Node 与 WebUI 初始化

前端构建前必须执行 preflight：

```powershell
.\automation\scripts\preflight_webui_node.ps1
```

如提示多 Node/npm 来源，应先收敛到单一主用来源。

安装依赖并构建：

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\build_webui.ps1 -Install
```

如 `npm -v` 在 PowerShell 失败，不应直接判定为缺少 npm，应按以下顺序复核：

```powershell
npm.cmd -v
cmd /c npm -v
"C:\Program Files\nodejs\npm.cmd" -v
```

## 10. PostgreSQL 恢复或初始化

### 10.1 方案 A：恢复旧电脑数据库

适用于需要保留旧电脑历史采集数据的场景。

创建数据库：

```powershell
createdb -h 127.0.0.1 -p 5432 -U postgres ierp
```

恢复备份：

```powershell
pg_restore -h 127.0.0.1 -p 5432 -U postgres -d ierp clawcheck_ierp.backup
```

执行前必须先确认 `settings.yaml` 中的 `host`、`port`、`dbname`、`user`。上方命令仅为默认示例，实际迁移时应替换为新电脑数据库配置。

恢复后执行基础查询：

```sql
select count(*) from "申请单基本信息";
select count(*) from "申请单权限列表";
select count(*) from "申请表组织范围";
select count(*) from "权限列表";
select count(*) from "人员属性查询";
```

### 10.2 方案 B：新库初始化

适用于不迁移历史数据、仅在新电脑重新采集的场景。

优先使用项目现有 `dbinit` 入口初始化，不建议按 SQL 文件编号手工全量执行：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py dbinit
```

如需显式指定生产配置与本地凭据：

```powershell
.\.venv-win\Scripts\python.exe .\automation\scripts\run.py dbinit --config automation\config\settings.prod.yaml --credentials automation\config\credentials.prod.local.yaml
```

执行前必须先查看：

```text
方案计划文档/001SQL迁移清单.md
```

手工执行 SQL 仅作为排障或专项修复路径。不得按编号全量执行 `automation/sql`，尤其不得把以下类型 SQL 当作新库初始化脚本执行：

- `回滚`
- `验收`
- `历史补丁`

如必须手工执行 SQL，应先确认对应方案文档、迁移清单状态和当前数据库状态。

## 11. Playwright 与登录态处理

安装 Playwright 浏览器依赖：

```powershell
.\.venv-win\Scripts\python.exe -m playwright install chromium
```

默认只安装 `chromium`。只有明确需要全浏览器兼容性验证时，才使用不带浏览器名称的 `playwright install`。

登录态处理规则：

- 能复用旧电脑 storage state 时，复制到相同路径后验证
- 不能复用时，在新电脑重新登录生成
- 登录态失效时优先重新生成，不直接修改业务采集代码

如涉及 EHR / iERP 统一认证跳转、session 复用和过期恢复，应按 `ehr-login` 相关实现口径排查。

## 12. 启动与验收

### 12.1 后端测试

开发机和迁机验收阶段应执行本节测试；正式运行机如不保留开发依赖，可在验收通过后不长期保留测试依赖。

优先执行核心测试：

```powershell
.\.venv-win\Scripts\python.exe -m pytest tests/test_collect_workbench.py tests/test_documents_router.py
```

条件允许时执行全量测试：

```powershell
.\.venv-win\Scripts\python.exe -m pytest
```

### 12.2 前端构建

```powershell
.\automation\scripts\preflight_webui_node.ps1
powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\build_webui.ps1 -Install
```

### 12.3 服务状态

按 `301` 方案的统一脚本检查：

```powershell
.\automation\scripts\status_all.ps1
```

如需要一键启动开发服务：

```powershell
.\automation\scripts\start_all.ps1
```

## 13. 验收清单

迁移完成后，应逐项确认：

- Git 代码已拉取到 `main` 最新版本
- 工作区干净
- Python 为 `3.12.x`
- `.venv-win` 创建成功
- 开发机已安装测试依赖，或正式运行机已明确不保留开发依赖
- VS Code 解释器指向 `.venv-win\Scripts\python.exe`
- Node/npm 来源单一或已确认脚本可稳定发现
- `preflight_webui_node.ps1` 通过
- `webui` 依赖安装成功
- WebUI 构建通过
- PostgreSQL 可连接
- `settings.yaml` 指向新电脑数据库
- 数据库已恢复或按迁移清单初始化
- Playwright 浏览器已安装
- iERP / EHR 登录态可用或已重新生成
- 核心 pytest 通过
- API 与 WebUI 可启动
- 采集入口能完成一次最小链路验证

## 14. 风险与应对

### 14.1 远程 Git 不可访问

风险：网络阻断导致旧电脑无法推送或新电脑无法拉取。

应对：

- 优先修复网络或 GitHub 访问
- 临时使用压缩包迁移仓库
- 新电脑恢复后尽快与远程仓库重新对齐

### 14.2 Python 版本不一致

风险：新电脑默认 Python 不是 `3.12.x`。

应对：

- 安装 Python `3.12.x`
- 使用 `.venv-win` 作为唯一项目解释器
- 不使用系统 Python `3.10` 执行正式脚本

### 14.3 Node 来源漂移

风险：机器中存在多套 Node/npm，导致 PowerShell、cmd、脚本命中不同来源。

应对：

- 默认推荐 `C:\Program Files\nodejs\`
- 构建前固定执行 `preflight_webui_node.ps1`
- 修改 PATH 后重启终端和 Codex 会话

### 14.4 数据库恢复失败

风险：PostgreSQL 版本、编码、权限或扩展差异导致恢复失败。

应对：

- 优先使用与旧电脑一致的 PostgreSQL 主版本
- 先恢复到测试库验证
- 保留原始 `pg_dump` 备份文件
- 不在失败状态下手工改业务表名或字段名

### 14.5 登录态不可复用

风险：旧电脑 storage state 在新电脑失效。

应对：

- 在新电脑重新登录生成登录态
- 验证统一认证跳转与过期恢复
- 不把登录态失效误判为采集逻辑损坏

## 15. 回滚策略

迁移期间旧电脑不应立即清理。

建议保留以下内容至少一个完整验收周期：

- 原仓库目录
- 原 PostgreSQL 数据库
- 原本地配置文件
- 原 Playwright 登录态
- 最近一次数据库备份

若新电脑迁移失败，可回到旧电脑继续运行；回滚仅涉及运行承载环境，不改变业务数据口径和方案文档口径。

## 16. 实施结论

本项目迁移到另一台 Windows 电脑时，推荐采用以下路径：

1. 代码通过 Git 迁移
2. 数据通过 `pg_dump / pg_restore` 迁移
3. 本地配置和登录态单独备份恢复
4. Python、Node、Playwright 依赖在新电脑重新安装
5. 按 `301` 的统一脚本完成环境检查、启动和验收

该方式能最大限度减少路径污染、二进制依赖不兼容和环境来源漂移，符合当前项目 Windows 原生部署与开发环境标准化口径。
