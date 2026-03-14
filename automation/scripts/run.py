#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CONFIG_PATH = "automation/config/settings.yaml"
DEFAULT_CREDENTIALS_PATH = "automation/config/credentials.local.yaml"
DEFAULT_SELECTORS_PATH = "automation/config/selectors.yaml"
PROD_CONFIG_PATH = "automation/config/settings.prod.yaml"
PROD_CREDENTIALS_PATH = "automation/config/credentials.prod.local.yaml"
PROD_DEFAULT_ACTIONS = {"check", "login", "run", "collect", "roster", "orglist", "rolecatalog", "dbinit"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="iERP automation runner")
    parser.add_argument(
        "action",
        choices=["check", "login", "run", "collect", "roster", "orglist", "rolecatalog", "dbinit"],
        help="Action to execute",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Settings YAML path")
    parser.add_argument(
        "--credentials",
        default=DEFAULT_CREDENTIALS_PATH,
        help="Local credentials YAML path",
    )
    parser.add_argument("--selectors", default=DEFAULT_SELECTORS_PATH, help="Selectors YAML path")
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
    parser.add_argument("--scheme", default="在职花名册基础版", help="Roster report scheme name")
    parser.add_argument("--employment-type", default="全职任职", help="Roster employment type value")
    parser.add_argument("--input-file", default="", help="Import an existing roster/orglist file instead of downloading it")
    parser.add_argument("--skip-export", action="store_true", help="Stop after query without exporting file")
    parser.add_argument("--skip-import", action="store_true", help="Download file but skip PostgreSQL import")
    parser.add_argument("--downloads-dir", default="", help="Optional override for downloads directory")
    parser.add_argument(
        "--download-timeout-minutes",
        type=int,
        default=15,
        help="How long to wait for roster/orglist download",
    )
    parser.add_argument(
        "--query-timeout-seconds",
        type=int,
        default=60,
        help="How long to wait for roster/orglist query to finish",
    )
    return parser.parse_args()


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def resolve_runtime_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    config_path = resolve_path(args.config)
    credentials_path = resolve_path(args.credentials)
    if args.action in PROD_DEFAULT_ACTIONS:
        if args.config == DEFAULT_CONFIG_PATH:
            prod_config = resolve_path(PROD_CONFIG_PATH)
            if prod_config.exists():
                config_path = prod_config
        if args.credentials == DEFAULT_CREDENTIALS_PATH:
            prod_credentials = resolve_path(PROD_CREDENTIALS_PATH)
            if prod_credentials.exists():
                credentials_path = prod_credentials
    selectors_path = resolve_path(args.selectors)
    return config_path, credentials_path, selectors_path


def build_context(playwright, settings, state_file: Path, use_state: bool):
    browser = playwright.chromium.launch(
        headless=not settings.browser.headed,
        slow_mo=settings.browser.slow_mo_ms,
    )

    context_kwargs = {
        "ignore_https_errors": settings.browser.ignore_https_errors,
        "viewport": {"width": 1440, "height": 900},
        "accept_downloads": True,
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
    from automation.utils.config_loader import load_local_auth, load_selectors, load_settings
    from automation.utils.logger import setup_logger

    settings_path, credentials_path, selectors_path = resolve_runtime_paths(args)

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
    downloads_dir = resolve_path(args.downloads_dir) if args.downloads_dir else resolve_path(settings.runtime.downloads_dir)

    state_file.parent.mkdir(parents=True, exist_ok=True)
    shots_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logger(logs_dir)
    logger.info("Action: %s", args.action)
    logger.info("Settings: %s", settings_path)
    if credentials_path.exists():
        logger.info("Credentials: %s", credentials_path)
    logger.info("Selectors: %s", selectors_path)

    if args.action in {"rolecatalog", "dbinit"}:
        from automation.db.postgres import (
            PostgresActiveRosterStore,
            PostgresOrganizationListStore,
            PostgresPermissionCatalogStore,
            PostgresPermissionStore,
        )

        try:
            if args.action == "rolecatalog":
                summary = PostgresPermissionCatalogStore(settings.db).seed_catalog()
                default_name = "rolecatalog"
            else:
                permission_store = PostgresPermissionStore(settings.db)
                roster_store = PostgresActiveRosterStore(settings.db)
                org_store = PostgresOrganizationListStore(settings.db)
                catalog_store = PostgresPermissionCatalogStore(settings.db)

                permission_store.ensure_table()
                roster_store.ensure_table()
                org_store.ensure_table()
                permission_catalog = catalog_store.seed_catalog()
                summary = {
                    "initialized_tables": [
                        "申请单基本信息",
                        "申请单权限列表",
                        "申请单审批记录",
                        "申请表组织范围",
                        "在职花名册表",
                        "组织列表",
                        "城市所属战区",
                        "组织属性查询",
                        "权限列表",
                    ],
                    "permission_catalog": permission_catalog,
                }
                default_name = "dbinit"

            dump_path = resolve_path(args.dump_json) if args.dump_json else logs_dir / f"{default_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("%s completed. Summary dump: %s", args.action, dump_path)
            logger.info("%s summary: %s", args.action, summary)
            logger.info("Automation finished successfully")
            return 0
        except Exception as exc:  # noqa: BLE001
            logger.exception("%s failed: %s", args.action, exc)
            return 1

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print(
            "Missing dependency: playwright. Run:\n"
            "1) pip install -r automation/requirements.txt\n"
            "2) playwright install chromium"
        )
        return 2

    from automation.db.postgres import (
        PostgresActiveRosterStore,
        PostgresOrganizationListStore,
        PostgresPermissionCatalogStore,
        PostgresPermissionStore,
    )
    from automation.flows.active_roster_flow import ActiveRosterFlow
    from automation.flows.organization_quick_maintain_flow import OrganizationQuickMaintainFlow
    from automation.flows.ierp_flow import IerpFlow
    from automation.flows.permission_collect_flow import PermissionCollectFlow, TODO_HEADERS
    from automation.pages.home_page import HomePage
    from automation.pages.login_page import LoginPage
    from automation.utils.playwright_helpers import save_screenshot, timestamp_slug
    from automation.utils.retry import retry_call
    from automation.utils.organization_list_excel import parse_organization_list_workbook
    from automation.utils.roster_excel import parse_roster_workbook

    result_code = 0

    def import_orglist_file(file_path: Path, source_root_org: str, include_all_children: bool) -> dict[str, object]:
        parsed = parse_organization_list_workbook(file_path)
        payload = {
            "file_path": str(file_path),
            "file_name": parsed["file_name"],
            "row_count": parsed["row_count"],
            "headers": parsed["headers"],
            "unmapped_headers": parsed.get("unmapped_headers", []),
            "source_root_org": source_root_org,
            "include_all_children": include_all_children,
        }
        dump_path = resolve_path(args.dump_json) if args.dump_json else logs_dir / f"orglist_{timestamp_slug()}.json"
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["dump_path"] = str(dump_path)
        logger.info("Organization list parsed. JSON dump: %s", dump_path)

        if args.skip_import:
            logger.info("Skip-import enabled; PostgreSQL write is skipped")
            return payload

        store = PostgresOrganizationListStore(settings.db)
        import_batch_no = f"orglist_{timestamp_slug()}"
        inserted_count = store.write_rows(
            rows=parsed["records"],
            source_file_name=parsed["file_name"],
            import_batch_no=import_batch_no,
            source_root_org=source_root_org,
            include_all_children=include_all_children,
            extra_headers=parsed.get("unmapped_headers", []),
        )
        payload["import_batch_no"] = import_batch_no
        payload["inserted_count"] = inserted_count
        logger.info("Persisted %s organization rows into PostgreSQL table 组织列表", inserted_count)
        return payload

    def import_roster_file(file_path: Path, fallback_query_date: str | None) -> dict[str, object]:
        parsed = parse_roster_workbook(file_path)
        query_date_text = parsed.get("query_date")
        if query_date_text is None:
            if not fallback_query_date:
                raise ValueError("Roster workbook did not contain query_date and no fallback query date was provided")
            query_date_value = date.fromisoformat(fallback_query_date)
        elif isinstance(query_date_text, date):
            query_date_value = query_date_text
        else:
            query_date_value = date.fromisoformat(str(query_date_text))

        payload = {
            "file_path": str(file_path),
            "file_name": parsed["file_name"],
            "query_date": query_date_value.isoformat(),
            "row_count": parsed["row_count"],
            "headers": parsed["headers"],
            "unmapped_headers": parsed.get("unmapped_headers", []),
        }
        dump_path = resolve_path(args.dump_json) if args.dump_json else logs_dir / f"roster_{timestamp_slug()}.json"
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        payload["dump_path"] = str(dump_path)
        logger.info("Roster parsed. JSON dump: %s", dump_path)

        if args.skip_import:
            logger.info("Skip-import enabled; PostgreSQL write is skipped")
            return payload

        store = PostgresActiveRosterStore(settings.db)
        import_batch_no = f"roster_{timestamp_slug()}"
        downloaded_at = datetime.fromtimestamp(file_path.stat().st_mtime)
        inserted_count = store.write_rows(
            rows=parsed["records"],
            query_date=query_date_value,
            source_file_name=parsed["file_name"],
            import_batch_no=import_batch_no,
            downloaded_at=downloaded_at,
        )
        payload["import_batch_no"] = import_batch_no
        payload["inserted_count"] = inserted_count
        logger.info("Persisted %s active roster rows into PostgreSQL table 在职花名册表", inserted_count)
        return payload

    try:
        if args.action == "roster" and args.input_file.strip():
            logger.info("Roster import-only mode. input_file=%s", args.input_file)
            import_roster_file(resolve_path(args.input_file.strip()), fallback_query_date=None)
            logger.info("Roster import-only flow completed successfully")
            return 0

        if args.action == "orglist" and args.input_file.strip():
            logger.info("Organization list import-only mode. input_file=%s", args.input_file)
            import_orglist_file(
                resolve_path(args.input_file.strip()),
                source_root_org="万物云",
                include_all_children=True,
            )
            logger.info("Organization list import-only flow completed successfully")
            return 0

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

                    skip_org_scope_role_codes: set[str] = set()
                    try:
                        skip_org_scope_role_codes = PostgresPermissionCatalogStore(settings.db).fetch_skip_org_scope_role_codes()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to preload skip-org-scope roles from PostgreSQL: %s", exc)

                    collector = PermissionCollectFlow(
                        page=page,
                        logger=logger,
                        timeout_ms=settings.browser.timeout_ms,
                        home_url=settings.app.home_url,
                        skip_org_scope_role_codes=skip_org_scope_role_codes,
                    )

                    def _collect_by_document_no(target_document_no: str) -> dict[str, object]:
                        home_page.open()
                        home_page.wait_ready()
                        documents = collector.collect(document_no=target_document_no, limit=1)
                        if not documents:
                            raise RuntimeError(f"No permission application documents matched document_no={target_document_no}")
                        return documents[0]

                    def _list_target_document_nos() -> list[str]:
                        home_page.open()
                        home_page.wait_ready()
                        collector.open_todo_list()
                        todo_rows = collector.extract_grid_rows(TODO_HEADERS)
                        permission_rows = [row for row in todo_rows if row.get("单据") == "权限申请"]
                        target_document_nos = [row.get("单据编号", "").strip() for row in permission_rows if row.get("单据编号")]
                        if args.document_no.strip():
                            target_document_nos = [doc_no for doc_no in target_document_nos if doc_no == args.document_no.strip()]
                        if args.limit > 0:
                            target_document_nos = target_document_nos[: args.limit]
                        return target_document_nos

                    target_document_nos = retry_call(
                        _list_target_document_nos,
                        retries=settings.runtime.retries,
                        wait_sec=settings.runtime.retry_wait_sec,
                    )
                    documents: list[dict[str, object]] = []
                    failed_documents: list[dict[str, str]] = []
                    for target_document_no in target_document_nos:
                        try:
                            documents.append(
                                retry_call(
                                    lambda target_document_no=target_document_no: _collect_by_document_no(target_document_no),
                                    retries=settings.runtime.retries,
                                    wait_sec=settings.runtime.retry_wait_sec,
                                )
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.error("Collect failed for document %s: %s", target_document_no, exc)
                            failed_documents.append(
                                {
                                    "document_no": target_document_no,
                                    "error": f"{type(exc).__name__}: {exc}",
                                }
                            )
                    if not documents:
                        raise RuntimeError("No permission application documents were collected successfully")

                    dump_path = resolve_path(args.dump_json) if args.dump_json else logs_dir / f"collect_{timestamp_slug()}.json"
                    dump_path.parent.mkdir(parents=True, exist_ok=True)
                    dump_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
                    logger.info(
                        "Collected %s/%s document(s). JSON dump: %s",
                        len(documents),
                        len(target_document_nos),
                        dump_path,
                    )

                    if args.dry_run:
                        logger.info("Dry-run enabled; skipping PostgreSQL write")
                    else:
                        store = PostgresPermissionStore(settings.db)
                        store.write_documents(documents)
                        logger.info("Persisted %s document(s) to PostgreSQL", len(documents))

                    if failed_documents:
                        logger.warning("Failed document count: %s", len(failed_documents))
                        failed_dump_path = dump_path.with_name(f"{dump_path.stem}_failed{dump_path.suffix}")
                        failed_dump_path.write_text(
                            json.dumps(
                                {
                                    "failed_documents": failed_documents,
                                    "summary": {
                                        "requested_count": len(target_document_nos),
                                        "success_count": len(documents),
                                        "failed_count": len(failed_documents),
                                    },
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                        logger.warning("Failed document dump: %s", failed_dump_path)

                    result_shot = save_screenshot(page, shots_dir, "collect_result")
                    logger.info("Collect completed. Screenshot: %s", result_shot)

                elif args.action == "roster":
                    if args.skip_export and not args.skip_import:
                        raise ValueError("--skip-export can only be used together with --skip-import or --input-file")

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

                    roster_flow = ActiveRosterFlow(
                        page=page,
                        logger=logger,
                        timeout_ms=settings.browser.timeout_ms,
                        home_url=settings.app.home_url,
                    )

                    def _do_roster() -> dict[str, object]:
                        return roster_flow.run(
                            downloads_dir=downloads_dir,
                            report_scheme=args.scheme.strip() or "在职花名册基础版",
                            employment_type=args.employment_type.strip() or "全职任职",
                            query_timeout_sec=max(args.query_timeout_seconds, 30),
                            download_timeout_sec=max(args.download_timeout_minutes, 1) * 60,
                            skip_export=args.skip_export,
                        )

                    roster_result = retry_call(
                        _do_roster,
                        retries=settings.runtime.retries,
                        wait_sec=settings.runtime.retry_wait_sec,
                    )
                    logger.info("Roster flow result: %s", roster_result)

                    downloaded_file = roster_result.get("downloaded_file")
                    if downloaded_file:
                        roster_import_result = import_roster_file(
                            file_path=Path(str(downloaded_file)),
                            fallback_query_date=roster_result.get("query_summary", {}).get("query_date"),
                        )
                    else:
                        logger.info("Roster flow finished without export file (skip-export mode)")

                    result_shot = save_screenshot(page, shots_dir, "roster_result")
                    logger.info("Roster completed. Screenshot: %s", result_shot)

                elif args.action == "orglist":
                    if args.skip_export and not args.skip_import:
                        raise ValueError("--skip-export can only be used together with --skip-import or --input-file")

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

                    orglist_flow = OrganizationQuickMaintainFlow(
                        page=page,
                        logger=logger,
                        timeout_ms=settings.browser.timeout_ms,
                        home_url=settings.app.home_url,
                    )

                    def _do_orglist() -> dict[str, object]:
                        return orglist_flow.run(
                            downloads_dir=downloads_dir,
                            query_timeout_sec=max(args.query_timeout_seconds, 30),
                            download_timeout_sec=max(args.download_timeout_minutes, 1) * 60,
                            skip_export=args.skip_export,
                            root_org_name="万物云",
                        )

                    orglist_result = retry_call(
                        _do_orglist,
                        retries=settings.runtime.retries,
                        wait_sec=settings.runtime.retry_wait_sec,
                    )
                    logger.info("Organization list flow result: %s", orglist_result)

                    downloaded_file = orglist_result.get("downloaded_file")
                    if downloaded_file:
                        orglist_import_result = import_orglist_file(
                            file_path=Path(str(downloaded_file)),
                            source_root_org=str(orglist_result.get("root_org_name") or "万物云"),
                            include_all_children=bool(orglist_result.get("include_all_children", True)),
                        )
                    else:
                        logger.info("Organization list flow finished without export file (skip-export mode)")

                    result_shot = save_screenshot(page, shots_dir, "orglist_result")
                    logger.info("Organization list completed. Screenshot: %s", result_shot)

            except Exception as exc:  # noqa: BLE001
                result_code = 1
                logger.exception("Automation failed: %s", exc)
                shot = save_screenshot(page, shots_dir, "error")
                logger.error("Error screenshot: %s", shot)
            finally:
                context.close()
                browser.close()

    except Exception as exc:  # noqa: BLE001
        result_code = 1
        logger.exception("Automation failed before browser startup: %s", exc)

    if result_code == 0:
        logger.info("Automation finished successfully")
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
