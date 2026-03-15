from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from automation.api.routers import documents, health, jobs, settings

app = FastAPI(
    title="clawcheck UI API",
    version="0.1.0",
    description="Web UI mock API for clawcheck operations dashboard.",
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
app.include_router(settings.router, prefix="/api")


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "service": "clawcheck-ui-api",
        "status": "ok",
        "apiBase": "/api",
    }
