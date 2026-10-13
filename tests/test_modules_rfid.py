"""RFID spool durability and backpressure with fake backend and disposable files."""
import asyncio
import io
import json
import sqlite3
import sys
import pytest

def test_spool_persists_outage_and_drains(monkeypatch,tmp_path):
    import adapters.rfid_ingest_cli as module
    spool=tmp_path/"device-spool.db"
    events=[]
    broken=[True]
    class FakeRally:
        token="fake-token"
        base="https://rally.invalid"
        async def post(self,path,body):
            if broken[0]:raise RuntimeError("Backend temporarily unavailable")
            events.append((path,body))
            return {"id":"event-1"}
        async def heartbeat(self,status,detail):pass
    class FakeResponse:
        def json(self):return {"tenant_id":"tenant-1"}
    async def fake_request(client,method,url,headers):
        return FakeResponse()
    monkeypatch.setattr(module,"RallyClient",FakeRally)
    monkeypatch.setattr("adapters.transport.request",fake_request)
    env={"RFID_EPC_ASSET_MAP":'{"E001":"asset-1"}',"RFID_SPOOL_PATH":str(spool),
         "RFID_MAX_SPOOL_EVENTS":"3","RFID_MAX_SPOOL_BYTES":"16777216"}
    for k,v in env.items():monkeypatch.setenv(k,v)
    line=(json.dumps({"reader_id":"door","epc":"E001","observed_at":"2026-10-13T12:00:00Z"})+"\n").encode()
    monkeypatch.setattr(sys,"stdin",io.TextIOWrapper(io.BytesIO(line)))
    monkeypatch.setattr(sys,"argv",["rfid_ingest_cli"])
    with pytest.raises(RuntimeError,match="Backend temporarily"):
        asyncio.run(module.main())
    with sqlite3.connect(spool) as db:
        assert db.execute("SELECT COUNT(*) FROM spool").fetchone()[0]==1
    broken[0]=False
    monkeypatch.setattr(sys,"argv",["rfid_ingest_cli","--drain"])
    asyncio.run(module.main())
    assert len(events)==1 and events[0][1]["event_type"]=="rfid_observed"
    with sqlite3.connect(spool) as db:
        assert db.execute("SELECT COUNT(*) FROM spool").fetchone()[0]==0

def test_rfid_oversize_input_rejected_before_ack(monkeypatch,tmp_path):
    import adapters.rfid_ingest_cli as module
    class FakeRally:
        base="https://rally.invalid"
        token="fake-token"
        async def post(self,*args):pytest.fail("Oversized event sent upstream")
        async def heartbeat(self,*args):pass
    class FakeResponse:
        def json(self):return {"tenant_id":"tenant-1"}
    async def fake_request(*args,**kwargs):return FakeResponse()
    monkeypatch.setattr(module,"RallyClient",FakeRally)
    monkeypatch.setattr("adapters.transport.request",fake_request)
    monkeypatch.setenv("RFID_SPOOL_PATH",str(tmp_path/"overflow.db"))
    monkeypatch.setenv("RFID_EPC_ASSET_MAP",'{"E001":"asset-1"}')
    monkeypatch.setattr(sys,"stdin",io.TextIOWrapper(io.BytesIO(b"x"*70000+b"\n")))
    monkeypatch.setattr(sys,"argv",["rfid_ingest_cli"])
    with pytest.raises(ValueError,match="64 KiB"):
        asyncio.run(module.main())
