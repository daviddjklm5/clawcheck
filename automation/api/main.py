from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from automation.api.routers import documents, health, jobs, reports, settings

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
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")

    resolved_dist_dir = _resolve_webui_dist_dir(webui_dist_dir)
    if resolved_dist_dir is not None:
        assets_dir = resolved_dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="webui-assets")

        def _resolve_dist_file(full_path: str) -> Path | None:
            if not full_path:
                return None
            candidate = (resolved_dist_dir / full_path).resolve()
            try:
                candidate.relative_to(resolved_dist_dir)
            except ValueError:
                return None
            return candidate if candidate.is_file() else None

        @app.get("/", include_in_schema=False)
        def read_webui_root() -> FileResponse:
            return FileResponse(resolved_dist_dir / "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        def read_webui_path(full_path: str) -> FileResponse:
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")

            matched_file = _resolve_dist_file(full_path)
            if matched_file is not None:
                return FileResponse(matched_file)
            return FileResponse(resolved_dist_dir / "index.html")
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
