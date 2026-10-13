"""Mock-provider contract checks; never contacts Odoo, Traccar or external systems."""
import asyncio
import json
from datetime import datetime, timezone, timedelta
import pytest

def test_odoo_keyset_import_and_customer_domain(monkeypatch):
    import adapters.odoo_sync_cli as module
    pages=[]
    sent=[]
    class FakeOdoo:
        def __init__(self, config): pass
        async def search_read(self,model,domain,fields,limit=500):
            pages.append(domain)
            if len(pages)==1:
                return [{"id":1,"name":"SO1","state":"sale","company_id":[7,"HQ"]}]
            return []
    class FakeRally:
        async def post(self,path,body):
            sent.append((path,body));return {"id":"job-1"}
        async def heartbeat(self,status,detail):
            sent.append(("heartbeat",status,detail))
    monkeypatch.setattr(module,"OdooJSON2",FakeOdoo)
    monkeypatch.setattr("adapters.transport.RallyClient",FakeRally)
    env={"ODOO_URL":"https://odoo.invalid","ODOO_DATABASE":"mycompany","ODOO_API_KEY":"test-key",
         "ODOO_COMPANY_IDS":"7","ODOO_INSTANCE":"my_odoo","RALLY_URL":"http://localhost:8080",
         "RALLY_TENANT_TOKEN":"test-token","ODOO_WORKORDER_DOMAIN_JSON":'[["x_is_field_service","=",true]]'}
    for k,v in env.items():monkeypatch.setenv(k,v)
    asyncio.run(module.main())
    assert len(pages)==2
    assert ["x_is_field_service","=",True] in pages[0]
    assert ["company_id","in",[7]] in pages[0]
    assert sent[0][1]["external_ref"]=="odoo:my_odoo:sale.order:1"
    assert sent[-1][1]=="ok"

def test_odoo_foreign_company_is_refused(monkeypatch):
    import adapters.odoo_sync_cli as module
    class FakeOdoo:
        def __init__(self,c): pass
        async def search_read(self,*args,**kwargs):
            return [{"id":1,"state":"sale","company_id":[999,"Not authorized"]}]
    class FakeRally:
        async def post(self,*args):pytest.fail("Unauthorized sale was sent to Rally")
        async def heartbeat(self,*args):pass
    monkeypatch.setattr(module,"OdooJSON2",FakeOdoo)
    monkeypatch.setattr("adapters.transport.RallyClient",FakeRally)
    env={"ODOO_URL":"https://odoo.invalid","ODOO_DATABASE":"db","ODOO_API_KEY":"x",
         "ODOO_COMPANY_IDS":"1","RALLY_URL":"http://localhost:8080",
         "RALLY_TENANT_TOKEN":"test-token","ODOO_WORKORDER_DOMAIN_JSON":'[["x_is_field_service","=",true]]'}
    for k,v in env.items():monkeypatch.setenv(k,v)
    with pytest.raises(ValueError,match="outside"):
        asyncio.run(module.main())

def test_traccar_gateway_fresh_and_empty_coverage(monkeypatch):
    import adapters.ingest_cli as module
    seen=[]
    fresh={"id":12,"deviceId":101,"fixTime":datetime.now(timezone.utc).isoformat(),
           "latitude":-12.2,"longitude":-77.1,"valid":True,"speed":0}
    positions=[fresh]
    class FakeTraccar:
        def __init__(self,*args):pass
        async def positions(self):return positions.copy()
    class FakeRally:
        async def post(self,path,body):seen.append((path,body))
        async def heartbeat(self,status,detail):seen.append(("heartbeat",status,detail))
    monkeypatch.setattr(module,"Traccar",FakeTraccar)
    monkeypatch.setattr(module,"RallyClient",FakeRally)
    env={"TRACCAR_URL":"https://tracking.invalid","TRACCAR_TOKEN":"read-only",
         "RALLY_URL":"http://localhost:8080","RALLY_TENANT_TOKEN":"test",
         "TRACCAR_DEVICE_ASSET_MAP":'{"101":"asset-1"}',"TRACCAR_INSTANCE":"traccarA"}
    for k,v in env.items():monkeypatch.setenv(k,v)
    asyncio.run(module.main())
    assert seen[0][1]["source_event_id"]=="traccarA:12"
    assert seen[-1][1]=="ok"
    seen.clear()
    positions.clear()
    asyncio.run(module.main())
    assert seen[-1][1]=="error"
    assert "mapped_devices_absent=1" in seen[-1][2]

def test_traccar_stale_not_reported_as_healthy(monkeypatch):
    import adapters.ingest_cli as module
    messages=[]
    stale={"id":43,"deviceId":111,
           "fixTime":(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat(),
           "latitude":-12.1,"longitude":-77.2,"valid":False}
    class FakeTraccar:
        def __init__(self,*args):pass
        async def positions(self):return [stale]
    class FakeRally:
        async def post(self,*args):pass
        async def heartbeat(self,status,detail):messages.append((status,detail))
    monkeypatch.setattr(module,"Traccar",FakeTraccar)
    monkeypatch.setattr(module,"RallyClient",FakeRally)
    env={"TRACCAR_URL":"https://tracking.invalid","TRACCAR_TOKEN":"x",
         "RALLY_URL":"http://localhost:8080","RALLY_TENANT_TOKEN":"x",
         "TRACCAR_DEVICE_ASSET_MAP":'{"111":"asset-1"}'}
    for k,v in env.items():monkeypatch.setenv(k,v)
    asyncio.run(module.main())
    assert messages[-1][0]=="error"
    assert "stale_or_unknown_fix=1" in messages[-1][1]
