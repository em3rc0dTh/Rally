# Delivery scope and remaining gates

## Implemented in 0.2

Custody/work-order/evidence API; PostgreSQL migrations; per-identity roles, expiry and revocation; actor audit; periodic deterministic reconciliation; exception assignment/notes; source-scoped credentials and coverage; role-aware Mission Control; paginated Odoo sales import with company scope; supervised Odoo/Traccar polling; RFID durable local delivery spool; HTTPS deployment configuration; backup/restore and MK0 data migration commands.

Implementation does not mean production certification. This release deliberately ran no tests. See the [release record](11-release-0.2.md).

## Deployment-specific completion

- Provision host, DNS, secrets and production PostgreSQL storage.
- Configure actual Odoo database/company scope, Traccar device mapping and RFID edge source.
- Establish backups outside the host, retention, monitoring and incident ownership.
- Validate deployment and provider behavior in the real environment before customer cutover.

These cannot be completed from source code without a target environment and credentials. No live deployment or vendor access is fabricated.

## Product expansion (outside the custody release)

- Enterprise SSO/MFA and stronger signed handover/customer acceptance.
- Multi-step Temporal recovery with externally authorized business side effects.
- Physical RFID reader drivers/attestation, historical GPS backfill, broader ERP models.
- Immutable external audit storage, managed HA/PITR, formal retention workflows.
- Subscription billing, paid pilot economics and commercial/trademark/license decisions.
- Fabrication quoting and other vertical hypotheses remain separate product work.

The immediate product remains custody assurance linked to work orders. It does not implement the entire original platform vision or certify that customers will pay for it.
