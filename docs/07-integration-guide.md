# Integrations — 0.2

Use a separate **connector** credential per tenant and provider. In Mission Control → Access management, choose role `connector` and a source (`odoo`, `traccar`, `rfid`, `gps`). Do not reuse the tenant administrator token. Secrets stay outside the repository.

Copy `.env.connector.example` to a protected deployment-specific environment file. Start the runner with that environment loaded:

```bash
set -a; . ./.env.connector; set +a
uv run --no-sync python -m adapters.runner
```

Use a process supervisor (systemd/container restart policy). `RALLY_CONNECTOR=odoo` or `traccar`; `RALLY_CONNECTOR_SECONDS=60` by default. Successful cycles send a heartbeat, failures report sanitized error classes. API 408/429/5xx and transport failures retry with bounded exponential delay. A later cycle replays idempotent imports. Authentication/schema failures are reported, not treated as successful delivery.

Endpoints require HTTPS outside localhost. `RALLY_ALLOW_INTERNAL_HTTP=1` is an explicit exception for a trusted private container network, never the public internet. Redirects are not followed with provider credentials.

## Odoo 19

Required: `ODOO_URL`, `ODOO_DATABASE`, `ODOO_API_KEY`, `ODOO_COMPANY_IDS` (comma-separated positive IDs), `RALLY_URL`, `RALLY_TENANT_TOKEN`. Optional stable `ODOO_INSTANCE` namespace defaults to the database name. Assign distinct namespaces for same-named databases on different servers. Do not change the namespace after importing.

The read-only JSON-2 adapter imports confirmed `sale.order` records in ascending-ID pages of 500. Every cycle traverses the full confirmed set, so later confirmations and changed titles are picked up. Explicit `company_id` domain limits business scope; upstream API rights must enforce the same scope. References are `odoo:INSTANCE:sale.order:ID`.

`POST /api/jobs/import` atomically upserts title by tenant/external reference. It does not reset locally completed jobs, mirror cancellations or automatically complete work. Deleted/unconfirmed source records are not automatically deleted from Rally. Sales intent is not physical execution proof.

One-shot operation: `python -m adapters.odoo_sync_cli`. Real Odoo edition, subscription/API eligibility, company permissions and response behavior remain deployment-specific.

Primary reference: https://www.odoo.com/documentation/19.0/developer/reference/external_api.html

## Traccar

Required: `TRACCAR_URL`, `TRACCAR_TOKEN`, `TRACCAR_DEVICE_ASSET_MAP` JSON mapping device IDs to Rally asset IDs, plus Rally URL/credential. `TRACCAR_INSTANCE` provides a stable namespace; default derives from server URL. Preserve it when migrating endpoints to avoid changed event identities.

One-shot: `python -m adapters.ingest_cli`. The runner polls current positions and ingests replay-safe observations. Unmapped devices produce degraded coverage, not silently complete coverage. This is not historical track backfill: events between polls may not be observed. Coordinates, fix time, validity and accuracy remain device claims. A successful empty poll proves API access, not physical reader/device activity.

## RFID edge spool

Provide `RFID_EPC_ASSET_MAP`, `RALLY_URL`, a source `rfid` credential, and persistent `RFID_SPOOL_PATH`. EPC keys are normalized to uppercase. The spool is tenant-bound to prevent accidental replay into another tenant. Reader ID scopes event identity. Input example:

```json
{"reader_id":"dock-01","epc":"E200001122","observed_at":"2026-10-13T15:00:00Z","event_id":"reader-seq-123","rssi":-42}
```

```bash
python -m adapters.rfid_ingest_cli < reader-events.ndjson
python -m adapters.rfid_ingest_cli --drain
```

An event is committed to disk before a `spooled` acknowledgment. It is deleted only after Rally accepts it. Delivery errors terminate the command and retain the queued event; supervise/restart and drain before resuming input. The upstream gateway must retain lines it has not seen acknowledged. Poison/conflicting events remain queued for operator intervention; do not silently discard them. `--drain` requires provider-independent Rally access to verify tenant binding. No LLRP/firmware driver is bundled.

## Coverage and recovery

`GET /api/connectors` shows never-seen, stale, degraded or current polling coverage. Heartbeat status is not proof of new physical observations. Use sensor timestamps/validity in the evidence ledger to assess actual observation quality.

Core exception recovery uses durable database state, ownership, notes and periodic reconciliation. It does not depend on Temporal. The `workflows/` directory remains an optional read-only human-review example; install `uv sync --extra temporal` to use it against your Temporal server. The example is not enabled or represented as production orchestration.
