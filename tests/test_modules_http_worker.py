"""Local HTML, security headers, validation, and periodic worker contracts."""
import pytest

def test_cockpit_html_and_security_headers(client):
    homepage=client.get("/")
    assert homepage.status_code==200
    assert "Mission Control" in homepage.text
    assert 'src="/static/app.js"' in homepage.text
    headers=homepage.headers
    assert headers.get("x-content-type-options")=="nosniff"
    assert headers.get("x-frame-options")=="DENY"
    assert headers.get("cache-control")=="no-store"
    script=client.get("/static/app.js")
    assert script.status_code==200
    assert "const canOperate" in script.text
    assert "sessionStorage.removeItem" in script.text

def test_cockpit_rejects_bad_host(client):
    r=client.get("/",headers={"Host":"untrusted-server.invalid"})
    assert r.status_code==400

def test_api_rejects_oversized_body_and_unexpected_json(authorized):
    api=authorized["api"];h=authorized["headers"]
    # Send a correctly typed JSON body too large for GuardMiddleware.
    r=api.post("/api/assets",headers={**h,"Content-Type":"application/json"},
               content=b'{"tag":"ONE","name":"'+b"x"*140000+b'"}')
    assert r.status_code==413
    bad=api.post("/api/assets",headers=h,json={"tag":"A","name":"B","tenant_id":"forged"})
    assert bad.status_code==422

def test_reconciliation_worker_updates_readiness(authorized,monkeypatch):
    from rally import worker
    from rally.storage import connect
    api=authorized["api"];h=authorized["headers"]
    before=api.get("/readyz")
    assert before.status_code==503
    class OneCycleEvent:
        def __init__(self):self.stopped=False
        def is_set(self):return self.stopped
        def set(self):self.stopped=True
        def wait(self,seconds):self.stopped=True
    monkeypatch.setattr(worker.threading,"Event",OneCycleEvent)
    monkeypatch.setattr(worker.signal,"signal",lambda *args:None)
    worker.main()
    after=api.get("/readyz")
    assert after.status_code==200,after.text
    assert after.json()["reconciliation"]=="ok"
