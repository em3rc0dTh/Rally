# Integration and operations guide

All examples refer to the standalone MK0 server. No provider live access or compatibility certification is claimed.

## API bootstrap

Run server per root README, then create tenant via admin-protected `POST /api/tenants`. Copy one-time token into tenant environment/secure vault. Tenant API supports Swagger at `/docs`. Token is never a tenant ID and cannot select another tenant.

## Odoo 19 read-only JSON-2 adapter

File: `adapters/odoo_json2.py`. Example:

~~~python
import asyncio
from adapters.odoo_json2 import OdooConfig, OdooJSON2

async def main():
    client = OdooJSON2(OdooConfig(
        base_url="https://YOUR-ODOO-DOMAIN",
        database="YOUR_DB",
        api_key="YOUR_RESTRICTED_ODDO_KEY",
    ))
    orders = await client.recent_sale_orders(limit=25)
    print(orders)

asyncio.run(main())
~~~

Use HTTPS and a narrowly restricted integration account. Validate Odoo external API availability for the actual deployment/plan. The adapter calls `/json/2/sale.order/search_read`. A **one-shot importer** maps up to 500 confirmed Odoo sales into Rally work-order intent, keyed as database + model + record ID. It does NOT provide continuous sync, full pagination or Odoo status updates:

~~~bash
export ODOO_URL=https://your-odoo-instance
export ODOO_DATABASE=your_database
export ODOO_API_KEY=YOUR_RESTRICTED_API_KEY
export RALLY_URL=http://127.0.0.1:8080
export RALLY_TENANT_TOKEN=YOUR_RALLY_TOKEN
python -m adapters.odoo_sync_cli
~~~

Use a controlled Odoo environment; real provider compatibility remains unverified.

Odoo JSON-2 documentation: https://www.odoo.com/documentation/19.0/developer/reference/external_api.html

## Traccar read-only polling into Rally

Files: `adapters/traccar.py`, `adapters/ingest_cli.py`.

Required environment:
- `TRACCAR_URL`: authenticated HTTPS server origin.
- `TRACCAR_TOKEN`: vendor token for allowed devices.
- `RALLY_URL`: local Rally API origin.
- `RALLY_TENANT_TOKEN`: tenant credential.
- `TRACCAR_DEVICE_ASSET_MAP`: JSON mapping external Traccar device IDs to existing Rally asset UUIDs.

~~~bash
export TRACCAR_URL=https://your-traccar-host
export TRACCAR_TOKEN=YOUR_TRACCAR_TOKEN
export RALLY_URL=http://127.0.0.1:8080
export RALLY_TENANT_TOKEN=YOUR_RALLY_TOKEN
export TRACCAR_DEVICE_ASSET_MAP='{"123":"ASSET_UUID_FROM_RALLY"}'
python -m adapters.ingest_cli
~~~

The command runs once; it does not install a daemon or Temporal schedule. It normalizes `/api/positions` responses, rejects out-of-range coordinates, and emits replay-safe source IDs. Confirm your server's authentication and position API semantics with the deployed Traccar version before use. No automatic work-order completion.

## RFID edge ingestion

File `adapters/rfid.py` accepts normalized LLRP/reader SDK observations. No physical reader/firmware is bundled. Set EPC-to-asset mapping explicitly.

~~~bash
export RALLY_URL=http://127.0.0.1:8080
export RALLY_TENANT_TOKEN=YOUR_RALLY_TOKEN
export RFID_EPC_ASSET_MAP='{"E200001122":"ASSET_UUID_FROM_RALLY"}'
echo '{"reader_id":"dock-01","epc":"E200001122","observed_at":"2026-10-13T15:00:00Z","rssi":-42}' \
 | python -m adapters.rfid_ingest_cli
~~~

Only an observation is recorded. Asset custody remains unchanged until authorized handover. In real hardware integration add edge signatures, retries, batching, device identity and EPC lifecycle controls.

## Temporal

Temporal workflow sample in `workflows/` is an **optional example of a durable human case review**, not automatically invoked by reconciliation. Temporal isn't necessary for MK0 to work. Do not let external retries mutate Odoo without idempotent business preconditions and independent verification.

## Production guidance

One instance, loopback-only Docker, no externally reachable port. If expanded: move data to PostgreSQL, add versioned migrations, outbox, ingestion worker, background replay, cloud TLS, scopes/RBAC, per-device auth, backups and explicit data retention.

### Optional Temporal case review commands

~~~bash
python -m pip install -e '.[temporal]'
# Start a compatible Temporal development server in another process.
export TEMPORAL_ADDRESS=localhost:7233
export RALLY_URL=http://127.0.0.1:8080
export RALLY_TENANT_TOKEN=YOUR_RALLY_TOKEN
python -m workflows.worker
# In another shell: start and signal an existing exception case
python -m workflows.start_review start CASE_UUID
python -m workflows.start_review approve CASE_UUID
~~~

This only performs a read-only case recheck following a human signal. It does not automatically recover or edit any ERP record.
