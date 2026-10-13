"""Read newline-delimited RFID JSON from stdin and ingest into Rally.

RALLY_URL, RALLY_TENANT_TOKEN and RFID_EPC_ASSET_MAP (JSON) are required.
Malformed and unmapped reads fail explicitly. No proprietary reader support.
"""
import json
import os
import sys
import httpx
from adapters.rfid import rfid_evidence

def main():
    required = ["RALLY_URL", "RALLY_TENANT_TOKEN", "RFID_EPC_ASSET_MAP"]
    if missing := [x for x in required if not os.getenv(x)]:
        raise RuntimeError("Missing configuration: " + ", ".join(missing))
    mapping = json.loads(os.environ["RFID_EPC_ASSET_MAP"])
    with httpx.Client(timeout=20.0) as client:
        for line in sys.stdin:
            if not line.strip():
                continue
            event = rfid_evidence(json.loads(line), mapping)
            response = client.post(
                os.environ["RALLY_URL"].rstrip("/") + "/api/evidence",
                headers={"Authorization": "Bearer " + os.environ["RALLY_TENANT_TOKEN"]},
                json=event,
            )
            response.raise_for_status()
            print(response.json()["id"])

if __name__ == "__main__":
    main()
