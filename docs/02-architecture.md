# Technical Architecture & Reliability Contract

## Logical system

~~~mermaid
flowchart TD
 O[Odoo ERP: work intent] --> OA[Odoo read-only adapter]
 T[Traccar: device position] --> TA[GPS normalizer]
 R[RFID readers via edge gateway] --> RA[RFID normalizer]
 Q[QR/operator claims] --> API[Rally tenant API]
 OA --> API
 TA --> API
 RA --> API
 API --> DB[(Rally tenant state / evidence / audit)]
 DB --> RECON[Deterministic reconciliation]
 RECON --> CASE[Exception queue]
 CASE --> UI[Mission Control]
 CASE -. future .-> TEMP[Temporal review / recovery]
~~~

Odoo, Traccar, and RFID clients currently exist as **separate read/normalization code**; they are not scheduled, provisioned, or commercially certified. Temporal is not wired to the Rally API.

## Invariants currently implemented in MK0

- API bearer token resolves exactly one tenant. Cross-tenant IDs for assets, jobs and custody are rejected.
- Asset tags and job external references are unique **per tenant**.
- Only **one active custody assignment for each asset**; SQL partial unique index plus SQLite `BEGIN IMMEDIATE` for issue/return operations.
- Custody-changing commands must supply an idempotency key; same key+same payload is safe to replay, different payload conflicts.
- Physical observations do not close work orders or transition custody automatically.
- Evidence uses source + source_event_id deduplication with conflicting duplicate rejection.
- Reconciliation fingerprints deterministic conditions: overdue returns, and completed jobs with active equipment custody.
- Exception closure requires that business state no longer violates the rule, then a new reconciliation scan.
- Audit records are append-only via current API, **not tamper-proof against database administrators**.

## Example

~~~mermaid
sequenceDiagram
 participant User
 participant API
 participant DB
 User->>API: Create work order + register asset
 User->>API: Issue asset (Idempotency-Key)
 API->>DB: Assert tenant, state, exclusive active custody
 DB-->>API: assignment + audit
 User->>API: Complete work order
 User->>API: Run reconcile
 API->>DB: Compare completed work to active custody
 DB-->>User: Open exception
 User->>API: Confirm return
 User->>API: Reconcile again
 DB-->>User: Condition resolved, audit history retained
~~~

## Why Temporal is optional, not central

Temporal supports durable exceptional workflows: multi-step retries, approvals, long timers, and post-action verification. It does not independently detect missing source events or guarantee exactly-once external effects. We should not schedule one workflow for each GPS ping or RFID read. Use a streaming/edge normalization boundary first; trigger Temporal only for expensive exceptions that need intervention.

## Target integrations

**Odoo**: JSON-2 external API, explicit per-database tenant mapping, stable record IDs, scoped read rights. Odoo deployment/subscription eligibility must be checked. Never automatically mutate invoices, orders, stock, or payments as an unverified retry.

**Traccar**: fetch device positions and map device IDs to Rally asset IDs explicitly. This is a reported vehicle/device position, not proof a technician worked.

**RFID**: edge LLRP/SDK reader emits reader ID, EPC, timestamp, signal and event ID. Map EPC explicitly, deduplicate; reader sightings are not custody authority.

## Scalability gate

MK0 SQLite is a local single-instance database, not multi-region HA. A production service should move to PostgreSQL with migrations, tenant-scoped roles, ingestion queues/outbox, retention controls, backups/restore, end-to-end tracing and dedicated time-series ingestion if needed.

Odoo engineering source: https://github.com/Em3rc0d/odoo-engineering
