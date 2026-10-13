"""One-shot read-only Odoo -> Rally work-order import.

This imports confirmed sales as Rally work-order *intent* (not job completion).
Stable references prevent duplicate import across repeated invocations.
Full keyset pagination and title upserts; no deletes or automatic completion.
"""
import asyncio
import os
import httpx
from adapters.odoo_json2 import OdooConfig, OdooJSON2

def map_confirmed_sale(order: dict, database: str) -> dict:
    if order.get("state") not in {"sale", "done"}:
        raise ValueError("Only confirmed sales may create operational intent")
    oid = order.get("id")
    if not isinstance(oid, int) or oid < 1:
        raise ValueError("Odoo sale order ID missing")
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
    odoo = OdooJSON2(OdooConfig(os.environ['ODOO_URL'], database, os.environ['ODOO_API_KEY']))
    rally = RallyClient()
    cursor, imported = 0, 0
    # Full keyset traversal each cycle also picks up changed titles and records
    # confirmed after a prior cycle. Never interprets ERP status as physical completion.
    while True:
        orders = await odoo.search_read('sale.order',
            [['state', 'in', ['sale', 'done']], ['company_id', 'in', companies], ['id', '>', cursor]],
            ['id', 'name', 'state', 'company_id'], limit=500)
        if not orders:
            break
        for order in orders:
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
