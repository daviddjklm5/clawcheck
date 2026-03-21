#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_CONFIG_PATH = "automation/config/settings.yaml"
DEFAULT_CREDENTIALS_PATH = "automation/config/credentials.local.yaml"
DEFAULT_SELECTORS_PATH = "automation/config/selectors.yaml"
PROD_CONFIG_PATH = "automation/config/settings.prod.yaml"
PROD_CREDENTIALS_PATH = "automation/config/credentials.prod.local.yaml"
PROD_DEFAULT_ACTIONS = {
    "check",
    "login",
    "run",
    "collect",
    "roster",
    "orglist",
    "rolecatalog",
    "dbinit",
    "audit",
    "sync-todo-status",
}
WSL_RUNTIME_OVERRIDE_ENV_NAMES = ("CLAWCHECK_ALLOW_WSL_RUNTIME", "IERP_ALLOW_WSL_RUNTIME")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="iERP automation runner")
    parser.add_argument(
        "action",
        choices=["check", "login", "run", "collect", "roster", "orglist", "rolecatalog", "dbinit", "audit", "sync-todo-status"],
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
    parser.add_argument(
        "--document-nos",
        default="",
        help="Comma-separated permission document numbers for audit action",
    )
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of permission documents to collect")
    parser.add_argument("--dry-run", action="store_true", help="Collect data without writing PostgreSQL")
    parser.add_argument(
        "--force-recollect",
        action="store_true",
        help="Force recollect documents even when approval snapshot is unchanged",
    )
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


def normalize_document_nos(document_no: str, document_nos_arg: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    for raw_value in [document_no, *document_nos_arg.split(",")]:
        normalized = raw_value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


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


def is_wsl_environment(
    environ: Mapping[str, str] | None = None,
    proc_version_text: str | None = None,
) -> bool:
    env = environ or os.environ
    if env.get("WSL_DISTRO_NAME") or env.get("WSL_INTEROP"):
        return True

    version_text = proc_version_text
    if version_text is None:
        for candidate in ("/proc/sys/kernel/osrelease", "/proc/version"):
            try:
                version_text = Path(candidate).read_text(encoding="utf-8", errors="ignore")
                break
            except OSError:
                continue

    lowered = (version_text or "").lower()
    return "microsoft" in lowered or "wsl" in lowered


def _is_runtime_override_enabled(environ: Mapping[str, str] | None = None) -> bool:
    env = environ or os.environ
    return any(str(env.get(name, "")).strip() == "1" for name in WSL_RUNTIME_OVERRIDE_ENV_NAMES)


def should_block_wsl_runtime(
    args: argparse.Namespace,
    settings_path: Path,
    credentials_path: Path,
    environ: Mapping[str, str] | None = None,
    proc_version_text: str | None = None,
) -> bool:
    if args.action not in PROD_DEFAULT_ACTIONS:
        return False
    if _is_runtime_override_enabled(environ):
        return False
    if not is_wsl_environment(environ=environ, proc_version_text=proc_version_text):
        return False

    prod_config_path = resolve_path(PROD_CONFIG_PATH)
    prod_credentials_path = resolve_path(PROD_CREDENTIALS_PATH)
    using_prod_config = settings_path == prod_config_path
    using_prod_credentials = credentials_path == prod_credentials_path
    return using_prod_config or using_prod_credentials


def build_wsl_runtime_block_message(
    action: str,
    settings_path: Path,
    credentials_path: Path,
) -> str:
    lines = [
        f"Blocked Windows-native runtime action on WSL: {action}",
        "Plan 300 requires formal runtime tasks to be launched from the Windows repo with .venv-win.",
        f"Resolved config: {settings_path}",
        f"Resolved credentials: {credentials_path}",
        r"Use PowerShell on Windows instead, for example:",
        rf"powershell.exe -ExecutionPolicy Bypass -File .\automation\scripts\run_windows_task.ps1 -Action {action}",
        "If you are intentionally doing temporary developer-side fallback on WSL, set CLAWCHECK_ALLOW_WSL_RUNTIME=1.",
    ]
    return "\n".join(lines)


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


def ensure_login(login_page, settings, retries: int, wait_sec: float, retry_call, bound_pages: list[object] | None = None):
    username, password = _resolve_credentials(settings)
    managed_pages = bound_pages or [login_page]

    def _refresh_closed_page() -> None:
        page = login_page.page
        if not page.is_closed():
            return
        new_page = page.context.new_page()
        for candidate in managed_pages:
            if hasattr(candidate, "set_page"):
                candidate.set_page(new_page)
        login_page.logger.warning("Detected closed Playwright page during login retry; created a fresh page in the same context")

    def _do_login():
        try:
            login_page.login(
                username=username,
                password=password,
                require_manual_captcha=settings.auth.require_manual_captcha,
            )
            return login_page.page
        except Exception:
            _refresh_closed_page()
            raise

    return retry_call(_do_login, retries=retries, wait_sec=wait_sec)


def main() -> int:
    args = parse_args()
    from automation.utils.config_loader import load_local_auth, load_selectors, load_settings
    from automation.utils.install_hints import PLAYWRIGHT_INSTALL_HINT, REQUIREMENTS_INSTALL_HINT
    from automation.utils.logger import setup_logger

    settings_path, credentials_path, selectors_path = resolve_runtime_paths(args)
    if should_block_wsl_runtime(args, settings_path, credentials_path):
        print(
            build_wsl_runtime_block_message(args.action, settings_path, credentials_path),
            file=sys.stderr,
        )
        return 2

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
            PostgresPersonAttributesStore,
            PostgresPermissionCatalogStore,
            PostgresPermissionStore,
            PostgresRiskTrustStore,
        )

        try:
            if args.action == "rolecatalog":
                summary = PostgresPermissionCatalogStore(settings.db).seed_catalog()
                default_name = "rolecatalog"
            else:
                permission_store = PostgresPermissionStore(settings.db)
                roster_store = PostgresActiveRosterStore(settings.db)
                org_store = PostgresOrganizationListStore(settings.db)
                person_attributes_store = PostgresPersonAttributesStore(settings.db)
                catalog_store = PostgresPermissionCatalogStore(settings.db)
                risk_trust_store = PostgresRiskTrustStore(settings.db)

                permission_store.ensure_table()
                roster_store.ensure_table()
                org_store.ensure_table()
                person_attributes_store.ensure_table()
                risk_trust_store.ensure_table()
                permission_catalog = catalog_store.seed_catalog()
                summary = {
                    "initialized_tables": [
                        "申请单基本信息",
                        "申请单权限列表",
                        "申请单审批记录",
                        "申请表组织范围",
                        "人员属性查询",
                        "在职花名册表",
                        "组织列表",
                        "城市所属战区",
                        "组织属性查询",
                        "权限列表",
                        "申请单风险信任评估",
                        "申请单风险信任评估明细",
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

    if args.action == "audit":
        from automation.db.postgres import PostgresRiskTrustStore
        from automation.rules import RiskTrustEvaluator, load_risk_trust_package

        try:
            target_document_nos = normalize_document_nos(args.document_no, args.document_nos)
            config_dir = REPO_ROOT / "automation" / "config" / "rules"
            package = load_risk_trust_package(config_dir)
            store = PostgresRiskTrustStore(settings.db)
            bundles = store.fetch_document_bundles(
                document_no=target_document_nos[0] if len(target_document_nos) == 1 else None,
                document_nos=target_document_nos if target_document_nos else None,
                limit=args.limit,
            )
            assessment_batch_no = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            evaluator = RiskTrustEvaluator(package)
            summary_rows, detail_rows, failed_documents = evaluator.evaluate_documents_resilient(
                bundles=bundles,
                assessment_batch_no=assessment_batch_no,
            )
            payload = {
                "assessment_batch_no": assessment_batch_no,
                "assessment_version": package.version,
                "document_count": len(summary_rows),
                "detail_count": len(detail_rows),
                "failed_document_count": len(failed_documents),
                "failed_documents": failed_documents,
                "documents": summary_rows,
            }
            dump_path = resolve_path(args.dump_json) if args.dump_json else logs_dir / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            logger.info("Audit completed. JSON dump: %s", dump_path)
            if args.dry_run:
                logger.info("Dry-run enabled; risk-trust assessment results were not written to PostgreSQL")
            else:
                store.write_assessment_results(summary_rows, detail_rows)
                logger.info("Persisted %s assessment summaries and %s detail rows", len(summary_rows), len(detail_rows))
            if failed_documents:
                logger.warning(
                    "Audit skipped %s document(s) because evaluation failed: %s",
                    len(failed_documents),
                    ", ".join(item["document_no"] or "<UNKNOWN>" for item in failed_documents[:10]),
                )
            logger.info("Audit summary: %s", payload)
            if summary_rows or not failed_documents:
                logger.info("Automation finished successfully")
                return 0
            logger.error("Audit failed for all %s document(s)", len(failed_documents))
            return 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("audit failed: %s", exc)
            return 1

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print(
            "Missing dependency: playwright. Run:\n"
            f"1) {REQUIREMENTS_INSTALL_HINT}\n"
            f"2) {PLAYWRIGHT_INSTALL_HINT}"
        )
        return 2

    from automation.db.postgres import (
        PostgresActiveRosterStore,
        PostgresOrganizationListStore,
        PostgresPermissionCatalogStore,
        PostgresPermissionStore,
        PostgresRiskTrustStore,
    )
    from automation.flows.active_roster_flow import ActiveRosterFlow
    from automation.flows.organization_quick_maintain_flow import OrganizationQuickMaintainFlow
    from automation.flows.ierp_flow import IerpFlow
    from automation.flows.permission_collect_flow import PermissionCollectFlow, TODO_HEADERS
    from automation.pages.home_page import HomePage
    from automation.pages.login_page import LoginPage
    from automation.utils.playwright_helpers import save_screenshot, timestamp_slug
    from automation.utils.approval_record_helpers import collect_unresolved_approver_names
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
        payload["import_batch_no"] = import_batch_no
        inserted_count = store.write_rows(
            rows=parsed["records"],
            source_file_name=parsed["file_name"],
            import_batch_no=import_batch_no,
            source_root_org=source_root_org,
            include_all_children=include_all_children,
            extra_headers=parsed.get("unmapped_headers", []),
        )
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

    def normalize_timestamp_text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return value.isoformat()
        return str(value).strip()

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
                    page = ensure_login(
                        login_page,
                        settings,
                        settings.runtime.retries,
                        settings.runtime.retry_wait_sec,
                        retry_call,
                        bound_pages=[login_page, home_page],
                    )
                    context.storage_state(path=str(state_file))
                    logger.info("Auth state saved: %s", state_file)

                elif args.action == "run":
                    home_page.open()
                    if not login_page.is_logged_in():
                        logger.info("Stored session is not valid, relogin required")
                        page = ensure_login(
                            login_page,
                            settings,
                            settings.runtime.retries,
                            settings.runtime.retry_wait_sec,
                            retry_call,
                            bound_pages=[login_page, home_page],
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
                        page = ensure_login(
                            login_page,
                            settings,
                            settings.runtime.retries,
                            settings.runtime.retry_wait_sec,
                            retry_call,
                            bound_pages=[login_page, home_page],
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

                    def _reset_collect_session_to_todo_list() -> None:
                        home_page.open()
                        home_page.wait_ready()
                        collector.open_todo_list()

                    def _list_target_document_nos() -> list[str]:
                        _reset_collect_session_to_todo_list()
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
                    store = PostgresPermissionStore(settings.db)
                    document_sync_states: dict[str, dict[str, object]] = {}
                    if PostgresPermissionStore.is_configured(settings.db):
                        try:
                            document_sync_states = store.fetch_document_sync_states(target_document_nos)
                            logger.info(
                                "Loaded existing sync states for %s/%s target document(s)",
                                len(document_sync_states),
                                len(target_document_nos),
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Failed to preload existing document sync states from PostgreSQL: %s", exc)

                    documents: list[dict[str, object]] = []
                    skipped_documents: list[dict[str, str]] = []
                    failed_documents: list[dict[str, str]] = []
                    todo_list_ready = True
                    for index, target_document_no in enumerate(target_document_nos):
                        close_document_tab_after = index < len(target_document_nos) - 1

                        attempt_no = 0
                        existing_state = document_sync_states.get(target_document_no)

                        def _collect_by_document_no(
                            target_document_no: str = target_document_no,
                            close_document_tab_after: bool = close_document_tab_after,
                            existing_state: dict[str, object] | None = existing_state,
                        ) -> dict[str, object]:
                            nonlocal todo_list_ready, attempt_no
                            attempt_no += 1
                            if attempt_no > 1 or not todo_list_ready:
                                logger.info(
                                    "Resetting collect session to todo list before collecting %s (attempt %s)",
                                    target_document_no,
                                    attempt_no,
                                )
                                _reset_collect_session_to_todo_list()
                                todo_list_ready = True

                            logger.info("Collecting document: %s", target_document_no)
                            started_at = datetime.now()
                            started_ts = time.monotonic()
                            collector.open_document(target_document_no)

                            probe: dict[str, object] | None = None
                            if existing_state and not args.force_recollect:
                                probe = collector.collect_current_document_probe()
                                live_latest_approval_time = normalize_timestamp_text(
                                    probe.get("latest_approval_time")
                                )
                                live_approval_record_count = len(list(probe.get("approval_records") or []))
                                stored_latest_approval_time = normalize_timestamp_text(
                                    existing_state.get("latest_approval_time")
                                )
                                stored_approval_record_count = int(existing_state.get("approval_record_count") or 0)
                                if (
                                    live_latest_approval_time == stored_latest_approval_time
                                    and live_approval_record_count == stored_approval_record_count
                                ):
                                    logger.info(
                                        "Skipping document %s because approval snapshot is unchanged: latest=%s, count=%s",
                                        target_document_no,
                                        live_latest_approval_time or "<empty>",
                                        live_approval_record_count,
                                    )
                                    if close_document_tab_after:
                                        collector.close_current_document_tab(target_document_no)
                                        page.wait_for_timeout(200)
                                        collector.return_to_todo_list()
                                        todo_list_ready = True
                                    else:
                                        collector.close_current_document_tab(target_document_no)
                                        todo_list_ready = False
                                    return {
                                        "_skip": True,
                                        "document_no": target_document_no,
                                        "stored_latest_approval_time": stored_latest_approval_time,
                                        "live_latest_approval_time": live_latest_approval_time,
                                        "stored_approval_record_count": str(stored_approval_record_count),
                                        "live_approval_record_count": str(live_approval_record_count),
                                    }
                                logger.info(
                                    "Recollecting document %s because approval snapshot changed: latest=%s->%s, count=%s->%s",
                                    target_document_no,
                                    stored_latest_approval_time or "<empty>",
                                    live_latest_approval_time or "<empty>",
                                    stored_approval_record_count,
                                    live_approval_record_count,
                                )
                            elif existing_state and args.force_recollect:
                                logger.info(
                                    "Force recollect enabled for %s; skipping approval snapshot comparison",
                                    target_document_no,
                                )

                            document = collector.collect_current_document(probe=probe)
                            elapsed_seconds = round(time.monotonic() - started_ts, 3)
                            finished_at = datetime.now()
                            document["collection_started_at"] = started_at.isoformat(timespec="seconds")
                            document["collection_finished_at"] = finished_at.isoformat(timespec="seconds")
                            document["collection_elapsed_seconds"] = elapsed_seconds

                            if existing_state:
                                next_collection_count = int(existing_state.get("collection_count") or 1) + 1
                                document["_write_mode"] = "recollect"
                            else:
                                next_collection_count = 1
                                document["_write_mode"] = "insert"
                            document["basic_info"]["collection_count"] = next_collection_count

                            logger.info(
                                "Collected document %s in %.3f seconds",
                                target_document_no,
                                elapsed_seconds,
                            )

                            if close_document_tab_after:
                                collector.close_current_document_tab(target_document_no)
                                page.wait_for_timeout(200)
                                collector.return_to_todo_list()
                                todo_list_ready = True
                            else:
                                todo_list_ready = False
                            return document

                        try:
                            collected_document = retry_call(
                                _collect_by_document_no,
                                retries=settings.runtime.retries,
                                wait_sec=settings.runtime.retry_wait_sec,
                            )
                            if collected_document.get("_skip"):
                                skipped_documents.append(
                                    {
                                        "document_no": str(collected_document.get("document_no") or target_document_no),
                                        "stored_latest_approval_time": str(
                                            collected_document.get("stored_latest_approval_time") or ""
                                        ),
                                        "live_latest_approval_time": str(
                                            collected_document.get("live_latest_approval_time") or ""
                                        ),
                                        "stored_approval_record_count": str(
                                            collected_document.get("stored_approval_record_count") or ""
                                        ),
                                        "live_approval_record_count": str(
                                            collected_document.get("live_approval_record_count") or ""
                                        ),
                                    }
                                )
                            else:
                                documents.append(collected_document)
                        except Exception as exc:  # noqa: BLE001
                            todo_list_ready = False
                            logger.error("Collect failed for document %s: %s", target_document_no, exc)
                            failed_documents.append(
                                {
                                    "document_no": target_document_no,
                                    "error": f"{type(exc).__name__}: {exc}",
                                }
                            )
                    if not documents and not skipped_documents:
                        raise RuntimeError("No permission application documents were collected successfully")

                    documents = store.prepare_documents(documents)
                    unresolved_approver_names = sorted(
                        {
                            approver_name
                            for document in documents
                            for approver_name in collect_unresolved_approver_names(
                                list(document.get("approval_records", []))
                            )
                        }
                    )
                    if unresolved_approver_names:
                        preview_names = ", ".join(unresolved_approver_names[:20])
                        logger.warning(
                            "Approver employee_no unresolved for %s name(s): %s%s",
                            len(unresolved_approver_names),
                            preview_names,
                            " ..." if len(unresolved_approver_names) > 20 else "",
                        )

                    if args.dry_run:
                        logger.info("Dry-run enabled; skipping PostgreSQL write")
                    elif documents:
                        documents, write_failed_documents = store.write_documents(documents)
                        if write_failed_documents:
                            failed_documents.extend(write_failed_documents)
                        logger.info("Persisted %s document(s) to PostgreSQL", len(documents))
                    else:
                        logger.info("No document required PostgreSQL write after sync-state comparison")

                    if not documents and not skipped_documents:
                        raise RuntimeError("No permission application documents were persisted successfully")

                    dump_path = resolve_path(args.dump_json) if args.dump_json else logs_dir / f"collect_{timestamp_slug()}.json"
                    dump_path.parent.mkdir(parents=True, exist_ok=True)
                    dump_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
                    logger.info(
                        "Collected %s/%s document(s), skipped %s. JSON dump: %s",
                        len(documents),
                        len(target_document_nos),
                        len(skipped_documents),
                        dump_path,
                    )

                    if skipped_documents:
                        logger.info("Skipped document count: %s", len(skipped_documents))
                        skipped_dump_path = dump_path.with_name(f"{dump_path.stem}_skipped{dump_path.suffix}")
                        skipped_dump_path.write_text(
                            json.dumps(
                                {
                                    "skipped_documents": skipped_documents,
                                    "summary": {
                                        "requested_count": len(target_document_nos),
                                        "success_count": len(documents),
                                        "skipped_count": len(skipped_documents),
                                    },
                                },
                                ensure_ascii=False,
                                indent=2,
                            ),
                            encoding="utf-8",
                        )
                        logger.info("Skipped document dump: %s", skipped_dump_path)

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

                elif args.action == "sync-todo-status":
                    sync_started_at = datetime.now()
                    process_store = PostgresRiskTrustStore(settings.db)
                    permission_store = PostgresPermissionStore(settings.db)
                    project_document_nos = process_store.fetch_process_workbench_document_nos()
                    existing_sync_states = permission_store.fetch_document_sync_states(project_document_nos)

                    ehr_permission_document_nos: list[str] = []
                    if project_document_nos:
                        home_page.open()
                        if not login_page.is_logged_in():
                            logger.info("Stored session is not valid, relogin required")
                            page = ensure_login(
                                login_page,
                                settings,
                                settings.runtime.retries,
                                settings.runtime.retry_wait_sec,
                                retry_call,
                                bound_pages=[login_page, home_page],
                            )
                            context.storage_state(path=str(state_file))
                            logger.info("Auth state refreshed: %s", state_file)

                        collector = PermissionCollectFlow(
                            page=page,
                            logger=logger,
                            timeout_ms=settings.browser.timeout_ms,
                            home_url=settings.app.home_url,
                        )

                        def _list_permission_todo_document_nos() -> list[str]:
                            home_page.open()
                            home_page.wait_ready()
                            collector.open_todo_list()
                            todo_rows = collector.extract_grid_rows(TODO_HEADERS)
                            ordered_document_nos: list[str] = []
                            seen_document_nos: set[str] = set()
                            for row in todo_rows:
                                if row.get("单据") != "权限申请":
                                    continue
                                document_no = str(row.get("单据编号") or "").strip()
                                if not document_no or document_no in seen_document_nos:
                                    continue
                                seen_document_nos.add(document_no)
                                ordered_document_nos.append(document_no)
                            return ordered_document_nos

                        ehr_permission_document_nos = retry_call(
                            _list_permission_todo_document_nos,
                            retries=settings.runtime.retries,
                            wait_sec=settings.runtime.retry_wait_sec,
                        )

                    ehr_permission_document_no_set = set(ehr_permission_document_nos)
                    status_by_document_no = {
                        document_no: ("待处理" if document_no in ehr_permission_document_no_set else "已处理")
                        for document_no in project_document_nos
                    }
                    pending_count = sum(1 for status in status_by_document_no.values() if status == "待处理")
                    processed_count = sum(1 for status in status_by_document_no.values() if status == "已处理")
                    changed_count = sum(
                        1
                        for document_no, status in status_by_document_no.items()
                        if (existing_sync_states.get(document_no, {}).get("todo_process_status") or "待处理") != status
                    )
                    unchanged_count = max(len(status_by_document_no) - changed_count, 0)
                    extra_ehr_todo_count = len(ehr_permission_document_no_set.difference(project_document_nos))

                    if args.dry_run:
                        logger.info("Dry-run enabled; skipping PostgreSQL todo-status write")
                    else:
                        permission_store.update_todo_process_statuses(status_by_document_no)
                        logger.info("Updated todo process status for %s project document(s)", len(status_by_document_no))

                    dump_path = (
                        resolve_path(args.dump_json)
                        if args.dump_json
                        else logs_dir / f"todo_sync_{timestamp_slug()}.json"
                    )
                    dump_path.parent.mkdir(parents=True, exist_ok=True)
                    payload = {
                        "status": "succeeded",
                        "dry_run": bool(args.dry_run),
                        "started_at": sync_started_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "project_document_count": len(project_document_nos),
                        "ehr_todo_count": len(ehr_permission_document_nos),
                        "pending_count": pending_count,
                        "processed_count": processed_count,
                        "changed_count": changed_count,
                        "unchanged_count": unchanged_count,
                        "extra_ehr_todo_count": extra_ehr_todo_count,
                        "message": (
                            f"待办状态同步完成：待处理 {pending_count} 张，已处理 {processed_count} 张，"
                            f"状态变更 {changed_count} 张"
                            + ("（dry-run，未写入 PostgreSQL）" if args.dry_run else "")
                        ),
                        "project_document_nos": project_document_nos,
                        "ehr_todo_document_nos": ehr_permission_document_nos,
                    }
                    dump_path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    logger.info("Todo status sync completed. JSON dump: %s", dump_path)
                    logger.info("Todo status sync summary: %s", payload)

                    if project_document_nos:
                        result_shot = save_screenshot(page, shots_dir, "todo_sync_result")
                        logger.info("Todo status sync screenshot: %s", result_shot)

                elif args.action == "roster":
                    if args.skip_export and not args.skip_import:
                        raise ValueError("--skip-export can only be used together with --skip-import or --input-file")

                    home_page.open()
                    if not login_page.is_logged_in():
                        logger.info("Stored session is not valid, relogin required")
                        page = ensure_login(
                            login_page,
                            settings,
                            settings.runtime.retries,
                            settings.runtime.retry_wait_sec,
                            retry_call,
                            bound_pages=[login_page, home_page],
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
                        import_roster_file(
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
                        page = ensure_login(
                            login_page,
                            settings,
                            settings.runtime.retries,
                            settings.runtime.retry_wait_sec,
                            retry_call,
                            bound_pages=[login_page, home_page],
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
                        import_orglist_file(
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
