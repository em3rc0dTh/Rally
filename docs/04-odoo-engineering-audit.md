# Independent audit of odoo-engineering and selective reuse

Source: https://github.com/Em3rc0d/odoo-engineering
Inspected commit: `9f88f323c906fb084b5f71a763ac61775ba1f773`
Date: 2026-10-13. Source review only; Odoo 19 runtime not executed in that review.

## Actual inventory

441 tracked files; seven custom addon candidates in `addons/`; eleven upstream snapshots in `vendor/`; research MK0–MK3, five studied upstream repositories, eleven recorded findings, eight patterns, and an index of 245 educational exercises. **245 indexed exercises are not 245 completed products.**

## Seven addon decisions

| Addon | Actual function | Rally reuse |
| --- | --- | --- |
| `oe_library` | Book-copy-loan with SQL one-active-loan index and transactional checkout lock | Adapt invariant for serialized equipment custody; do not copy library domain wholesale |
| `oe_sale_task_bridge` | Confirmed sale -> project task | Future ERP work-order bridge after certification |
| `oe_crm_task_bridge` | CRM lead -> project task | Future work assignment bridge; unify lifecycle first |
| `oe_sales_dashboard` | OWL sales dashboard using real but bounded sample of 500 orders | UI/ORM reference, not a production financial KPI |
| `oe_purchase_board` | Board/surface purchasing | Separate Fabrication vertical |
| `oe_workshop_quote` | Dimension-based sales quoting | Separate Fabrication vertical |
| `oe_loan_lab` | Educational amortization simulation | Exclude from Rally commercial baseline |

## Source-level risks

1. Loan transition methods protect action flows, but no global `write()` enforcement prevents other authorized state writes. DB index does enforce unique active copies.
2. Loan creation/modification restricted to Odoo system admins; operational roles and company record isolation are incomplete.
3. Sales task and CRM task modules maintain distinct relationship fields without a single commercial lifecycle contract.
4. Static validation document references `scripts/validate_addons.py` missing from examined remote commit; that result is not reproducible in that checkout.
5. Adoption matrix retains BACKLOG/TBD for implemented candidates.
6. Third-party `ica_web_responsive` was marked quarantined but its source/assets remained published under `vendor/`; rights and compatibility require verification.
7. All seven candidate addons were marked untested against Odoo 19; installable flags do not guarantee operational correctness.

## Good patterns

Upstream SHA pins and attribution (`UPSTREAM.md`), source-vs-adaptation segregation, scoped `oe_` namespace, SQL uniqueness for concurrency, OWL/ORM usage, and explicit limitations of sampled KPIs.

## Architectural decision

**Keep odoo-engineering independent.** Rally has its own evidence, reconciliation, and operational API. Use only separately verified, legitimately redistributable Odoo modules through a versioned Odoo adapter; no wholesale vendor copy and no automatic assertion that LGPL manifests settle ownership of all source/resources.
