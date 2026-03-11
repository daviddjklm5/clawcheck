from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AppSettings:
    base_url: str
    home_path: str

    @property
    def home_url(self) -> str:
        return f"{self.base_url.rstrip('/')}{self.home_path}"


@dataclass
class AuthSettings:
    username: str
    password: str
    require_manual_captcha: bool


@dataclass
class BrowserSettings:
    headed: bool
    slow_mo_ms: int
    timeout_ms: int
    navigation_timeout_ms: int
    ignore_https_errors: bool


@dataclass
class RuntimeSettings:
    state_file: str
    logs_dir: str
    screenshots_dir: str
    retries: int
    retry_wait_sec: float


@dataclass
class DatabaseSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    schema: str
    sslmode: str


@dataclass
class Settings:
    app: AppSettings
    auth: AuthSettings
    browser: BrowserSettings
    runtime: RuntimeSettings
    db: DatabaseSettings


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be an object: {path}")
    return data


def load_settings(path: Path) -> Settings:
    raw = _read_yaml(path)

    app = raw.get("app", {})
    auth = raw.get("auth", {})
    browser = raw.get("browser", {})
    runtime = raw.get("runtime", {})
    db = raw.get("db", {})

    return Settings(
        app=AppSettings(
            base_url=str(app.get("base_url", "https://thr.onewo.com:8443")),
            home_path=str(app.get("home_path", "/ierp/?formId=home_page")),
        ),
        auth=AuthSettings(
            username=str(auth.get("username", "")),
            password=str(auth.get("password", "")),
            require_manual_captcha=bool(auth.get("require_manual_captcha", True)),
        ),
        browser=BrowserSettings(
            headed=bool(browser.get("headed", True)),
            slow_mo_ms=int(browser.get("slow_mo_ms", 0)),
            timeout_ms=int(browser.get("timeout_ms", 15000)),
            navigation_timeout_ms=int(browser.get("navigation_timeout_ms", 45000)),
            ignore_https_errors=bool(browser.get("ignore_https_errors", True)),
        ),
        runtime=RuntimeSettings(
            state_file=str(runtime.get("state_file", "automation/state/auth.json")),
            logs_dir=str(runtime.get("logs_dir", "automation/logs")),
            screenshots_dir=str(runtime.get("screenshots_dir", "automation/screenshots")),
            retries=int(runtime.get("retries", 2)),
            retry_wait_sec=float(runtime.get("retry_wait_sec", 1.0)),
        ),
        db=DatabaseSettings(
            host=str(db.get("host", "")).strip(),
            port=int(db.get("port", 5432)),
            dbname=str(db.get("dbname", "")).strip(),
            user=str(db.get("user", "")).strip(),
            password=str(db.get("password", "")).strip(),
            schema=str(db.get("schema", "public")).strip() or "public",
            sslmode=str(db.get("sslmode", "prefer")).strip() or "prefer",
        ),
    )


def _ensure_selector_list(value: Any, key: str) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise ValueError(f"Selector '{key}' must be a string or list[str]")


def load_selectors(path: Path) -> dict[str, dict[str, list[str]]]:
    raw = _read_yaml(path)
    normalized: dict[str, dict[str, list[str]]] = {}

    for section, items in raw.items():
        if not isinstance(section, str):
            raise ValueError("Selector section names must be strings")
        if not isinstance(items, dict):
            raise ValueError(f"Selector section '{section}' must be an object")

        normalized[section] = {}
        for key, value in items.items():
            if not isinstance(key, str):
                raise ValueError(f"Selector key in section '{section}' must be a string")
            normalized[section][key] = _ensure_selector_list(value, f"{section}.{key}")

    return normalized


def load_local_auth(path: Path) -> dict[str, str]:
    data = _read_yaml(path)
    auth_section = data.get("auth", data)
    if not isinstance(auth_section, dict):
        raise ValueError("Local credentials file must be an object or contain an 'auth' object")

    username = str(auth_section.get("username", "")).strip()
    password = str(auth_section.get("password", "")).strip()
    return {"username": username, "password": password}
