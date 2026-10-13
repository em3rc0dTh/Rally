# Rally 0.2 — implementation delivery record

Date: 2026-10-13. Baseline: `dc96c60f071dbc60bf2fcbcefca1464a1af4d48d`.

## Delivered changes

- PostgreSQL persistence, ordered additive schema migration, database tenant constraints and explicit write transactions; SQLite local support and offline transfer command.
- Named credential roles, per-source integration tokens, expiry, revocation, last-administrator protection and audited deployment-operator recovery.
- Atomic completion and reconciliation; race-safe evidence replay; custody audit attributed to the authenticated credential.
- Durable reconciliation worker, readiness signal, exception acknowledgment/ownership/notes and verified condition-based resolution.
- Packaged Mission Control, memory-only tokens, clearing on disconnect, role-aware forms, preserved uncertain-request idempotency keys, record pagination, coverage, access administration and audit visibility.
- Odoo company-scoped full keyset sales imports and idempotent title upserts; Traccar namespaces and partial-mapping reporting; bounded HTTP retry; supervised polling and persistent RFID delivery spool.
- Non-root image, locked Python dependencies/hashes, production PostgreSQL + Caddy configuration, backup/restore scripts and operational documentation.

No third-party upstream application was copied into the repository. Earlier market, product vision and commercial research remain historical inputs, not newly validated market claims.

## Verification performed

- Python syntax compilation for application, adapters and optional workflows.
- JavaScript syntax check and shell syntax checks.
- Git diff whitespace/conflict review.
- Python dependency resolution and hash lock export.
- Python source distribution and wheel construction, including cockpit assets and adapters.
- Static source review of transaction boundaries, roles, tenant predicates, credential handling and migration order.

**No unit, integration, end-to-end, load, fault-injection or live-provider tests were executed.** Existing RFID test setup was aligned with source-scoped credentials without executing it. The existing CI workflow is retained; this delivery commit uses `[skip ci]` to honor the explicit instruction not to run tests. There is no green CI claim for this release.

Docker is not available in the implementation environment, so the container build and production Compose stack were not run. No production database was created, no real customer data was migrated, and no external DNS or provider credentials were used. No restore drill or operational capacity claim is made.

## Upgrade notes

- Existing tenant bearer keys become revocable bootstrap administrator identities; per-person keys should replace them.
- Sensor sources now require source-scoped connector credentials. Former tenant-token RFID/GPS calls will receive 403.
- Browser credentials are no longer retained across reloads. The cockpit removes the old sessionStorage entry.
- Lists default to 200, capped at 500, with offset pagination. Integrations must not assume an unbounded response.
- Odoo requires explicit `ODOO_COMPANY_IDS`; instance namespace defaults to the existing database reference scheme.
- Traccar/RFID IDs now include server/reader identity. Re-ingesting observations already recorded by MK0 may produce a second legacy/new identity pair. This does not change custody, but review the ingestion cutoff when migrating historical evidence.
- Static cockpit files moved into `rally/web/` so wheels and containers include them.
- Development Compose changes from a bind-mounted `./data` to a named volume; follow the runbook to preserve an existing database.
- PostgreSQL schema version 4 is reserved for compound tenant foreign keys; future migrations must continue after it for both backends.

## Remaining external decisions

Provision and validate a real environment, provider accounts/mappings, off-host backup policy and operator monitoring. SSO/MFA, enterprise HA/PITR, physical device attestation, billing, arbitrary ERP writes, immutable external audit, formal retention and commercial/legal clearance are outside this custody implementation. Optional Temporal is explicitly a read-only example, not hidden unfinished core recovery.

**Release classification:** implemented source and deployable configuration, reviewed statically and packaged; not production-certified through execution.


## Subsequent corrective follow-up

Later commits after the original delivery tightened import ownership, per-instance Odoo connector permissions and Traccar evidence freshness. The historical verification claims above apply only to the original 0.2 commit; the follow-up was reviewed statically without executing tests. See [post-release review](12-post-release-review.md) for upgrade requirements and known gaps.
