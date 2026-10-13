"""Real PostgreSQL contract checks, using a disposable CI database.

No customer database is modified. Without RALLY_PG_ADMIN_URL the module skips.
"""
import os
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest
from fastapi.testclient import TestClient


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
                yield client, test_url
    finally:
        admin.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
        )
        admin.close()


def bootstrap(api, name):
    reply = api.post("/api/tenants", headers={
        "X-Admin-Key": "postgres-test-admin-secret-" + "x" * 36,
    }, json={"name": name})
    assert reply.status_code == 201, reply.text
    return reply.json(), {"Authorization": "Bearer " + reply.json()["api_token"]}


def test_postgres_migrations_multi_tenant_integrity_and_scoped_import(postgres_client):
    api, db_url = postgres_client
    from rally.storage import connect, initialize

    with connect() as db:
        versions = {x["version"] for x in db.execute("SELECT version FROM schema_migrations").fetchall()}
        assert set(range(1, 7)).issubset(versions)
    initialize()  # Idempotent repeat startup; do not recreate existing columns.

    (a, admin_a) = bootstrap(api, "Alpha maintenance")
    (b, admin_b) = bootstrap(api, "Beta maintenance")

    # Manual operators cannot occupy the reserved ERP namespace.
    blocked = api.post("/api/jobs", headers=admin_a,
                       json={"external_ref": "odoo:alpha:sale.order:1", "title": "Impersonated"})
    assert blocked.status_code == 422

    source = api.post("/api/credentials", headers=admin_a,
                      json={"name": "Alpha Odoo", "role": "connector",
                            "source": "odoo", "scope": "alpha"})
    assert source.status_code == 201, source.text
    odoo = {"Authorization": "Bearer " + source.json()["api_token"]}

    assert api.get("/api/connectors", headers=odoo).status_code == 403
    assert api.post("/api/jobs/import", headers=odoo,
                    json={"external_ref": "odoo:beta:sale.order:1", "title": "Wrong instance"}).status_code == 403

    body = {"external_ref": "odoo:alpha:sale.order:1", "title": "Authorized job"}
    first = api.post("/api/jobs/import", headers=odoo, json=body)
    assert first.status_code == 200, first.text
    assert first.json()["source"] == "odoo"
    again = api.post("/api/jobs/import", headers=odoo, json=body)
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert api.get("/api/jobs", headers=admin_b).json() == []

    asset_b = api.post("/api/assets", headers=admin_b, json={"tag":"B-001","name":"Meter"}).json()

    # Raw database composite FK must reject cross-tenant equipment references
    # even if future application code accidentally skips its tenant guard.
    with psycopg.connect(db_url, autocommit=True) as direct:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            direct.execute(
                "INSERT INTO custody(id,tenant_id,asset_id,holder,state,issued_at) "
                "VALUES(%s,%s,%s,%s,'active',%s)",
                (str(uuid4()), a["tenant_id"], asset_b["id"], "Intruder",
                 datetime.now(timezone.utc).isoformat())
            )


def test_postgres_custody_idempotency_and_reconciliation(postgres_client):
    api, _ = postgres_client
    (_, auth) = bootstrap(api, "Industrial contractor")
    asset = api.post("/api/assets", headers=auth, json={"tag":"TOOL-1","name":"Pump"}).json()
    job = api.post("/api/jobs", headers=auth, json={"external_ref":"WO-1","title":"Repair"}).json()
    issue = {"asset_id":asset["id"],"job_id":job["id"],"holder":"Field technician"}
    first = api.post("/api/custody/issue", headers={**auth,"Idempotency-Key":"pg-issue-001"}, json=issue)
    assert first.status_code == 200, first.text
    repeat = api.post("/api/custody/issue", headers={**auth,"Idempotency-Key":"pg-issue-001"}, json=issue)
    assert repeat.status_code == 200 and repeat.json()["id"] == first.json()["id"]
    other = api.post("/api/custody/issue", headers={**auth,"Idempotency-Key":"pg-issue-002"}, json=issue)
    assert other.status_code == 409

    assert api.post("/api/jobs/"+job["id"]+"/complete", headers=auth).status_code == 200
    assert api.post("/api/reconcile", headers=auth).json()["open_conditions"] == 1
    returned = api.post("/api/custody/return",
                        headers={**auth,"Idempotency-Key":"pg-return-001"},
                        json={"custody_id":first.json()["id"],"confirmed_by":"Field technician"})
    assert returned.status_code == 200
    assert api.post("/api/reconcile", headers=auth).json()["open_conditions"] == 0
    assert api.get("/api/cases", headers=auth).json()[0]["state"] == "resolved"
