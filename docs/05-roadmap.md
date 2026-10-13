# Roadmap — product gates, not feature wish list

## MK0 — Controlled executable demonstration (current)

**Implemented**: standalone Rally API, one-time tenant provisioning, bearer token tenant scope, work orders, physical assets, custody issue/return, idempotency, evidence observations, deterministic exception reconciliation, audit log, dark Mission Control UI, initial CI tests.

**Integration code added**: read-only Odoo JSON-2, Traccar position polling/normalization, RFID normalized-event CLI. These are **not certified against vendor live endpoints or devices**.

### MK0 acceptance

- Two tenants cannot read or mutate each other's assets/jobs/assignments.
- Only one active custody per asset.
- Same idempotency key/identical body cannot duplicate a physical handover.
- Completed job + outstanding custody creates an exception on reconciliation.
- Returning item + reconciliation resolves it without deleting history.
- RFID, GPS and QR observation alone do NOT alter custody.
- Tests/CI explicitly prove supported behaviors; passing tests is not a production guarantee.

## MK1 — Source truth and business-proof vertical slice

- Choose exactly **one** Odoo deployment/edition and service process.
- Define per-tenant Odoo database credentials/record mapping in secured storage.
- Read confirmed sales/tasks and reconcile against Rally work orders by stable external ID, including missed webhook recovery.
- Conduct Odoo 19 real install/integration with logs and constrained permissions.
- Integrate a **real** Traccar device or tenant with API access; record GPS signal quality/staleness.
- Add QR/mobile handovers with actor identity and auditable acknowledgment.
- Full exception ownership, comments, escalation and closure policy.
- Resolve the uncovered security and permission issues.

**Gate**: external events reproducibly correlated; no phantom closures; two independent customers can follow the same workflow.

## MK2 — Durable recovery and hardware evidence

- Add Temporal only for multi-step exceptional workflows, wait timers, retry/backoff, human approvals and verified closure.
- Introduce transactional outbox and worker acknowledgment; avoid double submission to Odoo.
- Connect one **licensed, physically verified** RFID reader/edge SDK.
- Manage EPC/asset mappings, antenna noise, duplicate scans, offline buffers and device provisioning.
- Separate telemetry storage from business/audit records.
- No custom GPS/RFID hardware until supplier integration proves insufficient.

**Gate**: fault-injected duplicated/missing events are detected; safe corrective actions have no unintended duplicate effects; measured coverage clearly reported.

## MK3 — Production readiness / commerce

- PostgreSQL migration with deterministic schema migrations and backup/restore.
- Strong RBAC with operator/admin/reviewer roles per tenant.
- Credential rotation and per-connector secrets, Webhook HMAC/mTLS, API rate limiting.
- Public TLS and authentication proxy; SSO if enterprise required.
- Observability, alerts, audit retention, immutable evidence controls, disaster recovery.
- Data privacy/security compliance by country, fleet worker monitoring policies, tenant contracts and SLAs.
- Billing, onboarding, self-service tenant admin, metering, usage support and playbooks.
- License/trademark clearance; commercial license/SBOM review.

**Gate**: production security and operations review; customer acceptance; paid pilot economics validate margins.

## Decision table

| Evidence | Decision |
| --- | --- |
| Customers already solve the problem sufficiently | Stop Rally product; no sunk-cost build |
| Each customer needs bespoke code | Sell professional services instead of SaaS |
| Repeatable problem but no paid commitments | Return to discovery |
| Three paid pilots and repeatable source mappings | Approve narrowly scoped product MVP |
| Device and support costs break gross margin | Re-scope or change buyer |

The milestone labels are proposals. MK1–MK3 are not delivered in this repository.
