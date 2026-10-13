import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as home:
        monkeypatch.setenv("RALLY_DB_PATH", home + "/rally.db")
        monkeypatch.setenv("RALLY_ADMIN_KEY", "a" * 40)
        from rally.app import app
        with TestClient(app) as api:
            # The app is a process-global ASGI object; each disposable test
            # represents an independent installation with a fresh IP limiter.
            middleware = app.middleware_stack
            while middleware is not None:
                if hasattr(middleware, "windows"):
                    middleware.windows.clear()
                middleware = getattr(middleware, "app", None)
            yield api

@pytest.fixture
def authorized(client):
    created = client.post("/api/tenants", headers={"X-Admin-Key": "a" * 40}, json={"name":"Test Company"})
    assert created.status_code == 201
    return {"api": client, "headers": {"Authorization": "Bearer " + created.json()["api_token"]}, "tenant": created.json()["tenant_id"]}


@pytest.fixture
def postgres_client(monkeypatch):
    admin_url = os.getenv("RALLY_PG_ADMIN_URL")
    if not admin_url:
        pytest.skip("PostgreSQL service not configured")
    name = "rally_ci_" + uuid4().hex[:16]
    admin = psycopg.connect(admin_url, autocommit=True)
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    params = conninfo_to_dict(admin_url)
    params["dbname"] = name
    test_url = make_conninfo(**params)
    try:
        with monkeypatch.context() as env:
            env.setenv("RALLY_DATABASE_URL", test_url)
            env.setenv("RALLY_ADMIN_KEY", "postgres-test-admin-secret-" + "x" * 36)
            env.delenv("RALLY_ENV", raising=False)
            from rally.app import app
            with TestClient(app) as client:
                middleware = app.middleware_stack
                while middleware is not None:
                    if hasattr(middleware, "windows"):
                        middleware.windows.clear()
                    middleware = getattr(middleware, "app", None)
                yield client, test_url
    finally:
        admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
        )
        admin.close()

