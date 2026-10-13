"""One-shot Traccar→Rally poller. Configured device mapping is mandatory.

Environment: TRACCAR_URL, TRACCAR_TOKEN, RALLY_URL, RALLY_TENANT_TOKEN,
TRACCAR_DEVICE_ASSET_MAP (JSON: {"123":"Rally asset UUID"}).
Run periodically only after validating real device data and access rights.
"""
import asyncio
import json
import os
import httpx
from adapters.traccar import Traccar, location_evidence

async def main():
    keys = ("TRACCAR_URL", "TRACCAR_TOKEN", "RALLY_URL", "RALLY_TENANT_TOKEN", "TRACCAR_DEVICE_ASSET_MAP")
    if missing := [x for x in keys if not os.getenv(x)]:
        raise RuntimeError("Missing configuration: " + ", ".join(missing))
    mapping = json.loads(os.environ["TRACCAR_DEVICE_ASSET_MAP"])
    traccar = Traccar(os.environ["TRACCAR_URL"], os.environ["TRACCAR_TOKEN"])
    positions = await traccar.positions()
    sent, ignored = 0, 0
    async with httpx.AsyncClient(timeout=20.0) as client:
        for pos in positions:
            asset_id = mapping.get(str(pos.get("deviceId")))
            if not asset_id:
                ignored += 1
                continue
            observation = location_evidence(pos, asset_id)
            reply = await client.post(
                os.environ["RALLY_URL"].rstrip("/") + "/api/evidence",
                headers={"Authorization": "Bearer " + os.environ["RALLY_TENANT_TOKEN"]},
                json=observation,
            )
            reply.raise_for_status()
            sent += 1
    print(json.dumps({"sent": sent, "unmapped_ignored": ignored}))

if __name__ == "__main__":
    asyncio.run(main())
