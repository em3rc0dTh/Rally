#!/usr/bin/env bash
# Restore to a NEW, EMPTY database. Cutover is a separate operator action.
set -euo pipefail
if [[ $# != 2 || ! "$2" =~ ^rally_restore_[a-z0-9_]+$ ]]; then
  echo 'Usage: bash ops/restore.sh backups/FILE.dump rally_restore_NAME' >&2
  exit 2
fi
sha256sum -c "$1.sha256"
restore_db="$2"
docker compose --env-file .env.production -f compose.production.yaml exec -T postgres createdb -U rally "$restore_db"
docker compose --env-file .env.production -f compose.production.yaml exec -T postgres pg_restore -U rally -d "$restore_db" --no-owner --exit-on-error --single-transaction < "$1"
printf 'Restored into %s. Production database was not modified.\n' "$restore_db"
