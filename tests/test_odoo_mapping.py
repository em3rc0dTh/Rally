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
