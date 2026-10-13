from datetime import datetime, timedelta, timezone

def test_admin_auth_and_tenant_isolation(client, authorized):
    assert client.post("/api/tenants", json={"name":"Other"}).status_code == 403
    api, h = authorized["api"], authorized["headers"]
    assert api.get("/api/assets").status_code == 401
    a = api.post("/api/assets", headers=h, json={"tag":"CAM-1","name":"Camera"})
    assert a.status_code == 201
    other = api.post("/api/tenants", headers={"X-Admin-Key":"a"*40}, json={"name":"Another Company"}).json()
    h2 = {"Authorization":"Bearer "+other["api_token"]}
    assert api.get("/api/assets", headers=h2).json() == []
    assert api.get("/api/assets", headers=h).json()[0]["tag"] == "CAM-1"

def test_custody_unique_and_idempotency(authorized):
    api, h = authorized["api"], authorized["headers"]
    asset = api.post("/api/assets", headers=h, json={"tag":"TOOL-2","name":"Scanner"}).json()
    job = api.post("/api/jobs", headers=h, json={"external_ref":"WO-2","title":"Install"}).json()
    req={"asset_id":asset["id"],"job_id":job["id"],"holder":"Operator"}
    first = api.post("/api/custody/issue", headers={**h,"Idempotency-Key":"key-first-001"}, json=req)
    assert first.status_code == 200
    assert api.post("/api/custody/issue",headers={**h,"Idempotency-Key":"key-first-001"},json=req).json()["id"] == first.json()["id"]
    assert api.post("/api/custody/issue",headers={**h,"Idempotency-Key":"key-second-002"},json=req).status_code == 409
    assert api.post("/api/custody/issue",headers={**h,"Idempotency-Key":"key-first-001"},json={**req,"holder":"Someone else"}).status_code == 409
    returned=api.post("/api/custody/return",headers={**h,"Idempotency-Key":"key-return-003"},json={"custody_id":first.json()["id"],"confirmed_by":"Operator"})
    assert returned.status_code == 200
    assert api.post("/api/custody/return",headers={**h,"Idempotency-Key":"key-return-003"},json={"custody_id":first.json()["id"],"confirmed_by":"Operator"}).status_code == 200
    assert api.post("/api/custody/issue",headers={**h,"Idempotency-Key":"key-third-004"},json=req).status_code == 200

def test_reconciliation_opens_and_resolves(authorized):
    api,h=authorized["api"],authorized["headers"]
    asset=api.post("/api/assets",headers=h,json={"tag":"RF-3","name":"Meter"}).json()
    job=api.post("/api/jobs",headers=h,json={"external_ref":"WO-3","title":"Audit"}).json()
    due=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
    active=api.post("/api/custody/issue",headers={**h,"Idempotency-Key":"reconcile-001"},json={"asset_id":asset["id"],"job_id":job["id"],"holder":"Field tech","due_at":due}).json()
    assert api.post("/api/jobs/"+job["id"]+"/complete",headers=h).status_code == 200
    result=api.post("/api/reconcile",headers=h).json()
    assert result["open_conditions"] == 1
    assert api.get("/api/overview",headers=h).json()["open_cases"] == 1
    api.post("/api/custody/return",headers={**h,"Idempotency-Key":"reconcile-002"},json={"custody_id":active["id"],"confirmed_by":"Technician"})
    assert api.post("/api/reconcile",headers=h).json()["open_conditions"] == 0
    assert api.get("/api/cases",headers=h).json()[0]["state"] == "resolved"

def test_evidence_deduplicated_but_not_conflated_with_custody(authorized):
    api,h=authorized["api"],authorized["headers"]
    asset=api.post("/api/assets",headers=h,json={"tag":"TAG-9","name":"Router"}).json()
    raw={"asset_id":asset["id"],"source":"rfid","source_event_id":"reader-123","event_type":"asset_seen","observed_at":datetime.now(timezone.utc).isoformat(),"payload":{"reader":"dock-2"}}
    assert api.post("/api/evidence",headers=h,json=raw).status_code == 201
    assert api.post("/api/evidence",headers=h,json=raw).status_code == 201
    assert len(api.get("/api/evidence",headers=h).json()) == 1
    assert api.post("/api/evidence",headers=h,json={**raw,"event_type":"different"}).status_code == 409
    assert api.get("/api/overview",headers=h).json()["active_custody"] == 0
