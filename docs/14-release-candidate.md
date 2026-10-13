# Rally: Pre-test release candidate

Date: 2026-10-13. Scope: asset custody, work orders, reconciliation and source observations.
**Status: code candidate awaiting testing. Not production certified.**

## Implemented

Tenant-scoped API and roles; idempotent custody operations; evidence and audit records; reconciliation; Odoo JSON-2 confirmed work-order import with explicitly approved filters and ERP-instance credentials; Traccar freshness checks; RFID bounded spool; PostgreSQL schema 1–6; production-oriented Compose with Caddy; independent PostgreSQL runtime role; API/worker readiness and backups.

The most recent known green CI applied to commit `67f8ac1b4bc9eb02d0148833966226f474866d36`, **not the subsequent code commits**. All follow-up commits used `[skip ci]` by request. Do not claim that the current head was tested.

## Mandatory acceptance campaign — postponed until owner authorizes tests

1. Validate SQLite/PostgreSQL schema migrations 1–6 and new `rally_app` runtime role, including production startup rejection when using a DB superuser.
2. Build and launch disposable production-like Compose deployment with frontend/backend networks, Caddy TLS, readiness, API and worker.
3. Replay custody operations, concurrent issue attempts, restart-after-commit, tenant separation, revoked credentials, role permissions and authenticated return audit.
4. Check Odoo instance scope, explicit work-order filter, multiple companies, keyset iteration and conflicting/manual records against an authorized real Odoo environment.
5. Verify Traccar source timestamps, GPS validity, stale/no-data signals, lost connection and device mappings.
6. Validate RFID line size, disk/event spool limits, interruptions and replay; physical hardware only if included in the contracted SKU.
7. Demonstrate backup, restore to a separate PostgreSQL database and rollback; configure disk/alert/retention/incident response.
8. Obtain country-specific privacy review, license/trademark clearance and customer approval of the supported business workflow.

## Provisioning limitations

New production PostgreSQL volumes provision the non-superuser role with `ops/initdb/01-runtime-role.sh` and independent `RALLY_APP_PASSWORD`. Previous volumes do not run init scripts again: upgrade ownership under a separately reviewed data-migration plan, never delete the volume.

Three independent secrets are required: `POSTGRES_PASSWORD`, `RALLY_APP_PASSWORD`, `RALLY_ADMIN_KEY`. Use genuine `RALLY_DOMAIN` and `ACME_EMAIL`.

GPS is only reported device position, RFID is a sighting, QR is a scan claim, and authenticated return is an operator action—not customer acceptance. Temporal automatic business recovery, billing, SSO/MFA and external tamper-proof audit are outside this release.

**Go/no-go:** ready to begin the planned test campaign once frozen; NOT ready for customer production until the relevant tests, provider certification, recovery rehearsal and acceptance evidence succeed.
