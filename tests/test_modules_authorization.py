"""End-to-end isolated API coverage: credential roles, tenant boundaries and cases."""
from datetime import datetime, timezone
import json

def issue_identity(api, headers, name, role, source=None, scope=None):
    body={"name":name,"role":role}
    if source: body["source"]=source
    if scope: body["scope"]=scope
    response=api.post("/api/credentials",headers=headers,json=body)
    assert response.status_code==201, response.text
    return {"Authorization":"Bearer "+response.json()["api_token"]},response.json()

def test_roles_revocation_and_authentication(authorized):
    api=authorized["api"]; admin=authorized["headers"]
    viewer,_=issue_identity(api,admin,"Observer","viewer")
    operator,_=issue_identity(api,admin,"Crew member","operator")
    reviewer,_=issue_identity(api,admin,"Quality reviewer","reviewer")
    assert api.get("/api/me",headers=viewer).status_code==200
    assert api.get("/api/assets",headers=viewer).status_code==200
    assert api.post("/api/assets",headers=viewer,json={"tag":"A","name":"Tool"}).status_code==403
    assert api.post("/api/assets",headers=reviewer,json={"tag":"A","name":"Tool"}).status_code==403
    assert api.post("/api/assets",headers=operator,json={"tag":"A","name":"Tool"}).status_code==201
    assert api.post("/api/reconcile",headers=reviewer).status_code==200
    assert api.get("/api/credentials",headers=viewer).status_code==403
    assert api.post("/api/credentials",headers=operator,json={"name":"Bad","role":"admin"}).status_code==403
    named,_=issue_identity(api,admin,"Disposable viewer","viewer")
    key=api.get("/api/me",headers=named).json()["id"]
    assert api.post("/api/credentials/"+key+"/revoke",headers=admin).status_code==200
    assert api.get("/api/me",headers=named).status_code==401
    assert api.post("/api/credentials/"+api.get("/api/me",headers=admin).json()["id"]+"/revoke",headers=admin).status_code==409

def test_connector_cannot_read_others_or_overwrite_manual_jobs(authorized):
    api=authorized["api"];admin=authorized["headers"]
    odoo,_=issue_identity(api,admin,"Odoo A","connector",source="odoo",scope="erp_a")
    rfid,_=issue_identity(api,admin,"RFID reader","connector",source="rfid")
    manual=api.post("/api/jobs",headers=admin,json={"external_ref":"LOCAL-2","title":"Manual job"})
    assert manual.status_code==201
    assert api.post("/api/jobs/import",headers=odoo,json={"external_ref":"LOCAL-2","title":"Overwritten"}).status_code==422
    assert api.post("/api/jobs",headers=admin,json={"external_ref":"odoo:erp_a:sale.order:31","title":"Claimed"}).status_code==422
    assert api.post("/api/jobs/import",headers=odoo,json={"external_ref":"odoo:erp_b:sale.order:1","title":"Wrong origin"}).status_code==403
    assert api.post("/api/jobs/import",headers=rfid,json={"external_ref":"odoo:erp_a:sale.order:1","title":"Wrong source"}).status_code==403
    assert api.get("/api/jobs",headers=odoo).status_code==403
    assert api.get("/api/connectors",headers=odoo).status_code==403
    created=api.post("/api/jobs/import",headers=odoo,json={"external_ref":"odoo:erp_a:sale.order:1","title":"Job A"})
    assert created.status_code==200,created.text
    updated=api.post("/api/jobs/import",headers=odoo,json={"external_ref":"odoo:erp_a:sale.order:1","title":"Renamed"})
    assert updated.status_code==200 and updated.json()["id"]==created.json()["id"]
    assert updated.json()["title"]=="Renamed"
    assert next(j for j in api.get("/api/jobs",headers=admin).json() if j["external_ref"]=="odoo:erp_a:sale.order:1")["title"]=="Renamed"

def test_cases_owner_notes_and_authoritative_resolution(authorized):
    api=authorized["api"];admin=authorized["headers"]
    operator,_=issue_identity(api,admin,"Field lead","operator")
    reviewer,ridentity=issue_identity(api,admin,"Reviewer","reviewer")
    asset=api.post("/api/assets",headers=admin,json={"tag":"FIRE-21","name":"Diagnostic kit"}).json()
    job=api.post("/api/jobs",headers=admin,json={"external_ref":"WO-22","title":"Inspection"}).json()
    assignment=api.post("/api/custody/issue",headers={**admin,"Idempotency-Key":"case-issue-001"},
                         json={"asset_id":asset["id"],"job_id":job["id"],"holder":"Field lead"}).json()
    assert api.post("/api/jobs/"+job["id"]+"/complete",headers=admin).status_code==200
    assert api.post("/api/reconcile",headers=reviewer).json()["open_conditions"]==1
    case=api.get("/api/cases",headers=reviewer).json()[0]
    assert case["kind"]=="closed_job_active_custody"
    detail=api.get("/api/cases/"+case["id"],headers=reviewer)
    assert detail.status_code==200
    assert api.post("/api/cases/"+case["id"]+"/acknowledge",headers=reviewer,
            json={"note":"Review accepted","owner_id":ridentity["id"]}).status_code==200
    assert api.post("/api/cases/"+case["id"]+"/notes",headers=operator,
            json={"note":"Tracking the return"}).status_code==201
    assert len(api.get("/api/cases/"+case["id"],headers=reviewer).json()["notes"])==2
    assert api.post("/api/reconcile",headers=reviewer).json()["open_conditions"]==1
    assert api.get("/api/cases",headers=admin).json()[0]["state"]=="acknowledged"
    ret=api.post("/api/custody/return",headers={**operator,"Idempotency-Key":"case-return-001"},
                 json={"custody_id":assignment["id"]})
    assert ret.status_code==200,ret.text
    assert api.post("/api/reconcile",headers=reviewer).json()["open_conditions"]==0
    assert api.get("/api/cases",headers=reviewer).json()[0]["state"]=="resolved"
    assert api.post("/api/cases/"+case["id"]+"/acknowledge",headers=reviewer,
            json={"note":"Cannot reopen manually"}).status_code==409

def test_cross_tenant_auth_and_sensor_source_validation(client,authorized):
    api=authorized["api"];admin=authorized["headers"]
    other=api.post("/api/tenants",headers={"X-Admin-Key":"a"*40},json={"name":"Other group"}).json()
    other_auth={"Authorization":"Bearer "+other["api_token"]}
    asset=api.post("/api/assets",headers=admin,json={"tag":"LOCAL-7","name":"Microscope"}).json()
    assert api.post("/api/custody/issue",headers={**other_auth,"Idempotency-Key":"cross-tenant-001"},
        json={"asset_id":asset["id"],"holder":"Intruder"}).status_code==404
    rfid,_=issue_identity(api,admin,"RFID gate","connector",source="rfid")
    reading={"asset_id":asset["id"],"source":"gps","source_event_id":"gps-2",
             "event_type":"device_seen","observed_at":datetime.now(timezone.utc).isoformat()}
    assert api.post("/api/evidence",headers=rfid,json=reading).status_code==403
    reading["source"]="rfid"
    assert api.post("/api/evidence",headers=rfid,json=reading).status_code==201
    assert api.get("/api/evidence",headers=other_auth).json()==[]
