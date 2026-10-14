# Odoo Community 19 — disposable-purpose, persistent local integration laboratory

**Purpose:** a wholly separate source ERP for Rally development on WSL/Docker. **Not production** and not the customer's live Odoo.sh/Odoo Enterprise database. No real Odoo API key is required to start the environment. Built on the [official Odoo Docker image](https://hub.docker.com/_/odoo) and an independent PostgreSQL 16 service.

## Why we chose it

- Self-hosted Odoo Community 19 is suitable for safely probing Rally's `/json/2` read adapter, permissions, source identity, state transitions and refresh behavior.
- **Odoo.sh is Odoo Enterprise hosting**, not the same thing as Odoo Online SaaS. Its apps, custom code, backup and API access are governed by the customer's contract, privileges and installed modules. It is a better *eventual target* for real Enterprise-only flows (payroll, advanced accounting, etc.), not a reason to risk a production database while developing.
- Community supports a **subset** of the intended domains. Odoo versions/editions and modules determine the actual model and field availability. In particular, `hr.payslip` must not be assumed installed in Community. Accounting and payroll fidelity are **not certified** by the lab.
- Odoo 19 introduces JSON-2. The existing Rally `OdooJSON2` client requires Odoo 19. Odoo.sh on older versions must not be connected through this path without confirming API compatibility.

## Safety architecture

```text
 Windows browser --> http://127.0.0.1:8069 --> Odoo Community 19 (sandbox)
                                            |
                                      private Docker DB network
                                            |
                                        Postgres 16 (lab only)
                                            |
                                      odoo_lab_pgdata named volume

 Rally API / Worker / Traccar -------- existing Rally state (unchanged)
 Odoo Enterprise connector (optional) --> http://odoo-lab:8069
      with a separate Rally odoo_enterprise token + narrowly scoped Odoo bot API key
```

Odoo is exposed on **127.0.0.1:8069 only**; PostgreSQL has no published port and is isolated from Rally's application network. Filestore and Postgres data have distinct volumes `odoo_lab_filestore` and `odoo_lab_pgdata`. Nothing in this setup deletes or resets other services.

Database manager has a per-installation random master password, and Odoo connects to Postgres with a separately generated password. Local secret/config files are Git-ignored. Do not copy them into issues, chat, CI logs, or the public repo. On Windows-mounted `/mnt/c` repositories, native ACLs may not enforce Unix permission bits, so prefer a dedicated WSL Linux filesystem for stronger protection.

## 1. Start Odoo Community in the same local Docker project

From the root of the Rally checkout in WSL:

```bash
git pull --ff-only origin main
bash ops/odoo_lab.sh start
bash ops/odoo_lab.sh status
```

The first start pulls the official `odoo:19.0-20260908` image and `postgres:16-bookworm`; it can take a few minutes. The script creates `.env.odoo-lab` and `.local/odoo-lab/odoo.conf` using unique random passwords **without printing either**, then starts **only** Odoo and its Postgres dependency.

Do not run `docker compose down -v`; it removes valuable named volumes.

Open [http://localhost:8069](http://localhost:8069) and create a NEW local test database. Use:
- Database name: **`rally_odoo_lab`** (required by the strict dbfilter).
- Master password: obtain **locally** with `bash ops/odoo_lab.sh master-password`; don't paste it anywhere else.
- Administrator login and password: **choose your own strong unique values**; do not reuse credentials from Odoo.sh, Rally or your other apps.
- Demo data: optional only for this local sandbox; **never treat demo records as customer evidence**.

Odoo may expose a database creation prompt on the first visit; the exact installer screen depends on the published image. After creating the database, install the minimal desired Odoo apps from its UI: start with **Purchase** and, if needed, **Inventory**, then CRM. Each model must be verified in Odoo 19 before activating it in Rally.

## 2. Verify version / endpoint before any token

```bash
curl -fsS http://127.0.0.1:8069/web/version
```

Expected: JSON identifying Odoo version 19. This proves **HTTP server only**, not model access or a successful JSON-2 authentication.

Log in to Odoo and create a **dedicated low-privilege bot account and API key** in user preferences under *Account Security*. For Odoo 19, API keys have expiration (up to 3 months per current official docs), so record rotation ownership. The bot must have explicit read permissions to the installed model(s) and allowed company.

## 3. Authorize the lab in Rally (only AFTER Odoo is provisioned)

In Rally → **Audit & access**, create a NEW connector:
- role `connector`
- source `odoo_enterprise`
- scope `odoo_lab_19` (use exactly this stable source namespace)

In Rally → **Integrations → Odoo Enterprise · Explicit model authorization**, load the connector, choose your actual lab company ID and approve only selected models (e.g. `purchase.order`). The lab's company ID **must be read from Odoo**, not guessed from a default assumption.

In the existing local private `.env.odoo-enterprise`, set values only after the local Odoo database is initialized:

```dotenv
ODOO_URL=http://odoo-lab:8069
ODOO_DATABASE=rally_odoo_lab
ODOO_INSTANCE=odoo_lab_19
ODOO_COMPANY_IDS=<ACTUAL_APPROVED_ODOO_COMPANY_ID>
ODOO_API_KEY=<LAB_BOT_KEY_NOT_REAL_ODOO_SH_KEY>
RALLY_TENANT_TOKEN=<NEW_RALLY_ODOO_ENTERPRISE_CONNECTOR_TOKEN>
ODOO_ENTERPRISE_MODELS=purchase.order
ODOO_ENTERPRISE_SELECTORS_JSON={"purchase.order":[["state","in",["purchase","done"]]]}
```

`RALLY_ALLOW_INTERNAL_HTTP=1` is already set in the optional connector's Compose service. Local HTTP **must not** be used for Odoo.sh or a remote network. Odoo.sh targets should use valid HTTPS, verified API capabilities and provider-specific permissions.

## 4. Activate the optional importer when source and grants are ready

Because this laboratory stores its PostgreSQL secret outside Rally's default `.env`, Docker Compose needs to load **both** local environment files. After the local Odoo database, API key, Odoo company ID and Rally grant are configured:

```bash
docker compose --env-file .env --env-file .env.odoo-lab \
  -f compose.yaml -f compose.odoo-lab.yaml -f compose.odoo-enterprise.yaml \
  --profile odoo-lab --profile odoo-enterprise \
  up -d --build odoo-enterprise-sync

docker compose --env-file .env --env-file .env.odoo-lab \
  -f compose.yaml -f compose.odoo-lab.yaml -f compose.odoo-enterprise.yaml \
  --profile odoo-lab --profile odoo-enterprise \
  logs --tail=35 odoo-enterprise-sync
```

The connector only starts when explicitly selected, not when the Odoo lab starts. `RALLY_ALLOW_INTERNAL_HTTP=1` is already set in the optional connector Compose, and is **only appropriate for the isolated trusted Docker network**.

For Odoo.sh, omit `compose.odoo-lab.yaml` and `.env.odoo-lab`, and use `ODOO_URL=https://...` against an approved Odoo 19 system with external API entitlements and least-privilege access.

## 5. Stop without deleting anything

```bash
bash ops/odoo_lab.sh stop
```

Re-run `bash ops/odoo_lab.sh start` to resume. The Odoo database and filestore remain in named volumes. Do not claim that a running container proves installation of all eleven models, live key authorization, or customer ERP compatibility.

## Known operational limits

- No production TLS/domain, backups, regional data protection controls, Odoo Enterprise license, outgoing mail or multiuser availability have been supplied. **Do not expose this lab publicly.**
- Official Community Docker image contains the open-source apps; it does not package Enterprise add-ons. Licensed Enterprise code must never be copied or mounted without the appropriate agreement.
- Odoo.sh cannot be treated as a simple local Docker image; later migration from lab to Odoo.sh uses a separate authorized Odoo Enterprise instance and model/API verification, not copying the Community database blindly.
- Some Odoo models may lack `company_id` or have special record rules; the Rally importer fails closed rather than guessing. Validate one model first.
