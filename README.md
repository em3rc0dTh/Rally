# RALLY — Business Execution Assurance

**Know what's missing. Recover what failed. Verify what succeeded.**

Rally connects ERP commitments to evidence of physical business execution, detects discrepancies, and manages closure. The MK0 focus is **asset custody and work orders**, with optional Odoo, GPS/Traccar and RFID adapters. This is an **engineering pilot**, not a production SaaS or official Odoo product.

## Implemented vs proposed

| Capability | Location | Status |
| --- | --- | --- |
| Tenant-scoped API, assets, work orders, custody, idempotency | `rally/app.py`, `rally/storage.py` | Implemented MK0 |
| Browser Mission Control cockpit | `web/index.html` | Implemented MK0 |
| Evidence ingestion, deduplication, reconciliation, audit | `rally/app.py` | Implemented MK0 |
| Odoo 19 JSON-2 data fetch | `adapters/odoo_json2.py` | Read-only code; live credentials not tested |
| Traccar GPS fetch and one-shot import | `adapters/traccar.py`, `adapters/ingest_cli.py` | Code implemented; live provider not validated |
| RFID normalized event and stdin import | `adapters/rfid.py`, `adapters/rfid_ingest_cli.py` | Code implemented; physical readers not integrated |
| Temporal recovery | `workflows/` | Optional research prototype; NOT wired into main API |
| Automated checks | `tests/`, `.github/workflows/ci.yml` | Executed in CI |
| Production distributed architecture, RBAC, subscriptions | `docs/05-roadmap.md` | Not implemented |

## Quick start

Python 3.11+ required.

~~~bash
git clone https://github.com/em3rc0dTh/Rally.git
cd Rally
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
cp .env.example .env
# Replace RALLY_ADMIN_KEY with a random 32+ character secret in .env.
set -a; . ./.env; set +a
uvicorn rally.app:app --reload --port 8080
~~~

Open **http://127.0.0.1:8080/** for the operator cockpit and **http://127.0.0.1:8080/docs** for interactive API documentation.

Bootstrap a tenant and securely retain the one-time returned API token:

~~~bash
curl -X POST http://127.0.0.1:8080/api/tenants \
 -H "Content-Type: application/json" \
 -H "X-Admin-Key: $RALLY_ADMIN_KEY" \
 -d '{"name":"Demo Operations"}'
~~~

Paste the tenant token in the cockpit. You can then register assets, create work orders, issue/return equipment, record evidence, complete jobs and reconcile exceptions. For API calls, send `Authorization: Bearer TOKEN`. Custody issue and return calls additionally require `Idempotency-Key` (8–128 characters). To run the reconciliation manually:

~~~bash
curl -X POST http://127.0.0.1:8080/api/reconcile \
 -H "Authorization: Bearer $RALLY_TOKEN"
~~~

To launch a **local pilot** in Docker:

~~~bash
cp .env.example .env
# Set RALLY_ADMIN_KEY to a real secret.
docker compose up --build
~~~

Runs on loopback port 8080 with persisted `./data`. This is not an internet-ready deployment. See [security limitations](docs/06-security-and-risks.md).

## Complete documentation

1. [Product identity and competing business hypotheses](docs/00-product-vision.md)
2. [Market feasibility in Peru, Ecuador, Chile, Bolivia, Argentina and Brazil](docs/01-market-feasibility.md)
3. [Technical architecture and business consistency guarantees](docs/02-architecture.md)
4. [Open-source repository catalog and licensing](docs/03-open-source-catalog.md)
5. [Audit and reuse of odoo-engineering](docs/04-odoo-engineering-audit.md)
6. [Delivery roadmap and product gates](docs/05-roadmap.md)
7. [Security, privacy and production risks](docs/06-security-and-risks.md)
8. [Odoo, Traccar, RFID and Temporal integration guide](docs/07-integration-guide.md)
9. [Commercial validation and unit economics](docs/08-commercial-validation.md)
10. [Resumen ejecutivo en español](docs/09-resumen-ejecutivo-es.md)

## Principles

- **One buyer, one expensive problem, one verifiable outcome.** Do not pretend open-source assembly alone is differentiation.
- GPS reports **device position**, RFID reports **tag sightings**, QR reports a **scan**. None independently proves customer acceptance or work completion.
- Do not fork or vendor-copy unresolved third-party code into Rally.
- Odoo is a third-party ERP; **Rally** is a working name requiring trademark review, not an official Odoo product. Avoid marketing the name "Odoo Rally" without the necessary brand rights.
- We have deliberately **not selected a public license for Rally-authored source code**. A public GitHub repository does not itself grant unrestricted copying or commercial relicensing.

Source engineering study: https://github.com/Em3rc0d/odoo-engineering
