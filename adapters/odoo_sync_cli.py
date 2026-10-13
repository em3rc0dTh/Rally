"""One-shot read-only Odoo -> Rally work-order import.

This imports confirmed sales as Rally work-order *intent* (not job completion).
Stable references prevent duplicate import across repeated invocations.
Full keyset pagination and title upserts; no deletes or automatic completion.
"""
import asyncio
import json
import os
import re
import httpx
from adapters.odoo_json2 import OdooConfig, OdooJSON2

def map_confirmed_sale(order: dict, database: str) -> dict:
    if order.get("state") not in {"sale", "done"}:
        raise ValueError("Only confirmed sales may create operational intent")
    oid = order.get("id")
    if isinstance(oid, bool) or not isinstance(oid, int) or oid < 1:
        raise ValueError("Odoo sale order ID missing")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", database):
        raise ValueError("ODOO_INSTANCE must be a stable alphanumeric namespace (dot, dash, underscore allowed)")
    return {
        "external_ref": "odoo:" + database + ":sale.order:" + str(oid),
        "title": "Sales order " + str(order.get("name") or oid),
    }

async def main():
    from adapters.transport import RallyClient
    required = ('ODOO_URL', 'ODOO_DATABASE', 'ODOO_API_KEY', 'ODOO_COMPANY_IDS', 'RALLY_URL', 'RALLY_TENANT_TOKEN')
    if missing := [x for x in required if not os.getenv(x)]:
        raise RuntimeError('Missing: ' + ', '.join(missing))
    database = os.environ['ODOO_DATABASE']
    companies = [int(x.strip()) for x in os.environ['ODOO_COMPANY_IDS'].split(',')]
    if not companies or any(x < 1 for x in companies):
        raise ValueError('Explicit positive Odoo company IDs required')
    # A confirmed sales order is NOT necessarily a field-service work order.
    # Fail closed unless the customer explicitly identifies the subset of
    # commercial sales that represent jobs (e.g. a custom boolean/tag field).
    configured = os.environ.get('ODOO_WORKORDER_DOMAIN_JSON', '')
    if not configured.strip():
        raise ValueError('ODOO_WORKORDER_DOMAIN_JSON is required; do not import all sales')
    selector = json.loads(configured)
    if (not isinstance(selector, list) or not selector or
        any(not isinstance(term, list) or len(term) != 3 or
            not isinstance(term[0], str) or not term[0] for term in selector)):
        raise ValueError('ODOO_WORKORDER_DOMAIN_JSON must be a nonempty list of simple Odoo domain terms')
    odoo = OdooJSON2(OdooConfig(os.environ['ODOO_URL'], database, os.environ['ODOO_API_KEY']))
    rally = RallyClient()
    cursor, imported = 0, 0
    # Full keyset traversal each cycle also picks up changed titles and records
    # confirmed after a prior cycle. Never interprets ERP status as physical completion.
    while True:
        orders = await odoo.search_read('sale.order',
            [['state', 'in', ['sale', 'done']], ['company_id', 'in', companies], ['id', '>', cursor], *selector],
            ['id', 'name', 'state', 'company_id'], limit=500)
        if not orders:
            break
        for order in orders:
            # Odoo JSON-2 may return a many2one as [id, display_name].
            raw_company = order.get('company_id')
            company_id = raw_company[0] if isinstance(raw_company, (list, tuple)) and raw_company else raw_company
            if type(company_id) is not int or company_id not in companies:
                raise ValueError('Odoo returned a sale outside the explicitly permitted company IDs')
            job = map_confirmed_sale(order, (os.getenv('ODOO_INSTANCE') or database))
            await rally.post('jobs/import', job)
            imported += 1
        next_cursor = max(x['id'] for x in orders)
        if next_cursor <= cursor:
            raise ValueError('Odoo pagination did not advance')
        cursor = next_cursor
    await rally.heartbeat('ok', f'Confirmed sales imported: {imported}')
    print({'imported': imported})

if __name__ == '__main__':
    asyncio.run(main())
