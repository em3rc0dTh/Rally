"""Contract, security and schema checks; no calls to a real Odoo server."""
import asyncio
import json
from datetime import datetime, timezone, timedelta
import pytest
from adapters.odoo_enterprise_cli import validate_selector, load_config
from rally.erp_contract import normalize_record, MODEL_CONTRACTS


def tenant_credential(api, admin, *, name="Odoo enterprise", role="connector", source="odoo", scope="instance_1"):
    data = {"name": name, "role": role}
    if source: data["source"] = source
    if scope: data["scope"] = scope
    response = api.post("/api/credentials", headers=admin, json=data)
    assert response.status_code == 201, response.text
    row = response.json()
    return row["id"], {"Authorization": "Bearer " + row["api_token"]}


def test_models_are_status_only_and_company_bound():
    record = normalize_record("purchase.order", {
        "id": 19, "company_id": [7, "Restricted Company"], "state": "purchase",
        "write_date": "2026-10-13 17:02:00", "name": "DO NOT IMPORT",
        "amount_total": 999, "bank_account_id": "REDACT"
    }, "instance_1", {7})
    assert record == {
        "instance": "instance_1", "company_id": 7, "model": "purchase.order",
        "record_id": 19, "state": "purchase",
        "source_modified_at": "2026-10-13T17:02:00+00:00"
    }
    assert "amount_total" not in repr(record) and "DO NOT IMPORT" not in repr(record)
    with pytest.raises(ValueError, match="outside"):
        normalize_record("purchase.order", {
            "id": 1, "company_id": 9, "state": "purchase",
            "write_date": "2026-10-13 17:02:00"
        }, "instance_1", {7})
    assert normalize_record("hr.employee", {
        "id": 3, "company_id": 7, "active": True,
        "write_date": "2026-10-13 17:02:00", "name": "PRIVATE"
    }, "instance_1", {7})["state"] == "active"
    assert normalize_record("hr.attendance", {
        "id": 4, "company_id": 7, "check_out": False,
        "write_date": "2026-10-13 17:02:00", "employee_id": [3, "PRIVATE"]
    }, "instance_1", {7})["state"] == "checked_in"
    assert set(MODEL_CONTRACTS) >= {"crm.lead", "sale.order", "purchase.order",
        "stock.picking", "hr.employee", "hr.attendance", "hr.leave",
        "hr.payslip", "hr.expense", "account.move", "account.payment"}


def test_selector_validation_and_fail_closed_config(monkeypatch):
    assert validate_selector([["state", "in", ["purchase"]]]) == [["state", "in", ["purchase"]]]
    for bad in ([], [["|"]], [["id", "in", 1]], [["id", "=", []]],
                [["name", "ilike", "a"]], [["field;drop", "=", 1]]):
        with pytest.raises(ValueError):
            validate_selector(bad)
    config = {"ODOO_URL": "https://odoo.invalid", "ODOO_DATABASE": "db",
              "ODOO_API_KEY": "provider-key", "ODOO_INSTANCE": "instance_1",
              "ODOO_COMPANY_IDS": "7", "RALLY_URL": "http://localhost:8080",
              "RALLY_TENANT_TOKEN": "rally-key",
              "ODOO_ENTERPRISE_MODELS": "purchase.order",
              "ODOO_ENTERPRISE_SELECTORS_JSON": '{}'}
    for key, value in config.items(): monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match="reviewed selector"):
        load_config()
    monkeypatch.setenv("ODOO_ENTERPRISE_SELECTORS_JSON",
                       '{"purchase.order":[["state","in",["purchase","done"]]]}')
    instance, companies, models, selectors, maximum = load_config()
    assert (instance, companies, models) == ("instance_1", [7], ["purchase.order"])
    assert maximum == 10000
    assert selectors["purchase.order"][0] == ["state", "in", ["purchase", "done"]]
    monkeypatch.setenv("ODOO_ENTERPRISE_MODELS", "purchase.order,account.move")
    with pytest.raises(ValueError, match="reviewed selector"):
        load_config()


def test_erp_grants_snapshots_replay_transition_and_tenant_security(authorized):
    api, admin = authorized["api"], authorized["headers"]
    connector_id, connector = tenant_credential(api, admin)
    _, gps = tenant_credential(api, admin, name="GPS connector", source="traccar", scope=None)
    viewer_id, viewer = tenant_credential(api, admin, name="Viewer", role="viewer", source=None, scope=None)
    assert api.get("/api/erp/catalog", headers=admin).status_code == 200
    grant = {"credential_id": connector_id, "company_id": 7,
             "models": ["purchase.order", "account.move"]}
    created_grant = api.post("/api/erp/grants", headers=admin, json=grant)
    assert created_grant.status_code == 201, created_grant.text
    assert api.post("/api/erp/grants", headers=viewer, json=grant).status_code == 403
    assert api.get("/api/erp/grants", headers=connector).status_code == 403
    now = datetime.now(timezone.utc)-timedelta(minutes=2)
    payload = {"instance": "instance_1", "company_id": 7, "model": "purchase.order",
               "record_id": 55, "state": "purchase",
               "source_modified_at": now.isoformat()}
    assert api.post("/api/erp/records/import", headers=gps, json=payload).status_code == 403
    assert api.post("/api/erp/records/import", headers=admin, json=payload).status_code == 403
    assert api.post("/api/erp/records/import", headers=connector,
                    json={**payload, "company_id": 8}).status_code == 403
    assert api.post("/api/erp/records/import", headers=connector,
                    json={**payload, "instance": "other"}).status_code == 403
    assert api.post("/api/erp/records/import", headers=connector,
                    json={**payload, "model": "hr.payslip"}).status_code == 403
    assert api.post("/api/erp/records/import", headers=connector,
                    json={**payload, "amount_total": 9999}).status_code == 422
    first = api.post("/api/erp/records/import", headers=connector, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["action"] == "created"
    rid = first.json()["id"]
    replay = api.post("/api/erp/records/import", headers=connector, json=payload)
    assert replay.status_code == 201 and replay.json()["action"] == "unchanged"
    moved = {**payload, "source_modified_at": (now+timedelta(minutes=1)).isoformat(),
             "state": "done"}
    assert api.post("/api/erp/records/import", headers=connector, json=moved).json()["action"] == "changed"
    assert api.post("/api/erp/records/import", headers=connector, json=payload).json()["action"] == "older_ignored"
    conflict = {**moved, "state": "cancel"}
    assert api.post("/api/erp/records/import", headers=connector, json=conflict).status_code == 409
    history = api.get("/api/erp/records/" + rid + "/history", headers=admin).json()
    assert len(history) == 2 and {e["current_state"] for e in history} == {"done","purchase"}
    assert api.get("/api/erp/records", headers=viewer).status_code == 403
    assert api.get("/api/erp/summary", headers=viewer).status_code == 403
    assert api.get("/api/erp/records", headers=connector).status_code == 403
    assert api.get("/api/erp/records", headers=admin).json()[0]["state"] == "done"
    assert api.get("/api/erp/summary", headers=admin).json()[0]["records"] == 1
    removed = api.delete(f"/api/erp/grants/{connector_id}/7/purchase.order",headers=admin)
    assert removed.status_code == 200
    assert api.post("/api/erp/records/import", headers=connector, json=moved).status_code == 403
    assert api.get("/api/erp/records",headers=admin).json()[0]["state"] == "done"
    assert viewer_id


def test_erp_cross_tenant_isolation(client, authorized):
    api, admin = authorized["api"], authorized["headers"]
    connector_id, connector = tenant_credential(api, admin)
    api.post("/api/erp/grants", headers=admin, json={
        "credential_id": connector_id, "company_id": 7, "models":["crm.lead"]})
    ts=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    created=api.post("/api/erp/records/import",headers=connector,json={
        "instance":"instance_1","company_id":7,"model":"crm.lead",
        "record_id":1,"state":"stage:3","source_modified_at":ts})
    assert created.status_code == 201
    other = api.post("/api/tenants", headers={"X-Admin-Key": "a"*40},
                     json={"name": "Another tenant"}).json()
    foreign = {"Authorization": "Bearer " + other["api_token"]}
    assert api.get("/api/erp/records",headers=foreign).json() == []
    assert api.get("/api/erp/summary",headers=foreign).json() == []
    assert api.get("/api/erp/records/"+created.json()["id"]+"/history",headers=foreign).status_code==404
    assert api.post("/api/erp/grants",headers=foreign,json={
        "credential_id":connector_id,"company_id":7,"models":["crm.lead"]}).status_code==422


def test_odoo_enterprise_importer_bounded_read_only(monkeypatch):
    import adapters.odoo_enterprise_cli as module
    rows = [{"id":4, "company_id":[7,"HQ"],"state":"purchase",
             "write_date":"2026-10-13 12:00:00", "amount_total":999999}]
    calls = []
    class Odoo:
        def __init__(self, config): pass
        async def search_read(self, model, domain, fields, limit=100, order="id asc"):
            calls.append(("provider",model,domain,fields,limit))
            if domain[1][2] == 0:
                return rows.copy()
            return []
    class Rally:
        async def post(self, path, body):
            calls.append((path,body))
            return {"action":"created" if len([c for c in calls if c[0]==path])==1 else "unchanged"}
        async def heartbeat(self,status,detail):
            calls.append(("heartbeat",status,detail))
    monkeypatch.setattr(module,"OdooJSON2",Odoo)
    monkeypatch.setattr(module,"RallyClient",Rally)
    config={"ODOO_URL":"https://odoo.invalid","ODOO_DATABASE":"db","ODOO_API_KEY":"key",
            "ODOO_COMPANY_IDS":"7","ODOO_INSTANCE":"instance_1",
            "ODOO_ENTERPRISE_MODELS":"purchase.order",
            "ODOO_ENTERPRISE_SELECTORS_JSON":'{"purchase.order":[["state","=","purchase"]]}',
            "RALLY_URL":"http://localhost:8080","RALLY_TENANT_TOKEN":"connector"}
    for key,val in config.items():monkeypatch.setenv(key,val)
    asyncio.run(module.main())
    provider = calls[0]
    assert provider[2][0] == ["company_id","in",[7]]
    assert provider[2][1] == ["id",">",0]
    assert provider[3] == ["id","company_id","write_date","state"]
    posted = next(c[1] for c in calls if c[0] == "erp/records/import")
    assert posted == {"instance":"instance_1","company_id":7,"model":"purchase.order",
                      "record_id":4,"state":"purchase","source_modified_at":"2026-10-13T12:00:00+00:00"}
    assert "amount_total" not in json.dumps(posted)
    assert calls[-1][1] == "ok"
