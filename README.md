# RALLY — Business Execution Assurance

**Know what's missing. Recover what failed. Verify what succeeded.**

Rally links work-order intent to equipment custody, immutable-by-API observations and recoverable operational exceptions. The executable scope is equipment custody and work-order assurance. GPS/RFID/QR observations never automatically authorize custody or certify completed work.

## Mission Control 0.3 — modular UI
A redesigned left-navigation workspace now separates overview, work orders, asset custody, exception recovery, evidence, Fleet & GPS, integrations, and audit/access. Fleet GPS uses tenant-scoped recorded Traccar/GPS observations only. There are no sample coordinates or simulated live vehicles. Optional public basemap tiles are disabled by default in production until explicitly approved.

See [Mission Control 0.3](docs/16-mission-control-ui.md) for UX architecture, official Traccar/Odoo/Leaflet references, data-quality semantics and local startup.

## Release 0.2

- PostgreSQL production persistence with versioned migrations, tenant foreign keys and transactionally serialized writes. SQLite remains available for local development.
- Individual bearer identities: administrator, operator, reviewer, viewer and source-scoped connector. Issuance, expiry, revocation and actor audit.
- Exclusive active custody, replay-safe handover/return, atomic job completion and concurrent-safe evidence deduplication.
- Periodic reconciliation worker; overdue and completed-job custody exceptions; ownership, notes and condition-based resolution.
- Mission Control with role-aware controls, in-memory credentials, paginated data, audit, recovery and connector coverage.
- Odoo confirmed-sale keyset import with explicit company scope; scheduled Odoo/Traccar polling with bounded retry; disk-spooled RFID edge ingestion.
- Production Compose: private PostgreSQL/API, Caddy TLS, non-root application, readiness, backup/restore and legacy data migration.

**Odoo import requires an explicitly configured work-order domain** and will not treat all confirmed sales as jobs. See the integration guide.

**Hardening after 0.2:** connector credentials can be scoped to one Odoo instance; imports cannot take over manual/legacy work orders; Traccar coverage checks data freshness and absent mapped devices. Database schema upgrades through version 6. See [post-0.2 review](docs/12-post-release-review.md) for upgrade actions and unverified risks.

**Delivery status:** source implementation and deployment configuration. This release was produced **without executing tests**, as requested. It is not a certification of a live production environment, hardware, load capacity or vendor compatibility. Review [the release record](docs/11-release-0.2.md) and [operations guide](docs/10-production-operations.md) before customer cutover.

## Production configuration gate

Before a real installation, load the approved production environment and run `python -m ops.preflight` (requires Python 3.11+). This rejects placeholders and unsafe deployment secrets but **does not replace live readiness, backups, privacy, or provider certification**. See `docs/10-production-operations.md` and [the production go/no-go gate](docs/13-production-readiness.md).

## Development

Python 3.11+ (container uses 3.12). Generate an administrator secret; do not commit it.

```bash
git clone https://github.com/em3rc0dTh/Rally.git
cd Rally
cp .env.example .env
# Create a unique local administrator secret. Do not commit .env.
python3 -c 'from pathlib import Path; import secrets; p=Path(".env"); s=p.read_text(); assert "RALLY_ADMIN_KEY=" in s; p.write_text(s.replace("RALLY_ADMIN_KEY=", "RALLY_ADMIN_KEY="+secrets.token_hex(32), 1))'
chmod 600 .env
docker compose up --build -d
docker compose ps
curl --fail-with-body http://127.0.0.1:8080/healthz
```

Open http://127.0.0.1:8080. The worker reconciles every 60 seconds. SQLite uses a named Docker volume. For existing MK0 `./data/rally.db`, follow the migration instructions; a new named volume does not automatically contain the old bind-mounted database.

Without Docker:

```bash
uv sync --frozen --no-dev
set -a; . ./.env; set +a
uv run --no-sync uvicorn rally.app:app --port 8080 --no-access-log
# Separate terminal with the same environment:
uv run --no-sync python -m rally.worker
```

Local API docs: `/docs`. Liveness: `/healthz`; database + worker readiness: `/readyz`.

### WSL / Windows troubleshooting

If Windows shows `ERR_CONNECTION_REFUSED` at `http://localhost:8080`, check `docker compose ps` and `docker compose logs --tail=80 rally` **inside WSL** first. A completed Docker image build is not evidence that the server is running. When `RALLY_ADMIN_KEY` is absent/blank, Rally refuses startup; the local Compose file now rejects blank values immediately, before creating containers.

If the containers are healthy, first confirm `curl -i http://127.0.0.1:8080/healthz` from WSL. The development stack publishes `127.0.0.1:8080:8080` on the Docker host. If WSL can reach that endpoint but the Windows browser cannot, verify Docker Desktop's WSL integration, Windows localhost forwarding and any proxy/firewall settings rather than changing the application's database or security configuration.

The container worker and API share the same .env. After changing the secret use `docker compose up -d --force-recreate`. Never copy test or example secrets into a customer deployment.


## Bootstrap

```bash
curl --fail-with-body http://127.0.0.1:8080/api/tenants \
  -H "X-Admin-Key: $RALLY_ADMIN_KEY" -H 'Content-Type: application/json' \
  -d '{"name":"Operations"}'
```

The bootstrap `curl` command uses your shell variable `$RALLY_ADMIN_KEY`. To load the same value saved in `.env`, first run `set -a; . ./.env; set +a` in the WSL terminal (do not echo or post the secret). Save the one-time `api_token`. Connect with it in Mission Control, create individual credentials in Access management, then revoke the bootstrap credential after creating another administrator. Use `Authorization: Bearer TOKEN` for API access. Custody commands also require `Idempotency-Key` (8–128 characters); preserve it after uncertain responses.

Create assets and work orders → issue equipment → record observations → complete work → inspect exceptions → return equipment → reconciliation verifies resolution. Acknowledging an exception assigns responsibility; it does not waive the discrepancy.

## Production deployment

```bash
cp .env.production.example .env.production
# Set RALLY_DOMAIN, ACME_EMAIL and two independent random hexadecimal secrets.
chmod 600 .env.production
docker compose --env-file .env.production -f compose.production.yaml up --build -d
```

Point the domain to the host and permit ports 80/443. PostgreSQL and the API have no public port mapping. Provisioning, secrets, backups and external integration credentials belong to the deployment operator. See the [complete runbook](docs/10-production-operations.md), including rollback and migration procedures.

## Documentation

| Document | Purpose |
| --- | --- |
| [Product vision](docs/00-product-vision.md) | Mission and business hypotheses |
| [Market study](docs/01-market-feasibility.md) | Original market research, not new validation |
| [Architecture](docs/02-architecture.md) | Runtime, transaction and recovery contract |
| [Open-source catalog](docs/03-open-source-catalog.md) | Adoption and provenance |
| [Odoo engineering audit](docs/04-odoo-engineering-audit.md) | Separate engineering foundation |
| [Roadmap](docs/05-roadmap.md) | Delivered scope and remaining product gates |
| [Security](docs/06-security-and-risks.md) | Permissions, boundaries and residual risks |
| [Integrations](docs/07-integration-guide.md) | Odoo, Traccar, RFID and optional Temporal |
| [Commercial validation](docs/08-commercial-validation.md) | Buyer validation and economics |
| [Executive summary](docs/09-resumen-ejecutivo-es.md) | Original Spanish product summary |
| [Operations](docs/10-production-operations.md) | Deployment, backup, restore and incidents |
| [Release record](docs/11-release-0.2.md) | Changes and exact verification limits |

`odoo-engineering` remains external: https://github.com/Em3rc0d/odoo-engineering. No third-party vendor tree is copied into Rally. Public availability does not grant a license to Rally-authored source; a commercial/public license and trademark clearance remain owner decisions.


## Release-candidate hardening

The pre-test production candidate separates the PostgreSQL bootstrap account from the `rally_app` runtime role, segregates proxy and database networks, binds custody return audits to the authenticated operator, and bounds the on-disk RFID event queue. These post-CI changes have **not been tested**, per the requested release workflow. See `docs/14-release-candidate.md` for the precise acceptance boundary.
