from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from automation.api.routers import chat, documents, health, jobs, settings

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEBUI_DIST_DIR = REPO_ROOT / "webui" / "dist"


def _resolve_webui_dist_dir(webui_dist_dir: Path | None = None) -> Path | None:
    candidate = webui_dist_dir
    if candidate is None:
        env_value = os.getenv("CLAWCHECK_WEBUI_DIST_DIR", "").strip()
        if env_value:
            candidate = Path(env_value)
        else:
            candidate = DEFAULT_WEBUI_DIST_DIR

    candidate = candidate.expanduser()
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    return candidate if candidate.exists() else None


def create_app(webui_dist_dir: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="clawcheck UI API",
        version="0.1.0",
        description="API for clawcheck automation, dashboards, and static web UI hosting.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_origin_regex=r"^vscode-webview://.*$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")

    resolved_dist_dir = _resolve_webui_dist_dir(webui_dist_dir)
    if resolved_dist_dir is not None:
        # Host the built SPA directly from FastAPI in Windows native deployments.
        app.mount("/", StaticFiles(directory=str(resolved_dist_dir), html=True), name="webui")
    else:

        @app.get("/")
        def read_root() -> dict[str, str]:
            return {
                "service": "clawcheck-ui-api",
                "status": "ok",
                "apiBase": "/api",
                "webuiDist": "missing",
            }

    return app


app = create_app()
