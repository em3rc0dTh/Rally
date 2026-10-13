"""Read-only Traccar adapter with normalized, replay-safe location observations.

GPS evidence proves only a device-reported position; it does NOT prove that a
job was performed or an asset was in a vehicle.
"""
from hashlib import sha256
from adapters.transport import validate_url, request
import httpx

def location_evidence(position: dict, asset_id: str) -> dict:
    required = ("deviceId", "fixTime", "latitude", "longitude")
    if any(position.get(k) is None for k in required):
        raise ValueError("Traccar position lacks required fields")
    latitude, longitude = float(position["latitude"]), float(position["longitude"])
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("GPS coordinate out of range")
    identity = ":".join(str(position[k]) for k in required)
    event_id = str(position.get("id") or sha256(identity.encode()).hexdigest())
    return {
        "asset_id": asset_id,
        "job_id": None,
        "source": "traccar",
        "source_event_id": event_id,
        "event_type": "gps_position_reported",
        "observed_at": position["fixTime"],
        "payload": {
            "device_id": position["deviceId"],
            "latitude": latitude,
            "longitude": longitude,
            "speed": position.get("speed"),
            "accuracy": position.get("accuracy"),
            "valid": position.get("valid"),
        },
    }

class Traccar:
    def __init__(self, base_url: str, bearer_token: str):
        validate_url(base_url)
        if not bearer_token:
            raise ValueError("Traccar token is required")
        self.base_url = base_url.rstrip("/")
        self.token = bearer_token

    async def positions(self, device_id: int | None = None) -> list[dict]:
        params = {"deviceId": device_id} if device_id is not None else {}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await request(client, "GET",
                self.base_url + "/api/positions",
                headers={"Authorization": "Bearer " + self.token},
                params=params,
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, list):
            raise ValueError("Unexpected Traccar positions response")
        return data
