# Rally Mission Control 0.3 — modules, genuine data and GPS map

**Design intent:** Move beyond a CRUD/test cockpit to a navigable control center that joins business intent, asset custody, exceptions, source coverage, and reported device positions.

## Navigation
- **Overview:** KPIs, five-stage execution lifecycle, unresolved conditions and source coverage.
- **Work orders:** Create work intent, review status, complete jobs. Source labels remain distinct from claims of field completion.
- **Equipment & custody:** Serialized asset register, free/assigned state, holder, handovers and returns.
- **Exception recovery:** Reconciliation outcomes, assignment/acknowledgment, notes and case history. Resolved cases remain read-only.
- **Evidence ledger:** Recorded observations, source, linked equipment and work orders. A manual QR event is not proof of optical scanning.
- **Fleet & GPS:** Tenant-specific last reported device locations; optional open map tiles. This is *historical/last-known*, **not** a Traccar WebSocket session.
- **Integrations:** Status from actual connector credentials and heartbeat coverage, with documentation for Odoo, Traccar and RFID.
- **Audit & access:** Existing audit and credential administration.

The business workflow is unchanged; existing API requests are reused. No new fictitious assets, GPS coordinates, ERP orders, or sensor evidence are generated.

## GPS architecture and integrity

Traccar can feed Rally using `python -m adapters.ingest_cli`, with `TRACCAR_DEVICE_ASSET_MAP` mapping Traccar numeric device IDs to Rally asset IDs. The ingestor persists normalized, idempotent GPS position observations in Rally's evidence ledger.

A new authenticated `GET /api/geo/positions` endpoint returns the **latest valid-coordinate recorded observation per source/device** within a bounded scan of the latest 1000 GPS evidence events, scoped to the requesting tenant. It includes event provenance, asset tag/name, fix time, location, and a quality label based on `valid=true` and the configured freshness threshold. If no events exist, Fleet & GPS displays an explicit no-data state. Source outage or stale fix is **not** represented as success.

Important: the endpoint's bounded scan makes it a preview read model, not a complete historical telemetry/GIS database. There is no automatic Odoo action based on GPS.

## Map/privacy and third-party code

- The local UI draws a simple coordinate overview using **only observed latitude and longitude**; it does not invent device positions.
- The optional street basemap uses **Leaflet 1.9.4**, SRI-pinned assets loaded on user action, and OpenStreetMap raster tiles with attribution. No Traccar UI source is copied.
- Public tiles are **disabled by default when `RALLY_ENV=production`**, and enabled by default in development. Set `RALLY_PUBLIC_MAP_TILES=on` deliberately after customer consent, map provider assessment and data/privacy review. No tile request is made until a user with actual positions explicitly selects "Show street map".
- For commercially hosted use, choose a tile provider with terms and SLA matching usage; OSMF's community tiles have a usage policy and no uptime guarantee. Never bulk download or proxy tiles without identification and caching compliance.
- Rally's application security sends `strict-origin-when-cross-origin` for web UI/static assets (needed for OSM map attribution/usage compliance); API replies retain `no-referrer`.
- A rendered map is **device-reported position**, not vehicle/technician identity verification, custody transfer, or proof of completed service.
- In a regulated environment, restrict who may view worker/device location and define lawful data retention before launch.

## Official references

- Traccar REST API: https://www.traccar.org/api-reference/
- Traccar WebSocket documentation: https://www.traccar.org/traccar-api/ — preferred for actual live updates; current Rally integration is periodic polling.
- Odoo 19 JSON-2 API: https://www.odoo.com/documentation/19.0/developer/reference/external_api.html — availability depends on deployment plan and model permissions.
- Leaflet quick start: https://leafletjs.com/examples/quick-start/
- Leaflet license: https://github.com/Leaflet/Leaflet/blob/main/LICENSE
- OSM tile policy: https://operations.osmfoundation.org/policies/tiles/

## Local review

1. Update the clone with `git pull --ff-only`; preserve `.env` and Docker volume.
2. Rebuild via `docker compose up --build -d`.
3. Load `http://localhost:8080`, authenticate with a current non-revoked personal tenant token.
4. Use the left navigation, confirm original assets/jobs/custody/history remain available.
5. In Fleet & GPS, with no configured device, verify the **No GPS positions yet** state—not fake map markers.
6. Connect a real Traccar instance separately using existing adapters and approved source credentials; reload positions.
7. Check reader roles still disable mutations and that state is isolated across tenants.

This implementation is a UI/UX and read-model milestone, not a certification of a production Odoo instance, physical device, or realtime tracking.