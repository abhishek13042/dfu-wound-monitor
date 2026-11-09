"""P07-S02 failure modes: a database outage must not stop the service."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import ApiSettings, create_app

UNREACHABLE = "postgresql://nobody@127.0.0.1:1/none"


def test_unreachable_database_leaves_the_service_alive_but_not_ready(tiny_engine, tmp_path):
    settings = ApiSettings(data_dir=tmp_path, load_model=False, database_url=UNREACHABLE)
    with TestClient(create_app(settings, engine=tiny_engine)) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json()["model"] == "READY"
        assert ready.json()["database"] == "NOT_READY"
        response = client.post("/api/v1/cases", json={})
        assert response.status_code == 503
        assert response.json()["error"]["category"] == "INFRASTRUCTURE_FAILURE"
        assert "nobody" not in response.text


def test_unmigrated_schema_reports_not_ready(tiny_engine, tmp_path, database_url, monkeypatch):
    if database_url.endswith(".sqlite3"):
        return  # SQLite migrates itself when opened
    monkeypatch.setattr("src.storage.database.SCHEMA_VERSION", 999)
    monkeypatch.setattr("src.api.app.SCHEMA_VERSION", 999)
    settings = ApiSettings(data_dir=tmp_path, load_model=False, database_url=database_url)
    with TestClient(create_app(settings, engine=tiny_engine)) as client:
        ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["database"] == "NOT_READY"
