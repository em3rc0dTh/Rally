"""One-shot Traccar→Rally poller. Configured device mapping is mandatory.

Environment: TRACCAR_URL, TRACCAR_TOKEN, RALLY_URL, RALLY_TENANT_TOKEN,
TRACCAR_DEVICE_ASSET_MAP (JSON: {"123":"Rally asset UUID"}).
Run periodically only after validating real device data and access rights.
"""
import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
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
    sent, ignored, stale, invalid = 0, 0, 0, 0
    seen_devices = set()
    max_age = max(30, int(os.getenv("TRACCAR_MAX_POSITION_AGE_SECONDS", "300")))
    current = datetime.now(timezone.utc)
    rally = RallyClient()
    instance = (os.getenv('TRACCAR_INSTANCE') or sha256(os.environ['TRACCAR_URL'].rstrip('/').encode()).hexdigest()[:16])
    for pos in positions:
        device_id = str(pos.get('deviceId'))
        asset_id = mapping.get(device_id)
        if not asset_id:
            ignored += 1
            continue
        seen_devices.add(device_id)
        try:
            fix = datetime.fromisoformat(str(pos["fixTime"]).replace("Z", "+00:00"))
            if fix.tzinfo is None:
                raise ValueError("Traccar fixTime must be timezone-aware")
            observation = location_evidence(pos, asset_id)
        except (KeyError, ValueError, TypeError):
            invalid += 1
            continue
        if fix > current + timedelta(minutes=5):
            invalid += 1
            continue
        observation['source_event_id'] = instance + ':' + observation['source_event_id']
        await rally.post('evidence', observation)
        sent += 1
        if pos.get('valid') is not True or current - fix > timedelta(seconds=max_age):
            stale += 1
    missing_devices = set(mapping) - seen_devices
    if sent == 0 or stale or ignored or invalid or missing_devices:
        await rally.heartbeat('error',
            f'Coverage unverified/degraded: sent={sent}; stale_or_unknown_fix={stale}; '
            f'unmapped={ignored}; malformed={invalid}; mapped_devices_absent={len(missing_devices)}; '
            f'returned={len(positions)}')
    else:
        await rally.heartbeat('ok',
            f'Fresh device positions delivered: {sent}; returned={len(positions)}')

    print(json.dumps({"sent": sent, "unmapped_ignored": ignored,
                      "stale_or_unknown_fix": stale, "malformed": invalid,
                      "mapped_devices_absent": len(missing_devices),
                      "provider_returned": len(positions)}))

if __name__ == "__main__":
    asyncio.run(main())
