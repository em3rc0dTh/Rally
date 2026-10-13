import pytest
from adapters.odoo_sync_cli import map_confirmed_sale

def test_only_confirmed_sales_become_jobs():
    assert map_confirmed_sale({"id":42,"name":"SO42","state":"sale"}, "acme") == {
        "external_ref":"odoo:acme:sale.order:42",
        "title":"Sales order SO42"
    }
    with pytest.raises(ValueError):
        map_confirmed_sale({"id":42,"name":"DRAFT","state":"draft"}, "acme")
    with pytest.raises(ValueError):
        map_confirmed_sale({"name":"Missing ID","state":"sale"}, "acme")
    with pytest.raises(ValueError):
        map_confirmed_sale({"id":True, "state":"sale"}, "acme")
    with pytest.raises(ValueError):
        map_confirmed_sale({"id":1,"state":"sale"}, "namespace with spaces")

def test_rally_requires_explicit_work_order_domain(monkeypatch):
    import asyncio
    from adapters.odoo_sync_cli import main
    for key in ("ODOO_URL","ODOO_DATABASE","ODOO_API_KEY",
                "ODOO_COMPANY_IDS","RALLY_URL","RALLY_TENANT_TOKEN"):
        monkeypatch.setenv(key, "1" if key=="ODOO_COMPANY_IDS" else "placeholder")
    monkeypatch.delenv("ODOO_WORKORDER_DOMAIN_JSON", raising=False)
    with pytest.raises(ValueError, match="ODOO_WORKORDER_DOMAIN_JSON"):
        asyncio.run(main())
    monkeypatch.setenv("ODOO_WORKORDER_DOMAIN_JSON", "[]")
    with pytest.raises(ValueError, match="nonempty"):
        asyncio.run(main())
