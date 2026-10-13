# Rally contributor / agent instructions

Read README and docs before implementing or claiming product maturity.

- Mission: verified business execution assurance. Initial vertical: equipment custody linked to work orders.
- No copying whole upstream GitHub repositories without license and provenance review.
- Keep ``odoo-engineering`` external; do not move its vendor tree into Rally.
- Treat GPS/RFID/QR as **observations**, not conclusive work completion or custody authorization.
- Changes touching custody must preserve tenant isolation, idempotency and one-active-assignment invariant.
- Reconciliation must be deterministic and never silently close unresolved exceptions.
- Temporal is for durable exceptional workflows; not raw sensor ingestion.
- Odoo writes, billing, privacy compliance, trademark status and production certifications are not implied.
- Never claim live integration proof without corresponding logs/fixtures and an actual environment.
- Run CI after code changes and preserve status in change reports.
- Do not commit API tokens, Odoo passwords, GPS credentials, customer PII or real location traces.
- Any production deploy requires separate security and privacy gate.
