#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="iERP automation runner")
    parser.add_argument("action", choices=["check", "login", "run", "collect"], help="Action to execute")
    parser.add_argument("--config", default="automation/config/settings.yaml", help="Settings YAML path")
    parser.add_argument(
        "--credentials",
        default="automation/config/credentials.local.yaml",
        help="Local credentials YAML path",
    )
    parser.add_argument("--selectors", default="automation/config/selectors.yaml", help="Selectors YAML path")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--create", action="store_true", help="Enable create/save action in workflow run")
    parser.add_argument("--submit", action="store_true", help="Enable final submit action in workflow run")
    parser.add_argument("--document-no", default="", help="Specific permission document number to collect")
    parser.add_argument("--limit", type=int, default=1, help="Maximum number of permission documents to collect")
    parser.add_argument("--dry-run", action="store_true", help="Collect data without writing PostgreSQL")
    parser.add_argument("--dump-json", default="", help="Optional JSON dump path for collected payload")
    parser.add_argument(
        "--reason",
        default="",
        help="Reason text for workflow form (used when workflow.reason_input is configured)",
    )
    return parser.parse_args()


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def build_context(playwright, settings, state_file: Path, use_state: bool):
    browser = playwright.chromium.launch(
        headless=not settings.browser.headed,
        slow_mo=settings.browser.slow_mo_ms,
    )

    context_kwargs = {
        "ignore_https_errors": settings.browser.ignore_https_errors,
        "viewport": {"width": 1440, "height": 900},
    }

    if use_state and state_file.exists():
        context_kwargs["storage_state"] = str(state_file)

    context = browser.new_context(**context_kwargs)
    context.set_default_timeout(settings.browser.timeout_ms)
    context.set_default_navigation_timeout(settings.browser.navigation_timeout_ms)
    page = context.new_page()
    return browser, context, page


def _resolve_credentials(settings) -> tuple[str, str]:
    username = settings.auth.username.strip()
    password = settings.auth.password.strip()
    placeholder_values = {"your_username", "your_password", "username", "password"}
    invalid = (not username) or (not password) or (username.lower() in placeholder_values) or (password.lower() in placeholder_values)

    if not invalid:
        return username, password

    if not sys.stdin.isatty():
        raise ValueError(
            "Auth credentials missing or still placeholders. "
            "Set config/settings.yaml or env IERP_USERNAME/IERP_PASSWORD."
        )

    print("Auth credentials not configured. Please enter them for this run.")
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ").strip()
    if not username or not password:
        raise ValueError("Empty username/password from interactive input.")
    return username, password


def ensure_login(login_page, settings, retries: int, wait_sec: float, retry_call) -> None:
    username, password = _resolve_credentials(settings)

    def _do_login() -> None:
        login_page.login(
            username=username,
            password=password,
            require_manual_captcha=settings.auth.require_manual_captcha,
        )

    retry_call(_do_login, retries=retries, wait_sec=wait_sec)


def main() -> int:
    args = parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print(
            "Missing dependency: playwright. Run:\n"
            "1) pip install -r automation/requirements.txt\n"
            "2) playwright install chromium"
        )
        return 2

    from automation.flows.ierp_flow import IerpFlow
    from automation.flows.permission_collect_flow import PermissionCollectFlow
    from automation.pages.home_page import HomePage
    from automation.pages.login_page import LoginPage
    from automation.utils.config_loader import load_local_auth, load_selectors, load_settings
    from automation.utils.logger import setup_logger
    from automation.utils.playwright_helpers import save_screenshot, timestamp_slug
    from automation.utils.retry import retry_call
    from automation.db.postgres import PostgresPermissionStore

    settings_path = resolve_path(args.config)
    credentials_path = resolve_path(args.credentials)
    selectors_path = resolve_path(args.selectors)

    settings = load_settings(settings_path)
    selectors = load_selectors(selectors_path)

    if credentials_path.exists():
        local_auth = load_local_auth(credentials_path)
        if local_auth.get("username"):
            settings.auth.username = local_auth["username"]
        if local_auth.get("password"):
            settings.auth.password = local_auth["password"]

    settings.auth.username = os.getenv("IERP_USERNAME", settings.auth.username)
    settings.auth.password = os.getenv("IERP_PASSWORD", settings.auth.password)

    settings.db.host = os.getenv("IERP_PG_HOST", settings.db.host)
    settings.db.port = int(os.getenv("IERP_PG_PORT", str(settings.db.port)))
    settings.db.dbname = os.getenv("IERP_PG_DBNAME", settings.db.dbname)
    settings.db.user = os.getenv("IERP_PG_USER", settings.db.user)
    settings.db.password = os.getenv("IERP_PG_PASSWORD", settings.db.password)
    settings.db.schema = os.getenv("IERP_PG_SCHEMA", settings.db.schema)
    settings.db.sslmode = os.getenv("IERP_PG_SSLMODE", settings.db.sslmode)

    if args.headed:
        settings.browser.headed = True
    if args.headless:
        settings.browser.headed = False

    logs_dir = resolve_path(settings.runtime.logs_dir)
    shots_dir = resolve_path(settings.runtime.screenshots_dir)
    state_file = resolve_path(settings.runtime.state_file)

    state_file.parent.mkdir(parents=True, exist_ok=True)
    shots_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(logs_dir)
    logger.info("Action: %s", args.action)
    logger.info("Settings: %s", settings_path)
    if credentials_path.exists():
        logger.info("Credentials: %s", credentials_path)
    logger.info("Selectors: %s", selectors_path)

    result_code = 0

    with sync_playwright() as p:
        use_state = args.action != "login"
        browser, context, page = build_context(p, settings, state_file, use_state=use_state)

        home_page = HomePage(
            home_url=settings.app.home_url,
            page=page,
            selectors=selectors,
            logger=logger,
            timeout_ms=settings.browser.timeout_ms,
        )
        login_page = LoginPage(
            home_url=settings.app.home_url,
            page=page,
            selectors=selectors,
            logger=logger,
            timeout_ms=settings.browser.timeout_ms,
        )

        try:
            if args.action == "check":
                home_page.open()
                check_passed = False
                try:
                    home_page.wait_ready()
                    logger.info("Home ready marker matched")
                    check_passed = True
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Home marker not matched during check: %s", exc)

                if not check_passed:
                    if login_page.is_present("login", "username") or login_page.is_present("login", "password"):
                        logger.info("Login page markers matched; connectivity is OK")
                        check_passed = True

                if not check_passed:
                    raise RuntimeError("Neither home markers nor login markers were detected")

                check_shot = save_screenshot(page, shots_dir, "check_ready")
                logger.info("Check passed. Screenshot: %s", check_shot)

            elif args.action == "login":
                ensure_login(
                    login_page,
                    settings,
                    settings.runtime.retries,
                    settings.runtime.retry_wait_sec,
                    retry_call,
                )
                context.storage_state(path=str(state_file))
                logger.info("Auth state saved: %s", state_file)

            elif args.action == "run":
                home_page.open()
                if not login_page.is_logged_in():
                    logger.info("Stored session is not valid, relogin required")
                    ensure_login(
                        login_page,
                        settings,
                        settings.runtime.retries,
                        settings.runtime.retry_wait_sec,
                        retry_call,
                    )
                    context.storage_state(path=str(state_file))
                    logger.info("Auth state refreshed: %s", state_file)

                flow = IerpFlow(
                    page=page,
                    selectors=selectors,
                    logger=logger,
                    timeout_ms=settings.browser.timeout_ms,
                    auto_reason=(args.reason.strip() or None),
                    enable_create=args.create,
                    enable_submit=args.submit,
                )

                def _do_run_flow() -> None:
                    home_page.open()
                    home_page.wait_ready()
                    flow.run_example()

                retry_call(
                    _do_run_flow,
                    retries=settings.runtime.retries,
                    wait_sec=settings.runtime.retry_wait_sec,
                )
                result_shot = save_screenshot(page, shots_dir, "run_result")
                logger.info("Run completed. Screenshot: %s", result_shot)

            elif args.action == "collect":
                home_page.open()
                if not login_page.is_logged_in():
                    logger.info("Stored session is not valid, relogin required")
                    ensure_login(
                        login_page,
                        settings,
                        settings.runtime.retries,
                        settings.runtime.retry_wait_sec,
                        retry_call,
                    )
                    context.storage_state(path=str(state_file))
                    logger.info("Auth state refreshed: %s", state_file)

                collector = PermissionCollectFlow(
                    page=page,
                    logger=logger,
                    timeout_ms=settings.browser.timeout_ms,
                    home_url=settings.app.home_url,
                )

                def _do_collect() -> list[dict[str, object]]:
                    home_page.open()
                    home_page.wait_ready()
                    return collector.collect(
                        document_no=(args.document_no.strip() or None),
                        limit=max(args.limit, 0),
                    )

                documents = retry_call(
                    _do_collect,
                    retries=settings.runtime.retries,
                    wait_sec=settings.runtime.retry_wait_sec,
                )
                if not documents:
                    raise RuntimeError("No permission application documents matched the collect criteria")

                dump_path = resolve_path(args.dump_json) if args.dump_json else logs_dir / f"collect_{timestamp_slug()}.json"
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                dump_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
                logger.info("Collected %s document(s). JSON dump: %s", len(documents), dump_path)

                if args.dry_run:
                    logger.info("Dry-run enabled; skipping PostgreSQL write")
                else:
                    store = PostgresPermissionStore(settings.db)
                    store.write_documents(documents)
                    logger.info("Persisted %s document(s) to PostgreSQL", len(documents))

                result_shot = save_screenshot(page, shots_dir, "collect_result")
                logger.info("Collect completed. Screenshot: %s", result_shot)

        except Exception as exc:  # noqa: BLE001
            result_code = 1
            logger.exception("Automation failed: %s", exc)
            shot = save_screenshot(page, shots_dir, "error")
            logger.error("Error screenshot: %s", shot)
        finally:
            context.close()
            browser.close()

    if result_code == 0:
        logger.info("Automation finished successfully")
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
