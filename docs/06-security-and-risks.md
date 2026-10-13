# Security model — 0.2

## Permission matrix

| Capability | Admin | Operator | Reviewer | Viewer | Connector |
| --- | --- | --- | --- | --- | --- |
| Read tenant operations/audit | Yes | Yes | Yes | Yes | No |
| Register assets/jobs; custody; completion | Yes | Yes | No | No | No |
| Manual / QR evidence | Yes | Yes | No | No | No |
| Reconcile, acknowledge, recovery notes | Yes | Yes | Yes | No | No |
| Issue / revoke credentials | Yes | No | No | No | No |
| Sensor evidence | No | No | No | No | Own source |
| Odoo job import | Yes | No | No | No | Odoo only |
| Connector heartbeat | No | No | No | No | Own identity |

Platform tenant provisioning uses a separate environment administrator key. Keep it off operator devices. Each human should have a named credential; shared keys defeat attribution. Random bearer keys are hashed with SHA-256, revealed once, optionally expire, and can be revoked. This is API-key authentication, not password authentication or an MFA/SSO implementation. Requests authorized before a concurrent revocation may finish; subsequent requests fail.

The last unexpired tenant administrator cannot be revoked until another exists. Administrators should overlap credentials during rotation. Expiring every administrator can still lock a tenant out; the deployment operator can recover access using `python -m rally.admin recover TENANT_ID NAME` with database access.

## Implemented controls

- Startup rejects weak/missing platform key, production SQLite and wildcard/missing production hosts.
- Database transaction locks, tenant constraints, replay protection and audit actor attribution.
- Body bound before JSON parsing (128 KiB default), evidence payload bound (64 KiB), future observation bound (5 minutes).
- IP rate limiting: 600 API requests/minute default, 10 tenant provisioning requests/minute; bounded in-memory buckets. This is per process, not a distributed DDoS defense. Upstream traffic controls are needed for replicas or hostile load.
- Production Compose exposes only Caddy 80/443; PostgreSQL/API remain private. Proxy headers are trusted only in this dedicated private stack. Do not publish the API container or attach untrusted workloads to its network.
- Host validation, no-store, CSP with external scripts, frame blocking and HTTPS HSTS. API docs are disabled in production.
- Cockpit credentials remain in memory; disconnect clears data and rejects stale session responses. Script injection still threatens any browser-held credential; use trusted operator devices.
- Client logs exclude tokens, bodies and provider error strings. Do not enable debug HTTP logging in customer environments.
- Container excludes `.env`, backups and local databases; application runs non-root/read-only.

## Evidence limits and privacy

A GPS device position does not locate a tool in a vehicle. RFID sightings do not authorize handover. QR can be copied. Manual customer acceptance is an attributed claim, not a cryptographic signature. Source-scoped bearer authentication is not hardware attestation or mTLS.

Audit is append-only by API; database administrators can modify it. Use least-privilege database access, encrypted storage/backups, access auditing and an external immutable sink if required by a customer. The bundled Compose database owner supports schema migration; a managed environment should separate migration privileges and runtime permissions.

No destructive automatic retention is enabled. Establish a customer-approved retention/export/deletion policy before collecting real location or employee data. Legal/privacy obligations, worker notices, contractual SLAs and trademark/licensing decisions require deployment-specific review. No country-wide compliance statement is implied.

## Delivery limits

Tests, fault injection, restore drills, live provider certification and load measurement were not executed for this release at the user's instruction. Code and deployment configuration alone cannot establish those outcomes. The repository does not contain production credentials or a public deployment.
