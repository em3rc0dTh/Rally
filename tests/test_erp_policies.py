"""Admin-configured ERP state-age rules must never infer business facts blindly."""
from datetime import datetime, timezone, timedelta


def _credential(api, admin):
    response = api.post("/api/credentials", headers=admin,
        json={"name":"Odoo limited","role":"connector","source":"odoo","scope":"customer_a"})
    assert response.status_code==201,response.text
    record=response.json()
    return record["id"], {"Authorization":"Bearer "+record["api_token"]}


def _record(state, age_seconds=180):
    return {"instance":"customer_a","company_id":7,"model":"purchase.order",
            "record_id":83,"state":state,
            "source_modified_at":(datetime.now(timezone.utc)-timedelta(seconds=age_seconds)).isoformat()}


def test_explicit_erp_rule_opens_and_resolves_only_with_valid_evidence(authorized):
    api,admin=authorized["api"],authorized["headers"]
    cid,reader=_credential(api,admin)
    policy={"instance":"customer_a","company_id":7,"model":"purchase.order",
            "state":"draft","max_age_seconds":60,"severity":"warning"}
    assert api.post("/api/erp/policies",headers=admin,json=policy).status_code==422
    assert api.post("/api/erp/grants",headers=admin,json={
        "credential_id":cid,"company_id":7,"models":["purchase.order"]}).status_code==201
    assert api.post("/api/erp/records/import",headers=reader,json=_record("draft")).status_code==201
    assert api.post("/api/reconcile",headers=admin).json()["open_conditions"]==0
    added=api.post("/api/erp/policies",headers=admin,json=policy)
    assert added.status_code==201,added.text
    assert api.get("/api/erp/policies",headers=admin).json()[0]["enabled"]==1
    result=api.post("/api/reconcile",headers=admin)
    assert result.status_code==200 and result.json()["open_conditions"]==1
    case=next(c for c in api.get("/api/cases",headers=admin).json()
              if c["kind"]=="erp_state_overdue")
    assert case["severity"]=="warning" and case["state"]=="open"
    assert "purchase.order" in case["description"]
    # Repeated reconcile does not generate duplicate cases.
    api.post("/api/reconcile",headers=admin)
    assert len([c for c in api.get("/api/cases",headers=admin).json()
                if c["kind"]=="erp_state_overdue"])==1
    # A state transition invalidates the agreed condition and can resolve a case.
    assert api.post("/api/erp/records/import",headers=reader,
                    json=_record("purchase",5)).status_code==201
    api.post("/api/reconcile",headers=admin)
    case2=api.get("/api/cases/"+case["id"],headers=admin).json()
    assert case2["state"]=="resolved"
    assert api.post("/api/erp/policies/"+added.json()["id"]+"/disable",
                    headers=reader).status_code==403


def test_admin_can_disable_policy_and_source_stale_cannot_close_open_case(authorized):
    api,admin=authorized["api"],authorized["headers"]
    cid,reader=_credential(api,admin)
    api.post("/api/erp/grants",headers=admin,json={
        "credential_id":cid,"company_id":7,"models":["purchase.order"]})
    policy={"instance":"customer_a","company_id":7,"model":"purchase.order",
            "state":"draft","max_age_seconds":60}
    pid=api.post("/api/erp/policies",headers=admin,json=policy).json()["id"]
    api.post("/api/erp/records/import",headers=reader,json=_record("draft"))
    api.post("/api/reconcile",headers=admin)
    case=next(c for c in api.get("/api/cases",headers=admin).json()
              if c["kind"]=="erp_state_overdue")
    # Force the source cache to be older than the freshness boundary in disposable DB.
    from rally.storage import connect
    with connect() as db:
        db.execute("UPDATE erp_records SET last_seen=? WHERE tenant_id=?",
                   ((datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),
                    authorized["tenant"]))
        db.commit()
    api.post("/api/reconcile",headers=admin)
    assert api.get("/api/cases/"+case["id"],headers=admin).json()["state"]=="open"
    assert api.post("/api/erp/policies/"+pid+"/disable",headers=admin).status_code==200
    api.post("/api/reconcile",headers=admin)
    assert api.get("/api/cases/"+case["id"],headers=admin).json()["state"]=="resolved"
