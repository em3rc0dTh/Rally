# Production operations runbook

## Scope and prerequisite

This runbook provisions the custody product on a dedicated Docker host. It is not a statement that this deployment has been executed. Tests and live deployment validation were intentionally not performed in the implementation session.

Use a dedicated domain and host with Docker Engine/Compose, persistent disk and managed access. Allow 80/443, restrict SSH, do not expose PostgreSQL. An initial 2-vCPU/4-GiB host is an allocation starting point, **not measured capacity or a cost estimate**. The shared write lock prioritizes consistency over telemetry throughput.

## Deploy

1. Clone this repository and select the reviewed release commit.
2. Copy `.env.production.example` to `.env.production`, permission 0600.
3. Generate independent 32-byte hexadecimal secrets for `POSTGRES_PASSWORD` and `RALLY_ADMIN_KEY`. Hex avoids special characters in the constructed database URL. Fill `RALLY_DOMAIN` and `ACME_EMAIL`; point DNS to the host.
4. Run `docker compose --env-file .env.production -f compose.production.yaml up --build -d`.
5. Caddy obtains TLS for the configured domain. API and worker apply versioned migrations under a database lock. PostgreSQL data and Caddy state use named volumes.
6. Provision a tenant at `https://DOMAIN/api/tenants` with the platform key; retain its one-time token. Create individual administrators/operators/reviewers and source-specific connectors in Mission Control. Rotate away the bootstrap token.

Do not attach untrusted workloads to the stack's private network. Proxy-header trust is broad inside this dedicated network because only Caddy exposes public traffic; if the topology changes, restrict trusted proxy addresses before exposing anything else. Caddy HTTP access logging is intentionally not enabled with real customer paths or data.

**Never use `docker compose down -v` on an installed system.** It deletes named volumes.

## Health and observability

- `/healthz`: API process liveness, not business readiness.
- `/readyz`: PostgreSQL access and successful reconciliation cycle within 180 seconds; 503 means investigate. A newly started stack may remain unready until its first worker cycle.
- `GET /api/connectors`: per-identity polling coverage; unknown before first success, stale after 300 seconds, degraded on reported errors. It does not prove fresh physical sensor readings.
- API logs: JSON request ID, method, path, status and duration; no bearer token or body. Request ID is also a response header.
- Worker logs: cycle completion or sanitized error type. Container log files rotate.

Configure external alerts for readiness, repeated 5xx/429, worker failures, stale/degraded connectors, host disk capacity, PostgreSQL volume growth and backup age. Docker health alone does not restart an unhealthy but running container. Choose an operator/supervisor escalation policy.

Migration v5 marks existing work orders as `manual` by default. For an MK0 or 0.2 database that has already imported Odoo references, **inspect each matching record and its provenance before explicitly changing its `source` to `odoo`**. The import endpoint returns 409 for legacy/manual records rather than silently taking them over. New imports require `odoo:INSTANCE:sale.order:POSITIVE_ID`; manual work orders cannot occupy that namespace. Keep `ODOO_INSTANCE` stable and limited to letters, digits, dot, underscore and dash. **Migration v6 scopes Odoo credentials:** existing Odoo connector tokens have no instance scope and must be replaced with a newly issued connector token specifying `scope=ODOO_INSTANCE`, then revoked. An unscoped Odoo connector will receive 403 for imports. The namespace in the imported work order must match its token scope exactly.

Traccar coverage now reports degraded when the provider returns no positions, when mapped positions are stale/invalid, or when devices are unmapped. `TRACCAR_MAX_POSITION_AGE_SECONDS` defaults to 300; polling health is not proof of physical execution.

The worker rereads durable business state after restart. No scheduler queue is lost; interrupted transactions roll back. Odoo polling performs a complete keyset traversal and Traccar replays current positions; neither mutates the ERP. RFID recovery uses its persistent spool.

## Connector services

Use one protected environment file per tenant/provider. Run `python -m adapters.runner` with a process supervisor. The application image includes adapters, so an alternative is a separate container with `--env-file`, `--restart unless-stopped` and command `python -m adapters.runner`. It needs network access to the HTTPS Rally/provider endpoints and no application database access.

RFID's `python -m adapters.rfid_ingest_cli` additionally needs a persistent writable spool directory owned by UID 10001 when using the image. Keep upstream input until acknowledged and use `--drain` after interruption. Do not share spool paths across tenants. Reader/edge hardware integration remains an external deployment component.

## Backup and restore

From repository root:

```bash
bash ops/backup.sh
```

This writes a PostgreSQL custom-format dump with permission restricted by umask and a SHA-256 sidecar. The script does not back up platform/provider secrets or TLS state; manage those separately in your secret store and host backup policy. Schedule the script in your infrastructure (for example daily), encrypt and copy backups off the host. Define retention and recovery objectives with the customer; do not infer guaranteed RPO/RTO from the script.

Restore into a **new empty** database:

```bash
bash ops/restore.sh backups/rally-TIMESTAMP-PID.dump rally_restore_20261013
```

The script verifies the archive checksum, creates the named database, and restores in one transaction. It refuses names outside `rally_restore_*` and does not overwrite production. After environment-specific review, stop API/worker writers and point **both** services at the restored database through an edited deployment configuration. Keep the previous database for rollback. A backup is not proven recoverable until the operator conducts a restore drill; none was executed in this session.

## Migrate MK0 SQLite

Stop all old writers. Create a consistent backup using SQLite's backup API while the source is stopped (include WAL state; do not copy only a live `.db` file). Work on a backup copy because the migration command upgrades that copy's schema.

```bash
# Environment: RALLY_DATABASE_URL points at a NEW PostgreSQL Rally database.
uv run --no-sync python -m rally.migrate_sqlite /absolute/path/to/rally-backup.db
```

The target must have no tenant data. The command installs schema, copies records in dependency order in a single target transaction and preserves legacy token hashes as revocable administrator identities. It prints counts, never tokens. PostgreSQL foreign keys reject inconsistent tenant relationships. It retains the source; any failed target transaction rolls back. A successful rerun against a populated target is rejected, preventing duplication.

If using the Docker image, mount the backup directory read-write and pass the production database environment to a one-off migration container; the migration needs to write schema changes to the backup copy. Keep API/worker stopped until the copy finishes.

Local development Compose now uses a named volume, unlike MK0's `./data` bind mount. To retain local data, stop the old process and explicitly import/copy a consistent upgraded backup into the named volume, with UID 10001 ownership, before starting the new containers.

## Release and rollback

Pin the application commit and build an image for that commit. `uv.lock` and `requirements.lock` pin Python dependencies with hashes; base container images use maintained major tags and should be promoted to approved immutable digests by deployment infrastructure.

Before upgrading, save a database backup and the running image digest. Migrations are additive but old application behavior may be incompatible. Roll back image **and, if needed, restore to a separate prior database**, then switch both API and worker together during a maintenance window. Do not downgrade schema in place or delete migration rows.

## Credential incidents

Use Access management to create a replacement token, distribute it securely, then revoke the old identity. An identity should identify a person or specific connector. Revoking a connector stops future ingestion; it does not erase historical evidence.

If every administrator is unavailable/expired, the deployment operator with direct DB access can run:

```bash
python -m rally.admin recover TENANT_UUID 'Replacement administrator'
```

It creates a named administrator, records a platform-recovery audit action and outputs its token once. Run in a private terminal with the application's database/environment settings. This is not a public password-reset endpoint. Rotate the platform key in deployment configuration if exposed; restart services.

## Operational boundaries

No destructive retention cron is provided: custody, idempotency and evidence history are business records. Define customer-approved archival/deletion rules first. The code does not claim SSO/MFA, immutable storage, managed HA/PITR, hardware attestation, commercial licensing or live integration certification.


### Field-service import selector

Before provisioning an Odoo connector, configure `ODOO_WORKORDER_DOMAIN_JSON` with the customer's agreed filter that identifies actual field-service orders. A confirmed sales order must not implicitly be treated as a physical work order. The new importer fails closed when no nonempty simple domain selector is supplied and rejects records outside `ODOO_COMPANY_IDS`. The example `x_rally_work_order` field is not an Odoo standard: implement or substitute an actual field in the customer's ERP and check domain permissions, multi-company separation and results before enabling supervised polling.


### Preflight obligatorio antes del primer despliegue

No se debe iniciar una instalación de clientes sin revisar configuración y procedimientos. Cargar las variables **sin imprimir secretos en logs** desde un entorno confiable y ejecutar `python -m ops.preflight`. El chequeo falla si la clave de plataforma o la contraseña PostgreSQL son inseguras, si el dominio/correo son de ejemplo, o si el URL de PostgreSQL opcional no coincide con la contraseña. Es una revisión **estática**: no prueba DNS, emisión ACME, base de datos, recuperación, backups ni conexiones externas. Después ejecutar el despliegue con la versión aprobada, verificar `/readyz`, ejecutar restauración de respaldo en una base separada y certificar proveedor Odoo/Traccar/RFID con datos controlados.

### Control de saturación de spool RFID

`RFID_MAX_SPOOL_EVENTS` limita la cola local a 100000 observaciones por defecto; al alcanzar el tope la ingestión deja de confirmar nuevas lecturas. Conservar los eventos pendientes, drenar/restaurar el enlace, ampliar almacenamiento con capacidad documentada y alertar al operador. No borrar la base del spool para recuperar espacio, porque se perderían observaciones aún no entregadas. Las lecturas anteriores al aviso deben contar con confirmación persistente en el dispositivo/edge.
