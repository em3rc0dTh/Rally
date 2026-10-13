# Rally 0.2 — Post-release static review and hardening
Date: 2026-10-13. Source baseline: commit `68ebc5bbf38595efdd9e4a9554b2b0cbffd02f18`.

## Scope

GitHub `main` was inspected after the large production-oriented changes. That source includes PostgreSQL migrations, credential roles and revocation, a periodic reconciliation worker, GPS/Odoo connectors, RFID spool, non-root Docker image, Caddy TLS, and backup/restore scripts. **The review did not establish running production status**; the user requested no tests or live deployment.

## Resolved concerns

1. **Imported work-order ownership:** an Odoo connector previously accepted an arbitrary external reference and could rename an existing manual work order. Migration v5 introduces `jobs.source`. Manual creation reserves the `odoo:` prefix, and ERP upserts only modify rows explicitly owned by `odoo`.
2. **Odoo connector instance scope:** two Odoo connector credentials previously had the same tenant-wide import privileges. Migration v6 adds `credentials.scope`; the API requires a stable instance namespace and verifies it during import. Existing unscoped connector tokens cannot import until reissued.
3. **GPS freshness:** a successful HTTP request to Traccar was previously displayed as healthy even when the returned list was empty or contained stale positions. The Traccar poller now uses a configured max fix age (300 seconds by default), requires `valid=true`, and tracks missing mapped devices. The connector reports degraded rather than a misleading healthy status.
4. **Connector information boundary:** source-scoped connector tokens may access `/api/me` but cannot enumerate tenant connector identities via `GET /api/connectors`.

## Upgrade instructions

- Stop API, reconciliation worker, and Odoo connector writers for the schema upgrade; **back up PostgreSQL first** using the documented method. The startup schema migration is additive but not proven against a real live database.
- Apply schema migrations under the repository's transaction lock; versions 5 and 6 are installed after existing version 4.
- Review historical `odoo:...` jobs. Version 5 conservatively marks them manual. Only after evidence of legitimate source ownership should an operator update their `jobs.source` to `odoo`. Never mass-reclassify by string prefix alone.
- Issue a new Odoo connector credential with explicit `scope` matching `ODOO_INSTANCE` (or the normalized database name); rotate/revoke unscoped tokens.
- Configure `TRACCAR_MAX_POSITION_AGE_SECONDS` according to real GPS reporting interval; adjust by measured signal cadence, not optimistic assumptions.
- Restore / failback procedures remain exactly as documented in [production operations](10-production-operations.md).

## Outstanding risks

The shipped solution is **not production-certified**: no actual database migration rehearsal, no PostgreSQL failover, no Caddy/TLS/live deployment, no Odoo or Traccar provider verification, no physical RFID evidence, no Temporal business-recovery integration, no load test, no restore drill, no subscription metering and no external audit immutability verification.

The global PostgreSQL advisory transaction lock intentionally serializes mutations. This may become a throughput bottleneck and needs measurement before large multi-tenant deployments.

**Verification during this follow-up:** inspection of repository contents and updated source changes only. No tests, builds, migrations, external requests or customer environment execution were performed. Commits continue to use `[skip ci]` in accordance with the instruction not to run tests.

## Commercial go/no-go

Engineering maturity does not validate commercial demand. Rally still needs identified paying customers with demonstrable custody or field-service losses, ROI evidence and repeatable onboarding. Do not label this product a production SaaS until both technical certification and commercial feasibility have evidence.
