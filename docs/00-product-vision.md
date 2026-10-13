# Rally — Product Thesis

Date: 2026-10-13. MK0 code implements only a subset of this strategy.

## Core mission

**Rally connects what a business promised, what its ERP recorded, and what happened in physical operations. It detects missing evidence and inconsistencies, then helps people reach a verifiable resolution.**

Business systems record intent and transactions; sensors supply observations; humans confirm responsibility; Rally evaluates whether the desired outcome has credible evidence.

A product has value only if a real buyer will pay to remove a real and repeatable pain. Temporal, Odoo, QR, RFID and GPS are implementation ingredients, not value propositions.

## Product options from the same source repository

| Candidate | Paid problem hypothesis | Repo leverage | Why it might fail |
| --- | --- | --- | --- |
| **Rally Custody (MK0)** | Who has each high-value asset, for what job, and why is it not returned? | Physical copy/loan integrity in `oe_library` | Cheqroom and Odoo can already cover portions of custody |
| **Rally Job Assurance** | Can a field contractor prove execution and close work orders without unbilled exceptions? | `oe_sale_task_bridge`, `oe_crm_task_bridge` | Odoo Field Service and delivery/FSM competitors |
| **Rally Fabrication** | Accurate dimension-based quotes, purchasing, waste and gross margin | `oe_workshop_quote`, `oe_purchase_board` | Specialized cutting/MRP vendors and Odoo stock |
| **Rally Transaction Assurance** | Detect orders/payments missing or stuck across systems | Data adapters + new reconciliation | Pipe17, Celigo and Odoo existing tools |

No customer contracts, willingness-to-pay evidence or unit economics have been demonstrated for these hypotheses.

## Initial ideal customer (hypothesis)

Industrial or technical services contractor; 20–500+ high-value movable assets, multiple technicians/vehicles/sites, Odoo or another ERP used for work records, recurring manual reconciliation. Economic buyer: Head of Operations, CFO, or owner personally exposed to equipment replacement costs and unbilled jobs.

## Fundamental evidence contract

1. **Obligation** — sale/work order/asset return due.
2. **Observation** — a tag scan, geofence event, log or user claim.
3. **Authorization** — accountable handover or explicit customer acceptance.
4. **Comparison** — expected vs actual with source traceability and stale/unknown quality.
5. **Outcome** — objectively resolved, unresolved, or awaiting approval.

A GPS ping may associate a vehicle with a site; it cannot confirm that a technician completed the job or that a particular tool was on board. RFID alone proves a reader reported an identifier, not transfer of legal custody.

## Scope discipline

MK0: assets, work orders, unique active custody, audit events, normalized evidence, operator cockpit, automated reconciliation and review queue.

Later: ERP-to-Rally intent synchronization; geofence correlation; RFID edge gateways; mobile signed handovers; durable Temporal recovery; paid multi-company SaaS controls.

Deliberately excluded: proprietary GPS trackers, RFID hardware manufacturing, payment execution, country-specific fiscal engines, ERP replacement and generic CRM.
