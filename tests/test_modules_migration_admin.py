"""Offline data migration and direct-operator recovery, using disposable records only."""
from hashlib import sha256
from uuid import uuid4
import sys
import pytest

def test_local_admin_recovery_creates_named_revocable_identity(authorized,monkeypatch,capsys):
    from rally import admin
    api=authorized["api"]
    tenant_id=authorized["tenant"]
    monkeypatch.setattr(sys,"argv",["rally.admin","recover",tenant_id,"Recovery custodian"])
    admin.main()
    output=capsys.readouterr().out.splitlines()
    token=output[-1].strip()
    assert len(token)>32
    response=api.get("/api/me",headers={"Authorization":"Bearer "+token})
    assert response.status_code==200
    assert response.json()["name"]=="Recovery custodian"
    assert response.json()["role"]=="admin"
    audits=api.get("/api/audit",headers=authorized["headers"]).json()
    assert any(x["action"]=="recovered_by_deployment_operator" for x in audits)
    assert all(token not in str(a) for a in audits)

def test_offline_sqlite_to_empty_postgres_migration(postgres_client,tmp_path,monkeypatch):
    from rally.storage import initialize, connect, transaction, one
    from rally import migrate_sqlite
    api,pg_url=postgres_client
    source_path=str(tmp_path/"mk0-export.db")
    initialize(source_path)
    tenant_id=str(uuid4())
    asset_id=str(uuid4())
    with connect(source_path) as source:
        with transaction(source):
            source.execute("INSERT INTO tenants(id,name,token_hash,created_at) VALUES(?,?,?,?)",
                           (tenant_id,"Imported legacy tenant",sha256(b"test-migration-token").hexdigest(),"2026-10-13T12:00:00+00:00"))
            source.execute("INSERT INTO assets(id,tenant_id,tag,name,created_at) VALUES(?,?,?,?,?)",
                           (asset_id,tenant_id,"MIG-01","Legacy barcode","2026-10-13T12:00:00+00:00"))
    monkeypatch.setattr(sys,"argv",["rally.migrate_sqlite",source_path])
    migrate_sqlite.main()
    with connect() as pg:
        tenant=one(pg,"SELECT * FROM tenants WHERE id=?",(tenant_id,))
        asset=one(pg,"SELECT * FROM assets WHERE id=?",(asset_id,))
        assert tenant["name"]=="Imported legacy tenant"
        assert asset["tag"]=="MIG-01"
        assert one(pg,"SELECT id FROM credentials WHERE id=?",(tenant_id,)) is not None
    # The original source stays intact.
    with connect(source_path) as source:
        assert one(source,"SELECT id FROM assets WHERE id=?",(asset_id,)) is not None
    # Re-import must reject non-empty destination before any duplicate write.
    with pytest.raises(RuntimeError,match="Destination must be empty"):
        migrate_sqlite.main()
