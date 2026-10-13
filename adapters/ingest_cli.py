"""One-shot Traccar→Rally poller. Configured device mapping is mandatory.

Environment: TRACCAR_URL, TRACCAR_TOKEN, RALLY_URL, RALLY_TENANT_TOKEN,
TRACCAR_DEVICE_ASSET_MAP (JSON: {"123":"Rally asset UUID"}).
Run periodically only after validating real device data and access rights.
"""
import asyncio
import json
import os
from adapters.transport import RallyClient
from hashlib import sha256
from adapters.traccar import Traccar, location_evidence

async def main():
    keys = ("TRACCAR_URL", "TRACCAR_TOKEN", "RALLY_URL", "RALLY_TENANT_TOKEN", "TRACCAR_DEVICE_ASSET_MAP")
    if missing := [x for x in keys if not os.getenv(x)]:
        raise RuntimeError("Missing configuration: " + ", ".join(missing))
    mapping = json.loads(os.environ["TRACCAR_DEVICE_ASSET_MAP"])
    traccar = Traccar(os.environ["TRACCAR_URL"], os.environ["TRACCAR_TOKEN"])
    positions = await traccar.positions()
    sent, ignored = 0, 0
    rally = RallyClient()
    instance = (os.getenv('TRACCAR_INSTANCE') or sha256(os.environ['TRACCAR_URL'].rstrip('/').encode()).hexdigest()[:16])
    for pos in positions:
        asset_id = mapping.get(str(pos.get('deviceId')))
        if not asset_id:
            ignored += 1
            continue
        observation = location_evidence(pos, asset_id)
        observation['source_event_id'] = instance + ':' + observation['source_event_id']
        await rally.post('evidence', observation)
        sent += 1
    if ignored:
        await rally.heartbeat('error', f'Partial coverage: {ignored} unmapped devices; {sent} imported')
    else:
        await rally.heartbeat('ok', f'Positions imported: {sent}; provider returned: {len(positions)}')

    print(json.dumps({"sent": sent, "unmapped_ignored": ignored}))

if __name__ == "__main__":
    asyncio.run(main())
