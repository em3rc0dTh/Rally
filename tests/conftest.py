import os
import tempfile
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as home:
        monkeypatch.setenv("RALLY_DB_PATH", home + "/rally.db")
        monkeypatch.setenv("RALLY_ADMIN_KEY", "a" * 40)
        from rally.app import app
        with TestClient(app) as api:
            yield api

@pytest.fixture
def authorized(client):
    created = client.post("/api/tenants", headers={"X-Admin-Key": "a" * 40}, json={"name":"Test Company"})
    assert created.status_code == 201
    return {"api": client, "headers": {"Authorization": "Bearer " + created.json()["api_token"]}, "tenant": created.json()["tenant_id"]}
