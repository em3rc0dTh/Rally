# Odoo enterprise multi-domain bridge — executable, opt-in

**Status:** Rally provides a local and Docker-ready read-only JSON-2 importer, strict per-tenant/instance/company/model grants, a version-7 schema and an admin-only summary. **This does not mean any Odoo customer system has been contacted.** No API key is required to build or deploy this code.

## Supported contracts, not installed-module claims

| Logical domain | Model | Source state derived from |
| --- | --- | --- |
| CRM | `crm.lead` | `stage_id` (numeric stage only) |
| Sales | `sale.order` | `state` |
| Procurement | `purchase.order` | `state` |
| Inventory flows | `stock.picking` | `state` |
| Workforce directory | `hr.employee` | `active` |
| Attendance | `hr.attendance` | presence of `check_out` |
| Leave | `hr.leave` | `state` |
| Payroll | `hr.payslip` | `state` |
| Employee expenses | `hr.expense` | `state` |
| Accounting | `account.move` | `state` |
| Payments | `account.payment` | `state` |

A model's existence, `company_id` availability, read permissions and `write_date` availability **depend on the exact Odoo edition, installed modules, company setup and current API version**. Do not enable unverified models. For invoice-only reads use an explicit `move_type` selector; **posted payment is not bank-settled payment**. This bridge never transfers names, salaries, wages, personal documents, bank identifiers, payment values or raw Odoo JSON.

## What it really implements

- `POST /api/erp/grants` (tenant admin): grant model/company to an existing active `connector/odoo_enterprise` credential with exact `scope=ODOO_INSTANCE`. Grants default deny and can be revoked with `DELETE /api/erp/grants/{credential_id}/{company_id}/{model}`.
- `GET /api/erp/catalog`, `GET /api/erp/grants` (tenant admin).
- `POST /api/erp/records/import` (scoped Odoo connector only): durable source-only state mirror. Rejects unapproved models, companies, namespaces, invalid/future timestamps. Same state+timestamp is an idempotent replay; older updates cannot roll back current state; equal timestamp with conflicting state is rejected. Appends events only for first appearance or state changes.
- `GET /api/erp/summary`, `GET /api/erp/records`, `GET /api/erp/records/{uuid}/history` (tenant admin only): status-only records, never unapproved tenant browsing.
- `adapters/odoo_enterprise_cli.py`: per-model customer-reviewed selector, explicit company allowlist, bounded keyset pagination, fixed model/field allowlists, source-only statuses and heartbeat. Uses the same `OdooJSON2` implementation as the existing work-order importer. It performs NO Odoo writes.
- `compose.odoo-enterprise.yaml`: optional container `odoo-enterprise-sync` with separate restricted credentials; shares Rally's network, not its source database.
- **Unchanged**: current custody, job importer, Traccar GPS, RFID spool and their database volumes.

**Not implemented:** automated exception rules across these new models; CRM handoff linking; Odoo invoice/accounting line-item reconciliation; payment gateway settlement; HR attendance justification decisions; cross-model business workflows. These require formal business rule approvals, legal/privacy constraints and authentic reference data.

## Prepare WITHOUT a real provider key

From Rally WSL checkout:

```bash
git pull --ff-only origin main
cp .env.odoo-enterprise.example .env.odoo-enterprise
chmod 600 .env.odoo-enterprise
# Do not start enterprise sync yet.
docker compose -f compose.yaml -f compose.odoo-enterprise.yaml --profile odoo-enterprise config --quiet
```

Do not edit `.env` for Rally admin credentials. The new `.env.odoo-enterprise` is separate and ignored by Git. The service is opt-in and does not run until explicitly enabled.

## Activate when approved API credentials exist

1. Confirm your Odoo database, version/edition, JSON-2 API eligibility, `res.company` IDs, per-model ACLs, record rules and availability of `write_date` and `company_id`. Some domains (e.g. `hr.payslip`) are not part of every installation.
2. As a Rally tenant admin, issue a dedicated credential in **Audit & access**: `role=connector`, `source=odoo_enterprise`, `scope=stable-instance-namespace`. Keep the token private. **Do not reuse the Traccar token or an administrative token.**
3. Find the new credential's ID via `GET /api/credentials` as the admin. Then grant ONLY approved company+models, e.g. via locally authenticated API:

   ```json
   {"credential_id": "<REAL_ODOO_CONNECTOR_UUID>", "company_id": 1,
    "models": ["purchase.order", "stock.picking"]}
   ```

   Submit to `POST /api/erp/grants` with an administrator bearer. **Do not use placeholder IDs**. Model grants are separate from the existing `/api/jobs/import` Odoo selected-sale bridge.
4. Fill in `.env.odoo-enterprise` locally: provider URL (HTTPS), database, API key, matching `ODOO_INSTANCE`, allowed `ODOO_COMPANY_IDS`, Rally Odoo Enterprise connector token, selected `ODOO_ENTERPRISE_MODELS` and `ODOO_ENTERPRISE_SELECTORS_JSON`. Every selected model requires a **nonempty, customer-reviewed** list of simple Odoo domain clauses; the adapter adds company + ascending ID filters itself. Example for approved purchase orders:

   ```dotenv
   ODOO_ENTERPRISE_MODELS=purchase.order
   ODOO_ENTERPRISE_SELECTORS_JSON={"purchase.order":[["state","in",["purchase","done"]]]}
   ```

5. Only after company grants and credentials are verified, start the sync service:

   ```bash
   docker compose -f compose.yaml -f compose.odoo-enterprise.yaml \\
     --profile odoo-enterprise up -d --build odoo-enterprise-sync
   docker compose -f compose.yaml -f compose.odoo-enterprise.yaml \\
     --profile odoo-enterprise logs --tail=35 odoo-enterprise-sync
   ```

   The connector heartbeat reports successful complete scans or errors. `/api/erp/summary` is tenant-admin-only; open **Mission Control → Integrations → Load approved ERP states**. If a model is unsupported or permissions are insufficient, **disable it and correct Odoo access**—do not bypass company filters.

## Safety and recovery

- Scoped connectors cannot browse ERP records, add their own grants, or use any other tenant's assets or records; administrative grant actions are audited.
- A successful API poll does not prove process completion. Status `paid`/`posted` in Odoo is not, without financial reconciliation, a bank receipt.
- No new payroll, expense amount or payment value is copied; detailed financial/HR verification requires a separately approved rights and privacy model.
- No direct secrets in source or web UI. Don't paste values into chat or commit `.env.odoo-enterprise`; if the reference `OdooAttendance/services/ErpAdapterService.ts` contains a working embedded credential, rotate it before deployment.
- A revoked grant blocks subsequent imports immediately. Already imported non-sensitive source states remain historical; determine retention and erase/export requirements with the customer before production.
- Stop the optional connector without touching Rally or Traccar: `docker compose -f compose.yaml -f compose.odoo-enterprise.yaml --profile odoo-enterprise stop odoo-enterprise-sync`.
- Never `docker compose down -v`; it deletes named volumes. No real source has been accessed as part of this software development.


## Configurable ERP exception cases (optional, default off)

After creating the company/model grant, the tenant administrator may establish an approved state-age policy in **Integrations → ERP exception policy**, or submit:

```json
{"instance":"APPROVED_INSTANCE","company_id":7,"model":"purchase.order",
 "state":"draft","max_age_seconds":86400,"severity":"warning"}
```

Submit to `POST /api/erp/policies`. The rule means: *an observed record of this specific model and company has remained in this state for more than the configured duration*, **not** that a supplier contract or accounting obligation is definitely breached. Rules only evaluate records whose last import is within `RALLY_CONNECTOR_STALE_SECONDS`; stale feeds do not create new asserted cases, and existing cases do not silently close when the source becomes stale. A fresh authorized state transition can resolve its condition using existing Rally case audit and human review. `GET /api/erp/policies` lists configurations; `POST /api/erp/policies/{id}/disable` disables one and allows the worker to close the rule's cases with an audited reason.

The system has no policies by default. No tenant, employee or company is subjected to automatically invented SLA assumptions. Financial/HR policies must receive additional compliance and access review before enabling outside a laboratory.


**Credential segregation:** legacy `source=odoo` can import selected sale-based work orders only. The new `source=odoo_enterprise` is required for state snapshots and cannot import jobs. Never reuse the old sales connector or Traccar token for the enterprise mirror.
