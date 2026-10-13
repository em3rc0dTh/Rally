# Open-source baseline catalog — adopt, adapt, improve, commercialize

Date: 2026-10-13. Repositories below are **evaluation candidates**, not copied source or commercial sublicensing approvals. Verify the currently selected commit, license files, dependency licenses and trademarks before distributing derivative works.

| Upstream | Repo | What exists | Licensing / adoption decision |
| --- | --- | --- | --- |
| **Odoo Community** | https://github.com/odoo/odoo | ERP domain system and modules | Mixed Odoo core/addon licensing incl. LGPL and Enterprise proprietary; select by actual module/deployment; **integration first** |
| **Traccar server** | https://github.com/traccar/traccar | GPS protocols, tracking, locations, geofences, REST API | Apache-2.0 upstream; use as external service, preserve notices |
| **Traccar web** | https://github.com/traccar/traccar-web | GPS map application | Apache-2.0 upstream; no need to rebrand/fork initially |
| **Traccar–Odoo** | https://github.com/traccar/traccar-odoo | Odoo fleet GPS adapter | Verify exact module declarations and potentially inconsistent license materials before adaptation |
| **OCA Field Service** | https://github.com/OCA/field-service | Odoo orders, equipment, vehicles, routes, signatures | Commonly AGPL-3 modules; review each addon and SaaS/distribution obligations; candidate for future ERP bridge |
| **OCA Logistics** | https://github.com/OCA/stock-logistics-warehouse | Warehouse and stock improvements | Review per-addon license; no wholesale importing |
| **OCA Connector** | https://github.com/OCA/connector | Odoo connector infrastructure | Check current addon licenses and API compatibility; useful reference |
| **Fleetbase** | https://github.com/fleetbase/fleetbase | Logistics/supply-chain operating system | AGPL / commercial licensing paths; avoid duplicating Odoo + Rally without business justification |
| **Snipe-IT** | https://github.com/grokability/snipe-it | Asset check-in/out, IT equipment inventory | AGPL-3.0; its domain differs from field-service tools |
| **Metratec RFID SDK** | https://github.com/metratec/rfid-sdk-python | Vendor-specific RFID reader control | MIT; hardware compatibility must be established |
| **OpenRFID Middleware** | https://github.com/rfidsoftwares/OpenRFID-Middleware | RFID event filtering and edge integration concept | Review source maturity and claimed MIT license; **experimental only**, not production certified |
| **Temporal Server** | https://github.com/temporalio/temporal | Durable execution engine | MIT; optional orchestrator, not required for observations |
| **Temporal Python SDK** | https://github.com/temporalio/sdk-python | Workflow/activities programming | MIT; optional workflow example in Rally |

## What we did NOT copy

No Odoo source, Traccar source, OCA addons, Snipe-IT, Fleetbase, or vendor RFID drivers were transplanted into Rally. Rally provides original normalized API contracts and independent adapter clients using published provider endpoints. Linking to a repository is not code adoption.

## Reuse compliance policy

1. Record upstream URL, exact commit SHA, author and file/component license before importing.
2. Determine if the asset is under MIT, Apache-2.0, LGPL, GPL, AGPL, BSL, or no license.
3. GPL/AGPL obligations may apply to distributed derivatives and modified network-served services. Calling across APIs does not categorically eliminate all copyleft analysis.
4. Preserve license notices, modification dates, copyright attribution, and third-party assets' separate terms.
5. Do not copy from a public but unlicensed repository without permission; independently implement generic requirements.
6. Do not claim that open-source equals free hosted infrastructure, free support, or trademark rights.
7. Seek appropriate counsel and a per-component Software Bill of Materials before commercial redistribution.
8. Proprietary or source-available code can be studied under applicable terms but not automatically cloned for resale.

## Branding

**Rally** is a working product name. Broadcom also markets a separate enterprise software product named Rally, making trademark clearance necessary. Use "integrates with Odoo" rather than "Odoo Rally" until the Odoo brand and partner restrictions have been reviewed. Verify any partner affiliation independently.

## License of Rally's own new code

No umbrella commercial/open-source license has been assigned by the repository owner in this delivery. Do not presume a public repository grants downstream unrestricted copying. Choose the distribution policy deliberately before offering software as open source, hosted SaaS, or white-label product.
