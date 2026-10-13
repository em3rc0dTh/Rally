# Security, evidence quality and commercial safety

## Current MK0 security model

- Admin bootstrap protected by `X-Admin-Key` environment secret, minimum 32 characters; absence/weakness blocks bootstrap.
- Generated tenant API tokens are returned only at creation; SHA-256 hashes persist in database.
- Every tenant route resolves tenant identity from its bearer token. Cross-tenant entity IDs are checked before business mutations.
- SQLite uniqueness and `BEGIN IMMEDIATE` protect active custody and replay handling on a single local instance.
- Repository/CI contains no real Odoo, GPS or customer credentials.
- Browser token is kept in sessionStorage for the current browser tab; this is a tradeoff for pilot convenience, not an enterprise credential design.

## Known blockers to public SaaS deployment

1. One bearer token represents the entire tenant; no per-user RBAC, scoped connector identity or token rotation.
2. No rate limiting, admin key rotation endpoint, MFA or API key issuance governance.
3. SQLite single-node file without PostgreSQL migrations, point-in-time recovery, encryption-at-rest management, WAL/backups/restore validation.
4. API accepts self-reported event sources: a client can declare `source=rfid` or `gps`, not secure device attestation. This is **unverified observation**.
5. Audit events are append-only by API convention but a DB administrator can alter them. No append-only external audit sink or signatures.
6. No automatic sensor evidence integrity, secure GPS device certificates, geofence trust model or timestamp-skew policy.
7. No on-device identity, independent reviewer signoff, customer signature capture or role-based closure approval.
8. No continuous connector retries, dead-letter queue, provider rate-limit observability, credential vault, replay retention or event ingestion backpressure.
9. No personal data retention/deletion workflows, privacy impact analysis or per-country fleet worker consent/employment review.
10. No public HTTPS deployment config, firewall policy, infrastructure backup or tested incident response.
11. External API access to Odoo depends on edition/plan/deployment; secrets must never be embedded in source.
12. No seller/subscription entitlement checks or contractual warranty.

**Do not publicly deploy with real customer data until the security and licensing gates are closed.**

## Security model for sensors

GPS: device positions are location observations, not technician work acceptance. Accuracy, fix timestamp, spoofing, outage and stale quality matter. Vehicle position does not prove attached tool location.

RFID: a tag seen by an antenna may reflect nearby objects, duplicated reads, wrong EPC mapping or replay. Require verified edge ownership, anti-replay and documented operating procedure.

QR: easy to copy and manually submit; a signed handover with accountable actor is stronger than a raw scan.

Odoo: avoid automatic writes in MK0, especially stock transfers, invoices, payments or tax documents. Temporal's retries do not guarantee exactly-once external side effects. Always check external state before retrying.

## Operational privacy

Peru, Chile, Bolivia, Ecuador, Argentina and Brazil each have different privacy, employment, surveillance and retention requirements. Review the applicable framework (including Brazil LGPD where relevant) before enabling vehicle/employee location tracking. No blanket compliance claim is made.

## Commercial risk

Do not promise that Rally prevents all theft, guarantees every order is accounted for, or detects events from a source that cannot provide reliable independent queries. Source outage must appear as **unknown coverage**, not as evidence that nothing failed.
