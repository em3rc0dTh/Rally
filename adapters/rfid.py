"""Normalize events from upstream RFID edge gateways.

This is NOT an LLRP reader driver. RFID sightings remain observations and never
automatically change custody or confirm work-order completion.
"""
from hashlib import sha256

def rfid_evidence(read: dict, epc_to_asset: dict[str, str]) -> dict:
    reader = str(read.get("reader_id", "")).strip()
    epc = str(read.get("epc", "")).strip().upper()
    when = str(read.get("observed_at", "")).strip()
    if not (reader and epc and when):
        raise ValueError("RFID event needs reader_id, epc and observed_at")
    asset_id = epc_to_asset.get(epc)
    if not asset_id:
        raise ValueError("Unmapped EPC; do not create an unidentified asset implicitly")
    event_id = str(read.get("event_id") or sha256((reader+":"+epc+":"+when).encode()).hexdigest())
    return {
        "source": "rfid",
        "source_event_id": sha256((reader + ":" + event_id).encode()).hexdigest(),
        "event_type": "rfid_observed",
        "asset_id": asset_id,
        "job_id": None,
        "observed_at": when,
        "payload": {
            "reader_id": reader,
            "epc": epc,
            "rssi": read.get("rssi"),
            "antenna": read.get("antenna"),
            "observation_only": True,
        },
    }
