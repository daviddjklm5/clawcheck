# 方案编号300：本项目 Windows 原生部署替代 WSL 运行方案文档

## 1. 方案目标

本方案目标是将 `clawcheck` 的日常运行环境从“依赖 WSL2 内常驻开发进程”迁移为“Windows 原生部署”，降低 `vmmemWSL` 占用，减少对 WSL 的依赖。

本方案明确交付以下结果：

- 本项目在 Windows 主机上可完成安装、配置、运行与发布
- 日常运行不再要求开启 WSL
- PostgreSQL 不再依赖 Docker Desktop + WSL2
- Web UI 不再依赖 `vite dev` 常驻进程
- API 不再以 `uvicorn --reload` 作为正式运行方式
- Playwright 自动化在 Windows 原生 Python 环境下可运行
- WSL 保留为可选开发辅助环境，不再是正式部署前提

本方案的核心目标不是“把代码拷到 Windows”这么简单，而是把当前高内存占用的运行模式整体切换掉。

## 2. 背景与问题

### 2.1 当前现场情况

`2026-03-20` 对本机运行态排查结果显示：

- WSL 当前总内存占用约 `6.1GB`
- 其中约 `4.0GB+` 为 Linux 文件缓存
- 约 `2.2GB` 为进程常驻内存
- `node` 相关进程合计约 `2.0GB`
- 头部进程包括：
  - VS Code Remote `extensionHost` 约 `829MB`
  - Pylance 约 `440MB`
  - `vite` 开发服务约 `182MB`
  - 其他 VS Code 语言服务、watcher、扩展进程若干
- Docker 中 `clawcheck-postgres` 容器约 `405MB`

同时，本机 WSL 配置存在如下约束：

- `memory=8GB`
- `swap=32GB`
- `autoMemoryReclaim=gradual`

这意味着：

- 只要项目继续在 WSL 内以开发态方式运行，`vmmemWSL` 就会长期维持高位
- 即使部分内存只是缓存，Windows 任务管理器中也会体现为 `vmmemWSL` 高占用

### 2.2 当前部署形态的实际问题

当前项目虽未形成完整“生产部署手册”，但实际运行方式已体现出明显 WSL 依赖：

1. Python 环境、Playwright、FastAPI 运行均以 Linux/WSL 命令为主
2. Web UI 以 `vite dev` 方式常驻运行
3. PostgreSQL 当前存在 Docker 容器运行形态
4. README 与部分报错提示使用 `.venv/bin/python`、`/home/...` 等 Linux 路径口径
5. VS Code Remote + Pylance + Vite 使 WSL 变成“开发工具运行容器”，而不是单纯代码目录

问题本质不是 WSL 本身，而是“正式或准正式运行仍建立在 WSL 开发态栈之上”。

## 3. 方案边界

### 3.1 本方案纳入范围

- Windows 原生部署总体方案
- Python、Playwright、PostgreSQL、Web UI 的 Windows 化运行方式
- 运行命令、发布方式、服务托管方式的调整
- 从内存占用角度对不同部署方式进行取舍

### 3.2 本方案不纳入范围

- 不改业务表中文命名规范
- 不改现有 SQL 业务口径
- 不重写自动化流程逻辑
- 不把项目改造成云原生或 Kubernetes 方案
- 不在本方案内直接引入新的前端框架或新的后端主语言

## 4. 设计原则

### 4.1 先消除运行态 WSL 依赖，再谈开发体验

本方案优先解决的是：

- 日常运行是否必须依赖 WSL
- 内存是否被 `vmmemWSL` 长时间占住

而不是优先优化：

- Linux 开发命令是否更顺手

### 4.2 正式运行禁止继续沿用开发态常驻进程

以下形态不能继续作为正式部署方案：

- `uvicorn --reload`
- `npm run dev`
- Docker Desktop 承载 PostgreSQL
- VS Code Remote 常开并承接服务运行

### 4.3 Windows 部署必须保持对现有代码低侵入

本项目主体仍保持：

- `Python`
- `Playwright`
- `PostgreSQL`
- `FastAPI`
- `React + Vite`

迁移重点是运行方式，不是重写系统。

### 4.4 WSL 由“必需运行环境”降级为“可选辅助环境”

迁移完成后：

- 运维、值班、日常使用人员可完全不依赖 WSL
- 研发如需保留 WSL 作为个人开发工具，可继续使用
- 但任何正式运行步骤都不能再要求“先打开 WSL”

## 5. 备选方案评估

### 5.1 方案 A：继续使用 WSL，只优化 `.wslconfig`

做法：

- 调小 `memory`
- 调整 `autoMemoryReclaim`
- 减少部分常驻进程

优点：

- 改动最小

缺点：

- 不能消除 `vmmemWSL`
- 仍要求项目运行依赖 WSL
- Docker Desktop、VS Code Remote、Vite Dev 的额外占用仍存在

结论：

- 不满足“减少对 WSL 的依赖”这一主目标
- 不推荐作为 `300` 正式方案

### 5.2 方案 B：迁到 Windows，但 PostgreSQL 继续放在 Docker Desktop

做法：

- Python 与 Web UI 改到 Windows
- PostgreSQL 继续通过 Docker Desktop 运行

优点：

- 数据库迁移阻力较小

缺点：

- Docker Desktop 在 Windows 上通常仍依赖 WSL2
- 仍会保留 `vmmemWSL` 占用
- 只迁移了一半，不能真正摆脱 WSL

结论：

- 不推荐

### 5.3 方案 C：Windows 原生 Python + Windows 原生 PostgreSQL + Web UI 静态发布

做法：

- Python venv 在 Windows 本机创建
- Playwright 在 Windows 本机安装与执行
- PostgreSQL 使用 Windows 服务或既有独立实例
- 前端使用 `npm run build` 产出静态文件
- 静态资源由 FastAPI 或 Windows Web Server 承接

优点：

- 从根上消除对 WSL 运行态的依赖
- 不再保留 `vite dev` 常驻进程
- 不再保留 Docker Desktop + WSL2 的数据库占用
- 运行进程数量更少，结构更稳定

缺点：

- 需要补齐 Windows 部署脚本、文档和部分跨平台细节

结论：

- **推荐作为 `300` 正式方案**

## 6. 推荐总方案

`300` 推荐采用以下目标架构：

### 6.1 后端运行层

- 使用 Windows 原生 Python `3.12.x`
- 在仓库根目录创建独立 Windows 虚拟环境，建议命名：
  - `.venv-win`
- 通过 Windows 虚拟环境运行：
  - `automation/scripts/run.py`
  - `automation.api.main:app`

推荐命令形态：

```powershell
py -3.12 -m venv .venv-win
.venv-win\Scripts\python.exe -m pip install -r automation\requirements.txt
.venv-win\Scripts\python.exe -m pip install -r automation\requirements-dev.txt
.venv-win\Scripts\python.exe -m playwright install chromium
```

说明：

- 不建议复用 WSL 下已有 `.venv`
- Linux 与 Windows 的二进制依赖不同，同目录复用虚拟环境风险很高

### 6.2 自动化浏览器层

- Playwright 改为在 Windows 原生 Python 下执行
- 正式运行优先采用：
  - `headless`
  - 或受控 `headed`
- 推荐后续补充可选配置：
  - `browser.channel`

Windows 推荐优先支持：

- `msedge`
- 或 Playwright 自带 `chromium`

原因：

- 便于与 Windows 桌面环境一致
- 减少“浏览器只在 WSL 安装”的环境分裂

### 6.3 数据库层

PostgreSQL 推荐两种可接受落地方式：

1. 首选：Windows 原生 PostgreSQL 服务
2. 备选：已有独立 PostgreSQL 服务器

本方案明确不推荐以下形态作为正式运行依赖：

- Docker Desktop + WSL2 承载 PostgreSQL

推荐口径：

- 端口可继续沿用现有正式配置中的 `5440`
- 库名、Schema、中文表名规范保持不变
- `automation/config/settings*.yaml` 与 `IERP_PG_*` 环境变量继续沿用

### 6.4 Web UI 层

Web UI 正式运行不再使用：

- `npm run dev`

改为：

1. 在发布时执行前端构建
2. 生成 `webui/dist`
3. 以静态资源方式提供

推荐承接方式：

1. 首选：由 FastAPI 直接挂载 `webui/dist`
2. 备选：由 IIS / Nginx / 其他 Windows Web Server 承接静态文件，再反向代理 `/api`

在本项目当前体量下，推荐首选 FastAPI 挂载静态资源，原因是：

- 进程更少
- 部署更简单
- 不再需要 Vite Dev Server 常驻

### 6.5 服务托管层

正式运行建议拆成两类：

1. 长驻服务
   - `clawcheck-api`
2. 定时任务
   - `collect`
   - `roster`
   - `orglist`
   - `audit`
   - `sync-todo-status`

推荐 Windows 承载方式：

- 长驻服务：
  - `WinSW` 或 `NSSM`
- 定时任务：
  - Windows Task Scheduler

不再建议：

- 靠终端手工保持进程常驻
- 靠 VS Code 终端挂着服务

## 7. 需要同步改造的工程点

本方案虽以运行方式迁移为主，但要真正落地，至少需要补齐以下工程项。

### 7.1 命令与文档口径改造

当前仓库存在大量 Linux/WSL 口径，例如：

- `.venv/bin/python`
- `source .venv/bin/activate`
- `/home/shangmeilin/clawcheck`

需要统一改为：

- 平台无关命令说明
- 或同时给出 `bash` / `PowerShell` 两套命令

优先需要同步的文档与提示包括：

- `automation/README.md`
- 相关方案计划文档中的运行步骤
- 代码内依赖安装失败提示

### 7.2 Python 环境隔离

需要明确仓库中的环境规范：

- WSL 使用 `.venv`
- Windows 使用 `.venv-win`

避免以下问题：

- 不同平台覆盖同一个虚拟环境目录
- compiled wheel 混用
- Playwright 浏览器依赖与 Python site-packages 混乱

### 7.3 正式 API 运行模式改造

当前文档中的 API 示例为：

```bash
.venv/bin/uvicorn automation.api.main:app --reload
```

正式运行应改为：

```powershell
.venv-win\Scripts\python.exe -m uvicorn automation.api.main:app --host 127.0.0.1 --port 8000
```

要求：

- 禁止 `--reload`
- 日志输出到既有 `automation/logs`
- 配置文件继续读取仓库内 YAML 与环境变量

### 7.4 Web UI 发布模式改造

当前前端仍按开发态运行：

- `npm install`
- `npm run dev`

正式发布应调整为：

```powershell
cd webui
npm ci
npm run build
```

后续需要新增：

- FastAPI 静态资源挂载
- 或 Windows 静态站点配置说明

### 7.5 PostgreSQL 部署口径改造

需补齐以下内容：

- Windows PostgreSQL 安装与初始化说明
- 新库初始化命令
- 正式配置示例
- 备份、恢复、升级口径

推荐沿用已有 runner 初始化方式：

```powershell
.venv-win\Scripts\python.exe automation\scripts\run.py dbinit --config automation\config\settings.prod.yaml --credentials automation\config\credentials.prod.local.yaml
```

### 7.6 可选的代码级增强项

为提高 Windows 落地稳定性，建议追加以下低侵入改造：

1. 新增 `browser.channel` 配置
2. 新增 FastAPI 静态资源挂载
3. 将安装提示从 `.venv/bin/python` 改为更中性的 `python -m pip`
4. 补充 Windows 启动脚本：
   - `automation/scripts/start_api.ps1`
   - `automation/scripts/build_webui.ps1`
   - `automation/scripts/install_windows_env.ps1`

## 8. 分阶段实施方案

### 8.1 第一阶段：文档与命令去 WSL 化

目标：

- 先让项目具备清晰的 Windows 安装与运行口径

实施项：

- 新增 `300` 方案文档
- 补 Windows 部署说明
- 更新 `automation/README.md`
- 统一运行命令与环境说明

验收标准：

- 新同事在不依赖 WSL 的前提下，可以按文档完成环境安装

### 8.2 第二阶段：Windows 后端运行打通

目标：

- `run.py` 与 FastAPI 在 Windows 下稳定运行

实施项：

- 建立 `.venv-win`
- 安装 Python 依赖与 Playwright
- 验证：
  - `check`
  - `login`
  - `collect`
  - `roster`
  - `orglist`
  - `audit`

验收标准：

- 主要自动化命令在 Windows PowerShell 中可执行

### 8.3 第三阶段：PostgreSQL 去 Docker Desktop 化

目标：

- 数据库不再依赖 WSL2

实施项：

- 部署 Windows PostgreSQL 服务或切换到独立 PostgreSQL 实例
- 导入现有数据
- 验证表结构、中文字段、函数、视图
- 验证 `dbinit`、写库、查询 API

验收标准：

- 停止 Docker Desktop 后，项目数据库能力仍可用

### 8.4 第四阶段：Web UI 去 Vite Dev 化

目标：

- 前端发布不再依赖 Node 常驻开发服务

实施项：

- 采用 `npm run build` 产出静态文件
- FastAPI 或 Windows Web Server 承接静态资源
- 调整 API Base URL 与跨域策略

验收标准：

- 停止 `vite` 进程后，页面仍可访问并调用真实 API

### 8.5 第五阶段：服务化与切换

目标：

- 完成正式 Windows 化运行

实施项：

- API 注册为 Windows 服务
- 定时任务接入 Windows Task Scheduler
- 完成运行监控、日志目录、失败恢复说明
- 保留 WSL 作为回滚路径

验收标准：

- 正常使用场景不再需要打开 WSL

## 9. 预期收益

### 9.1 内存收益

迁移完成后，以下高占用来源将被移除或显著下降：

- `vmmemWSL`
- VS Code Remote for WSL 常驻内存
- WSL 文件缓存占用
- `vite dev` 常驻进程
- Docker Desktop + WSL2 的 PostgreSQL 占用

预期效果不是“总内存永远很低”，而是：

- 不再由 `vmmemWSL` 把一整块内存长期锁在 WSL 中
- 进程占用更接近真实业务负载

### 9.2 运行稳定性收益

- 正式运行与开发态分离
- 服务重启方式更标准
- 值班人员无需掌握 WSL/Remote VS Code
- 故障定位更接近 Windows 本机服务体系

### 9.3 维护收益

- 部署口径统一
- 降低“工具链跑在 WSL、浏览器开在 Windows、数据库在 Docker”这种三层分裂
- 后续更容易补齐安装脚本、服务脚本与交付手册

## 10. 风险与应对

### 10.1 Playwright 在 Windows 下的兼容性风险

风险：

- 企业浏览器策略、下载目录权限、弹窗焦点行为可能与 WSL 不同

应对：

- 先逐条验证 `check/login/collect/roster/orglist`
- 保留 `headless/headed` 双模式
- 必要时增加 `browser.channel`

### 10.2 虚拟环境混用风险

风险：

- 同一仓库跨平台复用一个 `.venv`，会造成依赖损坏

应对：

- 明确分离 `.venv` 与 `.venv-win`
- 文档中禁止跨平台复用虚拟环境目录

### 10.3 数据库迁移风险

风险：

- 从 Docker PostgreSQL 切到 Windows PostgreSQL 时，存在数据迁移、扩展、编码与权限差异

应对：

- 先做全库备份
- 先在非正式库回放 `dbinit` 与验收 SQL
- 切换窗口保留回滚路径

### 10.4 前端静态发布切换风险

风险：

- 目前前端开发环境依赖 Vite 的代理与热更新

应对：

- 明确区分开发态和正式态
- 正式态只验证构建产物与 API 联调

## 11. 回滚策略

在 `300` 切换期间，允许短期保留双运行口径：

1. Windows 原生运行链路
2. WSL 原运行链路

若 Windows 化切换中出现阻塞，可回滚到原有 WSL 路径，但回滚要求：

- 不回滚业务表结构
- 不回滚中文字段体系
- 仅回滚运行承载环境

当 Windows 方案稳定后，再将 WSL 口径从正式文档中降级为“开发辅助说明”。

## 12. 实施结论

`300` 的正式结论如下：

- 本项目应从“WSL 内开发态常驻运行”迁移到“Windows 原生正式运行”
- 正式部署推荐采用：
  - Windows 原生 Python
  - Windows 原生 PostgreSQL 或独立 PostgreSQL 实例
  - FastAPI 正式服务
  - Web UI 静态发布
  - Windows 服务 + 计划任务
- Docker Desktop + WSL2 不再作为正式数据库承载方案
- `vite dev` 与 `uvicorn --reload` 不再作为正式运行方式

该方案是当前最符合以下目标的路线：

- 减少 `vmmemWSL` 占用
- 减少对 WSL 的依赖
- 保持现有技术栈低侵入演进
- 控制改造成本

## 13. 建议后续落地顺序

建议按以下顺序推进后续实施：

1. 先补 Windows 部署文档与脚本
2. 再打通 Windows 原生 Python + Playwright
3. 再切换 PostgreSQL 承载方式
4. 再改 Web UI 为静态发布
5. 最后完成服务化与正式切换

不建议一开始同时改代码、数据库、服务托管和前端发布，否则排障面会过大。
