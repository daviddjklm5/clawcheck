# 方案编号302：WebUI 依赖供应链 IOC 拦截加固方案文档

## 1. 背景

`2026-03-31` 出现了 Axios npm 发布链路被劫持事件。针对本项目 `webui` 的依赖安装链路，需要补齐“安装前静态拦截”能力，避免在 `npm ci` 阶段拉取并执行已知恶意版本。

本方案仅聚焦 WebUI 依赖安装安全，不改变业务功能与数据库逻辑。

## 2. 目标与边界

目标：

- 在 `npm ci` 前自动扫描 `package.json` 与 `package-lock.json`
- 对已知 IOC 命中直接失败退出，阻断安装流程
- 本地脚本与 CI 使用同一套校验逻辑

边界：

- 不替代通用漏洞扫描（如 `npm audit`）
- 不引入新包管理器
- 不改动现有 WebUI 技术栈（React + Vite）

## 3. IOC 口径

当前拦截口径：

- `axios@1.14.1`
- `axios@0.30.4`
- `plain-crypto-js`（任意版本均视为可疑，直接阻断）

后续如有新增 IOC，统一在 `automation/scripts/check_webui_supply_chain_ioc.js` 增补。

## 4. 实施改造

### 4.1 新增统一检查脚本

- 新增：`automation/scripts/check_webui_supply_chain_ioc.js`
- 职责：
  - 解析 `webui/package.json`
  - 解析 `webui/package-lock.json`
  - 命中 IOC 时输出命中项并 `exit 1`

### 4.2 接入 WebUI 安装入口

- `webui/package.json` 新增：
  - `preinstall`：安装前自动执行 IOC 检查
  - `security:check-supply-chain`：手动触发检查
- `webui/package.json` 的 `build` 增加供应链检查步骤
- `webui/.npmrc` 新增 `min-release-age=7`，默认忽略发布时间不足 7 天的版本

### 4.3 接入本地脚本入口

- `automation/scripts/build_webui.ps1`
- `automation/scripts/start_webui_dev.ps1`

在执行 `npm ci` 前先运行 IOC 检查，命中即中断流程。

### 4.4 接入 CI

- `.github/workflows/ci.yml`

在 `Install webui deps` 之前新增 `Check webui npm supply chain IOC` 步骤。

## 5. 使用与验收

手动执行：

```powershell
node automation/scripts/check_webui_supply_chain_ioc.js --webui-dir webui
```

验收标准：

- 未命中 IOC 时返回 0 并输出 `OK`
- 命中 IOC 时返回非 0 并输出命中明细
- CI 中该检查步骤可独立失败并阻断后续 `npm ci`

## 6. 回滚说明

若需临时回滚，仅回退以下改动：

- `automation/scripts/check_webui_supply_chain_ioc.js`
- `webui/package.json` 中新增脚本
- `build_webui.ps1` / `start_webui_dev.ps1` 中新增调用
- `ci.yml` 中新增检查步骤

回滚不涉及数据库与业务数据。
