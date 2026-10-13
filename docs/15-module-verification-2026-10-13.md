# Rally — Module-by-module validation report

**Date:** 2026-10-13  
**Exact code revision validated:** `94e1c7899a06dc7a13751bea4afa8762dd009a08`  
**GitHub Actions:** https://github.com/em3rc0dTh/Rally/actions/runs/38436825875  
**Result:** **PASS — 34 automated tests, one non-fatal Python dependency deprecation warning**. All configured CI steps, including an isolated production-profile backup/restore drill, concluded successfully.

## Test environment and scope

- GitHub Actions Ubuntu runner, Python 3.12, Node.js for JavaScript syntax check.
- Disposable SQLite databases and real PostgreSQL 17 databases for relational integration tests.
- Isolated Docker Compose containers for local and production-profile services.
- Caddy configuration validated **without public HTTPS or ACME certificate issuance**.
- Odoo/Traccar provider APIs are replaced with deterministic in-process fakes. No live provider credentials or customer systems touched.
- RFID gateway uses simulated normalized JSON reads; no physical reader connected.
- Temporal workflow **read-only activity** is tested through a mocked Rally HTTP endpoint; no Temporal server started.
- All temporary CI databases and containers are cleaned up.

## Per-module results

| Module | Validation | Outcome | Limitation |
| --- | --- | --- | --- |
| Tenant bootstrap / authorization | Tenant isolation, bearer authentication, source-scoped connector roles, admin/operator/reviewer/viewer rights, credential revocation | **PASS** | Real IAM/SSO integration not tested |
| Asset catalog and work orders | Create/read constraints, unique references, Odoo-reserved namespace protection | **PASS** | Real Odoo state mapping requires live integration |
| Custody | Exclusive active custody, idempotent issue/return, audited authenticated actor, replay and conflicting payloads | **PASS** | Concurrent high-volume load not yet benchmarked |
| Reconciliation / cases | Completed work order + active custody raises exception; owner, acknowledgment, notes, authoritative resolution | **PASS** | Real customer acceptance not performed |
| Evidence ledger | Source restrictions, tenant isolation, duplicate event handling and unsupported sensors | **PASS** | Device-origin signatures/attestation not available |
| SQLite | Isolated local CRUD and state machine contracts | **PASS** | Not the planned multi-instance production store |
| PostgreSQL | Actual database migrations 1–6, composite tenant foreign keys, custody uniqueness, transaction contracts | **PASS** | Real customer data migrations and load not certified |
| Legacy data migration | Offline SQLite → empty PostgreSQL copy, preserve source, reject repeated import | **PASS** | Customer-size migration dry run still needed |
| Odoo JSON-2 / source mapping | Stable order references, explicit work-order selector, company allowlist, import scopes, mocked paginated provider | **PASS (simulated)** | **No real Odoo account/edition/API certification** |
| GPS / Traccar | Event normalization, unique origin, fresh/stale/no-data coverage, mocked device telemetry | **PASS (simulated)** | **No real device or Traccar deployment** |
| RFID / edge spool | EPC mapping, durable SQLite spool, simulated upstream outage/replay, oversized input rejection | **PASS (simulated)** | **No real RFID reader** |
| Periodic worker / readiness | Reconciliation worker lifecycle and readiness transition; disposable Docker API+worker boot | **PASS** | Production monitoring alert routing not proven |
| Temporal | SDK import and read-only case activity against mocked API | **PASS (limited)** | **No real Temporal server/workflow execution; automatic recovery out of scope** |
| Cockpit | HTML/static JS served, CSP and basic security headers, JavaScript syntax validation | **PASS (technical)** | Browser UI/E2E accessibility tests not performed |
| HTTP/host guard | Oversized request rejection, invalid fields, untrusted Host, security headers | **PASS** | Independent security penetration test pending |
| Administrator recovery | Recovery generates a named credential and audit entry without leaking token into audit | **PASS** | Recovery playbook with real operations team pending |
| Deployment/Compose | Image build, Compose config and isolated startup with restricted `rally_app` role | **PASS** | Customer DNS/public TLS/infra unavailable |
| Caddy | Production Caddyfile parsed and validated in disposable container | **PASS** | Public ACME/TLS handshake not performed |
| Backup / restore | Real `pg_dump`, checksum verification, separate restore database, restored asset verified | **PASS** | Scheduled encrypted off-host backup and recovery targets not tested |

## Observed findings corrected during campaign

1. Historical tests still used arbitrary return confirmation names, despite the new authenticated-actor requirement. Updated fixtures.
2. Test-suite rate limiter was process-global and persisted across disposable database fixtures, leading to HTTP 429. Fixed test isolation, retaining the production rate limiter.
3. A new assertion incorrectly assumed a fixed position in a jobs list. Asserted by stable external reference.
4. Temporary Docker test project name was malformed. Replaced with an allowed project identifier.
5. PostgreSQL fixture was only visible to the test module that originally declared it; exposed it to the legacy-migration module through `tests/conftest.py`.
6. Caddy emits a **cosmetic Caddyfile formatting warning** but its configuration validates successfully.
7. Python emits a **non-fatal Starlette/httpx deprecation warning**; watch for dependency updates.

## Current disposition

**Engineering verification:** GO for staging and a controlled pilot acceptance test, with the exact validated commit pinned.  
**Customer production:** NOT CERTIFIED. Live Odoo, Traccar, RFID, public TLS, country-specific privacy, operator runbooks and customer acceptance still require their own evidence.  
**Commercial positioning:** Do not advertise GPS/RFID/Temporal auto-recovery as end-to-end certified capabilities.

This report commits test evidence only. A documentation-only HEAD ahead of the validated SHA does not make the earlier checks applicable to any future code changes.
