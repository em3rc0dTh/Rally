import pytest
from adapters.traccar import location_evidence
from adapters.rfid import rfid_evidence
from adapters.odoo_json2 import OdooConfig

def test_traccar_repeat_identity_stable():
    position = {"deviceId": 12, "fixTime": "2026-10-13T12:00:00Z",
                "latitude": -12.04, "longitude": -77.03, "speed": 10}
    a = location_evidence(position, "uuid-1")
    b = location_evidence(position, "uuid-1")
    assert a == b and a["source"] == "traccar"
    with pytest.raises(ValueError):
        location_evidence({**position, "latitude": 200}, "uuid-1")

def test_rfid_requires_explicit_mapping():
    item = {"reader_id": "gate-1", "epc": "AAA12", "observed_at": "2026-10-13T12:00:00Z"}
    with pytest.raises(ValueError):
        rfid_evidence(item, {})
    assert rfid_evidence(item, {"AAA12": "asset-uuid"})["asset_id"] == "asset-uuid"

def test_odoo_blocks_insecure_public_url():
    with pytest.raises(ValueError):
        OdooConfig("http://odoo.example.com", "db", "key").validate()
