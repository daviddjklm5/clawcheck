from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from automation.utils.config_loader import Settings, load_settings

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = REPO_ROOT / "automation/config/settings.yaml"
PROD_SETTINGS_PATH = REPO_ROOT / "automation/config/settings.prod.yaml"


def _resolve_settings_path() -> Path:
    if PROD_SETTINGS_PATH.exists():
        return PROD_SETTINGS_PATH
    return DEFAULT_SETTINGS_PATH


def _load_runtime_settings() -> tuple[Path, Settings]:
    settings_path = _resolve_settings_path()
    settings = load_settings(settings_path)

    settings.db.host = os.getenv("IERP_PG_HOST", settings.db.host)
    settings.db.port = int(os.getenv("IERP_PG_PORT", str(settings.db.port)))
    settings.db.dbname = os.getenv("IERP_PG_DBNAME", settings.db.dbname)
    settings.db.user = os.getenv("IERP_PG_USER", settings.db.user)
    settings.db.password = os.getenv("IERP_PG_PASSWORD", settings.db.password)
    settings.db.schema = os.getenv("IERP_PG_SCHEMA", settings.db.schema)
    settings.db.sslmode = os.getenv("IERP_PG_SSLMODE", settings.db.sslmode)
    settings.ai.provider = os.getenv("CLAWCHECK_AI_PROVIDER", settings.ai.provider)
    settings.ai.base_url = os.getenv("CLAWCHECK_AI_BASE_URL", settings.ai.base_url)
    settings.ai.model = os.getenv("CLAWCHECK_AI_MODEL", settings.ai.model)
    settings.ai.timeout_seconds = int(
        os.getenv("CLAWCHECK_AI_TIMEOUT_SECONDS", str(settings.ai.timeout_seconds))
    )
    settings.ai.max_output_tokens = int(
        os.getenv("CLAWCHECK_AI_MAX_OUTPUT_TOKENS", str(settings.ai.max_output_tokens))
    )
    settings.ai.api_key_env = os.getenv("CLAWCHECK_AI_API_KEY_ENV", settings.ai.api_key_env)

    return settings_path, settings


def _to_repo_relative(raw_path: str) -> str:
    path = Path(raw_path)
    if not path.is_absolute():
        path = REPO_ROOT / path

    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def get_runtime_configuration_summary() -> dict[str, Any]:
    settings_path, settings = _load_runtime_settings()

    env_overrides = {
        "IERP_PG_HOST": bool(os.getenv("IERP_PG_HOST")),
        "IERP_PG_PORT": bool(os.getenv("IERP_PG_PORT")),
        "IERP_PG_DBNAME": bool(os.getenv("IERP_PG_DBNAME")),
        "IERP_PG_USER": bool(os.getenv("IERP_PG_USER")),
        "IERP_PG_PASSWORD": bool(os.getenv("IERP_PG_PASSWORD")),
        "IERP_PG_SCHEMA": bool(os.getenv("IERP_PG_SCHEMA")),
        "IERP_PG_SSLMODE": bool(os.getenv("IERP_PG_SSLMODE")),
        "CLAWCHECK_AI_PROVIDER": bool(os.getenv("CLAWCHECK_AI_PROVIDER")),
        "CLAWCHECK_AI_BASE_URL": bool(os.getenv("CLAWCHECK_AI_BASE_URL")),
        "CLAWCHECK_AI_MODEL": bool(os.getenv("CLAWCHECK_AI_MODEL")),
        "CLAWCHECK_AI_TIMEOUT_SECONDS": bool(os.getenv("CLAWCHECK_AI_TIMEOUT_SECONDS")),
        "CLAWCHECK_AI_MAX_OUTPUT_TOKENS": bool(os.getenv("CLAWCHECK_AI_MAX_OUTPUT_TOKENS")),
        "CLAWCHECK_AI_API_KEY_ENV": bool(os.getenv("CLAWCHECK_AI_API_KEY_ENV")),
        settings.ai.api_key_env: bool(os.getenv(settings.ai.api_key_env)),
    }

    environment_label = "生产默认配置" if settings_path == PROD_SETTINGS_PATH else "本地默认配置"
    browser_mode = "可见浏览器" if settings.browser.headed else "无头浏览器"

    return {
        "environmentLabel": environment_label,
        "configFile": str(settings_path.relative_to(REPO_ROOT)),
        "stats": [
            {
                "label": "浏览器模式",
                "value": browser_mode,
                "hint": "前端仅展示摘要，不在页面暴露账号口令。",
                "tone": "info",
            },
            {
                "label": "数据库 Schema",
                "value": settings.db.schema or "public",
                "hint": "默认沿用现有 PostgreSQL 中文表结构。",
                "tone": "success",
            },
            {
                "label": "日志目录",
                "value": _to_repo_relative(settings.runtime.logs_dir),
                "hint": "用于查看自动化执行日志与结果 JSON。",
                "tone": "default",
            },
            {
                "label": "敏感信息策略",
                "value": "不展示密码",
                "hint": "只显示 host / port / dbname / schema 等摘要。",
                "tone": "warning",
            },
        ],
        "runtime": [
            {
                "label": "当前配置文件",
                "value": str(settings_path.relative_to(REPO_ROOT)),
                "hint": "API 启动时自动读取。存在 prod 文件时优先取 prod。",
            },
            {
                "label": "默认首页",
                "value": settings.app.home_url,
                "hint": "沿用现有自动化脚本入口地址。",
            },
            {
                "label": "运行重试次数",
                "value": str(settings.runtime.retries),
                "hint": f"重试等待 {settings.runtime.retry_wait_sec:.1f} 秒。",
            },
        ],
        "browser": [
            {
                "label": "浏览器是否可见",
                "value": "是" if settings.browser.headed else "否",
                "hint": "对应 `browser.headed`。",
            },
            {
                "label": "slow_mo_ms",
                "value": str(settings.browser.slow_mo_ms),
                "hint": "用于减慢浏览器动作，便于观察。",
            },
            {
                "label": "timeout_ms",
                "value": str(settings.browser.timeout_ms),
                "hint": "页面控件与普通等待超时。",
            },
            {
                "label": "navigation_timeout_ms",
                "value": str(settings.browser.navigation_timeout_ms),
                "hint": "页面跳转超时。",
            },
            {
                "label": "ignore_https_errors",
                "value": "是" if settings.browser.ignore_https_errors else "否",
                "hint": "保持与当前 Playwright 行为一致。",
            },
        ],
        "database": [
            {
                "label": "host",
                "value": settings.db.host or "未配置",
                "hint": "可被环境变量覆盖。",
            },
            {
                "label": "port",
                "value": str(settings.db.port),
                "hint": "只显示端口，不显示密码。",
            },
            {
                "label": "dbname",
                "value": settings.db.dbname or "未配置",
                "hint": "当前项目默认库名摘要。",
            },
            {
                "label": "user",
                "value": settings.db.user or "未配置",
                "hint": "仅展示用户名摘要。",
            },
            {
                "label": "schema",
                "value": settings.db.schema or "public",
                "hint": "对应中文业务表所在 schema。",
            },
            {
                "label": "sslmode",
                "value": settings.db.sslmode or "prefer",
                "hint": "直接读取当前运行配置。",
            },
        ],
        "paths": [
            {
                "label": "state_file",
                "value": _to_repo_relative(settings.runtime.state_file),
                "hint": "Playwright 登录态文件。",
            },
            {
                "label": "logs_dir",
                "value": _to_repo_relative(settings.runtime.logs_dir),
                "hint": "任务执行日志输出目录。",
            },
            {
                "label": "screenshots_dir",
                "value": _to_repo_relative(settings.runtime.screenshots_dir),
                "hint": "异常截图与探针截图目录。",
            },
            {
                "label": "downloads_dir",
                "value": _to_repo_relative(settings.runtime.downloads_dir),
                "hint": "花名册与组织列表下载目录。",
            },
        ],
        "securityNotes": [
            "UI 第一阶段不开放口令在线编辑。",
            "数据库密码仍只保留在本地 YAML 或环境变量中。",
            f"环境变量覆盖状态：{', '.join([name for name, enabled in env_overrides.items() if enabled]) or '无'}。",
        ],
    }
