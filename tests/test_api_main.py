from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from automation.api.main import create_app


def test_create_app_without_webui_dist_returns_json_root(tmp_path: Path) -> None:
    app = create_app(webui_dist_dir=tmp_path / "missing-dist")
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["apiBase"] == "/api"
    assert response.json()["webuiDist"] == "missing"


def test_create_app_with_webui_dist_serves_spa_index(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html><body>clawcheck webui</body></html>", encoding="utf-8")

    app = create_app(webui_dist_dir=dist_dir)
    client = TestClient(app)

    root_response = client.get("/")
    health_response = client.get("/api/health")

    assert root_response.status_code == 200
    assert "clawcheck webui" in root_response.text
    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
