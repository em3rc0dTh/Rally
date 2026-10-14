#!/usr/bin/env bash
# Initialize/manage the optional self-hosted Odoo Community 19 sandbox.
# Does not modify Rally .env, run migrations on other DBs, or delete volumes.
set -euo pipefail
cd "$(dirname "$0")/.."
task="${1:-help}"

compose=(docker compose --env-file .env --env-file .env.odoo-lab
  -f compose.yaml -f compose.odoo-lab.yaml --profile odoo-lab)

initialize() {
  if [[ ! -f .env ]]; then
    echo "Rally .env missing. Set up Rally first; the lab never creates a Rally admin secret." >&2
    exit 1
  fi
  mkdir -p .local/odoo-lab
  chmod 700 .local/odoo-lab
  if [[ ! -e .env.odoo-lab ]]; then
    python3 - <<'PY'
from pathlib import Path
from secrets import token_urlsafe
import os
dest=Path(".env.odoo-lab")
flags=os.O_WRONLY | os.O_CREAT | os.O_EXCL
fd=os.open(str(dest), flags, 0o600)
with os.fdopen(fd, "w") as out:
    out.write("# Auto-generated; do not share or commit. Independent of Rally/Traccar.\n")
    out.write("ODOO_LAB_DB_PASSWORD=" + token_urlsafe(36) + "\n")
PY
    echo "Generated private Odoo lab DB secret (not displayed)."
  fi
  if [[ ! -e .local/odoo-lab/odoo.conf ]]; then
    python3 - <<'PY'
from pathlib import Path
from secrets import token_urlsafe
import os
path=Path(".local/odoo-lab/odoo.conf")
fd=os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
with os.fdopen(fd, "w") as conf:
    conf.write("[options]\n")
    conf.write("admin_passwd = " + token_urlsafe(40) + "\n")
    conf.write("dbfilter = ^rally_odoo_lab$\n")
    conf.write("list_db = True\n")
    conf.write("proxy_mode = False\n")
PY
    echo "Generated protected Odoo database-manager password (not displayed)."
  fi
  # Odoo runs under its own UID. The local config is readable *inside* the
  # container while the parent host directory is owner-only. Windows DrvFS
  # permissions may differ; use WSL Linux storage for higher-assurance secrets.
  chmod 600 .env.odoo-lab
}

case "$task" in
  init)
    initialize
    echo "Lab configuration ready. Start with: bash ops/odoo_lab.sh start"
    ;;
  start)
    initialize
    "${compose[@]}" up -d odoo-lab
    echo "Odoo lab requested at http://127.0.0.1:8069 (loopback only)."
    echo "Database name must be rally_odoo_lab."
    echo "To view the database-manager password LOCALLY: bash ops/odoo_lab.sh master-password"
    ;;
  stop)
    [[ -f .env.odoo-lab ]] || { echo "Lab was not initialized."; exit 0; }
    "${compose[@]}" stop odoo-lab odoo-lab-db
    echo "Odoo lab stopped. Volumes and passwords retained."
    ;;
  status)
    [[ -f .env.odoo-lab ]] || { echo "Lab not initialized."; exit 0; }
    "${compose[@]}" ps odoo-lab odoo-lab-db
    ;;
  logs)
    [[ -f .env.odoo-lab ]] || { echo "Lab not initialized."; exit 0; }
    "${compose[@]}" logs --tail=60 odoo-lab
    ;;
  master-password)
    [[ -f .local/odoo-lab/odoo.conf ]] || { echo "Lab not initialized."; exit 1; }
    echo "Sensitive: do not paste this value into chat, logs or issues."
    sed -n 's/^admin_passwd = //p' .local/odoo-lab/odoo.conf
    ;;
  *)
    echo "Usage: bash ops/odoo_lab.sh {init|start|stop|status|logs|master-password}"
    exit 2
    ;;
esac
