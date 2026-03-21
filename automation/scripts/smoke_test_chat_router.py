from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any
import urllib.error
import urllib.request

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from automation.db.postgres import (  # noqa: E402
    CHAT_EXECUTION_LOG_COLUMNS,
    CHAT_EXECUTION_LOG_TABLE,
    PostgresChatStore,
)
from automation.utils.config_loader import load_settings  # noqa: E402

DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api"
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_POLL_INTERVAL_SECONDS = 2.0


def _resolve_settings_path(raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate.resolve()


def _load_runtime_settings(settings_path: Path):
    settings = load_settings(settings_path)
    settings.db.host = _getenv("IERP_PG_HOST", settings.db.host)
    settings.db.port = int(_getenv("IERP_PG_PORT", str(settings.db.port)))
    settings.db.dbname = _getenv("IERP_PG_DBNAME", settings.db.dbname)
    settings.db.user = _getenv("IERP_PG_USER", settings.db.user)
    settings.db.password = _getenv("IERP_PG_PASSWORD", settings.db.password)
    settings.db.schema = _getenv("IERP_PG_SCHEMA", settings.db.schema)
    settings.db.sslmode = _getenv("IERP_PG_SSLMODE", settings.db.sslmode)
    return settings


def _getenv(name: str, default: str) -> str:
    value = __import__("os").getenv(name)
    return value if value is not None else default


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def _find_stat_value(payload: dict[str, Any], label: str) -> str:
    stats = payload.get("stats")
    if not isinstance(stats, list):
        return ""
    for item in stats:
        if not isinstance(item, dict):
            continue
        if str(item.get("label") or "").strip() == label:
            return str(item.get("value") or "").strip()
    return ""


def _wait_for_completion(api_base_url: str, session_id: str, timeout_seconds: int) -> dict[str, Any]:
    started_at = time.monotonic()
    detail_url = f"{api_base_url}/chat/sessions/{session_id}"
    while time.monotonic() - started_at < timeout_seconds:
        detail = _http_json("GET", detail_url)
        if not detail.get("running"):
            return detail
        time.sleep(DEFAULT_POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Timed out while waiting for chat session {session_id}.")


def _fetch_execution_logs(store: PostgresChatStore, session_id: str) -> list[dict[str, Any]]:
    columns = [
        CHAT_EXECUTION_LOG_COLUMNS["event_type"],
        CHAT_EXECUTION_LOG_COLUMNS["event_summary"],
        CHAT_EXECUTION_LOG_COLUMNS["exit_code"],
        CHAT_EXECUTION_LOG_COLUMNS["created_at"],
    ]
    query = (
        f"SELECT {store._quoted_columns(columns)} "
        f"FROM {CHAT_EXECUTION_LOG_TABLE} "
        f"WHERE {store._quote_identifier(CHAT_EXECUTION_LOG_COLUMNS['session_id'])} = %s "
        f"ORDER BY {store._quote_identifier(CHAT_EXECUTION_LOG_COLUMNS['created_at'])} ASC"
    )
    with store.connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (session_id,))
            rows = cursor.fetchall()
    return [
        {
            "eventType": str(row[0]),
            "summary": str(row[1] or ""),
            "exitCode": row[2],
            "createdAt": str(row[3]),
        }
        for row in rows
    ]


def _contains_event(events: list[dict[str, Any]], event_type: str, keyword: str = "") -> bool:
    for event in events:
        if event.get("eventType") != event_type:
            continue
        if not keyword:
            return True
        if keyword in str(event.get("summary") or ""):
            return True
    return False


def _run_case(
    *,
    api_base_url: str,
    store: PostgresChatStore,
    name: str,
    question: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    session = _http_json(
        "POST",
        f"{api_base_url}/chat/sessions",
        {"title": question[:20], "workspaceDir": ""},
    )["session"]
    submit = _http_json(
        "POST",
        f"{api_base_url}/chat/sessions/{session['sessionId']}/messages",
        {"content": question},
    )
    detail = _wait_for_completion(api_base_url, session["sessionId"], timeout_seconds)
    events = _fetch_execution_logs(store, session["sessionId"])
    assistant_message = str(detail["messages"][-1]["content"])
    return {
        "name": name,
        "question": question,
        "sessionId": session["sessionId"],
        "submitStatus": submit["run"]["status"],
        "sessionStatus": detail["session"]["status"],
        "assistantMessage": assistant_message,
        "events": events,
    }


def _build_cases(api_base_url: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    process_payload = _http_json("GET", f"{api_base_url}/documents/process-workbench")
    collect_payload = _http_json("GET", f"{api_base_url}/documents/collect-workbench")

    process_pending_count = _find_stat_value(process_payload, "\u5f85\u5904\u7406\u5355\u636e")
    collect_recollect_count = _find_stat_value(collect_payload, "\u5f85\u8865\u91c7\u5355\u636e")

    documents = process_payload.get("documents")
    first_document_no = ""
    if isinstance(documents, list) and documents:
        first_document = documents[0]
        if isinstance(first_document, dict):
            first_document_no = str(first_document.get("documentNo") or "").strip()

    cases = [
        {
            "name": "process_pending_count",
            "question": "\u5355\u636e\u5904\u7406\u6a21\u5757\u6709\u591a\u5c11\u6761\u5f85\u529e",
        },
        {
            "name": "document_status_missing_document_no",
            "question": "\u8fd9\u5f20\u5355\u636e\u73b0\u5728\u4ec0\u4e48\u72b6\u6001",
        },
        {
            "name": "collect_recollect_count",
            "question": "\u91c7\u96c6\u5de5\u4f5c\u53f0\u6709\u591a\u5c11\u5f85\u8865\u91c7\u5355\u636e",
        },
        {
            "name": "project_introduction",
            "question": "\u4ecb\u7ecd\u4e00\u4e0b clawcheck \u9879\u76ee",
        },
    ]
    if first_document_no:
        cases.insert(
            2,
            {
                "name": "document_status_live_document",
                "question": f"\u5355\u636e {first_document_no} \u73b0\u5728\u4ec0\u4e48\u72b6\u6001",
            },
        )

    expectations = {
        "processPendingCount": process_pending_count,
        "collectRecollectCount": collect_recollect_count,
        "documentNo": first_document_no,
    }
    return cases, expectations


def _evaluate_case(case: dict[str, Any], expectations: dict[str, Any]) -> dict[str, Any]:
    name = str(case["name"])
    assistant_message = str(case["assistantMessage"])
    events = case["events"]
    failures: list[str] = []

    if name == "process_pending_count":
        if not _contains_event(events, "tool_call", "get_process_workbench"):
            failures.append("Expected get_process_workbench tool call.")
        expected_count = str(expectations.get("processPendingCount") or "")
        if expected_count and expected_count not in assistant_message:
            failures.append(f"Assistant message did not contain process pending count {expected_count}.")
    elif name == "document_status_missing_document_no":
        if _contains_event(events, "router_fallback"):
            failures.append("Missing document number case should not fall back to general chat.")
        if not _contains_event(events, "clarification"):
            failures.append("Missing document number case should emit clarification event.")
        if "documentNo" not in assistant_message:
            failures.append("Clarification reply should mention documentNo.")
    elif name == "document_status_live_document":
        document_no = str(expectations.get("documentNo") or "")
        if not _contains_event(events, "tool_call", "get_process_document_detail"):
            failures.append("Expected get_process_document_detail tool call.")
        if document_no and document_no not in assistant_message:
            failures.append(f"Assistant message did not mention live document number {document_no}.")
    elif name == "collect_recollect_count":
        if not _contains_event(events, "tool_call", "get_collect_workbench"):
            failures.append("Expected get_collect_workbench tool call.")
        expected_count = str(expectations.get("collectRecollectCount") or "")
        if expected_count and expected_count not in assistant_message:
            failures.append(f"Assistant message did not contain collect recollect count {expected_count}.")
    elif name == "project_introduction":
        if _contains_event(events, "tool_call"):
            failures.append("Project introduction should not trigger a registered realtime tool call.")
        if not _contains_event(events, "compose_answer"):
            failures.append("Project introduction should compose a model-generated answer.")

    return {
        **case,
        "passed": not failures,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live smoke tests for the 403 chat router chain.")
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help="API base URL, default: http://127.0.0.1:8000/api",
    )
    parser.add_argument(
        "--settings",
        default="automation/config/settings.prod.yaml",
        help="Settings file path used for PostgreSQL execution log access.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-chat timeout in seconds.",
    )
    args = parser.parse_args()

    settings_path = _resolve_settings_path(args.settings)
    settings = _load_runtime_settings(settings_path)
    store = PostgresChatStore(settings.db)

    try:
        health = _http_json("GET", f"{args.api_base_url}/chat/health")
        config_summary = _http_json("GET", f"{args.api_base_url}/chat/config-summary")
        cases, expectations = _build_cases(args.api_base_url)
        evaluated_cases = [
            _evaluate_case(
                _run_case(
                    api_base_url=args.api_base_url,
                    store=store,
                    name=case["name"],
                    question=case["question"],
                    timeout_seconds=max(args.timeout_seconds, 30),
                ),
                expectations,
            )
            for case in cases
        ]
    except (TimeoutError, urllib.error.URLError, KeyError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "passed": False,
                    "error": str(exc),
                    "apiBaseUrl": args.api_base_url,
                    "settingsPath": str(settings_path),
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 1

    passed = all(case["passed"] for case in evaluated_cases)
    payload = {
        "passed": passed,
        "apiBaseUrl": args.api_base_url,
        "settingsPath": str(settings_path),
        "health": {
            "status": health.get("status"),
            "provider": health.get("provider"),
            "model": health.get("model"),
            "routerEnabled": health.get("routerEnabled"),
            "codexCliAvailable": health.get("codexCliAvailable"),
        },
        "configSummary": {
            "provider": config_summary.get("provider"),
            "model": config_summary.get("model"),
            "routerEnabled": config_summary.get("routerEnabled"),
            "workspaceDir": config_summary.get("workspaceDir"),
        },
        "expectations": expectations,
        "cases": evaluated_cases,
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
