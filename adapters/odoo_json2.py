"""Read-only Odoo 19 JSON-2 adapter.

External API requires compatible Odoo deployment/subscription. Never treat an
HTTP success as verification of business completion. No writes or retries.
"""
from dataclasses import dataclass
from adapters.transport import validate_url, request
import httpx
from rally.erp_contract import MODEL_CONTRACTS

@dataclass(frozen=True)
class OdooConfig:
    base_url: str
    database: str
    api_key: str

    def validate(self):
        validate_url(self.base_url)
        if not self.database or not self.api_key:
            raise ValueError("Odoo database and API key are required")

class OdooJSON2:
    def __init__(self, config: OdooConfig):
        config.validate()
        self.config = config

    async def search_read(self, model: str, domain: list, fields: list[str], limit: int = 100, order: str = "id asc"):
        if model not in (set(MODEL_CONTRACTS) | {"project.task"}):
            raise ValueError("Model not approved for read-only Rally connector")
        if not 1 <= limit <= 500:
            raise ValueError("Limit must be between 1 and 500")
        headers = {
            "Authorization": "bearer " + self.config.api_key,
            "X-Odoo-Database": self.config.database,
        }
        url = self.config.base_url.rstrip("/") + "/json/2/" + model + "/search_read"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await request(client, "POST",
                url, headers=headers, json={"domain": domain, "fields": fields, "limit": limit, "order": order}
            )
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, list):
            raise ValueError("Unexpected Odoo search_read response")
        return result

    async def recent_sale_orders(self, limit: int = 100):
        return await self.search_read("sale.order", [], ["id", "name", "state", "date_order"], limit)
