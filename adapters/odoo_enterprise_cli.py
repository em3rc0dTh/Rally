"""One-shot Odoo 19 enterprise read-only state bridge.

Fails closed: an explicit model allowlist AND a customer-reviewed domain for
EVERY selected model, company allowlist and matching Rally model grants.
No external business writes, no names/amounts/HR details copied to Rally.
"""
import asyncio
import json
import os
import re
from adapters.odoo_json2 import OdooConfig, OdooJSON2
from adapters.transport import RallyClient
from rally.erp_contract import MODEL_CONTRACTS, normalize_record, valid_namespace

OPERATORS = frozenset({"=", "!=", "in", "not in", ">", ">=", "<", "<="})
FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,79}$")


def validate_selector(value):
    if not isinstance(value, list) or not value or len(value) > 20:
        raise ValueError("Every Odoo model requires a nonempty bounded selector")
    cleaned = []
    for clause in value:
        if (not isinstance(clause, list) or len(clause) != 3 or
            not isinstance(clause[0], str) or not FIELD.fullmatch(clause[0]) or
            clause[1] not in OPERATORS):
            raise ValueError("Only customer-approved simple Odoo domain clauses are supported")
        field, op, term = clause
        values = term if isinstance(term, list) else [term]
        if (not values or len(values) > 100 or
            any(type(item) not in (str, int, float, bool) or
                isinstance(item, str) and len(item) > 120 for item in values)):
            raise ValueError("Odoo selector values must be bounded primitives")
        if (op in {"in", "not in"}) != isinstance(term, list):
            raise ValueError("Selector list operators require lists")
        cleaned.append([field, op, term])
    return cleaned


def load_config():
    required = ("ODOO_URL", "ODOO_DATABASE", "ODOO_API_KEY", "ODOO_COMPANY_IDS",
                "ODOO_INSTANCE", "ODOO_ENTERPRISE_MODELS",
                "ODOO_ENTERPRISE_SELECTORS_JSON", "RALLY_URL", "RALLY_TENANT_TOKEN")
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError("Missing enterprise Odoo configuration: " + ", ".join(missing))
    instance = valid_namespace(os.environ["ODOO_INSTANCE"])
    company_parts = os.environ["ODOO_COMPANY_IDS"].split(",")
    if any(not re.fullmatch(r"[1-9][0-9]*", x.strip()) for x in company_parts):
        raise ValueError("Explicit positive company IDs required")
    companies = sorted({int(x.strip()) for x in company_parts})
    models = [m.strip() for m in os.environ["ODOO_ENTERPRISE_MODELS"].split(",")]
    if not models or len(models) != len(set(models)) or any(m not in MODEL_CONTRACTS for m in models):
        raise ValueError("Explicit supported, nonduplicated enterprise models required")
    selectors = json.loads(os.environ["ODOO_ENTERPRISE_SELECTORS_JSON"])
    if not isinstance(selectors, dict) or set(selectors) != set(models):
        raise ValueError("A reviewed selector for every enabled model, and no others, is required")
    selectors = {model: validate_selector(selectors[model]) for model in models}
    maximum = int(os.getenv("ODOO_ENTERPRISE_MAX_PER_MODEL", "10000"))
    if not 1 <= maximum <= 100000:
        raise ValueError("ODOO_ENTERPRISE_MAX_PER_MODEL must be 1-100000")
    return instance, companies, models, selectors, maximum


async def main():
    instance, companies, models, selectors, maximum = load_config()
    odoo = OdooJSON2(OdooConfig(os.environ["ODOO_URL"],
                                os.environ["ODOO_DATABASE"], os.environ["ODOO_API_KEY"]))
    rally = RallyClient()
    report = {}
    # Preserve stage/status only, never arbitrary Odoo JSON, monetary amounts,
    # employee names, emails, card data or bank details.
    for model in models:
        cursor, imported, unchanged, ignored = 0, 0, 0, 0
        while True:
            page = await odoo.search_read(model,
                [["company_id", "in", companies], ["id", ">", cursor], *selectors[model]],
                list(MODEL_CONTRACTS[model][1]), limit=min(500, maximum - imported - unchanged - ignored))
            if not page:
                break
            next_cursor = cursor
            for row in page:
                record = normalize_record(model, row, instance, set(companies))
                if record["record_id"] <= cursor:
                    raise ValueError("Provider pagination repeated a prior record")
                next_cursor = max(next_cursor, record["record_id"])
                result = await rally.post("erp/records/import", record)
                if result["action"] == "changed" or result["action"] == "created":
                    imported += 1
                elif result["action"] == "older_ignored":
                    ignored += 1
                else:
                    unchanged += 1
            if next_cursor <= cursor:
                raise ValueError("Odoo keyset pagination did not advance")
            cursor = next_cursor
            if imported + unchanged + ignored >= maximum:
                # Fail closed rather than claiming complete coverage from a truncated scan.
                raise ValueError("Model scan cap reached; coverage cannot be certified")
        report[model] = {"created_or_changed": imported, "unchanged": unchanged, "older_ignored": ignored}
    await rally.heartbeat("ok", "Enterprise Odoo state scan completed for " + ", ".join(models))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
