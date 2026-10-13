"""One-shot read-only Odoo -> Rally work-order import.

This imports confirmed sales as Rally work-order *intent* (not job completion).
Stable references prevent duplicate import across repeated invocations.
No webhooks, backfill pagination, deletes or update sync are implemented.
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
    required = ("ODOO_URL", "ODOO_DATABASE", "ODOO_API_KEY", "RALLY_URL", "RALLY_TENANT_TOKEN")
    if missing := [x for x in required if not os.getenv(x)]:
        raise RuntimeError("Missing: " + ", ".join(missing))
    db = os.environ["ODOO_DATABASE"]
    odoo = OdooJSON2(OdooConfig(os.environ["ODOO_URL"], db, os.environ["ODOO_API_KEY"]))
    orders = await odoo.search_read(
        "sale.order", [["state", "in", ["sale", "done"]]],
        ["id", "name", "state", "date_order"], limit=500
    )
    created = already_present = 0
    async with httpx.AsyncClient(timeout=20.0) as client:
        base = os.environ["RALLY_URL"].rstrip("/") + "/api/jobs"
        headers = {"Authorization": "Bearer " + os.environ["RALLY_TENANT_TOKEN"]}
        existing_request = await client.get(base, headers=headers)
        existing_request.raise_for_status()
        existing = {j["external_ref"] for j in existing_request.json()}
        for order in orders:
            job = map_confirmed_sale(order, db)
            if job["external_ref"] in existing:
                already_present += 1
                continue
            response = await client.post(base, headers=headers, json=job)
            if response.status_code == 409:
                # Concurrent importer: refresh and prove the key exists.
                again = await client.get(base, headers=headers)
                again.raise_for_status()
                if job["external_ref"] not in {j["external_ref"] for j in again.json()}:
                    response.raise_for_status()
                already_present += 1
                continue
            response.raise_for_status()
            existing.add(job["external_ref"])
            created += 1
    print({"created": created, "already_present": already_present, "retrieved": len(orders),
           "limit": 500, "note": "One page; no guaranteed full synchronization"})

if __name__ == "__main__":
    asyncio.run(main())
