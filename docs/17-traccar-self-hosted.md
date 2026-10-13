# Self-hosted Traccar GPS lab for Rally (WSL 2 + Docker Desktop)

**Scope:** local lab only. Use your own Traccar server and a real phone, not a cloud subscription.
Rally's existing tenants, SQLite volume, work orders, and evidence are not replaced.

## Official basis / version

The upstream [Traccar Docker documentation](https://www.traccar.org/docker/) documents official images, persistent logs/data and the recommendation to publish **only the needed protocol ports**. This overlay pins `traccar/traccar:6.16.0-alpine` for reproducibility.
The [Traccar Client](https://www.traccar.org/client-configuration/) uses **OsmAnd/HTTP on TCP 5055**. Its receiver is separate from the server's web UI on TCP 8082.
The official [API](https://www.traccar.org/traccar-api/) supports API tokens and retrieving last reported device positions.
Traccar's default embedded H2 database **is not recommended for production**. This lab retains H2 data in its **own named volume**; a real deployment must migrate to a supported external database and use HTTPS.

## Architecture

```text
Traccar Client on phone (real GPS)
           | TCP/5055, local trusted Wi-Fi only
           v
traccar/traccar:6.16.0-alpine
  Web UI -> http://localhost:8082 (host loopback only)
  H2 database -> separate persistent traccar_data volume
           | REST /api/positions (read-only)
           v
traccar-sync (opt-in Compose profile; no browser secrets)
  Uses scoped Traccar API token and scoped Rally connector credential
  Poll every 60 s -> normalized idempotent evidence + heartbeat
           |
           v
rally:8080, tenant-specific evidence
           |
           v
Mission Control -> Fleet & GPS (reported positions, age/quality)
```

A location fix is device-reported data; it is **not** proof of vehicle custody, technician presence, or job completion. Rally does not create fake map markers.

## Start Traccar without disturbing Rally

From the Rally repository folder in WSL, with `.env` already configured for Rally:

```bash
cp .env.traccar.example .env.traccar
chmod 600 .env.traccar
docker compose -f compose.yaml -f compose.traccar.yaml up -d --build rally worker traccar
docker compose -f compose.yaml -f compose.traccar.yaml ps
```

Open **http://localhost:8082** in Windows. On recent Traccar versions there are **no default administrator credentials**; register the first user promptly and keep the web UI on loopback. Traccar may need a little time to initialize. Do not connect the phone until the device has been added in Traccar.

To check the public server information from WSL, without any secrets:
```bash
curl -i --max-time 10 http://127.0.0.1:8082/api/server
docker compose -f compose.yaml -f compose.traccar.yaml logs --tail=40 traccar
```

Do **not** run `docker compose down -v`: it would delete volumes. Starting this overlay alongside the existing stack does not touch the other BFDB/MQTT/TimescaleDB containers.

## Create a real phone device

1. On Traccar Web UI (`localhost:8082`) create an account and a device, with **Unique ID** exactly matching the **Device identifier** in your Traccar Client application.
2. Download [Traccar Client](https://www.traccar.org/client/) on the phone (not Traccar Manager). Enable appropriate location permission, and **start** the tracking service.
3. By default the overlay binds TCP 5055 only to Windows/WSL loopback. For a phone on the **same trusted Wi-Fi**, append `TRACCAR_DEVICE_BIND=0.0.0.0` to your **ignored root `.env`**, then run:
   ```bash
   docker compose -f compose.yaml -f compose.traccar.yaml up -d --force-recreate traccar
   ```
4. On Windows, run `ipconfig` and identify your Wi-Fi/Ethernet IPv4 (e.g. `192.168.1.25`). Set the **Traccar Client Server URL** to `http://YOUR_WINDOWS_LAN_IP:5055`. **Do not use `localhost` or WSL's internal 172.* address on the phone.**
5. Permit inbound TCP 5055 **only for the trusted local subnet** in Windows Firewall if necessary. **Never port-forward 5055 from your router to the public internet.** OsmAnd location reports over plain HTTP are not private on an untrusted network.
6. Once the device reports real GPS fixes, confirm the device is **online** and its last position updates in Traccar Web UI.

Traccar Web UI stays at `http://localhost:8082`; mobile reports go to `:5055`. For off-LAN tracking, set up VPN or a properly secured HTTPS receiver first.

## Connect this server to Tenant A in Rally

**Never paste tokens into chats, tickets, screenshots, or Git.** Traccar API tokens and Rally connector tokens are distinct.

1. Inside Traccar's Web UI, create a **Traccar user API token** for the authorized devices; save it privately.
2. Inside **Rally → Audit & access**, create a new credential named `Traccar Local Lab`, role `connector`, source `traccar`. Keep the one-time secret.
3. Identify the internal **numeric device ID** using Traccar's API, and the Rally **asset UUID** using Rally's API. These are **not** Traccar's phone Unique ID and **not** the Rally tag `CAM-001`. Run locally:

   ```bash
   python3 - <<'PY'
   import getpass, json, urllib.request
   t=getpass.getpass('Traccar user API token (hidden): ')
   r=getpass.getpass('Rally tenant admin/reader token (hidden): ')
   for label,url,token in [
       ('Traccar devices','http://127.0.0.1:8082/api/devices',t),
       ('Rally assets','http://127.0.0.1:8080/api/assets',r)]:
       req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token})
       with urllib.request.urlopen(req,timeout=15) as response:
           values=json.load(response)
       print(label, ':')
       for x in values:
           if label == 'Traccar devices':
               print('  id:',x['id'],' uniqueId:',x.get('uniqueId'),' name:',x.get('name'))
           else:
               print('  id:',x['id'],' tag:',x.get('tag'),' name:',x.get('name'))
   PY
   ```

4. Edit **`.env.traccar`** (gitignored) with the provider token, dedicated Rally connector token and the mapping, using only real IDs:

   ```dotenv
   TRACCAR_TOKEN=<PRIVATE_PROVIDER_TOKEN>
   RALLY_TENANT_TOKEN=<PRIVATE_RALLY_CONNECTOR_TOKEN>
   TRACCAR_DEVICE_ASSET_MAP={"<NUMERIC_DEVICE_ID>":"<RALLY_ASSET_UUID>"}
   TRACCAR_MAX_POSITION_AGE_SECONDS=300
   ```

   *The values above are placeholders. Never commit a filled env file.*
5. Start the optional connector poller (the other containers stay running):

   ```bash
   docker compose -f compose.yaml -f compose.traccar.yaml --profile gps-sync up -d --build traccar-sync
   docker compose -f compose.yaml -f compose.traccar.yaml --profile gps-sync logs --tail=50 traccar-sync
   ```

6. In Rally Mission Control, use **Integrations** to check the Traccar connector's coverage and **Fleet & GPS → Reload positions**. Real device readings arrive within the configured interval plus processing time. Missing fixes, malformed readings, stale positions or unknown mappings produce degraded/unknown coverage, **not fake locations**.

**Recovery:** To stop the poller while keeping Rally and Traccar running:
```bash
docker compose -f compose.yaml -f compose.traccar.yaml --profile gps-sync stop traccar-sync
```

## Guardrails

- Local-only H2 is for pilot/experimentation, **not production**. For production use a supported database, independent backup/restore, TLS, VPN/firewall access, secrets management, and device/user access rules. Traccar does not have to share Rally's database.
- Source snapshots come from `GET /api/positions`, which reports last-known device positions; the current integration is periodic polling, **not Traccar's live WebSocket**.
- Rally's map respects tenant ownership, uses last reported positions and quality indicators, and optionally loads public OpenStreetMap tiles only with user action.
- Traccar device **Unique ID** is not authentication; anyone who learns it and can reach the unsecured protocol port may submit reports. Constrain the network and never expose it publicly with the lab configuration.
- Position tracking is personal location data. Get appropriate informed consent, follow applicable labor/privacy law, and set retention and access limits.
- If you've shared Rally tokens in chat before, revoke those and issue new dedicated credentials before connecting this GPS source.
